import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import (
    CorsairEffect,
    aurora_colors,
    fan_layout,
    fan_xy,
    stack_height,
)
from ledfx.effects.utils.custom import FloatArray


class FanAurora(CorsairEffect):
    NAME = "Fan Aurora"

    class Config(CorsairEffect.Config):
        speed: CoercedFloat = Field(
            0.4, description="How quickly the curtains drift", ge=0.1, le=2.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        fans = fan_layout(pixel_count)
        x, _ = fan_xy(fans)
        self._across: FloatArray = x * 0.42
        self._up: FloatArray = stack_height(fans) * fans.count
        self._time = 0.0

    @override
    def render(self) -> None:
        # The music stirs the curtains and makes them glow
        self._time += self.step() * self.config.speed * (1 + self.loudness)
        t = self._time
        across, up = self._across, self._up
        curtain = 0.5 + 0.5 * np.sin(across * 5 + t + 2 * np.sin(up * 2 + t * 0.7))
        shade = 0.5 + 0.5 * np.sin(up * 1.3 - t * 0.5 + across * 2)
        level = curtain**2 * (0.3 + 0.7 * self.loudness)
        self.pixels = aurora_colors(shade) * np.maximum(level, 0.04)[:, None]
