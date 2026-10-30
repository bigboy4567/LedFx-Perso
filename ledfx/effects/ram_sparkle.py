from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, ram_layout
from ledfx.effects.utils.custom import FloatArray

# How quickly a sparkle fades
FADE = 5.0
WHITE = np.array((255.0, 255.0, 255.0))


class RamSparkle(CorsairEffect, GradientEffect):
    NAME = "RAM Sparkle"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        density: CoercedFloat = Field(
            1.0, description="How many sparkles the treble sets off", ge=0.2, le=4.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._ram = ram_layout(pixel_count)
        self._sparkles: FloatArray = np.zeros(pixel_count)
        self._hues: FloatArray = np.zeros(pixel_count)

    @override
    def render(self) -> None:
        dt = self.step()
        self._sparkles *= float(np.exp(-dt * FADE))
        # The treble sets LEDs sparkling here and there, a percussive hit lights a whole stick
        chance = 2 * self.levels[2] * self.config.density * dt
        new = self._rng.random(self._sparkles.size) < chance
        if self.hit():
            new |= self._ram.stick == self._rng.integers(self._ram.sticks)
        self._sparkles[new] = 1.0
        self._hues[new] = self._rng.random(int(np.count_nonzero(new)))
        colors = self.get_gradient_color_vectorized1d(self._hues)
        pixels = colors * self._sparkles[:, None]
        # Each sparkle flashes white as it is born
        pixels = pixels + (WHITE - pixels) * (self._sparkles**8)[:, None]
        self.pixels = np.clip(pixels, 0, 255)
