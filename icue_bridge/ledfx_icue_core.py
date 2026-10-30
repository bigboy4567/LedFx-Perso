import difflib
import json
import logging
import logging.handlers
import math
import os
import pathlib
import queue
import selectors
import shutil
import socket
import subprocess
import sys
import threading
import time
import traceback

import i18n

_TIMING_LOG = logging.getLogger("bridge.timing")
_CONFIG_PATH = None
LOG_FILE_NAME = "ledfx_icue_bridge.log"
# Loopback by default: LedFx usually runs on the same PC. Use "0.0.0.0" for a remote LedFx.
DEFAULT_UDP_HOST = "127.0.0.1"

KNOWN_CONFIG_KEYS = frozenset(
    """
    aio_angle_direction aio_angle_start aio_cluster aio_cluster_count aio_cluster_order
    aio_cluster_sort aio_flip_x aio_flip_y aio_pump_angle_direction aio_pump_angle_start
    aio_pump_first aio_pump_split aio_pump_white_balance aio_swap_xy brightness
    clear_on_start cpu_affinity_core default_mode device_type_mask device_types_exclude
    device_types_include fan_count fan_device_types fan_direction fan_flip_x fan_flip_y
    fan_group_order fan_group_sort fan_inner_first fan_inner_leds fan_layout
    fan_led_inner_first fan_led_rotation fan_led_start fan_lock_to_first fan_outer_leds
    fan_ring fan_ring_order fan_start fan_surface fan_surface_first fan_swap_xy
    fusion_cpu_after_fan fusion_order fusion_port fusion_ram_led_axis fusion_ram_mirror fusion_ram_mode
    gamma group_port groups icue_apply_fail_threshold icue_direct_async_timeout
    icue_keepalive icue_keepalive_interval icue_keepalive_reapply
    icue_keepalive_request_always icue_layer_priority icue_reconnect_cooldown
    icue_reconnect_timeout icue_request_control_fail_threshold
    icue_request_control_interval icue_request_control_reconnect icue_restart_on_sdk_hang
    icue_skip_reconnect_when_idle icue_update_mode icue_watchdog
    icue_watchdog_fail_threshold icue_watchdog_idle_only icue_watchdog_interval
    icue_watchdog_sdk_check keyboard_serpentine keyboard_serpentine_first_dir
    keyboard_serpentine_flip_x keyboard_serpentine_flip_y keyboard_serpentine_mode
    keyboard_serpentine_row_order keyboard_serpentine_row_tolerance keyboard_serpentine_rows
    keyboard_serpentine_swap_xy log_file log_level max_fps mousemat_angle_direction
    mousemat_angle_start mousemat_order_mode mousemat_reverse mousemat_serpentine
    mousemat_serpentine_first_dir mousemat_serpentine_flip_x mousemat_serpentine_flip_y
    mousemat_serpentine_mode mousemat_serpentine_row_order
    mousemat_serpentine_row_tolerance mousemat_serpentine_rows mousemat_serpentine_swap_xy
    perf_debug perf_log_cooldown perf_threshold process_priority protocol
    ram_group_layout ram_match_group_order ram_order_axis ram_serpentine
    ram_serpentine_first_dir ram_serpentine_flip_x ram_serpentine_flip_y
    ram_serpentine_mode ram_serpentine_row_order ram_serpentine_row_tolerance
    ram_serpentine_rows ram_serpentine_swap_xy startup_prompt udp_host udp_port
    ui_language unique_idle_clear unique_idle_clear_seconds
    """.split()
)

# Keys of removed features: accepted silently so older config files stay valid.
OBSOLETE_CONFIG_KEYS = frozenset(
    ("update_check_enabled", "update_check_interval_seconds", "update_repo")
)

KNOWN_GROUP_KEYS = frozenset(
    """
    name udp_port udp_host protocol device_ids device_order device_types_include device_types_exclude
    model_contains model serial_contains serial device_sort update_mode keepalive_reapply
    idle_clear_disabled idle_clear_seconds link_mouse_to_mousemat_center ram_group_layout
    pump_split
    """.split()
)

try:
    import msvcrt

    _HAS_MSVCRT = True
except Exception:
    msvcrt = None
    _HAS_MSVCRT = False

try:
    import psutil

    _HAS_PSUTIL = True
except ImportError:
    psutil = None
    _HAS_PSUTIL = False


_TK_DLL_DIRS = []


def _bootstrap_tk_runtime():
    candidates = []
    try:
        module_dir = pathlib.Path(__file__).resolve().parent
    except Exception:
        module_dir = pathlib.Path.cwd()

    if getattr(sys, "frozen", False):
        exe_dir = pathlib.Path(sys.executable).resolve().parent
        candidates.extend([exe_dir, exe_dir / "_internal"])
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            mp = pathlib.Path(meipass)
            candidates.extend([mp, mp / "_internal"])
    else:
        candidates.extend([module_dir, module_dir / "_internal"])

    seen = set()
    ordered = []
    for candidate in candidates:
        try:
            key = str(candidate.resolve()).lower()
        except Exception:
            key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(candidate)

    tcl_dir = None
    tk_dir = None
    for candidate in ordered:
        candidate = pathlib.Path(candidate)
        cur_tcl = candidate / "_tcl_data"
        cur_tk = candidate / "_tk_data"
        if tcl_dir is None and cur_tcl.is_dir():
            tcl_dir = cur_tcl
        if tk_dir is None and cur_tk.is_dir():
            tk_dir = cur_tk
        if (candidate / "tcl86t.dll").exists() or (candidate / "tk86t.dll").exists():
            path_value = os.environ.get("PATH", "")
            candidate_str = str(candidate)
            if candidate_str.lower() not in path_value.lower():
                os.environ["PATH"] = candidate_str + os.pathsep + path_value
        if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
            if (candidate / "tcl86t.dll").exists() or (candidate / "tk86t.dll").exists():
                try:
                    _TK_DLL_DIRS.append(os.add_dll_directory(str(candidate)))
                except Exception:
                    pass
    if tcl_dir is not None and not os.environ.get("TCL_LIBRARY"):
        os.environ["TCL_LIBRARY"] = str(tcl_dir)
    if tk_dir is not None and not os.environ.get("TK_LIBRARY"):
        os.environ["TK_LIBRARY"] = str(tk_dir)


def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise RuntimeError("config.json invalide: objet JSON attendu.")
    return data


def _app_dir():
    if getattr(sys, "frozen", False):
        return pathlib.Path(sys.executable).resolve().parent
    return pathlib.Path(__file__).resolve().parent


def _resolve_config_path(path):
    p = pathlib.Path(path)
    if p.is_absolute():
        return p
    if getattr(sys, "frozen", False):
        target = _app_dir() / p
        if target.exists():
            return target
        # First run of the exe: extract the bundled default config next to it.
        meipass = getattr(sys, "_MEIPASS", None)
        bundled = pathlib.Path(meipass) / p if meipass else None
        if bundled is not None and bundled.exists():
            try:
                shutil.copyfile(bundled, target)
                return target
            except OSError:
                return bundled
        return target
    candidates = [pathlib.Path.cwd() / p]
    try:
        candidates.append(pathlib.Path(sys.executable).resolve().parent / p)
    except Exception:
        pass
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        try:
            candidates.append(pathlib.Path(meipass) / p)
        except Exception:
            pass
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return p


def _log_file_path(cfg=None):
    value = (cfg or {}).get("log_file")
    if value is False:
        return None
    p = pathlib.Path(value) if value else pathlib.Path(LOG_FILE_NAME)
    if not p.is_absolute():
        p = _app_dir() / p
    return p


def setup_logging(cfg):
    level_name = str(cfg.get("log_level", "info")).upper()
    level = getattr(logging, level_name, logging.INFO)

    root_logger = logging.getLogger()
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    # A windowed (console=False) exe has no stderr: the log file is the only output.
    if sys.stderr is not None:
        stream = logging.StreamHandler()
        stream.setLevel(level)
        stream.setFormatter(formatter)
        root_logger.addHandler(stream)

    log_path = _log_file_path(cfg)
    if log_path is not None:
        try:
            file_handler = logging.handlers.RotatingFileHandler(
                log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
            )
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except OSError:
            pass

    root_logger.setLevel(level)
    return logging.getLogger("bridge")


def _configure_timing_logger(enabled):
    # Fine-grained timing traces are only emitted when perf_debug is on.
    _TIMING_LOG.setLevel(logging.DEBUG if enabled else logging.CRITICAL + 1)
    return _TIMING_LOG


def _has_console():
    return sys.stdout is not None and sys.stdin is not None


def _show_error_box(title, message):
    if sys.platform != "win32":
        return
    try:
        import ctypes

        MB_ICONERROR = 0x10
        ctypes.windll.user32.MessageBoxW(None, str(message), str(title), MB_ICONERROR)
    except Exception:
        pass


def _fatal(logger, message):
    """Report a startup error through every available channel."""
    if logger is not None:
        logger.error(message)
    print(message)
    if not _has_console():
        _show_error_box("LedFx iCUE Bridge", message)


def _cfg_number(cfg, key, default, cast=float, minimum=None, maximum=None, logger=None):
    raw = cfg.get(key, default)
    if raw is None:
        raw = default
    try:
        value = cast(raw)
    except (TypeError, ValueError):
        (logger or logging.getLogger("bridge")).warning(
            "config: %s=%r invalide, valeur par defaut %r utilisee.", key, raw, default
        )
        value = cast(default)
    if minimum is not None and value < minimum:
        value = minimum
    if maximum is not None and value > maximum:
        value = maximum
    return value


def _cfg_float(cfg, key, default, minimum=None, maximum=None, logger=None):
    return _cfg_number(cfg, key, default, float, minimum, maximum, logger)


def _cfg_int(cfg, key, default, minimum=None, maximum=None, logger=None):
    return _cfg_number(cfg, key, default, int, minimum, maximum, logger)


def validate_config(cfg, logger):
    """Warn about unknown keys (typos) and malformed groups. Returns warning count."""
    warnings = 0
    for key in cfg:
        if key in KNOWN_CONFIG_KEYS or key in OBSOLETE_CONFIG_KEYS or key.startswith("_"):
            continue
        close = difflib.get_close_matches(key, KNOWN_CONFIG_KEYS, n=1)
        hint = f" (vouliez-vous dire '{close[0]}' ?)" if close else ""
        logger.warning("config: cle inconnue '%s' ignoree%s", key, hint)
        warnings += 1
    groups = cfg.get("groups")
    if groups is not None and not isinstance(groups, list):
        logger.warning("config: 'groups' doit etre une liste.")
        return warnings + 1
    for idx, grp in enumerate(groups or []):
        if not isinstance(grp, dict):
            logger.warning("config: groupe #%s invalide (objet attendu).", idx + 1)
            warnings += 1
            continue
        name = grp.get("name") or f"#{idx + 1}"
        for key in grp:
            if key in KNOWN_GROUP_KEYS or key.startswith("_"):
                continue
            close = difflib.get_close_matches(key, KNOWN_GROUP_KEYS, n=1)
            hint = f" (vouliez-vous dire '{close[0]}' ?)" if close else ""
            logger.warning("config: groupe '%s' cle inconnue '%s'%s", name, key, hint)
            warnings += 1
        try:
            port = int(grp.get("udp_port"))
            if not 1 <= port <= 65535:
                raise ValueError
        except (TypeError, ValueError):
            logger.warning("config: groupe '%s' udp_port invalide: %r", name, grp.get("udp_port"))
            warnings += 1
    return warnings


def write_config(path, data):
    """Atomically write config.json (the bridge may be watching it)."""
    tmp = pathlib.Path(str(path) + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def persist_config_value(key, value, path=None):
    """Update one top-level key in config.json, preserving key order."""
    path = path or _CONFIG_PATH
    if not path:
        return False
    try:
        data = load_config(path)
        data[key] = value
        write_config(path, data)
        return True
    except Exception as exc:
        logging.getLogger("bridge").warning("Sauvegarde config impossible (%s): %s", key, exc)
        return False


def get_perf_options(cfg, args):
    enabled = bool(cfg.get("perf_debug", False) or getattr(args, "perf_debug", False))
    threshold_value = getattr(args, "perf_threshold", None)
    if threshold_value is None:
        threshold_value = cfg.get("perf_threshold", 0.20)
    try:
        threshold = max(0.02, float(threshold_value))
    except Exception:
        threshold = 0.20
    try:
        cooldown = max(0.0, float(cfg.get("perf_log_cooldown", 2.0)))
    except Exception:
        cooldown = 2.0
    return enabled, threshold, cooldown


def build_lut(brightness, gamma):
    lut = [0] * 256
    for i in range(256):
        v = i / 255.0
        if gamma != 1.0:
            v = v ** gamma
        v = v * 255.0 * brightness
        if v < 0:
            v = 0
        if v > 255:
            v = 255
        lut[i] = int(v + 0.5)
    return lut


_IDENTITY_LUT = list(range(256))


def parse_rgb(value):
    if value is None:
        return None
    if isinstance(value, (list, tuple)) and len(value) == 3:
        return tuple(_clamp_byte(int(v)) for v in value)
    s = str(value).strip()
    if not s:
        return None
    s = s.replace(";", ",").replace(" ", "")
    parts = s.split(",")
    if len(parts) != 3:
        return None
    try:
        return tuple(_clamp_byte(int(p)) for p in parts)
    except Exception:
        return None


def parse_white_balance(value):
    if value is None:
        return None
    r = g = b = None
    if isinstance(value, dict):
        r = value.get("r")
        g = value.get("g")
        b = value.get("b")
    elif isinstance(value, (list, tuple)) and len(value) == 3:
        r, g, b = value
    else:
        return None
    try:
        r = float(r)
        g = float(g)
        b = float(b)
    except Exception:
        return None
    if r > 2.0 or g > 2.0 or b > 2.0:
        r /= 255.0
        g /= 255.0
        b /= 255.0
    r = max(0.0, min(2.0, r))
    g = max(0.0, min(2.0, g))
    b = max(0.0, min(2.0, b))
    return (r, g, b)


def _clamp_byte(v):
    if v < 0:
        return 0
    if v > 255:
        return 255
    return v


def _get_attr(obj, names):
    for name in names:
        if obj is None:
            return None
        if hasattr(obj, name):
            return getattr(obj, name)
    return None


def parse_int_list(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        raw = []
        for v in value:
            raw.extend(str(v).replace(";", ",").split(","))
    else:
        raw = str(value).replace(";", ",").split(",")
    out = []
    for part in raw:
        p = part.strip()
        if not p:
            continue
        try:
            out.append(int(p))
        except Exception:
            pass
    return out


def normalize_protocol(value, fallback="drgb"):
    proto = (value or fallback or "drgb").lower()
    if proto in ("udp", "drgb", "wled"):
        return "wled"
    return proto


def _normalize_list(value):
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set)):
        return [str(v) for v in value]
    return [str(value)]


def _match_contains(text, patterns):
    if not patterns:
        return True
    if text is None:
        return False
    t = str(text).lower()
    for p in patterns:
        if p is None:
            continue
        if str(p).lower() in t:
            return True
    return False


def _device_sort_key(dev, sort_key):
    if sort_key == "x":
        return (dev.get("center_x") is None, dev.get("center_x", 0.0))
    if sort_key == "y":
        return (dev.get("center_y") is None, dev.get("center_y", 0.0))
    if sort_key == "xy":
        return (
            dev.get("center_x") is None,
            dev.get("center_x", 0.0),
            dev.get("center_y", 0.0),
        )
    if sort_key == "yx":
        return (
            dev.get("center_y") is None,
            dev.get("center_y", 0.0),
            dev.get("center_x", 0.0),
        )
    if sort_key == "model":
        return str(dev.get("model") or "")
    return str(dev.get("device_id_str") or dev.get("device_id") or "")


def _transform_points(positions, flip_x=False, flip_y=False, swap_xy=False, allowed=None):
    """Return [(idx, x, y)] with optional flips/swap, or None if any LED lacks coords."""
    if not positions:
        return None
    points = []
    for idx, pos in enumerate(positions):
        if allowed is not None and idx not in allowed:
            continue
        x = pos.get("x")
        y = pos.get("y")
        if x is None or y is None:
            return None
        fx = -float(x) if flip_x else float(x)
        fy = -float(y) if flip_y else float(y)
        if swap_xy:
            fx, fy = fy, fx
        points.append((idx, fx, fy))
    return points or None


def _angle_order(points, start, direction):
    start = (start or "top").lower()
    direction = (direction or "clockwise").lower()
    start_angle = {
        "right": 0.0,
        "top": math.pi / 2.0,
        "left": math.pi,
        "bottom": -math.pi / 2.0,
    }.get(start, math.pi / 2.0)
    order = []
    for idx, x, y, cx, cy in points:
        angle = math.atan2(y - cy, x - cx)
        if direction == "clockwise":
            delta = (start_angle - angle) % (2 * math.pi)
        else:
            delta = (angle - start_angle) % (2 * math.pi)
        order.append((delta, idx))
    order.sort(key=lambda t: t[0])
    return [idx for _, idx in order]


def _kmeans_2d(points, k, max_iter=20):
    if not points or k <= 1:
        return [points]
    xs = sorted(p[1] for p in points)
    ys = sorted(p[2] for p in points)
    centers = []
    for i in range(k):
        q = i / (k - 1) if k > 1 else 0
        xi = xs[int(q * (len(xs) - 1))]
        yi = ys[int(q * (len(ys) - 1))]
        centers.append((xi, yi))
    for _ in range(max_iter):
        clusters = [[] for _ in range(k)]
        for p in points:
            best = min(range(k), key=lambda j: (p[1] - centers[j][0]) ** 2 + (p[2] - centers[j][1]) ** 2)
            clusters[best].append(p)
        new_centers = []
        for i, c in enumerate(clusters):
            if c:
                mx = sum(p[1] for p in c) / len(c)
                my = sum(p[2] for p in c) / len(c)
                new_centers.append((mx, my))
            else:
                new_centers.append(centers[i])
        shift = max(
            (new_centers[i][0] - centers[i][0]) ** 2 + (new_centers[i][1] - centers[i][1]) ** 2
            for i in range(k)
        )
        centers = new_centers
        if shift < 1e-4:
            break
    clusters = [[] for _ in range(k)]
    for p in points:
        best = min(range(k), key=lambda j: (p[1] - centers[j][0]) ** 2 + (p[2] - centers[j][1]) ** 2)
        clusters[best].append(p)
    # Warn when k-means leaves empty clusters that callers skip.
    empty_count = sum(1 for c in clusters if not c)
    if empty_count:
        logging.warning(
            "k-means produced %s empty cluster(s); requested=%s points=%s",
            empty_count,
            k,
            len(points),
        )
    return clusters


def _cluster_sort_key(center, sort_key):
    x, y = center
    if sort_key == "y":
        return (y, x)
    if sort_key == "xy":
        return (x, y)
    if sort_key == "yx":
        return (y, x)
    return (x, y)


def _normalize_group_order(order, count):
    if not order:
        return None
    try:
        order_list = [int(x) for x in order]
    except Exception:
        return None
    if not order_list:
        return None
    if all(i >= 1 for i in order_list):
        order_list = [i - 1 for i in order_list]
    order_list = [i for i in order_list if 0 <= i < count]
    if not order_list:
        return None
    if len(order_list) < count:
        order_list += [i for i in range(count) if i not in order_list]
    return order_list


def _ring_order(points, outer_leds, inner_leds, start, direction, inner_first, order_mode):
    if not points:
        return []
    order_mode = (order_mode or "index").lower()
    if order_mode == "index":
        indices = [p[0] for p in points]
        outer = indices[: int(outer_leds)] if outer_leds else []
        inner = indices[int(outer_leds) : int(outer_leds) + int(inner_leds)] if inner_leds else []
        if (direction or "").lower() == "counter":
            outer = list(reversed(outer))
            inner = list(reversed(inner))
        return (inner + outer) if inner_first else (outer + inner)

    cx =sum(p[1] for p in points) / len(points)
    cy = sum(p[2] for p in points) / len(points)
    by_dist = []
    for idx, x, y in points:
        dist = (x - cx) ** 2 + (y - cy) ** 2
        by_dist.append((dist, idx, x, y))
    by_dist.sort(key=lambda t: t[0], reverse=True)
    outer = by_dist[: int(outer_leds)] if outer_leds else []
    inner = by_dist[int(outer_leds) : int(outer_leds) + int(inner_leds)] if inner_leds else []

    outer_pts = [(idx, x, y, cx, cy) for _, idx, x, y in outer]
    inner_pts = [(idx, x, y, cx, cy) for _, idx, x, y in inner]
    outer_order = _angle_order(outer_pts, start, direction)
    inner_order = _angle_order(inner_pts, start, direction)

    if inner_first:
        return inner_order + outer_order
    return outer_order + inner_order


def _fan_layout(positions, fan_count, leds_per_fan, layout="sequential", group_sort="x",
                flip_x=False, flip_y=True, swap_xy=False):
    """Split one fan device into physical fans, in iCUE order (before fan_group_order).

    Returns (fans, points): fans is a list of LED index lists, points the
    transformed (idx, x, y) coordinates or [] when positions lack coordinates.
    """
    total = len(positions or [])
    leds_per_fan = max(1, int(leds_per_fan))
    k = fan_count
    if k is None:
        k = total // leds_per_fan if total % leds_per_fan == 0 else 1
    k = max(1, int(k))
    points = _transform_points(positions, flip_x, flip_y, swap_xy) or []
    layout = (layout or "sequential").lower()
    if layout == "auto":
        layout = "cluster" if points else "sequential"
    if layout == "sequential" or not points:
        fans = []
        for fan_idx in range(k):
            start_i = fan_idx * leds_per_fan
            fans.append(list(range(start_i, min(total, start_i + leds_per_fan))))
        return fans, points
    cluster_info = []
    for c in _kmeans_2d(points, k):
        if not c:
            continue
        cx = sum(p[1] for p in c) / len(c)
        cy = sum(p[2] for p in c) / len(c)
        cluster_info.append(([p[0] for p in c], (cx, cy)))
    cluster_info.sort(key=lambda t: _cluster_sort_key(t[1], group_sort))
    return [c for c, _ in cluster_info], points


