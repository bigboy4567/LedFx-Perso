from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CORSAIR_CATEGORY, rig_layout
from ledfx.effects.utils.custom import (
    BeatLatch,
    FloatArray,
    PeakTracker,
    Trigger,
    frame_step,
)

# Waves travelling at once, at most; the oldest makes room
MAX_WAVES = 6
# Between waves each device glows with its own band, up to this much
GLOW = 0.35
WHITE = np.array((255.0, 255.0, 255.0))


class RigWave(AudioReactiveEffect, GradientEffect):
    NAME = "Rig Wave"
    CATEGORY = CORSAIR_CATEGORY
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        speed: CoercedFloat = Field(
            3.0,
            description="How fast a wave travels through the gear, in devices per second",
            ge=0.5,
            le=15.0,
        )
        glow: bool = Field(
            True,
            description="Between waves, fans and pump glow with the bass, RAM with the mids, keyboard and pad with the treble",
        )
        trigger: Trigger = Field(
            "Beat", description="Send a wave on the bass or on every percussive hit"
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        rig = rig_layout(pixel_count)
        self._band = rig.band
        # The whole setup as one path, a unit of length per device
        self._path: FloatArray = rig.stage + rig.local
        self._length = float(rig.stages)
        self._fronts: FloatArray = np.full(MAX_WAVES, np.inf)
        self._levels: FloatArray = np.zeros(3)
        self._peaks = PeakTracker(3)
        self._latch = BeatLatch()

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        bands = np.array(
            (data.lows_power(), data.mids_power(), data.high_power()), dtype=float
        )
        self._levels = np.clip(self._peaks.update(bands), 0, 1)
        self._latch.listen(data, self.config.trigger)

    @override
    def render(self) -> None:
        self._fronts += frame_step(self.passed) * self.config.speed
        if self._latch.take(self.now):
            self._fronts[int(np.argmax(self._fronts))] = 0.0

        colors = self.get_gradient_color_vectorized1d(
            np.clip(self._path / self._length, 0, 0.999)
        )
        level = (
            GLOW * self._levels[self._band]
            if self.config.glow
            else np.zeros_like(self._path)
        )
        crest = np.zeros_like(self._path)
        for front in self._fronts:
            if front > self._length + 1:
                continue
            # The wave lights each device in turn, leaving a short trail behind it
            behind = front - self._path
            np.maximum(
                crest,
                np.where(behind >= 0, np.exp(-behind * 3), np.exp(behind * 12)),
                out=crest,
            )
        pixels = colors * np.maximum(level, crest)[:, None]
        pixels = pixels + (WHITE - pixels) * (crest**6 * 0.5)[:, None]
        self.pixels = np.clip(pixels, 0, 255)
