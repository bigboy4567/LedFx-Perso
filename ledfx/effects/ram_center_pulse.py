from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, ram_layout
from ledfx.effects.utils.custom import FloatArray

# Pulses on their way out at once, at most
MAX_PULSES = 6
# How thick a pulse's ring is
WIDTH = 0.18
# Sticks are this far apart, as a share of a stick's height
STICK_GAP = 0.35


class RamCenterPulse(CorsairEffect, GradientEffect):
    NAME = "RAM Center Pulse"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        speed: CoercedFloat = Field(
            1.5, description="How quickly the pulses spread", ge=0.3, le=5.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        ram = ram_layout(pixel_count)
        self._ram = ram
        # How far each LED is from the middle of the bank of sticks
        across = (ram.stick - (ram.sticks - 1) / 2) * STICK_GAP
        self._distance: FloatArray = np.hypot(across, ram.height - 0.5)
        # Each pulse: how far it has spread, and its color along the gradient
        self._pulses: FloatArray = np.zeros((0, 2))
        self._hue = 0.0

    @override
    def render(self) -> None:
        dt = self.step()
        if self.beat():
            self._hue = (self._hue + 0.13) % 1
            pulse = np.array([[0.0, self._hue]])
            self._pulses = np.concatenate((self._pulses, pulse))[-MAX_PULSES:]
        if len(self._pulses):
            self._pulses[:, 0] += dt * self.config.speed
            self._pulses = self._pulses[self._pulses[:, 0] < 2]

        distance = self._distance
        # The middle glows faintly with the bass between pulses
        core = np.exp(-((distance / 0.2) ** 2)) * 0.3 * self.levels[0]
        pixels = (
            self.get_gradient_color_vectorized1d(np.full(distance.size, self._hue))
            * core[:, None]
        )
        for spread, hue in self._pulses:
            ring = np.exp(-(((distance - spread) / WIDTH) ** 2)) * max(
                0.0, 1 - spread / 2
            )
            color = self.get_gradient_color_vectorized1d(np.full(distance.size, hue))
            np.maximum(pixels, color * ring[:, None], out=pixels)
        self.pixels = pixels
