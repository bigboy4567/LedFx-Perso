from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, mat_layout
from ledfx.effects.utils.custom import FloatArray

# Comets on the pad at once, at most
MAX_COMETS = 6
# How long a comet's tail is, as a share of the pad's edge
TAIL = 0.25
WHITE = np.array((255.0, 255.0, 255.0))


class MatComets(CorsairEffect, GradientEffect):
    NAME = "Mat Comets"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        speed: CoercedFloat = Field(
            1.5, description="Pad edges a comet crosses a second", ge=0.3, le=5.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        mat = mat_layout(pixel_count)
        self._along: FloatArray = mat.along
        self._mouse = mat.mouse
        # Each comet: how far it has gone from its tip, its direction (1 rightward), its color
        self._comets: FloatArray = np.zeros((0, 3))
        self._direction = 1.0
        self._passing = 0.0

    @override
    def render(self) -> None:
        dt = self.step()
        # Each percussive hit shoots a comet from one tip of the U, the next from the other
        if self.hit():
            comet = np.array([[0.0, self._direction, self._rng.random()]])
            self._comets = np.concatenate((self._comets, comet))[-MAX_COMETS:]
            self._direction = -self._direction
        self._passing *= float(np.exp(-dt * 6))
        if len(self._comets):
            before = self._comets[:, 0].copy()
            self._comets[:, 0] += dt * self.config.speed
            if ((before < 0.5) & (self._comets[:, 0] >= 0.5)).any():
                self._passing = 1.0
            self._comets = self._comets[self._comets[:, 0] < 1 + TAIL]

        size = self._along.size
        pixels = np.zeros((size, 3))
        for travelled, direction, hue in self._comets:
            place = self._along if direction > 0 else 1 - self._along
            behind = travelled - place
            level = np.where(
                (behind >= -0.03) & (behind < TAIL),
                1 - np.clip(behind, 0, TAIL) / TAIL,
                0.0,
            )
            color = self.get_gradient_color_vectorized1d(np.full(size, hue))
            color = color + (WHITE - color) * (level**8)[:, None]
            np.maximum(pixels, color * level[:, None], out=pixels)
        # The mouse sparkles as a comet passes the middle of the pad
        self.pixels = np.clip(
            np.where(self._mouse[:, None], WHITE * max(0.03, self._passing), pixels),
            0,
            255,
        )
