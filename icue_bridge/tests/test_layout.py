import copy
import json
import math
import pathlib
import queue
import sys
import tempfile
import unittest
from types import SimpleNamespace

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import layout_editor  # noqa: E402
import ledfx_icue_core as core  # noqa: E402
from test_core import FakeDeviceType as T  # noqa: E402
from test_core import FakeSdk  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
ARGS = SimpleNamespace(group_port=None, fusion_port=None, debug_icue=False, perf_debug=False, perf_threshold=None)


def ring(cx, cy, n, r):
    return [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)]


DEVICES = {
    "kb": (T.CDT_Keyboard, [(x * 10.0, y * 12.0) for y in range(4) for x in range(12)], "K70"),
    "mouse": (T.CDT_Mouse, [(500, 300), (505, 310)], "M65"),
    "mat": (T.CDT_Mousemat, [(400 + 10 * i, 300) for i in range(15)], "MM800"),
    "ram1": (T.CDT_MemoryModule, [(700, 100 + 5 * i) for i in range(10)], "DIMM"),
    "ram2": (T.CDT_MemoryModule, [(720, 100 + 5 * i) for i in range(10)], "DIMM"),
    # The pump ring sits in the middle; radiator fans left and right.
    "aio": (T.CDT_Cooler, ring(100, 100, 8, 10) + ring(40, 100, 8, 15) + ring(160, 100, 8, 15), "H150i"),
    "fans": (T.CDT_LedController, sum((ring(100 * k, 400, 12, 30) + ring(100 * k, 400, 4, 10) for k in range(3)), []), "Commander"),
}


def shipped_cfg(**overrides):
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    cfg.update(overrides)
    return cfg


def build(cfg, mode="unique"):
    sdk = FakeSdk(DEVICES)
    mapper = core.build_mapper(cfg, sdk, T.CDT_All, ARGS)
    return sdk, mapper, core.get_groups_for_mode(mode, cfg, mapper, sdk, "wled", ARGS)


def group(groups, name):
    return next(g for g in groups if g["name"] == name)


