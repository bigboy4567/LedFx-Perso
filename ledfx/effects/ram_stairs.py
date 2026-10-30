from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, ram_layout
from ledfx.effects.utils.custom import FloatArray

UNLIT = 0.03


class RamStairs(CorsairEffect, GradientEffect):
    NAME = "RAM Stairs"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        response: CoercedFloat = Field(
            8.0,
            description="How quickly the steps slide to their new heights",
            ge=2.0,
            le=30.0,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._ram = ram_layout(pixel_count)
        self.climbing = True
        self.steps: FloatArray = np.zeros(self._ram.sticks)

    @override
    def render(self) -> None:
        ram = self._ram
        # Each beat turns the stairs round, climbing to the right, then to the left
        if self.beat():
            self.climbing = not self.climbing
        rise = (np.arange(ram.sticks) + 1) / ram.sticks
        target = rise if self.climbing else rise[::-1]
        # The louder the music, the taller the flight of stairs
        target = target * (0.4 + 0.6 * self.loudness)
        self.steps += (target - self.steps) * min(
            1.0, self.step() * self.config.response
        )
        lit = ram.height <= self.steps[ram.stick] + 1e-9
        colors = self.get_gradient_color_vectorized1d(
            ram.stick / max(ram.sticks - 1, 1) * 0.999
        )
        self.pixels = colors * np.where(lit, 1.0, UNLIT)[:, None]
