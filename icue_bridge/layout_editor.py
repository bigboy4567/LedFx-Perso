"""Layout editor: choose the LED stream order of fans, AIO zones, devices and fusion sections.

The editor only writes existing/additive config.json keys; the running bridge
reloads the file on its own. Everything starts from the current configuration.
"""

import copy
import math

import ledfx_icue_core as core


def _default_t(key, **kwargs):
    return key.format(**kwargs) if kwargs else key


def _choice(value, allowed, default):
    value = str(value or "").lower()
    return value if value in allowed else default


# Keys copied as-is from the editor state when they change.
_FAN_SURFACE_KEYS = (
    "fan_surface",
    "fan_surface_first",
    "fan_led_start",
    "fan_led_rotation",
    "fan_led_inner_first",
)


def _all_leds(dev):
    return [(dev["device_id"], i) for i in range(int(dev.get("leds") or 0))]


class LayoutModel:
    """What can be reordered for this setup, and the config changes an order implies."""

    def __init__(self, cfg, mapper, sdk, t=None):
        self.cfg = cfg
        self.t = t or _default_t
        self.items = {}  # list name -> {key: {"label", "targets"}}
        self.group_names = {}  # group index -> name
        state = {}

        fan_items, fan_count = self._build_fans(mapper, sdk)
        self.items["fans"] = fan_items
        self.case_fan_count = fan_count
        n_fans = len(fan_items)
        state["fans"] = self._initial_index_order(cfg.get("fan_group_order"), fan_items)
        direction = str(cfg.get("fan_direction") or "clockwise").lower()
        state["fan_direction"] = "counter" if direction == "counter" else "clockwise"
        state["fan_surface"] = bool(cfg.get("fan_surface", False))
        state["fan_surface_first"] = _choice(cfg.get("fan_surface_first"), core.FAN_SIDES, "top")
        state["fan_led_start"] = _choice(cfg.get("fan_led_start"), core.FAN_SIDES, "top")
        state["fan_led_rotation"] = _choice(cfg.get("fan_led_rotation"), ("clockwise", "counter"), "clockwise")
        state["fan_led_inner_first"] = bool(cfg.get("fan_led_inner_first", False))
        self.has_fans = n_fans >= 1
        self.mapper = mapper
        self.sdk = sdk

        aio_items, pump_key = self._build_aio(mapper, sdk)
        self.items["aio"] = aio_items
        self.pump_key = pump_key
        default_aio = [pump_key] + [k for k in aio_items if k != pump_key] if aio_items else []
        state["aio"] = (
            self._initial_index_order(cfg.get("aio_cluster_order"), aio_items)
            if cfg.get("aio_cluster_order")
            else default_aio
        )
        state["aio_unique"] = bool(cfg.get("aio_cluster", False))
        self.has_aio = len(aio_items) >= 2

        state["groups"] = {}
        for idx, grp in enumerate(cfg.get("groups") or []):
            if not isinstance(grp, dict):
                continue
            try:
                devices, _ = core.group_devices(grp, mapper, sdk, cfg)
            except Exception:
                continue
            if len(devices) < 2:
                continue
            list_name = f"group:{idx}"
            self.items[list_name] = self._device_items(devices, mapper)
            self.group_names[idx] = str(grp.get("name") or f"#{idx + 1}")
            state["groups"][idx] = [str(d.get("device_id_str") or d["device_id"]) for d in devices]

        self.items["fusion"] = self._build_fusion_sections(mapper, sdk)
        state["fusion"] = core.normalize_fusion_order(cfg.get("fusion_order"))
        state["cpu_after"] = core._cfg_int(cfg, "fusion_cpu_after_fan", 1, minimum=0)

        self.initial = state

    # --- discovery -------------------------------------------------------

    def _fan_types(self, sdk, fallback):
        types = core.parse_device_types(self.cfg.get("fan_device_types"), sdk)
        if not types and fallback:
            types = core.parse_device_types(["CDT_LedController", "CDT_Fan"], sdk)
        return set(types)

    def _build_fans(self, mapper, sdk):
        cfg = self.cfg
        leds_per_fan = core._cfg_int(cfg, "fan_outer_leds", 12) + core._cfg_int(cfg, "fan_inner_leds", 4)
        per_fan = []
        total_fans = 0
        if leds_per_fan > 0:
            fan_types = self._fan_types(sdk, fallback=False)
            for dev in mapper.devices:
                if dev.get("device_type") not in fan_types:
                    continue
                positions = mapper.positions_by_device.get(dev["device_id"])
                if not positions:
                    continue
                fans, _ = core._fan_layout(
                    positions,
                    cfg.get("fan_count"),
                    leds_per_fan,
                    cfg.get("fan_layout", "sequential"),
                    cfg.get("fan_group_sort", "x"),
                    cfg.get("fan_flip_x", False),
                    cfg.get("fan_flip_y", True),
                    cfg.get("fan_swap_xy", False),
                )
                for i, leds in enumerate(fans):
                    while len(per_fan) <= i:
                        per_fan.append([])
                    per_fan[i].extend((dev["device_id"], led) for led in leds)
                    total_fans += 1 if leds else 0
        items = {}
        for i, targets in enumerate(per_fan):
            if targets:
                items[i] = {"label": self.t("layout_fan", n=i + 1), "targets": targets}
        return items, total_fans

    def _build_aio(self, mapper, sdk):
        cfg = self.cfg
        cooler_types = set(core.parse_device_types(["CDT_Cooler"], sdk))
        flips = (cfg.get("aio_flip_x", False), cfg.get("aio_flip_y", False), cfg.get("aio_swap_xy", False))
        for dev in mapper.devices:
            if dev.get("device_type") not in cooler_types:
                continue
            positions = mapper.positions_by_device.get(dev["device_id"])
            clusters = core._build_aio_cluster_orders(
                positions,
                cluster_count=cfg.get("aio_cluster_count", 3),
                group_sort=cfg.get("aio_cluster_sort", "x"),
                group_order=None,
                start=cfg.get("aio_angle_start", "top"),
                direction=cfg.get("aio_angle_direction", "clockwise"),
                flip_x=flips[0],
                flip_y=flips[1],
                swap_xy=flips[2],
                pump_first=False,
            )
            if not clusters:
                continue
            points = {idx: (x, y) for idx, x, y in core._transform_points(positions, *flips)}
            gx = sum(x for x, _ in points.values()) / len(points)
            gy = sum(y for _, y in points.values()) / len(points)

            def dist(leds):
                cx = sum(points[i][0] for i in leds) / len(leds)
                cy = sum(points[i][1] for i in leds) / len(leds)
                return math.hypot(cx - gx, cy - gy)

            pump = min(range(len(clusters)), key=lambda i: dist(clusters[i]))
            items = {}
            fan_no = 0
            for i, leds in enumerate(clusters):
                if i == pump:
                    label = self.t("layout_pump")
                else:
                    fan_no += 1
                    label = self.t("layout_aio_fan", n=fan_no)
                items[i] = {"label": label, "targets": [(dev["device_id"], led) for led in leds]}
            return items, pump
        return {}, None

    def _device_items(self, devices, mapper):
        # Same-model devices (RAM sticks) get a stable number from iCUE enumeration order.
        totals = {}
        for dev in mapper.devices:
            label = core._device_label(dev)
            totals[label] = totals.get(label, 0) + 1
        seen = {}
        numbers = {}
        for dev in mapper.devices:
            label = core._device_label(dev)
            seen[label] = seen.get(label, 0) + 1
            numbers[str(dev.get("device_id_str") or dev["device_id"])] = seen[label]
        items = {}
        for dev in devices:
            key = str(dev.get("device_id_str") or dev["device_id"])
            label = core._device_label(dev)
            if totals.get(label, 0) > 1:
                label = f"{label} #{numbers.get(key, 1)}"
            items[key] = {"label": label, "targets": _all_leds(dev)}
        return items

    def _build_fusion_sections(self, mapper, sdk):
        def by_types(names):
            types = set(core.parse_device_types(names, sdk))
            return [dev for dev in mapper.devices if dev.get("device_type") in types]

        def leds(devices):
            out = []
            for dev in devices:
                out.extend(_all_leds(dev))
            return out

        pump_targets = []
        if self.pump_key is not None:
            pump_targets = list(self.items["aio"][self.pump_key]["targets"])
        pump_set = set(pump_targets)
        fan_types = self._fan_types(sdk, fallback=True)
        case_fans = [dev for dev in mapper.devices if dev.get("device_type") in fan_types]
        targets = {
            "clavier": leds(by_types(["CDT_Keyboard"])),
            "tapis": leds(by_types(["CDT_Mousemat"])),
            "souris": leds(by_types(["CDT_Mouse"])),
            "ventilos": leds(case_fans) + pump_targets,
            "ram": leds(by_types(["CDT_MemoryModule"])),
            "aio_ventilos": [t for t in leds(by_types(["CDT_Cooler"])) if t not in pump_set],
        }
        return {
            name: {"label": self.t(f"section_{name}"), "targets": targets[name]}
            for name in core.FUSION_SECTIONS
        }

    @staticmethod
    def _initial_index_order(raw, items):
        keys = list(items)
        order = core._normalize_group_order(raw, max(keys) + 1 if keys else 0)
        if not order:
            return keys
        order = [i for i in order if i in items]
        return order + [k for k in keys if k not in order]

    # --- state -------------------------------------------------------------

    def state(self):
        return copy.deepcopy(self.initial)

    def changes(self, state):
        """Config changes implied by `state`: (top-level keys, {group index: keys})."""
        init = self.initial
        top = {}
        if state["fans"] != init["fans"]:
            # fan_group_order is 1-based and indexes the fans in iCUE order.
            top["fan_group_order"] = [k + 1 for k in state["fans"]]
            if not self.cfg.get("fan_ring"):
                top["fan_ring"] = True
        if state["fan_direction"] != init["fan_direction"]:
            top["fan_direction"] = state["fan_direction"]
        for key in _FAN_SURFACE_KEYS:
            if state[key] != init[key]:
                top[key] = state[key]
        if state["aio"] != init["aio"] or state["aio_unique"] != init["aio_unique"]:
            # Always write the order with aio_cluster so unique mode matches the list.
            top["aio_cluster_order"] = [k + 1 for k in state["aio"]]
            top["aio_cluster"] = bool(state["aio_unique"])
        if state["fusion"] != init["fusion"]:
            top["fusion_order"] = list(state["fusion"])
        if state["cpu_after"] != init["cpu_after"]:
            top["fusion_cpu_after_fan"] = int(state["cpu_after"])
        groups = {}
        for idx, order in state["groups"].items():
            if order != init["groups"].get(idx):
                groups[idx] = {"device_order": list(order)}
        return top, groups

    def commit(self, state):
        # Fold the saved values into cfg first: changes() is relative to `initial`.
        self.cfg = dict(self.cfg, **self.changes_applied_to_cfg(state))
        self.initial = copy.deepcopy(state)

    def changes_applied_to_cfg(self, state):
        top, _ = self.changes(state)
        return top

    def fan_preview_targets(self, state):
        """Fan LEDs in the order LedFx would sweep them with `state` (saved or not)."""
        cfg = dict(copy.deepcopy(self.cfg), **self.changes_applied_to_cfg(state))
        preview = copy.copy(self.mapper)
        preview.order_by_device = dict(self.mapper.order_by_device)
        fan_types = set(core.parse_device_types(cfg.get("fan_device_types"), self.sdk))
        for dev in self.mapper.devices:
            if dev.get("device_type") in fan_types:
                preview.order_by_device.pop(dev["device_id"], None)
        core.apply_fan_layout(preview, cfg, self.sdk)
        targets = []
        for dev in self.mapper.devices:
            if dev.get("device_type") in fan_types:
                device_id = dev["device_id"]
                targets.extend((device_id, i) for i in preview.get_device_order(device_id))
        return targets


