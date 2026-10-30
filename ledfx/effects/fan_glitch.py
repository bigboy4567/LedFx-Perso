from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, fan_layout
from ledfx.effects.utils.custom import FloatArray, hue_colors

# Glitches at once, at most
MAX_GLITCHES = 6
# A glitch lasts between these, in seconds
SHORTEST, LONGEST = 0.06, 0.2
# A percussive hit inverts a whole fan for this long
INVERT = 0.08
WHITE = np.array((255.0, 255.0, 255.0))


class FanGlitch(CorsairEffect, GradientEffect):
    NAME = "Fan Glitch"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        glitchiness: CoercedFloat = Field(
            1.0, description="How readily the treble glitches the fans", ge=0.2, le=4.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._fans = fan_layout(pixel_count)
        # Each glitch: its fan, where its arc starts, how long it is, its hue, its time left
        self._glitches: FloatArray = np.zeros((0, 5))
        self._inverted = -1
        self._invert_left = 0.0
        self._time = 0.0

    @override
    def render(self) -> None:
        dt = self.step()
        self._time += dt
        fans = self._fans
        if self._rng.random() < 8 * self.levels[2] * self.config.glitchiness * dt:
            glitch = np.array(
                [
                    [
                        self._rng.integers(fans.count),
                        self._rng.random(),
                        0.1 + self._rng.random() * 0.3,
                        self._rng.random(),
                        SHORTEST + self._rng.random() * (LONGEST - SHORTEST),
                    ]
                ]
            )
            self._glitches = np.concatenate((self._glitches, glitch))[-MAX_GLITCHES:]
        if len(self._glitches):
            self._glitches[:, 4] -= dt
            self._glitches = self._glitches[self._glitches[:, 4] > 0]
        self._invert_left -= dt
        if self.hit():
            self._inverted = int(self._rng.integers(fans.count))
            self._invert_left = INVERT

        # A calm picture turning round the fans, which the glitches break up
        calm = (fans.angle + self._time * 0.1) % 1
        pixels = self.get_gradient_color_vectorized1d(calm * 0.999) * 0.25
        for fan, start, length, hue, _ in self._glitches:
            arc = (fans.fan == fan) & ((fans.angle - start) % 1 < length)
            pixels[arc] = hue_colors(np.array([hue]))[0]
        if self._invert_left > 0:
            fan = fans.fan == self._inverted
            pixels[fan] = WHITE - pixels[fan]
        self.pixels = pixels
