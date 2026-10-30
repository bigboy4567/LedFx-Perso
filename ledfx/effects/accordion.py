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

# The bellows never squeeze below, or stretch beyond, these shares of their length
SHORTEST, LONGEST = 0.3, 1.6
# A beat squeezes the bellows this hard, in lengths per second
PUSH = 2.5
DAMPING = 0.35


class Accordion(AudioReactiveEffect, GradientEffect):
    NAME = "Accordion"
    CATEGORY = CUSTOM_CATEGORY
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        folds: CoercedInt = Field(
            8,
            description="Folds of the bellows on each side of the middle",
            ge=2,
            le=40,
        )
        squeeze: CoercedFloat = Field(
            0.6, description="How far the bass squeezes the bellows", ge=0.0, le=1.0
        )
        stiffness: CoercedFloat = Field(
            4.0, description="How quickly the bellows spring back", ge=1.0, le=10.0
        )
        trigger: Trigger = Field(
            "Beat", description="Squeeze on the bass or on every percussive hit"
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._distance: FloatArray = np.abs(
            np.arange(pixel_count) - (pixel_count - 1) / 2
        ) / max(pixel_count / 2, 0.5)
        # How far the bellows are from their rest length, and how fast that changes
        self.stretch = 0.0
        self._speed = 0.0
        self._lows = 0.0
        self._latch = BeatLatch()

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._lows = float(data.lows_power())
        self._latch.listen(data, self.config.trigger)

    @override
    def render(self) -> None:
        dt = frame_step(self.passed)
        if self._latch.take(self.now):
            self._speed -= PUSH * self.config.squeeze
        # A spring pulls the bellows toward a length the bass keeps squeezing
        rest = -0.4 * self.config.squeeze * self._lows
        omega = self.config.stiffness * 2
        pull = -(omega**2) * (self.stretch - rest) - 2 * DAMPING * omega * self._speed
        self._speed += pull * dt
        self.stretch += self._speed * dt
        length = float(np.clip(1 + self.stretch, SHORTEST, LONGEST))

        along = self._distance / length
        folds = 0.5 + 0.5 * np.cos(2 * np.pi * along * self.config.folds)
        colors = self.get_gradient_color_vectorized1d(np.clip(along, 0, 1))
        level = np.where(along <= 1, 0.25 + 0.75 * folds**2, 0.0)
        self.pixels = colors * level[:, None]
