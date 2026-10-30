import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, mat_layout
from ledfx.effects.utils.custom import color_array

GREEN = color_array("#00FF40")
YELLOW = color_array("#FFD000")
RED = color_array("#FF1000")


class MouseMeter(CorsairEffect):
    NAME = "Mouse Meter"

    class Config(CorsairEffect.Config):
        sensitivity: CoercedFloat = Field(
            1.0,
            description="How readily the volume turns the mouse red",
            ge=0.3,
            le=3.0,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._mouse = mat_layout(pixel_count).mouse
        self.level = 0.0

    @override
    def render(self) -> None:
        dt = self.step()
        target = min(1.0, self.loudness * self.config.sensitivity)
        self.level += (target - self.level) * min(1.0, dt * 10)
        level = self.level
        # Green when it is quiet, yellow, then red when it is loud, brighter as it gets louder
        low, high = min(1.0, level / 0.6), max(0.0, (level - 0.6) / 0.4)
        color = GREEN + (YELLOW - GREEN) * low + (RED - YELLOW) * high
        mouse = color * (0.2 + 0.8 * level)
        # The pad keeps a faint glow of the same color
        pad = color * 0.06
        self.pixels = np.where(self._mouse[:, None], mouse, pad)
