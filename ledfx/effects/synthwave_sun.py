from typing import Literal

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
    TempoTracker,
    color_array,
    frame_step,
)

TOP = color_array("#FFE14D")
BOTTOM = color_array("#FF2E88")
SKY = color_array("#2A0050")
# The slices cut the lower part of the sun, thickest at the bottom
SLICED = 0.55
# Slices scroll down by one per this many beats
BEATS_PER_SLICE = 2

Top = Literal["At the end", "At the start"]


class SynthwaveSun(AudioReactiveEffect):
    NAME = "Synthwave Sun"
    CATEGORY = CUSTOM_CATEGORY

    class Config(AudioReactiveEffect.Config):
        sun_size: CoercedFloat = Field(
            0.8,
            description="Height of the sun, as a share of the strip",
            ge=0.2,
            le=1.0,
        )
        slices: CoercedInt = Field(
            6, description="Dark slices across the lower half of the sun", ge=0, le=14
        )
        pulse: CoercedFloat = Field(
            0.5, description="How much the sun swells with each beat", ge=0.0, le=1.0
        )
        top: Top = Field(
            "At the end", description="Which end of the strip is the top of the sun"
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._u: FloatArray = np.arange(pixel_count) / max(pixel_count - 1, 1)
        self._glow = 0.0
        self._tempo = TempoTracker()
        self._latch = BeatLatch()

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._tempo.listen(data)
        self._latch.listen(data, "Beat")

    def height(self) -> FloatArray:
        """How far up the sun each pixel is, 0 at its bottom and 1 at its top."""
        u = self._u if self.config.top == "At the end" else 1 - self._u
        size = self.config.sun_size
        return (u - (0.5 - size / 2)) / size

    @override
    def render(self) -> None:
        self._glow *= float(np.exp(-frame_step(self.passed) * 4))
        if self._latch.take(self.now):
            self._glow = 1.0

        v = self.height()
        inside = (v >= 0) & (v <= 1)
        sun = BOTTOM + (TOP - BOTTOM) * np.clip(v, 0, 1)[:, None]
        # Slices scroll down and widen toward the bottom of the sun
        if self.config.slices:
            scroll = self._tempo.beats / BEATS_PER_SLICE
            band = (v / SLICED * self.config.slices + scroll) % 1
            gap = 0.55 * (1 - v / SLICED)
            inside &= ~((v < SLICED) & (band < gap))
        level = 0.75 + 0.25 * self.config.pulse * self._glow
        # Around the sun the sky glows, fading away from the horizon
        sky = SKY * np.clip(1 - np.abs(v - 0.3) * 0.8, 0, 1)[:, None] * 0.5
        self.pixels = np.where(inside[:, None], np.clip(sun * level, 0, 255), sky)
