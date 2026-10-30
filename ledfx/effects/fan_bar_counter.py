from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedInt
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import FAN_HUB, CorsairEffect, fan_layout

UNLIT = 0.03
WHITE = np.array((255.0, 255.0, 255.0))


class FanBarCounter(CorsairEffect, GradientEffect):
    NAME = "Fan Bar Counter"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        beats_per_bar: CoercedInt = Field(
            4, description="Beats in a bar, and slices round each rim", ge=2, le=8
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._fans = fan_layout(pixel_count)

    @override
    def render(self) -> None:
        fans = self._fans
        per_bar = self.config.beats_per_bar
        beats = self.song.beats
        # Each fan is a bar: its rim fills a slice a beat; the fans take turns, from the top
        bar = int(beats // per_bar) % fans.count
        beat = int(beats) % per_bar
        part = np.floor(fans.angle * per_bar)
        counted = np.where(
            fans.fan < bar, per_bar, np.where(fans.fan == bar, beat + 1, 0)
        )
        lit = part < counted
        playing = (fans.fan == bar) & (part == beat)
        colors = self.get_gradient_color_vectorized1d(part / per_bar * 0.999)
        rim = np.where(
            playing[:, None], WHITE, colors * np.where(lit, 0.6, UNLIT)[:, None]
        )
        # The hub of the bar being played lights its LED for the beat
        hub_lit = (fans.fan == bar) & (part == beat)
        hub = np.where(hub_lit[:, None], WHITE, colors * UNLIT)
        self.pixels = np.where((fans.ring == FAN_HUB)[:, None], hub, rim)
