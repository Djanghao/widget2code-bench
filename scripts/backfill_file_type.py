#!/usr/bin/env python3
import json
import sys
from pathlib import Path
import argparse


def infer_type_from_category(category_dir: Path) -> str:
    name = category_dir.name.lower()
    return "html" if name.startswith("html") else "jsx"


def iter_run_dirs(root: Path):
    """Yield run directories. Accept either a results root or a single run dir."""
    # Case 1: root is a single run directory
    if (root / "run.meta.json").exists():
        yield root
        return
    # Case 2: root contains multiple run directories
    for p in sorted([p for p in root.iterdir() if p.is_dir()]):
        if (p / "run.meta.json").exists():
            yield p


def backfill(results_root: Path, dry_run: bool = False) -> int:
    updated = 0
    skipped = 0
    for run_dir in iter_run_dirs(results_root):
        run_meta = run_dir / "run.meta.json"
        for image_dir in sorted([p for p in run_dir.iterdir() if p.is_dir()]):
            for category_dir in sorted([p for p in image_dir.iterdir() if p.is_dir()]):
                file_type = infer_type_from_category(category_dir)
                for meta_file in sorted(category_dir.glob("*.meta.json")):
                    try:
                        data = json.loads(meta_file.read_text(encoding="utf-8"))
                    except Exception:
                        print(f"WARN: Could not parse json: {meta_file}")
                        continue
                    if data.get("file_type") == file_type:
                        skipped += 1
                        continue
                    # Update when missing or mismatched
                    data["file_type"] = file_type
                    if dry_run:
                        print(f"DRY-RUN: would set file_type={file_type} -> {meta_file}")
                        updated += 1
                        continue
                    meta_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                    print(f"Updated file_type={file_type}: {meta_file}")
                    updated += 1
    print(f"Done. Updated: {updated}, Skipped: {skipped}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Backfill file_type field in *.meta.json under results/")
    p.add_argument("--results-root", default=str(Path("results").resolve()))
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    root = Path(args.results_root)
    if not root.exists():
        print(f"Results root not found: {root}", file=sys.stderr)
        return 2
    return backfill(root, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
