#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path
from typing import List
import subprocess


def get_result_dirs(results_dir: Path) -> List[Path]:
    if not results_dir.exists():
        return []
    return sorted([d for d in results_dir.iterdir() if d.is_dir()], key=lambda x: x.name)


def check_single_run(run_dir: Path) -> dict:
    result = subprocess.run(
        [sys.executable, "scripts/check_results_v2.py", str(run_dir)],
        capture_output=True,
        text=True
    )

    lines = result.stdout.strip().split('\n')
    stats = {}

    for line in lines:
        if line.startswith('Total tasks:'):
            stats['total'] = int(line.split(':')[1].strip())
        elif line.startswith('✓ Success'):
            parts = line.split(':')[1].strip().split()
            stats['success'] = int(parts[0])
            stats['success_pct'] = parts[1].strip('()')
        elif line.startswith('✗ Missing output file:'):
            parts = line.split(':')[1].strip().split()
            stats['missing'] = int(parts[0])
        elif line.startswith('✗ Has error in meta.json:'):
            parts = line.split(':')[1].strip().split()
            stats['error'] = int(parts[0])
        elif line.startswith('✗ Invalid meta.json:'):
            parts = line.split(':')[1].strip().split()
            stats['invalid'] = int(parts[0])

    return stats


def main(argv: List[str] = None) -> int:
    p = argparse.ArgumentParser(description="Check all result directories")
    p.add_argument("--results-dir", default="results", help="Results parent directory (default: results)")
    p.add_argument("--filter", help="Filter run directories by substring")
    args = p.parse_args(argv)

    results_dir = Path(args.results_dir)
    if not results_dir.exists():
        print(f"Results directory not found: {results_dir}", file=sys.stderr)
        return 2

    run_dirs = get_result_dirs(results_dir)
    if not run_dirs:
        print(f"No run directories found in {results_dir}", file=sys.stderr)
        return 2

    if args.filter:
        run_dirs = [d for d in run_dirs if args.filter in d.name]
        if not run_dirs:
            print(f"No run directories match filter: {args.filter}", file=sys.stderr)
            return 2

    print(f"\n{'='*120}")
    print(f"Checking {len(run_dirs)} run directories in {results_dir}")
    print(f"{'='*120}\n")

    results = []
    for run_dir in run_dirs:
        print(f"Checking {run_dir.name}...", end=' ', flush=True)
        stats = check_single_run(run_dir)
        results.append((run_dir.name, stats))

        if stats.get('success', 0) == stats.get('total', 0):
            print(f"✓ {stats['success']}/{stats['total']}")
        else:
            failed = stats.get('total', 0) - stats.get('success', 0)
            print(f"✗ {stats['success']}/{stats['total']} (failed: {failed})")

    print(f"\n{'='*120}")
    print("Summary by Model")
    print(f"{'='*120}\n")

    model_stats = {}
    for run_name, stats in results:
        model = run_name.split('-test-')[0].split('-', 3)[-1] if '-test-' in run_name else 'unknown'

        if model not in model_stats:
            model_stats[model] = {
                'runs': 0,
                'total_tasks': 0,
                'success_tasks': 0,
                'failed_tasks': 0,
                'details': []
            }

        model_stats[model]['runs'] += 1
        model_stats[model]['total_tasks'] += stats.get('total', 0)
        model_stats[model]['success_tasks'] += stats.get('success', 0)
        model_stats[model]['failed_tasks'] += (stats.get('total', 0) - stats.get('success', 0))
        model_stats[model]['details'].append((run_name, stats))

    for model in sorted(model_stats.keys()):
        data = model_stats[model]
        success_rate = (data['success_tasks'] / data['total_tasks'] * 100) if data['total_tasks'] > 0 else 0

        print(f"{model.upper()}")
        print(f"  Runs: {data['runs']}")
        print(f"  Total tasks: {data['total_tasks']}")
        print(f"  Success: {data['success_tasks']} ({success_rate:.2f}%)")
        print(f"  Failed: {data['failed_tasks']}")

        failed_runs = [(name, stats) for name, stats in data['details']
                       if stats.get('success', 0) < stats.get('total', 0)]
        if failed_runs:
            print(f"  Failed runs:")
            for name, stats in failed_runs:
                failed = stats.get('total', 0) - stats.get('success', 0)
                print(f"    - {name}: {failed} tasks failed")
        print()

    print(f"{'='*120}\n")

    total_runs = len(results)
    perfect_runs = sum(1 for _, stats in results if stats.get('success', 0) == stats.get('total', 0))
    total_tasks = sum(stats.get('total', 0) for _, stats in results)
    total_success = sum(stats.get('success', 0) for _, stats in results)

    print(f"Overall Statistics:")
    print(f"  Total runs: {total_runs}")
    print(f"  Perfect runs (100% success): {perfect_runs} ({perfect_runs/total_runs*100:.1f}%)")
    print(f"  Total tasks across all runs: {total_tasks}")
    print(f"  Total successful tasks: {total_success} ({total_success/total_tasks*100:.2f}%)")
    print(f"  Total failed tasks: {total_tasks - total_success}")
    print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
