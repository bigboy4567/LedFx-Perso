from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, ram_layout
from ledfx.effects.utils.custom import FloatArray

# Bubbles in the sticks at once, at most
MAX_BUBBLES = 24
# Half the height of a bubble, as a share of a stick
SIZE = 0.08


class RamRising(CorsairEffect, GradientEffect):
    NAME = "RAM Rising"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        speed: CoercedFloat = Field(
            1.0, description="How quickly the bubbles rise", ge=0.2, le=4.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._ram = ram_layout(pixel_count)
        # Each bubble: its stick, its height, and its color along the gradient
        self._bubbles: FloatArray = np.zeros((0, 3))

    def _release(self, count: int) -> None:
        sticks = self._ram.sticks
        new = np.column_stack(
            (
                self._rng.integers(sticks, size=count).astype(float),
                np.zeros(count),
                self._rng.random(count),
            )
        )
        self._bubbles = np.concatenate((self._bubbles, new))[-MAX_BUBBLES:]

    @override
    def render(self) -> None:
        dt = self.step()
        # A bubble on each percussive hit, two on each bass beat, a few at random when it is loud
        if self.hit():
            self._release(1)
        if self.beat():
            self._release(2)
        if self._rng.random() < self.loudness * dt * 3:
            self._release(1)
        if len(self._bubbles):
            self._bubbles[:, 1] += dt * self.config.speed * (0.5 + self.loudness)
            self._bubbles = self._bubbles[self._bubbles[:, 1] < 1 + SIZE]

        ram = self._ram
        pixels = np.zeros((ram.height.size, 3))
        for stick, height, hue in self._bubbles:
            near = np.clip(1 - np.abs(ram.height - height) / SIZE, 0, 1)
            near = np.where(ram.stick == stick, near, 0.0)
            color = self.get_gradient_color_vectorized1d(np.full(near.size, hue))
            np.maximum(pixels, color * near[:, None], out=pixels)
        self.pixels = pixels
