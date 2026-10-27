import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from cryptography import x509
from numpy.typing import NDArray

from ledfx.api.phone import PhoneEndpoint
from ledfx.api.phone_ca import PhoneCaEndpoint
from ledfx.api.phone_page import PAGE, PhonePageEndpoint
from ledfx.effects.phone_paint import (
    CURSOR_TIMEOUT,
    Clear,
    Fill,
    Mark,
    PhonePaint,
    Stroke,
)
from tools import phone_cert

FPS = 60
RED = np.array([255.0, 0.0, 0.0])
BLUE = np.array([0.0, 0.0, 255.0])
Client = TestClient[web.Request, web.Application]


def make(count: int, **config: object) -> PhonePaint:
    effect = PhonePaint(MagicMock(), PhonePaint.config_model().model_validate(config))
    effect.pixels = np.zeros((count, 3))
    effect.on_activate(count)
    return effect


def frame(effect: PhonePaint) -> NDArray[np.float64]:
    effect.now += 1 / FPS
    effect.passed = 1 / FPS
    effect.render()
    pixels = effect.pixels
    assert pixels is not None
    return pixels


def run(effect: PhonePaint, seconds: float) -> NDArray[np.float64]:
    pixels = frame(effect)
    for _ in range(int(seconds * FPS) - 1):
        pixels = frame(effect)
    return pixels


def stroke(
    x: float | None,
    down: bool = True,
    color: NDArray[np.float64] = RED,
    size: float = 0.0,
    erase: bool = False,
    client: str = "a",
) -> Stroke:
    return Stroke(client=client, x=x, down=down, color=color, size=size, erase=erase)


def lit(pixels: NDArray[np.float64]) -> list[int]:
    return np.flatnonzero(pixels.max(axis=1) > 1).tolist()


@pytest.mark.parametrize("count", [1, 2, 7, 150, 37555])
def test_renders_valid_frames_at_any_length(count: int) -> None:
    effect = make(count, fade=1.0)
    for x in (0.0, 0.3, 1.0, None):
        effect.send(stroke(x, size=0.1))
        pixels = frame(effect)
        assert pixels.shape == (count, 3)
        assert pixels.min() >= 0
        assert pixels.max() <= 255
    effect.send(Mark(0.5))
    effect.send(Fill(BLUE))
    assert frame(effect).max() > 0


def test_paints_where_the_phone_points() -> None:
    effect = make(101, cursor=False)
    effect.send(stroke(0.5))
    pixels = frame(effect)
    assert lit(pixels) == [50]
    np.testing.assert_allclose(pixels[50], RED)


def test_a_fast_sweep_paints_a_continuous_line() -> None:
    effect = make(101, cursor=False)
    effect.send(stroke(0.1))
    effect.send(stroke(0.6))
    assert lit(frame(effect)) == list(range(10, 61))


def test_lifting_the_finger_breaks_the_line() -> None:
    effect = make(101, cursor=False)
    effect.send(stroke(0.1))
    effect.send(stroke(0.3, down=False))
    effect.send(stroke(0.6))
    assert lit(frame(effect)) == [10, 60]


def test_phones_paint_their_own_lines() -> None:
    effect = make(101, cursor=False)
    effect.send(stroke(0.1, client="a"))
    effect.send(stroke(0.9, client="b", color=BLUE))
    effect.send(stroke(0.2, client="a"))
    pixels = frame(effect)
    # a's line stops at 0.2 and never joins b's point
    assert lit(pixels) == [*range(10, 21), 90]
    np.testing.assert_allclose(pixels[90], BLUE)


def test_brush_size_is_a_share_of_the_strip() -> None:
    effect = make(100, cursor=False, softness=0.0)
    effect.send(stroke(0.5, size=0.2))
    # A brush a fifth of the strip wide, centred on position 49.5
    assert len(lit(frame(effect))) == 20


def test_screen_colors_keep_a_red_red() -> None:
    # The phone's red: on a screen, the faint green and blue barely show
    tinted = np.array([255.0, 42.0, 42.0])
    matched = make(101, cursor=False)
    raw = make(101, cursor=False, screen_colors=False)
    for effect in (matched, raw):
        effect.send(stroke(0.5, color=tinted))
    red = frame(matched)[50]
    assert red[0] == 255
    assert red[1:].max() < 7
    np.testing.assert_allclose(frame(raw)[50], tinted)


