import locale
import os


_MESSAGES = {
    "fr": {
        "window_title": "Choisir mode",
        "app_title": "LedFx iCUE Bridge",
        "choose_mode": "Choisir le mode (defaut: {default_mode})",
        "mode_selected": "Mode selectionne: {mode}",
        "mode_unique": "Unique",
        "mode_group": "Groupe",
        "mode_fusion": "Fusion",
        "quit": "Quitter",
        "confirm_close_title": "Confirmer la fermeture",
        "confirm_close_body": "Voulez-vous fermer le programme ?",
        "toggle_language": "Langue",
        "layout_button": "Disposition",
        "layout_title": "Disposition des LEDs",
        "layout_unavailable": "L'éditeur sera disponible une fois iCUE connecté.",
        "layout_intro": "Le haut de chaque liste reçoit le début de l'effet LedFx. "
        "Glisse les éléments ou utilise les flèches, puis Enregistrer.",
        "layout_tab_fans": "Ventilateurs",
        "layout_tab_aio": "AIO",
        "layout_tab_devices": "Périphériques",
        "layout_tab_fusion": "Mode fusion",
        "layout_fans_help": "Ordre des ventilateurs du boîtier (tous modes). En mode surface, "
        "le haut de la liste est le ventilateur placé du côté où l'effet démarre.",
        "layout_surface": "Les ventilateurs forment une seule surface (l'effet les balaie d'un bout à l'autre)",
        "layout_calibration": "Calibrage de la surface",
        "layout_surface_first": "1er ventilateur de la liste (début de l'effet) :",
        "layout_led_start": "1re LED de chaque anneau :",
        "layout_led_rotation": "Sens des LEDs dans l'anneau :",
        "layout_clockwise": "horaire",
        "layout_counter": "antihoraire",
        "layout_led_inner_first": "Les LEDs du centre sont câblées en premier",
        "layout_side_top": "en haut",
        "layout_side_bottom": "en bas",
        "layout_side_left": "à gauche",
        "layout_side_right": "à droite",
        "layout_sweep": "Tester le balayage",
        "layout_sweeping": "Balayage en cours : vérifie qu'il part du bon côté et traverse les ventilateurs en bloc.",
        "layout_fan_direction": "Sens dans chaque ventilateur (sans surface) :",
        "layout_dir_normal": "normal",
        "layout_dir_reverse": "inversé",
        "layout_aio_help": "Ordre des zones de l'AIO. En mode fusion, le 1er élément est inséré "
        "parmi les ventilateurs du boîtier, les suivants vont en fin de ruban.",
        "layout_aio_unique": "Appliquer aussi au groupe AIO du mode unique",
        "layout_devices_help": "Ordre des périphériques dans chaque groupe (modes unique et fusion).",
        "layout_fusion_help": "Ordre des sections du ruban en mode fusion.",
        "layout_cpu_after": "Pompe AIO insérée après le ventilateur n° :",
        "layout_up": "▲ Monter",
        "layout_down": "▼ Descendre",
        "layout_identify": "Identifier",
        "layout_save": "Enregistrer et appliquer",
        "layout_reset": "Rétablir",
        "layout_close": "Fermer",
        "layout_saved": "Enregistré : appliqué au bridge dans 1 seconde.",
        "layout_no_change": "Aucune modification.",
        "layout_save_error": "Échec de l'enregistrement : {error}",
        "layout_identifying": "Clignotement de « {item} » pendant 3 s...",
        "layout_unsaved_title": "Modifications non enregistrées",
        "layout_unsaved_body": "Fermer sans enregistrer ?",
        "layout_fan": "Ventilateur {n}",
        "layout_pump": "Pompe",
        "layout_aio_fan": "Ventilateur AIO {n}",
        "section_clavier": "Clavier",
        "section_tapis": "Tapis de souris",
        "section_souris": "Souris",
        "section_ventilos": "Ventilateurs boîtier (+ pompe AIO)",
        "section_ram": "RAM",
        "section_aio_ventilos": "Ventilateurs AIO (radiateur)",
    },
    "en": {
        "window_title": "Choose mode",
        "app_title": "LedFx iCUE Bridge",
        "choose_mode": "Choose the mode (default: {default_mode})",
        "mode_selected": "Selected mode: {mode}",
        "mode_unique": "Unique",
        "mode_group": "Group",
        "mode_fusion": "Fusion",
        "quit": "Quit",
        "confirm_close_title": "Confirm exit",
        "confirm_close_body": "Do you want to close the program?",
        "toggle_language": "Language",
        "layout_button": "Layout",
        "layout_title": "LED layout",
        "layout_unavailable": "The editor becomes available once iCUE is connected.",
        "layout_intro": "The top of each list receives the start of the LedFx effect. "
        "Drag items or use the arrows, then Save.",
        "layout_tab_fans": "Fans",
        "layout_tab_aio": "AIO",
        "layout_tab_devices": "Devices",
        "layout_tab_fusion": "Fusion mode",
        "layout_fans_help": "Order of the case fans (all modes). In surface mode, the top of "
        "the list is the fan on the side where the effect starts.",
        "layout_surface": "The fans form a single surface (the effect sweeps across them)",
        "layout_calibration": "Surface calibration",
        "layout_surface_first": "First fan of the list (effect start):",
        "layout_led_start": "First LED of each ring:",
        "layout_led_rotation": "LED direction in the ring:",
        "layout_clockwise": "clockwise",
        "layout_counter": "counter-clockwise",
        "layout_led_inner_first": "The centre LEDs are wired first",
        "layout_side_top": "top",
        "layout_side_bottom": "bottom",
        "layout_side_left": "left",
        "layout_side_right": "right",
        "layout_sweep": "Test the sweep",
        "layout_sweeping": "Sweeping: check it starts on the right side and crosses the fans as one block.",
        "layout_fan_direction": "Direction inside each fan (no surface):",
        "layout_dir_normal": "normal",
        "layout_dir_reverse": "reversed",
        "layout_aio_help": "Order of the AIO zones. In fusion mode the first item is inserted "
        "among the case fans, the others go to the end of the strip.",
        "layout_aio_unique": "Also apply to the AIO group in unique mode",
        "layout_devices_help": "Order of the devices inside each group (unique and fusion modes).",
        "layout_fusion_help": "Order of the strip sections in fusion mode.",
        "layout_cpu_after": "AIO pump inserted after case fan no.:",
        "layout_up": "▲ Up",
        "layout_down": "▼ Down",
        "layout_identify": "Identify",
        "layout_save": "Save and apply",
        "layout_reset": "Revert",
        "layout_close": "Close",
        "layout_saved": "Saved: applied to the bridge within 1 second.",
        "layout_no_change": "No changes.",
        "layout_save_error": "Save failed: {error}",
        "layout_identifying": "Blinking “{item}” for 3 s...",
        "layout_unsaved_title": "Unsaved changes",
        "layout_unsaved_body": "Close without saving?",
        "layout_fan": "Fan {n}",
        "layout_pump": "Pump",
        "layout_aio_fan": "AIO fan {n}",
        "section_clavier": "Keyboard",
        "section_tapis": "Mousemat",
        "section_souris": "Mouse",
        "section_ventilos": "Case fans (+ AIO pump)",
        "section_ram": "RAM",
        "section_aio_ventilos": "AIO fans (radiator)",
    },
}


def _normalize_lang(value):
    if not value:
        return None
    v = str(value).strip().lower()
    if v.startswith("fr"):
        return "fr"
    if v.startswith("en"):
        return "en"
    return None


def _detect_lang():
    env_lang = _normalize_lang(os.environ.get("LEDFX_UI_LANG"))
    if env_lang:
        return env_lang
    try:
        loc = locale.getlocale()[0] or ""
    except Exception:
        loc = ""
    detected = _normalize_lang(loc)
    return detected or "fr"


class I18n:
    def __init__(self, lang=None):
        self.lang = _normalize_lang(lang) or _detect_lang()

    def set_lang(self, lang):
        normalized = _normalize_lang(lang)
        if normalized:
            self.lang = normalized

    def t(self, key, **kwargs):
        msg = _MESSAGES.get(self.lang, _MESSAGES["fr"]).get(key, key)
        if kwargs:
            try:
                return msg.format(**kwargs)
            except Exception:
                return msg
        return msg


def get_i18n(cfg=None, lang=None):
    if lang is None and cfg is not None:
        lang = cfg.get("ui_language")
    return I18n(lang)
