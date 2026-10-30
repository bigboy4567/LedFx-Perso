from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import FAN_HUB, CorsairEffect, breath, fan_layout


class FanBreathe(CorsairEffect, GradientEffect):
    NAME = "Fan Breathe"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        beats_per_breath: CoercedFloat = Field(
            4.0, description="Beats of the song for one breath", ge=1.0, le=16.0
        )
        spread: CoercedFloat = Field(
            0.15,
            description="How far behind the fan above it each fan breathes, as a share of a breath",
            ge=0.0,
            le=0.5,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._fans = fan_layout(pixel_count)
        self._breaths = 0.0

    @override
    def render(self) -> None:
        self._breaths += (
            self.song_moved() / self.config.beats_per_breath + self.step() * 0.03
        )
        fans = self._fans
        phase = self._breaths - fans.fan * self.config.spread
        # The hub breathes out while the rim breathes in
        phase = np.where(fans.ring == FAN_HUB, phase + 0.5, phase)
        level = breath(phase) * (0.6 + 0.4 * self.loudness)
        colors = self.get_gradient_color_vectorized1d(
            fans.fan / max(fans.count - 1, 1) * 0.999
        )
        self.pixels = colors * (0.03 + 0.97 * level)[:, None]
