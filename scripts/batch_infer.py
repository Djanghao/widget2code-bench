#!/usr/bin/env python3
import argparse
import concurrent.futures as futures
import datetime as dt
from zoneinfo import ZoneInfo
import json
import os
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from bs4 import BeautifulSoup
from PIL import Image

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from provider_hub import LLM, ChatMessage, prepare_image_content


def list_images(images_dir: Path) -> List[Path]:
    exts = {".png", ".jpg", ".jpeg", ".webp"}
    files = []
    for p in sorted(images_dir.iterdir()):
        if p.is_file() and p.suffix.lower() in exts:
            files.append(p)
    return files


def read_prompt_file(path: Path) -> Optional[str]:
    """Read prompt text from a Markdown file.

    The entire file content is used as the prompt text.
    """
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:
        return None


def collect_prompts(prompts_root: Path, includes: Optional[List[str]], excludes: Optional[List[str]]) -> List[Tuple[str, Path, str]]:
    items: List[Tuple[str, Path, str]] = []
    for category in sorted([p for p in prompts_root.iterdir() if p.is_dir()]):
        for md in sorted(category.glob("*.md")):
            rel = md.relative_to(prompts_root)
            rel_str = str(rel)
            if includes and not any(fnmatch(rel_str, pat) for pat in includes):
                continue
            if excludes and any(fnmatch(rel_str, pat) for pat in excludes):
                continue
            prompt_text = read_prompt_file(md)
            if not prompt_text:
                continue
            items.append((category.name, md, prompt_text))
    return items


def fnmatch(s: str, pat: str) -> bool:
    if pat == "*":
        return True
    if "*" not in pat:
        return s == pat
    parts = pat.split("*")
    i = 0
    for idx, part in enumerate(parts):
        if part == "":
            continue
        j = s.find(part, i)
        if j == -1:
            return False
        if idx == 0 and not pat.startswith("*") and j != 0:
            return False
        i = j + len(part)
    if not pat.endswith("*") and not s.endswith(parts[-1]):
        return False
    return True


def extract_code(content: str) -> str:
    s = content.strip()
    fence = re.match(r"^```([a-zA-Z0-9\-\+]*)\n([\s\S]*?)\n```\s*$", s)
    if fence:
        return fence.group(2).strip()
    return s


def decide_extension(code: str) -> str:
    starts = code.lstrip().lower()
    if starts.startswith("<html"):
        return ".html"
    if starts.startswith("export default function"):
        return ".jsx"
    if re.search(r"export\s+default\s+function\s+\w+\s*\(\)\s*\{", code):
        return ".jsx"
    return ".txt"


def prettify_html(code: str) -> str:
    """Format HTML using BeautifulSoup while failing gracefully."""
    try:
        soup = BeautifulSoup(code, "html.parser")
        pretty = soup.prettify()
    except Exception:
        return code
    if not pretty.endswith("\n"):
        pretty += "\n"
    return pretty

def build_size_constraint_text(image_path: Path, size_flag: bool, aspect_ratio_flag: bool) -> tuple[str, dict]:
    if not size_flag and not aspect_ratio_flag:
        return "", {}
    img = Image.open(image_path)
    width, height = img.size
    ratio = width / height
    size_info = {"width": width, "height": height, "aspect_ratio": round(ratio, 2)}
    if size_flag and aspect_ratio_flag:
        return f"The widget must match the screenshot size ({width}×{height} px) and maintain its aspect ratio (≈{ratio:.2f}:1) as closely as possible.", size_info
    elif size_flag:
        return f"The widget must match the screenshot size ({width}×{height} px) as closely as possible.", size_info
    else:
        return f"The widget must maintain the screenshot's aspect ratio (≈{ratio:.2f}:1) as closely as possible.", size_info

