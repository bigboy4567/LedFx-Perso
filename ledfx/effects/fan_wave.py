from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, fan_layout, stack_height
from ledfx.effects.utils.custom import FloatArray


class FanWave(CorsairEffect, GradientEffect):
    NAME = "Fan Wave"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        waves: CoercedFloat = Field(
            1.5, description="Waves up the stack of fans at once", ge=0.5, le=5.0
        )
        speed: CoercedFloat = Field(
            0.5, description="Waves rising past per beat of the song", ge=0.1, le=2.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._height: FloatArray = stack_height(fan_layout(pixel_count))
        self._phase = 0.0

    @override
    def render(self) -> None:
        self._phase += self.song_moved() * self.config.speed + self.step() * 0.1
        # Bands of color rise up through the fans, brighter as the music gets louder
        place = self._height * self.config.waves - self._phase
        crest = (0.5 + 0.5 * np.cos(2 * np.pi * place)) ** 2
        colors = self.get_gradient_color_vectorized1d(place % 1 * 0.999)
        level = 0.05 + 0.95 * crest * (0.4 + 0.6 * self.loudness)
        self.pixels = colors * level[:, None]
