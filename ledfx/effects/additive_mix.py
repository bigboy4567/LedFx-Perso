import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.utils.custom import (
    CUSTOM_CATEGORY,
    FloatArray,
    PeakTracker,
    frame_step,
)

# Red follows the bass, green the mids, blue the treble; each rests at its own spot
HOMES = np.array((0.25, 0.5, 0.75))
# Each light wanders at its own pace, in turns per second
WANDER_RATES = np.array((0.13, 0.21, 0.17))


class AdditiveMix(AudioReactiveEffect):
    NAME = "Additive Mix"
    CATEGORY = CUSTOM_CATEGORY

    class Config(AudioReactiveEffect.Config):
        spread: CoercedFloat = Field(
            0.12,
            description="Width of each light, as a share of the strip",
            ge=0.02,
            le=0.5,
        )
        wander: CoercedFloat = Field(
            0.3, description="How much the lights drift on their own", ge=0.0, le=1.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._u: FloatArray = np.arange(pixel_count) / max(pixel_count - 1, 1)
        self.levels: FloatArray = np.zeros(3)
        self._targets: FloatArray = np.zeros(3)
        self._peaks = PeakTracker(3)
        self._time = 0.0

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        bands = np.array(
            (data.lows_power(), data.mids_power(), data.high_power()), dtype=float
        )
        self._targets = np.clip(self._peaks.update(bands), 0, 1)

    def positions(self) -> FloatArray:
        # The louder its band, the closer a light comes to the middle, where all three meet
        drift = self.config.wander * 0.1 * np.sin(2 * np.pi * WANDER_RATES * self._time)
        return HOMES + (0.5 - HOMES) * self.levels + drift

    @override
    def render(self) -> None:
        dt = frame_step(self.passed)
        self._time += dt
        self.levels += (self._targets - self.levels) * min(1.0, dt * 8)

        u = self._u[:, None]
        spots = np.exp(-(((u - self.positions()[None, :]) / self.config.spread) ** 2))
        # Each light drives only its own channel, so where they overlap the colors add
        self.pixels = 255 * spots * (0.3 + 0.7 * self.levels)[None, :]
