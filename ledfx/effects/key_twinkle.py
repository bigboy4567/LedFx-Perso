from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, CoercedInt
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, keyboard_layout
from ledfx.effects.utils.custom import FloatArray

# How quickly a key flashed by a beat fades back
FLASH_FADE = 4.0
WHITE = np.array((255.0, 255.0, 255.0))


class KeyTwinkle(CorsairEffect, GradientEffect):
    NAME = "Key Twinkle"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        pace: CoercedFloat = Field(
            1.0, description="How quickly the keys twinkle", ge=0.2, le=4.0
        )
        flashes_per_beat: CoercedInt = Field(
            6, description="Keys flashing white on each beat", ge=0, le=30
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        board = keyboard_layout(pixel_count)
        # Every key twinkles at its own pace, with its own color
        self._phase: FloatArray = self._rng.random(pixel_count) * 2 * np.pi
        self._rate: FloatArray = 0.5 + self._rng.random(pixel_count) * 1.5
        self._hue: FloatArray = board.x * 0.6 + self._rng.random(pixel_count) * 0.4
        self._flash: FloatArray = np.zeros(pixel_count)
        self._time = 0.0

    @override
    def render(self) -> None:
        dt = self.step()
        self._time += dt * self.config.pace
        self._flash *= float(np.exp(-dt * FLASH_FADE))
        if self.beat():
            count = min(self.config.flashes_per_beat, self._flash.size)
            self._flash[self._rng.choice(self._flash.size, count, replace=False)] = 1.0
        # The mids make the whole sky twinkle brighter
        twinkle = (0.5 + 0.5 * np.sin(self._time * self._rate * 3 + self._phase)) ** 3
        level = twinkle * (0.25 + 0.75 * self.levels[1])
        colors = self.get_gradient_color_vectorized1d(np.clip(self._hue, 0, 0.999))
        pixels = colors * level[:, None]
        pixels = pixels + (WHITE - pixels) * self._flash[:, None]
        self.pixels = np.clip(pixels, 0, 255)
