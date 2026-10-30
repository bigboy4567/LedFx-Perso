from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, mat_height, mat_layout
from ledfx.effects.utils.custom import FloatArray, IntArray

BANDS = 8
UNLIT = 0.03


class MatSpectrum(CorsairEffect, GradientEffect):
    NAME = "Mat Spectrum"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        gain: CoercedFloat = Field(
            1.5, description="How brightly the music lights the bands", ge=0.5, le=5.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        mat = mat_layout(pixel_count)
        # Up both sides of the U, the bass at the bottom, the treble at the tips
        self._band: IntArray = np.minimum(
            (mat_height(mat) * BANDS).astype(int), BANDS - 1
        )
        self._mouse = mat.mouse
        self._bands: FloatArray = np.zeros(BANDS)
        self._shown: FloatArray = np.zeros(BANDS)

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        super().audio_data_updated(data)
        bands = self.melbank(filtered=True, size=BANDS)
        self._bands = np.clip(np.asarray(bands, dtype=float) * self.config.gain, 0, 1)

    @override
    def render(self) -> None:
        self._shown += (self._bands - self._shown) * min(1.0, self.step() * 15)
        # The mouse, at the bottom of the U, throbs with the deepest band
        band = np.where(self._mouse, 0, self._band)
        colors = self.get_gradient_color_vectorized1d(band / (BANDS - 1) * 0.999)
        self.pixels = colors * (UNLIT + (1 - UNLIT) * self._shown[band])[:, None]
