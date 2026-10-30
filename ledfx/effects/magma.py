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
    Trigger,
    color_array,
    frame_step,
    heat_colors,
    splat,
)

# The cooled crust is nearly black, with a dull red glow seeping through
CRUST = color_array("#1A0400")
# A crack burst open by a beat flares this hot, then settles back
FLARE = 1.6
# Chance a beat opens a fresh crack somewhere else instead
NEW_CRACK = 0.25


class Magma(AudioReactiveEffect):
    NAME = "Magma"
    CATEGORY = CUSTOM_CATEGORY

    class Config(AudioReactiveEffect.Config):
        cracks: CoercedInt = Field(14, description="Cracks in the crust", ge=2, le=60)
        heat: CoercedFloat = Field(
            1.0, description="How far the bass opens the cracks", ge=0.0, le=2.0
        )
        trigger: Trigger = Field(
            "Beat", description="Burst a crack on the bass or on every percussive hit"
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._x: FloatArray = np.arange(pixel_count, dtype=float)
        self._u: FloatArray = self._x / max(pixel_count - 1, 1)
        self._crack()
        self._time = 0.0
        self._lows = 0.0
        self._latch = BeatLatch()

    def _crack(self) -> None:
        count = self.config.cracks
        self._at: FloatArray = self._rng.random(count)
        self._widths: FloatArray = self._rng.uniform(0.3, 1.0, count)
        self._glow: FloatArray = np.ones(count)

    @override
    def config_updated(self, config: object) -> None:
        if not hasattr(self, "_rng"):
            self._rng = np.random.default_rng()
        if hasattr(self, "_at") and self._at.size != self.config.cracks:
            self._crack()

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._lows = float(data.lows_power())
        self._latch.listen(data, self.config.trigger)

    @override
    def render(self) -> None:
        dt = frame_step(self.passed)
        self._time += dt
        self._glow += (1 - self._glow) * min(1.0, dt * 2)
        if self._latch.take(self.now):
            crack = int(self._rng.integers(self._at.size))
            if self._rng.random() < NEW_CRACK:
                self._at[crack] = self._rng.random()
            self._glow[crack] = FLARE

        n = self.pixel_count
        opening = 0.3 + 0.7 * min(1.0, self._lows * self.config.heat)
        heat = np.zeros(n)
        base_width = max(0.6, n / 150)
        for at, width, glow in zip(self._at, self._widths, self._glow, strict=True):
            splat(
                heat,
                self._x,
                float(at) * (n - 1),
                base_width * width * (0.5 + opening),
                float(glow * opening * 0.75),
            )
        # The molten rock below churns slowly, seeping a dull glow through the crust
        seep = 0.06 + 0.04 * np.sin(
            2 * np.pi * (self._u * 3 + self._time * 0.07)
        ) * np.sin(2 * np.pi * (self._u * 7 - self._time * 0.05))
        pixels = np.maximum(
            heat_colors(heat),
            CRUST + 255 * np.clip(seep, 0, 1)[:, None] * np.array((1.0, 0.15, 0.0)),
        )
        self.pixels = np.clip(pixels, 0, 255)
