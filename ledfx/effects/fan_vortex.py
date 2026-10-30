from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, CoercedInt
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import FAN_RIM, CorsairEffect, fan_layout

# Each fan down the stack is turned a little further along the gradient
FAN_SHIFT = 0.15


class FanVortex(CorsairEffect, GradientEffect):
    NAME = "Fan Vortex"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        arms: CoercedInt = Field(3, description="Arms of the vortex", ge=1, le=6)
        turns_per_beat: CoercedFloat = Field(
            0.25, description="Turns per beat of the song", ge=0.05, le=2.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._fans = fan_layout(pixel_count)
        self._turn = 0.0

    @override
    def render(self) -> None:
        self._turn += (
            self.song_moved() * self.config.turns_per_beat + self.step() * 0.05
        )
        fans = self._fans
        # The rim turns one way and the hub the other, which reads as a vortex
        spin = np.where(fans.ring == FAN_RIM, 1.0, -1.0)
        phase = (fans.angle - self._turn * spin) % 1
        arms = (0.5 + 0.5 * np.cos(2 * np.pi * phase * self.config.arms)) ** 2
        colors = self.get_gradient_color_vectorized1d(
            (phase + fans.fan * FAN_SHIFT) % 1
        )
        level = (0.15 + 0.85 * arms) * (0.5 + 0.5 * self.loudness)
        self.pixels = colors * level[:, None]
