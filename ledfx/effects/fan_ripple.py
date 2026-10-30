from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, fan_layout, fan_xy, stack_height
from ledfx.effects.utils.custom import FloatArray

# Ripples at once, at most
MAX_RIPPLES = 5
# A ripple lives this long, and its ring is this wide, in fan widths
LIFE = 1.5
WIDTH = 0.2


class FanRipple(CorsairEffect, GradientEffect):
    NAME = "Fan Ripple"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        speed: CoercedFloat = Field(
            1.5, description="Fan widths a ripple spreads a second", ge=0.3, le=5.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        fans = fan_layout(pixel_count)
        x, _ = fan_xy(fans)
        self._across: FloatArray = x * 0.42
        self._up: FloatArray = stack_height(fans) * fans.count
        self._height = float(fans.count)
        # Each ripple: across, up the stack, its age, and its color
        self._ripples: FloatArray = np.zeros((0, 4))

    @override
    def render(self) -> None:
        dt = self.step()
        # Each percussive hit drops a ripple somewhere on the stack of fans
        if self.hit():
            ripple = np.array(
                [
                    [
                        (self._rng.random() - 0.5) * 0.8,
                        self._rng.random() * self._height,
                        0.0,
                        self._rng.random(),
                    ]
                ]
            )
            self._ripples = np.concatenate((self._ripples, ripple))[-MAX_RIPPLES:]
        if len(self._ripples):
            self._ripples[:, 2] += dt
            self._ripples = self._ripples[self._ripples[:, 2] < LIFE]
        size = self._up.size
        pixels = np.zeros((size, 3))
        for across, up, age, hue in self._ripples:
            distance = np.hypot(self._across - across, self._up - up)
            ring = np.exp(-(((distance - age * self.config.speed) / WIDTH) ** 2))
            ring *= 1 - age / LIFE
            color = self.get_gradient_color_vectorized1d(np.full(size, hue))
            np.maximum(pixels, color * ring[:, None], out=pixels)
        self.pixels = pixels
