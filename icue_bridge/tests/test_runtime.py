"""End-to-end test of run_bridge with a fake `cuesdk` module and real UDP sockets."""

import enum
import json
import pathlib
import socket
import sys
import tempfile
import threading
import time
import types
import unittest
from dataclasses import dataclass
from types import SimpleNamespace

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import ledfx_icue_core as core  # noqa: E402

KB_LEDS = 4


class _State:
    writes = []
    fail_writes = False
    lock = threading.Lock()


class CorsairError(enum.IntEnum):
    CE_Success = 0
    CE_NotConnected = 1
    CE_NoControl = 2


class CorsairDeviceType(enum.IntEnum):
    CDT_Keyboard = 1
    CDT_All = 0xFFFFFFF


class CorsairAccessLevel(enum.IntEnum):
    CAL_Shared = 0
    CAL_ExclusiveLightingControl = 1


@dataclass
class CorsairLedColor:
    id: int
    r: int
    g: int
    b: int
    a: int


class CorsairDeviceFilter:
    def __init__(self, device_type_mask):
        self.device_type_mask = device_type_mask


class CueSdk:
    def connect(self, callback=None):
        return CorsairError.CE_Success

    def disconnect(self):
        return CorsairError.CE_Success

    def get_devices(self, filt):
        return [SimpleNamespace(device_id="kb")], CorsairError.CE_Success

    def get_led_positions(self, device_id):
        return [SimpleNamespace(id=i + 1, cx=float(i), cy=0.0) for i in range(KB_LEDS)], CorsairError.CE_Success

    def get_device_info(self, device_id):
        return SimpleNamespace(type=CorsairDeviceType.CDT_Keyboard, model="K70", serial="1"), CorsairError.CE_Success

    def set_layer_priority(self, priority):
        return CorsairError.CE_Success

    def request_control(self, device_id, level):
        return CorsairError.CE_Success

    def release_control(self, device_id=None):
        return CorsairError.CE_Success

    def set_led_colors(self, device_id, colors):
        with _State.lock:
            _State.writes.append([(c.r, c.g, c.b) for c in colors])
            fail = _State.fail_writes
        return CorsairError.CE_NotConnected if fail else CorsairError.CE_Success


def _fake_cuesdk_module():
    mod = types.ModuleType("cuesdk")
    for obj in (CueSdk, CorsairDeviceFilter, CorsairDeviceType, CorsairAccessLevel, CorsairLedColor, CorsairError):
        setattr(mod, obj.__name__, obj)
    return mod


class _StopWindow:
    """Stands in for the mode window: lets the test stop the main loop."""

    available = True

    def __init__(self):
        self.stop = threading.Event()

    def poll(self):
        return core._MODE_EXIT if self.stop.is_set() else None

    def notify_update(self, version, url):
        pass


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _dnrgb(start, rgb_bytes):
    return bytes([4, 1, start >> 8, start & 0xFF]) + bytes(rgb_bytes)


