from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedInt
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, ram_layout

UNLIT = 0.03
FLASH = 4.0
WHITE = np.array((255.0, 255.0, 255.0))


class RamTimer(CorsairEffect, GradientEffect):
    NAME = "RAM Timer"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        beats: CoercedInt = Field(
            16, description="Beats of the song for the sticks to run down", ge=4, le=64
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._ram = ram_layout(pixel_count)
        self._round = -1
        self._flash = 0.0

    @override
    def render(self) -> None:
        self._flash *= float(np.exp(-self.step() * FLASH))
        ram = self._ram
        beats = self.config.beats
        counted = self.song.beats
        if int(counted // beats) != self._round:
            self._round = int(counted // beats)
            self._flash = 1.0
        # The sticks run down from the right one to the left, each from its top
        left = 1 - (counted % beats) / beats
        level = np.clip(left * ram.sticks - ram.stick, 0, 1)
        lit = (ram.height <= level + 1e-9) & (level > 1e-9)
        colors = self.get_gradient_color_vectorized1d(np.full(level.size, left * 0.999))
        pixels = colors * np.where(lit, 1.0, UNLIT)[:, None]
        # The sticks flash white as they fill up again
        self.pixels = pixels + (WHITE - pixels) * self._flash**2
