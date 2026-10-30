from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, mat_height, mat_layout
from ledfx.effects.utils.custom import FloatArray

# Rockets and bursts at once, at most
MAX_ROCKETS = 2
MAX_BURSTS = 3
# A burst's sparks rain back down the side for this long
BURST_TIME = 1.0
FLASH = 6.0
WHITE = np.array((255.0, 255.0, 255.0))


class MatFireworks(CorsairEffect, GradientEffect):
    NAME = "Mat Fireworks"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        rocket_speed: CoercedFloat = Field(
            2.0, description="Sides of the pad a rocket climbs a second", ge=0.5, le=6.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        mat = mat_layout(pixel_count)
        self._height: FloatArray = mat_height(mat)
        self._right = mat.along > 0.5
        self._mouse = mat.mouse
        self._sparkle: FloatArray = self._rng.random(pixel_count)
        # Each rocket: its side (1 the right), its height, and its color
        self._rockets: FloatArray = np.zeros((0, 3))
        # Each burst: its side, its age, and its color
        self._bursts: FloatArray = np.zeros((0, 3))
        self._launch = 0.0

    @override
    def render(self) -> None:
        dt = self.step()
        self._launch *= float(np.exp(-dt * FLASH))
        # Each beat launches a rocket from the mouse, up one side or the other
        if self.beat():
            rocket = np.array([[self._rng.integers(2), 0.0, self._rng.random()]])
            self._rockets = np.concatenate((self._rockets, rocket))[-MAX_ROCKETS:]
            self._launch = 1.0
        if len(self._rockets):
            self._rockets[:, 1] += dt * self.config.rocket_speed
            # It bursts at the tip
            burst = self._rockets[:, 1] >= 1
            if burst.any():
                new = self._rockets[burst].copy()
                new[:, 1] = 0.0
                self._bursts = np.concatenate((self._bursts, new))[-MAX_BURSTS:]
            self._rockets = self._rockets[~burst]
        if len(self._bursts):
            self._bursts[:, 1] += dt
            self._bursts = self._bursts[self._bursts[:, 1] < BURST_TIME]
        self._sparkle = (self._sparkle + dt * 3) % 1

        size = self._height.size
        height = self._height
        pixels = np.zeros((size, 3))
        for side, climbed, _ in self._rockets:
            near = (self._right == (side > 0)) * np.clip(
                1 - np.abs(height - climbed) / 0.12, 0, 1
            )
            np.maximum(pixels, WHITE * 0.8 * near[:, None], out=pixels)
        for side, age, hue in self._bursts:
            # The sparks rain down from the tip, twinkling as they fall
            reach = 1 - age * 0.8
            on = (self._right == (side > 0)) & (height >= reach)
            twinkle = 0.4 + 0.6 * (self._sparkle > 0.5)
            level = np.where(on, twinkle * (1 - age / BURST_TIME), 0.0)
            color = self.get_gradient_color_vectorized1d(np.full(size, hue))
            color = color + (WHITE - color) * max(0.0, 1 - age * 5)
            np.maximum(pixels, color * level[:, None], out=pixels)
        self.pixels = np.clip(
            np.where(self._mouse[:, None], WHITE * max(0.03, self._launch), pixels),
            0,
            255,
        )
