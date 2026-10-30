from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, fan_layout, fan_xy, stack_height
from ledfx.effects.utils.custom import FloatArray


class FanPlasma(CorsairEffect, GradientEffect):
    NAME = "Fan Plasma"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        speed: CoercedFloat = Field(
            0.5,
            description="How quickly the plasma churns when the music is quiet",
            ge=0.1,
            le=3.0,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        fans = fan_layout(pixel_count)
        x, _ = fan_xy(fans)
        # Across each fan and up the stack, both in fan widths
        self._across: FloatArray = x * 0.42
        self._up: FloatArray = stack_height(fans) * fans.count
        self._time = 0.0

    @override
    def render(self) -> None:
        # The music speeds the plasma up, and the bass makes it glow brighter
        self._time += self.step() * self.config.speed * (1 + 3 * self.loudness)
        t = self._time
        x, y = self._across, self._up
        field = (
            np.sin(x * 4 + t)
            + np.sin(y * 2.5 - t * 1.3)
            + np.sin((x + y) * 2 + t * 0.7)
            + np.sin(np.hypot(x, y - 1.5) * 3 - t * 1.7)
        )
        colors = self.get_gradient_color_vectorized1d((field + 4) / 8 * 0.999)
        self.pixels = colors * (0.35 + 0.65 * self.levels[0])