class RunBridgeTests(unittest.TestCase):
    def setUp(self):
        _State.writes = []
        _State.fail_writes = False
        self._saved = {
            "cuesdk": sys.modules.get("cuesdk"),
            "window": core._MODE_WINDOW,
            "setup_runtime": core.setup_runtime,
            "popen": core.subprocess.Popen,
            "exit": core.os._exit,
        }
        sys.modules["cuesdk"] = _fake_cuesdk_module()
        self.window = _StopWindow()
        core._MODE_WINDOW = self.window
        self.restarts = []

        def fake_exit(code):
            self.restarts.append(code)
            raise RuntimeError("restart requested")

        core.subprocess.Popen = lambda *a, **k: None
        core.os._exit = fake_exit
        self.tmp = tempfile.TemporaryDirectory()
        self.port = _free_port()
        cfg = {
            "udp_host": "127.0.0.1",
            "protocol": "drgb",
            "max_fps": 20,
            "startup_prompt": False,
            "default_mode": "unique",
            "clear_on_start": False,
            "process_priority": "normal",
            "cpu_affinity_core": None,
            "icue_watchdog": False,
            "icue_keepalive": False,
            "icue_apply_fail_threshold": 2,
            "icue_reconnect_cooldown": 0.0,
            "icue_reconnect_timeout": 1.0,
            "icue_update_mode": "direct",
            "keyboard_serpentine": False,
            "log_file": False,
            "log_level": "warning",
            "groups": [{"name": "clavier", "udp_port": self.port, "device_types_include": ["CDT_Keyboard"]}],
        }
        self.cfg_path = pathlib.Path(self.tmp.name) / "config.json"
        self.cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
        self.tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def tearDown(self):
        self.window.stop.set()
        if getattr(self, "thread", None):
            self.thread.join(timeout=5)
        self.tx.close()
        if self._saved["cuesdk"] is None:
            sys.modules.pop("cuesdk", None)
        else:
            sys.modules["cuesdk"] = self._saved["cuesdk"]
        core._MODE_WINDOW = self._saved["window"]
        core.setup_runtime = self._saved["setup_runtime"]
        core.subprocess.Popen = self._saved["popen"]
        core.os._exit = self._saved["exit"]
        self.tmp.cleanup()

    def _start(self):
        args = SimpleNamespace(
            config=str(self.cfg_path), list_devices=False, list_groups=False, test=False,
            test_color=None, debug_udp=False, debug_icue=False, perf_debug=False,
            perf_threshold=None, mode=None, group_port=None, fusion_port=None,
            fan_sweep=False, fan_index=1, fan_speed=0.08, fan_group="ventilos",
            fan_on=None, fan_color="255,255,255",
        )
        self.result = {}
        self.thread = threading.Thread(
            target=lambda: self.result.setdefault("code", core.run_bridge(args)), daemon=True
        )
        self.thread.start()
        self._wait_bound()

    def _wait_bound(self, timeout=5.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                probe.bind(("127.0.0.1", self.port))
            except OSError:
                return
            finally:
                probe.close()
            time.sleep(0.02)
        self.fail("bridge never bound its UDP port")

    def _send(self, packet):
        self.tx.sendto(packet, ("127.0.0.1", self.port))

    def _wait_for_write(self, expected, timeout=3.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with _State.lock:
                if _State.writes and _State.writes[-1] == expected:
                    return
            time.sleep(0.01)
        with _State.lock:
            last = _State.writes[-1] if _State.writes else None
        self.fail(f"expected last write {expected}, got {last}")

    def test_dnrgb_chunks_and_throttled_last_frame(self):
        self._start()
        # A frame split over two DNRGB packets must be applied in full.
        self._send(_dnrgb(0, [1, 1, 1, 2, 2, 2]))
        self._send(_dnrgb(2, [3, 3, 3, 4, 4, 4]))
        self._wait_for_write([(1, 1, 1), (2, 2, 2), (3, 3, 3), (4, 4, 4)])
        # Two frames inside one 50ms throttle window: the last one must still show.
        self._send(bytes([2, 1] + [9] * (KB_LEDS * 3)))
        self._send(bytes([2, 1] + [7] * (KB_LEDS * 3)))
        self._wait_for_write([(7, 7, 7)] * KB_LEDS)
        self.window.stop.set()
        self.thread.join(timeout=5)
        self.assertEqual(self.result.get("code"), 0)
        self.assertEqual(self.restarts, [])

    def test_config_change_is_hot_reloaded(self):
        self._start()
        new_port = _free_port()
        cfg = json.loads(self.cfg_path.read_text(encoding="utf-8"))
        cfg["groups"][0]["udp_port"] = new_port
        core.write_config(self.cfg_path, cfg)
        self.port = new_port
        self._wait_bound()
        self._send(bytes([2, 1] + [5] * (KB_LEDS * 3)))
        self._wait_for_write([(5, 5, 5)] * KB_LEDS)
        self.assertEqual(self.restarts, [])

    def test_identify_blinks_then_restores_frame(self):
        saved_seconds = core.IDENTIFY_SECONDS
        core.IDENTIFY_SECONDS = 0.8
        try:
            self._start()
            self._send(bytes([2, 1] + [9] * (KB_LEDS * 3)))
            self._wait_for_write([(9, 9, 9)] * KB_LEDS)
            with _State.lock:
                start = len(_State.writes)
            self.window.layout_backend.identify([("kb", 1)])
            # LedFx frames received meanwhile are held, then shown when it ends.
            self._send(bytes([2, 1] + [3] * (KB_LEDS * 3)))
            self._wait_for_write([(3, 3, 3)] * KB_LEDS)
            with _State.lock:
                history = _State.writes[start:]
            lit = [(0, 0, 0), (255, 255, 255), (0, 0, 0), (0, 0, 0)]
            self.assertIn(lit, history)
            # Nothing from LedFx was shown before the identification ended.
            self.assertLess(history.index(lit), history.index([(3, 3, 3)] * KB_LEDS))
        finally:
            core.IDENTIFY_SECONDS = saved_seconds

    def test_sweep_runs_band_in_given_order(self):
        self._start()
        self._send(bytes([2, 1] + [9] * (KB_LEDS * 3)))
        self._wait_for_write([(9, 9, 9)] * KB_LEDS)
        with _State.lock:
            start = len(_State.writes)
        self.window.layout_backend.sweep([("kb", 3), ("kb", 2), ("kb", 1), ("kb", 0)])
        self._send(bytes([2, 1] + [3] * (KB_LEDS * 3)))
        self._wait_for_write([(3, 3, 3)] * KB_LEDS)
        with _State.lock:
            history = _State.writes[start:]
        black, white = (0, 0, 0), (255, 255, 255)
        frames = [
            [black, black, black, white],  # band enters at the first LED of the order
            [black, black, white, white],
            [black, white, white, white],
            [white, white, white, white],
        ]
        positions = [history.index(f) for f in frames]
        self.assertEqual(positions, sorted(positions))
        self.assertLess(positions[-1], history.index([(3, 3, 3)] * KB_LEDS))

    def test_failed_reconnect_restores_runtime(self):
        real_setup = core.setup_runtime
        calls = {"n": 0}

        def flaky_setup(groups):
            calls["n"] += 1
            if calls["n"] == 2:  # the reconnect's bind attempt
                raise OSError("simulated bind failure")
            return real_setup(groups)

        core.setup_runtime = flaky_setup
        self._start()
        _State.fail_writes = True
        # Failing writes trigger a reconnect, whose new runtime fails to bind.
        deadline = time.monotonic() + 5.0
        i = 0
        while calls["n"] < 3 and time.monotonic() < deadline:
            self._send(bytes([2, 1] + [i % 200] * (KB_LEDS * 3)))
            i += 1
            time.sleep(0.06)
        self.assertGreaterEqual(calls["n"], 3, "old runtime was never restored")
        _State.fail_writes = False
        self._wait_bound()
        # The bridge must still be listening after the failed reconnect.
        self._send(bytes([2, 1] + [42] * (KB_LEDS * 3)))
        self._wait_for_write([(42, 42, 42)] * KB_LEDS)
        self.assertEqual(self.restarts, [])


if __name__ == "__main__":
    unittest.main()
