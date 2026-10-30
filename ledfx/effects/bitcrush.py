from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.custom import (
    CUSTOM_CATEGORY,
    BeatLatch,
    FloatArray,
    Trigger,
    frame_step,
)

# At full crush, blocks are this share of the strip and colors have two levels a channel
MAX_BLOCK = 0.06
MAX_BITS = 8
MIN_BITS = 1
# How hard a hit crushes, and how fast the crush lets go
HIT = 0.6
RECOVER = 4.0


class Bitcrush(AudioReactiveEffect, GradientEffect):
    NAME = "Bitcrush"
    CATEGORY = CUSTOM_CATEGORY
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        crush: CoercedFloat = Field(
            0.5, description="How much the treble crushes the picture", ge=0.0, le=1.0
        )
        speed: CoercedFloat = Field(
            0.3, description="How fast the waves move", ge=0.0, le=2.0
        )
        trigger: Trigger = Field(
            "Beat", description="Crush hard on the bass or on every percussive hit"
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._x: FloatArray = np.arange(pixel_count, dtype=float)
        self._time = 0.0
        self._kick = 0.0
        self._highs = 0.0
        self._latch = BeatLatch()

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._highs = float(data.high_power())
        self._latch.listen(data, self.config.trigger)

    def amount(self) -> float:
        return float(
            np.clip(self.config.crush * (0.3 + 0.7 * self._highs) + self._kick, 0, 1)
        )

    @override
    def render(self) -> None:
        dt = frame_step(self.passed)
        self._time += dt * self.config.speed
        self._kick *= float(np.exp(-dt * RECOVER))
        if self._latch.take(self.now):
            self._kick = HIT

        n = self.pixel_count
        amount = self.amount()
        # Fewer samples: the picture is read in blocks, each showing its first pixel
        block = max(1, round(1 + amount * n * MAX_BLOCK))
        u = (self._x // block * block) / max(n - 1, 1)
        wave = (0.5 + 0.5 * np.sin(2 * np.pi * (u * 2 - self._time))) ** 1.5
        colors = self.get_gradient_color_vectorized1d((u + self._time * 0.1) % 1)
        pixels = colors * (0.15 + 0.85 * wave)[:, None]
        # Fewer bits: each channel snaps to a handful of levels
        bits = round(MAX_BITS - amount * (MAX_BITS - MIN_BITS))
        levels = 2**bits - 1
        self.pixels = np.round(pixels / 255 * levels) / levels * 255
