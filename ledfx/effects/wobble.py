from typing import Literal

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.utils.custom import (
    CUSTOM_CATEGORY,
    FloatArray,
    PeakTracker,
    TempoTracker,
    color_array,
)

# Wobbles per beat for each rate
RATES = {
    "Quarter notes": 1,
    "Eighth notes": 2,
    "Eighth triplets": 3,
    "Sixteenth notes": 4,
}
# The least the filter ever opens, as a share of the strip
CLOSED = 0.1
# Width of the soft edge of the opening, as a share of the strip
EDGE = 0.08
RESONANCE = np.array((255.0, 255.0, 255.0))

Rate = Literal["Quarter notes", "Eighth notes", "Eighth triplets", "Sixteenth notes"]


class Wobble(AudioReactiveEffect):
    NAME = "Wobble"
    CATEGORY = CUSTOM_CATEGORY

    class Config(AudioReactiveEffect.Config):
        color_closed: Color = Field("#6A00FF", description="Color of the closed filter")
        color_open: Color = Field("#00F0FF", description="Color of the open filter")
        rate: Rate = Field(
            "Eighth notes",
            description="How fast the wobble goes, in step with the song",
        )
        depth: CoercedFloat = Field(
            1.0, description="How far the bass opens the wobble", ge=0.1, le=1.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._distance: FloatArray = np.abs(
            np.arange(pixel_count) - (pixel_count - 1) / 2
        ) / max(pixel_count / 2, 0.5)
        self._bass = 0.0
        self._peaks = PeakTracker(1)
        self._tempo = TempoTracker()

    @override
    def config_updated(self, config: object) -> None:
        self._closed = color_array(self.config.color_closed)
        self._open = color_array(self.config.color_open)

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._tempo.listen(data)
        level = self._peaks.update(np.array((float(data.lows_power()),)))
        self._bass = float(np.clip(level[0], 0, 1))

    def opening(self) -> float:
        """How far the wobble filter is open, 0 to 1."""
        phase = self._tempo.beats * RATES[self.config.rate]
        lfo = 0.5 - 0.5 * float(np.cos(2 * np.pi * phase))
        return lfo * self.config.depth * self._bass

    @override
    def render(self) -> None:
        opened = self.opening()
        width = CLOSED + (1 - CLOSED) * opened
        inside = np.clip((width - self._distance) / EDGE, 0, 1)
        color = self._closed + (self._open - self._closed) * opened
        # The filter's resonance rings at the edge of the opening
        edge = np.exp(-(((self._distance - width) / (EDGE / 2)) ** 2)) * 0.6 * opened
        pixels = color * (inside * (0.35 + 0.65 * opened))[:, None]
        self.pixels = np.clip(pixels + (RESONANCE - pixels) * edge[:, None], 0, 255)
