from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedInt
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, aio_layout, pump_turn, ring_gap

BEATS_PER_BAR = 4
# The hand trails a fading arc behind it, this long as a share of the dial
TRAIL = 0.15
WHITE = np.array((255.0, 255.0, 255.0))


class PumpClock(CorsairEffect, GradientEffect):
    NAME = "Pump Clock"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        top_led: CoercedInt = Field(
            0, description="Which LED of the pump's ring is at the top", ge=0, le=15
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._aio = aio_layout(pixel_count)
        self._downbeat = 0.0
        self._bars = 0

    @override
    def render(self) -> None:
        self._downbeat *= float(np.exp(-self.step() * 4))
        bars = self.song.beats / BEATS_PER_BAR
        bar = bars % 1
        if int(bars) != self._bars:
            self._bars = int(bars)
            self._downbeat = 1.0
        aio = self._aio
        dial = pump_turn(aio, self.config.top_led)
        # The hand goes round once a bar, a tick marks each beat, the one being played bright
        behind = (bar - dial) % 1
        hand = np.where(behind < TRAIL, 1 - behind / TRAIL, 0.0)
        ticks = (
            ring_gap(dial * BEATS_PER_BAR, np.round(dial * BEATS_PER_BAR)) < 0.15
        ) * 0.15
        current = ring_gap(dial, np.floor(bar * BEATS_PER_BAR) / BEATS_PER_BAR) < 0.04
        level = np.maximum(hand, np.where(current, 0.7, ticks))
        colors = self.get_gradient_color_vectorized1d(np.clip(dial, 0, 0.999))
        pump = colors * level[:, None]
        # The radiator fans flash white on the first beat of each bar
        fans = WHITE * (0.05 + 0.95 * self._downbeat)
        self.pixels = np.where(aio.pump[:, None], pump, fans)
