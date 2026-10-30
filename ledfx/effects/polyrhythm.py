from typing import Literal

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.utils.custom import (
    CUSTOM_CATEGORY,
    FloatArray,
    IntArray,
    TempoTracker,
    hue_colors,
    segment_widths,
)

# Pulses per bar in each lane
RHYTHMS: dict[str, tuple[int, ...]] = {
    "3 against 2": (2, 3),
    "4 against 3": (3, 4),
    "3, 4 and 5": (3, 4, 5),
    "2 to 6": (2, 3, 4, 5, 6),
}
BEATS_PER_BAR = 4
# A lane rests at this brightness between its pulses
LANE_LEVEL = 0.08

Rhythm = Literal["3 against 2", "4 against 3", "3, 4 and 5", "2 to 6"]


class Polyrhythm(AudioReactiveEffect):
    NAME = "Polyrhythm"
    CATEGORY = CUSTOM_CATEGORY

    class Config(AudioReactiveEffect.Config):
        rhythm: Rhythm = Field(
            "3, 4 and 5",
            description="Pulses per bar in each lane; all lanes meet at the start of every bar",
        )
        cursor: bool = Field(
            True, description="Show a dot running across each lane between its pulses"
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._layout(pixel_count)
        self._tempo = TempoTracker()

    def _layout(self, pixel_count: int) -> None:
        pulses = RHYTHMS[self.config.rhythm]
        widths = segment_widths(pixel_count, len(pulses))
        self._lane: IntArray = np.repeat(np.arange(widths.size), widths)
        starts = np.cumsum(widths) - widths
        self._within: FloatArray = (
            np.arange(pixel_count) - starts[self._lane] + 0.5
        ) / widths[self._lane]
        self._pulses: FloatArray = np.array(pulses[: widths.size], dtype=float)
        self._colors: FloatArray = hue_colors(np.arange(widths.size) / len(pulses))
        self._edge: FloatArray = np.maximum(1.5 / widths[self._lane], 0.03)

    @override
    def config_updated(self, config: object) -> None:
        pixels = getattr(self, "pixels", None)
        if pixels is not None and hasattr(self, "_lane"):
            self._layout(len(pixels))

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._tempo.listen(data)

    @override
    def render(self) -> None:
        bars = self._tempo.beats / BEATS_PER_BAR
        # Where each lane is between two of its pulses, 0 right on a pulse
        phase = (bars * self._pulses) % 1
        flash = (1 - phase) ** 4
        level = LANE_LEVEL + (1 - LANE_LEVEL) * flash
        pixels = (self._colors * level[:, None])[self._lane]
        if self.config.cursor:
            dot = np.exp(-(((self._within - phase[self._lane]) / self._edge) ** 2))
            pixels = pixels + (self._colors[self._lane] - pixels) * dot[:, None]
        # Every lane pulses together at the start of the bar
        together = (1 - bars % 1) ** 12
        pixels = pixels + (255 - pixels) * together * 0.6
        self.pixels = np.clip(pixels, 0, 255)
