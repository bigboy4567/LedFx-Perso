from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, fan_layout
from ledfx.effects.utils.custom import FloatArray, IntArray

# Frequency bands round each fan
BANDS_PER_FAN = 12


class FanSpectrum(CorsairEffect, GradientEffect):
    NAME = "Fan Spectrum"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        gain: CoercedFloat = Field(
            1.5, description="How brightly the music lights the bands", ge=0.5, le=5.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        fans = fan_layout(pixel_count)
        count = fans.count * BANDS_PER_FAN
        # The bass round the bottom fan, the treble round the top one, each clockwise from the top
        place = (fans.count - 1 - fans.fan + fans.angle) / fans.count
        self._band: IntArray = np.minimum((place * count).astype(int), count - 1)
        self._bands: FloatArray = np.zeros(count)
        self._shown: FloatArray = np.zeros(count)

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        super().audio_data_updated(data)
        bands = self.melbank(filtered=True, size=self._bands.size)
        self._bands = np.clip(np.asarray(bands, dtype=float) * self.config.gain, 0, 1)

    @override
    def render(self) -> None:
        self._shown += (self._bands - self._shown) * min(1.0, self.step() * 15)
        count = self._bands.size
        level = self._shown[self._band]
        colors = self.get_gradient_color_vectorized1d(
            self._band / max(count - 1, 1) * 0.999
        )
        self.pixels = colors * (0.03 + 0.97 * level)[:, None]
