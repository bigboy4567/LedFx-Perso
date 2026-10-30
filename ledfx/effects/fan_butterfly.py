from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, fan_layout, fan_xy


class FanButterfly(CorsairEffect, GradientEffect):
    NAME = "Fan Butterfly"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        flaps_per_beat: CoercedFloat = Field(
            0.5, description="Wing beats per beat of the song", ge=0.1, le=2.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        fans = fan_layout(pixel_count)
        x, y = fan_xy(fans)
        # Mirrored left and right, like a butterfly's wings
        self._side = np.abs(x)
        self._y = y
        self._fan = fans.fan
        self._flap = 0.0

    @override
    def render(self) -> None:
        self._flap += (
            self.song_moved() * self.config.flaps_per_beat + self.step() * 0.05
        )
        opening = 0.5 + 0.5 * np.sin(2 * np.pi * self._flap)
        # The wings open from the middle line outward, their pattern sliding up and down
        wings = np.clip((opening * 1.2 - self._side) * 4 + 1, 0, 1)
        pattern = 0.5 + 0.5 * np.sin(
            2 * np.pi * (self._side * 1.5 + self._y * 0.5 - self._flap)
        )
        colors = self.get_gradient_color_vectorized1d(
            (pattern * 0.8 + self._fan * 0.07) % 1
        )
        level = (0.1 + 0.9 * wings * (0.4 + 0.6 * pattern)) * (
            0.5 + 0.5 * self.loudness
        )
        self.pixels = colors * level[:, None]
