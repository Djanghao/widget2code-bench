"""Versioned wire contract for the shared benchmark daemon.

Both images cross the Unix socket as bytes.  The daemon never reads a caller's
filesystem, so the container only needs the small runtime-directory mount that
holds the socket and heartbeat.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any, Mapping


PROTOCOL_VERSION = 1
STREAM_LIMIT = 64 * 1024 * 1024
DEFAULT_RUNTIME_DIR = Path(os.environ.get("W2C_BENCH_RUNTIME_DIR", "/tmp/w2c-bench"))


def socket_path(runtime_dir: Path | None = None) -> Path:
    return (runtime_dir or DEFAULT_RUNTIME_DIR) / "bench.sock"


def heartbeat_path(runtime_dir: Path | None = None) -> Path:
    return (runtime_dir or DEFAULT_RUNTIME_DIR) / "heartbeat.json"


def encode(message: Mapping[str, Any]) -> bytes:
    return (json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n").encode()


def decode(line: bytes) -> dict[str, Any]:
    return json.loads(line.decode("utf-8"))


def build_request(
    gt_bytes: bytes,
    pred_bytes: bytes,
    *,
    metrics: str | None = None,
    gt_name: str = "gt.png",
    pred_name: str = "pred.png",
) -> dict[str, Any]:
    return {
        "v": PROTOCOL_VERSION,
        "gt_b64": base64.b64encode(gt_bytes).decode("ascii"),
        "pred_b64": base64.b64encode(pred_bytes).decode("ascii"),
        "gt_name": Path(gt_name).name,
        "pred_name": Path(pred_name).name,
        "metrics": metrics,
    }


def image_bytes(message: Mapping[str, Any], key: str) -> bytes:
    payload = message.get(key)
    if not isinstance(payload, str) or not payload:
        raise ValueError(f"request is missing non-empty {key}")
    return base64.b64decode(payload, validate=True)


def success(scores: Mapping[str, Any]) -> dict[str, Any]:
    return {"v": PROTOCOL_VERSION, "ok": True, "scores": dict(scores)}


def failure(exc: Exception) -> dict[str, Any]:
    return {
        "v": PROTOCOL_VERSION,
        "ok": False,
        "error": type(exc).__name__,
        "message": str(exc),
    }
