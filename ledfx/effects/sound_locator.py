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
    FloatArray,
    PeakTracker,
    frame_step,
)

# Where each analysed band sits along the strip: beat, bass, mids, treble
BAND_PLACES = np.array((0.08, 0.3, 0.6, 0.9))


class SoundLocator(AudioReactiveEffect, GradientEffect):
    NAME = "Sound Locator"
    CATEGORY = CUSTOM_CATEGORY
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        responsiveness: CoercedFloat = Field(
            6.0,
            description="How quickly the spotlight follows the sound",
            ge=1.0,
            le=20.0,
        )
        size: CoercedFloat = Field(
            1.0, description="How wide the spotlight is", ge=0.3, le=3.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._x: FloatArray = np.arange(pixel_count, dtype=float)
        self._bands = PeakTracker(4)
        self._levels: FloatArray = np.zeros(4)
        self._place = 0.5
        self._spread = 0.1
        self._brightness = 0.0

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        bands = np.array(
            (
                data.beat_power(),
                data.bass_power(),
                data.mids_power(),
                data.high_power(),
            ),
            dtype=float,
        )
        self._levels = self._bands.update(bands)

    @override
    def render(self) -> None:
        n = self.pixel_count
        dt = frame_step(self.passed)
        weights = self._levels**2
        total = float(weights.sum())
        # The balance point of the sound: dull sounds sit low, bright sounds high
        if total > 0:
            target = float(weights @ BAND_PLACES) / total
            spread = float(np.sqrt(weights @ (BAND_PLACES - target) ** 2 / total))
        else:
            target, spread = self._place, self._spread
        ease = 1 - float(np.exp(-dt * self.config.responsiveness))
        self._place += (target - self._place) * ease
        self._spread += (spread - self._spread) * ease
        self._brightness += (
            min(1.0, float(self._levels.max())) - self._brightness
        ) * ease

        center = self._place * (n - 1)
        # A spread-out sound (bass and treble together) widens the spotlight
        radius = max(1.0, (0.04 + self._spread * 0.5) * n * self.config.size)
        glow = np.exp(-(((self._x - center) / radius) ** 2)) * self._brightness
        color = self.get_gradient_color(self._place)
        self.pixels = color * glow[:, None]
