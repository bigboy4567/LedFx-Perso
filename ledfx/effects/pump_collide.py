from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, aio_layout, ring_gap
from ledfx.effects.utils.custom import FloatArray

# Pairs of pulses on their way round at once, at most
MAX_PULSES = 4
# How wide a pulse is, and a burst, as a share of a turn
PULSE = 0.05
BURST = 0.12
BURST_FADE = 4.0
WHITE = np.array((255.0, 255.0, 255.0))


class PumpCollide(CorsairEffect, GradientEffect):
    NAME = "Pump Collide"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        speed: CoercedFloat = Field(
            0.8, description="Turns a second each pulse travels", ge=0.2, le=3.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._aio = aio_layout(pixel_count)
        # Each pair: where it set off, how far each pulse has gone, and its color
        self._pulses: FloatArray = np.zeros((0, 3))
        self._burst = 0.0
        self._burst_at = 0.0

    @override
    def render(self) -> None:
        dt = self.step()
        self._burst *= float(np.exp(-dt * BURST_FADE))
        # Each percussive hit sends two pulses round the ring, one each way
        if self.hit():
            pulse = np.array([[self._rng.random(), 0.0, self._rng.random()]])
            self._pulses = np.concatenate((self._pulses, pulse))[-MAX_PULSES:]
        if len(self._pulses):
            self._pulses[:, 1] += dt * self.config.speed
            # Half a turn on, they meet on the far side of the ring and burst
            met = self._pulses[:, 1] >= 0.5
            if met.any():
                self._burst = 1.0
                self._burst_at = float(self._pulses[met, 0][-1] + 0.5)
            self._pulses = self._pulses[~met]

        aio = self._aio
        size = aio.angle.size
        pixels = np.zeros((size, 3))
        for start, gone, hue in self._pulses:
            near = np.maximum(
                np.exp(-((ring_gap(aio.angle, start + gone) / PULSE) ** 2)),
                np.exp(-((ring_gap(aio.angle, start - gone) / PULSE) ** 2)),
            )
            color = self.get_gradient_color_vectorized1d(np.full(size, hue))
            np.maximum(pixels, color * near[:, None], out=pixels)
        burst = (
            np.exp(-((ring_gap(aio.angle, self._burst_at) / BURST) ** 2)) * self._burst
        )
        np.maximum(pixels, WHITE * burst[:, None], out=pixels)
        # The radiator fans flash with each burst
        fans = WHITE * max(0.02, self._burst)
        self.pixels = np.where(aio.pump[:, None], pixels, fans)
