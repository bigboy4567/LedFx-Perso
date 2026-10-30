import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.utils.custom import (
    CUSTOM_CATEGORY,
    BeatLatch,
    FloatArray,
    Trigger,
    frame_step,
    hue_colors,
    volume_of,
)

# The rolling bar of a television out of sync: its speed in strips per second, and width
ROLL_SPEED = 0.3
ROLL_WIDTH = 0.08
# Seconds a burst of color lasts
BURST_TIME = 0.15


class TvStatic(AudioReactiveEffect):
    NAME = "TV Static"
    CATEGORY = CUSTOM_CATEGORY

    class Config(AudioReactiveEffect.Config):
        snow: CoercedFloat = Field(
            1.0, description="How bright the snow gets with loud music", ge=0.2, le=1.0
        )
        roll: bool = Field(True, description="A bright bar rolls through, out of sync")
        color_bursts: bool = Field(
            True, description="Bursts of colored snow on the beat"
        )
        trigger: Trigger = Field(
            "Beat", description="Burst on the bass or on every percussive hit"
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._u: FloatArray = np.arange(pixel_count) / max(pixel_count - 1, 1)
        self._roll = 0.0
        self._burst = 0.0
        self._volume = 0.0
        self._latch = BeatLatch()

    @override
    def config_updated(self, config: object) -> None:
        if not hasattr(self, "_rng"):
            self._rng = np.random.default_rng()

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._volume = volume_of(data)
        self._latch.listen(data, self.config.trigger)

    @override
    def render(self) -> None:
        dt = frame_step(self.passed)
        n = self.pixel_count
        self._roll = (self._roll + dt * ROLL_SPEED) % 1
        self._burst = max(0.0, self._burst - dt)
        if self._latch.take(self.now) and self.config.color_bursts:
            self._burst = BURST_TIME

        # Snow: every pixel picks a new random grey each frame, brighter with the music
        loudness = 0.12 + 0.88 * min(1.0, self._volume * 2) * self.config.snow
        snow = self._rng.random(n) ** 2 * loudness
        if self.config.roll:
            distance = np.abs((self._u - self._roll + 0.5) % 1 - 0.5)
            snow = np.clip(snow + 0.3 * np.exp(-((distance / ROLL_WIDTH) ** 2)), 0, 1)
        pixels = np.repeat(snow[:, None] * 255, 3, axis=1)
        if self._burst:
            tint = hue_colors(self._rng.random(n))
            pixels = pixels * 0.4 + tint * snow[:, None] * 0.8
        self.pixels = np.clip(pixels, 0, 255)
