import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, CoercedInt
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.utils.custom import (
    CUSTOM_CATEGORY,
    BeatLatch,
    FloatArray,
    Trigger,
    frame_step,
)

# How fast a split snaps back together, per second
RECOVER = 5.0
# How far the treble jitters the channels, as a share of the strip
JITTER = 0.01


class RgbSplit(AudioReactiveEffect):
    NAME = "RGB Split"
    CATEGORY = CUSTOM_CATEGORY

    class Config(AudioReactiveEffect.Config):
        bars: CoercedInt = Field(
            8, description="White bars along the strip", ge=1, le=60
        )
        split: CoercedFloat = Field(
            0.05,
            description="How far a hit pulls red and blue apart, as a share of the strip",
            ge=0.0,
            le=0.25,
        )
        jitter: CoercedFloat = Field(
            0.3,
            description="How much the treble shakes the channels apart",
            ge=0.0,
            le=1.0,
        )
        speed: CoercedFloat = Field(
            0.1, description="How fast the bars move", ge=0.0, le=1.0
        )
        trigger: Trigger = Field(
            "Beat", description="Split on the bass or on every percussive hit"
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._u: FloatArray = np.arange(pixel_count) / max(pixel_count - 1, 1)
        self._scroll = 0.0
        self._kick = 0.0
        self._highs = 0.0
        self._latch = BeatLatch()

    @override
    def config_updated(self, config: object) -> None:
        if not hasattr(self, "_rng"):
            self._rng = np.random.default_rng()

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._highs = float(data.high_power())
        self._latch.listen(data, self.config.trigger)

    def _bars(self, shift: float) -> FloatArray:
        wave = np.sin(2 * np.pi * ((self._u - shift) * self.config.bars - self._scroll))
        return np.clip(wave * 3, 0, 1)

    @override
    def render(self) -> None:
        dt = frame_step(self.passed)
        self._scroll += dt * self.config.speed
        self._kick *= float(np.exp(-dt * RECOVER))
        if self._latch.take(self.now):
            self._kick = 1.0

        shake = self.config.jitter * self._highs * JITTER * float(self._rng.normal())
        shift = self._kick * self.config.split + shake
        # The lens no longer brings the colors together: red slides one way, blue the other
        red, green, blue = self._bars(shift), self._bars(0.0), self._bars(-shift)
        self.pixels = np.stack((red, green, blue), axis=1) * 255
