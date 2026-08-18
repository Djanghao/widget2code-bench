"""Long-lived single-pair evaluator served over a Unix socket."""
from __future__ import annotations

import argparse
import asyncio
import json
import multiprocessing
import os
import signal
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from . import bench_ipc as ipc


HEARTBEAT_INTERVAL_S = 5.0


def _safe_suffix(name: str) -> str:
    suffix = Path(name).suffix.lower()
    return suffix if suffix in {".png", ".jpg", ".jpeg", ".webp", ".bmp"} else ".png"


def _evaluate_in_worker(
    gt_bytes: bytes,
    pred_bytes: bytes,
    gt_name: str,
    pred_name: str,
    metrics: str | None,
    use_cuda: bool,
) -> dict:
    # Import here so the supervisor/client side stays light and every worker
    # owns its own lazy EasyOCR/LPIPS model instances.
    from widget2code_bench.single import evaluate_single

    with tempfile.TemporaryDirectory(prefix="w2c-bench-") as tmp:
        root = Path(tmp)
        gt = root / f"gt{_safe_suffix(gt_name)}"
        pred = root / f"pred{_safe_suffix(pred_name)}"
        gt.write_bytes(gt_bytes)
        pred.write_bytes(pred_bytes)
        return evaluate_single(gt, pred, metrics=metrics, use_cuda=use_cuda)


class BenchDaemon:
    def __init__(self, *, runtime_dir: Path, workers: int, use_cuda: bool):
        self.runtime_dir = runtime_dir
        self.workers = workers
        self.use_cuda = use_cuda
        self._in_flight = 0
        self._completed = 0
        self._started_at = time.time()
        self._last_completed_at = time.time()
        self._stopping = asyncio.Event()
        self._pool: ProcessPoolExecutor | None = None

    def _write_heartbeat(self) -> None:
        payload = {
            "pid": os.getpid(),
            "started_at": self._started_at,
            "now": time.time(),
            "last_completed_at": self._last_completed_at,
            "in_flight": self._in_flight,
            "completed": self._completed,
            "workers": self.workers,
            "cuda": self.use_cuda,
        }
        path = ipc.heartbeat_path(self.runtime_dir)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload))
        os.replace(tmp, path)

    async def _heartbeat_loop(self) -> None:
        while not self._stopping.is_set():
            try:
                self._write_heartbeat()
            except Exception:
                pass
            try:
                await asyncio.wait_for(self._stopping.wait(), HEARTBEAT_INTERVAL_S)
            except asyncio.TimeoutError:
                pass

    async def _evaluate(self, request: dict) -> dict:
        if request.get("v") != ipc.PROTOCOL_VERSION:
            raise ValueError(
                f"protocol mismatch: daemon v{ipc.PROTOCOL_VERSION}, request v{request.get('v')}"
            )
        gt = ipc.image_bytes(request, "gt_b64")
        pred = ipc.image_bytes(request, "pred_b64")
        assert self._pool is not None
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self._pool,
            _evaluate_in_worker,
            gt,
            pred,
            str(request.get("gt_name") or "gt.png"),
            str(request.get("pred_name") or "pred.png"),
            request.get("metrics"),
            self.use_cuda,
        )

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            while True:
                line = await reader.readline()
                if not line:
                    return
                try:
                    request = ipc.decode(line)
                except Exception as exc:
                    writer.write(ipc.encode(ipc.failure(exc)))
                    await writer.drain()
                    return
                self._in_flight += 1
                try:
                    reply = ipc.success(await self._evaluate(request))
                except Exception as exc:
                    # A malformed/corrupt sample is an evaluation outcome; it
                    # must not kill the daemon or be retried forever.
                    reply = ipc.failure(exc)
                finally:
                    self._in_flight -= 1
                    self._completed += 1
                    self._last_completed_at = time.time()
                try:
                    writer.write(ipc.encode(reply))
                    await writer.drain()
                except (ConnectionResetError, BrokenPipeError):
                    return
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"bench-daemon: connection failed: {type(exc).__name__}: {exc}", flush=True)
        finally:
            try:
                writer.close()
            except Exception:
                pass

    async def run(self) -> None:
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        sock = ipc.socket_path(self.runtime_dir)
        sock.unlink(missing_ok=True)
        context = multiprocessing.get_context("spawn")
        self._pool = ProcessPoolExecutor(max_workers=self.workers, mp_context=context)
        server = await asyncio.start_unix_server(
            self._handle, path=str(sock), limit=ipc.STREAM_LIMIT, backlog=4096
        )
        heartbeat = asyncio.create_task(self._heartbeat_loop())
        print(
            f"bench-daemon: listening on {sock} "
            f"(pid {os.getpid()}, {self.workers} workers, cuda={self.use_cuda})",
            flush=True,
        )
        try:
            await self._stopping.wait()
        finally:
            heartbeat.cancel()
            server.close()
            await server.wait_closed()
            sock.unlink(missing_ok=True)
            self._pool.shutdown(wait=False, cancel_futures=True)
        print("bench-daemon: stopped", flush=True)

    def stop(self) -> None:
        self._stopping.set()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-dir", type=Path, default=ipc.DEFAULT_RUNTIME_DIR)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--cuda", action="store_true")
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("--workers must be at least 1")
    daemon = BenchDaemon(
        runtime_dir=args.runtime_dir, workers=args.workers, use_cuda=args.cuda
    )

    async def _run() -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, daemon.stop)
        await daemon.run()

    asyncio.run(_run())
    return 0


if __name__ == "__main__":
    sys.exit(main())
