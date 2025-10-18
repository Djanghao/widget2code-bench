#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple


def check_output_file_exists(meta_path: Path) -> Tuple[bool, str]:
    base_name = meta_path.stem.replace(".meta", "")
    parent = meta_path.parent

    html_file = parent / f"{base_name}.html"
    if html_file.exists():
        return True, str(html_file)

    jsx_file = parent / f"{base_name}.jsx"
    if jsx_file.exists():
        return True, str(jsx_file)

    return False, ""


def analyze_meta_file(meta_path: Path) -> Tuple[str, Dict]:
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception as e:
        return "invalid_meta", {"error": str(e), "path": str(meta_path)}

    has_output, output_path = check_output_file_exists(meta_path)

    # If output file doesn't exist, it needs rerun
    if not has_output:
        return "missing_output", {"path": str(meta_path)}

    # Check if there's an error in meta.json
    error = meta.get("error")
    if error:
        return "has_error", {"error": error, "path": str(meta_path), "output_path": output_path}

    # Output file exists and no error
    return "success", {"path": str(meta_path), "output_path": output_path}


def main(argv: List[str] = None) -> int:
    p = argparse.ArgumentParser(description="Check batch_infer results (works with old and new meta.json formats)")
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
        stats[status].append(info)

    total = len(meta_files)
    success_count = len(stats["success"])
    missing_output_count = len(stats["missing_output"])
    has_error_count = len(stats["has_error"])
    invalid_meta_count = len(stats["invalid_meta"])

    print(f"\n{'='*60}")
    print(f"Results Analysis for: {results_dir}")
    print(f"{'='*60}")
    print(f"Total tasks: {total}")
    print(f"✓ Success (has output file): {success_count} ({success_count/total*100:.1f}%)")
    print(f"✗ Missing output file: {missing_output_count} ({missing_output_count/total*100:.1f}%)")
    print(f"✗ Has error in meta.json: {has_error_count} ({has_error_count/total*100:.1f}%)")
    print(f"✗ Invalid meta.json: {invalid_meta_count} ({invalid_meta_count/total*100:.1f}%)")
    print(f"{'='*60}\n")

    if args.verbose:
        for status in ["missing_output", "has_error", "invalid_meta"]:
            items = stats[status]
            if items:
                print(f"\n{status.upper().replace('_', ' ')} ({len(items)} items):")
                print("-" * 60)
                for item in items[:10]:
                    print(f"  Path: {item['path']}")
                    if "error" in item:
                        print(f"  Error: {item['error'][:100]}...")
                    if "output_path" in item:
                        print(f"  Output: {item['output_path']}")
                    print()
                if len(items) > 10:
                    print(f"  ... and {len(items) - 10} more\n")

    missing_count = missing_output_count + has_error_count + invalid_meta_count
    if missing_count > 0:
        print(f"\nTo rerun missing items ({missing_count} total), use:")
        print(f"  python scripts/rerun_missing.py --run-dir {results_dir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
