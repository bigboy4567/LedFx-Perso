from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import FAN_HUB, CorsairEffect, fan_layout

# Hub to rim, as distances on the face of a fan
HUB, RIM = 0.0, 1.0
WHITE = np.array((255.0, 255.0, 255.0))


class FanPulse(CorsairEffect, GradientEffect):
    NAME = "Fan Pulse"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        speed: CoercedFloat = Field(
            6.0,
            description="How fast a pulse spreads from the hub to the rim",
            ge=1.0,
            le=20.0,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        fans = fan_layout(pixel_count)
        self._reach = np.where(fans.ring == FAN_HUB, HUB, RIM)
        self._front = np.inf
        self._hue = 0.0

    @override
    def render(self) -> None:
        self._front += self.step() * self.config.speed
        if self.beat():
            self._front = 0.0
            self._hue = (self._hue + 0.12) % 1
        color = self.get_gradient_color_vectorized1d(np.array((self._hue,)))[0]
        # The pulse leaves the hub on the beat and spreads out to the rim, fading
        behind = self._front - self._reach
        pulse = np.where(behind >= 0, np.exp(-behind * 2.5), 0.0)
        # Between pulses the mids keep the fans gently lit
        level = np.maximum(pulse, 0.08 + 0.25 * self.levels[1])
        pixels = color * level[:, None]
        self.pixels = np.clip(
            pixels + (WHITE - pixels) * (pulse**8)[:, None] * 0.6, 0, 255
        )