class LayoutModelTests(unittest.TestCase):
    def setUp(self):
        self.cfg = shipped_cfg()
        self.sdk, self.mapper, _ = build(self.cfg)
        self.model = layout_editor.LayoutModel(self.cfg, self.mapper, self.sdk)

    def test_defaults_reflect_current_config(self):
        state = self.model.state()
        self.assertEqual(state["fans"], [0, 1, 2])
        self.assertEqual(state["fusion"], list(core.FUSION_SECTIONS))
        self.assertEqual(state["cpu_after"], 1)
        # The centre cluster is recognised as the pump and listed first.
        pump = self.model.items["aio"][state["aio"][0]]
        self.assertEqual(pump["label"], "layout_pump")
        self.assertEqual({led for _, led in pump["targets"]}, set(range(8)))
        names = {self.model.group_names[i] for i in state["groups"]}
        self.assertEqual(names, {"ram", "souris_tapis"})
        self.assertEqual(self.model.changes(state), ({}, {}))

    def test_fan_order_drives_the_led_stream(self):
        state = self.model.state()
        state["fans"] = [2, 0, 1]
        top, groups = self.model.changes(state)
        self.assertEqual(top, {"fan_group_order": [3, 1, 2]})
        _, _, gs = build(dict(self.cfg, **top))
        first = [led for _, led in group(gs, "ventilos")["map"][:16]]
        self.assertEqual(sorted(first), list(range(32, 48)))

    def test_fan_order_enables_fan_ring_when_off(self):
        cfg = shipped_cfg(fan_ring=False)
        sdk, mapper, _ = build(cfg)
        model = layout_editor.LayoutModel(cfg, mapper, sdk)
        state = model.state()
        state["fans"] = [1, 0, 2]
        self.assertTrue(model.changes(state)[0]["fan_ring"])

    def test_device_order_in_unique_and_fusion(self):
        state = self.model.state()
        ram_idx = next(i for i, n in self.model.group_names.items() if n == "ram")
        state["groups"][ram_idx] = list(reversed(state["groups"][ram_idx]))
        top, groups = self.model.changes(state)
        self.assertEqual(groups, {ram_idx: {"device_order": ["ram2", "ram1"]}})
        cfg = copy.deepcopy(self.cfg)
        cfg["groups"][ram_idx].update(groups[ram_idx])
        _, _, gs = build(cfg)
        self.assertEqual(group(gs, "ram")["device_ids"], ["ram2", "ram1"])
        _, _, fusion = build(cfg, "fusion")
        ram_ids = [d for d in fusion[0]["device_ids"] if d.startswith("ram")]
        self.assertEqual(ram_ids, ["ram2", "ram1"])

    def test_fusion_section_order_and_mouse_link(self):
        state = self.model.state()
        state["fusion"] = ["souris", "ram", "clavier", "tapis", "ventilos", "aio_ventilos"]
        top, _ = self.model.changes(state)
        _, _, fusion = build(dict(self.cfg, **top), "fusion")
        fmap = fusion[0]["map"]
        self.assertEqual([e[0] for e in fmap[:2]], ["mouse", "mouse"])
        self.assertTrue(fmap[2][0].startswith("ram"))
        # Every LED appears exactly once, whatever the order.
        _, _, default = build(self.cfg, "fusion")
        self.assertEqual(sorted(e[:2] for e in fmap), sorted(e[:2] for e in default[0]["map"]))
        # The mouse still mirrors the mousemat centre, placed after it in the strip.
        mat_positions = [i for i, e in enumerate(fmap) if e[0] == "mat"]
        self.assertEqual(fmap[0][2], mat_positions[0] + len(mat_positions) // 2)

    def test_aio_unique_writes_explicit_order(self):
        state = self.model.state()
        state["aio_unique"] = True
        top, _ = self.model.changes(state)
        self.assertTrue(top["aio_cluster"])
        self.assertEqual(top["aio_cluster_order"], [k + 1 for k in state["aio"]])
        _, _, gs = build(dict(self.cfg, **top))
        pump_leds = [led for _, led in group(gs, "aio")["map"][:8]]
        self.assertEqual(sorted(pump_leds), list(range(8)))

    def test_commit_resets_baseline(self):
        state = self.model.state()
        state["cpu_after"] = 0
        self.assertTrue(self.model.changes(state)[0])
        self.model.commit(state)
        self.assertEqual(self.model.changes(state), ({}, {}))


FANS = [list(range(k * 16, k * 16 + 16)) for k in range(3)]  # 12 outer + 4 inner each


class FanSurfaceOrderTests(unittest.TestCase):
    def test_fans_are_swept_as_one_block_from_fan_one(self):
        order = core.fan_surface_order(48, FANS, 4, first="top", led_start="top")
        self.assertEqual(sorted(order), list(range(48)))
        # Fan 1 entirely first, then fan 2, then fan 3 (stacked, no overlap).
        self.assertEqual([i // 16 for i in order], [0] * 16 + [1] * 16 + [2] * 16)
        # Starts at the top LED of fan 1, ends at the bottom LED of fan 3 (outer LED 6).
        self.assertEqual(order[0], 0)
        self.assertEqual(order[-1], 32 + 6)
        # Inside a fan the sweep is by height: top LED, then the two next to it.
        self.assertEqual(order[:3], [0, 11, 1])

    def test_bottom_start_and_calibration(self):
        order = core.fan_surface_order(48, FANS, 4, first="bottom", led_start="top")
        self.assertEqual(order[0], 6)  # bottom LED of fan 1 (fan 1 sits at the bottom)
        self.assertEqual([i // 16 for i in order[:16]], [0] * 16)
        inner_first = core.fan_surface_order(48, FANS, 4, first="top", led_start="top", inner_first=True)
        self.assertEqual(inner_first[0], 4)  # outer ring starts after the 4 centre LEDs
        right = core.fan_surface_order(48, FANS, 4, first="left", led_start="left")
        self.assertEqual(right[0], 0)  # fans side by side, sweep starts at fan 1's left LED

    def test_fan_order_and_leftover_leds(self):
        order = core.fan_surface_order(50, FANS, 4, group_order=[3, 1, 2])
        self.assertEqual([i // 16 for i in order[:16]], [2] * 16)
        self.assertEqual(order[-2:], [48, 49])


class FanSurfaceModeTests(unittest.TestCase):
    def setUp(self):
        self.cfg = shipped_cfg(fan_surface=True, fan_surface_first="top", fan_led_start="top")

    def test_unique_group_follows_surface(self):
        _, _, gs = build(self.cfg)
        fan_map = group(gs, "ventilos")["map"]
        expected = core.fan_surface_order(48, FANS, 4, first="top", led_start="top")
        self.assertEqual([led for _, led in fan_map], expected)

    def test_fusion_keeps_fans_contiguous(self):
        for after, pump_side in ((1, "after"), (0, "before")):
            _, _, fusion = build(dict(self.cfg, fusion_cpu_after_fan=after), "fusion")
            ids = [e[0] for e in fusion[0]["map"]]
            fan_pos = [i for i, d in enumerate(ids) if d == "fans"]
            self.assertEqual(fan_pos, list(range(fan_pos[0], fan_pos[0] + 48)), "block split")
            pump_pos = [i for i, e in enumerate(fusion[0]["map"]) if e[0] == "aio" and e[1] < 8]
            if pump_side == "after":
                self.assertEqual(pump_pos[0], fan_pos[-1] + 1)
            else:
                self.assertEqual(pump_pos[-1], fan_pos[0] - 1)

    def test_group_mode_follows_surface(self):
        _, mapper, gs = build(self.cfg, "group")
        fan_leds = [led for d, led in gs[0]["map"] if d == "fans"]
        self.assertEqual(fan_leds, core.fan_surface_order(48, FANS, 4))


class FanSurfaceEditorTests(unittest.TestCase):
    def test_surface_changes_and_unsaved_preview(self):
        cfg = shipped_cfg(fan_surface=False)
        sdk, mapper, _ = build(cfg)
        model = layout_editor.LayoutModel(cfg, mapper, sdk)
        live_order = mapper.get_device_order("fans")
        state = model.state()
        state["fan_surface"] = True
        state["fan_surface_first"] = "bottom"
        top, _ = model.changes(state)
        self.assertEqual(top, {"fan_surface": True, "fan_surface_first": "bottom"})
        preview = model.fan_preview_targets(state)
        self.assertEqual(preview[0], ("fans", 6))
        self.assertEqual(len(preview), 48)
        # The preview never touches the running bridge's mapper.
        self.assertEqual(mapper.get_device_order("fans"), live_order)
        model.commit(state)
        self.assertEqual(model.changes(state), ({}, {}))
        self.assertEqual(model.fan_preview_targets(state)[0], ("fans", 6))


class BackendTests(unittest.TestCase):
    def test_save_keeps_other_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "config.json"
            cfg = shipped_cfg()
            path.write_text(json.dumps(cfg), encoding="utf-8")
            requests = queue.Queue()
            backend = core.LayoutBackend(lambda: (cfg, None, None), requests, path)
            backend.save({"fusion_order": ["ram"]}, {1: {"device_order": ["b", "a"]}})
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(list(saved), list(cfg) + ["fusion_order"])
            self.assertEqual(saved["groups"][1]["device_order"], ["b", "a"])
            self.assertEqual(saved["groups"][0], cfg["groups"][0])
            backend.identify([("kb", 3)])
            self.assertEqual(requests.get_nowait(), ("identify", [("kb", 3)]))

    def test_new_keys_are_known(self):
        logger = core.logging.getLogger("test.layout")
        cfg = shipped_cfg(fusion_order=["ram"])
        cfg["groups"][0]["device_order"] = ["x"]
        self.assertEqual(core.validate_config(cfg, logger), 0)


class EditorUiTests(unittest.TestCase):
    """Drives the real Tk window (skipped when no display is available)."""

    def test_reorder_save_and_reset(self):
        try:
            import tkinter as tk

            root = tk.Tk()
        except Exception as exc:  # pragma: no cover - headless machines
            self.skipTest(f"Tk indisponible: {exc}")
        try:
            root.withdraw()
            cfg = shipped_cfg()
            sdk, mapper, _ = build(cfg)
            saved = []
            backend = SimpleNamespace(
                snapshot=lambda: (cfg, mapper, sdk),
                identify=lambda targets: saved.append(("identify", targets)),
                save=lambda top, groups: saved.append((top, groups)),
            )
            i18n = SimpleNamespace(t=lambda key, **kw: key)
            window = layout_editor.open_editor(root, backend, i18n)
            editor = window._editor if hasattr(window, "_editor") else None
            self.assertIsNotNone(editor)
            fans = editor.lists["fans"]
            fans.listbox.selection_set(2)
            fans.move(-1)
            self.assertEqual(fans.order, [0, 2, 1])
            fans.listbox.selection_set(1)
            fans._identify(editor.identify)
            self.assertEqual(saved[0][0], "identify")
            editor.save()
            self.assertEqual(saved[1], ({"fan_group_order": [1, 3, 2]}, {}))
            self.assertFalse(editor.dirty())
            fans.move(-1)
            editor.reset()
            self.assertEqual(fans.order, [0, 2, 1])

            # Surface: calibration widgets follow the checkbox, the test sweep uses unsaved values.
            surface_was = editor.surface_var.get()
            editor.surface_var.set(not surface_was)
            editor._on_fan_option()
            var, options, combo = editor.fan_choices["fan_surface_first"]
            self.assertEqual(str(combo.cget("state")), "readonly" if not surface_was else "disabled")
            var.set(options["bottom"])
            backend.sweep = lambda targets: saved.append(("sweep", targets))
            editor.sweep_fans()
            self.assertEqual(saved[-1][0], "sweep")
            self.assertEqual(len(saved[-1][1]), 48)
            editor.save()
            self.assertEqual(saved[-1][0]["fan_surface"], not surface_was)
            self.assertEqual(saved[-1][0]["fan_surface_first"], "bottom")
            window.destroy()
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
