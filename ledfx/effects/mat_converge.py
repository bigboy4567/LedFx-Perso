from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, mat_height, mat_layout
from ledfx.effects.utils.custom import FloatArray

# Pulses on their way down at once, at most
MAX_PULSES = 6
# How long a pulse is, as a share of a side of the pad
LENGTH = 0.3
# How quickly the burst where the pulses meet fades
BURST_FADE = 5.0
WHITE = np.array((255.0, 255.0, 255.0))


class MatConverge(CorsairEffect, GradientEffect):
    NAME = "Mat Converge"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        speed: CoercedFloat = Field(
            2.0,
            description="Sides of the pad a pulse runs down a second",
            ge=0.5,
            le=6.0,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        mat = mat_layout(pixel_count)
        self._height: FloatArray = mat_height(mat)
        self._mouse = mat.mouse
        # Each pulse: how far down it has come from the tips, 0 to 1, and its color
        self._pulses: FloatArray = np.zeros((0, 2))
        self._burst = 0.0
        self._burst_hue = 0.0
        self._hue = 0.0

    @override
    def render(self) -> None:
        dt = self.step()
        self._burst *= float(np.exp(-dt * BURST_FADE))
        # On each beat two pulses set off from the tips and run down to meet at the bottom
        if self.beat():
            self._hue = (self._hue + 0.21) % 1
            pulse = np.array([[0.0, self._hue]])
            self._pulses = np.concatenate((self._pulses, pulse))[-MAX_PULSES:]
        if len(self._pulses):
            self._pulses[:, 0] += dt * self.config.speed
            met = self._pulses[:, 0] >= 1
            if met.any():
                self._burst = 1.0
                self._burst_hue = float(self._pulses[met, 1][-1])
            self._pulses = self._pulses[~met]

        down = 1 - self._height
        size = down.size
        pixels = np.zeros((size, 3))
        for travelled, hue in self._pulses:
            ahead = travelled - down
            level = np.where((ahead >= 0) & (ahead < LENGTH), 1 - ahead / LENGTH, 0.0)
            color = self.get_gradient_color_vectorized1d(np.full(size, hue))
            np.maximum(pixels, color * level[:, None], out=pixels)
        # Where they meet, a burst lights the bottom of the pad and the mouse
        burst_color = self.get_gradient_color_vectorized1d(
            np.full(size, self._burst_hue)
        )
        burst = np.clip(1 - self._height * 2.5, 0, 1) * self._burst
        np.maximum(pixels, burst_color * burst[:, None], out=pixels)
        mouse = burst_color + (WHITE - burst_color) * self._burst**3
        self.pixels = np.where(
            self._mouse[:, None], mouse * max(0.05, self._burst), pixels
        )
