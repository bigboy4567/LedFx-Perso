from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, mat_layout
from ledfx.effects.utils.custom import FloatArray


class MatWave(CorsairEffect, GradientEffect):
    NAME = "Mat Wave"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        waves: CoercedFloat = Field(
            2.0, description="Waves round the pad's edge at once", ge=0.5, le=6.0
        )
        speed: CoercedFloat = Field(
            0.5, description="Waves passing by per beat of the song", ge=0.1, le=2.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        mat = mat_layout(pixel_count)
        self._along: FloatArray = mat.along
        self._mouse = mat.mouse
        self._phase = 0.0

    @override
    def render(self) -> None:
        self._phase += self.song_moved() * self.config.speed + self.step() * 0.1
        # Waves run round the U from the left tip to the right, brighter as the music gets louder
        place = self._along * self.config.waves - self._phase
        crest = (0.5 + 0.5 * np.cos(2 * np.pi * place)) ** 2
        colors = self.get_gradient_color_vectorized1d(self._along * 0.999)
        level = 0.04 + 0.96 * crest * (0.4 + 0.6 * self.loudness)
        # The mouse bobs with the wave passing beneath it
        under = 0.5 + 0.5 * np.cos(2 * np.pi * (0.5 * self.config.waves - self._phase))
        level = np.where(self._mouse, 0.1 + 0.9 * under**2, level)
        self.pixels = colors * level[:, None]
