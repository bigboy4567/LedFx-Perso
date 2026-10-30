from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CORSAIR_CATEGORY, FAN_HUB, fan_layout
from ledfx.effects.utils.custom import (
    BeatLatch,
    FloatArray,
    Trigger,
    frame_step,
)

# Waves falling at once, at most; the oldest makes room
MAX_WAVES = 6
# Each fan is two steps deep: its hub, then its rim
STEPS_PER_FAN = 2
# The fans glow this faintly between waves
IDLE = 0.04


class FanCascade(AudioReactiveEffect, GradientEffect):
    NAME = "Fan Cascade"
    CATEGORY = CORSAIR_CATEGORY
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        speed: CoercedFloat = Field(
            10.0,
            description="How fast a wave falls through the fans, in steps per second",
            ge=2.0,
            le=40.0,
        )
        trigger: Trigger = Field(
            "Beat", description="Start a wave on the bass or on every percussive hit"
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        fans = fan_layout(pixel_count)
        # Where each LED is along the fall: the top fan's hub first, the bottom fan's rim last
        self._depth: FloatArray = fans.fan * STEPS_PER_FAN + np.where(
            fans.ring == FAN_HUB, 0.0, 1.0
        )
        self._waves: FloatArray = np.full(MAX_WAVES, np.inf)
        self._hues: FloatArray = np.zeros(MAX_WAVES)
        self._hue = 0.0
        self._latch = BeatLatch()

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._latch.listen(data, self.config.trigger)

    @override
    def render(self) -> None:
        self._waves += frame_step(self.passed) * self.config.speed
        if self._latch.take(self.now):
            slot = int(np.argmax(self._waves))
            self._waves[slot] = 0.0
            self._hue = (self._hue + 0.13) % 1
            self._hues[slot] = self._hue

        pixels = np.zeros((self._depth.size, 3))
        colors = self.get_gradient_color_vectorized1d(self._hues)
        bottom = float(self._depth.max(initial=0)) + 2
        for front, color in zip(self._waves, colors, strict=True):
            if front > bottom:
                continue
            # A wave lights each step as it passes, leaving a fading trail above it
            behind = front - self._depth
            level = np.where(behind >= 0, np.exp(-behind * 1.5), np.exp(behind * 6))
            np.maximum(pixels, color * level[:, None], out=pixels)
        self.pixels = np.maximum(pixels, 255 * IDLE)
