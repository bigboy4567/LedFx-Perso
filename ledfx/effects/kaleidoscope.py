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
    volume_of,
)

# How far a beat turns the kaleidoscope, as a share of the gradient
BEAT_TURN = 0.2


class Kaleidoscope(AudioReactiveEffect, GradientEffect):
    NAME = "Kaleidoscope"
    CATEGORY = CUSTOM_CATEGORY
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        mirrors: CoercedInt = Field(
            6, description="Number of mirrored copies along the strip", ge=2, le=16
        )
        bands: CoercedInt = Field(
            3, description="Stripes of light in each copy", ge=1, le=8
        )
        speed: CoercedFloat = Field(
            0.3, description="How fast the pattern turns", ge=0.0, le=2.0
        )
        trigger: Trigger = Field(
            "Beat", description="Turn on the bass or on every percussive hit"
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._layout(pixel_count)
        self._turn = 0.0
        self._kick = 0.0
        self._flash = 0.0
        self._volume = 0.0
        self._latch = BeatLatch()

    def _layout(self, pixel_count: int) -> None:
        mirrors = self.config.mirrors
        along = np.arange(pixel_count) / max(pixel_count, 1) * mirrors
        # Every other copy runs backwards, as in a mirror
        within = along % 1
        flipped = along.astype(int) % 2 == 1
        self._u: FloatArray = np.where(flipped, 1 - within, within)

    @override
    def config_updated(self, config: object) -> None:
        pixels = getattr(self, "pixels", None)
        if pixels is not None and hasattr(self, "_u"):
            self._layout(len(pixels))

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._volume = volume_of(data)
        self._latch.listen(data, self.config.trigger)

    @override
    def render(self) -> None:
        dt = frame_step(self.passed)
        if self._latch.take(self.now):
            self._kick += BEAT_TURN
            self._flash = 1.0
        # The beat's turn is eased in rather than jumped
        eased = self._kick * (1 - float(np.exp(-dt * 10)))
        self._kick -= eased
        self._turn += eased + dt * self.config.speed * (1 + self._volume)
        self._flash *= float(np.exp(-dt * 6))

        u = self._u
        colors = self.get_gradient_color_vectorized1d((u * 0.5 + self._turn) % 1)
        stripes = 0.5 + 0.5 * np.sin(
            2 * np.pi * (u * self.config.bands - self._turn * 2)
        )
        level = 0.25 + 0.75 * stripes**2
        pixels = colors * level[:, None]
        self.pixels = pixels + (255 - pixels) * 0.35 * self._flash
