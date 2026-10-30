import json
import logging
import os
import pathlib
import socket
import sys
import tempfile
import time
import unittest
from dataclasses import dataclass
from types import SimpleNamespace

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import ledfx_icue_core as core  # noqa: E402


# --- Fake iCUE SDK ---------------------------------------------------------


class FakeError:
    CE_Success = 0
    CE_NoControl = 2


class FakeDeviceType:
    CDT_Keyboard = 1
    CDT_Mouse = 2
    CDT_Mousemat = 4
    CDT_MemoryModule = 8
    CDT_Cooler = 16
    CDT_LedController = 32
    CDT_Fan = 64
    CDT_All = 0xFFFFFFFF


@dataclass
class FakeColor:
    id: int
    r: int
    g: int
    b: int
    a: int


class FakeSdk:
    CorsairError = FakeError
    CorsairDeviceType = FakeDeviceType
    CorsairLedColor = FakeColor
    CorsairSessionState = None

    def __init__(self, devices=None, fail_writes=False):
        # devices: {device_id: (type, [(x, y), ...], model)}
        self.devices = devices or {}
        self.fail_writes = fail_writes
        self.writes = []

    def get_devices(self, mask):
        return [SimpleNamespace(device_id=d) for d in self.devices], FakeError.CE_Success

    def get_led_positions(self, device_id):
        _, coords, _ = self.devices[device_id]
        return [SimpleNamespace(id=100 + i, cx=x, cy=y) for i, (x, y) in enumerate(coords)], 0

    def get_device_info(self, device_id):
        dtype, _, model = self.devices[device_id]
        return SimpleNamespace(type=dtype, model=model, serial=f"SN-{device_id}"), 0

    def set_led_colors(self, device_id, colors):
        self.writes.append((device_id, [(c.id, c.r, c.g, c.b) for c in colors]))
        return 1 if self.fail_writes else FakeError.CE_Success

    set_led_colors_buffer = set_led_colors

    def flush(self):
        return FakeError.CE_Success

    def request_control(self, device_id, access_level=None):
        return FakeError.CE_Success

    def is_success(self, err):
        return err is None or int(err) == 0


def make_mapper(devices, **kwargs):
    sdk = FakeSdk(devices, **kwargs)
    mapper = core.LedMapper(sdk, FakeDeviceType.CDT_All)
    mapper.enumerate(clear_on_start=False)
    return sdk, mapper


# --- Protocol parsing ------------------------------------------------------


class ProtocolTests(unittest.TestCase):
    def test_drgb_full_frame(self):
        fb = bytearray(6)
        ready, is_ddp = core.parse_udp_packet("wled", bytes([2, 1, 10, 20, 30, 40, 50, 60]), fb)
        self.assertTrue(ready)
        self.assertFalse(is_ddp)
        self.assertEqual(fb, bytearray([10, 20, 30, 40, 50, 60]))

    def test_drgb_short_frame_clears_tail(self):
        fb = bytearray([9] * 6)
        core.parse_wled_or_raw(bytes([2, 1, 1, 2, 3]), fb)
        self.assertEqual(fb, bytearray([1, 2, 3, 0, 0, 0]))

    def test_dnrgb_chunks_are_all_applied(self):
        # LedFx splits large frames into several DNRGB packets (start index in bytes 2-3).
        fb = bytearray(4 * 3)
        chunk1 = bytes([4, 1, 0, 0]) + bytes([1, 1, 1, 2, 2, 2])
        chunk2 = bytes([4, 1, 0, 2]) + bytes([3, 3, 3, 4, 4, 4])
        ready, _ = core.ingest_udp_packets("wled", [chunk1, chunk2], fb)
        self.assertTrue(ready)
        self.assertEqual(fb, bytearray([1, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4]))

    def test_dnrgb_write_ending_on_boundary(self):
        fb = bytearray(6)
        core.parse_wled_or_raw(bytes([4, 1, 0, 1, 7, 8, 9]), fb)
        self.assertEqual(fb, bytearray([0, 0, 0, 7, 8, 9]))

    def test_warls(self):
        fb = bytearray(9)
        core.parse_wled_or_raw(bytes([1, 1, 2, 5, 6, 7, 9, 1, 1, 1]), fb)
        self.assertEqual(fb, bytearray([0, 0, 0, 0, 0, 0, 5, 6, 7]))

    def test_ddp_push_flag(self):
        fb = bytearray(6)
        header = bytes([0x40, 0, 0, 0]) + (3).to_bytes(4, "big") + (3).to_bytes(2, "big")
        ready, is_ddp = core.parse_udp_packet("wled", header + bytes([1, 2, 3]), fb)
        self.assertTrue(is_ddp)
        self.assertFalse(ready)
        self.assertEqual(fb, bytearray([0, 0, 0, 1, 2, 3]))
        pushed = bytes([0x41]) + header[1:]
        ready, _ = core.parse_udp_packet("ddp", pushed + bytes([4, 5, 6]), fb)
        self.assertTrue(ready)

    def test_wled_packets_are_not_ddp(self):
        for proto in (1, 2, 3, 4):
            self.assertFalse(core.looks_like_ddp(bytes([proto, 1] + [0] * 30)))

    def test_raw_ignores_partial_pixels(self):
        fb = bytearray(6)
        self.assertEqual(core.parse_udp_packet("raw", bytes([1, 2, 3, 4]), fb), (False, False))
        self.assertEqual(core.parse_udp_packet("raw", bytes([1, 2, 3]), fb), (True, False))
        self.assertEqual(fb[:3], bytearray([1, 2, 3]))

    def test_read_udp_packets_drains_socket(self):
        rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            rx.bind(("127.0.0.1", 0))
            rx.setblocking(False)
            for i in range(3):
                tx.sendto(bytes([i]), rx.getsockname())
            time.sleep(0.05)
            self.assertEqual(core.read_udp_packets(rx), [b"\x00", b"\x01", b"\x02"])
            self.assertEqual(core.read_udp_packets(rx), [])
        finally:
            rx.close()
            tx.close()


