from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from homely.app import Runtime
from homely.display.framebus import HEADER
from homely.web.server import create_app


@pytest.fixture
def rt(tmp_path: Path):
    runtime = Runtime(
        config_path=tmp_path / "config.yaml", state_dir=tmp_path / "state", backend="none", start_pollers=False
    )
    yield runtime


@pytest.fixture
def client(rt: Runtime):
    app = create_app(rt, static_dir=Path("/nonexistent"))
    # TestClient runs the app's lifespan; start the runtime inside the loop it provides.
    with TestClient(app) as c:
        c.portal.call(rt.start)  # type: ignore[attr-defined]
        try:
            yield c
        finally:
            c.portal.call(rt.stop)  # type: ignore[attr-defined]


def test_health_and_fallback(client: TestClient):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"
    r = client.get("/")
    assert r.status_code == 200 and "homely is running" in r.text


def test_catalog_and_rotation(client: TestClient):
    cat = client.get("/api/modules").json()
    assert "clock" in [m["id"] for m in cat] and "weather" in [m["id"] for m in cat]
    assert cat[0]["schema"]["properties"]["time_format"]["enum"] == ["12h", "24h"]
    assert cat[0]["supports_current_size"] is True
    rot = client.get("/api/rotation").json()
    assert len(rot) == 1 and rot[0]["instance_id"] == "clock" and rot[0]["status"] == "ok"
    assert rot[0]["settings"]["time_format"] == "12h"


def test_settings_roundtrip_and_validation(client: TestClient, rt: Runtime):
    r = client.put("/api/rotation/clock/settings", json={"time_format": "24h", "time_color": "#FF0000"})
    assert r.status_code == 200, r.text
    assert r.json()["settings"]["time_format"] == "24h"
    assert rt.cfg.entry("clock").settings["time_format"] == "24h"
    # Persisted to disk
    assert "24h" in rt.config_path.read_text()

    r = client.put("/api/rotation/clock/settings", json={"time_format": "13h", "time_color": "red"})
    assert r.status_code == 422
    paths = {e["path"] for e in r.json()["errors"]}
    assert paths == {"time_format", "time_color"}

    r = client.put("/api/rotation/clock/settings", json={"bogus": 1})
    assert r.status_code == 422 and r.json()["errors"][0]["path"] == "bogus"

    r = client.put("/api/rotation/nope/settings", json={})
    assert r.status_code == 404


def test_patch_add_reorder_remove(client: TestClient):
    r = client.patch("/api/rotation/clock", json={"enabled": False, "duration_s": 42})
    assert r.json()["enabled"] is False and r.json()["duration_s"] == 42
    r = client.patch("/api/rotation/clock", json={"clear_duration": True})
    assert r.json()["duration_s"] is None

    r = client.post("/api/rotation", json={"module": "clock"})
    assert r.status_code == 409  # clock does not allow multiple instances
    r = client.post("/api/rotation", json={"module": "nope"})
    assert r.status_code == 404

    r = client.put("/api/rotation/order", json={"order": ["clock", "x"]})
    assert r.status_code == 400
    r = client.put("/api/rotation/order", json={"order": ["clock"]})
    assert r.status_code == 200

    assert client.post("/api/rotation/clock/pin", json={"pinned": True}).status_code == 204
    assert client.delete("/api/rotation/clock").status_code == 204
    assert client.get("/api/rotation").json() == []


def test_global_settings_and_brightness(client: TestClient, rt: Runtime):
    r = client.get("/api/settings")
    assert r.status_code == 200 and "rotation" in r.json()["schema"]
    r = client.put("/api/settings", json={"rotation": {"default_duration_s": 20, "transition": "cut"}})
    assert r.status_code == 200 and r.json()["rotation"]["default_duration_s"] == 20
    r = client.put("/api/settings", json={"rotation": {"transition": "wipe"}})
    assert r.status_code == 422
    r = client.put("/api/brightness", json={"level": 33})
    assert r.status_code == 200 and rt.cfg.brightness.level == 33
    r = client.put("/api/brightness", json={"level": 150})
    assert r.status_code == 422


def test_hardware_marks_restart_pending(client: TestClient, rt: Runtime):
    r = client.get("/api/hardware")
    assert r.json()["panel"]["hardware_mapping"] == "adafruit-hat"
    r = client.put("/api/hardware", json={"panel": {"hardware_mapping": "adafruit-hat-pwm", "gpio_slowdown": 3}})
    assert r.status_code == 200
    # The listener runs asynchronously; fetch system info a few times.
    import time

    for _ in range(50):
        if client.get("/api/system").json()["restart_pending"]:
            break
        time.sleep(0.02)
    assert client.get("/api/system").json()["restart_pending"] is True
    assert rt.cfg.panel.gpio_slowdown == 3


def test_system_state_actions(client: TestClient):
    info = client.get("/api/system").json()
    assert info["backend"] == "none" and info["size"] == "64x64"
    st = client.get("/api/state").json()
    assert "phase" in st and st["rotation"] == ["clock"]
    assert client.post("/api/system/actions/test-pattern").json()["ok"] is True
    assert client.post("/api/system/actions/next").json()["ok"] is True
    assert client.post("/api/system/actions/bogus").status_code == 422


def test_preview_and_events_ws(client: TestClient, rt: Runtime):
    import time

    for _ in range(100):  # wait for the render loop to publish a frame
        if rt.framebus.latest() is not None:
            break
        time.sleep(0.02)
    with client.websocket_connect("/api/ws/preview?fps=30") as ws:
        data = ws.receive_bytes()
        ver, enc, w, h, seq, _br = HEADER.unpack(data[: HEADER.size])
        assert (ver, enc, w, h) == (1, 0, 64, 64) and seq >= 1
        img = Image.open(io.BytesIO(data[HEADER.size :])).convert("RGB")
        assert img.size == (64, 64)
        assert any(img.getpixel((x, 10)) != (0, 0, 0) for x in range(64))  # clock digits are visible
    with client.websocket_connect("/api/ws/events") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "status" and msg["current"] == "clock"


def test_auth_when_enabled(rt: Runtime):
    rt.set_password("pw")
    rt.store.update(
        lambda c: c.model_copy(update={"web": c.web.model_copy(update={"auth_enabled": True})}), scope="web"
    )
    app = create_app(rt, static_dir=Path("/nonexistent"))
    with TestClient(app) as c:
        assert c.get("/api/health").status_code == 200
        assert c.get("/api/system").status_code == 401
        assert c.get("/api/system", auth=("homely", "wrong")).status_code == 401
        assert c.get("/api/system", auth=("homely", "pw")).status_code == 200


def test_geocode_proxies_and_caches(client: TestClient, rt: Runtime):
    import json

    import httpx

    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        assert request.url.params["name"] == "Minneapolis"
        return httpx.Response(200, json=json.loads(Path("tests/fixtures/open_meteo_geocode.json").read_text()))

    rt.http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    r = client.get("/api/geocode?q=Minneapolis&count=3")
    assert r.status_code == 200
    first = r.json()[0]
    assert first["name"] == "Minneapolis" and first["timezone"] == "America/Chicago"
    assert first["label"] == "Minneapolis, Minnesota, United States"
    assert abs(first["latitude"] - 44.98) < 0.01
    r2 = client.get("/api/geocode?q=minneapolis&count=3")
    assert r2.status_code == 200 and calls["n"] == 1  # served from cache
    assert client.get("/api/geocode?q=a").status_code == 422
