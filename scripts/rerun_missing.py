#!/usr/bin/env python3
import argparse
import concurrent.futures as futures
import json
import sys
from pathlib import Path
from typing import List, Optional, Tuple
import os
import datetime as dt

# Import sibling helpers from batch_infer
try:
    # When executed as a script (python scripts/rerun_missing.py), this works
    import batch_infer  # type: ignore
except Exception as e:
    print(f"Failed to import batch_infer: {e}", file=sys.stderr)
    raise

# Use provider_hub directly to avoid re-writing meta.json
try:
    from provider_hub import LLM, ChatMessage, prepare_image_content  # type: ignore
except Exception as e:
    print(f"Failed to import provider_hub: {e}", file=sys.stderr)
    raise


def find_source_image(image_dir: Path) -> Optional[Path]:
    exts = {".png", ".jpg", ".jpeg", ".webp"}
    # Prefer saved copy named source.*
    for p in image_dir.iterdir():
        if p.is_file() and p.stem == "source" and p.suffix.lower() in exts:
            return p
    # Fallback: first image file in the folder
    for p in image_dir.iterdir():
        if p.is_file() and p.suffix.lower() in exts:
            return p
    return None


def code_exists(category_dir: Path, base_name: str) -> bool:
    # Accept any of these as a produced result
    for ext in (".html", ".jsx"):
        if (category_dir / f"{base_name}{ext}").exists():
            return True
    return False


def collect_missing(run_dir: Path) -> Tuple[dict, List[Tuple[Path, str, str, Path]]]:
    """Return (run_meta, tasks) where tasks are tuples:
    (image_dir, category, base_name, meta_file_path)
    Only includes items where output html/jsx is missing and a meta.json exists.
    """
    run_meta_file = run_dir / "run.meta.json"
    if not run_meta_file.exists():
        raise FileNotFoundError(f"run.meta.json not found in {run_dir}")
    run_meta = json.loads(run_meta_file.read_text(encoding="utf-8"))

    def base_from_meta(meta_path: Path) -> str:
        name = meta_path.name
        if name.endswith(".meta.json"):
            return name[: -len(".meta.json")]
        # Fallback: single stem
        return meta_path.stem

    tasks: List[Tuple[Path, str, str, Path]] = []
    for image_dir in sorted([p for p in run_dir.iterdir() if p.is_dir()]):
        if image_dir.name == "run.meta.json":
            continue
        for category_dir in sorted([p for p in image_dir.iterdir() if p.is_dir()]):
            category = category_dir.name
            for meta_file in sorted(category_dir.glob("*.meta.json")):
                base_name = base_from_meta(meta_file)
                if code_exists(category_dir, base_name):
                    continue
                tasks.append((image_dir, category, base_name, meta_file))

    return run_meta, tasks


def resolve_prompt_text_from_meta(meta_file: Path) -> Optional[str]:
    try:
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        return meta.get("prompt")
    except Exception:
        return None


def expected_extension_from_type(file_type: str) -> str:
    t = (file_type or "").lower()
    if t == "html":
        return ".html"
    if t == "jsx":
        return ".jsx"
    # default safe fallback
    return ".html"


def run_one_snapshot(
    image_path: Path,
    category: str,
    base_name: str,
    file_type: str,
    prompt_text: str,
    out_dir: Path,
    model: str,
    provider: Optional[str],
    api_key: Optional[str],
    base_url: Optional[str],
    temperature: float,
    top_p: float,
    max_tokens: int,
    timeout: int,
) -> Tuple[Path, Optional[str], Optional[str]]:
    # Build LLM
    llm = LLM(
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
        timeout=timeout,
    )
    img = prepare_image_content(str(image_path))
    messages = [ChatMessage(role="user", content=[{"type": "text", "text": prompt_text}, img])]
    try:
        resp = llm.chat(messages, stream=False)
        raw = resp.content if hasattr(resp, "content") else str(resp)
    except Exception as e:
        # Return a sensible path where it would have written
        out_cat = out_dir / category
        out_cat.mkdir(parents=True, exist_ok=True)
        return (out_cat / f"{base_name}{expected_extension_from_type(file_type)}", None, f"ERROR: {e}")

    code = batch_infer.extract_code(raw)
    expected_ext = expected_extension_from_type(file_type)
    # Strictly use meta-declared file_type for extension
    file_ext = expected_ext
    out_cat = out_dir / category
    out_cat.mkdir(parents=True, exist_ok=True)
    out_file = out_cat / f"{base_name}{file_ext}"
    formatted_code = code
    if file_ext == ".html":
        formatted_code = batch_infer.prettify_html(formatted_code)
    out_file.write_text(formatted_code, encoding="utf-8")
    return (out_file, formatted_code[:64], None)


def append_log(run_dir: Path, line: str) -> None:
    log_file = run_dir / "run.log"
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(line.rstrip("\n") + "\n")
    except Exception:
        pass


def log_line(run_dir: Path, tag: str, message: str) -> None:
    ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    append_log(run_dir, f"[{ts}] {tag:<12} | {message}")


def count_missing_all(run_dir: Path) -> int:
    _, tasks = collect_missing(run_dir)
    return len(tasks)


