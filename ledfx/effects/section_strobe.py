from typing import ClassVar, Literal

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, CoercedInt, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.custom import (
    CUSTOM_CATEGORY,
    BeatLatch,
    FloatArray,
    IntArray,
    Trigger,
    color_array,
    frame_step,
)

Pattern = Literal["Random", "Chase", "Bounce", "Alternate"]


class SectionStrobe(AudioReactiveEffect, GradientEffect):
    NAME = "Section Strobe"
    CATEGORY = CUSTOM_CATEGORY
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        sections: CoercedInt = Field(
            8, description="Number of sections the strip is split into", ge=2, le=64
        )
        sections_per_beat: CoercedInt = Field(
            1, description="How many sections flash on each beat", ge=1, le=32
        )
        pattern: Pattern = Field(
            "Random",
            description="Which sections flash: random, marching forward, back and forth, or odd/even",
        )
        trigger: Trigger = Field(
            "Beat",
            description="Flash on the beat (bass) or on every percussive hit",
        )
        decay: CoercedFloat = Field(
            12.0,
            description="How fast a flash fades. Higher -> shorter flashes",
            ge=1.0,
            le=40.0,
        )
        strobe_color: Color = Field("#FFFFFF", description="Color of the flashes")
        use_gradient: bool = Field(
            False,
            description="Color each section from the gradient instead of the strobe color",
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        # A strip shorter than the section count gets one pixel per section
        count = max(1, min(self.config.sections, pixel_count))
        edges = np.linspace(0, pixel_count, count + 1).astype(int)
        self._widths: IntArray = np.diff(edges)
        self._levels: FloatArray = np.zeros(count)
        self._last: IntArray = np.empty(0, dtype=int)
        self._cursor = 0
        self._direction = 1
        self._odd = False
        self._latch = BeatLatch()

    @override
    def config_updated(self, config: object) -> None:
        if not hasattr(self, "_rng"):
            self._rng = np.random.default_rng()
        self._color = color_array(self.config.strobe_color)
        # Runs before the first activation too, when there are no pixels yet.
        # Only a new section count needs new boundaries: other settings keep the pattern going.
        pixels = getattr(self, "pixels", None)
        if (
            pixels is not None
            and hasattr(self, "_levels")
            and self._levels.size != max(1, min(self.config.sections, len(pixels)))
        ):
            self.on_activate(len(pixels))

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._latch.listen(data, self.config.trigger)

    def _pick(self) -> IntArray:
        count = self._levels.size
        per_beat = min(self.config.sections_per_beat, count)
        pattern = self.config.pattern
        if pattern == "Alternate":
            self._odd = not self._odd
            return np.arange(int(self._odd), count, 2)
        if pattern == "Chase":
            picked = (self._cursor + np.arange(per_beat)) % count
            self._cursor = (self._cursor + per_beat) % count
            return picked
        if pattern == "Bounce":
            last_start = count - per_beat
            picked = self._cursor + np.arange(per_beat)
            if last_start > 0:
                step = self._cursor + self._direction * per_beat
                if not 0 <= step <= last_start:
                    self._direction = -self._direction
                    step = self._cursor + self._direction * per_beat
                self._cursor = int(np.clip(step, 0, last_start))
            return picked
        # Random: never flash the same section twice in a row when there is a choice
        fresh = np.setdiff1d(np.arange(count), self._last)
        pool = fresh if fresh.size >= per_beat else np.arange(count)
        picked = self._rng.choice(pool, per_beat, replace=False)
        self._last = picked
        return picked

    @override
    def render(self) -> None:
        dt = frame_step(self.passed)
        self._levels *= float(np.exp(-self.config.decay * dt))
        if self._latch.take(self.now):
            self._levels[self._pick()] = 1.0

        level = np.repeat(self._levels, self._widths)[:, None]
        if self.config.use_gradient:
            centers = (np.arange(self._levels.size) + 0.5) / self._levels.size
            colors = np.repeat(
                self.get_gradient_color_vectorized1d(centers), self._widths, axis=0
            )
            self.pixels = colors * level
        else:
            self.pixels = self._color * level
