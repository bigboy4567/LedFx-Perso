from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedInt
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import FAN_HUB, FAN_RIM, CorsairEffect, fan_layout
from ledfx.effects.utils.custom import FloatArray

# How fast a spark dies
SPARK_DECAY = 6.0
WHITE = np.array((255.0, 255.0, 255.0))


class FanSparks(CorsairEffect, GradientEffect):
    NAME = "Fan Sparks"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        sparks_per_hit: CoercedInt = Field(
            4, description="Rim LEDs that spark on each percussive hit", ge=1, le=12
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        fans = fan_layout(pixel_count)
        self._rim = np.flatnonzero(fans.ring == FAN_RIM)
        self._hub = fans.ring == FAN_HUB
        self._sparks: FloatArray = np.zeros(pixel_count)
        self._hues: FloatArray = np.zeros(pixel_count)

    @override
    def render(self) -> None:
        self._sparks *= float(np.exp(-self.step() * SPARK_DECAY))
        if self.hit() and self._rim.size:
            count = min(self.config.sparks_per_hit, self._rim.size)
            chosen = self._rng.choice(self._rim, count, replace=False)
            self._sparks[chosen] = 1.0
            self._hues[chosen] = self._rng.random(count)

        colors = self.get_gradient_color_vectorized1d(self._hues)
        pixels = colors * self._sparks[:, None]
        # A fresh spark burns white before it takes its color
        pixels = pixels + (WHITE - pixels) * (self._sparks**6)[:, None]
        hub = self.get_gradient_color_vectorized1d(np.full(self._sparks.size, 0.5))
        hub = hub * (0.1 + 0.6 * self.levels[1])
        self.pixels = np.clip(np.where(self._hub[:, None], hub, pixels), 0, 255)
