from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedInt
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import FAN_HUB, CorsairEffect, fan_layout

DROP_FADE = 3.0
WHITE = np.array((255.0, 255.0, 255.0))


class FanRiser(CorsairEffect, GradientEffect):
    NAME = "Fan Riser"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        beats_per_build: CoercedInt = Field(
            16, description="Beats of the song the build-up lasts", ge=4, le=64
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._fans = fan_layout(pixel_count)
        self._turn = 0.0
        self._build = -1
        self.drop = 0.0

    @override
    def render(self) -> None:
        dt = self.step()
        self.drop *= float(np.exp(-dt * DROP_FADE))
        per_build = self.config.beats_per_build
        beats = self.song.beats
        # Through each build-up the fans spin faster and glow brighter, then the drop flashes
        build = int(beats // per_build)
        if build != self._build:
            if self._build >= 0:
                self.drop = 1.0
            self._build = build
        rising = (beats % per_build) / per_build
        self._turn += dt * (0.2 + 4 * rising**2)
        fans = self._fans
        blades = (0.5 + 0.5 * np.cos(2 * np.pi * (fans.angle * 3 - self._turn))) ** 2
        level = (0.1 + 0.9 * rising**1.5) * (0.4 + 0.6 * blades)
        level = np.where(fans.ring == FAN_HUB, 0.1 + 0.9 * rising**2, level)
        colors = self.get_gradient_color_vectorized1d(
            np.full(level.size, rising * 0.999)
        )
        pixels = colors * level[:, None]
        self.pixels = pixels + (WHITE - pixels) * self.drop
