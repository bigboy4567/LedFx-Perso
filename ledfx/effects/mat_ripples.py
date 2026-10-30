from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, mat_layout
from ledfx.effects.utils.custom import FloatArray

# Ripples at once, at most
MAX_RIPPLES = 6
# A ripple lives this long, and is this wide, as a share of the pad's edge
LIFE = 1.5
WIDTH = 0.06
FLASH = 6.0
WHITE = np.array((255.0, 255.0, 255.0))


class MatRipples(CorsairEffect, GradientEffect):
    NAME = "Mat Ripples"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        speed: CoercedFloat = Field(
            0.6, description="Pad edges a ripple spreads a second", ge=0.1, le=2.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        mat = mat_layout(pixel_count)
        self._along: FloatArray = mat.along
        self._mouse = mat.mouse
        # Each ripple: where it was dropped, its age, and its color
        self._ripples: FloatArray = np.zeros((0, 3))
        self._flash = 0.0

    @override
    def render(self) -> None:
        dt = self.step()
        speed = self.config.speed
        self._flash *= float(np.exp(-dt * FLASH))
        # Each percussive hit drops a ripple somewhere on the pad's edge
        if self.hit():
            ripple = np.array([[self._rng.random(), 0.0, self._rng.random()]])
            self._ripples = np.concatenate((self._ripples, ripple))[-MAX_RIPPLES:]
        if len(self._ripples):
            before = self._ripples[:, 1] * speed
            self._ripples[:, 1] += dt
            after = self._ripples[:, 1] * speed
            # The mouse flashes as a ripple reaches the middle of the U, beneath it
            middle = np.abs(self._ripples[:, 0] - 0.5)
            if ((before < middle) & (after >= middle)).any():
                self._flash = 1.0
            self._ripples = self._ripples[self._ripples[:, 1] < LIFE]
        size = self._along.size
        pixels = np.zeros((size, 3))
        for start, age, hue in self._ripples:
            ring = np.exp(-(((np.abs(self._along - start) - age * speed) / WIDTH) ** 2))
            ring *= 1 - age / LIFE
            color = self.get_gradient_color_vectorized1d(np.full(size, hue))
            np.maximum(pixels, color * ring[:, None], out=pixels)
        self.pixels = np.where(
            self._mouse[:, None], WHITE * max(0.03, self._flash), pixels
        )
