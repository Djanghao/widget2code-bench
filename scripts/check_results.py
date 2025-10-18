#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple


def analyze_meta_file(meta_path: Path) -> Tuple[str, Dict]:
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception as e:
        return "invalid_meta", {"error": str(e), "path": str(meta_path)}

    response = meta.get("response")
    error = meta.get("error")

    if error:
        return "request_failed", {"error": error, "path": str(meta_path)}

    if response is None:
        return "response_none", {"path": str(meta_path)}

    content = response.get("content") if isinstance(response, dict) else None

    if content is None or content == "" or content == "None":
        return "content_empty", {"path": str(meta_path), "response": response}

    return "success", {"path": str(meta_path), "content_length": len(content)}


def check_html_file_exists(meta_path: Path) -> bool:
    base_name = meta_path.stem.replace(".meta", "")
    parent = meta_path.parent
    html_file = parent / f"{base_name}.html"
    jsx_file = parent / f"{base_name}.jsx"
    return html_file.exists() or jsx_file.exists()


def main(argv: List[str] = None) -> int:
    p = argparse.ArgumentParser(description="Check batch_infer results and categorize outcomes")
    p.add_argument("results_dir", help="Results directory to analyze")
    p.add_argument("--verbose", "-v", action="store_true", help="Show detailed information")
    args = p.parse_args(argv)

    results_dir = Path(args.results_dir)
    if not results_dir.exists():
        print(f"Results directory not found: {results_dir}", file=sys.stderr)
        return 2

    meta_files = list(results_dir.rglob("*.meta.json"))
    if not meta_files:
        print(f"No meta.json files found in {results_dir}", file=sys.stderr)
        return 2

    # Filter out run.meta.json
    meta_files = [f for f in meta_files if f.name != "run.meta.json"]
    if not meta_files:
        print(f"No task meta.json files found in {results_dir}", file=sys.stderr)
        return 2

    stats = defaultdict(list)

    for meta_path in meta_files:
        status, info = analyze_meta_file(meta_path)
        info["has_output_file"] = check_html_file_exists(meta_path)
        stats[status].append(info)

    total = len(meta_files)
    success_count = len(stats["success"])
    request_failed_count = len(stats["request_failed"])
    response_none_count = len(stats["response_none"])
    content_empty_count = len(stats["content_empty"])
    invalid_meta_count = len(stats["invalid_meta"])

    print(f"\n{'='*60}")
    print(f"Results Analysis for: {results_dir}")
    print(f"{'='*60}")
    print(f"Total tasks: {total}")
    print(f"✓ Success (got HTML/JSX): {success_count} ({success_count/total*100:.1f}%)")
    print(f"✗ Request failed (exception): {request_failed_count} ({request_failed_count/total*100:.1f}%)")
    print(f"✗ Response is None: {response_none_count} ({response_none_count/total*100:.1f}%)")
    print(f"✗ Content empty/None: {content_empty_count} ({content_empty_count/total*100:.1f}%)")
    print(f"✗ Invalid meta.json: {invalid_meta_count} ({invalid_meta_count/total*100:.1f}%)")
    print(f"{'='*60}\n")

    if args.verbose:
        for status, items in stats.items():
            if items and status != "success":
                print(f"\n{status.upper()} ({len(items)} items):")
                print("-" * 60)
                for item in items[:10]:
                    print(f"  Path: {item['path']}")
                    if "error" in item:
                        print(f"  Error: {item['error'][:100]}...")
                    print()
                if len(items) > 10:
                    print(f"  ... and {len(items) - 10} more\n")

    missing_count = request_failed_count + response_none_count + content_empty_count + invalid_meta_count
    if missing_count > 0:
        print(f"\nTo rerun missing items ({missing_count} total), use:")
        print(f"  python scripts/rerun_missing.py {results_dir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