# --- Tk user interface --------------------------------------------------------

BG = "#1f1f22"
PANEL = "#2a2a2e"
FG = "#f2f2f2"
MUTED = "#a8a8ad"
ACCENT = "#3d6fd1"


class OrderList:
    """Reorderable list (drag and drop or arrow buttons) with an Identify action."""

    def __init__(self, tk, ttk, parent, items, order, t, on_identify, on_change, height=6):
        self.items = items
        self.order = list(order)
        self.on_change = on_change
        self.frame = ttk.Frame(parent, style="App.TFrame")
        self.listbox = tk.Listbox(
            self.frame,
            height=max(2, min(height, len(self.order))),
            activestyle="none",
            exportselection=False,
            bg=PANEL,
            fg=FG,
            selectbackground=ACCENT,
            selectforeground=FG,
            highlightthickness=0,
            relief="flat",
            font=("Segoe UI", 10),
        )
        self.listbox.grid(row=0, column=0, rowspan=3, sticky="nsew")
        buttons = [
            (t("layout_up"), lambda: self.move(-1)),
            (t("layout_down"), lambda: self.move(1)),
            (t("layout_identify"), lambda: self._identify(on_identify)),
        ]
        for row, (text, command) in enumerate(buttons):
            ttk.Button(self.frame, text=text, style="App.TButton", command=command).grid(
                row=row, column=1, sticky="ew", padx=(8, 0), pady=2
            )
        self.frame.columnconfigure(0, weight=1)
        self._drag_from = None
        self.listbox.bind("<ButtonPress-1>", self._drag_start)
        self.listbox.bind("<B1-Motion>", self._drag_motion)
        self.refresh()

    def refresh(self, select=None):
        self.listbox.delete(0, "end")
        for pos, key in enumerate(self.order, start=1):
            self.listbox.insert("end", f"  {pos}.  {self.items[key]['label']}")
        if select is not None and 0 <= select < len(self.order):
            self.listbox.selection_set(select)
            self.listbox.see(select)

    def set_order(self, order):
        self.order = list(order)
        self.refresh()

    def selected(self):
        sel = self.listbox.curselection()
        return sel[0] if sel else None

    def move(self, delta):
        i = self.selected()
        if i is None:
            return
        j = i + delta
        if not 0 <= j < len(self.order):
            return
        self.order[i], self.order[j] = self.order[j], self.order[i]
        self.refresh(select=j)
        self.on_change()

    def _identify(self, on_identify):
        i = self.selected()
        if i is not None:
            on_identify(self.items[self.order[i]])

    def _drag_start(self, event):
        self._drag_from = self.listbox.nearest(event.y)

    def _drag_motion(self, event):
        if self._drag_from is None:
            return
        target = self.listbox.nearest(event.y)
        if target == self._drag_from or not 0 <= target < len(self.order):
            return
        key = self.order.pop(self._drag_from)
        self.order.insert(target, key)
        self._drag_from = target
        self.refresh(select=target)
        self.on_change()


