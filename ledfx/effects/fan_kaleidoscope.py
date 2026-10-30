from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedInt
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import FAN_HUB, CorsairEffect, fan_layout


class FanKaleidoscope(CorsairEffect, GradientEffect):
    NAME = "Fan Kaleidoscope"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        mirrors: CoercedInt = Field(
            3, description="Mirrored slices round each rim", ge=2, le=6
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._fans = fan_layout(pixel_count)
        self._time = 0.0

    @override
    def render(self) -> None:
        dt = self.step()
        # The music turns the kaleidoscope, and each beat gives it a twist
        self._time += dt * (0.2 + self.loudness) + self.song_moved() * 0.1
        if self.beat():
            self._time += 0.3
        fans = self._fans
        t = self._time
        # Each slice is the mirror image of the one beside it
        slice_place = (fans.angle * self.config.mirrors) % 1
        mirrored = np.minimum(slice_place, 1 - slice_place) * 2
        hues = (mirrored * 0.6 + t * 0.15 + fans.fan * 0.2) % 1
        level = 0.35 + 0.65 * (0.5 + 0.5 * np.cos(2 * np.pi * (mirrored * 1.5 - t)))
        # The hub is the eyepiece, in the color at the heart of the pattern
        hues = np.where(fans.ring == FAN_HUB, (t * 0.15 + fans.fan * 0.2) % 1, hues)
        colors = self.get_gradient_color_vectorized1d(hues * 0.999)
        self.pixels = colors * level[:, None]