# Screen angles (degrees, y pointing down as in iCUE) of the four sides of a fan.
_SIDE_ANGLES = {"right": 0.0, "bottom": 90.0, "left": 180.0, "top": 270.0}
FAN_SIDES = ("top", "bottom", "left", "right")


def fan_surface_order(total, fans, inner_leds, first="top", led_start="top",
                      rotation="clockwise", inner_first=False, group_order=None):
    """Order the LEDs of one fan device as a single surface swept from fan 1's side.

    iCUE gives no real geometry for fan hubs (Lighting Node Pro, Commander), so each
    fan is modelled as an outer ring and an inner ring of evenly spaced LEDs, the
    fans being stacked side by side. `fans` lists LED indices per fan in iCUE order;
    `group_order` says which fan sits in each physical slot, starting at `first`.
    Returns every index in 0..total-1 exactly once.
    """
    first = str(first or "top").lower()
    if first not in FAN_SIDES:
        first = "top"
    vertical = first in ("top", "bottom")
    step_sign = 1.0 if first in ("top", "left") else -1.0
    start = math.radians(_SIDE_ANGLES.get(str(led_start or "top").lower(), 270.0))
    turn = -1.0 if str(rotation or "").lower() == "counter" else 1.0
    slots = [fans[i] for i in (_normalize_group_order(group_order, len(fans)) or range(len(fans)))]

    keyed = []
    for slot, leds in enumerate(slots):
        n_inner = max(0, min(int(inner_leds), len(leds)))
        n_outer = len(leds) - n_inner
        if inner_first:
            rings = ((leds[n_inner:], 0.42), (leds[:n_inner], 0.15))
        else:
            rings = ((leds[:n_outer], 0.42), (leds[n_outer:], 0.15))
        for ring, radius in rings:
            for j, led in enumerate(ring):
                angle = start + turn * 2.0 * math.pi * j / len(ring)
                dx, dy = radius * math.cos(angle), radius * math.sin(angle)
                along = slot + step_sign * (dy if vertical else dx)
                across = dx if vertical else dy
                keyed.append(((round(along, 4), round(across, 4)), led))
    keyed.sort(key=lambda t: t[0])
    order = [led for _, led in keyed]
    seen = set(order)
    order.extend(i for i in range(total) if i not in seen)
    return order


def _build_aio_cluster_orders(
    positions,
    cluster_count=3,
    group_sort="x",
    group_order=None,
    start="top",
    direction="clockwise",
    flip_x=False,
    flip_y=False,
    swap_xy=False,
    pump_first=False,
):
    points = _transform_points(positions, flip_x, flip_y, swap_xy)
    if not points:
        return None
    try:
        k = int(cluster_count)
    except Exception:
        k = 1
    k = max(1, min(k, len(points)))
    clusters = _kmeans_2d(points, k) if k > 1 else [points]
    cluster_info = []
    for c in clusters:
        if not c:
            continue
        cx = sum(p[1] for p in c) / len(c)
        cy = sum(p[2] for p in c) / len(c)
        cluster_info.append((c, (cx, cy)))
    if not cluster_info:
        return None
    cluster_info.sort(key=lambda t: _cluster_sort_key(t[1], group_sort))
    order_idx = _normalize_group_order(group_order, len(cluster_info))
    if order_idx:
        cluster_info = [cluster_info[i] for i in order_idx]
    elif pump_first and len(cluster_info) > 1:
        gx = sum(p[1] for p in points) / len(points)
        gy = sum(p[2] for p in points) / len(points)
        pump_idx = min(
            range(len(cluster_info)),
            key=lambda i: (cluster_info[i][1][0] - gx) ** 2
            + (cluster_info[i][1][1] - gy) ** 2,
        )
        if pump_idx != 0:
            pump_cluster = cluster_info.pop(pump_idx)
            cluster_info.insert(0, pump_cluster)

    orders = []
    for c, center in cluster_info:
        cx, cy = center
        pts = [(idx, x, y, cx, cy) for idx, x, y in c]
        order = _angle_order(pts, start, direction)
        if not order:
            order = [p[0] for p in c]
        orders.append(order)
    return orders


def _build_pump_lr_pairs(
    positions,
    start="left",
    flip_x=False,
    flip_y=False,
    swap_xy=False,
    allowed_indices=None,
):
    allowed = set(int(i) for i in allowed_indices) if allowed_indices else None
    points = _transform_points(positions, flip_x, flip_y, swap_xy, allowed=allowed)
    if not points:
        return None
    cy =sum(p[2] for p in points) / len(points)
    top = [p for p in points if p[2] <= cy]
    bottom = [p for p in points if p[2] > cy]
    start = (start or "left").lower()
    reverse = start == "right"
    top.sort(key=lambda p: (p[1], p[2]), reverse=reverse)
    bottom.sort(key=lambda p: (p[1], p[2]), reverse=reverse)
    pairs = []
    max_len = max(len(top), len(bottom))
    for i in range(max_len):
        pair = []
        if i < len(top):
            pair.append(top[i][0])
        if i < len(bottom):
            pair.append(bottom[i][0])
        if pair:
            pairs.append(pair)
    return pairs


def _normalize_mode(value):
    v = str(value or "").strip().lower()
    if v in ("2", "g", "group", "groupe"):
        return "group"
    if v in ("3", "f", "fusion"):
        return "fusion"
    if v in ("1", "u", "unique"):
        return "unique"
    return None


def _normalize_name(value):
    return str(value or "").strip().lower()


def _cluster_rows_by_y(points, rows_count):
    ys = [p[2] for p in points]
    ys_sorted = sorted(ys)
    if not ys_sorted:
        return []
    if rows_count >= len(ys_sorted):
        return [[p] for p in sorted(points, key=lambda p: p[2])]
    centers = []
    for i in range(rows_count):
        q = i / (rows_count - 1) if rows_count > 1 else 0
        idx = int(q * (len(ys_sorted) - 1))
        centers.append(ys_sorted[idx])
    for _ in range(20):
        clusters = [[] for _ in range(rows_count)]
        for point in points:
            cluster_idx = min(range(rows_count), key=lambda j: abs(point[2] - centers[j]))
            clusters[cluster_idx].append(point)
        new_centers = []
        for i, cluster in enumerate(clusters):
            if cluster:
                new_centers.append(sum(p[2] for p in cluster) / len(cluster))
            else:
                new_centers.append(centers[i])
        delta = max(abs(new_centers[i] - centers[i]) for i in range(rows_count))
        centers = new_centers
        if delta < 1e-3:
            break
    return [cluster for _, cluster in sorted(zip(centers, clusters), key=lambda t: t[0])]


def _compute_serpentine_led_order(
    positions,
    row_tolerance=None,
    first_dir="left",
    row_order="top",
    rows_count=None,
    flip_x=False,
    flip_y=False,
    swap_xy=False,
    mode="serpentine",
):
    points = _transform_points(positions, flip_x, flip_y, swap_xy)
    if not points:
        return None
    rows = []
    if rows_count is not None:
        try:
            k = int(rows_count)
        except Exception:
            k = None
        if k and k > 1:
            rows = _cluster_rows_by_y(points, k)
            # Apply requested top/bottom row order after row clustering.
            rows = sorted(
                rows,
                key=lambda row: sum(p[2] for p in row) / len(row) if row else 0.0,
                reverse=(row_order or "top").lower() == "bottom",
            )
    if not rows:
        ys = sorted({p[2] for p in points})
        if row_tolerance is None or row_tolerance <= 0:
            if len(ys) <= 1:
                tol = 1.0
            else:
                min_diff = None
                for i in range(1, len(ys)):
                    diff = ys[i] - ys[i - 1]
                    if diff > 0 and (min_diff is None or diff < min_diff):
                        min_diff = diff
                tol = (min_diff / 2.0) if min_diff else 1.0
        else:
            tol = float(row_tolerance)

        row_order_val = (row_order or "top").lower()
        if row_order_val == "bottom":
            points = sorted(points, key=lambda p: (-p[2], p[1]))
        else:
            points = sorted(points, key=lambda p: (p[2], p[1]))
        current = []
        current_y = None
        for point in points:
            if current_y is None:
                current_y = point[2]
                current = [point]
                continue
            if abs(point[2] - current_y) <= tol:
                current.append(point)
            else:
                rows.append(current)
                current = [point]
                current_y = point[2]
        if current:
            rows.append(current)

    first_dir = (first_dir or "left").lower()
    mode = (mode or "serpentine").lower()
    order = []
    for idx_row, row in enumerate(rows):
        if mode == "linear":
            reverse = first_dir == "right"
        else:
            if first_dir == "right":
                reverse = (idx_row % 2 == 0)
            else:
                reverse = (idx_row % 2 == 1)
        row_sorted = sorted(row, key=lambda p: p[1], reverse=reverse)
        order.extend([p[0] for p in row_sorted])
    return order


def _enum_to_int(value):
    if hasattr(value, "value"):
        return int(value.value)
    return int(value)


def parse_device_types(value, sdk):
    if not value:
        return []
    items = []
    if isinstance(value, str):
        parts = [p.strip() for p in value.replace(",", "|").split("|")]
        items = [p for p in parts if p]
    elif isinstance(value, (list, tuple, set)):
        items = [str(p).strip() for p in value if str(p).strip()]
    else:
        return []

    out = []
    for name in items:
        if hasattr(sdk.CorsairDeviceType, name):
            out.append(_enum_to_int(getattr(sdk.CorsairDeviceType, name)))
        else:
            try:
                out.append(int(name))
            except Exception:
                pass
    return out


def parse_device_type_mask(value, sdk):
    if value is None:
        return getattr(sdk.CorsairDeviceType, "CDT_All", 0xFFFFFFFF)
    if isinstance(value, int):
        return value
    items = []
    if isinstance(value, str):
        s = value.strip()
        if "|" in s or "," in s:
            parts = [p.strip() for p in s.replace(",", "|").split("|")]
            items = [p for p in parts if p]
        else:
            if hasattr(sdk.CorsairDeviceType, s):
                return _enum_to_int(getattr(sdk.CorsairDeviceType, s))
            try:
                return int(s)
            except Exception:
                return getattr(sdk.CorsairDeviceType, "CDT_All", 0xFFFFFFFF)
    elif isinstance(value, (list, tuple, set)):
        items = [str(p).strip() for p in value if str(p).strip()]

    if items:
        mask = 0
        for name in items:
            if hasattr(sdk.CorsairDeviceType, name):
                mask |= _enum_to_int(getattr(sdk.CorsairDeviceType, name))
            else:
                try:
                    mask |= int(name)
                except Exception:
                    pass
        if mask:
            return mask

    return getattr(sdk.CorsairDeviceType, "CDT_All", 0xFFFFFFFF)


_bootstrap_tk_runtime()


APP_VERSION = "0.2.0"

_MODE_WINDOW = None
_MODE_EXIT = "__exit__"
_I18N = None


def _prompt_mode_cli(default_mode):
    default_mode = _normalize_mode(default_mode) or "unique"
    if sys.stdin is None:
        return default_mode
    while True:
        try:
            raw = input(
                f"Choisir mode [1=unique, 2=groupe, 3=fusion] (defaut {default_mode}): "
            )
        except (EOFError, RuntimeError, OSError):
            # No usable console (windowed exe): fall back to the default mode.
            return default_mode
        mode = _normalize_mode(raw)
        if mode:
            return mode
        if raw.strip() == "":
            return default_mode
        print("Choix invalide. Tape 1 (unique), 2 (groupe) ou 3 (fusion).")