# --- Pure helpers ----------------------------------------------------------


class HelperTests(unittest.TestCase):
    def test_disconnect_keeps_session_callback_alive(self):
        # cuesdk clears its ctypes callback before CorsairDisconnect, which still calls it.
        callback = object()

        class Sdk:
            session_state_changed_event_handler = callback

            def disconnect(self):
                self.session_state_changed_event_handler = None
                return 0

        wrapper = object.__new__(core.CueSdkWrapper)
        wrapper.sdk = Sdk()
        self.assertEqual(wrapper.disconnect(), 0)
        self.assertIn(callback, core._SDK_CALLBACKS)

    def test_removed_update_keys_are_accepted_silently(self):
        logger = logging.getLogger("test.obsolete")
        cfg = {"update_check_enabled": True, "update_check_interval_seconds": 30, "update_repo": "a/b"}
        self.assertEqual(core.validate_config(cfg, logger), 0)

    def test_strip_mode_args(self):
        argv = ["app.py", "--mode", "group", "--debug-udp", "--mode=fusion"]
        self.assertEqual(core._strip_mode_args(argv), ["app.py", "--debug-udp"])

    def test_transform_points(self):
        pos = [{"x": 1, "y": 2}, {"x": 3, "y": 4}]
        self.assertEqual(core._transform_points(pos, flip_x=True, swap_xy=True), [(0, 2.0, -1.0), (1, 4.0, -3.0)])
        self.assertIsNone(core._transform_points([{"x": 1, "y": None}]))
        self.assertIsNone(core._transform_points([]))

    def test_serpentine_order(self):
        # 2 rows of 3 LEDs, given in scrambled order.
        pos = [{"x": x, "y": y} for x, y in [(2, 0), (0, 0), (1, 0), (0, 1), (2, 1), (1, 1)]]
        order = core._compute_serpentine_led_order(pos, mode="serpentine")
        self.assertEqual(order, [1, 2, 0, 4, 5, 3])
        linear = core._compute_serpentine_led_order(pos, mode="linear")
        self.assertEqual(linear, [1, 2, 0, 3, 5, 4])

    def test_build_lut(self):
        lut = core.build_lut(0.5, 1.0)
        self.assertEqual((lut[0], lut[255]), (0, 128))

    def test_cfg_number_fallback(self):
        logger = logging.getLogger("test.cfg")
        with self.assertLogs(logger, level="WARNING"):
            self.assertEqual(core._cfg_float({"max_fps": "abc"}, "max_fps", 60, logger=logger), 60.0)
        self.assertEqual(core._cfg_int({"x": 500}, "x", 1, maximum=255), 255)
        self.assertEqual(core._cfg_float({"x": None}, "x", 2.5), 2.5)

    def test_validate_config_suggests_typo(self):
        logger = logging.getLogger("test.validate")
        cfg = {"max_fsp": 60, "groups": [{"name": "a", "udp_port": 70000, "protocl": "ddp"}]}
        with self.assertLogs(logger, level="WARNING") as logs:
            self.assertEqual(core.validate_config(cfg, logger), 3)
        text = "\n".join(logs.output)
        self.assertIn("max_fps", text)
        self.assertIn("protocol", text)

    def test_shipped_config_is_valid(self):
        cfg = core.load_config(pathlib.Path(__file__).resolve().parent.parent / "config.json")
        self.assertEqual(core.validate_config(cfg, logging.getLogger("test.shipped")), 0)

    def test_persist_config_value_keeps_other_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "config.json"
            path.write_text(json.dumps({"a": 1, "ui_language": "fr", "z": [1, 2]}), encoding="utf-8")
            self.assertTrue(core.persist_config_value("ui_language", "en", path))
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(list(data), ["a", "ui_language", "z"])
            self.assertEqual(data["ui_language"], "en")
            self.assertFalse(os.path.exists(str(path) + ".tmp"))


# --- LedMapper -------------------------------------------------------------


