"""Shared pieces of the Custom effects: their category, beat latch and drawing helpers."""

import colorsys
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from ledfx.color import parse_color
from ledfx.effects.audio import AudioAnalysisSource

# Every Custom effect lists itself here in the effect picker
CUSTOM_CATEGORY = "Custom"
# Longest frame step a simulation integrates: a stalled frame must not teleport things
MAX_STEP = 0.1
# Shortest gap between two hits: one drum hit can be detected on two frames in a row
TRIGGER_COOLDOWN = 0.08
# The audio callback runs once per analysis frame, at this rate
AUDIO_STEP = 1 / 60
# Below this volume a detected pitch is noise, not a note
NOTE_GATE = 0.05
# Beats per second assumed until the tempo is known (120 BPM), and the believable range
DEFAULT_BEAT_RATE = 2.0
MIN_BEAT_RATE = 0.75
MAX_BEAT_RATE = 3.5

FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int_]
BoolArray = NDArray[np.bool_]
Trigger = Literal["Beat", "Percussion"]


def color_array(value: str) -> FloatArray:
    return np.array(parse_color(value), dtype=float)


def frame_step(passed: float) -> float:
    return min(passed, MAX_STEP)


def hue_colors(hues: FloatArray) -> FloatArray:
    """Fully saturated colors for hues from 0 to 1, red at 0, one row per hue."""
    sixths = (np.asarray(hues, dtype=float) % 1)[..., None] * 6
    k = (np.array((5.0, 3.0, 1.0)) + sixths) % 6
    return (1 - np.clip(np.minimum(k, 4 - k), 0, 1)) * 255


def segment_widths(pixel_count: int, count: int) -> IntArray:
    """Widths of count near-equal segments covering the strip, at least one pixel each."""
    count = max(1, min(count, pixel_count))
    return np.diff(np.linspace(0, pixel_count, count + 1).astype(int))


def splat(
    target: FloatArray, x: FloatArray, center: float, radius: float, amount: float
) -> None:
    """Max-blend a soft glow of the given radius into target, touching only nearby pixels."""
    lo = max(0, int(center - 3 * radius))
    hi = min(target.size, int(center + 3 * radius) + 2)
    if lo >= hi or amount <= 0:
        return
    glow = np.exp(-(((x[lo:hi] - center) / radius) ** 2)) * amount
    np.maximum(target[lo:hi], glow, out=target[lo:hi])


def paint_glow(
    pixels: FloatArray,
    x: FloatArray,
    center: float,
    radius: float,
    color: FloatArray,
    amount: float = 1.0,
) -> None:
    """Max-blend a soft glow of one color into an (n, 3) frame, touching only nearby pixels."""
    lo = max(0, int(center - 3 * radius))
    hi = min(len(pixels), int(center + 3 * radius) + 2)
    if lo >= hi or amount <= 0:
        return
    glow = np.exp(-(((x[lo:hi] - center) / radius) ** 2)) * amount
    np.maximum(pixels[lo:hi], color * glow[:, None], out=pixels[lo:hi])


def heat_colors(heat: FloatArray) -> FloatArray:
    """Black through red, orange and yellow to white as heat goes from 0 to 1."""
    h = np.clip(np.asarray(heat, dtype=float), 0, 1)[..., None] * 3
    return np.clip(h - np.array((0.0, 1.0, 2.0)), 0, 1) * 255


def volume_of(data: AudioAnalysisSource) -> float:
    volume = data.volume()
    # None until the volume filter has seen its first frame
    return float(volume) if volume is not None else 0.0


class BeatLatch:
    """Holds a hit seen on the audio thread until the next frame takes it.

    The audio callback and render run under the effect lock, one at a time, so
    plain attributes are enough.
    """

    def __init__(self) -> None:
        self.pending = False
        self.last = -TRIGGER_COOLDOWN

    def listen(self, data: AudioAnalysisSource, trigger: Trigger) -> None:
        hit = data.volume_beat_now() if trigger == "Beat" else data.onset()
        if hit:
            self.pending = True

    def take(self, now: float) -> bool:
        """True once per hit, skipping hits that follow the last one too closely."""
        hit = self.pending and now - self.last >= TRIGGER_COOLDOWN
        self.pending = False
        if hit:
            self.last = now
        return hit


class TempoTracker:
    """Follows the song's tempo through the bar oscillator: beats counted so far and their rate.

    The bar oscillator climbs from 0 to 4 over each bar while the tempo is locked,
    and stands still otherwise, so the count pauses when the music does.
    """

    def __init__(self) -> None:
        self.beats = 0.0
        self.rate = DEFAULT_BEAT_RATE
        self._bar: float | None = None

    def listen(self, data: AudioAnalysisSource) -> None:
        bar = float(data.bar_oscillator())
        if self._bar is not None:
            step = (bar - self._bar) % 4
            # A jump of half a beat or more is a resync, not the music moving on
            if step < 0.5:
                self.beats += step
                if step > 0:
                    self.rate += (step / AUDIO_STEP - self.rate) * 0.05
        self._bar = bar

    def beat_length(self) -> float:
        """Seconds per beat, kept within a believable range of tempos."""
        return 1 / min(max(self.rate, MIN_BEAT_RATE), MAX_BEAT_RATE)


def note_color(midi: float) -> FloatArray:
    """The color of a note on a chromatic wheel: C is red, each semitone a twelfth further."""
    red, green, blue = colorsys.hsv_to_rgb((midi % 12) / 12, 1.0, 1.0)
    return np.array((red, green, blue)) * 255


def heard_note(data: AudioAnalysisSource) -> float | None:
    """The MIDI note being played, or None when nothing clear enough is heard."""
    if volume_of(data) < NOTE_GATE:
        return None
    note = data.pitch()
    return float(note) if note else None


class PeakTracker:
    """Scales signals against their own recent peaks, so quiet songs still fill the range."""

    def __init__(self, size: int, fade: float = 0.3, floor: float = 0.05) -> None:
        self.fade = fade
        self.floor = floor
        self.peak: FloatArray = np.full(size, floor)

    def update(self, values: FloatArray, dt: float = AUDIO_STEP) -> FloatArray:
        faded = np.maximum(self.peak * float(np.exp(-dt * self.fade)), self.floor)
        self.peak = np.maximum(values, faded)
        return values / self.peak


KICK, SNARE, HAT = 0, 1, 2


class HitClassifier:
    """Guesses which drum a percussive hit was from the band that jumped the most."""

    def __init__(self) -> None:
        self._bands = PeakTracker(3, fade=0.5)
        self._previous: FloatArray = np.zeros(3)

    def listen(self, data: AudioAnalysisSource) -> int | None:
        """The drum hit this frame (KICK, SNARE or HAT), or None if there was no hit."""
        bands = np.array(
            (data.lows_power(), data.mids_power(), data.high_power()), dtype=float
        )
        level = self._bands.update(bands)
        # A drum shows as a band that is both loud for this song and rising right now
        score = level + (level - self._previous)
        self._previous = level
        if data.volume_beat_now():
            return KICK
        if data.onset():
            return int(np.argmax(score))
        return None
