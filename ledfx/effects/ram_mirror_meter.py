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


class RamMirrorMeter(CorsairEffect, GradientEffect):
    NAME = "RAM Mirror Meter"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        response: CoercedFloat = Field(
            12.0, description="How quickly the meters follow the music", ge=2.0, le=40.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._ram = ram_layout(pixel_count)
        self._shown: FloatArray = np.zeros(self._ram.sticks)

    @override
    def render(self) -> None:
        ram = self._ram
        # The outer sticks show the bass, the inner ones the mids and treble, mirrored left to right
        outer = np.abs(np.arange(ram.sticks) - (ram.sticks - 1) / 2) / max(
            (ram.sticks - 1) / 2, 0.5
        )
        lows, mids, highs = self.levels
        target = outer * lows + (1 - outer) * (mids + highs) / 2
        self._shown += (target - self._shown) * min(
            1.0, self.step() * self.config.response
        )
        # Each meter spreads from the middle of its stick to both ends
        reach = np.abs(ram.height - 0.5) * 2
        lit = reach <= self._shown[ram.stick] + 0.05
        colors = self.get_gradient_color_vectorized1d(np.clip(reach, 0, 0.999))
        self.pixels = colors * np.where(lit, 1.0, UNLIT)[:, None]