def run_one(
    image_path: Path,
    category: str,
    prompt_file: Path,
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
    thinking: Optional[bool],
    size_flag: bool,
    aspect_ratio_flag: bool,
) -> Tuple[Path, Optional[str], Optional[str]]:
    constraint_text, size_info = build_size_constraint_text(image_path, size_flag, aspect_ratio_flag)
    if constraint_text:
        prompt_text = prompt_text + "\n" + constraint_text

    out_cat = out_dir / category
    out_cat.mkdir(parents=True, exist_ok=True)
    base_name = prompt_file.stem
    meta_out_file = out_cat / f"{base_name}.meta.json"
    meta_data = {
        "prompt": prompt_text,
        "category": category,
        "prompt_file": str(prompt_file),
        "size_flag": size_flag,
        "aspect_ratio_flag": aspect_ratio_flag,
    }
    if size_info:
        meta_data["image_size"] = {"width": size_info["width"], "height": size_info["height"]}
        meta_data["aspect_ratio"] = size_info["aspect_ratio"]
    meta_out_file.write_text(json.dumps(meta_data, ensure_ascii=False, indent=2), encoding="utf-8")

    llm = LLM(
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
        timeout=timeout,
        thinking=thinking,
    )
    img = prepare_image_content(str(image_path))
    messages = [ChatMessage(role="user", content=[{"type": "text", "text": prompt_text}, img])]
    try:
        resp = llm.chat(messages, stream=False)
        raw = resp.content if hasattr(resp, "content") else str(resp)
    except Exception as e:
        return (prompt_file, None, f"ERROR: {e}")
    code = extract_code(raw)
    ext = decide_extension(code)
    expected_ext = ".html" if category.startswith("html") else ".jsx"
    file_ext = ext if ext in (".html", ".jsx") else expected_ext
    out_file = out_cat / f"{base_name}{file_ext}"
    formatted_code = code
    if file_ext == ".html":
        formatted_code = prettify_html(formatted_code)
    out_file.write_text(formatted_code, encoding="utf-8")
    return (out_file, formatted_code[:64], None)


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Batch widget2code inference using provider-hub")
    p.add_argument("--images-dir", required=True, help="Directory with images")
    p.add_argument("--prompts-root", default=str(Path("prompts").resolve()), help="Prompts root directory (expects .md files)")
    p.add_argument("--results-root", default=str(Path("results").resolve()), help="Results root directory")
    p.add_argument("--experiment", required=True, help="Experiment name suffix")
    p.add_argument("--threads", type=int, default=os.cpu_count() or 4, help="Max concurrent workers")
    p.add_argument("--model", default="doubao-seed-1-6-250615", help="Model id for provider-hub")
    p.add_argument("--provider", default=None, help="Provider override (e.g. 'openai_compatible', 'qwen', 'doubao', 'deepseek', 'openai')")
    p.add_argument("--api-key", dest="api_key", default=None, help="API key for provider (required for 'openai_compatible')")
    p.add_argument("--base-url", dest="base_url", default=None, help="Base URL for provider (required for 'openai_compatible')")
    p.add_argument("--temperature", type=float, default=0.2)
    p.add_argument("--top-p", type=float, default=0.9)
    p.add_argument("--max-tokens", type=int, default=1500)
    p.add_argument("--timeout", type=int, default=90)
    p.add_argument("--thinking", action="store_true", default=None, help="Enable provider thinking when supported")
    p.add_argument("--include", nargs="*", help="Optional glob filters relative to prompts root, e.g. 'react/*' 'html/1-*' ")
    p.add_argument("--exclude", nargs="*", help="Optional glob filters to exclude")
    p.add_argument("--suffix", default="", help="Optional extra suffix for run directory name")
    p.add_argument("--size", action="store_true", help="Append image size constraint to prompt")
    p.add_argument("--aspect-ratio", action="store_true", help="Append aspect ratio constraint to prompt")
    args = p.parse_args(argv)

    images_dir = Path(args.images_dir)
    prompts_root = Path(args.prompts_root)
    results_root = Path(args.results_root)
    if not images_dir.exists():
        print(f"Images dir not found: {images_dir}", file=sys.stderr)
        return 2
    if not prompts_root.exists():
        print(f"Prompts root not found: {prompts_root}", file=sys.stderr)
        return 2
    images = list_images(images_dir)
    if not images:
        print("No images found", file=sys.stderr)
        return 2
    prompts = collect_prompts(prompts_root, args.include, args.exclude)
    if not prompts:
        print("No prompts collected", file=sys.stderr)
        return 2

    ts = dt.datetime.now(ZoneInfo("America/Toronto")).strftime("%Y%m%d-%H%M%S")
    run_dir_name = f"{ts}-{args.experiment}{('-' + args.suffix) if args.suffix else ''}"
    run_dir = results_root / run_dir_name
    run_dir.mkdir(parents=True, exist_ok=True)

    meta = {
        "experiment": args.experiment,
        "provider": args.provider,
        "base_url": args.base_url,
        "model": args.model,
        "temperature": args.temperature,
        "top_p": args.top_p,
        "max_tokens": args.max_tokens,
        "timeout": args.timeout,
        "thinking": args.thinking,
        "images_dir": str(images_dir),
        "prompts_root": str(prompts_root),
        "include": args.include,
        "exclude": args.exclude,
        "size": args.size,
        "aspect_ratio": args.aspect_ratio,
        "created_at": ts,
    }
    (run_dir / "run.meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    tasks = []
    with futures.ThreadPoolExecutor(max_workers=args.threads) as pool:
        for img in images:
            image_id = img.stem
            out_dir = run_dir / image_id
            out_dir.mkdir(parents=True, exist_ok=True)
            try:
                dst = out_dir / f"source{img.suffix.lower()}"
                if not dst.exists():
                    dst.write_bytes(img.read_bytes())
            except Exception:
                pass
            for category, prompt_file, prompt_text in prompts:
                tasks.append(
                    pool.submit(
                        run_one,
                        img,
                        category,
                        prompt_file,
                        prompt_text,
                        out_dir,
                        args.model,
                        args.provider,
                        args.api_key,
                        args.base_url,
                        args.temperature,
                        args.top_p,
                        args.max_tokens,
                        args.timeout,
                        args.thinking,
                        args.size,
                        args.aspect_ratio,
                    )
                )

        ok = 0
        fail = 0
        for i, t in enumerate(futures.as_completed(tasks), start=1):
            out_path, preview, err = t.result()
            if err:
                fail += 1
                print(f"[{i}/{len(tasks)}] FAIL {out_path}: {err}")
            else:
                ok += 1
                print(f"[{i}/{len(tasks)}] OK   {out_path}")

    print(f"Done. Succeeded: {ok}, Failed: {fail}. Output: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
