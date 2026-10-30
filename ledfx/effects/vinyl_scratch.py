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
    TempoTracker,
    Trigger,
    frame_step,
)

# A scratch lasts this long, and the record goes back and forth this many times in it
SCRATCH_TIME = 0.5
STROKES = 2
NEEDLE = np.array((255.0, 255.0, 255.0))


class VinylScratch(AudioReactiveEffect, GradientEffect):
    NAME = "Vinyl Scratch"
    CATEGORY = CUSTOM_CATEGORY
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        groove_width: CoercedInt = Field(
            8, description="Pixels per groove of the record", ge=2, le=100
        )
        scratch_size: CoercedFloat = Field(
            0.2,
            description="How far a scratch pulls the record, as a share of the strip",
            ge=0.02,
            le=0.6,
        )
        trigger: Trigger = Field(
            "Beat", description="Scratch on the bass or on every percussive hit"
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._x: FloatArray = np.arange(pixel_count, dtype=float)
        # How far the record has turned, in grooves
        self._turned = 0.0
        self._age = np.inf
        self._tempo = TempoTracker()
        self._latch = BeatLatch()

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._tempo.listen(data)
        self._latch.listen(data, self.config.trigger)

    def pull(self) -> float:
        """How far the hand has dragged the record from where it would be, in grooves."""
        if self._age >= SCRATCH_TIME:
            return 0.0
        progress = self._age / SCRATCH_TIME
        reach = self.config.scratch_size * self.pixel_count / self.config.groove_width
        return -reach * float(np.sin(np.pi * 2 * STROKES * progress)) * (1 - progress)

    @override
    def render(self) -> None:
        dt = frame_step(self.passed)
        self._age += dt
        if self._latch.take(self.now):
            self._age = 0.0
        # Two grooves turn by on each beat of the song
        self._turned += dt / self._tempo.beat_length() * 2

        place = self._x / self.config.groove_width + self._turned + self.pull()
        groove = 0.5 + 0.5 * np.cos(2 * np.pi * place)
        colors = self.get_gradient_color_vectorized1d((place * 0.05) % 1)
        pixels = colors * (0.25 + 0.75 * groove**2)[:, None]
        if self._age < SCRATCH_TIME:
            # The needle shows while the hand is on the record
            middle = (self.pixel_count - 1) / 2
            needle = np.exp(
                -(((self._x - middle) / max(1.0, self.pixel_count * 0.01)) ** 2)
            )
            pixels = pixels + (NEEDLE - pixels) * needle[:, None]
        self.pixels = np.clip(pixels, 0, 255)
