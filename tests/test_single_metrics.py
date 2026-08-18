import json
import asyncio
import time
from types import SimpleNamespace

import pytest
from PIL import Image, ImageDraw

from widget2code_bench import bench_ipc as ipc
from widget2code_bench.bench_client import BenchClient
from widget2code_bench.main import _run_single
from widget2code_bench.single import evaluate_single, parse_metric_selection
from widget2code_bench.supervisor import diagnose


def _image(path):
    image = Image.new("RGB", (96, 64), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((12, 10, 82, 52), fill=(30, 60, 90))
    draw.ellipse((30, 20, 55, 45), fill=(230, 100, 60))
    image.save(path)


def test_metric_selection_accepts_groups_and_aliases():
    selected = parse_metric_selection("ssim,geometry,contrast,palette")
    assert selected == {
        "perceptual": {"ssim"},
        "geometry": None,
        "legibility": {"ContrastDiff"},
        "style": {"PaletteDistance"},
    }


def test_metric_selection_rejects_unknown_names():
    with pytest.raises(ValueError, match="unknown metric"):
        parse_metric_selection("ssim,not-a-metric")


def test_selective_identity_evaluation_skips_unrequested_groups(tmp_path):
    path = tmp_path / "image.png"
    _image(path)
    result = evaluate_single(path, path, metrics="ssim,geometry,contrast")
    assert result == {
        "PerceptualScore": {"ssim": 1.0},
        "Geometry": {"geo_score": 100.0},
        "LegibilityScore": {"ContrastDiff": 100.0},
    }


def test_json_only_single_mode_is_machine_readable(tmp_path, capsys):
    path = tmp_path / "image.png"
    _image(path)
    _run_single(SimpleNamespace(
        gt_image=str(path),
        pred_image=str(path),
        metrics="ssim",
        cuda=False,
        json_only=True,
    ))
    assert json.loads(capsys.readouterr().out) == {
        "PerceptualScore": {"ssim": 1.0}
    }


def test_images_travel_over_the_wire_without_caller_paths(tmp_path):
    path = tmp_path / "image.png"
    _image(path)
    request = ipc.build_request(path.read_bytes(), path.read_bytes(), metrics="ssim")
    assert "gt_b64" in request and "pred_b64" in request
    assert "gt_path" not in request and "pred_path" not in request
    assert ipc.image_bytes(request, "gt_b64") == path.read_bytes()


def test_socket_client_evaluates_selected_metrics(tmp_path):
    path = tmp_path / "image.png"
    _image(path)
    seen = {}

    async def scenario():
        async def handle(reader, writer):
            seen.update(ipc.decode(await reader.readline()))
            writer.write(ipc.encode(ipc.success({
                "PerceptualScore": {"ssim": 1.0},
                "Geometry": {"geo_score": 100.0},
            })))
            await writer.drain()
            writer.close()

        server = await asyncio.start_unix_server(
            handle, path=str(ipc.socket_path(tmp_path)), limit=ipc.STREAM_LIMIT
        )
        async with server:
            return await BenchClient(tmp_path).evaluate(path, path, metrics="ssim,geometry")

    assert asyncio.run(scenario()) == {
        "PerceptualScore": {"ssim": 1.0},
        "Geometry": {"geo_score": 100.0},
    }
    assert set(seen).isdisjoint({"gt_path", "pred_path"})


def test_client_waits_for_daemon_start(tmp_path):
    path = tmp_path / "image.png"
    _image(path)

    async def scenario():
        client = BenchClient(tmp_path)
        pending = asyncio.create_task(client.evaluate(path, path, metrics="ssim"))
        await asyncio.sleep(0.8)
        assert not pending.done()

        async def handle(reader, writer):
            await reader.readline()
            writer.write(ipc.encode(ipc.success({"PerceptualScore": {"ssim": 1.0}})))
            await writer.drain()
            writer.close()

        server = await asyncio.start_unix_server(handle, path=str(ipc.socket_path(tmp_path)))
        async with server:
            return await asyncio.wait_for(pending, timeout=10)

    assert asyncio.run(scenario()) == {"PerceptualScore": {"ssim": 1.0}}


def test_client_retries_dropped_connection(tmp_path):
    path = tmp_path / "image.png"
    _image(path)
    attempts = 0

    async def scenario():
        async def handle(reader, writer):
            nonlocal attempts
            await reader.readline()
            attempts += 1
            if attempts == 1:
                writer.close()
                return
            writer.write(ipc.encode(ipc.success({"Geometry": {"geo_score": 100.0}})))
            await writer.drain()
            writer.close()

        server = await asyncio.start_unix_server(handle, path=str(ipc.socket_path(tmp_path)))
        async with server:
            return await asyncio.wait_for(
                BenchClient(tmp_path).evaluate(path, path, metrics="geometry"), timeout=10
            )

    assert asyncio.run(scenario()) == {"Geometry": {"geo_score": 100.0}}
    assert attempts == 2


def test_supervisor_only_kills_stalled_work():
    now = time.time()
    idle = {"now": now, "in_flight": 0, "last_completed_at": now - 10_000}
    stuck = {"now": now, "in_flight": 2, "last_completed_at": now - 700}
    assert diagnose(idle, now=now, stall_s=600, silence_s=60) is None
    assert "outstanding" in diagnose(stuck, now=now, stall_s=600, silence_s=60)
