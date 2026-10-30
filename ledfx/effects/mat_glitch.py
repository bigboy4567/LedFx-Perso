from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, mat_layout
from ledfx.effects.utils.custom import FloatArray, hue_colors

# Glitches on screen at once, at most
MAX_GLITCHES = 5
# A glitch lasts between these, in seconds
SHORTEST, LONGEST = 0.06, 0.2
# A percussive hit inverts the whole pad for this long
INVERT = 0.08
WHITE = np.array((255.0, 255.0, 255.0))


class MatGlitch(CorsairEffect, GradientEffect):
    NAME = "Mat Glitch"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        glitchiness: CoercedFloat = Field(
            1.0, description="How readily the treble glitches the pad", ge=0.2, le=4.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        mat = mat_layout(pixel_count)
        self._along: FloatArray = mat.along
        self._mouse = mat.mouse
        # Each glitch: the start and end of the stretch it hits, its hue, its time left
        self._glitches: FloatArray = np.zeros((0, 4))
        self._invert_left = 0.0
        self._time = 0.0

    @override
    def render(self) -> None:
        dt = self.step()
        self._time += dt
        if self._rng.random() < 8 * self.levels[2] * self.config.glitchiness * dt:
            start = self._rng.random() * 0.85
            glitch = np.array(
                [
                    [
                        start,
                        start + 0.05 + self._rng.random() * 0.2,
                        self._rng.random(),
                        SHORTEST + self._rng.random() * (LONGEST - SHORTEST),
                    ]
                ]
            )
            self._glitches = np.concatenate((self._glitches, glitch))[-MAX_GLITCHES:]
        if len(self._glitches):
            self._glitches[:, 3] -= dt
            self._glitches = self._glitches[self._glitches[:, 3] > 0]
        self._invert_left -= dt
        if self.hit():
            self._invert_left = INVERT

        # A calm picture flowing round the pad, which the glitches break up
        calm = (self._along + self._time * 0.2) % 1
        pixels = self.get_gradient_color_vectorized1d(calm * 0.999) * 0.25
        for start, end, hue, _ in self._glitches:
            stretch = (self._along >= start) & (self._along <= end) & ~self._mouse
            pixels[stretch] = hue_colors(np.array([hue]))[0]
        # The mouse flickers with the glitches
        pixels[self._mouse] = WHITE * (0.6 if len(self._glitches) else 0.03)
        if self._invert_left > 0:
            pixels = WHITE - pixels
        self.pixels = pixels