def test_the_eraser_wipes_paint() -> None:
    effect = make(101, cursor=False)
    effect.send(Fill(RED))
    effect.send(stroke(0.5, size=0.1, erase=True))
    pixels = frame(effect)
    assert pixels[50].max() == 0
    np.testing.assert_allclose(pixels[0], RED)


def test_clear_and_fill_the_whole_strip() -> None:
    effect = make(20, cursor=False)
    effect.send(Fill(BLUE))
    assert np.all(frame(effect) == BLUE)
    effect.send(Clear())
    assert frame(effect).max() == 0


def test_paint_stays_unless_it_fades() -> None:
    kept = make(20, cursor=False)
    faded = make(20, cursor=False, fade=1.0)
    for effect in (kept, faded):
        effect.send(Fill(RED))
        frame(effect)
    assert run(kept, 3).max() == 255
    assert run(faded, 3).max() < 255 * 0.1


def test_cursor_shows_the_aim_and_goes_when_the_phone_stops() -> None:
    effect = make(101, cursor_brightness=0.5)
    effect.send(stroke(0.5, down=False))
    pixels = frame(effect)
    assert lit(pixels) == [50]
    np.testing.assert_allclose(pixels[50], RED * 0.5)
    assert run(effect, CURSOR_TIMEOUT + 0.1).max() == 0


def test_cursor_is_hidden_off_the_strip_and_when_turned_off() -> None:
    effect = make(101)
    effect.send(stroke(None))
    assert frame(effect).max() == 0
    hidden = make(101, cursor=False)
    hidden.send(stroke(0.5, down=False))
    assert frame(hidden).max() == 0


def test_calibration_mark_blinks_at_its_spot() -> None:
    effect = make(101)
    effect.send(Mark(1.0))
    shown = [frame(effect)[100].max() > 0 for _ in range(FPS)]
    assert any(shown)
    assert not all(shown)
    effect.send(Mark(None))
    assert run(effect, 0.5).max() == 0


# ---------------------------------------------------------------- endpoint


def fake_ledfx(effect: object, config_dir: Path) -> MagicMock:
    painting = SimpleNamespace(
        id="wall", name="Mur", pixel_count=101, active=True, active_effect=effect
    )
    other = SimpleNamespace(
        id="desk", name="Bureau", pixel_count=10, active=False, active_effect=None
    )
    strips = {"wall": painting, "desk": other}
    ledfx = MagicMock()
    ledfx.virtuals.get.side_effect = strips.get
    ledfx.virtuals.values.return_value = list(strips.values())
    ledfx.config_dir = str(config_dir)
    ledfx.port_s = 8900
    return ledfx


def test_dispatch_hands_strokes_to_the_named_strip(tmp_path: Path) -> None:
    effect = make(101, cursor=False)
    endpoint = PhoneEndpoint(fake_ledfx(effect, tmp_path))
    message = {"t": "p", "v": "wall", "x": 0.5, "d": True, "c": "#0000ff", "s": 0}
    assert endpoint.dispatch("phone", json.dumps(message)) == "wall"
    np.testing.assert_allclose(frame(effect)[50], BLUE)


@pytest.mark.parametrize(
    "data",
    [
        "not json",
        '{"t": "p", "v": "wall", "x": 1.5}',
        '{"t": "p", "v": "wall", "x": 0.5, "c": "not a color"}',
        '{"t": "explode", "v": "wall"}',
        '{"t": "clear"}',
    ],
)
def test_dispatch_ignores_malformed_messages(tmp_path: Path, data: str) -> None:
    effect = make(101)
    endpoint = PhoneEndpoint(fake_ledfx(effect, tmp_path))
    assert endpoint.dispatch("phone", data) is None
    assert frame(effect).max() == 0


def test_dispatch_leaves_strips_running_other_effects_alone(tmp_path: Path) -> None:
    endpoint = PhoneEndpoint(fake_ledfx(make(101), tmp_path))
    assert endpoint.dispatch("phone", '{"t": "clear", "v": "desk"}') == "desk"
    assert endpoint.dispatch("phone", '{"t": "clear", "v": "nowhere"}') == "nowhere"


