from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, mat_layout
from ledfx.effects.utils.custom import FloatArray


class MatFlow(CorsairEffect, GradientEffect):
    NAME = "Mat Flow"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        top_speed: CoercedFloat = Field(
            1.0,
            description="Gradients flowing round the pad a second at full volume",
            ge=0.1,
            le=4.0,
        )
        repeats: CoercedFloat = Field(
            1.0,
            description="Times the gradient fits round the pad's edge",
            ge=0.5,
            le=4.0,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        mat = mat_layout(pixel_count)
        self._along: FloatArray = mat.along
        self._mouse = mat.mouse
        self._flow = 0.0
        self._speed = 0.0

    @override
    def render(self) -> None:
        dt = self.step()
        # The current picks up with the music and slackens when it calms
        target = 0.05 + 0.95 * self.loudness
        self._speed += (target - self._speed) * min(1.0, dt * 3)
        self._flow += dt * self._speed * self.config.top_speed
        place = (self._along * self.config.repeats - self._flow) % 1
        # A smooth back-and-forth through the gradient, so its ends never meet in a seam
        colors = self.get_gradient_color_vectorized1d(np.abs(place * 2 - 1) * 0.999)
        pixels = colors * (0.4 + 0.6 * self._speed)
        # The mouse carries the color flowing past the middle of the pad, under it
        middle = (0.5 * self.config.repeats - self._flow) % 1
        mouse = self.get_gradient_color_vectorized1d(
            np.full(self._along.size, abs(middle * 2 - 1) * 0.999)
        )
        self.pixels = np.where(self._mouse[:, None], mouse, pixels)
