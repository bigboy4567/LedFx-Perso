from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, ram_layout
from ledfx.effects.utils.custom import FloatArray, IntArray


class RamWaterfall(CorsairEffect, GradientEffect):
    NAME = "RAM Waterfall"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        gain: CoercedFloat = Field(
            1.5, description="How brightly the music lights the bands", ge=0.5, le=5.0
        )
        rows_per_second: CoercedFloat = Field(
            8.0,
            description="How quickly the music flows down the sticks",
            ge=2.0,
            le=30.0,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        ram = ram_layout(pixel_count)
        self._ram = ram
        # Rows counted from the top of the sticks
        heights = np.unique(ram.height)[::-1]
        self._row: IntArray = np.searchsorted(-heights, -ram.height)
        # What each row of each stick showed, the newest at the top
        self._history: FloatArray = np.zeros((heights.size, ram.sticks))
        self._bands: FloatArray = np.zeros(ram.sticks)
        self._due = 0.0

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        super().audio_data_updated(data)
        bands = self.melbank(filtered=True, size=self._bands.size)
        self._bands = np.clip(np.asarray(bands, dtype=float) * self.config.gain, 0, 1)

    @override
    def render(self) -> None:
        self._due += self.step() * self.config.rows_per_second
        history = self._history
        # Each stick is a band, the bass on the left; what was heard flows down the sticks
        steps = min(int(self._due), history.shape[0])
        self._due -= int(self._due)
        if steps:
            history[steps:] = history[:-steps].copy()
            history[:steps] = self._bands
        history[0] = self._bands
        value = history[self._row, self._ram.stick]
        colors = self.get_gradient_color_vectorized1d(value * 0.999)
        self.pixels = colors * np.maximum(value, 0.02)[:, None]