class _ModeWindowThread:
    def __init__(self, default_mode, i18n_obj):
        self.default_mode = _normalize_mode(default_mode) or "unique"
        self.i18n = i18n_obj
        self.last_mode = self.default_mode
        self.available = False
        self.closed = False
        self._queue = queue.Queue()
        self._ready = threading.Event()
        # Set by run_bridge once iCUE is connected; enables the layout editor.
        self.layout_backend = None
        self._layout_window = None
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        # Tk can be slow to start on a cold disk; waiting too little would open
        # the CLI prompt while the window still appears afterwards.
        self._ready.wait(timeout=8.0)

    def _toggle_language(self):
        new_lang = "en" if self.i18n.lang == "fr" else "fr"
        self.i18n.set_lang(new_lang)
        persist_config_value("ui_language", new_lang)

    def _run(self):
        try:
            import tkinter as tk
            from tkinter import ttk
            from tkinter import messagebox
        except Exception:
            if self._run_native_win32():
                return
            self.available = False
            self._ready.set()
            return
        try:
            t = self.i18n.t
            root = tk.Tk()
            root.title(t("window_title"))
            root.resizable(False, False)
            root.configure(bg="#1f1f22")

            def push_mode(mode):
                self.last_mode = mode
                while True:
                    try:
                        self._queue.get_nowait()
                    except queue.Empty:
                        break
                self._queue.put(mode)
                status_label.config(text=t("mode_selected", mode=mode))

            def confirm_quit():
                return messagebox.askyesno(
                    t("confirm_close_title"),
                    t("confirm_close_body"),
                    parent=root,
                )

            def on_close():
                if not confirm_quit():
                    return
                self.closed = True
                try:
                    self._queue.put(_MODE_EXIT)
                except Exception:
                    pass
                root.destroy()

            def toggle_language():
                self._toggle_language()
                apply_lang()

            def open_layout():
                window = self._layout_window
                if window is not None and window.winfo_exists():
                    window.deiconify()
                    window.lift()
                    return
                if self.layout_backend is None:
                    messagebox.showinfo(t("layout_title"), t("layout_unavailable"), parent=root)
                    return
                try:
                    import layout_editor

                    self._layout_window = layout_editor.open_editor(
                        root, self.layout_backend, self.i18n
                    )
                except Exception as exc:
                    logging.getLogger("bridge").exception("Editeur de disposition: %s", exc)
                    messagebox.showerror(t("layout_title"), str(exc), parent=root)

            def apply_lang():
                root.title(t("window_title"))
                title_label.config(text=t("app_title"))
                subtitle.config(
                    text=t("choose_mode", default_mode=self.default_mode)
                )
                status_label.config(
                    text=t("mode_selected", mode=self.last_mode)
                )
                btn_unique.config(text=t("mode_unique"))
                btn_group.config(text=t("mode_group"))
                btn_fusion.config(text=t("mode_fusion"))
                btn_lang.config(text=t("toggle_language"))
                btn_layout.config(text=t("layout_button"))
                btn_quit.config(text=t("quit"))

            root.protocol("WM_DELETE_WINDOW", on_close)

            style = ttk.Style()
            try:
                style.theme_use("clam")
            except Exception:
                pass
            style.configure(
                "App.TFrame",
                background="#1f1f22",
            )
            style.configure(
                "Title.TLabel",
                background="#1f1f22",
                foreground="#f2f2f2",
                font=("Segoe UI", 12, "bold"),
            )
            style.configure(
                "App.TLabel",
                background="#1f1f22",
                foreground="#cfcfcf",
                font=("Segoe UI", 9),
            )
            style.configure(
                "App.TButton",
                font=("Segoe UI", 10, "bold"),
                padding=6,
            )

            frame = ttk.Frame(root, padding=16, style="App.TFrame")
            frame.grid(row=0, column=0, sticky="nsew")
            title_label = ttk.Label(
                frame,
                text=t("app_title"),
                style="Title.TLabel",
            )
            title_label.grid(row=0, column=0, columnspan=3, pady=(0, 6))

            subtitle = ttk.Label(
                frame,
                text=t("choose_mode", default_mode=self.default_mode),
                style="App.TLabel",
            )
            subtitle.grid(row=1, column=0, columnspan=3, pady=(0, 8))

            ttk.Separator(frame, orient="horizontal").grid(
                row=2, column=0, columnspan=3, sticky="ew", pady=(0, 10)
            )

            btn_unique = ttk.Button(
                frame, text=t("mode_unique"), style="App.TButton", command=lambda: push_mode("unique")
            )
            btn_group = ttk.Button(
                frame, text=t("mode_group"), style="App.TButton", command=lambda: push_mode("group")
            )
            btn_fusion = ttk.Button(
                frame, text=t("mode_fusion"), style="App.TButton", command=lambda: push_mode("fusion")
            )
            btn_unique.grid(row=3, column=0, padx=6)
            btn_group.grid(row=3, column=1, padx=6)
            btn_fusion.grid(row=3, column=2, padx=6)

            status_label = ttk.Label(
                frame,
                text=t("mode_selected", mode=self.default_mode),
                style="App.TLabel",
            )
            status_label.grid(row=4, column=0, columnspan=3, pady=(10, 6))

            btn_lang = ttk.Button(
                frame, text=t("toggle_language"), style="App.TButton", command=toggle_language
            )
            btn_lang.grid(row=5, column=0, pady=(10, 0), sticky="ew", padx=6)

            btn_layout = ttk.Button(
                frame, text=t("layout_button"), style="App.TButton", command=open_layout
            )
            btn_layout.grid(row=5, column=1, pady=(10, 0), sticky="ew", padx=6)

            btn_quit = ttk.Button(frame, text=t("quit"), style="App.TButton", command=on_close)
            btn_quit.grid(row=5, column=2, pady=(10, 0), sticky="ew")

            self.available = True
            self._ready.set()
            root.mainloop()
            self.available = False
        except Exception:
            if self._run_native_win32():
                return
            self.available = False
            self._ready.set()

    def _run_native_win32(self):
        if sys.platform != "win32":
            return False
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.WinDLL("user32", use_last_error=True)
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

            LRESULT = ctypes.c_ssize_t
            HCURSOR = wintypes.HANDLE
            WNDPROC = ctypes.WINFUNCTYPE(
                LRESULT,
                wintypes.HWND,
                wintypes.UINT,
                wintypes.WPARAM,
                wintypes.LPARAM,
            )

            class WNDCLASSW(ctypes.Structure):
                _fields_ = [
                    ("style", wintypes.UINT),
                    ("lpfnWndProc", WNDPROC),
                    ("cbClsExtra", ctypes.c_int),
                    ("cbWndExtra", ctypes.c_int),
                    ("hInstance", wintypes.HINSTANCE),
                    ("hIcon", wintypes.HICON),
                    ("hCursor", HCURSOR),
                    ("hbrBackground", wintypes.HBRUSH),
                    ("lpszMenuName", wintypes.LPCWSTR),
                    ("lpszClassName", wintypes.LPCWSTR),
                ]

            user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
            user32.RegisterClassW.restype = wintypes.ATOM
            user32.CreateWindowExW.argtypes = [
                wintypes.DWORD,
                wintypes.LPCWSTR,
                wintypes.LPCWSTR,
                wintypes.DWORD,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                wintypes.HWND,
                wintypes.HMENU,
                wintypes.HINSTANCE,
                wintypes.LPVOID,
            ]
            user32.CreateWindowExW.restype = wintypes.HWND
            user32.DefWindowProcW.argtypes = [
                wintypes.HWND,
                wintypes.UINT,
                wintypes.WPARAM,
                wintypes.LPARAM,
            ]
            user32.DefWindowProcW.restype = LRESULT
            user32.DestroyWindow.argtypes = [wintypes.HWND]
            user32.GetMessageW.argtypes = [
                ctypes.POINTER(wintypes.MSG),
                wintypes.HWND,
                wintypes.UINT,
                wintypes.UINT,
            ]
            user32.GetMessageW.restype = wintypes.BOOL
            user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
            user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
            user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
            user32.UpdateWindow.argtypes = [wintypes.HWND]
            user32.SendMessageW.argtypes = [
                wintypes.HWND,
                wintypes.UINT,
                wintypes.WPARAM,
                wintypes.LPARAM,
            ]
            user32.SetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPCWSTR]
            user32.PostQuitMessage.argtypes = [ctypes.c_int]
            user32.MessageBoxW.argtypes = [
                wintypes.HWND,
                wintypes.LPCWSTR,
                wintypes.LPCWSTR,
                wintypes.UINT,
            ]
            user32.MessageBoxW.restype = ctypes.c_int
            user32.GetSystemMetrics.argtypes = [ctypes.c_int]
            user32.GetSystemMetrics.restype = ctypes.c_int
            kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
            kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE
            gdi32.GetStockObject.argtypes = [ctypes.c_int]
            gdi32.GetStockObject.restype = wintypes.HGDIOBJ

            WS_CAPTION = 0x00C00000
            WS_SYSMENU = 0x00080000
            WS_MINIMIZEBOX = 0x00020000
            WS_VISIBLE = 0x10000000
            WS_CHILD = 0x40000000
            SS_LEFT = 0x00000000
            BS_PUSHBUTTON = 0x00000000
            BN_CLICKED = 0
            WM_CLOSE = 0x0010
            WM_DESTROY = 0x0002
            WM_COMMAND = 0x0111
            WM_SETFONT = 0x0030
            SW_SHOW = 5
            IDYES = 6
            MB_YESNO = 0x00000004
            MB_ICONQUESTION = 0x00000020
            DEFAULT_GUI_FONT = 17
            COLOR_WINDOW = 5

            ID_UNIQUE = 1001
            ID_GROUP = 1002
            ID_FUSION = 1003
            ID_LANG = 1004
            ID_QUIT = 1005

            t = self.i18n.t
            controls = {}
            font = gdi32.GetStockObject(DEFAULT_GUI_FONT)

            def set_control_text(name, text):
                handle = controls.get(name)
                if handle:
                    user32.SetWindowTextW(handle, str(text))

            def apply_lang(hwnd):
                user32.SetWindowTextW(hwnd, t("window_title"))
                set_control_text("title", t("app_title"))
                set_control_text(
                    "subtitle",
                    t("choose_mode", default_mode=self.default_mode),
                )
                set_control_text(
                    "status",
                    t("mode_selected", mode=self.last_mode),
                )
                set_control_text("unique", t("mode_unique"))
                set_control_text("group", t("mode_group"))
                set_control_text("fusion", t("mode_fusion"))
                set_control_text("lang", t("toggle_language"))
                set_control_text("quit", t("quit"))

            def push_mode(mode):
                self.last_mode = mode
                while True:
                    try:
                        self._queue.get_nowait()
                    except queue.Empty:
                        break
                self._queue.put(mode)
                set_control_text("status", t("mode_selected", mode=mode))

            def confirm_quit(hwnd):
                result = user32.MessageBoxW(
                    hwnd,
                    t("confirm_close_body"),
                    t("confirm_close_title"),
                    MB_YESNO | MB_ICONQUESTION,
                )
                return result == IDYES

            def wndproc(hwnd, msg, wparam, lparam):
                if msg == WM_COMMAND:
                    control_id = int(wparam) & 0xFFFF
                    notify_code = (int(wparam) >> 16) & 0xFFFF
                    if notify_code == BN_CLICKED:
                        if control_id == ID_UNIQUE:
                            push_mode("unique")
                            return 0
                        if control_id == ID_GROUP:
                            push_mode("group")
                            return 0
                        if control_id == ID_FUSION:
                            push_mode("fusion")
                            return 0
                        if control_id == ID_LANG:
                            self._toggle_language()
                            apply_lang(hwnd)
                            return 0
                        if control_id == ID_QUIT:
                            if confirm_quit(hwnd):
                                self.closed = True
                                try:
                                    self._queue.put(_MODE_EXIT)
                                except Exception:
                                    pass
                                user32.DestroyWindow(hwnd)
                            return 0
                if msg == WM_CLOSE:
                    if confirm_quit(hwnd):
                        self.closed = True
                        try:
                            self._queue.put(_MODE_EXIT)
                        except Exception:
                            pass
                        user32.DestroyWindow(hwnd)
                    return 0
                if msg == WM_DESTROY:
                    self.available = False
                    user32.PostQuitMessage(0)
                    return 0
                return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

            wndproc_ref = WNDPROC(wndproc)
            self._native_wndproc_ref = wndproc_ref
            hinstance = kernel32.GetModuleHandleW(None)
            class_name = "LedFxIcueBridgeModeWindow"
            wc = WNDCLASSW()
            wc.lpfnWndProc = wndproc_ref
            wc.hInstance = hinstance
            try:
                user32.LoadCursorW.argtypes = [wintypes.HINSTANCE, wintypes.LPVOID]
                user32.LoadCursorW.restype = HCURSOR
                wc.hCursor = user32.LoadCursorW(None, ctypes.c_void_p(32512))  # IDC_ARROW
            except Exception:
                pass
            wc.hbrBackground = ctypes.c_void_p(COLOR_WINDOW + 1)
            wc.lpszClassName = class_name
            if not user32.RegisterClassW(ctypes.byref(wc)):
                err = ctypes.get_last_error()
                if err != 1410:  # ERROR_CLASS_ALREADY_EXISTS
                    raise ctypes.WinError(err)

            width = 420
            height = 230
            screen_w = user32.GetSystemMetrics(0)
            screen_h = user32.GetSystemMetrics(1)
            x = max(0, (screen_w - width) // 2)
            y = max(0, (screen_h - height) // 2)
            hwnd = user32.CreateWindowExW(
                0,
                class_name,
                t("window_title"),
                WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX,
                x,
                y,
                width,
                height,
                None,
                None,
                hinstance,
                None,
            )
            if not hwnd:
                raise ctypes.WinError(ctypes.get_last_error())

            def create_control(kind, text, style, x_pos, y_pos, w, h, control_id=0):
                handle = user32.CreateWindowExW(
                    0,
                    kind,
                    str(text),
                    WS_VISIBLE | WS_CHILD | style,
                    x_pos,
                    y_pos,
                    w,
                    h,
                    hwnd,
                    ctypes.c_void_p(control_id),
                    hinstance,
                    None,
                )
                if handle and font:
                    user32.SendMessageW(handle, WM_SETFONT, font, 1)
                return handle

            controls["title"] = create_control(
                "STATIC", t("app_title"), SS_LEFT, 20, 16, 370, 24
            )
            controls["subtitle"] = create_control(
                "STATIC",
                t("choose_mode", default_mode=self.default_mode),
                SS_LEFT,
                20,
                44,
                370,
                24,
            )
            controls["unique"] = create_control(
                "BUTTON", t("mode_unique"), BS_PUSHBUTTON, 20, 80, 115, 34, ID_UNIQUE
            )
            controls["group"] = create_control(
                "BUTTON", t("mode_group"), BS_PUSHBUTTON, 150, 80, 115, 34, ID_GROUP
            )
            controls["fusion"] = create_control(
                "BUTTON", t("mode_fusion"), BS_PUSHBUTTON, 280, 80, 115, 34, ID_FUSION
            )
            controls["status"] = create_control(
                "STATIC",
                t("mode_selected", mode=self.default_mode),
                SS_LEFT,
                20,
                126,
                370,
                24,
            )
            controls["lang"] = create_control(
                "BUTTON", t("toggle_language"), BS_PUSHBUTTON, 20, 158, 245, 32, ID_LANG
            )
            controls["quit"] = create_control(
                "BUTTON", t("quit"), BS_PUSHBUTTON, 280, 158, 115, 32, ID_QUIT
            )

            apply_lang(hwnd)
            self.available = True
            self._ready.set()
            user32.ShowWindow(hwnd, SW_SHOW)
            user32.UpdateWindow(hwnd)

            msg = wintypes.MSG()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            self.available = False
            return True
        except Exception:
            self.available = False
            self._ready.set()
            return False

    def wait_for_choice(self, timeout=None):
        if not self.available:
            if timeout is None:
                return self.default_mode
            return None
        try:
            if timeout is None:
                mode = self._queue.get()
            else:
                mode = self._queue.get(timeout=timeout)
        except queue.Empty:
            return None
        except Exception:
            return self.last_mode or self.default_mode
        return mode or self.default_mode

    def poll(self):
        if not self.available:
            return None
        mode = None
        while True:
            try:
                mode = self._queue.get_nowait()
            except queue.Empty:
                break
        return mode



def prompt_mode(default_mode):
    default_mode = _normalize_mode(default_mode) or "unique"
    global _MODE_WINDOW, _I18N
    if _I18N is None:
        _I18N = i18n.get_i18n()
    if _MODE_WINDOW is None or not _MODE_WINDOW.available:
        window = _ModeWindowThread(default_mode, _I18N)
        if not window.available:
            _MODE_WINDOW = None
            return _prompt_mode_cli(default_mode)
        _MODE_WINDOW = window
    while True:
        mode = _MODE_WINDOW.wait_for_choice(timeout=0.15)
        if mode is not None:
            if mode == _MODE_EXIT:
                raise SystemExit(0)
            return mode


def choose_mode(cfg, args, prompt_allowed=True):
    if getattr(args, "mode", None):
        return _normalize_mode(args.mode) or "unique"
    default_mode = _normalize_mode(cfg.get("default_mode")) or "unique"
    if not cfg.get("startup_prompt", True) or not prompt_allowed:
        return default_mode
    return prompt_mode(default_mode)


# Session callbacks of disconnected SDK wrappers; iCUE may still call them.
_SDK_CALLBACKS = []


class CueSdkWrapper:
    def __init__(self):
        try:
            from cuesdk import (
                CueSdk,
                CorsairDeviceFilter,
                CorsairDeviceType,
                CorsairAccessLevel,
                CorsairLedColor,
                CorsairError,
            )
            try:
                from cuesdk import CorsairSessionState
            except Exception:
                CorsairSessionState = None
        except Exception as exc:
            raise RuntimeError(
                "Le module Python 'cuesdk' est requis. Installe-le avec "
                "'py -3 -m pip install -U cuesdk'."
            ) from exc
        self.sdk = CueSdk()
        self.CorsairDeviceFilter = CorsairDeviceFilter
        self.CorsairDeviceType = CorsairDeviceType
        self.CorsairAccessLevel = CorsairAccessLevel
        self.CorsairLedColor = CorsairLedColor
        self.CorsairError = CorsairError
        self.CorsairSessionState = CorsairSessionState

    def _call(self, names, *args):
        for name in names:
            fn = getattr(self.sdk, name, None)
            if fn is not None:
                return fn(*args)
        raise RuntimeError(f"Methode SDK introuvable: {names}")

    def connect(self):
        def _on_state_changed(evt):
            _ = evt
        try:
            return self._call(("connect",), _on_state_changed)
        except TypeError:
            return self._call(("connect",))

    def disconnect(self):
        # cuesdk drops its ctypes session callback *before* CorsairDisconnect, which
        # still invokes it: the freed thunk crashes the whole process. Keep it alive.
        handler = getattr(self.sdk, "session_state_changed_event_handler", None)
        if handler is not None:
            _SDK_CALLBACKS.append(handler)
        try:
            return self._call(("disconnect",))
        except Exception:
            return None

    def _control_levels(self, access_level=None):
        levels = []
        if access_level is not None:
            levels.append(access_level)
        else:
            if hasattr(self.CorsairAccessLevel, "CAL_ExclusiveLightingControl"):
                levels.append(self.CorsairAccessLevel.CAL_ExclusiveLightingControl)
            if hasattr(self.CorsairAccessLevel, "CAL_Shared"):
                levels.append(self.CorsairAccessLevel.CAL_Shared)
        deduped = []
        seen = set()
        for level in levels:
            if level is None:
                continue
            try:
                key = int(level)
            except Exception:
                key = level
            if key in seen:
                continue
            seen.add(key)
            deduped.append(level)
        return deduped

    def request_control(self, device_id=None, access_level=None):
        if not device_id:
            return None
        levels = self._control_levels(access_level)
        if not levels:
            return None
        last_err = None
        for name in ("request_control", "requestControl"):
            fn = getattr(self.sdk, name, None)
            if fn is None:
                continue
            for level in levels:
                try:
                    err = fn(device_id, level)
                except TypeError:
                    continue
                except Exception as exc:
                    last_err = exc
                    continue
                last_err = err
                if self.is_success(err):
                    return err
        return last_err

    def release_control(self, device_id=None):
        try:
            return self._call(("release_control", "releaseControl"), device_id)
        except TypeError:
            try:
                return self._call(("release_control", "releaseControl"))
            except Exception:
                return None
        except Exception:
            return None

    def get_devices(self, device_type_mask):
        filt = self.CorsairDeviceFilter(device_type_mask=device_type_mask)
        return self._call(("get_devices", "getDevices"), filt)

    def get_session_state(self):
        return self._call(("get_session_state", "getSessionState"))

    def get_device_info(self, device_id):
        return self._call(("get_device_info", "getDeviceInfo"), device_id)

    def get_led_positions(self, device_id):
        return self._call(("get_led_positions", "getLedPositions"), device_id)

    def set_layer_priority(self, priority):
        return self._call(("set_layer_priority", "setLayerPriority"), int(priority))

    def set_led_colors_buffer(self, device_id, colors):
        return self._call(
            ("set_led_colors_buffer", "setLedColorsBuffer"), device_id, colors
        )

    def set_led_colors(self, device_id, colors):
        return self._call(
            ("set_led_colors", "setLedColors", "set_leds_colors"), device_id, colors
        )

    def flush(self):
        for name in (
            "set_led_colors_flush_buffer_async",
            "setLedColorsFlushBufferAsync",
        ):
            fn = getattr(self.sdk, name, None)
            if fn is None:
                continue
            try:
                res = fn(None)
                return self.CorsairError.CE_Success if res is None else res
            except TypeError:
                try:
                    res = fn(None, None)
                    return self.CorsairError.CE_Success if res is None else res
                except Exception:
                    pass
            except Exception:
                return None
        try:
            res = self._call(
                (
                    "set_led_colors_flush_buffer",
                    "setLedColorsFlushBuffer",
                    "flush_led_colors_buffer",
                )
            )
            return self.CorsairError.CE_Success if res is None else res
        except Exception:
            return None

    def is_success(self, err):
        if err is None:
            return True
        try:
            return int(err) == int(self.CorsairError.CE_Success)
        except Exception:
            return False


class LedMapper:
    def __init__(self, sdk, device_type_mask):
        self.sdk = sdk
        self.device_type_mask = device_type_mask
        self.led_colors_by_device = {}
        self.positions_by_device = {}
        self.order_by_device = {}
        self.global_map = []
        self.total_leds = 0
        # Stage RGB bytes separately from CorsairLedColor objects.
        self._staging = {}
        self._staging_lock = threading.Lock()
        self.devices = []
        self.device_types_include = set()
        self.device_types_exclude = set()
        self.direct_async_timeout = 10.0
        self._direct_async_lock = threading.Lock()
        self._direct_async_event = threading.Event()
        self._direct_async_thread = None
        # Store pending device ids only; color copies run on the writer thread.
        self._direct_async_device_ids = None
        self._direct_async_inflight_since = 0.0
        self._direct_async_last_error = None
        self._closed = False
        # id(map_list) -> (map_list, compiled entries); maps are rebuilt with the mapper.
        self._compiled_maps = {}
        # Per-thread reusable CorsairLedColor objects (the SDK copies them during the call).
        self._color_cache = threading.local()
        try:
            self._success_code = int(self.sdk.CorsairError.CE_Success)
        except Exception:
            self._success_code = 0
        try:
            self._no_control_code = int(self.sdk.CorsairError.CE_NoControl)
        except Exception:
            self._no_control_code = 2
        self.debug_icue = False
        self.perf_debug = False
        self.perf_logger = None
        self.perf_threshold = 0.20
        self.perf_log_cooldown = 2.0
        self._perf_last_log = {}

    def set_debug(self, enabled):
        self.debug_icue = bool(enabled)

    def set_perf_debug(self, enabled, logger=None, threshold=0.20, cooldown=2.0):
        self.perf_debug = bool(enabled)
        self.perf_logger = logger
        try:
            self.perf_threshold = max(0.02, float(threshold))
        except Exception:
            self.perf_threshold = 0.20
        try:
            self.perf_log_cooldown = max(0.0, float(cooldown))
        except Exception:
            self.perf_log_cooldown = 2.0

    def _perf_warn(self, key, message, *args):
        if not self.perf_debug:
            return
        now = time.monotonic()
        last = self._perf_last_log.get(key, 0.0)
        if now - last < self.perf_log_cooldown:
            return
        self._perf_last_log[key] = now
        logger = self.perf_logger or logging.getLogger("bridge")
        logger.warning(message, *args)

    def _perf_apply_warn(self, update_mode, elapsed, device_ids, map_list, ok, err=None):
        if elapsed <= self.perf_threshold:
            return
        self._perf_warn(
            f"apply_{update_mode}",
            "[PERF] apply_frame_map %s lent %.3fs devices=%s leds=%s ok=%s err=%s",
            update_mode,
            elapsed,
            len(device_ids or []),
            len(map_list or []),
            ok,
            err,
        )

    def set_type_filters(self, include_types, exclude_types):
        self.device_types_include = set(include_types or [])
        self.device_types_exclude = set(exclude_types or [])

    def _get_device_type(self, info, dev):
        for obj in (info, dev):
            if obj is None:
                continue
            if hasattr(obj, "type"):
                return self._type_to_int(getattr(obj, "type"))
            if hasattr(obj, "device_type"):
                return self._type_to_int(getattr(obj, "device_type"))
        return None

    def _type_to_int(self, val):
        if val is None:
            return None
        try:
            if hasattr(val, "value"):
                return int(val.value)
            return int(val)
        except Exception:
            return None

    def _get_device_id(self, dev):
        return getattr(dev, "device_id", None) or getattr(dev, "id", None)

    def _get_led_id(self, pos):
        return getattr(pos, "id", None) or getattr(pos, "led_id", None)

    def _get_led_xy(self, pos):
        x = _get_attr(pos, ("cx", "x", "left"))
        y = _get_attr(pos, ("cy", "y", "top"))
        try:
            if x is not None:
                x = float(x)
            if y is not None:
                y = float(y)
        except Exception:
            return None, None
        return x, y

    def apply_serpentine(
        self,
        device_types,
        row_tolerance=None,
        first_dir="left",
        row_order="top",
        rows_count=None,
        flip_x=False,
        flip_y=False,
        swap_xy=False,
        mode="serpentine",
    ):
        if not device_types:
            return
        for dev in self.devices:
            dev_type = dev.get("device_type")
            if dev_type not in device_types:
                continue
            device_id = dev["device_id"]
            positions = self.positions_by_device.get(device_id)
            order = _compute_serpentine_led_order(
                positions,
                row_tolerance=row_tolerance,
                first_dir=first_dir,
                row_order=row_order,
                rows_count=rows_count,
                flip_x=flip_x,
                flip_y=flip_y,
                swap_xy=swap_xy,
                mode=mode,
            )
            if order:
                self.order_by_device[device_id] = order

    def apply_index_order(self, device_types, reverse=False):
        if not device_types:
            return
        for dev in self.devices:
            dev_type = dev.get("device_type")
            if dev_type not in device_types:
                continue
            device_id = dev["device_id"]
            colors = self.led_colors_by_device.get(device_id) or []
            order = list(range(len(colors)))
            if reverse:
                order.reverse()
            self.order_by_device[device_id] = order

    def apply_angle_order(
        self,
        device_types,
        start="left",
        direction="clockwise",
        flip_x=False,
        flip_y=False,
        swap_xy=False,
    ):
        if not device_types:
            return
        for dev in self.devices:
            dev_type = dev.get("device_type")
            if dev_type not in device_types:
                continue
            device_id = dev["device_id"]
            pts = _transform_points(
                self.positions_by_device.get(device_id), flip_x, flip_y, swap_xy
            )
            if not pts:
                continue
            cx = sum(p[1] for p in pts) / len(pts)
            cy = sum(p[2] for p in pts) / len(pts)
            order = _angle_order(
                [(idx, x, y, cx, cy) for idx, x, y in pts], start, direction
            )
            if order:
                self.order_by_device[device_id] = order

    def apply_axis_order(self, device_types, axis="auto"):
        if not device_types:
            return
        axis = (axis or "auto").lower()
        for dev in self.devices:
            dev_type = dev.get("device_type")
            if dev_type not in device_types:
                continue
            device_id = dev["device_id"]
            pts = _transform_points(self.positions_by_device.get(device_id))
            if not pts:
                continue
            xs = [p[1] for p in pts]
            ys = [p[2] for p in pts]
            rx = max(xs) - min(xs)
            ry = max(ys) - min(ys)
            chosen = axis
            if chosen == "auto":
                chosen = "x" if rx >= ry else "y"
            if chosen == "y":
                pts.sort(key=lambda p: (p[2], p[1]))
            else:
                pts.sort(key=lambda p: (p[1], p[2]))
            order = [p[0] for p in pts]
            if order:
                self.order_by_device[device_id] = order

    def apply_aio_cluster(
        self,
        device_types,
        cluster_count=3,
        group_sort="x",
        group_order=None,
        start="top",
        direction="clockwise",
        flip_x=False,
        flip_y=False,
        swap_xy=False,
        pump_first=False,
    ):
        if not device_types:
            return
        for dev in self.devices:
            dev_type = dev.get("device_type")
            if dev_type not in device_types:
                continue
            device_id = dev["device_id"]
            positions = self.positions_by_device.get(device_id)
            orders = _build_aio_cluster_orders(
                positions,
                cluster_count=cluster_count,
                group_sort=group_sort,
                group_order=group_order,
                start=start,
                direction=direction,
                flip_x=flip_x,
                flip_y=flip_y,
                swap_xy=swap_xy,
                pump_first=pump_first,
            )
            if not orders:
                continue
            order = []
            for chunk in orders:
                order.extend(chunk)
            if order:
                self.order_by_device[device_id] = order

    def apply_reverse_order(self, device_types):
        if not device_types:
            return
        for dev in self.devices:
            dev_type = dev.get("device_type")
            if dev_type not in device_types:
                continue
            device_id = dev["device_id"]
            colors = self.led_colors_by_device.get(device_id) or []
            order = self.order_by_device.get(device_id) or list(range(len(colors)))
            order = list(reversed(order))
            self.order_by_device[device_id] = order

    def apply_fan_ring(
        self,
        device_types,
        outer_leds=12,
        inner_leds=4,
        fan_count=None,
        start="top",
        direction="clockwise",
        group_sort="x",
        layout="sequential",
        group_order=None,
        ring_order="index",
        lock_to_first=False,
        inner_first=False,
        flip_x=False,
        flip_y=True,
        swap_xy=False,
    ):
        if not device_types:
            return
        leds_per_fan = int(outer_leds) + int(inner_leds)
        if leds_per_fan <= 0:
            return
        for dev in self.devices:
            dev_type = dev.get("device_type")
            if dev_type not in device_types:
                continue
            device_id = dev["device_id"]
            positions = self.positions_by_device.get(device_id)
            if not positions:
                continue
            fans, points = _fan_layout(
                positions, fan_count, leds_per_fan, layout, group_sort, flip_x, flip_y, swap_xy
            )
            order_idx = _normalize_group_order(group_order, len(fans))
            if order_idx:
                fans = [fans[i] for i in order_idx]

            order = []
            base_pattern = None
            for fan_indices in fans:
                if not fan_indices:
                    continue
                if not points:
                    order.extend(fan_indices)
                    continue
                if lock_to_first and base_pattern is not None:
                    allowed = set(fan_indices)
                    ring = [fan_indices[0] + i for i in base_pattern if fan_indices[0] + i in allowed]
                else:
                    members = set(fan_indices)
                    ring = _ring_order(
                        [p for p in points if p[0] in members],
                        outer_leds,
                        inner_leds,
                        start,
                        direction,
                        inner_first,
                        ring_order,
                    )
                    if lock_to_first and ring:
                        base_pattern = [i - fan_indices[0] for i in ring]
                order.extend(ring or fan_indices)
            if order:
                self.order_by_device[device_id] = order

    def apply_fan_surface(
        self,
        device_types,
        fan_count=None,
        outer_leds=12,
        inner_leds=4,
        group_order=None,
        first="top",
        led_start="top",
        rotation="clockwise",
        inner_first=False,
    ):
        """Order each fan device as one surface (see fan_surface_order)."""
        if not device_types:
            return
        leds_per_fan = int(outer_leds) + int(inner_leds)
        if leds_per_fan <= 0:
            return
        for dev in self.devices:
            if dev.get("device_type") not in device_types:
                continue
            device_id = dev["device_id"]
            positions = self.positions_by_device.get(device_id)
            if not positions:
                continue
            # Hub positions are unreliable, so fans are always split by LED index.
            fans, _ = _fan_layout(positions, fan_count, leds_per_fan, "sequential")
            self.order_by_device[device_id] = fan_surface_order(
                len(positions), fans, inner_leds, first, led_start, rotation, inner_first, group_order
            )

    def enumerate(self, clear_on_start):
        devices, err = self.sdk.get_devices(self.device_type_mask)
        if err != self.sdk.CorsairError.CE_Success:
            raise RuntimeError(f"get_devices erreur: {err}")

        for dev in devices:
            device_id = self._get_device_id(dev)
            if device_id is None:
                continue
            positions, perr = self.sdk.get_led_positions(device_id)
            if perr != self.sdk.CorsairError.CE_Success or not positions:
                continue
            info = None
            try:
                info, _ = self.sdk.get_device_info(device_id)
            except Exception:
                info = None
            model = _get_attr(info, ("model",))
            serial = _get_attr(info, ("serial",))
            dev_type = self._get_device_type(info, dev)
            if self.device_types_include and dev_type not in self.device_types_include:
                continue
            if self.device_types_exclude and dev_type in self.device_types_exclude:
                continue
            colors = []
            positions_list = []
            for pos in positions:
                led_id = self._get_led_id(pos)
                if led_id is None:
                    continue
                x, y = self._get_led_xy(pos)
                positions_list.append({"id": led_id, "x": x, "y": y})
                color = self._make_color(led_id, 0, 0, 0)
                colors.append(color)
            if not colors:
                continue
            self.led_colors_by_device[device_id] = colors
            # Prepare a plain RGB staging buffer for this device.
            self._staging[device_id] = bytearray(len(colors) * 3)
            self.positions_by_device[device_id] = positions_list
            for idx in range(len(colors)):
                self.global_map.append((device_id, idx))
            stats = self._compute_device_stats(positions_list)
            self.devices.append(
                {
                    "device_id": device_id,
                    "device_id_str": str(device_id),
                    "info": info,
                    "device_type": dev_type,
                    "leds": len(colors),
                    "model": model,
                    "serial": serial,
                    "center_x": stats.get("center_x"),
                    "center_y": stats.get("center_y"),
                    "min_x": stats.get("min_x"),
                    "max_x": stats.get("max_x"),
                    "min_y": stats.get("min_y"),
                    "max_y": stats.get("max_y"),
                }
            )

        self.total_leds = len(self.global_map)
        if self.total_leds == 0:
            raise RuntimeError("Aucun LED detecte via iCUE.")

        if clear_on_start:
            self.apply_frame(bytearray(self.total_leds * 3))

    def apply_frame(self, frame_bytes, lut=None):
        return self.apply_frame_map(
            self.global_map,
            list(self.led_colors_by_device.keys()),
            frame_bytes,
            lut=lut,
            update_mode="direct",
        )

    def _make_color(self, led_id, r, g, b):
        try:
            return self.sdk.CorsairLedColor(led_id, r, g, b, 255)
        except Exception:
            try:
                c = self.sdk.CorsairLedColor(led_id, r, g, b)
                if hasattr(c, "a"):
                    c.a = 255
                return c
            except Exception:
                return self.sdk.CorsairLedColor(led_id, r, g, b, 255)

    def _compute_device_stats(self, positions_list):
        xs = [p["x"] for p in positions_list if p.get("x") is not None]
        ys = [p["y"] for p in positions_list if p.get("y") is not None]
        if not xs or not ys:
            return {}
        return {
            "min_x": min(xs),
            "max_x": max(xs),
            "min_y": min(ys),
            "max_y": max(ys),
            "center_x": (min(xs) + max(xs)) / 2.0,
            "center_y": (min(ys) + max(ys)) / 2.0,
        }

    def get_device_order(self, device_id):
        order = self.order_by_device.get(device_id)
        colors = self.led_colors_by_device.get(device_id) or []
        if order and len(order) == len(colors):
            return order
        return list(range(len(colors)))

    def _compile_map(self, map_list):
        """Pre-resolve map entries to (staging, dst_offsets, src_offset, wb)."""
        compiled = []
        for entry in map_list:
            device_id, led_idx = entry[0], entry[1]
            src_index = entry[2] if len(entry) > 2 else None
            wb = entry[3] if len(entry) > 3 else None
            staging = self._staging.get(device_id)
            led_count = len(staging) // 3 if staging is not None else 0
            dsts = []
            targets = led_idx if isinstance(led_idx, (list, tuple)) else (led_idx,)
            for li in targets:
                try:
                    led_pos = int(li)
                except (TypeError, ValueError):
                    continue
                if led_pos < 0:
                    led_pos += led_count
                if 0 <= led_pos < led_count:
                    dsts.append(led_pos * 3)
            src_offset = None if src_index is None else int(src_index) * 3
            # Entries without a staging buffer still consume a sequential source slot.
            compiled.append((staging if dsts else None, tuple(dsts), src_offset, wb or None))
        return compiled

    def _get_compiled_map(self, map_list):
        key = id(map_list)
        cached = self._compiled_maps.get(key)
        if cached is not None and cached[0] is map_list:
            return cached[1]
        compiled = self._compile_map(map_list)
        if len(self._compiled_maps) > 64:
            self._compiled_maps.clear()
        self._compiled_maps[key] = (map_list, compiled)
        return compiled

    def _stage_frame(self, map_list, frame_bytes, lut):
        compiled = self._get_compiled_map(map_list)
        n = len(frame_bytes)
        seq = 0
        # Main thread writes only plain RGB bytes, never CorsairLedColor fields.
        with self._staging_lock:
            for staging, dsts, src_offset, wb in compiled:
                if src_offset is None:
                    off = seq
                    seq += 3
                else:
                    off = src_offset
                if staging is None:
                    continue
                if off + 2 < n:
                    r = lut[frame_bytes[off]]
                    g = lut[frame_bytes[off + 1]]
                    b = lut[frame_bytes[off + 2]]
                    if wb:
                        r = int(max(0, min(255, r * wb[0])))
                        g = int(max(0, min(255, g * wb[1])))
                        b = int(max(0, min(255, b * wb[2])))
                else:
                    r = g = b = 0
                for dst in dsts:
                    staging[dst] = r
                    staging[dst + 1] = g
                    staging[dst + 2] = b

    def apply_frame_map(
        self, map_list, device_ids, frame_bytes, lut=None, update_mode="direct_async"
    ):
        if not map_list:
            return False
        if lut is None:
            lut = _IDENTITY_LUT
        apply_start = time.perf_counter()
        self._stage_frame(map_list, frame_bytes, lut)

        update_mode = (update_mode or "direct_async").lower()
        if update_mode == "auto":
            update_mode = "direct_async"
        if update_mode == "direct_async":
            ok, err = self._enqueue_direct_async(device_ids)
            if self.debug_icue and not ok:
                print(f"iCUE direct_async echoue: {err}")
            self._perf_apply_warn(
                update_mode, time.perf_counter() - apply_start, device_ids, map_list, ok, err
            )
            return ok

        any_ok = False
        # Direct/buffer writes use staged snapshots, not shared color objects.
        payload = self._copy_device_colors(device_ids)
        if update_mode == "direct":
            for device_id, colors in payload.items():
                okd, errd = self._try_set_direct(device_id, colors)
                any_ok = any_ok or okd
                if self.debug_icue and not okd:
                    print(f"iCUE set_led_colors echoue pour {device_id}: {errd}")
        else:
            # "buffer", "buffer_safe" and unknown modes use buffered writes + flush.
            used_buffer = False
            for device_id, colors in payload.items():
                okb, errb = self._try_set_buffer(device_id, colors)
                if okb:
                    used_buffer = True
                elif self.debug_icue:
                    print(f"iCUE set_led_colors_buffer echoue pour {device_id}: {errb}")
            if used_buffer:
                flush_err = self._err_from_result(self.sdk.flush())
                if self._is_success(flush_err):
                    any_ok = True
                elif self.debug_icue:
                    print(f"iCUE flush buffer echoue: {flush_err}")
        self._perf_apply_warn(
            update_mode, time.perf_counter() - apply_start, device_ids, map_list, any_ok
        )
        return any_ok

    def _err_from_result(self, result):
        if result is None:
            return None
        if isinstance(result, tuple):
            if len(result) == 2:
                return result[1]
            if len(result) == 1:
                return result[0]
        return result

    def _is_success(self, err):
        if err is None:
            return True
        try:
            return int(err) == self._success_code
        except Exception:
            return False

    def _is_no_control(self, err):
        if err is None:
            return False
        try:
            return int(err) == self._no_control_code
        except Exception:
            return False

    def _request_device_control(self, device_id):
        try:
            res = self.sdk.request_control(device_id)
        except Exception:
            return False, "exception"
        err = self._err_from_result(res)
        return self._is_success(err), err

    def _retry_after_control(self, device_id, colors, setter):
        okc, errc = self._request_device_control(device_id)
        if not okc:
            return False, errc
        try:
            res = setter(device_id, colors)
        except Exception:
            return False, "exception"
        err = self._err_from_result(res)
        return self._is_success(err), err

    def _thread_colors(self, device_id, colors):
        """Reusable CorsairLedColor list owned by the calling thread."""
        cache = getattr(self._color_cache, "by_device", None)
        if cache is None:
            cache = {}
            self._color_cache.by_device = cache
        reusable = cache.get(device_id)
        if reusable is None or len(reusable) != len(colors):
            reusable = []
            for color in colors:
                try:
                    led_id = color.id
                except Exception:
                    continue
                reusable.append(self._make_color(led_id, 0, 0, 0))
            cache[device_id] = reusable
        return reusable

    def _copy_device_colors(self, device_ids):
        copy_total_start = time.perf_counter()
        device_ids_list = list(device_ids or [])
        payload = {}
        total_leds = 0
        for device_id in device_ids_list:
            colors = self.led_colors_by_device.get(device_id)
            if not colors:
                continue
            # Snapshot staged RGB bytes under lock, then fill SDK colors unlocked.
            with self._staging_lock:
                staging = self._staging.get(device_id)
                if staging is None:
                    continue
                snapshot = bytes(staging)
            if not snapshot:
                continue
            out = self._thread_colors(device_id, colors)
            led_count = min(len(out), len(snapshot) // 3)
            total_leds += led_count
            base = 0
            for idx in range(led_count):
                color = out[idx]
                color.r = snapshot[base]
                color.g = snapshot[base + 1]
                color.b = snapshot[base + 2]
                base += 3
            if led_count:
                payload[device_id] = out if led_count == len(out) else out[:led_count]
        copy_total_elapsed = time.perf_counter() - copy_total_start
        if copy_total_elapsed >= 0.005:
            _TIMING_LOG.warning(
                "[WORKER] _copy_device_colors took %.1fms devices=%s leds=%s",
                copy_total_elapsed * 1000.0,
                len(device_ids_list),
                total_leds,
            )
        return payload

    def close(self):
        """Stop the writer thread; used when a reconnect replaces this mapper."""
        with self._direct_async_lock:
            self._closed = True
            self._direct_async_device_ids = None
        self._direct_async_event.set()

    def _ensure_direct_async_worker(self):
        with self._direct_async_lock:
            if self._closed:
                return
            if (
                self._direct_async_thread is not None
                and self._direct_async_thread.is_alive()
            ):
                return
            self._direct_async_thread = threading.Thread(
                target=self._direct_async_loop,
                name="icue-direct-writer",
                daemon=True,
            )
            self._direct_async_thread.start()

    @staticmethod
    def _merge_direct_async_device_ids(current, incoming):
        merged = list(current or [])
        for device_id in incoming or []:
            if device_id not in merged:
                merged.append(device_id)
        return merged

    def _enqueue_direct_async(self, device_ids):
        enqueue_start = time.perf_counter()
        try:
            self._ensure_direct_async_worker()
            now = time.monotonic()
            with self._direct_async_lock:
                if self._closed:
                    return False, "mapper ferme"
                # Report the previous write's error, but still queue this frame.
                err = self._direct_async_last_error
                self._direct_async_last_error = None
                if self._direct_async_inflight_since > 0:
                    elapsed = now - self._direct_async_inflight_since
                    # Coalesce busy async writes without waiting on iCUE.
                    if elapsed > self.perf_threshold:
                        self._perf_warn(
                            "direct_async_busy",
                            "[PERF] iCUE direct_async encore occupe %.3fs; les appareils en attente sont fusionnes",
                            elapsed,
                        )
                    if elapsed > self.direct_async_timeout:
                        return False, f"direct_async bloque depuis {elapsed:.1f}s"
                # Main thread only publishes ids and signals the worker.
                self._direct_async_device_ids = self._merge_direct_async_device_ids(
                    self._direct_async_device_ids,
                    device_ids,
                )
                self._direct_async_event.set()
            return (err is None), err
        finally:
            enqueue_elapsed = time.perf_counter() - enqueue_start
            if enqueue_elapsed >= 0.002:
                _TIMING_LOG.warning(
                    "[BLOCK] _enqueue_direct_async took %.1fms",
                    enqueue_elapsed * 1000.0,
                )

    def direct_async_elapsed(self):
        with self._direct_async_lock:
            if self._direct_async_inflight_since <= 0:
                return 0.0
            return time.monotonic() - self._direct_async_inflight_since

    def direct_async_blocked(self):
        elapsed = self.direct_async_elapsed()
        return elapsed > self.direct_async_timeout, elapsed

    def _direct_async_loop(self):
        while True:
            self._direct_async_event.wait()
            while True:
                with self._direct_async_lock:
                    if self._closed:
                        return
                    device_ids = self._direct_async_device_ids
                    self._direct_async_device_ids = None
                    if device_ids is None:
                        self._direct_async_event.clear()
                        break
                # Time full worker frame copy plus iCUE write.
                frame_start = time.perf_counter()
                # Copy colors on the worker so UDP processing is not blocked.
                copy_start = time.perf_counter()
                payload = self._copy_device_colors(device_ids)
                copy_elapsed = time.perf_counter() - copy_start
                if copy_elapsed > self.perf_threshold:
                    self._perf_warn(
                        "direct_async_copy",
                        "[PERF] copie couleurs iCUE lente %.3fs devices=%s",
                        copy_elapsed,
                        len(device_ids or []),
                    )
                if not payload:
                    with self._direct_async_lock:
                        self._direct_async_last_error = "aucune couleur a envoyer"
                    continue
                with self._direct_async_lock:
                    self._direct_async_inflight_since = time.monotonic()
                    write_start = self._direct_async_inflight_since
                ok_any = False
                failures = []
                led_count = 0
                for device_id, colors in payload.items():
                    led_count += len(colors or [])
                    ok, err = self._try_set_direct(device_id, colors)
                    ok_any = ok_any or ok
                    if not ok:
                        failures.append(f"{device_id}:{err}")
                write_elapsed = time.monotonic() - write_start
                with self._direct_async_lock:
                    self._direct_async_inflight_since = 0.0
                    self._direct_async_last_error = (
                        None if ok_any else "; ".join(failures[:3])
                    )
                if write_elapsed > self.perf_threshold:
                    self._perf_warn(
                        "direct_async_write",
                        "[PERF] ecriture iCUE lente %.3fs devices=%s leds=%s ok=%s failures=%s",
                        write_elapsed,
                        len(payload),
                        led_count,
                        ok_any,
                        len(failures),
                    )
                frame_elapsed = time.perf_counter() - frame_start
                if frame_elapsed >= 0.020:
                    _TIMING_LOG.warning(
                        "[WORKER] frame: copy=%.1fms write=%.1fms total=%.1fms leds=%s",
                        copy_elapsed * 1000.0,
                        write_elapsed * 1000.0,
                        frame_elapsed * 1000.0,
                        led_count,
                    )
                # Soft-throttle successful writes to avoid saturating iCUE.
                if ok_any and write_elapsed < 0.004:
                    time.sleep(max(0.0, 0.004 - write_elapsed))

    def _try_set_buffer(self, device_id, colors):
        try:
            res = self.sdk.set_led_colors_buffer(device_id, colors)
        except Exception:
            return False, "exception"
        err = self._err_from_result(res)
        if self._is_no_control(err):
            return self._retry_after_control(
                device_id, colors, self.sdk.set_led_colors_buffer
            )
        return self._is_success(err), err

    def _try_set_direct(self, device_id, colors):
        # Time worker-side iCUE set_led_colors call.
        set_start = time.perf_counter()
        try:
            res = self.sdk.set_led_colors(device_id, colors)
        except Exception:
            set_elapsed = time.perf_counter() - set_start
            if set_elapsed >= 0.010:
                _TIMING_LOG.warning(
                    "[WORKER] set_led_colors(%s) took %.1fms",
                    device_id,
                    set_elapsed * 1000.0,
                )
            return False, "exception"
        set_elapsed = time.perf_counter() - set_start
        if set_elapsed >= 0.010:
            _TIMING_LOG.warning(
                "[WORKER] set_led_colors(%s) took %.1fms",
                device_id,
                set_elapsed * 1000.0,
            )
        err = self._err_from_result(res)
        if self._is_no_control(err):
            return self._retry_after_control(device_id, colors, self.sdk.set_led_colors)
        return self._is_success(err), err


def looks_like_ddp(data):
    if len(data) < 10:
        return False
    version = (data[0] & 0xC0) >> 6
    if version == 0:
        return False
    header_len = 14 if (data[0] & 0x10) else 10
    if len(data) < header_len:
        return False
    length = int.from_bytes(data[8:10], "big")
    if length == 0:
        return True
    payload_len = len(data) - header_len
    if length <= payload_len:
        return True
    # Certains emetteurs mettent le nombre de pixels au lieu d'octets.
    if length * 3 == payload_len:
        return True
    return False


def parse_ddp(data, frame_buffer):
    header_len = 14 if (data[0] & 0x10) else 10
    offset = int.from_bytes(data[4:8], "big")
    length = int.from_bytes(data[8:10], "big")
    payload = data[header_len:]
    if length and length * 3 == len(payload):
        length = len(payload)
    if length and len(payload) > length:
        payload = payload[:length]
    push = (data[0] & 0x01) != 0
    if offset < len(frame_buffer):
        end = min(len(frame_buffer), offset + len(payload))
        frame_buffer[offset:end] = payload[: end - offset]
    return push


def _clear_tail(frame_buffer, start):
    if start < len(frame_buffer):
        frame_buffer[start:] = b"\x00" * (len(frame_buffer) - start)


def parse_wled_or_raw(data, frame_buffer):
    if not data:
        return
    proto = data[0]
    if proto in (1, 2, 3, 4) and len(data) >= 2:
        if proto == 2 and (len(data) - 1) % 3 == 0:
            payload = data[1:]
            copy_len = min(len(frame_buffer), len(payload))
            frame_buffer[:copy_len] = payload[:copy_len]
            if len(payload) < len(frame_buffer):
                _clear_tail(frame_buffer, copy_len)
            return
        if len(data) < 2:
            return
        if proto == 1:
            payload = data[2:]
            for i in range(0, len(payload), 4):
                if i + 3 >= len(payload):
                    break
                idx = payload[i]
                offset = idx * 3
                if offset + 2 >= len(frame_buffer):
                    continue
                frame_buffer[offset] = payload[i + 1]
                frame_buffer[offset + 1] = payload[i + 2]
                frame_buffer[offset + 2] = payload[i + 3]
            return
        if proto == 2:
            payload = data[2:]
            copy_len = min(len(frame_buffer), len(payload))
            frame_buffer[:copy_len] = payload[:copy_len]
            if len(payload) < len(frame_buffer):
                _clear_tail(frame_buffer, copy_len)
            return
        if proto == 3:
            payload = data[2:]
            out = 0
            for i in range(0, len(payload), 4):
                if i + 2 >= len(payload) or out + 2 >= len(frame_buffer):
                    break
                frame_buffer[out] = payload[i]
                frame_buffer[out + 1] = payload[i + 1]
                frame_buffer[out + 2] = payload[i + 2]
                out += 3
            return
        if proto == 4:
            if len(data) < 4:
                return
            start = (data[2] << 8) | data[3]
            payload = data[4:]
            for i in range(0, len(payload), 3):
                idx = start + (i // 3)
                offset = idx * 3
                # Allow writes ending exactly at the frame buffer boundary.
                if i + 2 >= len(payload) or offset + 3 > len(frame_buffer):
                    break
                frame_buffer[offset] = payload[i]
                frame_buffer[offset + 1] = payload[i + 1]
                frame_buffer[offset + 2] = payload[i + 2]
            return

    if len(data) % 3 == 0:
        copy_len = min(len(frame_buffer), len(data))
        frame_buffer[:copy_len] = data[:copy_len]
        if len(data) < len(frame_buffer):
            _clear_tail(frame_buffer, copy_len)


MAX_PACKETS_PER_READ = 256


def read_udp_packets(sock, limit=MAX_PACKETS_PER_READ):
    """Drain every datagram currently queued on a non-blocking socket."""
    packets = []
    while len(packets) < limit:
        try:
            data, _ = sock.recvfrom(65535)
        except (BlockingIOError, InterruptedError):
            break
        except OSError:
            # Includes WSAECONNRESET and sockets closed during a reconnect.
            break
        packets.append(data)
    return packets


def parse_udp_packet(protocol, data, frame_buffer):
    """Write one datagram into frame_buffer. Returns (frame_ready, is_ddp)."""
    if not data:
        return False, False
    if protocol == "ddp" or (protocol in ("auto", "wled") and looks_like_ddp(data)):
        return parse_ddp(data, frame_buffer), True
    if protocol == "raw":
        if len(data) % 3:
            return False, False
        n = min(len(frame_buffer), len(data))
        frame_buffer[:n] = data[:n]
        return True, False
    parse_wled_or_raw(data, frame_buffer)
    return True, False


def ingest_udp_packets(protocol, packets, frame_buffer):
    """Apply every packet in order (DNRGB/DDP frames span several datagrams).

    Returns (frame_ready, saw_ddp).
    """
    ready = False
    saw_ddp = False
    for data in packets:
        packet_ready, is_ddp = parse_udp_packet(protocol, data, frame_buffer)
        ready = ready or packet_ready
        saw_ddp = saw_ddp or is_ddp
    return ready, saw_ddp


IDENTIFY_SECONDS = 3.0
SWEEP_STEP_SECONDS = 0.06
SWEEP_BAND = 4


class LayoutBackend:
    """Bridge services used by the layout editor; methods are called from the GUI thread."""

    def __init__(self, get_state, requests, cfg_path):
        self._get_state = get_state
        self._requests = requests
        self.cfg_path = cfg_path

    def snapshot(self):
        """(config copy, mapper, sdk) of the running bridge."""
        for _ in range(3):
            try:
                return self._get_state()
            except RuntimeError:
                # cfg was being swapped by a reload; try again.
                time.sleep(0.05)
        return self._get_state()

    def identify(self, targets):
        """Blink the given (device_id, led_index) LEDs for IDENTIFY_SECONDS."""
        self._requests.put(("identify", list(targets)))

    def sweep(self, targets):
        """Run a white band along the given LEDs, in order (layout preview)."""
        self._requests.put(("sweep", list(targets)))

    def save(self, top_changes, group_changes):
        """Write the changes to config.json; the bridge reloads it within a second."""
        data = load_config(self.cfg_path)
        data.update(top_changes)
        groups = data.get("groups") or []
        for idx, values in group_changes.items():
            if 0 <= idx < len(groups) and isinstance(groups[idx], dict):
                groups[idx].update(values)
        write_config(self.cfg_path, data)


def _strip_mode_args(argv):
    out = []
    skip = False
    for arg in argv:
        if skip:
            skip = False
            continue
        if arg == "--mode":
            skip = True
            continue
        if arg.startswith("--mode="):
            continue
        out.append(arg)
    return out


def _log_active_groups(logger, runtime_groups):
    logger.info("Groupes actifs:")
    for g in runtime_groups:
        logger.info(
            "%s -> %s:%s (LEDs: %s, protocole: %s)",
            g["name"],
            g["udp_host"],
            g["udp_port"],
            g["led_count"],
            g["protocol"],
        )


def _device_label(dev):
    return str(dev.get("model") or dev.get("device_id_str") or dev.get("device_id"))


def _select_devices(mapper, grp, sdk, force_types=None):
    """Devices of mapper matching a group's filters (ids, types, model, serial)."""
    grp = grp or {}
    device_ids = [s.lower() for s in _normalize_list(grp.get("device_ids"))]
    include_types = parse_device_types(grp.get("device_types_include"), sdk)
    if force_types:
        include_types = list(force_types)
    exclude_types = parse_device_types(grp.get("device_types_exclude"), sdk)
    model_contains = _normalize_list(grp.get("model_contains") or grp.get("model"))
    serial_contains = _normalize_list(grp.get("serial_contains") or grp.get("serial"))
    selected = []
    for dev in mapper.devices:
        dev_id_str = str(dev.get("device_id_str") or dev.get("device_id")).lower()
        if device_ids and dev_id_str not in device_ids:
            continue
        if include_types and dev.get("device_type") not in include_types:
            continue
        if exclude_types and dev.get("device_type") in exclude_types:
            continue
        if model_contains and not _match_contains(dev.get("model"), model_contains):
            continue
        if serial_contains and not _match_contains(dev.get("serial"), serial_contains):
            continue
        selected.append(dev)
    return selected, include_types


def _device_key(dev):
    return str(dev.get("device_id_str") or dev.get("device_id")).lower()


def _apply_device_order(devices, order):
    """Put devices listed in `order` (device ids) first, in that order; others keep their place after."""
    if not order:
        return list(devices)
    rank = {}
    for i, value in enumerate(_normalize_list(order)):
        rank.setdefault(str(value).strip().lower(), i)
    return sorted(devices, key=lambda d: rank.get(_device_key(d), len(rank)))


def group_devices(grp, mapper, sdk, cfg=None, name=None):
    """Devices of a unique-mode group, in LED stream order. Returns (devices, include_types)."""
    name = name if name is not None else (grp.get("name") or "")
    selected, include_types = _select_devices(mapper, grp, sdk)
    mouse_types = set(parse_device_types(["CDT_Mouse"], sdk))
    mousemat_types = set(parse_device_types(["CDT_Mousemat"], sdk))
    sort_key = (grp.get("device_sort") or "").strip().lower()
    if cfg and cfg.get("ram_match_group_order", False):
        if _normalize_name(name) in ("ram", "memory"):
            sort_key = ""
        else:
            include_types_for_ram = parse_device_types(["CDT_MemoryModule"], sdk)
            if include_types_for_ram and include_types:
                if any(t in include_types for t in include_types_for_ram):
                    sort_key = ""
    if sort_key:
        selected = sorted(selected, key=lambda d: _device_sort_key(d, sort_key))
    else:
        # For mixed mouse+mousemat groups, keep a deterministic order:
        # mousemat first, mouse last. This avoids stream index drift.
        has_mouse = any(dev.get("device_type") in mouse_types for dev in selected)
        has_mousemat = any(dev.get("device_type") in mousemat_types for dev in selected)
        if has_mouse and has_mousemat:
            mats = [dev for dev in selected if dev.get("device_type") in mousemat_types]
            mice = [dev for dev in selected if dev.get("device_type") in mouse_types]
            others = [
                dev
                for dev in selected
                if dev.get("device_type") not in mousemat_types
                and dev.get("device_type") not in mouse_types
            ]
            selected = mats + mice + others
    # An explicit order chosen in the layout editor wins over every heuristic.
    return _apply_device_order(selected, grp.get("device_order")), include_types


def build_groups(cfg_groups, mapper, sdk, default_protocol, default_host, cfg=None):
    groups = []
    used_ids = set()
    if not cfg_groups:
        return groups
    mouse_types = set(parse_device_types(["CDT_Mouse"], sdk))
    mousemat_types = set(parse_device_types(["CDT_Mousemat"], sdk))
    cooler_types = set(parse_device_types(["CDT_Cooler"], sdk))
    pump_wb = parse_white_balance(cfg.get("aio_pump_white_balance")) if cfg else None
    for idx, grp in enumerate(cfg_groups):
        name = grp.get("name") or f"groupe_{idx+1}"
        keepalive_reapply_group = grp.get("keepalive_reapply")
        if keepalive_reapply_group is None and _normalize_name(name) in (
            "souris_tapis",
            "mouse_tapis",
            "mousemat_mouse",
        ):
            keepalive_reapply_group = False
        if "udp_port" not in grp:
            raise RuntimeError(f"Groupe '{name}' sans udp_port.")
        udp_port = int(grp["udp_port"])
        udp_host = grp.get("udp_host", default_host)
        protocol = normalize_protocol(grp.get("protocol"), default_protocol)

        selected, include_types = group_devices(grp, mapper, sdk, cfg, name=name)

        if not selected:
            print(f"Avertissement: groupe '{name}' sans appareil.")
            continue

        for dev in selected:
            dev_id_str = str(dev.get("device_id_str") or dev.get("device_id")).lower()
            if dev_id_str in used_ids:
                raise RuntimeError(
                    f"Appareil duplique entre groupes: {dev_id_str} ({name})"
                )
        for dev in selected:
            dev_id_str = str(dev.get("device_id_str") or dev.get("device_id")).lower()
            used_ids.add(dev_id_str)

        map_list = []
        device_ranges = {}
        device_ids_raw = []
        device_labels = []
        mouse_ids = set()
        mousemat_ids = []
        link_mouse_center = bool(grp.get("link_mouse_to_mousemat_center"))

        ram_layout = str(
            grp.get("ram_group_layout")
            or (cfg.get("ram_group_layout") if cfg else None)
            or ""
        ).lower()
        is_ram_group = False
        if _normalize_name(name) in ("ram", "memory"):
            is_ram_group = True
        elif include_types:
            ram_types = set(parse_device_types(["CDT_MemoryModule"], sdk))
            if ram_types and all(t in ram_types for t in include_types):
                is_ram_group = True

        if is_ram_group and ram_layout == "rows":
            for dev in selected:
                device_id = dev["device_id"]
                device_ids_raw.append(device_id)
                label = dev.get("model") or dev.get("device_id_str") or str(device_id)
                device_labels.append(str(label))
            map_list = _build_ram_interleaved_map(selected, mapper)
            groups.append(
                {
                    "name": name,
                    "udp_host": udp_host,
                    "udp_port": udp_port,
                    "protocol": protocol,
                    "device_ids": device_ids_raw,
                    "map": map_list,
                    "led_count": len(map_list),
                    "device_labels": device_labels,
                    "update_mode": (
                        grp.get("update_mode")
                        or (cfg.get("icue_update_mode") if cfg else None)
                        or "direct_async"
                    ).lower(),
                    "keepalive_reapply": keepalive_reapply_group,
                    "idle_clear_disabled": bool(grp.get("idle_clear_disabled", False)),
                    "idle_clear_seconds": grp.get("idle_clear_seconds"),
                }
            )
            continue

        for dev in selected:
            device_id = dev["device_id"]
            device_ids_raw.append(device_id)
            colors = mapper.led_colors_by_device.get(device_id)
            if colors:
                order = None
                pump_split = False
                if cfg and dev.get("device_type") in cooler_types:
                    pump_split = bool(cfg.get("aio_pump_split")) or bool(
                        grp.get("pump_split")
                    )
                if pump_split:
                    start_side = cfg.get("aio_pump_angle_start") if cfg else "left"
                    orders = None
                    if cfg:
                        orders = _build_aio_cluster_orders(
                            mapper.positions_by_device.get(device_id),
                            cluster_count=cfg.get("aio_cluster_count", 3),
                            group_sort=cfg.get("aio_cluster_sort", "x"),
                            group_order=cfg.get("aio_cluster_order"),
                            start=cfg.get("aio_angle_start", "top"),
                            direction=cfg.get("aio_angle_direction", "clockwise"),
                            flip_x=cfg.get("aio_flip_x", False),
                            flip_y=cfg.get("aio_flip_y", False),
                            swap_xy=cfg.get("aio_swap_xy", False),
                            pump_first=True,
                        )
                    allowed_indices = orders[0] if orders else None
                    pairs = _build_pump_lr_pairs(
                        mapper.positions_by_device.get(device_id),
                        start=start_side or "left",
                        flip_x=cfg.get("aio_flip_x", False) if cfg else False,
                        flip_y=cfg.get("aio_flip_y", False) if cfg else False,
                        swap_xy=cfg.get("aio_swap_xy", False) if cfg else False,
                        allowed_indices=allowed_indices,
                    )
                    if pairs:
                        start_idx = len(map_list)
                        order = []
                        full_order = mapper.get_device_order(device_id)
                        allowed_set = set(allowed_indices) if allowed_indices else None
                        for pair in pairs:
                            if not pair:
                                continue
                            base_idx = len(map_list)
                            if pump_wb:
                                map_list.append((device_id, pair[0], None, pump_wb))
                            else:
                                map_list.append((device_id, pair[0]))
                            order.append(pair[0])
                            if len(pair) > 1:
                                if pump_wb:
                                    map_list.append(
                                        (device_id, pair[1], base_idx, pump_wb)
                                    )
                                else:
                                    map_list.append((device_id, pair[1], base_idx))
                                order.append(pair[1])
                        # Append remaining LEDs (ex: ventilos AIO) after the pump
                        for idx_led in full_order:
                            if allowed_set is not None and idx_led in allowed_set:
                                continue
                            map_list.append((device_id, idx_led))
                            order.append(idx_led)
                if order is None:
                    order = mapper.get_device_order(device_id)
                    start_idx = len(map_list)
                    for i in order:
                        map_list.append((device_id, i))
                if order:
                    # Store the real number of map entries added for this device.
                    device_ranges[device_id] = (start_idx, len(map_list) - start_idx)
            if dev.get("device_type") in mouse_types:
                mouse_ids.add(device_id)
            if dev.get("device_type") in mousemat_types:
                mousemat_ids.append(device_id)
            label = dev.get("model") or dev.get("device_id_str") or str(device_id)
            device_labels.append(str(label))

        if link_mouse_center and mousemat_ids and mouse_ids:
            mat_id = mousemat_ids[0]
            mat_range = device_ranges.get(mat_id)
            if mat_range:
                start_idx, length = mat_range
                if length > 0:
                    src_index = start_idx + (length // 2)
                    new_map = []
                    for entry in map_list:
                        if entry[0] in mouse_ids:
                            # Keep any white-balance field (index 3) intact.
                            new_map.append((entry[0], entry[1], src_index) + tuple(entry[3:]))
                        else:
                            new_map.append(entry)
                    map_list = new_map

        groups.append(
            {
                "name": name,
                "udp_host": udp_host,
                "udp_port": udp_port,
                "protocol": protocol,
                "device_ids": device_ids_raw,
                "map": map_list,
                "led_count": len(map_list),
                "device_labels": device_labels,
                "update_mode": (
                    grp.get("update_mode")
                    or (cfg.get("icue_update_mode") if cfg else None)
                    or "direct_async"
                ).lower(),
                "keepalive_reapply": keepalive_reapply_group,
                "idle_clear_disabled": bool(grp.get("idle_clear_disabled", False)),
                "idle_clear_seconds": grp.get("idle_clear_seconds"),
            }
        )
    return groups


def build_group_all(mapper, default_protocol, udp_host, group_port, cfg=None, sdk=None):
    device_labels = []
    for dev in mapper.devices:
        label = dev.get("model") or dev.get("device_id_str")
        if label:
            device_labels.append(str(label))
    ram_types = None
    ram_layout = None
    if cfg and sdk:
        ram_layout = (cfg.get("ram_group_layout") or "").lower()
        if ram_layout == "rows":
            ram_types = set(parse_device_types(["CDT_MemoryModule"], sdk))
    return [
        {
            "name": "groupe",
            "udp_host": udp_host,
            "udp_port": int(group_port),
            "protocol": default_protocol,
            "device_ids": list(mapper.led_colors_by_device.keys()),
            "map": _build_full_map_with_ram(mapper, ram_types=ram_types, ram_layout=ram_layout),
            "led_count": mapper.total_leds,
            "device_labels": device_labels,
            "update_mode": (
                cfg.get("icue_update_mode", "direct_async")
                if cfg
                else "direct_async"
            ).lower(),
        }
    ]


FUSION_SECTIONS = ("clavier", "tapis", "souris", "ventilos", "ram", "aio_ventilos")


def normalize_fusion_order(value):
    """Valid fusion section list: known names in the given order, missing ones appended."""
    order = []
    for item in _normalize_list(value):
        name = str(item).strip().lower()
        if name in FUSION_SECTIONS and name not in order:
            order.append(name)
    order.extend(name for name in FUSION_SECTIONS if name not in order)
    return order


def build_group_fusion(cfg, mapper, sdk, default_protocol, udp_host, fusion_port):
    groups_cfg = cfg.get("groups") or []
    groups_by_name = {}
    for grp in groups_cfg:
        name = (grp.get("name") or "").strip().lower()
        if name:
            groups_by_name[name] = grp

    def pick_group(*names):
        for name in names:
            grp = groups_by_name.get(name)
            if grp is not None:
                return grp
        return None

    def select_devices(grp, force_types=None):
        selected, _ = _select_devices(mapper, grp, sdk, force_types=force_types)
        sort_key = (grp.get("device_sort") or "").strip().lower() if grp else ""
        if sort_key:
            selected = sorted(selected, key=lambda d: _device_sort_key(d, sort_key))
        return _apply_device_order(selected, grp.get("device_order") if grp else None)

    def ram_axis_order(dev, prefer_axis="auto"):
        device_id = dev["device_id"]
        pts = _transform_points(mapper.positions_by_device.get(device_id))
        if not pts:
            return mapper.get_device_order(device_id)
        xs = [p[1] for p in pts]
        ys = [p[2] for p in pts]
        prefer_axis = (prefer_axis or "auto").lower()
        rx = max(xs) - min(xs)
        ry = max(ys) - min(ys)
        axis = prefer_axis
        if axis == "auto":
            axis = "x" if rx >= ry else "y"
        if axis == "x":
            pts.sort(key=lambda p: (p[1], p[2]))
        else:
            pts.sort(key=lambda p: (p[2], p[1]))
        return [p[0] for p in pts]

    keyboard_types = parse_device_types(["CDT_Keyboard"], sdk)
    mousemat_types = parse_device_types(["CDT_Mousemat"], sdk)
    mouse_types = parse_device_types(["CDT_Mouse"], sdk)
    ram_types = parse_device_types(["CDT_MemoryModule"], sdk)
    cooler_types = parse_device_types(["CDT_Cooler"], sdk)
    fan_types = parse_device_types(cfg.get("fan_device_types"), sdk)
    if not fan_types:
        fan_types = parse_device_types(["CDT_LedController", "CDT_Fan"], sdk)

    grp_keyboard = pick_group("clavier", "keyboard")
    grp_mousemat = pick_group("tapis", "mousemat")
    grp_mouse = pick_group("souris", "mouse")
    grp_mousemat_mouse = pick_group("souris_tapis", "mouse_tapis")
    grp_ventilos = pick_group("ventilos", "fans")
    grp_aio = pick_group("aio", "cooler")
    grp_ram = pick_group("ram", "memory")

    map_list = []
    device_ids_raw = []
    device_ids_set = set()
    device_labels = []
    label_set = set()
    used_leds = {}

    def ensure_device(device_id, label):
        if device_id not in device_ids_set:
            device_ids_set.add(device_id)
            device_ids_raw.append(device_id)
        if label and label not in label_set:
            label_set.add(label)
            device_labels.append(label)

    def add_device(device_id, label, indices, src_index=None, dedupe=False):
        ensure_device(device_id, label)
        used = used_leds.setdefault(device_id, set())
        for i in indices:
            # With dedupe, skip LEDs already recorded for this device.
            if dedupe and i in used:
                continue
            used.add(i)
            if src_index is None:
                map_list.append((device_id, i))
            else:
                map_list.append((device_id, i, src_index))

    def add_devices(devices):
        for dev in devices:
            device_id = dev["device_id"]
            order = mapper.get_device_order(device_id)
            label = _device_label(dev)
            add_device(device_id, label, order)

    link_mouse = False
    if grp_mousemat_mouse:
        link_mouse = bool(grp_mousemat_mouse.get("link_mouse_to_mousemat_center"))
    mousemat_devices = select_devices(grp_mousemat_mouse or grp_mousemat, force_types=mousemat_types)
    mouse_devices = select_devices(grp_mousemat_mouse or grp_mouse, force_types=mouse_types)
    mousemat_span = {"start": None, "len": 0}
    mouse_slots = []

    # CPU cooler: pump cluster first, radiator fan clusters after.
    aio_devices = select_devices(grp_aio, force_types=cooler_types)
    aio_pump_orders = []
    aio_fan_orders = []
    aio_start = cfg.get("aio_angle_start", "top")
    aio_dir = cfg.get("aio_angle_direction", "clockwise")
    pump_start = cfg.get("aio_pump_angle_start") or aio_start
    pump_dir = cfg.get("aio_pump_angle_direction") or aio_dir
    for dev in aio_devices:
        device_id = dev["device_id"]
        positions = mapper.positions_by_device.get(device_id)
        orders_pump = _build_aio_cluster_orders(
            positions,
            cluster_count=cfg.get("aio_cluster_count", 3),
            group_sort=cfg.get("aio_cluster_sort", "x"),
            group_order=cfg.get("aio_cluster_order"),
            start=pump_start,
            direction=pump_dir,
            flip_x=cfg.get("aio_flip_x", False),
            flip_y=cfg.get("aio_flip_y", False),
            swap_xy=cfg.get("aio_swap_xy", False),
            pump_first=True,
        )
        orders_fans = _build_aio_cluster_orders(
            positions,
            cluster_count=cfg.get("aio_cluster_count", 3),
            group_sort=cfg.get("aio_cluster_sort", "x"),
            group_order=cfg.get("aio_cluster_order"),
            start=aio_start,
            direction=aio_dir,
            flip_x=cfg.get("aio_flip_x", False),
            flip_y=cfg.get("aio_flip_y", False),
            swap_xy=cfg.get("aio_swap_xy", False),
            pump_first=True,
        )
        orders = orders_pump or orders_fans
        if not orders:
            full_order = mapper.get_device_order(device_id)
            aio_pump_orders.append((dev, full_order, positions))
            continue
        aio_pump_orders.append((dev, (orders_pump or orders)[0], positions))
        fan_orders = orders_fans or orders
        if len(fan_orders) > 1:
            rest = []
            for chunk in fan_orders[1:]:
                rest.extend(chunk)
            if rest:
                aio_fan_orders.append((dev, rest))

    pump_leds = {}
    for dev, order, _positions in aio_pump_orders:
        pump_leds.setdefault(dev["device_id"], set()).update(order)

    def add_aio_pump():
        pump_split = bool(cfg.get("aio_pump_split"))
        pump_wb = parse_white_balance(cfg.get("aio_pump_white_balance"))
        for dev, order, positions in aio_pump_orders:
            device_id = dev["device_id"]
            label = _device_label(dev)
            if pump_split:
                start_side = cfg.get("aio_pump_angle_start") or "left"
                pairs = _build_pump_lr_pairs(
                    positions,
                    start=start_side,
                    flip_x=cfg.get("aio_flip_x", False),
                    flip_y=cfg.get("aio_flip_y", False),
                    swap_xy=cfg.get("aio_swap_xy", False),
                    allowed_indices=(order if isinstance(order, (list, tuple)) else None),
                )
                if pairs:
                    ensure_device(device_id, label)
                    used = used_leds.setdefault(device_id, set())
                    for pair in pairs:
                        if not pair:
                            continue
                        base_idx = len(map_list)
                        if pump_wb:
                            map_list.append((device_id, pair[0], None, pump_wb))
                        else:
                            map_list.append((device_id, pair[0]))
                        # Record pump LEDs so later AIO fan chunks skip them.
                        used.add(pair[0])
                        if len(pair) > 1:
                            if pump_wb:
                                map_list.append(
                                    (device_id, pair[1], base_idx, pump_wb)
                                )
                            else:
                                map_list.append((device_id, pair[1], base_idx))
                            used.add(pair[1])
                    continue
            add_device(device_id, label, order)

    case_fan_devices = select_devices(grp_ventilos, force_types=fan_types)
    case_segments = []
    leds_per_fan = int(cfg.get("fan_outer_leds", 12)) + int(cfg.get("fan_inner_leds", 4))
    if leds_per_fan < 1:
        leds_per_fan = 0
    for dev in case_fan_devices:
        device_id = dev["device_id"]
        order = mapper.get_device_order(device_id)
        if (
            not cfg.get("fan_surface")
            and leds_per_fan
            and order
            and len(order) >= leds_per_fan
            and len(order) % leds_per_fan == 0
        ):
            for i in range(0, len(order), leds_per_fan):
                case_segments.append((dev, order[i : i + leds_per_fan]))
        else:
            case_segments.append((dev, order))

    insert_after = cfg.get("fusion_cpu_after_fan", 1)
    try:
        insert_after = int(insert_after)
    except Exception:
        insert_after = 1
    if insert_after < 0:
        insert_after = 0

    def emit_keyboard():
        add_devices(select_devices(grp_keyboard, force_types=keyboard_types))

    def emit_mousemat():
        mousemat_span["start"] = len(map_list)
        for dev in mousemat_devices:
            order = mapper.get_device_order(dev["device_id"])
            add_device(dev["device_id"], _device_label(dev), order)
            mousemat_span["len"] += len(order)

    def emit_mouse():
        for dev in mouse_devices:
            start_idx = len(map_list)
            add_device(dev["device_id"], _device_label(dev), mapper.get_device_order(dev["device_id"]))
            if link_mouse:
                mouse_slots.append((start_idx, len(map_list)))

    def emit_case_fans():
        # The pump cluster is inserted after `fusion_cpu_after_fan` case fans.
        inserted = False
        for count, (dev, segment) in enumerate(case_segments):
            if count == insert_after and not inserted:
                add_aio_pump()
                inserted = True
            add_device(dev["device_id"], _device_label(dev), segment)
        if not inserted:
            add_aio_pump()

    def emit_ram():
        ram_devices = select_devices(grp_ram, force_types=ram_types)
        if ram_devices:
            if cfg.get("ram_match_group_order", False):
                ram_layout = (cfg.get("ram_group_layout") or "").lower()
                if ram_layout == "rows":
                    for dev in ram_devices:
                        device_id = dev["device_id"]
                        label = _device_label(dev)
                        ensure_device(device_id, label)
                    for device_id, led_idx in _build_ram_interleaved_map(ram_devices, mapper):
                        map_list.append((device_id, led_idx))
                else:
                    for dev in ram_devices:
                        device_id = dev["device_id"]
                        order = mapper.get_device_order(device_id)
                        label = _device_label(dev)
                        add_device(device_id, label, order)
            else:
                ram_devices = sorted(
                    ram_devices,
                    key=lambda d: (
                        d.get("center_x") is None,
                        d.get("center_x", 0.0),
                        d.get("center_y", 0.0),
                    ),
                )
                # An explicit order from the layout editor wins over the position sort.
                ram_devices = _apply_device_order(
                    ram_devices, grp_ram.get("device_order") if grp_ram else None
                )
                ram_mode = (cfg.get("fusion_ram_mode") or "sticks").lower()
                mirror = bool(cfg.get("fusion_ram_mirror", False))
                ram_axis = (cfg.get("fusion_ram_led_axis") or "auto").lower()
                if ram_mode == "rows":
                    stick_orders = []
                    for idx_dev, dev in enumerate(ram_devices):
                        order = ram_axis_order(dev, prefer_axis=ram_axis)
                        if mirror and (idx_dev % 2 == 1):
                            order = list(reversed(order))
                        stick_orders.append((dev, order))
                    max_len = max((len(order) for _dev, order in stick_orders), default=0)
                    for i in range(max_len):
                        for dev, order in stick_orders:
                            if i >= len(order):
                                continue
                            device_id = dev["device_id"]
                            label = _device_label(dev)
                            ensure_device(device_id, label)
                            map_list.append((device_id, order[i]))
                else:
                    for idx_dev, dev in enumerate(ram_devices):
                        device_id = dev["device_id"]
                        order = ram_axis_order(dev, prefer_axis=ram_axis)
                        label = _device_label(dev)
                        add_device(device_id, label, order)

    def emit_aio_fans():
        for dev, order in aio_fan_orders:
            device_id = dev["device_id"]
            skip = pump_leds.get(device_id, set())
            add_device(
                device_id,
                _device_label(dev),
                [i for i in order if i not in skip],
                dedupe=True,
            )

    sections = {
        "clavier": emit_keyboard,
        "tapis": emit_mousemat,
        "souris": emit_mouse,
        "ventilos": emit_case_fans,
        "ram": emit_ram,
        "aio_ventilos": emit_aio_fans,
    }
    for section in normalize_fusion_order(cfg.get("fusion_order")):
        sections[section]()

    # The mouse mirrors the mousemat centre, wherever both ended up in the strip.
    if mouse_slots and mousemat_span["start"] is not None and mousemat_span["len"] > 0:
        src_index = mousemat_span["start"] + (mousemat_span["len"] // 2)
        for start_idx, end_idx in mouse_slots:
            for i in range(start_idx, end_idx):
                entry = map_list[i]
                map_list[i] = (entry[0], entry[1], src_index)

    if not map_list:
        raise RuntimeError("Mode fusion: aucun LED detecte.")

    return [
        {
            "name": "fusion",
            "udp_host": udp_host,
            "udp_port": int(fusion_port),
            "protocol": default_protocol,
            "device_ids": device_ids_raw,
            "map": map_list,
            "led_count": len(map_list),
            "device_labels": device_labels,
            "update_mode": (cfg.get("icue_update_mode", "direct_async") or "direct_async").lower(),
        }
    ]


def _build_full_map(mapper):
    map_list = []
    for device_id in mapper.led_colors_by_device.keys():
        order = mapper.get_device_order(device_id)
        for i in order:
            map_list.append((device_id, i))
    return map_list


def _build_ram_interleaved_map(devices, mapper):
    if not devices:
        return []
    stick_orders = []
    for dev in devices:
        device_id = dev["device_id"]
        order = mapper.get_device_order(device_id)
        stick_orders.append((dev, order))
    max_len = max((len(order) for _dev, order in stick_orders), default=0)
    map_list = []
    for i in range(max_len):
        for dev, order in stick_orders:
            if i >= len(order):
                continue
            map_list.append((dev["device_id"], order[i]))
    return map_list


def _build_full_map_with_ram(mapper, ram_types=None, ram_layout=None):
    if not ram_types or ram_layout != "rows":
        return _build_full_map(mapper)
    ram_devices = [dev for dev in mapper.devices if dev.get("device_type") in ram_types]
    if not ram_devices:
        return _build_full_map(mapper)
    ram_map = _build_ram_interleaved_map(ram_devices, mapper)
    ram_ids = {dev["device_id"] for dev in ram_devices}
    map_list = []
    inserted = False
    for dev in mapper.devices:
        device_id = dev["device_id"]
        if device_id in ram_ids:
            if not inserted:
                map_list.extend(ram_map)
                inserted = True
            continue
        order = mapper.get_device_order(device_id)
        for i in order:
            map_list.append((device_id, i))
    if not inserted:
        map_list.extend(ram_map)
    return map_list


def get_groups_for_mode(mode, cfg, mapper, sdk, default_protocol, args):
    if mode == "group":
        group_port = args.group_port or cfg.get("group_port", 34983)
        return build_group_all(
            mapper, default_protocol, cfg.get("udp_host", DEFAULT_UDP_HOST), group_port, cfg=cfg, sdk=sdk
        )
    if mode == "fusion":
        fusion_port = args.fusion_port or cfg.get("fusion_port", 34984)
        return build_group_fusion(
            cfg,
            mapper,
            sdk,
            default_protocol,
            cfg.get("udp_host", DEFAULT_UDP_HOST),
            fusion_port,
        )
    groups_cfg = cfg.get("groups") or []
    groups = build_groups(
        groups_cfg,
        mapper,
        sdk,
        default_protocol,
        cfg.get("udp_host", DEFAULT_UDP_HOST),
        cfg=cfg,
    )
    if not groups:
        raise RuntimeError("Mode unique demande des groupes dans config.json.")
    return groups


def setup_runtime(groups):
    sel = selectors.DefaultSelector()
    bound = set()
    runtime_groups = []
    opened_groups = []
    try:
        for g in groups:
            if g.get("led_count", 0) <= 0:
                print(f"Avertissement: groupe '{g['name']}' sans LEDs, ignore.")
                continue
            host_port = (g["udp_host"], int(g["udp_port"]))
            if host_port in bound:
                raise RuntimeError(f"Port duplique: {host_port[0]}:{host_port[1]}")
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(host_port)
            sock.setblocking(False)
            g["sock"] = sock
            opened_groups.append(g)
            g["frame_buffer"] = bytearray(g["led_count"] * 3)
            now = time.monotonic()
            g["last_send"] = now
            g["first_packet"] = True
            g["pkt_count"] = 0
            g["byte_count"] = 0
            g["stats_ts"] = now
            g["last_packet_ts"] = 0.0
            g["fail_count"] = 0
            g["perf_last_udp_gap_warn"] = 0.0
            g["perf_last_apply_warn"] = 0.0
            g["perf_max_udp_gap"] = 0.0
            g["perf_max_apply_elapsed"] = 0.0
            g["idle_cleared"] = False
            g["pending_apply"] = False
            g["idle_clear_disabled"] = bool(g.get("idle_clear_disabled", False))
            idle_clear_seconds = g.get("idle_clear_seconds")
            try:
                g["idle_clear_seconds"] = (
                    max(0.2, float(idle_clear_seconds))
                    if idle_clear_seconds is not None
                    else None
                )
            except Exception:
                g["idle_clear_seconds"] = None
            g["keepalive_interval"] = g.get("keepalive_interval")
            g["last_keepalive"] = now
            sel.register(sock, selectors.EVENT_READ, data=g)
            bound.add(host_port)
            runtime_groups.append(g)
    except Exception:
        for g in opened_groups:
            sock = g.get("sock")
            if not sock:
                continue
            try:
                sel.unregister(sock)
            except Exception:
                pass
            try:
                sock.close()
            except Exception:
                pass
            g["sock"] = None
        raise
    return sel, runtime_groups


def close_runtime(sel, runtime_groups):
    for g in runtime_groups:
        sock = g.get("sock")
        if sock:
            try:
                sel.unregister(sock)
            except Exception:
                pass
            try:
                sock.close()
            except Exception:
                pass
            g["sock"] = None


def wait_for_icue(sdk, device_type_mask, timeout_s=8.0):
    start = time.monotonic()
    last_err = None
    while time.monotonic() - start < timeout_s:
        try:
            if sdk.CorsairSessionState is not None:
                state, err = sdk.get_session_state()
                last_err = err
                if err == sdk.CorsairError.CE_Success and hasattr(
                    sdk.CorsairSessionState, "CSS_Connected"
                ):
                    if state == sdk.CorsairSessionState.CSS_Connected:
                        return True, last_err
        except Exception:
            pass

        try:
            _, err = sdk.get_devices(device_type_mask)
            last_err = err
            if err == sdk.CorsairError.CE_Success:
                return True, last_err
        except Exception:
            pass

        time.sleep(0.2)
    return False, last_err


def is_icue_connected(sdk, device_type_mask):
    # Time watchdog SDK connectivity checks.
    timing_logger = _TIMING_LOG
    check_start = time.perf_counter()

    def finish(result):
        elapsed = time.perf_counter() - check_start
        if elapsed >= 0.100:
            timing_logger.warning(
                "[BLOCK] is_icue_connected took %.1fms result=%s",
                elapsed * 1000.0,
                result,
            )
        else:
            timing_logger.debug(
                "[BLOCK] is_icue_connected took %.1fms result=%s",
                elapsed * 1000.0,
                result,
            )
        return result

    try:
        if sdk.CorsairSessionState is not None:
            state, err = sdk.get_session_state()
            if err == sdk.CorsairError.CE_Success and hasattr(
                sdk.CorsairSessionState, "CSS_Connected"
            ):
                return finish(state == sdk.CorsairSessionState.CSS_Connected)
    except Exception:
        pass
    try:
        _, err = sdk.get_devices(device_type_mask)
        return finish(err == sdk.CorsairError.CE_Success)
    except Exception:
        return finish(False)


def request_control_for_devices(sdk, mapper=None, device_ids=None, logger=None, context="request_control"):
    # Time request_control batch and each per-device SDK call.
    timing_logger = _TIMING_LOG
    request_total_start = time.perf_counter()
    targets = []
    seen = set()
    raw_ids = device_ids
    if raw_ids is None and mapper is not None:
        raw_ids = [dev.get("device_id") for dev in mapper.devices]
    for device_id in raw_ids or []:
        if not device_id or device_id in seen:
            continue
        seen.add(device_id)
        targets.append(device_id)

    failures = []
    ok_any = False
    if not targets:
        request_total_elapsed = time.perf_counter() - request_total_start
        if request_total_elapsed >= 0.002:
            timing_logger.warning(
                "[BLOCK] request_control_for_devices took %.1fms devices=%s ok=%s",
                request_total_elapsed * 1000.0,
                len(targets),
                True,
            )
        return True

    for device_id in targets:
        request_start = time.perf_counter()
        try:
            err = sdk.request_control(device_id)
        except Exception as exc:
            request_elapsed = time.perf_counter() - request_start
            if request_elapsed >= 0.005:
                timing_logger.warning(
                    "[BLOCK] request_control(%s) took %.1fms",
                    device_id,
                    request_elapsed * 1000.0,
                )
            failures.append(f"{device_id}:{exc}")
            continue
        request_elapsed = time.perf_counter() - request_start
        if request_elapsed >= 0.005:
            timing_logger.warning(
                "[BLOCK] request_control(%s) took %.1fms",
                device_id,
                request_elapsed * 1000.0,
            )
        if sdk.is_success(err):
            ok_any = True
        else:
            failures.append(f"{device_id}:{err}")

    if failures and logger is not None:
        sample = "; ".join(failures[:3])
        if len(failures) > 3:
            sample += f"; +{len(failures) - 3} autres"
        logger.warning("iCUE %s echoue sur %s appareil(s): %s", context, len(failures), sample)
    request_total_elapsed = time.perf_counter() - request_total_start
    if request_total_elapsed >= 0.002:
        timing_logger.warning(
            "[BLOCK] request_control_for_devices took %.1fms devices=%s ok=%s",
            request_total_elapsed * 1000.0,
            len(targets),
            ok_any,
        )
    return ok_any


def apply_fan_layout(mapper, cfg, sdk):
    """Set the LED order of fan devices: single surface, per-fan rings, or iCUE order."""
    fan_types = parse_device_types(cfg.get("fan_device_types"), sdk)
    if cfg.get("fan_surface"):
        mapper.apply_fan_surface(
            fan_types,
            fan_count=cfg.get("fan_count"),
            outer_leds=cfg.get("fan_outer_leds", 12),
            inner_leds=cfg.get("fan_inner_leds", 4),
            group_order=cfg.get("fan_group_order"),
            first=cfg.get("fan_surface_first", "top"),
            led_start=cfg.get("fan_led_start", "top"),
            rotation=cfg.get("fan_led_rotation", "clockwise"),
            inner_first=bool(cfg.get("fan_led_inner_first", False)),
        )
    elif cfg.get("fan_ring"):
        mapper.apply_fan_ring(
            fan_types,
            outer_leds=cfg.get("fan_outer_leds", 12),
            inner_leds=cfg.get("fan_inner_leds", 4),
            fan_count=cfg.get("fan_count"),
            start=cfg.get("fan_start", "top"),
            direction=cfg.get("fan_direction", "clockwise"),
            group_sort=cfg.get("fan_group_sort", "x"),
            layout=cfg.get("fan_layout", "sequential"),
            group_order=cfg.get("fan_group_order"),
            ring_order=cfg.get("fan_ring_order", "index"),
            lock_to_first=cfg.get("fan_lock_to_first", False),
            inner_first=cfg.get("fan_inner_first", False),
            flip_x=cfg.get("fan_flip_x", False),
            flip_y=cfg.get("fan_flip_y", True),
            swap_xy=cfg.get("fan_swap_xy", False),
        )


def build_mapper(cfg, sdk, device_type_mask, args, clear_on_start=None):
    mapper = LedMapper(sdk, device_type_mask)
    try:
        mapper.direct_async_timeout = max(
            1.0, float(cfg.get("icue_direct_async_timeout", 10.0))
        )
    except Exception:
        mapper.direct_async_timeout = 10.0
    include_types = parse_device_types(cfg.get("device_types_include"), sdk)
    exclude_types = parse_device_types(cfg.get("device_types_exclude"), sdk)
    mapper.set_type_filters(include_types, exclude_types)
    mapper.set_debug(getattr(args, "debug_icue", False))
    perf_debug, perf_threshold, perf_log_cooldown = get_perf_options(cfg, args)
    mapper.set_perf_debug(
        perf_debug,
        logger=logging.getLogger("bridge"),
        threshold=perf_threshold,
        cooldown=perf_log_cooldown,
    )
    if clear_on_start is None:
        clear_on_start = cfg.get("clear_on_start", True)
    mapper.enumerate(clear_on_start)

    if cfg.get("keyboard_serpentine"):
        keyboard_types = parse_device_types(["CDT_Keyboard"], sdk)
        mapper.apply_serpentine(
            keyboard_types,
            row_tolerance=cfg.get("keyboard_serpentine_row_tolerance"),
            first_dir=cfg.get("keyboard_serpentine_first_dir", "left"),
            row_order=cfg.get("keyboard_serpentine_row_order", "top"),
            rows_count=cfg.get("keyboard_serpentine_rows"),
            flip_x=cfg.get("keyboard_serpentine_flip_x", False),
            flip_y=cfg.get("keyboard_serpentine_flip_y", False),
            swap_xy=cfg.get("keyboard_serpentine_swap_xy", False),
            mode=cfg.get("keyboard_serpentine_mode", "serpentine"),
        )
    ram_types = parse_device_types(["CDT_MemoryModule"], sdk)
    if cfg.get("ram_serpentine"):
        mapper.apply_serpentine(
            ram_types,
            row_tolerance=cfg.get("ram_serpentine_row_tolerance"),
            first_dir=cfg.get("ram_serpentine_first_dir", "left"),
            row_order=cfg.get("ram_serpentine_row_order", "bottom"),
            rows_count=cfg.get("ram_serpentine_rows"),
            flip_x=cfg.get("ram_serpentine_flip_x", False),
            flip_y=cfg.get("ram_serpentine_flip_y", False),
            swap_xy=cfg.get("ram_serpentine_swap_xy", False),
            mode=cfg.get("ram_serpentine_mode", "linear"),
        )
    ram_axis = (cfg.get("ram_order_axis") or "").lower()
    if ram_axis in ("auto", "x", "y"):
        mapper.apply_axis_order(ram_types, axis=ram_axis)
    apply_fan_layout(mapper, cfg, sdk)
    if cfg.get("aio_cluster"):
        aio_types = parse_device_types(["CDT_Cooler"], sdk)
        mapper.apply_aio_cluster(
            aio_types,
            cluster_count=cfg.get("aio_cluster_count", 3),
            group_sort=cfg.get("aio_cluster_sort", "x"),
            group_order=cfg.get("aio_cluster_order"),
            start=cfg.get("aio_angle_start", "top"),
            direction=cfg.get("aio_angle_direction", "clockwise"),
            flip_x=cfg.get("aio_flip_x", False),
            flip_y=cfg.get("aio_flip_y", False),
            swap_xy=cfg.get("aio_swap_xy", False),
            pump_first=cfg.get("aio_pump_first", False),
        )
    mat_types = parse_device_types(["CDT_Mousemat"], sdk)
    mousemat_mode = (cfg.get("mousemat_order_mode") or "serpentine").lower()
    if mousemat_mode == "index":
        mapper.apply_index_order(
            mat_types, reverse=cfg.get("mousemat_reverse", False)
        )
    elif mousemat_mode == "angle":
        mapper.apply_angle_order(
            mat_types,
            start=cfg.get("mousemat_angle_start", "left"),
            direction=cfg.get("mousemat_angle_direction", "clockwise"),
            flip_x=cfg.get("mousemat_serpentine_flip_x", False),
            flip_y=cfg.get("mousemat_serpentine_flip_y", False),
            swap_xy=cfg.get("mousemat_serpentine_swap_xy", False),
        )
        if cfg.get("mousemat_reverse", False):
            mapper.apply_reverse_order(mat_types)
    elif cfg.get("mousemat_serpentine"):
        mapper.apply_serpentine(
            mat_types,
            row_tolerance=cfg.get("mousemat_serpentine_row_tolerance"),
            first_dir=cfg.get("mousemat_serpentine_first_dir", "left"),
            row_order=cfg.get("mousemat_serpentine_row_order", "top"),
            rows_count=cfg.get("mousemat_serpentine_rows", 1),
            flip_x=cfg.get("mousemat_serpentine_flip_x", False),
            flip_y=cfg.get("mousemat_serpentine_flip_y", False),
            swap_xy=cfg.get("mousemat_serpentine_swap_xy", False),
            mode=cfg.get("mousemat_serpentine_mode", "linear"),
        )
        if cfg.get("mousemat_reverse", False):
            mapper.apply_reverse_order(mat_types)

    return mapper


def _apply_process_priority(cfg, logger):
    process_priority = str(cfg.get("process_priority", "high")).lower()
    if process_priority == "realtime":
        # REALTIME_PRIORITY_CLASS can starve input/audio drivers and freeze Windows.
        logger.warning("process_priority=realtime refuse (risque de gel systeme), 'high' utilise.")
        process_priority = "high"
    if process_priority not in ("normal", "high"):
        return
    try:
        if sys.platform == "win32":
            import ctypes

            priority_class = {
                "normal": 0x00000020,  # NORMAL_PRIORITY_CLASS
                "high": 0x00000080,  # HIGH_PRIORITY_CLASS
            }[process_priority]
            ctypes.windll.kernel32.SetPriorityClass(
                ctypes.windll.kernel32.GetCurrentProcess(),
                priority_class,
            )
        elif process_priority == "high":
            os.nice(-10)
    except Exception as exc:
        logger.debug("Priorite processus non appliquee: %s", exc)


def _apply_cpu_affinity(cfg, logger):
    cpu_affinity_core = cfg.get("cpu_affinity_core", -1)
    if cpu_affinity_core is None:
        return
    if not _HAS_PSUTIL:
        logger.warning("Affinite CPU demandee mais psutil indisponible.")
        return
    try:
        p = psutil.Process()
        cpu_count = psutil.cpu_count()
        if not cpu_count:
            raise RuntimeError("Nombre de coeurs indisponible.")
        try:
            core_index = int(cpu_affinity_core)
        except (TypeError, ValueError):
            raise ValueError("cpu_affinity_core invalide.")
        if core_index == -1:
            if cpu_count < 4:
                logger.info("Affinite CPU ignoree (moins de 4 coeurs disponibles).")
                return
            dedicated_core = [cpu_count - 1]
        else:
            if core_index < 0 or core_index >= cpu_count:
                raise ValueError(f"cpu_affinity_core invalide (0..{cpu_count - 1}).")
            dedicated_core = [core_index]
        p.cpu_affinity(dedicated_core)
        logger.info("Affinite CPU definie sur coeur %s", dedicated_core)
    except Exception as exc:
        logger.warning("Impossible de definir l'affinite CPU : %s", exc)


def _dump_thread_stacks(log_fn, prefix):
    thread_names = {thread.ident: thread.name for thread in threading.enumerate()}
    for thread_id, frame in sys._current_frames().items():
        log_fn(
            "%s thread=%s ident=%s\n%s",
            prefix,
            thread_names.get(thread_id, "unknown"),
            thread_id,
            "".join(traceback.format_stack(frame)),
        )


def _run_fan_tool(args, cfg, groups, mapper, lut):
    target_name = str(args.fan_group or "ventilos").lower()
    target = None
    for g in groups:
        if str(g.get("name", "")).lower() == target_name:
            target = g
            break
    if target is None:
        print(f"Groupe '{target_name}' introuvable. Utilise --mode unique.")
        return 1
    leds_per_fan = _cfg_int(cfg, "fan_outer_leds", 12) + _cfg_int(cfg, "fan_inner_leds", 4)
    if leds_per_fan <= 0:
        print("fan_outer_leds + fan_inner_leds invalide.")
        return 1
    total_leds = target.get("led_count", 0)
    if total_leds <= 0:
        print("Aucun LED detecte pour le groupe ventilos.")
        return 1
    if total_leds % leds_per_fan != 0:
        print(f"LEDs non multiple de {leds_per_fan} (total={total_leds}).")
    fan_count = _cfg_int(cfg, "fan_count", 0) or max(1, total_leds // leds_per_fan)
    map_len = len(target["map"])

    def push(frame):
        mapper.apply_frame_map(
            target["map"],
            target["device_ids"],
            frame,
            lut=lut,
            update_mode=target.get("update_mode", "direct_async"),
        )

    if args.fan_sweep:
        fan_index = int(args.fan_index)
        if fan_index < 1 or fan_index > fan_count:
            print(f"fan_index invalide (1..{fan_count}).")
            return 1
        start = (fan_index - 1) * leds_per_fan
        end = min(map_len, start + leds_per_fan)
        print(f"Sweep ventilo {fan_index}/{fan_count} (LEDs {start}-{end-1})")
        try:
            while True:
                for i in range(start, end):
                    frame = bytearray(map_len * 3)
                    frame[i * 3 : i * 3 + 3] = b"\xff\xff\xff"
                    push(frame)
                    time.sleep(max(0.01, float(args.fan_speed)))
        except KeyboardInterrupt:
            push(bytearray(map_len * 3))
            return 0

    indices = parse_int_list(args.fan_on)
    if not indices:
        print("fan_on invalide. Exemple: --fan-on 1,2")
        return 1
    color = parse_rgb(args.fan_color) or (255, 255, 255)
    frame = bytearray(map_len * 3)
    for fan_index in indices:
        if fan_index < 1 or fan_index > fan_count:
            continue
        start = (fan_index - 1) * leds_per_fan
        end = min(map_len, start + leds_per_fan)
        for i in range(start, end):
            frame[i * 3 : i * 3 + 3] = bytes(color)
    push(frame)
    print(f"Ventilos allumes: {indices} couleur={color[0]},{color[1]},{color[2]}")
    return 0


def run_bridge(args):
    global _I18N, _CONFIG_PATH
    cfg_path = _resolve_config_path(args.config)
    try:
        cfg = load_config(cfg_path)
    except FileNotFoundError:
        setup_logging({})
        _fatal(
            logging.getLogger("bridge"),
            f"Config introuvable: {cfg_path}. Place un config.json a cote du programme.",
        )
        return 1
    except (ValueError, RuntimeError) as exc:
        setup_logging({})
        _fatal(logging.getLogger("bridge"), f"config.json invalide ({cfg_path}): {exc}")
        return 1
    _CONFIG_PATH = cfg_path
    _I18N = i18n.get_i18n(cfg)
    logger = setup_logging(cfg)
    perf_debug, perf_threshold, perf_log_cooldown = get_perf_options(cfg, args)
    timing_logger = _configure_timing_logger(perf_debug)
    logger.info("Version: %s", APP_VERSION)
    logger.info("Config: %s", cfg_path)
    validate_config(cfg, logger)
    if perf_debug:
        logger.info(
            "[PERF] Diagnostic actif: seuil=%.3fs cooldown=%.1fs",
            perf_threshold,
            perf_log_cooldown,
        )
    _apply_process_priority(cfg, logger)
    _apply_cpu_affinity(cfg, logger)

    prompt_allowed = not (
        args.list_devices
        or args.list_groups
        or args.test
        or args.test_color
        or args.fan_sweep
        or args.fan_on
    )
    mode = choose_mode(cfg, args, prompt_allowed=prompt_allowed)

    try:
        sdk = CueSdkWrapper()
    except RuntimeError as exc:
        _fatal(logger, str(exc))
        return 1
    device_type_mask = parse_device_type_mask(cfg.get("device_type_mask"), sdk)
    reconnect_timeout = _cfg_float(cfg, "icue_reconnect_timeout", 8.0, minimum=0.5, logger=logger)
    layer_priority = _cfg_int(cfg, "icue_layer_priority", 255, minimum=0, maximum=255, logger=logger)

    logger.info("Connexion iCUE SDK...")
    err = sdk.connect()
    if err != sdk.CorsairError.CE_Success:
        _fatal(logger, f"Connexion iCUE SDK echouee: {err}")
        return 1
    ok, last_err = wait_for_icue(sdk, device_type_mask, timeout_s=reconnect_timeout)
    if not ok:
        msg = "iCUE non connecte (CE_NotConnected)"
        if last_err is not None and last_err != sdk.CorsairError.CE_Success:
            msg = f"iCUE non connecte: {last_err}"
        _fatal(
            logger,
            msg
            + "\nVerifie que iCUE est lance, que le SDK est active,"
            + "\net que le programme est lance avec les memes droits (admin ou non).",
        )
        return 1
    logger.info("iCUE connecte.")
    try:
        layer_err = sdk.set_layer_priority(layer_priority)
        if not sdk.is_success(layer_err):
            logger.warning("Priorite couche iCUE non appliquee: %s", layer_err)
        else:
            logger.info("Priorite couche iCUE definie sur %s.", layer_priority)
    except Exception as exc:
        logger.warning("Impossible de definir la priorite couche iCUE: %s", exc)

    try:
        mapper = build_mapper(cfg, sdk, device_type_mask, args)
    except RuntimeError as exc:
        _fatal(logger, str(exc))
        return 1
    request_control_for_devices(
        sdk, mapper=mapper, logger=logger, context="startup_request_control"
    )
    default_protocol = normalize_protocol(cfg.get("protocol"), "drgb")

    def setup_runtime_with_retry(next_groups, context):
        delays = (0.0, 0.05, 0.2, 0.5)
        for attempt, delay in enumerate(delays, start=1):
            if delay > 0:
                time.sleep(delay)
            try:
                return setup_runtime(next_groups)
            except OSError as exc:
                if getattr(exc, "winerror", None) == 10048 and attempt < len(delays):
                    logger.warning(
                        "%s: ports UDP encore occupes, tentative %s/%s",
                        context,
                        attempt + 1,
                        len(delays),
                    )
                    continue
                raise

    if args.list_devices:
        print(f"LED detectes: {mapper.total_leds}")
        logger.info("LED detectes: %s", mapper.total_leds)
        for dev in mapper.devices:
            dtype = _get_attr(dev.get("info"), ("type", "device_type"))
            print(
                f"- id={dev['device_id_str']} leds={dev.get('leds')} type={dtype} "
                f"model={dev.get('model')} serial={dev.get('serial')}"
            )
        return 0

    lut = build_lut(
        _cfg_float(cfg, "brightness", 1.0, minimum=0.0, logger=logger),
        _cfg_float(cfg, "gamma", 1.0, minimum=0.01, logger=logger),
    )
    if args.test or args.test_color:
        color = (255, 0, 0)
        if args.test_color:
            parsed = parse_rgb(args.test_color)
            if parsed is None:
                print("Couleur invalide. Exemple: --test-color 255,0,0")
                return 1
            color = parsed
        mapper.apply_frame(bytearray(bytes(color) * mapper.total_leds), lut=lut)
        print(f"Test LEDs applique: {color[0]},{color[1]},{color[2]}")
        logger.info("Test LEDs applique: %s,%s,%s", color[0], color[1], color[2])
        return 0

    max_fps = _cfg_float(cfg, "max_fps", 60.0, minimum=0.0, logger=logger)
    min_interval = 1.0 / max_fps if max_fps > 0 else 0.0
    try:
        groups = get_groups_for_mode(mode, cfg, mapper, sdk, default_protocol, args)
    except RuntimeError as exc:
        _fatal(logger, f"{exc}\nAjoute `groups` ou passe en mode groupe.")
        return 1

    if args.list_groups:
        for g in groups:
            labels = ", ".join(g.get("device_labels") or [])
            print(
                f"- {g['name']} port={g['udp_port']} leds={g['led_count']} proto={g['protocol']} devices={labels}"
            )
        return 0

    if args.fan_sweep or args.fan_on:
        return _run_fan_tool(args, cfg, groups, mapper, lut)

    debug_udp = args.debug_udp
    try:
        sel, runtime_groups = setup_runtime_with_retry(groups, "Initialisation runtime")
    except OSError as exc:
        _fatal(logger, f"Ouverture des ports UDP impossible: {exc}")
        return 1
    if not runtime_groups:
        _fatal(logger, "Aucun groupe valide. Verifie la config.")
        return 1

    _log_active_groups(logger, runtime_groups)
    if _HAS_MSVCRT and prompt_allowed and _has_console():
        print("Appuie sur M pour changer de mode.")

    watchdog_enabled = bool(cfg.get("icue_watchdog", True))
    watchdog_interval = _cfg_float(cfg, "icue_watchdog_interval", 5.0, minimum=0.5, logger=logger)
    watchdog_fail_threshold = _cfg_int(cfg, "icue_watchdog_fail_threshold", 3, minimum=1, logger=logger)
    reconnect_cooldown = _cfg_float(cfg, "icue_reconnect_cooldown", 15.0, minimum=0.0, logger=logger)
    watchdog_idle_only = bool(cfg.get("icue_watchdog_idle_only", False))
    skip_reconnect_when_idle = bool(cfg.get("icue_skip_reconnect_when_idle", False))
    watchdog_sdk_check = bool(cfg.get("icue_watchdog_sdk_check", False))
    restart_on_sdk_hang = bool(cfg.get("icue_restart_on_sdk_hang", True))
    keepalive_enabled = bool(cfg.get("icue_keepalive", True))
    keepalive_interval = _cfg_float(cfg, "icue_keepalive_interval", 5.0, minimum=0.5, logger=logger)
    keepalive_reapply = bool(cfg.get("icue_keepalive_reapply", True))
    keepalive_request_always = bool(cfg.get("icue_keepalive_request_always", False))
    request_control_interval = _cfg_float(
        cfg, "icue_request_control_interval", 0.0, minimum=0.0, logger=logger
    )
    request_control_reconnect = bool(cfg.get("icue_request_control_reconnect", False))
    unique_idle_clear_enabled = mode == "unique" and bool(cfg.get("unique_idle_clear", False))
    unique_idle_clear_s = _cfg_float(cfg, "unique_idle_clear_seconds", 1.0, minimum=0.2, logger=logger)
    apply_fail_threshold = _cfg_int(cfg, "icue_apply_fail_threshold", 6, minimum=1, logger=logger)
    request_control_fail_threshold = _cfg_int(
        cfg, "icue_request_control_fail_threshold", 2, minimum=1, logger=logger
    )
    last_watchdog = time.monotonic()
    last_stats_log = time.monotonic()
    last_request_control = time.monotonic()
    last_reconnect = 0.0
    watchdog_fail_count = 0
    request_control_fail_count = 0
    select_fail_count = 0

    _reconnect_lock = threading.Lock()
    _loop_alive = threading.Event()
    _last_loop_ts = time.monotonic()
    _perf_last_loop_warn = 0.0
    # Watchdog SDK checks and periodic request_control run off the UDP/main thread.
    _watchdog_lock = threading.Lock()
    _watchdog_result = {"connected": True, "ts": 0.0, "inflight": False}
    _request_control_lock = threading.Lock()
    _request_control_inflight = [False]

    def restart_process(reason):
        logger.warning("Redemarrage du processus requis: %s", reason)
        print(f"Redemarrage du bridge: {reason}")
        try:
            close_runtime(sel, runtime_groups)
        except Exception:
            pass
        _loop_alive.set()
        if getattr(sys, "frozen", False):
            cmd = [sys.executable] + _strip_mode_args(sys.argv[1:])
        else:
            cmd = [sys.executable] + _strip_mode_args(sys.argv)
        if mode:
            cmd.extend(["--mode", mode])
        try:
            subprocess.Popen(cmd, cwd=str(pathlib.Path.cwd()), close_fds=False)
        except Exception as exc:
            logger.error("Redemarrage impossible: %s", exc)
            print(f"Redemarrage impossible: {exc}")
        for handler in logging.getLogger().handlers:
            try:
                handler.flush()
            except Exception:
                pass
        os._exit(75)

    def activate_runtime(next_groups, context):
        """Bind next_groups' ports. The caller must have closed the previous runtime."""
        new_sel, new_runtime_groups = setup_runtime_with_retry(next_groups, context)
        if not new_runtime_groups:
            close_runtime(new_sel, new_runtime_groups)
            raise RuntimeError("aucun groupe actif")
        return new_sel, new_runtime_groups

    def attempt_reconnect(reason):
        logger.debug("attempt_reconnect raison=%s", reason)
        # Reconnect runs on a daemon thread so UDP polling continues meanwhile.
        if not _reconnect_lock.acquire(blocking=False):
            logger.debug("attempt_reconnect deja en cours raison=%s", reason)
            return

        def reconnect_worker():
            nonlocal last_reconnect, last_request_control, last_watchdog
            nonlocal mapper, groups, sdk, sel, runtime_groups, watchdog_fail_count
            nonlocal request_control_fail_count
            try:
                if restart_on_sdk_hang:
                    blocked, elapsed = mapper.direct_async_blocked()
                    if blocked:
                        restart_process(f"appel iCUE direct bloque depuis {elapsed:.1f}s")
                        return
                if (time.monotonic() - last_reconnect) < reconnect_cooldown:
                    logger.warning("Reconnexion ignoree (cooldown) raison=%s", reason)
                    return
                last_reconnect = time.monotonic()
                logger.warning("Reconnexion iCUE (raison: %s)", reason)
                sdk.release_control()
                sdk.disconnect()
                try:
                    new_sdk = CueSdkWrapper()
                    err = new_sdk.connect()
                except Exception as exc:
                    logger.exception("Connexion iCUE echoue pendant reconnexion: %s", exc)
                    return
                if err != new_sdk.CorsairError.CE_Success:
                    logger.warning("Reconnexion iCUE echouee: %s", err)
                    return
                ok, last_err = wait_for_icue(
                    new_sdk, device_type_mask, timeout_s=reconnect_timeout
                )
                if not ok:
                    logger.warning("iCUE pas pret apres reconnexion: %s", last_err)
                    return
                try:
                    layer_err = new_sdk.set_layer_priority(layer_priority)
                    if not new_sdk.is_success(layer_err):
                        logger.debug("set_layer_priority erreur err=%s", layer_err)
                except Exception as exc:
                    logger.debug("set_layer_priority exception: %s", exc)
                try:
                    new_mapper = build_mapper(cfg, new_sdk, device_type_mask, args)
                    new_groups = get_groups_for_mode(
                        mode, cfg, new_mapper, new_sdk, default_protocol, args
                    )
                except Exception as exc:
                    logger.exception("Rebuild apres reconnexion echoue: %s", exc)
                    return
                try:
                    request_control_for_devices(
                        new_sdk,
                        mapper=new_mapper,
                        logger=logger,
                        context="reconnect_request_control",
                    )
                except Exception as exc:
                    logger.debug("request_control_for_devices exception: %s", exc)

                # The same UDP ports are reused, so the old sockets must be released
                # before binding. If binding fails, restore the old runtime; if even
                # that fails, restart the process rather than staying deaf forever.
                old_mapper = mapper
                close_runtime(sel, runtime_groups)
                try:
                    new_sel, new_runtime_groups = activate_runtime(new_groups, "Reconnexion iCUE")
                except Exception as exc:
                    logger.error("Activation runtime apres reconnexion echouee: %s", exc)
                    new_mapper.close()
                    try:
                        sel, runtime_groups = activate_runtime(groups, "Restauration runtime")
                        logger.warning("Ancien runtime restaure; nouvelle tentative plus tard.")
                    except Exception as exc2:
                        restart_process(f"ports UDP indisponibles apres reconnexion: {exc2}")
                    return
                sdk = new_sdk
                mapper = new_mapper
                groups = new_groups
                sel = new_sel
                runtime_groups = new_runtime_groups
                old_mapper.close()
                last_request_control = time.monotonic()
                last_watchdog = last_request_control
                watchdog_fail_count = 0
                request_control_fail_count = 0
                logger.info("Reconnexion iCUE OK.")
                _log_active_groups(logger, runtime_groups)
            except Exception as exc:
                logger.exception("Reconnexion iCUE: erreur inattendue: %s", exc)
            finally:
                _reconnect_lock.release()

        try:
            threading.Thread(
                target=reconnect_worker,
                name="icue-reconnect",
                daemon=True,
            ).start()
        except Exception as exc:
            _reconnect_lock.release()
            logger.warning("Demarrage thread reconnexion echoue: %s", exc)

    def ensure_request_control(context, reconnect_reason):
        nonlocal request_control_fail_count
        try:
            ok = request_control_for_devices(
                sdk,
                mapper=mapper,
                logger=logger,
                context=context,
            )
        except Exception as exc:
            logger.warning("iCUE %s exception: %s", context, exc)
            ok = False
        if ok:
            request_control_fail_count = 0
            return True
        request_control_fail_count += 1
        logger.warning(
            "iCUE %s fail (%s/%s)",
            context,
            request_control_fail_count,
            request_control_fail_threshold,
        )
        if request_control_reconnect and (
            request_control_fail_count >= request_control_fail_threshold
        ):
            request_control_fail_count = 0
            attempt_reconnect(reconnect_reason)
        return False

    def apply_mode_change(new_mode):
        nonlocal mode, groups, sel, runtime_groups
        if not new_mode or new_mode == mode:
            return
        if _reconnect_lock.locked():
            logger.warning("Changement de mode ignore: reconnexion en cours.")
            return
        try:
            new_groups = get_groups_for_mode(
                new_mode, cfg, mapper, sdk, default_protocol, args
            )
        except RuntimeError as exc:
            logger.warning("Mode %s indisponible (%s). Reste en mode %s.", new_mode, exc, mode)
            print(f"Mode {new_mode} indisponible: {exc}. Reste en mode {mode}.")
            return
        close_runtime(sel, runtime_groups)
        try:
            new_sel, new_runtime_groups = activate_runtime(new_groups, "Changement de mode")
        except Exception as exc:
            logger.error("Changement de mode vers %s impossible: %s", new_mode, exc)
            try:
                sel, runtime_groups = activate_runtime(groups, "Restauration mode")
            except Exception as exc2:
                restart_process(f"restauration du mode {mode} impossible: {exc2}")
            return
        mode = new_mode
        groups = new_groups
        sel = new_sel
        runtime_groups = new_runtime_groups
        logger.info("Mode actif: %s", mode)
        _log_active_groups(logger, runtime_groups)

    def recover_runtime(reason):
        """Rebind the current groups after the selector became unusable."""
        nonlocal sel, runtime_groups
        logger.warning("Reouverture des ports UDP: %s", reason)
        close_runtime(sel, runtime_groups)
        try:
            sel, runtime_groups = activate_runtime(groups, "Reouverture runtime")
        except Exception as exc:
            restart_process(f"reouverture des ports UDP impossible: {exc}")

    def _run_watchdog_check():
        try:
            result = is_icue_connected(sdk, device_type_mask)
        except Exception:
            result = False
        with _watchdog_lock:
            _watchdog_result["connected"] = result
            _watchdog_result["ts"] = time.monotonic()
            _watchdog_result["inflight"] = False

    def _run_request_control(context, reconnect_reason, success_message=None):
        try:
            ok = ensure_request_control(context, reconnect_reason)
            if ok and success_message:
                logger.info(success_message)
        finally:
            with _request_control_lock:
                _request_control_inflight[0] = False

    def start_request_control(*thread_args):
        with _request_control_lock:
            if _request_control_inflight[0]:
                return
            _request_control_inflight[0] = True
        try:
            threading.Thread(
                target=_run_request_control,
                args=thread_args,
                daemon=True,
                name="icue-request-control",
            ).start()
        except Exception as exc:
            with _request_control_lock:
                _request_control_inflight[0] = False
            logger.warning("request_control thread exception: %s", exc)

    def _perf_group_warn(g, key, message, *values):
        if not perf_debug:
            return
        now_perf = time.monotonic()
        store_key = f"perf_last_{key}_warn"
        last_perf = g.get(store_key, 0.0)
        if now_perf - last_perf < perf_log_cooldown:
            return
        g[store_key] = now_perf
        logger.warning(message, *values)

    def push_group(g, context):
        """Send g's frame buffer to iCUE; exceptions propagate to the caller."""
        apply_start = time.perf_counter()
        ok = mapper.apply_frame_map(
            g["map"],
            g["device_ids"],
            g["frame_buffer"],
            lut=lut,
            update_mode=g.get("update_mode", "direct_async"),
        )
        apply_elapsed = time.perf_counter() - apply_start
        timing_logger.log(
            logging.WARNING if apply_elapsed >= 0.010 else logging.DEBUG,
            "[BLOCK] apply_frame_map(%s) took %.1fms ok=%s",
            context,
            apply_elapsed * 1000.0,
            ok,
        )
        if perf_debug:
            g["perf_max_apply_elapsed"] = max(
                g.get("perf_max_apply_elapsed", 0.0), apply_elapsed
            )
            if apply_elapsed > perf_threshold:
                _perf_group_warn(
                    g,
                    "apply",
                    "[PERF] bridge apply %s[%s] lent %.3fs update_mode=%s ok=%s",
                    context,
                    g.get("name"),
                    apply_elapsed,
                    g.get("update_mode", "direct_async"),
                    ok,
                )
        return ok

    def send_udp_frame(g, now):
        if identify_state["until"] > now:
            # The layout editor is highlighting LEDs: keep the frame for later.
            g["pending_apply"] = True
            return
        g["last_send"] = now
        g["pending_apply"] = False
        try:
            ok = push_group(g, "udp")
        except Exception as exc:
            # Transient mapper errors are expected while a reconnect swaps state.
            if _reconnect_lock.locked():
                logger.debug("apply_frame_map ignore pendant reconnexion: %s", exc)
                return
            logger.exception("apply_frame_map erreur: %s", exc)
            attempt_reconnect("apply_frame_map_error")
            return
        if ok:
            g["fail_count"] = 0
            return
        g["fail_count"] = g.get("fail_count", 0) + 1
        if g["fail_count"] >= apply_fail_threshold:
            g["fail_count"] = 0
            attempt_reconnect("apply_no_success")

    def _debug_loop_watchdog():
        while not _loop_alive.wait(3.0):
            delta = time.monotonic() - _last_loop_ts
            if delta <= 10.0:
                continue
            logger.error(
                "[WATCHDOG] boucle principale bloquee delta=%.3fs mode=%s runtime_groups=%s",
                delta,
                mode,
                len(runtime_groups),
            )
            _dump_thread_stacks(logger.error, "[WATCHDOG]")

    def reload_layout():
        """Apply a changed config.json without restarting. Returns False to retry later."""
        nonlocal mapper, groups, sel, runtime_groups
        try:
            new_cfg = load_config(cfg_path)
        except Exception as exc:
            logger.warning("config.json modifie mais illisible, ignore: %s", exc)
            return True
        if new_cfg == cfg:
            return True
        if {k: v for k, v in new_cfg.items() if k != "ui_language"} == {
            k: v for k, v in cfg.items() if k != "ui_language"
        }:
            cfg.update(new_cfg)
            return True
        if not _reconnect_lock.acquire(blocking=False):
            return False
        try:
            validate_config(new_cfg, logger)
            try:
                new_mapper = build_mapper(new_cfg, sdk, device_type_mask, args, clear_on_start=False)
                new_groups = get_groups_for_mode(
                    mode, new_cfg, new_mapper, sdk, default_protocol, args
                )
            except Exception as exc:
                logger.error("Nouvelle disposition invalide, ancienne conservee: %s", exc)
                return True
            old_mapper = mapper
            close_runtime(sel, runtime_groups)
            try:
                new_sel, new_runtime_groups = activate_runtime(new_groups, "Rechargement config")
            except Exception as exc:
                logger.error("Rechargement config: ports UDP indisponibles: %s", exc)
                new_mapper.close()
                try:
                    sel, runtime_groups = activate_runtime(groups, "Restauration runtime")
                except Exception as exc2:
                    restart_process(f"restauration apres rechargement impossible: {exc2}")
                return True
            cfg.clear()
            cfg.update(new_cfg)
            mapper = new_mapper
            groups = new_groups
            sel = new_sel
            runtime_groups = new_runtime_groups
            old_mapper.close()
            logger.info("Disposition rechargee depuis config.json.")
            _log_active_groups(logger, runtime_groups)
            return True
        finally:
            _reconnect_lock.release()

    def _global_indices(targets):
        index = {(d, i): n for n, (d, i) in enumerate(mapper.global_map)}
        return [index[t] for t in targets if t in index]

    def start_identify(targets, now):
        identify_state.update(
            mode="blink",
            until=now + IDENTIFY_SECONDS,
            lit=sorted(set(_global_indices(targets))),
            next=0.0,
            on=False,
        )

    def start_sweep(targets, now):
        sequence = _global_indices(targets)
        identify_state.update(
            mode="sweep",
            until=now + len(sequence) * SWEEP_STEP_SECONDS + 0.4,
            sequence=sequence,
            pos=0,
            next=0.0,
        )

    def step_identify(now):
        """Run the editor's LED preview; returns True while it is running."""
        if identify_state["until"] <= 0:
            return False
        if now >= identify_state["until"]:
            identify_state["until"] = 0.0
            # Restore every group's last LedFx frame.
            for g in runtime_groups:
                g["pending_apply"] = True
            return False
        if now >= identify_state["next"]:
            frame = bytearray(len(mapper.global_map) * 3)
            if identify_state["mode"] == "sweep":
                # A short white band travels along the LEDs in stream order.
                pos = identify_state["pos"]
                lit = identify_state["sequence"][max(0, pos - SWEEP_BAND + 1) : pos + 1]
                identify_state["pos"] = pos + 1
                identify_state["next"] = now + SWEEP_STEP_SECONDS
            else:
                identify_state["on"] = not identify_state["on"]
                identify_state["next"] = now + 0.25
                lit = identify_state["lit"] if identify_state["on"] else []
            for n in lit:
                frame[n * 3 : n * 3 + 3] = b"\xff\xff\xff"
            try:
                mapper.apply_frame_map(
                    mapper.global_map,
                    list(mapper.led_colors_by_device.keys()),
                    frame,
                    update_mode="direct_async",
                )
            except Exception as exc:
                logger.debug("Identification: ecriture ignoree: %s", exc)
        return True

    def _config_mtime():
        try:
            return os.stat(cfg_path).st_mtime_ns
        except OSError:
            return None

    identify_state = {"mode": "blink", "until": 0.0, "lit": [], "next": 0.0, "on": False}
    layout_requests = queue.Queue()
    cfg_mtime = _config_mtime()
    last_cfg_check = time.monotonic()
    if _MODE_WINDOW is not None:
        _MODE_WINDOW.layout_backend = LayoutBackend(
            lambda: (json.loads(json.dumps(cfg)), mapper, sdk),
            layout_requests,
            cfg_path,
        )

    _debug_watchdog_thread = threading.Thread(
        target=_debug_loop_watchdog,
        name="loop-watchdog",
        daemon=True,
    )
    _debug_watchdog_thread.start()
    try:
        while True:
            now = time.monotonic()
            _loop_delta = now - _last_loop_ts
            _last_loop_ts = now
            if perf_debug:
                if _loop_delta > 0.100:
                    timing_logger.warning("[TICK] loop iter took %.1fms", _loop_delta * 1000.0)
                if _loop_delta > 0.200:
                    _dump_thread_stacks(timing_logger.warning, "[STACK]")
                if _loop_delta > max(0.75, perf_threshold) and (
                    now - _perf_last_loop_warn >= perf_log_cooldown
                ):
                    _perf_last_loop_warn = now
                    logger.warning(
                        "[PERF] boucle principale lente %.3fs mode=%s runtime_groups=%s",
                        _loop_delta,
                        mode,
                        len(runtime_groups),
                    )
            if _MODE_WINDOW is not None and _MODE_WINDOW.available:
                gui_mode = _MODE_WINDOW.poll()
                if gui_mode == _MODE_EXIT:
                    print("Arret demande via la fenetre.")
                    logger.info("Arret demande via la fenetre.")
                    return 0
                if gui_mode and gui_mode != mode:
                    apply_mode_change(gui_mode)

            while True:
                try:
                    request, payload = layout_requests.get_nowait()
                except queue.Empty:
                    break
                if request == "identify":
                    start_identify(payload, now)
                elif request == "sweep":
                    start_sweep(payload, now)
            identifying = step_identify(now)

            # Pick up config.json edits (layout editor or manual) without a restart.
            if now - last_cfg_check >= 1.0:
                last_cfg_check = now
                mtime = _config_mtime()
                if mtime != cfg_mtime and reload_layout():
                    cfg_mtime = mtime

            # Wake up early when a throttled frame is waiting to be flushed.
            select_timeout = 0.05
            if identifying:
                select_timeout = max(0.001, min(select_timeout, identify_state["next"] - now))
            elif min_interval:
                for g in runtime_groups:
                    if g.get("pending_apply"):
                        remaining = min_interval - (now - g["last_send"])
                        select_timeout = max(0.001, min(select_timeout, remaining))
            select_start = time.perf_counter()
            current_sel = sel
            try:
                events = current_sel.select(timeout=select_timeout)
                select_fail_count = 0
            except Exception as exc:
                events = []
                if _reconnect_lock.locked():
                    # Sockets are being swapped by the reconnect worker.
                    time.sleep(0.01)
                else:
                    select_fail_count += 1
                    logger.warning(
                        "sel.select exception (%s/20) runtime_groups=%s %s: %s",
                        select_fail_count,
                        len(runtime_groups),
                        type(exc).__name__,
                        exc,
                    )
                    time.sleep(0.05)
                    if select_fail_count >= 20:
                        select_fail_count = 0
                        recover_runtime(f"select en echec: {exc}")
            select_elapsed = time.perf_counter() - select_start
            timing_logger.log(
                logging.WARNING if select_elapsed >= select_timeout + 0.010 else logging.DEBUG,
                "[BLOCK] sel.select took %.1fms (events=%s)",
                select_elapsed * 1000.0,
                len(events),
            )
            now = time.monotonic()

            if request_control_interval > 0 and (
                now - last_request_control
            ) >= request_control_interval:
                start_request_control(
                    "periodic_request_control",
                    "periodic_request_control_no_control",
                )
                last_request_control = now

            any_active_recent = any(
                g.get("last_packet_ts", 0.0)
                and (now - g["last_packet_ts"]) < (g.get("keepalive_interval") or keepalive_interval)
                for g in runtime_groups
            )
            if keepalive_enabled and not identifying:
                due_groups = []
                for g in runtime_groups:
                    interval = g.get("keepalive_interval") or keepalive_interval
                    if now - g.get("last_keepalive", 0.0) < interval:
                        continue
                    g["last_keepalive"] = now
                    if g.get("keepalive_reapply", None) is False:
                        continue
                    last_pkt = g.get("last_packet_ts", 0.0)
                    if not last_pkt or (now - last_pkt) < interval:
                        continue
                    if g.get("last_send", 0.0) <= 0:
                        continue
                    due_groups.append(g)

                if due_groups and keepalive_request_always:
                    start_request_control(
                        "keepalive_request_control",
                        "keepalive_request_control_no_control",
                        "iCUE keepalive: request_control",
                    )

                if keepalive_reapply:
                    for g in due_groups:
                        try:
                            ok = push_group(g, "keepalive")
                        except Exception as exc:
                            if _reconnect_lock.locked():
                                logger.debug("Keepalive ignore pendant reconnexion: %s", exc)
                                continue
                            logger.exception("Keepalive apply_frame_map erreur: %s", exc)
                            if skip_reconnect_when_idle and not any_active_recent:
                                logger.warning("Keepalive erreur (idle), reconnexion ignoree.")
                            else:
                                attempt_reconnect("keepalive_error")
                            continue
                        if ok:
                            continue
                        g["fail_count"] = g.get("fail_count", 0) + 1
                        if g["fail_count"] >= apply_fail_threshold:
                            g["fail_count"] = 0
                            if skip_reconnect_when_idle and not any_active_recent:
                                logger.warning("Keepalive echec (idle), reconnexion ignoree.")
                            else:
                                attempt_reconnect("keepalive_no_success")

            if unique_idle_clear_enabled and any_active_recent and not identifying:
                for g in runtime_groups:
                    if g.get("idle_clear_disabled", False) or g.get("idle_cleared", False):
                        continue
                    clear_after = g.get("idle_clear_seconds")
                    if clear_after is None:
                        clear_after = unique_idle_clear_s
                    last_pkt = g.get("last_packet_ts", 0.0)
                    if not last_pkt:
                        continue
                    idle_for = now - last_pkt
                    if idle_for < clear_after:
                        continue
                    frame = g.get("frame_buffer")
                    if frame is None:
                        continue
                    frame[:] = bytes(len(frame))
                    g["pending_apply"] = False
                    try:
                        ok = push_group(g, "idle_clear")
                    except Exception as exc:
                        if _reconnect_lock.locked():
                            logger.debug("Idle clear ignore pendant reconnexion (%s): %s", g.get("name"), exc)
                        else:
                            logger.exception("Idle clear erreur (%s): %s", g.get("name"), exc)
                        continue
                    if ok:
                        g["last_send"] = now
                        g["fail_count"] = 0
                        g["idle_cleared"] = True
                        logger.info("UDP[%s]: clear idle apres %.1fs", g.get("name"), idle_for)

            direct_blocked, direct_elapsed = mapper.direct_async_blocked()
            if direct_blocked and restart_on_sdk_hang:
                restart_process(f"appel iCUE direct bloque depuis {direct_elapsed:.1f}s")
                return 0

            if watchdog_enabled and now - last_watchdog >= watchdog_interval:
                last_watchdog = now
                active_recent = any(
                    (now - g.get("last_packet_ts", 0.0)) < watchdog_interval
                    for g in runtime_groups
                )
                if (
                    (watchdog_idle_only and active_recent)
                    or (skip_reconnect_when_idle and not active_recent)
                    or direct_elapsed > 0
                    or not watchdog_sdk_check
                ):
                    watchdog_fail_count = 0
                else:
                    # The main loop only reads the cached result of the last check.
                    with _watchdog_lock:
                        watchdog_already_inflight = _watchdog_result["inflight"]
                        watchdog_last_result = _watchdog_result["connected"]
                        if not watchdog_already_inflight:
                            _watchdog_result["inflight"] = True
                    if not watchdog_already_inflight:
                        try:
                            threading.Thread(
                                target=_run_watchdog_check,
                                daemon=True,
                                name="icue-watchdog-check",
                            ).start()
                        except Exception as exc:
                            with _watchdog_lock:
                                _watchdog_result["inflight"] = False
                            logger.warning("watchdog thread exception: %s", exc)
                    if not watchdog_last_result:
                        watchdog_fail_count += 1
                        logger.warning(
                            "iCUE check fail (%s/%s)", watchdog_fail_count, watchdog_fail_threshold
                        )
                        if watchdog_fail_count >= watchdog_fail_threshold:
                            watchdog_fail_count = 0
                            logger.warning("iCUE deconnecte, tentative de reconnexion...")
                            print("iCUE deconnecte, tentative de reconnexion...")
                            attempt_reconnect("watchdog")
                    else:
                        watchdog_fail_count = 0

            if now - last_stats_log >= 10.0:
                last_stats_log = now
                for g in runtime_groups:
                    last_pkt = g.get("last_packet_ts", 0.0)
                    last_send = g.get("last_send", 0.0)
                    logger.info(
                        "UDP[%s]: idle %s, last_send=%s, leds=%s",
                        g.get("name"),
                        "never" if not last_pkt else f"{now - last_pkt:.1f}s",
                        "never" if not last_send else f"{now - last_send:.1f}s ago",
                        g.get("led_count"),
                    )
                    if perf_debug:
                        logger.info(
                            "[PERF] UDP[%s]: max_udp_gap=%.3fs max_apply=%.3fs",
                            g.get("name"),
                            g.get("perf_max_udp_gap", 0.0),
                            g.get("perf_max_apply_elapsed", 0.0),
                        )
                        g["perf_max_udp_gap"] = 0.0
                        g["perf_max_apply_elapsed"] = 0.0

            if debug_udp:
                for g in runtime_groups:
                    if now - g["stats_ts"] >= 1.0:
                        if g["pkt_count"] == 0:
                            print(f"UDP[{g['name']}]: 0 paquets/s")
                        else:
                            max_val = max(g["frame_buffer"]) if g["frame_buffer"] else 0
                            print(
                                f"UDP[{g['name']}]: {g['pkt_count']} paquets/s, "
                                f"{g['byte_count']} octets/s, max={max_val}"
                            )
                        g["pkt_count"] = 0
                        g["byte_count"] = 0
                        g["stats_ts"] = now

            for key, _ in events:
                g = key.data
                # Every queued datagram is parsed in order: LedFx splits large
                # frames into several DNRGB/DDP packets, so keeping only the last
                # one would drop parts of the frame.
                packets = read_udp_packets(key.fileobj)
                if not packets:
                    continue
                if g["first_packet"]:
                    g["first_packet"] = False
                    first = packets[0]
                    proto_hex = f"0x{first[0]:02x}" if first else "n/a"
                    print(
                        f"Premier paquet UDP recu pour {g['name']}: "
                        f"{len(first)} octets, byte0={proto_hex}"
                    )
                    logger.info(
                        "Premier paquet UDP recu pour %s: %s octets, byte0=%s",
                        g["name"],
                        len(first),
                        proto_hex,
                    )
                if debug_udp:
                    g["pkt_count"] += len(packets)
                    g["byte_count"] += sum(len(p) for p in packets)
                prev_packet_ts = g.get("last_packet_ts", 0.0)
                if perf_debug and prev_packet_ts:
                    udp_gap = now - prev_packet_ts
                    g["perf_max_udp_gap"] = max(g.get("perf_max_udp_gap", 0.0), udp_gap)
                    if udp_gap > perf_threshold:
                        _perf_group_warn(
                            g,
                            "udp_gap",
                            "[PERF] UDP[%s] trou entre paquets %.3fs port=%s",
                            g.get("name"),
                            udp_gap,
                            g.get("udp_port"),
                        )
                g["last_packet_ts"] = now
                g["idle_cleared"] = False

                protocol = g["protocol"]
                ready, saw_ddp = ingest_udp_packets(protocol, packets, g["frame_buffer"])
                if protocol == "wled" and saw_ddp and not g.get("ddp_auto"):
                    g["ddp_auto"] = True
                    logger.info(
                        "DDP detecte sur %s (auto-detection activee pour wled).",
                        g.get("name"),
                    )
                if not ready:
                    continue
                if min_interval and now - g["last_send"] < min_interval:
                    # Throttled: remember the frame and flush it once the interval
                    # elapses, so the last frame of a burst is never lost.
                    g["pending_apply"] = True
                    continue
                send_udp_frame(g, now)

            for g in runtime_groups:
                if g.get("pending_apply") and (
                    not min_interval or now - g["last_send"] >= min_interval
                ):
                    send_udp_frame(g, now)

            if _HAS_MSVCRT and prompt_allowed and _has_console() and msvcrt.kbhit():
                key = msvcrt.getwch()
                if key in ("m", "M"):
                    if _MODE_WINDOW is None or not _MODE_WINDOW.available:
                        apply_mode_change(prompt_mode(mode))
    except KeyboardInterrupt:
        print("Arret.")
        logger.info("Arret.")
        return 0
    finally:
        _loop_alive.set()
        _debug_watchdog_thread.join(timeout=1.0)
        close_runtime(sel, runtime_groups)
