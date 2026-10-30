from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import FAN_HUB, CorsairEffect, fan_layout, ring_gap
from ledfx.effects.utils.custom import FloatArray

# The dial runs clockwise from the bottom left, over the top, to the bottom right
DIAL_START = 0.625
DIAL_SWEEP = 0.75
NEEDLE = 0.04
UNLIT = 0.03
WHITE = np.array((255.0, 255.0, 255.0))


class FanGauges(CorsairEffect, GradientEffect):
    NAME = "Fan Gauges"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        response: CoercedFloat = Field(
            8.0, description="How quickly the needles follow the music", ge=1.0, le=30.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        fans = fan_layout(pixel_count)
        self._fans = fans
        # The top fan reads the treble, the middle one the mids, the bottom one the bass
        self._band = np.clip(fans.count - 1 - np.arange(fans.count), 0, 2)
        self.needles: FloatArray = np.zeros(fans.count)
        self._reading: FloatArray = (fans.angle - DIAL_START) % 1 / DIAL_SWEEP

    @override
    def render(self) -> None:
        target = self.levels[self._band]
        self.needles += (target - self.needles) * min(
            1.0, self.step() * self.config.response
        )
        fans = self._fans
        needle = self.needles[fans.fan]
        reading = self._reading
        on_dial = reading <= 1
        # The dial lights up to the needle, which shows white
        filled = on_dial & (reading <= needle)
        colors = self.get_gradient_color_vectorized1d(np.clip(reading, 0, 1) * 0.999)
        level = np.where(filled, 0.7, np.where(on_dial, UNLIT, 0.0))
        pixels = colors * level[:, None]
        tip = ring_gap(fans.angle, DIAL_START + needle * DIAL_SWEEP) < NEEDLE
        pixels = np.where(tip[:, None], WHITE, pixels)
        # The hub glows with the band its fan reads
        hub = (
            self.get_gradient_color_vectorized1d(np.clip(needle, 0, 1) * 0.999)
            * (0.1 + 0.9 * needle)[:, None]
        )
        self.pixels = np.where((fans.ring == FAN_HUB)[:, None], hub, pixels)
