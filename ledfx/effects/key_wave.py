from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, keyboard_layout
from ledfx.effects.utils.custom import FloatArray

# How thick the wave's line is, as a share of the board's depth
THICKNESS = 0.12


class KeyWave(CorsairEffect, GradientEffect):
    NAME = "Key Wave"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        waves: CoercedFloat = Field(
            1.5, description="Waves across the width of the board", ge=0.5, le=5.0
        )
        speed: CoercedFloat = Field(
            0.5, description="Waves passing by per beat of the song", ge=0.1, le=2.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        board = keyboard_layout(pixel_count)
        self._x: FloatArray = board.x
        self._y: FloatArray = board.y
        self._phase = 0.0
        self._height = 0.1

    @override
    def render(self) -> None:
        dt = self.step()
        self._phase += self.song_moved() * self.config.speed + dt * 0.1
        # The louder the music, the taller the wave
        target = 0.1 + 0.4 * self.loudness
        self._height += (target - self._height) * min(1.0, dt * 6)
        x = self._x
        crest = 0.5 + self._height * np.sin(
            2 * np.pi * (x * self.config.waves - self._phase)
        )
        near = np.clip(1 - np.abs(self._y - crest) / THICKNESS, 0, 1)
        # Below the line the board glows faintly, like water under a wave
        under = np.where(self._y > crest, 0.08, 0.0)
        level = np.maximum(near, under)
        colors = self.get_gradient_color_vectorized1d(np.clip(x, 0, 0.999))
        self.pixels = colors * level[:, None]
