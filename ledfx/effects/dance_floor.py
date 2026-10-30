from typing import Literal

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedInt
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.utils.custom import (
    CUSTOM_CATEGORY,
    BeatLatch,
    FloatArray,
    IntArray,
    Trigger,
    color_array,
    frame_step,
    segment_widths,
)

PALETTES: dict[str, tuple[str, ...]] = {
    "Disco": ("#FF0040", "#FFD000", "#00C8FF", "#00FF60", "#FF00C8", "#FF7000"),
    "Pastel": ("#FF9AC8", "#9AD8FF", "#C8FF9A", "#FFE29A", "#D2A8FF", "#9AFFE4"),
    "Neon": ("#FF00FF", "#00FFFF", "#39FF14", "#FF3131"),
}
# The floor runs through these patterns, one per bar of four beats
PATTERNS = ("checker", "random", "shift", "spotlight")
# A lit tile glows at this level and flashes up from it on the beat
TILE_LEVEL = 0.7

Palette = Literal["Disco", "Pastel", "Neon"]


class DanceFloor(AudioReactiveEffect):
    NAME = "Dance Floor"
    CATEGORY = CUSTOM_CATEGORY

    class Config(AudioReactiveEffect.Config):
        tiles: CoercedInt = Field(
            12, description="Floor tiles along the strip", ge=2, le=40
        )
        palette: Palette = Field("Disco", description="Colors of the tiles")
        trigger: Trigger = Field(
            "Beat",
            description="Change the floor on the bass or on every percussive hit",
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._layout(pixel_count)
        self._hits = 0
        self._flash = 0.0
        self._latch = BeatLatch()

    def _layout(self, pixel_count: int) -> None:
        widths = segment_widths(pixel_count, self.config.tiles)
        count = widths.size
        self._tile: IntArray = np.repeat(np.arange(count), widths)
        ends = np.cumsum(widths) - 1
        self._grout = np.zeros(pixel_count, dtype=bool)
        self._grout[ends[widths >= 4]] = True
        self._colors: FloatArray = self._palette()[
            np.arange(count) % len(self._palette())
        ]
        self._levels: FloatArray = np.full(count, TILE_LEVEL)

    def _palette(self) -> FloatArray:
        return np.array([color_array(c) for c in PALETTES[self.config.palette]])

    @override
    def config_updated(self, config: object) -> None:
        if not hasattr(self, "_rng"):
            self._rng = np.random.default_rng()
        pixels = getattr(self, "pixels", None)
        if pixels is not None and hasattr(self, "_colors"):
            self._layout(len(pixels))

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._latch.listen(data, self.config.trigger)

    def step(self) -> None:
        palette = self._palette()
        count = self._colors.shape[0]
        self._levels[:] = TILE_LEVEL
        match PATTERNS[self._hits // 4 % len(PATTERNS)]:
            case "checker":
                pair = palette[
                    [self._hits % len(palette), (self._hits + 2) % len(palette)]
                ]
                self._colors = pair[(np.arange(count) + self._hits) % 2]
            case "random":
                self._colors = palette[self._rng.integers(0, len(palette), count)]
            case "shift":
                self._colors = np.roll(self._colors, 1, axis=0)
            case "spotlight":
                self._levels[:] = 0.12
                self._levels[self._rng.integers(count)] = 1.0
        self._hits += 1
        self._flash = 1.0

    @override
    def render(self) -> None:
        self._flash *= float(np.exp(-frame_step(self.passed) * 5))
        if self._latch.take(self.now):
            self.step()

        levels = np.minimum(
            self._levels + 0.3 * self._flash * (self._levels > 0.5), 1.0
        )
        pixels = (self._colors * levels[:, None])[self._tile]
        pixels[self._grout] = 0
        self.pixels = pixels
