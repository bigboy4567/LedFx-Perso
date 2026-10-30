from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, keyboard_layout
from ledfx.effects.utils.custom import FloatArray, hue_colors

# Glitches at once, at most
MAX_GLITCHES = 6
# A glitch lasts between these, in seconds
SHORTEST, LONGEST = 0.06, 0.2
# A percussive hit inverts the whole board for this long
INVERT = 0.08
WHITE = np.array((255.0, 255.0, 255.0))


class KeyGlitch(CorsairEffect, GradientEffect):
    NAME = "Key Glitch"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        glitchiness: CoercedFloat = Field(
            1.0, description="How readily the treble glitches the board", ge=0.2, le=4.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        board = keyboard_layout(pixel_count)
        self._x: FloatArray = board.x
        self._y: FloatArray = board.y
        # Each glitch: the left, top, width and height of its block, its hue, its time left
        self._glitches: FloatArray = np.zeros((0, 6))
        self._invert_left = 0.0
        self._time = 0.0

    @override
    def render(self) -> None:
        dt = self.step()
        self._time += dt
        if self._rng.random() < 8 * self.levels[2] * self.config.glitchiness * dt:
            glitch = np.array(
                [
                    [
                        self._rng.random() * 0.9,
                        self._rng.random() * 0.8,
                        0.05 + self._rng.random() * 0.25,
                        0.15 + self._rng.random() * 0.3,
                        self._rng.random(),
                        SHORTEST + self._rng.random() * (LONGEST - SHORTEST),
                    ]
                ]
            )
            self._glitches = np.concatenate((self._glitches, glitch))[-MAX_GLITCHES:]
        if len(self._glitches):
            self._glitches[:, 5] -= dt
            self._glitches = self._glitches[self._glitches[:, 5] > 0]
        self._invert_left -= dt
        if self.hit():
            self._invert_left = INVERT
        # A calm picture drifting across the board, which the glitches break up
        calm = (self._x + self._time * 0.1) % 1
        pixels = self.get_gradient_color_vectorized1d(calm * 0.999) * 0.25
        for left, top, width, height, hue, _ in self._glitches:
            block = (
                (self._x >= left)
                & (self._x <= left + width)
                & (self._y >= top)
                & (self._y <= top + height)
            )
            pixels[block] = hue_colors(np.array([hue]))[0]
        if self._invert_left > 0:
            pixels = WHITE - pixels
        self.pixels = pixels
