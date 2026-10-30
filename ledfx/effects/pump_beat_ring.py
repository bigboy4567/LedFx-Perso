from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedInt
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, aio_layout, pump_turn
from ledfx.effects.utils.custom import IntArray

UNLIT = 0.03
WHITE = np.array((255.0, 255.0, 255.0))


class PumpBeatRing(CorsairEffect, GradientEffect):
    NAME = "Pump Beat Ring"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        top_led: CoercedInt = Field(
            0, description="Which LED of the pump's ring is at the top", ge=0, le=15
        )
        beats_per_ring: CoercedInt = Field(
            16, description="Beats to go once round the ring", ge=4, le=32
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        aio = aio_layout(pixel_count)
        self._aio = aio
        # The radiator fans' LEDs in a row, to count the rings completed
        self._slot: IntArray = np.where(
            aio.fan >= 0, aio.fan * 4 + np.round(aio.angle * 4), -1
        ).astype(int)

    @override
    def render(self) -> None:
        aio = self._aio
        per_ring = self.config.beats_per_ring
        beats = self.song.beats
        # The ring fills clockwise from the top, a step each beat, the beat being played white
        done = (beats % per_ring) / per_ring
        place = pump_turn(aio, self.config.top_led)
        step = np.floor(place * per_ring)
        current = step == np.floor(beats % per_ring)
        filled = (step + 1) / per_ring <= done + 1e-9
        colors = self.get_gradient_color_vectorized1d(place * 0.999)
        pump = np.where(
            current[:, None], WHITE, colors * np.where(filled, 0.5, UNLIT)[:, None]
        )
        # The radiator fans count the rings gone round, one LED each
        rings = int(beats // per_ring) % 8
        fans = colors * np.where(self._slot <= rings, 0.6, UNLIT)[:, None]
        self.pixels = np.where(aio.pump[:, None], pump, fans)
