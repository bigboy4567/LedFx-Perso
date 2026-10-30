from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, ram_layout
from ledfx.effects.utils.custom import FloatArray

# Comets in flight at once, at most
MAX_COMETS = 8
# How long a comet's tail is, as a share of a stick
TAIL = 0.4
WHITE = np.array((255.0, 255.0, 255.0))


class RamComets(CorsairEffect, GradientEffect):
    NAME = "RAM Comets"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        speed: CoercedFloat = Field(
            2.0, description="Stick heights a comet climbs a second", ge=0.5, le=6.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._ram = ram_layout(pixel_count)
        # Each comet: its stick, how high its head is, and its color
        self._comets: FloatArray = np.zeros((0, 3))

    @override
    def render(self) -> None:
        dt = self.step()
        ram = self._ram
        # Each percussive hit shoots a comet up a stick
        if self.hit():
            comet = np.array(
                [[self._rng.integers(ram.sticks), -0.05, self._rng.random()]]
            )
            self._comets = np.concatenate((self._comets, comet))[-MAX_COMETS:]
        if len(self._comets):
            self._comets[:, 1] += dt * self.config.speed
            self._comets = self._comets[self._comets[:, 1] < 1 + TAIL]
        size = ram.height.size
        pixels = np.zeros((size, 3))
        for stick, head, hue in self._comets:
            below = head - ram.height
            on = (ram.stick == stick) & (below > -0.06) & (below < TAIL)
            level = np.where(on, 1 - np.clip(below, 0, TAIL) / TAIL, 0.0)
            color = self.get_gradient_color_vectorized1d(np.full(size, hue))
            # The head burns white
            color = color + (WHITE - color) * (level**6)[:, None]
            np.maximum(pixels, color * level[:, None], out=pixels)
        self.pixels = np.clip(pixels, 0, 255)
