import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, CoercedInt
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.utils.custom import (
    CUSTOM_CATEGORY,
    FloatArray,
    TempoTracker,
    frame_step,
    hue_colors,
    volume_of,
)

# Color harmonies a palette is drawn from: hue steps from a random base hue
HARMONIES = (
    (0.0, 0.08, 0.16),  # analogous
    (0.0, 0.5, 0.04),  # complementary
    (0.0, 1 / 3, 2 / 3),  # triadic
    (0.0, 0.42, 0.58),  # split complementary
)
# Pure hues are softened a little toward white, the way a designer would pick them
SOFTEN = 0.15


class PaletteMorph(AudioReactiveEffect):
    NAME = "Palette Morph"
    CATEGORY = CUSTOM_CATEGORY

    class Config(AudioReactiveEffect.Config):
        bars: CoercedInt = Field(
            4,
            description="Bars of the song before the colors move to a new palette",
            ge=1,
            le=32,
        )
        fade: CoercedFloat = Field(
            3.0, description="Seconds the colors take to morph", ge=0.5, le=15.0
        )
        drift: CoercedFloat = Field(
            0.3, description="How fast the colors drift along the strip", ge=0.0, le=2.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._u: FloatArray = np.arange(pixel_count) / max(pixel_count, 1)
        self._phrase = -1
        self._from: FloatArray = self.new_palette()
        self._to: FloatArray = self._from
        self._progress = 1.0
        self._offset = 0.0
        self._energy = 0.5
        self._tempo = TempoTracker()

    @override
    def config_updated(self, config: object) -> None:
        if not hasattr(self, "_rng"):
            self._rng = np.random.default_rng()

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._tempo.listen(data)
        self._energy += (volume_of(data) - self._energy) * 0.02

    def new_palette(self) -> FloatArray:
        base = float(self._rng.random())
        steps = HARMONIES[int(self._rng.integers(len(HARMONIES)))]
        colors = hue_colors(np.array([base + step for step in steps]))
        return colors + (255 - colors) * SOFTEN

    def palette(self) -> FloatArray:
        eased = self._progress * self._progress * (3 - 2 * self._progress)
        return self._from + (self._to - self._from) * eased

    @override
    def render(self) -> None:
        dt = frame_step(self.passed)
        phrase = int(self._tempo.beats // (4 * self.config.bars))
        if phrase != self._phrase:
            if self._phrase >= 0:
                self._from = self.palette()
                self._to = self.new_palette()
                self._progress = 0.0
            self._phrase = phrase
        self._progress = min(1.0, self._progress + dt / self.config.fade)
        self._offset = (self._offset + dt * self.config.drift * 0.05) % 1

        # The three colors of the palette blend round the strip as a loop
        stops = self.palette()
        place = (self._u + self._offset) % 1 * 3
        first = place.astype(int) % 3
        blend = (place - np.floor(place))[:, None]
        colors = stops[first] + (stops[(first + 1) % 3] - stops[first]) * blend
        self.pixels = colors * (0.3 + 0.7 * min(1.0, self._energy * 2))
