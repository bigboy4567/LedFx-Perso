from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedInt
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, aio_layout, pump_turn

# The dial reads from this tempo at its start to that one at its end, in beats a minute
SLOWEST = 60.0
FASTEST = 180.0
# The dial runs round this share of the ring, leaving a gap at the bottom like a gauge
SWEEP = 0.8
UNLIT = 0.04


class PumpTempoDial(CorsairEffect, GradientEffect):
    NAME = "Pump Tempo Dial"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        top_led: CoercedInt = Field(
            0, description="Which LED of the pump's ring is at the top", ge=0, le=15
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._aio = aio_layout(pixel_count)
        self._flash = 0.0

    def tempo(self) -> float:
        """The song's tempo as the dial shows it, 0 at the slowest to 1 at the fastest."""
        bpm = 60 / self.song.beat_length()
        return float(np.clip((bpm - SLOWEST) / (FASTEST - SLOWEST), 0, 1))

    @override
    def render(self) -> None:
        self._flash *= float(np.exp(-self.step() * 6))
        if self.beat():
            self._flash = 1.0
        aio = self._aio
        # From the bottom left, clockwise over the top, to the bottom right
        start = 0.5 + (1 - SWEEP) / 2
        reading = (pump_turn(aio, self.config.top_led) - start) % 1 / SWEEP
        on_dial = reading <= 1
        lit = on_dial & (reading <= self.tempo() + 0.02)
        colors = self.get_gradient_color_vectorized1d(np.clip(reading, 0, 0.999))
        level = np.where(lit, 0.35 + 0.65 * self._flash, np.where(on_dial, UNLIT, 0.0))
        pump = colors * level[:, None]
        # The radiator fans tick with each beat, in the tempo's color
        tick = self.get_gradient_color_vectorized1d(
            np.full(aio.angle.size, self.tempo() * 0.999)
        )
        fans = tick * (0.03 + 0.9 * self._flash)
        self.pixels = np.where(aio.pump[:, None], pump, fans)
