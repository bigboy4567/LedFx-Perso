from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import KEYBOARD_DEPTH, CorsairEffect, keyboard_layout
from ledfx.effects.utils.custom import FloatArray

# Rockets and bursts at once, at most
MAX_ROCKETS = 4
MAX_BURSTS = 5
# A burst lasts this long, spreading this far a second across the board
BURST_TIME = 1.0
SPREAD = 0.25
RING = 0.045
WHITE = np.array((255.0, 255.0, 255.0))


class KeyFireworks(CorsairEffect, GradientEffect):
    NAME = "Key Fireworks"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        rocket_speed: CoercedFloat = Field(
            1.5, description="Board depths a rocket climbs a second", ge=0.5, le=5.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        board = keyboard_layout(pixel_count)
        self._x: FloatArray = board.x
        self._y: FloatArray = board.y * KEYBOARD_DEPTH
        # Each rocket: across, how high up the board, where it bursts, and its color
        self._rockets: FloatArray = np.zeros((0, 4))
        # Each burst: across, up the board, its age, and its color
        self._bursts: FloatArray = np.zeros((0, 4))

    @override
    def render(self) -> None:
        dt = self.step()
        # Each beat launches a rocket from the front row
        if self.beat():
            rocket = np.array(
                [
                    [
                        0.1 + self._rng.random() * 0.8,
                        0.0,
                        0.4 + self._rng.random() * 0.5,
                        self._rng.random(),
                    ]
                ]
            )
            self._rockets = np.concatenate((self._rockets, rocket))[-MAX_ROCKETS:]
        if len(self._rockets):
            self._rockets[:, 1] += dt * self.config.rocket_speed
            burst = self._rockets[:, 1] >= self._rockets[:, 2]
            if burst.any():
                new = self._rockets[burst].copy()
                new[:, 1] = new[:, 2]
                new[:, 2] = 0.0
                self._bursts = np.concatenate((self._bursts, new))[-MAX_BURSTS:]
            self._rockets = self._rockets[~burst]
        if len(self._bursts):
            self._bursts[:, 2] += dt
            self._bursts = self._bursts[self._bursts[:, 2] < BURST_TIME]

        size = self._x.size
        pixels = np.zeros((size, 3))
        # Heights count up from the front of the board
        up = KEYBOARD_DEPTH - self._y
        for across, height, _, _ in self._rockets:
            near = np.clip(
                1 - np.hypot(self._x - across, up - height * KEYBOARD_DEPTH) / 0.03,
                0,
                1,
            )
            np.maximum(pixels, WHITE * 0.8 * near[:, None], out=pixels)
        for across, height, age, hue in self._bursts:
            distance = np.hypot(self._x - across, up - height * KEYBOARD_DEPTH)
            ring = np.exp(-(((distance - age * SPREAD) / RING) ** 2)) * (
                1 - age / BURST_TIME
            )
            color = self.get_gradient_color_vectorized1d(np.full(size, hue))
            color = color + (WHITE - color) * max(0.0, 1 - age * 5)
            np.maximum(pixels, color * ring[:, None], out=pixels)
        self.pixels = np.clip(pixels, 0, 255)
