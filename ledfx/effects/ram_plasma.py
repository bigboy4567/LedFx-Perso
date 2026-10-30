from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, ram_layout


class RamPlasma(CorsairEffect, GradientEffect):
    NAME = "RAM Plasma"
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
        self._ram = ram_layout(pixel_count)
        self._time = 0.0

    @override
    def render(self) -> None:
        # The music speeds the plasma up, and the bass makes it glow brighter
        self._time += self.step() * self.config.speed * (1 + 3 * self.loudness)
        ram = self._ram
        t = self._time
        x = ram.stick / max(ram.sticks - 1, 1)
        y = ram.height
        field = (
            np.sin(x * 5 + t)
            + np.sin(y * 7 - t * 1.3)
            + np.sin((x + y) * 4 + t * 0.7)
            + np.sin(np.hypot(x - 0.5, y - 0.5) * 9 - t * 1.7)
        )
        colors = self.get_gradient_color_vectorized1d((field + 4) / 8 * 0.999)
        self.pixels = colors * (0.35 + 0.65 * self.levels[0])
