import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, fan_layout, stack_height
from ledfx.effects.utils.custom import FloatArray, color_array

GREEN = color_array("#00FF40")
YELLOW = color_array("#FFD000")
RED = color_array("#FF1000")
WHITE = np.array((255.0, 255.0, 255.0))
UNLIT = 0.04
PEAK_FALL = 0.35


class FanStack(CorsairEffect):
    NAME = "Fan Stack"

    class Config(CorsairEffect.Config):
        sensitivity: CoercedFloat = Field(
            1.0,
            description="How high the music fills the stack of fans",
            ge=0.3,
            le=3.0,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        # The three fans together are one tall meter, filling from the bottom
        self._height: FloatArray = stack_height(fan_layout(pixel_count))
        self.level = 0.0
        self._peak = 0.0

    @override
    def render(self) -> None:
        dt = self.step()
        target = min(1.0, self.loudness * self.config.sensitivity)
        self.level += (target - self.level) * min(1.0, dt * 12)
        self._peak = max(self.level, self._peak - PEAK_FALL * dt)

        height = self._height
        low = np.clip(height / 0.6, 0, 1)[:, None]
        high = np.clip((height - 0.6) / 0.4, 0, 1)[:, None]
        colors = GREEN + (YELLOW - GREEN) * low + (RED - YELLOW) * high
        lit = np.where(height <= self.level + 0.02, 1.0, UNLIT)
        pixels = colors * lit[:, None]
        peak = np.abs(height - self._peak) < 0.03
        self.pixels = np.where(peak[:, None] & (self._peak > 0.05), WHITE, pixels)
