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
    TempoTracker,
    Trigger,
    frame_step,
)

# At the deepest duck the light also pulls in this far toward the middle
SQUEEZE = 0.3
# Width of the soft edge of the lit part, as a share of the strip
EDGE = 0.05


class SidechainPump(AudioReactiveEffect, GradientEffect):
    NAME = "Sidechain Pump"
    CATEGORY = CUSTOM_CATEGORY
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        depth: CoercedFloat = Field(
            0.85, description="How far each kick ducks the light", ge=0.1, le=1.0
        )
        release: CoercedFloat = Field(
            0.6,
            description="How long the light takes to swell back, as a share of a beat",
            ge=0.1,
            le=1.0,
        )
        drift: CoercedFloat = Field(
            0.05,
            description="How fast the colors drift along the strip",
            ge=0.0,
            le=1.0,
        )
        trigger: Trigger = Field(
            "Beat", description="Duck on the bass or on every percussive hit"
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._u: FloatArray = np.arange(pixel_count) / max(pixel_count - 1, 1)
        self._since = np.inf
        self._shift = 0.0
        self._tempo = TempoTracker()
        self._latch = BeatLatch()

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._tempo.listen(data)
        self._latch.listen(data, self.config.trigger)

    def duck(self) -> float:
        """How far the light is ducked right now, 0 for not at all."""
        release = self.config.release * self._tempo.beat_length()
        # A compressor's release: the light snaps down, holds low, then swells back
        t = min(1.0, self._since / release)
        return self.config.depth * (1 - t * t * (3 - 2 * t))

    @override
    def render(self) -> None:
        dt = frame_step(self.passed)
        self._since += dt
        if self._latch.take(self.now):
            self._since = 0.0
        self._shift = (self._shift + dt * self.config.drift) % 1

        duck = self.duck()
        reach = 1 - SQUEEZE * duck
        edge = np.clip((reach - np.abs(self._u - 0.5) * 2) / EDGE + 1, 0, 1)
        colors = self.get_gradient_color_vectorized1d((self._u + self._shift) % 1)
        self.pixels = colors * ((1 - duck) * edge)[:, None]
