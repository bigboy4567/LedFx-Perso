from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, mat_height, mat_layout
from ledfx.effects.utils.custom import FloatArray

# The ripple from the mouse is this wide, as a share of a side of the pad
RIPPLE = 0.25
# The pad glows this much of the mouse's light between ripples
SPILL = 0.15


class MousePulse(CorsairEffect, GradientEffect):
    NAME = "Mouse Pulse"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        decay: CoercedFloat = Field(
            4.0, description="How quickly the mouse fades after a beat", ge=1.0, le=12.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        mat = mat_layout(pixel_count)
        self._height: FloatArray = mat_height(mat)
        self._mouse = mat.mouse
        self._pulse = 0.0
        self._ripple = 2.0
        self._hue = 0.0

    @override
    def render(self) -> None:
        dt = self.step()
        self._pulse *= float(np.exp(-dt * self.config.decay))
        self._ripple += dt * 1.5
        # Each beat throbs through the mouse, in the next color, and sends a ripple up the pad
        if self.beat():
            self._pulse = 1.0
            self._ripple = 0.0
            self._hue = (self._hue + 0.09) % 1
        size = self._height.size
        color = self.get_gradient_color_vectorized1d(np.full(size, self._hue))
        mouse = color * max(0.08, self._pulse, 0.5 * self.levels[0])
        ring = np.exp(-(((self._height - self._ripple) / RIPPLE) ** 2)) * max(
            0.0, 1 - self._ripple
        )
        glow = np.maximum(ring, SPILL * self._pulse)
        pad = color * np.maximum(glow, 0.02)[:, None]
        self.pixels = np.where(self._mouse[:, None], mouse, pad)
