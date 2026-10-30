from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.custom import (
    AUDIO_STEP,
    CUSTOM_CATEGORY,
    BeatLatch,
    FloatArray,
    frame_step,
    volume_of,
)

# The build-up compares the last second of loudness with the last eight
SHORT_SECONDS = 1.0
LONG_SECONDS = 8.0
# A drop needs this much build-up behind it, and bass this strong
DROP_BUILD = 0.6
DROP_BASS = 0.5
DROP_TIME = 1.5
# The strip glows this faintly with no build-up at all
RESTING = 0.06
WHITE = np.array((255.0, 255.0, 255.0))


class Riser(AudioReactiveEffect, GradientEffect):
    NAME = "Riser"
    CATEGORY = CUSTOM_CATEGORY
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        sensitivity: CoercedFloat = Field(
            1.0, description="How quickly a rising song fills the riser", ge=0.3, le=4.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._u: FloatArray = np.arange(pixel_count) / max(pixel_count - 1, 1)
        self._short = 0.0
        self._long = 0.0
        self._lows = 0.0
        self.build = 0.0
        self._drop = np.inf
        self._latch = BeatLatch()

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        volume = volume_of(data)
        self._short += (volume - self._short) * AUDIO_STEP / SHORT_SECONDS
        self._long += (volume - self._long) * AUDIO_STEP / LONG_SECONDS
        self._lows = float(data.lows_power())
        self._latch.listen(data, "Beat")

    @override
    def render(self) -> None:
        dt = frame_step(self.passed)
        rising = (
            (self._short - self._long)
            / max(self._long, 0.05)
            * self.config.sensitivity
            * 2
        )
        self.build += (float(np.clip(rising, 0, 1)) - self.build) * min(1.0, dt * 1.5)
        self._drop += dt
        if (
            self._latch.take(self.now)
            and self.build > DROP_BUILD
            and self._lows > DROP_BASS
        ):
            # The drop: the build-up is spent, and starts again from the new loudness
            self._drop = 0.0
            self.build = 0.0
            self._long = self._short

        colors = self.get_gradient_color_vectorized1d(self._u)
        if self._drop < DROP_TIME:
            fade = 1 - self._drop / DROP_TIME
            self.pixels = colors + (WHITE - colors) * fade**3
            return
        # The riser fills the strip and flutters faster as it nears the top
        build = self.build
        flutter = 0.5 + 0.5 * np.sign(
            np.sin(2 * np.pi * self.now * (2 + 14 * build**2))
        )
        level = np.where(self._u <= build, 0.35 + 0.65 * self._u, RESTING)
        level = level * (1 - 0.6 * build * (1 - flutter))
        self.pixels = colors * level[:, None]
