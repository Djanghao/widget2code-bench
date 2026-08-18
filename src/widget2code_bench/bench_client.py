"""Pure-stdlib client for the long-lived benchmark daemon.

Infrastructure failures are retried across daemon restarts.  Invalid images or
metric selections are replies from a healthy evaluator and raise
``BenchEvaluationError`` immediately.
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path

from . import bench_ipc as ipc


RECONNECT_BACKOFF_S = (0.5, 1.0, 2.0, 4.0, 8.0, 15.0)
RECONNECT_ALARM_AFTER = 6


class BenchTransportError(RuntimeError):
    pass


class BenchEvaluationError(ValueError):
    pass


class BenchClient:
    """Evaluate image pairs without importing the numerical benchmark stack."""

    def __init__(self, runtime_dir: Path | None = None):
        self.socket_path = ipc.socket_path(runtime_dir)

    async def __aenter__(self) -> "BenchClient":
        return self

    async def __aexit__(self, *exc_info) -> None:
        return None

    async def evaluate(self, gt_path, pred_path, *, metrics: str | None = None) -> dict:
        gt = Path(gt_path)
        pred = Path(pred_path)
        return await self.evaluate_bytes(
            gt.read_bytes(), pred.read_bytes(), metrics=metrics,
            gt_name=gt.name, pred_name=pred.name,
        )

    async def evaluate_bytes(
        self,
        gt_bytes: bytes,
        pred_bytes: bytes,
        *,
        metrics: str | None = None,
        gt_name: str = "gt.png",
        pred_name: str = "pred.png",
    ) -> dict:
        reply = await self._exchange(ipc.build_request(
            gt_bytes, pred_bytes, metrics=metrics,
            gt_name=gt_name, pred_name=pred_name,
        ))
        if reply.get("v") != ipc.PROTOCOL_VERSION:
            raise BenchTransportError(
                f"benchmark protocol mismatch: client v{ipc.PROTOCOL_VERSION}, "
                f"daemon v{reply.get('v')}"
            )
        if not reply.get("ok"):
            raise BenchEvaluationError(
                f"{reply.get('error', 'evaluation error')}: {reply.get('message', '')}"
            )
        scores = reply.get("scores")
        if not isinstance(scores, dict):
            raise BenchTransportError("benchmark daemon returned no score dictionary")
        return scores

    async def _exchange(self, request: dict) -> dict:
        attempt = 0
        started = time.monotonic()
        while True:
            try:
                reader, writer = await asyncio.open_unix_connection(
                    str(self.socket_path), limit=ipc.STREAM_LIMIT
                )
            except (OSError, asyncio.TimeoutError) as exc:
                attempt += 1
                await self._wait(attempt, f"cannot connect: {exc}", started)
                continue
            try:
                writer.write(ipc.encode(request))
                await writer.drain()
                try:
                    line = await reader.readline()
                except ValueError as exc:
                    raise BenchTransportError(
                        f"reply exceeded bench_ipc.STREAM_LIMIT "
                        f"({ipc.STREAM_LIMIT // (1024 * 1024)} MB): {exc}"
                    ) from exc
                if not line:
                    raise ConnectionResetError("daemon closed the connection")
                return ipc.decode(line)
            except (OSError, ConnectionError, asyncio.IncompleteReadError) as exc:
                attempt += 1
                await self._wait(attempt, f"lost the daemon: {exc}", started)
            finally:
                try:
                    writer.close()
                except Exception:
                    pass

    async def _wait(self, attempt: int, reason: str, started: float) -> None:
        delay = RECONNECT_BACKOFF_S[min(attempt - 1, len(RECONNECT_BACKOFF_S) - 1)]
        if attempt >= RECONNECT_ALARM_AFTER:
            print(
                f"bench-client: STILL WAITING for {self.socket_path} - {reason} "
                f"(attempt {attempt}, {time.monotonic() - started:.0f}s so far)",
                flush=True,
            )
        await asyncio.sleep(delay)
