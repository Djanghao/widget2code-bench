"""Restart a benchmark daemon that exits or stops making progress."""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from . import bench_ipc as ipc


def read_heartbeat(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def diagnose(beat: dict | None, *, now: float, stall_s: float, silence_s: float) -> str | None:
    if beat is None:
        return None
    if now - beat.get("now", 0) > silence_s:
        return f"heartbeat is {now - beat.get('now', 0):.0f}s old (> {silence_s:.0f}s)"
    if beat.get("in_flight", 0) > 0 and now - beat.get("last_completed_at", 0) > stall_s:
        return (
            f"{beat['in_flight']} evaluation(s) outstanding and nothing completed for "
            f"{now - beat.get('last_completed_at', 0):.0f}s (> {stall_s:.0f}s)"
        )
    return None


def kill_process_group(pid: int) -> None:
    try:
        os.killpg(os.getpgid(pid), signal.SIGKILL)
    except Exception:
        try:
            os.kill(pid, signal.SIGKILL)
        except Exception:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-dir", type=Path, default=ipc.DEFAULT_RUNTIME_DIR)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--cuda", action="store_true")
    parser.add_argument("--stall-timeout", type=float, default=600.0)
    parser.add_argument("--silence-timeout", type=float, default=60.0)
    parser.add_argument("--poll", type=float, default=5.0)
    args = parser.parse_args()
    args.runtime_dir.mkdir(parents=True, exist_ok=True)
    heartbeat = ipc.heartbeat_path(args.runtime_dir)
    proc: subprocess.Popen | None = None
    stopping = False
    restarts = 0

    def _stop(*_):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)
    try:
        while not stopping:
            if proc is None or proc.poll() is not None:
                if proc is not None:
                    restarts += 1
                    print(f"supervisor: daemon exited with {proc.returncode}; restart #{restarts}", flush=True)
                heartbeat.unlink(missing_ok=True)
                command = [
                    sys.executable, "-u", "-m", "widget2code_bench.bench_daemon",
                    "--runtime-dir", str(args.runtime_dir), "--workers", str(args.workers),
                ]
                if args.cuda:
                    command.append("--cuda")
                proc = subprocess.Popen(command, start_new_session=True)
                print(f"supervisor: started daemon pid {proc.pid}", flush=True)
                deadline = time.time() + args.silence_timeout
                while time.time() < deadline and proc.poll() is None:
                    if read_heartbeat(heartbeat):
                        break
                    time.sleep(args.poll)
            time.sleep(args.poll)
            reason = diagnose(
                read_heartbeat(heartbeat), now=time.time(),
                stall_s=args.stall_timeout, silence_s=args.silence_timeout,
            )
            if reason and proc is not None and proc.poll() is None:
                print(f"supervisor: KILLING wedged daemon - {reason}", flush=True)
                kill_process_group(proc.pid)
                try:
                    proc.wait(timeout=30)
                except Exception:
                    pass
    finally:
        if proc is not None and proc.poll() is None:
            print("supervisor: stopping daemon", flush=True)
            try:
                proc.terminate()
                proc.wait(timeout=30)
            except Exception:
                kill_process_group(proc.pid)
    return 0


if __name__ == "__main__":
    sys.exit(main())
