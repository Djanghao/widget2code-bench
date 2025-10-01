#!/usr/bin/env python3
import json
import sys
from pathlib import Path

def backfill_meta(results_root: Path):
    for run_dir in results_root.iterdir():
        if not run_dir.is_dir():
            continue

        run_meta_file = run_dir / "run.meta.json"
        if not run_meta_file.exists():
            print(f"Skip {run_dir.name}: no run.meta.json")
            continue

        with open(run_meta_file) as f:
            run_meta = json.load(f)

        prompts_root = run_meta.get("prompts_root")
        if not prompts_root:
            print(f"Skip {run_dir.name}: no prompts_root in run.meta.json")
            continue

        prompts_root = Path(prompts_root)
        if not prompts_root.exists():
            print(f"Skip {run_dir.name}: prompts_root does not exist: {prompts_root}")
            continue

        size_flag = run_meta.get("size", False)
        aspect_ratio_flag = run_meta.get("aspect_ratio", False)

        for image_dir in run_dir.iterdir():
            if not image_dir.is_dir() or image_dir.name == "run.meta.json":
                continue

            for category_dir in image_dir.iterdir():
                if not category_dir.is_dir():
                    continue

                category = category_dir.name

                for code_file in category_dir.iterdir():
                    if code_file.suffix not in {".html", ".jsx", ".js"}:
                        continue

                    name = code_file.stem
                    meta_file = category_dir / f"{name}.meta.json"

                    if meta_file.exists():
                        continue

                    prompt_file = prompts_root / category / f"{name}.md"
                    if not prompt_file.exists():
                        print(f"Warning: prompt file not found: {prompt_file}")
                        continue

                    prompt_text = prompt_file.read_text(encoding="utf-8").strip()

                    meta_data = {
                        "prompt": prompt_text,
                        "category": category,
                        "prompt_file": str(prompt_file),
                        "size_flag": size_flag,
                        "aspect_ratio_flag": aspect_ratio_flag,
                    }

                    meta_file.write_text(json.dumps(meta_data, ensure_ascii=False, indent=2), encoding="utf-8")
                    print(f"Created: {meta_file.relative_to(results_root)}")

if __name__ == "__main__":
    results_root = Path(__file__).parent.parent / "results"
    if len(sys.argv) > 1:
        results_root = Path(sys.argv[1])

    print(f"Backfilling meta.json files in: {results_root}")
    backfill_meta(results_root)
    print("Done!")
