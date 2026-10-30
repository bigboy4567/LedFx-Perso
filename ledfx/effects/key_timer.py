from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedInt
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, keyboard_layout
from ledfx.effects.utils.custom import FloatArray

UNLIT = 0.03
FLASH = 4.0
WHITE = np.array((255.0, 255.0, 255.0))


class KeyTimer(CorsairEffect, GradientEffect):
    NAME = "Key Timer"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        beats: CoercedInt = Field(
            16, description="Beats of the song for the board to run down", ge=4, le=64
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._x: FloatArray = keyboard_layout(pixel_count).x
        self._round = -1
        self._flash = 0.0

    @override
    def render(self) -> None:
        self._flash *= float(np.exp(-self.step() * FLASH))
        beats = self.config.beats
        counted = self.song.beats
        if int(counted // beats) != self._round:
            self._round = int(counted // beats)
            self._flash = 1.0
        # The board runs down from the left, the color turning as time runs out
        spent = (counted % beats) / beats
        lit = self._x >= spent
        colors = self.get_gradient_color_vectorized1d(
            np.full(self._x.size, (1 - spent) * 0.999)
        )
        pixels = colors * np.where(lit, 1.0, UNLIT)[:, None]
        # The board flashes white as it fills up again
        self.pixels = pixels + (WHITE - pixels) * self._flash**2
