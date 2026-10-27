from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, CoercedInt
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

# Between beats the color creeps along the gradient this much per second
DRIFT = 0.02


class ColorJump(AudioReactiveEffect, GradientEffect):
    NAME = "Color Jump"
    CATEGORY = CUSTOM_CATEGORY
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        jump: CoercedFloat = Field(
            0.25,
            description="How far along the gradient each beat jumps",
            ge=0.05,
            le=0.5,
        )
        floor: CoercedFloat = Field(
            0.3, description="Brightness between the beats", ge=0.0, le=1.0
        )
        decay: CoercedFloat = Field(
            4.0, description="How fast the beat flash settles", ge=1.0, le=20.0
        )
        segments: CoercedInt = Field(
            1,
            description="Split the strip into segments, each a step further along the gradient",
            ge=1,
            le=8,
        )
        trigger: Trigger = Field(
            "Beat", description="Jump on the bass or on every percussive hit"
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._layout(pixel_count)
        self._hue = 0.0
        self._flash = 0.0
        self._latch = BeatLatch()

    def _layout(self, pixel_count: int) -> None:
        segments = max(1, min(self.config.segments, pixel_count))
        edges = np.linspace(0, pixel_count, segments + 1).astype(int)
        self._offsets: FloatArray = np.repeat(
            np.arange(segments) / segments, np.diff(edges)
        )

    @override
    def config_updated(self, config: object) -> None:
        pixels = getattr(self, "pixels", None)
        if pixels is not None and hasattr(self, "_offsets"):
            self._layout(len(pixels))

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._latch.listen(data, self.config.trigger)

    @override
    def render(self) -> None:
        dt = frame_step(self.passed)
        self._flash *= float(np.exp(-dt * self.config.decay))
        if self._latch.take(self.now):
            self._hue += self.config.jump
            self._flash = 1.0
        self._hue = (self._hue + DRIFT * dt) % 1
        floor = self.config.floor
        level = floor + (1 - floor) * self._flash
        colors = self.get_gradient_color_vectorized1d((self._hue + self._offsets) % 1)
        self.pixels = colors * level
