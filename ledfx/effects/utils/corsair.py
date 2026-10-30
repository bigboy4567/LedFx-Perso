"""Geometry of the Corsair gear for the Corsair effects, with a fallback for any other strip.

Each layout takes the pixel count of the virtual. With the exact count of the
device, as the LedFx to iCUE bridge streams it, the real positions are used;
with any other count the effect still runs, on a simple stand-in layout.
"""

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike
from typing_extensions import override

from ledfx.effects import Effect
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.utils.corsair_layouts import (
    AIO_FAN_LEDS,
    AIO_LEDS,
    AIO_PUMP_LEDS,
    FAN_COUNT,
    FAN_HUB,
    FAN_LEDS,
    FAN_PLACES,
    FAN_RIM,
    KEYBOARD_LEDS,
    KEYBOARD_XY,
    KEYBOARD_ZONES,
    MAT_ALONG,
    MAT_LEDS,
    MOUSE_LEDS,
    RAM_LEDS,
    RAM_STICK_LEDS,
    RAM_STICKS,
)
from ledfx.effects.utils.custom import (
    BeatLatch,
    BoolArray,
    FloatArray,
    IntArray,
    PeakTracker,
    TempoTracker,
    frame_step,
    heard_note,
    segment_widths,
    volume_of,
)

# The Corsair effects list themselves here in the effect picker
CORSAIR_CATEGORY = "Corsair"
# The K95 is about three times as wide as it is deep
KEYBOARD_DEPTH = 0.31
# Parts of the keyboard
KEY, BAR, LOGO, G_KEY = range(4)
ZONE_CODES = {"KEY": KEY, "BAR": BAR, "LOGO": LOGO, "G_KEY": G_KEY}

__all__ = ["FAN_HUB", "FAN_RIM"]


def _segments(pixel_count: int, count: int) -> tuple[IntArray, FloatArray]:
    """Which of count near-equal segments each pixel is in, and where in it, 0 to 1."""
    widths = segment_widths(pixel_count, count)
    segment = np.repeat(np.arange(widths.size), widths)
    starts = np.cumsum(widths) - widths
    within = (np.arange(pixel_count) - starts[segment]) / np.maximum(
        widths[segment] - 1, 1
    )
    return segment, within


@dataclass(frozen=True)
class Keyboard:
    """x from left to right and y from top to bottom, both 0 to 1, and the zone of each LED."""

    x: FloatArray
    y: FloatArray
    zone: IntArray


def keyboard_layout(pixel_count: int) -> Keyboard:
    if pixel_count == KEYBOARD_LEDS:
        xy = np.array(KEYBOARD_XY, dtype=float)
        zones = np.array([ZONE_CODES[zone] for zone in KEYBOARD_ZONES])
        return Keyboard(xy[:, 0], xy[:, 1], zones)
    # Any other strip: one row of keys
    x = np.arange(pixel_count) / max(pixel_count - 1, 1)
    return Keyboard(x, np.full(pixel_count, 0.5), np.full(pixel_count, KEY))


@dataclass(frozen=True)
class Fans:
    """For each LED: its fan (0 at the top), its ring (0 rim, 1 hub), and its angle
    round the ring, 0 to 1 clockwise from the top."""

    fan: IntArray
    ring: IntArray
    angle: FloatArray
    count: int


def fan_layout(pixel_count: int) -> Fans:
    if pixel_count == FAN_LEDS:
        places = np.array(FAN_PLACES, dtype=float)
        return Fans(
            places[:, 0].astype(int), places[:, 1].astype(int), places[:, 2], FAN_COUNT
        )
    # Any other strip: rings one after the other, a rim and no hub
    count = max(1, min(FAN_COUNT, pixel_count))
    fan, angle = _segments(pixel_count, count)
    return Fans(fan, np.full(pixel_count, FAN_RIM), angle, count)


@dataclass(frozen=True)
class Aio:
    """The pump's ring and the radiator fans: for each LED, whether it is on the pump,
    its radiator fan (-1 on the pump) and its angle round its ring, 0 to 1."""

    pump: BoolArray
    fan: IntArray
    angle: FloatArray


