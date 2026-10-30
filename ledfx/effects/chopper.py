from typing import ClassVar, Literal

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
    IntArray,
    Trigger,
    frame_step,
)

Move = Literal["Shuffle", "Reverse", "Swap pairs", "Rotate"]


class Chopper(AudioReactiveEffect, GradientEffect):
    NAME = "Chopper"
    CATEGORY = CUSTOM_CATEGORY
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        slices: CoercedInt = Field(
            8, description="Slices the strip is chopped into", ge=2, le=24
        )
        move: Move = Field(
            "Shuffle",
            description="How the slices are rearranged on each hit, like a chopped break",
        )
        slide_time: CoercedFloat = Field(
            0.12,
            description="Seconds the slices take to slide to their new places",
            ge=0.02,
            le=0.6,
        )
        trigger: Trigger = Field(
            "Beat", description="Chop on the bass or on every percussive hit"
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._u: FloatArray = np.arange(pixel_count) / max(pixel_count, 1)
        count = self.config.slices
        # Which original slice each place shows, before and after the last chop
        self.order: IntArray = np.arange(count)
        self._before: IntArray = self.order.copy()
        self._progress = 1.0
        self._time = 0.0
        self._latch = BeatLatch()

    @override
    def config_updated(self, config: object) -> None:
        if not hasattr(self, "_rng"):
            self._rng = np.random.default_rng()
        if hasattr(self, "order") and self.order.size != self.config.slices:
            self.order = np.arange(self.config.slices)
            self._before = self.order.copy()

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._latch.listen(data, self.config.trigger)

    def chop(self) -> None:
        self._before = self.order.copy()
        match self.config.move:
            case "Shuffle":
                self.order = self._rng.permutation(self.order)
            case "Reverse":
                self.order = self.order[::-1].copy()
            case "Swap pairs":
                swapped = self.order.copy()
                swapped[: len(swapped) // 2 * 2] = (
                    swapped[: len(swapped) // 2 * 2].reshape(-1, 2)[:, ::-1].ravel()
                )
                self.order = swapped
            case "Rotate":
                self.order = np.roll(self.order, 1)
        self._progress = 0.0

    def _content(self, place: FloatArray) -> FloatArray:
        """The unchopped picture: a gradient with bands drifting through it."""
        colors = self.get_gradient_color_vectorized1d((place + self._time * 0.03) % 1)
        bands = 0.55 + 0.45 * np.cos(
            2 * np.pi * (place * self.config.slices * 1.5 - self._time * 0.2)
        )
        return colors * bands[:, None]

    @override
    def render(self) -> None:
        dt = frame_step(self.passed)
        self._time += dt
        if self._latch.take(self.now):
            self.chop()
        self._progress = min(1.0, self._progress + dt / self.config.slide_time)

        count = self.order.size
        place = self._u * count
        slot = np.minimum(place.astype(int), count - 1)
        within = place - slot
        # Each slice slides from where it was taken before to where it is taken now
        eased = 1 - (1 - self._progress) ** 3
        source = self._before[slot] + (self.order[slot] - self._before[slot]) * eased
        self.pixels = self._content((source + within) / count)