def rerun_missing(run_dir: Path, threads: int = 8, limit: Optional[int] = None, dry_run: bool = False, api_key_opt: Optional[str] = None) -> int:
    run_meta, tasks = collect_missing(run_dir)

    provider = run_meta.get("provider")
    base_url = run_meta.get("base_url")
    model = run_meta.get("model")
    temperature = float(run_meta.get("temperature", 0.2))
    top_p = float(run_meta.get("top_p", 0.9))
    max_tokens = int(run_meta.get("max_tokens", 1500))
    timeout = int(run_meta.get("timeout", 90))
    thinking = run_meta.get("thinking")
    size_flag = bool(run_meta.get("size", False))
    aspect_ratio_flag = bool(run_meta.get("aspect_ratio", False))

    # API key will be validated (if required) after optional dry-run
    api_key: Optional[str] = None

    print(f"Loaded run.meta.json from: {run_dir}")
    print(f"- Provider: {provider}  Model: {model}")
    print(f"- Base URL: {base_url}  size={size_flag} aspect_ratio={aspect_ratio_flag}")
    total_missing_before = count_missing_all(run_dir)
    print(f"- Missing items detected: {len(tasks)}")

    if limit is not None and len(tasks) > limit:
        tasks = tasks[:limit]
        print(f"- Limiting to first {limit} tasks")

    if dry_run:
        for image_dir, category, base_name, meta_file in tasks:
            # read file_type for display if present
            try:
                md = json.loads(meta_file.read_text(encoding="utf-8"))
                ft = md.get("file_type")
            except Exception:
                ft = None
            out_dir = image_dir
            suffix = f" ({ft})" if ft else ""
            print(f"DRY-RUN: would run {image_dir.name}/{category}/{base_name}{suffix}")
        return 0

    # Start log
    log_line(run_dir, "RERUN START", f"provider={provider} model={model} base_url={base_url}")
    log_line(run_dir, "RERUN PLAN", f"missing_before={total_missing_before} scheduled={len(tasks)} threads={threads}")
    for image_dir, category, base_name, meta_file in tasks:
        try:
            md = json.loads(meta_file.read_text(encoding="utf-8"))
            ft = md.get("file_type")
        except Exception:
            ft = None
        log_line(run_dir, "RERUN TASK", f"image={image_dir.name} category={category} name={base_name}{(f' file_type={ft}' if ft else '')}")

    # If nothing to do, record summary and return early
    if len(tasks) == 0:
        total_missing_after = count_missing_all(run_dir)
        log_line(run_dir, "RERUN DONE", f"ok=0 fail=0 missing_after={total_missing_after}")
        print("Nothing to re-run. Missing=0")
        return 0

    # Resolve API key: must be explicitly provided for openai_compatible
    if provider == "openai_compatible":
        if not api_key_opt:
            print("ERROR: --api-key is required for provider 'openai_compatible' and environment variables are not allowed.", file=sys.stderr)
            return 2
        api_key = api_key_opt

    ok = 0
    fail = 0
    with futures.ThreadPoolExecutor(max_workers=max(1, threads)) as pool:
        futs = []
        for image_dir, category, base_name, meta_file in tasks:
            img_path = find_source_image(image_dir)
            if not img_path:
                print(f"WARN: No source image found in {image_dir}")
                log_line(run_dir, "RERUN SKIP", f"image={image_dir.name} category={category} name={base_name} reason=no_source_image")
                continue
            prompt_text = resolve_prompt_text_from_meta(meta_file)
            if not prompt_text:
                print(f"WARN: Could not read prompt from meta: {meta_file}")
                log_line(run_dir, "RERUN SKIP", f"image={image_dir.name} category={category} name={base_name} reason=no_prompt_in_meta")
                continue
            try:
                md = json.loads(meta_file.read_text(encoding="utf-8"))
                file_type = md.get("file_type")
            except Exception:
                file_type = None
            if not file_type:
                print(f"ERROR: meta missing file_type, please run scripts/backfill_file_type.py: {meta_file}")
                log_line(run_dir, "RERUN SKIP", f"image={image_dir.name} category={category} name={base_name} reason=missing_file_type")
                continue
            futs.append(
                pool.submit(
                    run_one_snapshot,
                    img_path,
                    category,
                    base_name,
                    file_type,
                    prompt_text,
                    image_dir,
                    model,
                    provider,
                    api_key,
                    base_url,
                    temperature,
                    top_p,
                    max_tokens,
                    timeout,
                )
            )

        for i, t in enumerate(futures.as_completed(futs), start=1):
            out_path, preview, err = t.result()
            if err:
                fail += 1
                print(f"[{i}/{len(futs)}] FAIL {out_path}: {err}")
                log_line(run_dir, "RERUN FAIL", f"path={out_path} error={err}")
            else:
                ok += 1
                print(f"[{i}/{len(futs)}] OK   {out_path}")
                log_line(run_dir, "RERUN OK", f"path={out_path}")

    total_missing_after = count_missing_all(run_dir)
    log_line(run_dir, "RERUN DONE", f"ok={ok} fail={fail} missing_after={total_missing_after}")
    print(f"Re-run complete. Succeeded: {ok}, Failed: {fail}.")
    return 0 if fail == 0 else 1


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Re-run missing widget code generations for an existing run directory.")
    p.add_argument("--run-dir", required=True, help="Path to an existing run directory under results/")
    p.add_argument("--threads", type=int, default=8, help="Max concurrent workers")
    p.add_argument("--limit", type=int, default=None, help="Limit number of re-runs (for testing)")
    p.add_argument("--dry-run", action="store_true", help="Only print what would be re-run")
    p.add_argument("--api-key", dest="api_key", default=None, help="API key override (used for 'openai_compatible')")
    args = p.parse_args(argv)

    run_dir = Path(args.run_dir)
    if not run_dir.exists() or not run_dir.is_dir():
        print(f"Run dir not found: {run_dir}", file=sys.stderr)
        return 2

    return rerun_missing(run_dir, threads=args.threads, limit=args.limit, dry_run=args.dry_run, api_key_opt=args.api_key)


if __name__ == "__main__":
    raise SystemExit(main())