class LayoutEditor:
    def __init__(self, root, backend, model, t):
        import tkinter as tk
        from tkinter import messagebox, ttk

        self.tk, self.ttk, self.messagebox = tk, ttk, messagebox
        self.backend = backend
        self.model = model
        self.t = t
        self.lists = {}
        self.window = tk.Toplevel(root)
        self.window.title(t("layout_title"))
        self.window.configure(bg=BG)
        self.window.minsize(480, 420)
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        style = ttk.Style(self.window)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("App.TFrame", background=BG)
        style.configure("App.TLabel", background=BG, foreground="#cfcfcf", font=("Segoe UI", 9))
        style.configure("App.TButton", font=("Segoe UI", 10, "bold"), padding=6)
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(12, 4), font=("Segoe UI", 9, "bold"))
        style.configure("Help.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("App.TCheckbutton", background=BG, foreground=FG)
        style.configure("Group.TLabelframe", background=BG, foreground=FG)
        style.configure("Group.TLabelframe.Label", background=BG, foreground=FG, font=("Segoe UI", 9, "bold"))

        outer = ttk.Frame(self.window, padding=12, style="App.TFrame")
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text=t("layout_intro"), style="App.TLabel", wraplength=460, justify="left").pack(
            fill="x", pady=(0, 8)
        )
        notebook = ttk.Notebook(outer)
        notebook.pack(fill="both", expand=True)

        state = model.state()
        if model.has_fans:
            self._fans_tab(notebook, state)
        if model.has_aio:
            self._aio_tab(notebook, state)
        if state["groups"]:
            self._devices_tab(notebook, state)
        self._fusion_tab(notebook, state)

        self.status = ttk.Label(outer, text="", style="Help.TLabel")
        self.status.pack(fill="x", pady=(8, 4))
        bar = ttk.Frame(outer, style="App.TFrame")
        bar.pack(fill="x")
        ttk.Button(bar, text=t("layout_save"), style="App.TButton", command=self.save).pack(side="left")
        ttk.Button(bar, text=t("layout_reset"), style="App.TButton", command=self.reset).pack(side="left", padx=6)
        ttk.Button(bar, text=t("layout_close"), style="App.TButton", command=self.close).pack(side="right")

    # --- tabs ----------------------------------------------------------------

    def _tab(self, notebook, title, help_key):
        frame = self.ttk.Frame(notebook, padding=10, style="App.TFrame")
        notebook.add(frame, text=title)
        self.ttk.Label(frame, text=self.t(help_key), style="Help.TLabel", wraplength=440, justify="left").pack(
            fill="x", pady=(0, 8)
        )
        return frame

    def _order_list(self, parent, name, order, height=6):
        widget = OrderList(
            self.tk, self.ttk, parent, self.model.items[name], order, self.t,
            self.identify, self.mark_dirty, height=height,
        )
        self.lists[name] = widget
        return widget

    def _combo_row(self, parent, label_key, options, value, pady=(6, 0)):
        """Label + read-only combobox; returns (StringVar, {value: label}, widget)."""
        row = self.ttk.Frame(parent, style="App.TFrame")
        row.pack(fill="x", pady=pady)
        self.ttk.Label(row, text=self.t(label_key), style="App.TLabel").pack(side="left")
        var = self.tk.StringVar(value=options[value])
        combo = self.ttk.Combobox(
            row, textvariable=var, state="readonly", values=list(options.values()), width=14
        )
        combo.pack(side="right")
        combo.bind("<<ComboboxSelected>>", lambda _e: self._on_fan_option())
        return var, options, combo

    def _fans_tab(self, notebook, state):
        t = self.t
        tab = self._tab(notebook, t("layout_tab_fans"), "layout_fans_help")
        self._order_list(tab, "fans", state["fans"], height=4).frame.pack(fill="x")

        self.surface_var = self.tk.BooleanVar(value=state["fan_surface"])
        self.ttk.Checkbutton(
            tab, text=t("layout_surface"), variable=self.surface_var,
            style="App.TCheckbutton", command=self._on_fan_option,
        ).pack(anchor="w", pady=(10, 0))

        sides = {side: t(f"layout_side_{side}") for side in ("top", "bottom", "left", "right")}
        box = self.ttk.LabelFrame(tab, text=t("layout_calibration"), style="Group.TLabelframe", padding=8)
        box.pack(fill="x", pady=(6, 0))
        self.fan_choices = {
            "fan_surface_first": self._combo_row(box, "layout_surface_first", sides, state["fan_surface_first"], pady=(0, 0)),
            "fan_led_start": self._combo_row(box, "layout_led_start", sides, state["fan_led_start"]),
            "fan_led_rotation": self._combo_row(
                box, "layout_led_rotation",
                {"clockwise": t("layout_clockwise"), "counter": t("layout_counter")},
                state["fan_led_rotation"],
            ),
        }
        self.inner_first_var = self.tk.BooleanVar(value=state["fan_led_inner_first"])
        self.inner_first_check = self.ttk.Checkbutton(
            box, text=t("layout_led_inner_first"), variable=self.inner_first_var,
            style="App.TCheckbutton", command=self._on_fan_option,
        )
        self.inner_first_check.pack(anchor="w", pady=(6, 0))

        self.direction_labels = {
            "clockwise": t("layout_dir_normal"),
            "counter": t("layout_dir_reverse"),
        }
        self.direction_var, _, self.direction_combo = self._combo_row(
            tab, "layout_fan_direction", self.direction_labels, state["fan_direction"], pady=(8, 0)
        )
        self.ttk.Button(
            tab, text=t("layout_sweep"), style="App.TButton", command=self.sweep_fans
        ).pack(anchor="e", pady=(10, 0))
        self._sync_fan_widgets()

    def _on_fan_option(self):
        self._sync_fan_widgets()
        self.mark_dirty()

    def _sync_fan_widgets(self):
        # Calibration only matters for the surface; the per-fan direction only without it.
        surface = bool(self.surface_var.get())
        for _var, _options, combo in self.fan_choices.values():
            combo.configure(state="readonly" if surface else "disabled")
        self.inner_first_check.state(["!disabled"] if surface else ["disabled"])
        self.direction_combo.configure(state="disabled" if surface else "readonly")

    def sweep_fans(self):
        targets = self.model.fan_preview_targets(self.current_state())
        if targets:
            self.backend.sweep(targets)
            self.status.config(text=self.t("layout_sweeping"))

    def _aio_tab(self, notebook, state):
        tab = self._tab(notebook, self.t("layout_tab_aio"), "layout_aio_help")
        self._order_list(tab, "aio", state["aio"]).frame.pack(fill="x")
        self.aio_unique_var = self.tk.BooleanVar(value=state["aio_unique"])
        self.ttk.Checkbutton(
            tab, text=self.t("layout_aio_unique"), variable=self.aio_unique_var,
            style="App.TCheckbutton", command=self.mark_dirty,
        ).pack(anchor="w", pady=(10, 0))

    def _devices_tab(self, notebook, state):
        tab = self._tab(notebook, self.t("layout_tab_devices"), "layout_devices_help")
        for idx, order in state["groups"].items():
            box = self.ttk.LabelFrame(tab, text=self.model.group_names[idx], style="Group.TLabelframe", padding=6)
            box.pack(fill="x", pady=(0, 8))
            self._order_list(box, f"group:{idx}", order, height=4).frame.pack(fill="x")

    def _fusion_tab(self, notebook, state):
        tab = self._tab(notebook, self.t("layout_tab_fusion"), "layout_fusion_help")
        self._order_list(tab, "fusion", state["fusion"], height=6).frame.pack(fill="x")
        row = self.ttk.Frame(tab, style="App.TFrame")
        row.pack(fill="x", pady=(10, 0))
        self.ttk.Label(row, text=self.t("layout_cpu_after"), style="App.TLabel").pack(side="left")
        self.cpu_after_var = self.tk.StringVar(value=str(state["cpu_after"]))
        self.ttk.Spinbox(
            row, from_=0, to=max(1, self.model.case_fan_count), width=5,
            textvariable=self.cpu_after_var, command=self.mark_dirty,
        ).pack(side="left", padx=8)

    # --- actions -------------------------------------------------------------

    def current_state(self):
        state = self.model.state()
        if "fans" in self.lists:
            state["fans"] = list(self.lists["fans"].order)
            reverse = {v: k for k, v in self.direction_labels.items()}
            state["fan_direction"] = reverse.get(self.direction_var.get(), state["fan_direction"])
            state["fan_surface"] = bool(self.surface_var.get())
            state["fan_led_inner_first"] = bool(self.inner_first_var.get())
            for key, (var, options, _combo) in self.fan_choices.items():
                reverse = {label: value for value, label in options.items()}
                state[key] = reverse.get(var.get(), state[key])
        if "aio" in self.lists:
            state["aio"] = list(self.lists["aio"].order)
            state["aio_unique"] = bool(self.aio_unique_var.get())
        for idx in state["groups"]:
            state["groups"][idx] = list(self.lists[f"group:{idx}"].order)
        state["fusion"] = list(self.lists["fusion"].order)
        try:
            state["cpu_after"] = max(0, int(self.cpu_after_var.get()))
        except ValueError:
            pass
        return state

    def dirty(self):
        top, groups = self.model.changes(self.current_state())
        return bool(top or groups)

    def mark_dirty(self):
        self.status.config(text="")

    def identify(self, item):
        self.backend.identify(item["targets"])
        self.status.config(text=self.t("layout_identifying", item=item["label"]))

    def save(self):
        state = self.current_state()
        top, groups = self.model.changes(state)
        if not top and not groups:
            self.status.config(text=self.t("layout_no_change"))
            return
        try:
            self.backend.save(top, groups)
        except Exception as exc:
            self.status.config(text=self.t("layout_save_error", error=exc))
            return
        self.model.commit(state)
        self.status.config(text=self.t("layout_saved"))

    def reset(self):
        state = self.model.state()
        for name, widget in self.lists.items():
            if name.startswith("group:"):
                widget.set_order(state["groups"][int(name.split(":", 1)[1])])
            else:
                widget.set_order(state[name])
        if "fans" in self.lists:
            self.direction_var.set(self.direction_labels[state["fan_direction"]])
            self.surface_var.set(state["fan_surface"])
            self.inner_first_var.set(state["fan_led_inner_first"])
            for key, (var, options, _combo) in self.fan_choices.items():
                var.set(options[state[key]])
            self._sync_fan_widgets()
        if "aio" in self.lists:
            self.aio_unique_var.set(state["aio_unique"])
        self.cpu_after_var.set(str(state["cpu_after"]))
        self.status.config(text="")

    def close(self):
        if self.dirty() and not self.messagebox.askyesno(
            self.t("layout_unsaved_title"), self.t("layout_unsaved_body"), parent=self.window
        ):
            return
        self.window.destroy()


def open_editor(root, backend, i18n_obj):
    """Open the editor as a child window of the bridge's Tk root; returns the Toplevel."""
    cfg, mapper, sdk = backend.snapshot()
    model = LayoutModel(cfg, mapper, sdk, i18n_obj.t)
    editor = LayoutEditor(root, backend, model, i18n_obj.t)
    editor.window._editor = editor  # keep the controller alive with its window
    return editor.window
