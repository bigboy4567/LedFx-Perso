from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, ram_layout
from ledfx.effects.utils.custom import FloatArray

BEATS_PER_BAR = 4
UNLIT = 0.04


class RamBarCounter(CorsairEffect, GradientEffect):
    NAME = "RAM Bar Counter"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        decay: CoercedFloat = Field(
            3.0, description="How quickly a stick fades after its beat", ge=0.5, le=10.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._ram = ram_layout(pixel_count)
        self._glow: FloatArray = np.zeros(self._ram.sticks)
        self._counted = -1

    @override
    def render(self) -> None:
        self._glow *= float(np.exp(-self.step() * self.config.decay))
        ram = self._ram
        # Each stick is one beat of the bar, from the left: the stick of the beat being played lights
        beat = int(self.song.beats) % BEATS_PER_BAR
        if beat != self._counted:
            self._counted = beat
            stick = beat * ram.sticks // BEATS_PER_BAR
            self._glow[stick] = 1.0
        level = np.maximum(UNLIT, self._glow[ram.stick] * (0.6 + 0.4 * ram.height))
        colors = self.get_gradient_color_vectorized1d(
            ram.stick / max(ram.sticks - 1, 1) * 0.999
        )
        self.pixels = colors * level[:, None]