def aio_layout(pixel_count: int) -> Aio:
    index = np.arange(pixel_count)
    if pixel_count == AIO_LEDS:
        pump = index < AIO_PUMP_LEDS
        fan = np.where(pump, -1, (index - AIO_PUMP_LEDS) // AIO_FAN_LEDS)
        angle = np.where(
            pump,
            index / AIO_PUMP_LEDS,
            (index - AIO_PUMP_LEDS) % AIO_FAN_LEDS / AIO_FAN_LEDS,
        )
        return Aio(pump, fan, angle)
    # Any other strip: the whole strip is the pump's ring
    return Aio(
        np.ones(pixel_count, dtype=bool),
        np.full(pixel_count, -1),
        index / max(pixel_count, 1),
    )


@dataclass(frozen=True)
class Ram:
    """For each LED: its stick (0 on the left) and its height, 0 at the bottom, 1 at the top."""

    stick: IntArray
    height: FloatArray
    sticks: int


def ram_layout(pixel_count: int) -> Ram:
    index = np.arange(pixel_count)
    if pixel_count == RAM_LEDS:
        return Ram(
            index // RAM_STICK_LEDS,
            1 - index % RAM_STICK_LEDS / (RAM_STICK_LEDS - 1),
            RAM_STICKS,
        )
    count = max(1, min(RAM_STICKS, pixel_count))
    stick, within = _segments(pixel_count, count)
    return Ram(stick, 1 - within, count)


@dataclass(frozen=True)
class Mat:
    """For each LED of the pad, how far along its U it sits (0 top of the left side,
    1 top of the right side), and which LED is the mouse."""

    along: FloatArray
    mouse: BoolArray


def mat_layout(pixel_count: int) -> Mat:
    if pixel_count == MAT_LEDS + MOUSE_LEDS:
        along = np.concatenate(
            (np.array(MAT_ALONG, dtype=float), np.full(MOUSE_LEDS, 0.5))
        )
        mouse = np.arange(pixel_count) >= MAT_LEDS
        return Mat(along, mouse)
    # Any other strip: the whole strip is the pad's edge, with no mouse
    return Mat(
        np.arange(pixel_count) / max(pixel_count - 1, 1),
        np.zeros(pixel_count, dtype=bool),
    )


# Bands each device answers to: the fans and the pump the bass, the RAM the mids,
# the keyboard and the pad the treble
LOWS, MIDS, HIGHS = range(3)


@dataclass(frozen=True)
class Rig:
    """The whole setup as one path: for each LED, which device along the way it is
    on, how far through that device the path has come (0 to 1), and the band the
    device answers to."""

    stage: IntArray
    local: FloatArray
    band: IntArray
    stages: int


def _rim_height(fans: Fans) -> FloatArray:
    # Height down the stack of fans: a rim LED's angle tells how high on its fan it sits
    radius = np.where(fans.ring == FAN_RIM, 0.42, 0.15)
    return (fans.fan + 0.5 - radius * np.cos(2 * np.pi * fans.angle)) / max(
        fans.count, 1
    )


def _device_path(kind: str, pixel_count: int) -> tuple[FloatArray, int]:
    """How far along each LED of one device sits, 0 to 1, and the band it answers to."""
    if kind == "keyboard":
        return keyboard_layout(pixel_count).x, HIGHS
    if kind == "mat":
        return mat_layout(pixel_count).along, HIGHS
    if kind == "fans":
        return _rim_height(fan_layout(pixel_count)), LOWS
    if kind == "aio":
        aio = aio_layout(pixel_count)
        return np.where(aio.pump, aio.angle, 1.0), LOWS
    ram = ram_layout(pixel_count)
    return (ram.stick + ram.height) / max(ram.sticks, 1), MIDS


# The device groups of the setup, in the order their segments run
RIGS = {
    KEYBOARD_LEDS + MAT_LEDS + MOUSE_LEDS + FAN_LEDS + AIO_LEDS + RAM_LEDS: (
        ("keyboard", KEYBOARD_LEDS),
        ("mat", MAT_LEDS + MOUSE_LEDS),
        ("fans", FAN_LEDS),
        ("aio", AIO_LEDS),
        ("ram", RAM_LEDS),
    ),
    FAN_LEDS + AIO_LEDS + RAM_LEDS: (
        ("fans", FAN_LEDS),
        ("aio", AIO_LEDS),
        ("ram", RAM_LEDS),
    ),
}


def rig_layout(pixel_count: int) -> Rig:
    devices = RIGS.get(pixel_count)
    if devices is None:
        # Any other strip: one device, from one end to the other
        local = np.arange(pixel_count) / max(pixel_count - 1, 1)
        return Rig(
            np.zeros(pixel_count, dtype=int), local, np.full(pixel_count, MIDS), 1
        )
    stages: list[IntArray] = []
    locals_: list[FloatArray] = []
    bands: list[IntArray] = []
    for stage, (kind, count) in enumerate(devices):
        local, band = _device_path(kind, count)
        stages.append(np.full(count, stage))
        locals_.append(local)
        bands.append(np.full(count, band))
    return Rig(
        np.concatenate(stages),
        np.concatenate(locals_),
        np.concatenate(bands),
        len(devices),
    )


def ring_gap(a: FloatArray | float, b: FloatArray | float) -> FloatArray:
    """How far apart two places round a ring are, 0 to 0.5 of a turn."""
    return np.abs((np.asarray(a, dtype=float) - b + 0.5) % 1 - 0.5)


def fan_xy(fans: Fans) -> tuple[FloatArray, FloatArray]:
    """Each LED's place on the face of its own fan: x to the right and y up, the rim at 1."""
    radius = np.where(fans.ring == FAN_RIM, 1.0, 0.4)
    turn = 2 * np.pi * fans.angle
    return radius * np.sin(turn), radius * np.cos(turn)


def stack_height(fans: Fans) -> FloatArray:
    """Each LED's height up the stack of fans, 0 at the bottom of the lowest, 1 at the top."""
    return 1 - _rim_height(fans)


def keyboard_rows(board: Keyboard) -> tuple[IntArray, int]:
    """Which row of keys each LED is in, 0 for the light bar at the top, and how many rows."""
    levels = np.unique(np.round(board.y, 1))
    rows = np.searchsorted(levels, np.round(board.y, 1))
    return rows.astype(int), int(levels.size)


def mat_height(mat: Mat) -> FloatArray:
    """How far up the sides of the U each LED is: 0 in the middle of the bottom, 1 at the tips."""
    return np.abs(mat.along - 0.5) * 2


@Effect.no_registration
class CorsairEffect(AudioReactiveEffect):
    """What every Corsair effect listens to: the three bands against their own recent
    peaks, the loudness, the note heard, the song's tempo, its beats and its hits."""

    CATEGORY = CORSAIR_CATEGORY

    def __init__(self, ledfx: object, config: object) -> None:
        self.levels: FloatArray = np.zeros(3)
        self.loudness = 0.0
        self.heard: float | None = None
        self.song = TempoTracker()
        self._song_seen = 0.0
        self._band_peaks = PeakTracker(3)
        self._beats = BeatLatch()
        self._hits = BeatLatch()
        self._rng = np.random.default_rng()
        super().__init__(ledfx, config)

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        bands = np.array(
            (data.lows_power(), data.mids_power(), data.high_power()), dtype=float
        )
        self.levels = np.clip(self._band_peaks.update(bands), 0, 1)
        self.loudness = min(1.0, volume_of(data) * 2)
        self.heard = heard_note(data)
        self.song.listen(data)
        self._beats.listen(data, "Beat")
        self._hits.listen(data, "Percussion")

    def beat(self) -> bool:
        """True once for each beat of the bass."""
        return self._beats.take(self.now)

    def hit(self) -> bool:
        """True once for each percussive hit."""
        return self._hits.take(self.now)

    def song_moved(self) -> float:
        """Beats of the song since the last call; call it once a frame."""
        moved = self.song.beats - self._song_seen
        self._song_seen = self.song.beats
        return moved

    def step(self) -> float:
        """Seconds since the last frame, never more than a stalled frame's worth."""
        return frame_step(self.passed)


def pump_turn(aio: Aio, top_led: int) -> FloatArray:
    """Each LED's place round the pump's ring, 0 to 1 clockwise from the LED at the top.

    iCUE does not say which way up the pump is mounted, so the effects that care
    let the user say which LED of the ring is at the top.
    """
    return (aio.angle - top_led / AIO_PUMP_LEDS) % 1


# An aurora runs from green through teal to violet
AURORA = np.array(((0.0, 255.0, 110.0), (0.0, 170.0, 255.0), (170.0, 50.0, 255.0)))


def aurora_colors(shade: FloatArray) -> FloatArray:
    """The aurora's color for each shade, 0 green to 1 violet."""
    scaled = np.clip(shade, 0, 1) * (len(AURORA) - 1)
    low = np.minimum(scaled.astype(int), len(AURORA) - 2)
    mix = (scaled - low)[:, None]
    return AURORA[low] * (1 - mix) + AURORA[low + 1] * mix


def breath(phase: ArrayLike) -> FloatArray:
    """How full a breath is at this point of it, 0 empty to 1 full, one breath per unit."""
    return 0.5 - 0.5 * np.cos(2 * np.pi * np.asarray(phase, dtype=float))