async def client_for(ledfx: MagicMock) -> Client:
    app = web.Application()
    for endpoint in (PhoneEndpoint, PhonePageEndpoint, PhoneCaEndpoint):
        app.router.add_route("GET", endpoint.ENDPOINT_PATH, endpoint(ledfx).handler)
    client = TestClient(TestServer(app))
    await client.start_server()
    return client


async def test_status_lists_the_strips(tmp_path: Path) -> None:
    client = await client_for(fake_ledfx(make(101), tmp_path))
    try:
        response = await client.get("/api/phone")
        body = await response.json()
    finally:
        await client.close()
    assert [s["id"] for s in body["virtuals"]] == ["wall", "desk"]
    assert body["virtuals"][1] == {
        "id": "desk",
        "name": "Bureau",
        "pixels": 10,
        "active": False,
        "effect": None,
    }
    # No certificate in the config directory, so no HTTPS address to offer
    assert body["phone_url"] is None


async def test_socket_paints_and_reports_a_strip_taken_back(tmp_path: Path) -> None:
    effect = make(101, cursor=False)
    client = await client_for(fake_ledfx(effect, tmp_path))
    try:
        socket = await client.ws_connect("/api/phone")
        await socket.send_json({"t": "p", "v": "wall", "x": 0.5, "d": True, "s": 0})
        # Two messages to a strip that is not painting: one notice, not two
        await socket.send_json({"t": "clear", "v": "desk"})
        await socket.send_json({"t": "clear", "v": "desk"})
        notice = await socket.receive_json(timeout=2)
        await socket.close()
    finally:
        await client.close()
    assert notice == {"t": "idle", "v": "desk"}
    assert lit(frame(effect)) == [50]


async def test_page_and_authority_are_served(tmp_path: Path) -> None:
    client = await client_for(fake_ledfx(make(101), tmp_path))
    try:
        page = await client.get("/phone")
        assert page.status == 200
        assert "Pinceau LED" in await page.text()
        assert (await client.get("/phone/ca.crt")).status == 404
        phone_cert.ensure(tmp_path)
        authority = await client.get("/phone/ca.crt")
        assert authority.status == 200
        assert (await authority.read()) == (tmp_path / "ssl" / "ca.crt").read_bytes()
        status = await (await client.get("/api/phone")).json()
        assert status["phone_url"].endswith(":8900/phone")
    finally:
        await client.close()


def test_page_file_ships_with_the_package() -> None:
    assert Path(PAGE).is_file()


# ---------------------------------------------------------------- certificate


def test_certificate_is_issued_once_by_the_local_authority(tmp_path: Path) -> None:
    assert phone_cert.ensure(tmp_path).startswith("certificate issued")
    assert phone_cert.ensure(tmp_path) == "certificate up to date"
    ssl_dir = tmp_path / "ssl"
    authority = x509.load_pem_x509_certificate((ssl_dir / "ca.crt").read_bytes())
    chain = x509.load_pem_x509_certificates((ssl_dir / "fullchain.pem").read_bytes())
    leaf = chain[0]
    assert chain[1] == authority
    leaf.verify_directly_issued_by(authority)
    names = leaf.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    assert "127.0.0.1" in {str(ip) for ip in names.get_values_for_type(x509.IPAddress)}
    # The authority may only vouch for private addresses and this PC's names
    constraints = authority.extensions.get_extension_for_class(x509.NameConstraints)
    assert constraints.critical


def test_certificate_reuses_an_existing_authority(tmp_path: Path) -> None:
    phone_cert.ensure(tmp_path)
    ssl_dir = tmp_path / "ssl"
    authority = (ssl_dir / "ca.crt").read_bytes()
    (ssl_dir / "fullchain.pem").unlink()
    phone_cert.ensure(tmp_path)
    assert (ssl_dir / "ca.crt").read_bytes() == authority
    leaf = x509.load_pem_x509_certificates((ssl_dir / "fullchain.pem").read_bytes())[0]
    leaf.verify_directly_issued_by(x509.load_pem_x509_certificate(authority))