KB = FakeDeviceType.CDT_Keyboard
MOUSE = FakeDeviceType.CDT_Mouse
MAT = FakeDeviceType.CDT_Mousemat
RAM = FakeDeviceType.CDT_MemoryModule


class MapperTests(unittest.TestCase):
    def test_direct_write_with_lut(self):
        sdk, mapper = make_mapper({"kb": (KB, [(0, 0), (1, 0)], "K70")})
        lut = core.build_lut(0.5, 1.0)
        self.assertTrue(
            mapper.apply_frame_map(mapper.global_map, ["kb"], bytes([255, 0, 0, 0, 0, 255]), lut=lut, update_mode="direct")
        )
        self.assertEqual(sdk.writes[-1], ("kb", [(100, 128, 0, 0), (101, 0, 0, 128)]))

    def test_map_entry_variants(self):
        sdk, mapper = make_mapper({"d": (KB, [(0, 0), (1, 0), (2, 0)], "x")})
        # led index list, negative index, explicit source index and white balance.
        map_list = [("d", [0, 1]), ("d", -1, 0, (0.5, 1.0, 1.0))]
        mapper.apply_frame_map(map_list, ["d"], bytes([200, 10, 20]), update_mode="direct")
        self.assertEqual(sdk.writes[-1][1], [(100, 200, 10, 20), (101, 200, 10, 20), (102, 100, 10, 20)])

    def test_short_frame_is_black(self):
        sdk, mapper = make_mapper({"d": (KB, [(0, 0), (1, 0)], "x")})
        mapper.apply_frame_map(mapper.global_map, ["d"], bytes([9, 9, 9]), update_mode="buffer")
        self.assertEqual(sdk.writes[-1][1], [(100, 9, 9, 9), (101, 0, 0, 0)])

    def test_direct_async_writes_and_close_stops_writer(self):
        sdk, mapper = make_mapper({"d": (KB, [(0, 0)], "x")})
        self.assertTrue(mapper.apply_frame_map(mapper.global_map, ["d"], bytes([1, 2, 3])))
        deadline = time.monotonic() + 2.0
        while not sdk.writes and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(sdk.writes[-1], ("d", [(100, 1, 2, 3)]))
        writer = mapper._direct_async_thread
        mapper.close()
        writer.join(timeout=2.0)
        self.assertFalse(writer.is_alive())
        self.assertFalse(mapper.apply_frame_map(mapper.global_map, ["d"], bytes([1, 2, 3])))

    def test_async_error_does_not_drop_next_frame(self):
        sdk, mapper = make_mapper({"d": (KB, [(0, 0)], "x")})
        mapper._direct_async_last_error = "previous failure"
        ok = mapper.apply_frame_map(mapper.global_map, ["d"], bytes([7, 7, 7]))
        self.assertFalse(ok)
        deadline = time.monotonic() + 2.0
        while not sdk.writes and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(sdk.writes[-1], ("d", [(100, 7, 7, 7)]))
        mapper.close()


# --- Group building ----------------------------------------------------------


class GroupTests(unittest.TestCase):
    def test_ram_group_without_layout_key(self):
        sdk, mapper = make_mapper({"r1": (RAM, [(0, 0), (0, 1)], "DIMM")})
        groups = core.build_groups(
            [{"name": "ram", "udp_port": 1234, "device_types_include": ["CDT_MemoryModule"]}],
            mapper,
            sdk,
            "wled",
            "127.0.0.1",
            cfg={},
        )
        self.assertEqual(groups[0]["led_count"], 2)

    def test_mouse_linked_to_mousemat_center(self):
        sdk, mapper = make_mapper(
            {
                "mouse": (MOUSE, [(0, 0), (1, 0)], "M65"),
                "mat": (MAT, [(0, 0), (1, 0), (2, 0), (3, 0)], "MM800"),
            }
        )
        groups = core.build_groups(
            [
                {
                    "name": "souris_tapis",
                    "udp_port": 9999,
                    "device_types_include": ["CDT_Mouse", "CDT_Mousemat"],
                    "link_mouse_to_mousemat_center": True,
                }
            ],
            mapper,
            sdk,
            "wled",
            "127.0.0.1",
            cfg={},
        )
        mouse_entries = [e for e in groups[0]["map"] if e[0] == "mouse"]
        # Mousemat comes first (4 LEDs), so its centre is source index 2.
        self.assertTrue(all(len(e) == 3 and e[2] == 2 for e in mouse_entries))

    def test_duplicate_device_between_groups_is_rejected(self):
        sdk, mapper = make_mapper({"kb": (KB, [(0, 0)], "K70")})
        grp = {"udp_port": 1, "device_types_include": ["CDT_Keyboard"]}
        with self.assertRaises(RuntimeError):
            core.build_groups([dict(grp, name="a"), dict(grp, name="b", udp_port=2)], mapper, sdk, "wled", "127.0.0.1", cfg={})


if __name__ == "__main__":
    unittest.main()
