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

# How long the burst of a full charge lasts
BOOM_TIME = 0.8


class ChargeUp(AudioReactiveEffect, GradientEffect):
    NAME = "Charge Up"
    CATEGORY = CUSTOM_CATEGORY
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        charge_per_beat: CoercedFloat = Field(
            0.08,
            description="How much each beat charges the meter. Louder beats charge more",
            ge=0.01,
            le=0.3,
        )
        leak: CoercedFloat = Field(
            0.03,
            description="How fast the charge drains away between beats, per second",
            ge=0.0,
            le=0.3,
        )
        trigger: Trigger = Field(
            "Beat", description="Charge on the bass or on every percussive hit"
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._along: FloatArray = np.arange(pixel_count) / max(pixel_count - 1, 1)
        self._charge = 0.0
        self._boom = 0.0
        self._lows = 0.0
        self._latch = BeatLatch()

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._lows = float(data.lows_power())
        self._latch.listen(data, self.config.trigger)

    @override
    def render(self) -> None:
        dt = frame_step(self.passed)
        self._boom = max(0.0, self._boom - dt)
        if self._latch.take(self.now) and not self._boom:
            self._charge += self.config.charge_per_beat * (0.5 + self._lows)
        self._charge = max(0.0, self._charge - self.config.leak * dt)
        if self._charge >= 1:
            self._charge = 0.0
            self._boom = BOOM_TIME

        # The meter shows the gradient up to the charge, its edge glowing white
        colors = self.get_gradient_color_vectorized1d(self._along)
        filled = self._along <= self._charge
        edge = np.exp(-(((self._along - self._charge) / 0.02) ** 2)) * (
            self._charge > 0
        )
        level = np.where(filled, 0.35 + 0.65 * self._along, 0.0)
        pixels = colors * level[:, None]
        pixels += (255 - pixels) * edge[:, None]
        if self._boom:
            # The release: everything flashes white and fades back through the colors
            burst = self._boom / BOOM_TIME
            pixels = colors * burst + (255 - colors * burst) * burst**3
        self.pixels = np.clip(pixels, 0, 255)
