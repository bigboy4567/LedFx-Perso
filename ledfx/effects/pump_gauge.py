from typing import Literal

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.utils.corsair import CORSAIR_CATEGORY, aio_layout
from ledfx.effects.utils.custom import (
    BeatLatch,
    FloatArray,
    Trigger,
    color_array,
    frame_step,
    volume_of,
)

GREEN = color_array("#00FF40")
YELLOW = color_array("#FFD000")
RED = color_array("#FF1000")
WHITE = np.array((255.0, 255.0, 255.0))
# The gauge stays faintly lit beyond the level
EMPTY = 0.05
PEAK_FALL = 0.3

Start = Literal["From the bottom", "From the top"]


class PumpGauge(AudioReactiveEffect):
    NAME = "Pump Gauge"
    CATEGORY = CORSAIR_CATEGORY

    class Config(AudioReactiveEffect.Config):
        start: Start = Field(
            "From the bottom", description="Where on the pump's ring the gauge starts"
        )
        sensitivity: CoercedFloat = Field(
            1.5, description="How far the music fills the gauge", ge=0.5, le=4.0
        )
        trigger: Trigger = Field(
            "Beat",
            description="Flash the radiator fans on the bass or on every percussive hit",
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._aio = aio_layout(pixel_count)
        self.level = 0.0
        self._peak = 0.0
        self._flash = 0.0
        self._beats = 0
        self._flashing = 0
        self._volume = 0.0
        self._latch = BeatLatch()

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._volume = volume_of(data)
        self._latch.listen(data, self.config.trigger)

    def _gauge_colors(self, along: FloatArray) -> FloatArray:
        # Green, then yellow, then red toward the top of the scale
        low = np.clip(along / 0.6, 0, 1)[:, None]
        high = np.clip((along - 0.6) / 0.4, 0, 1)[:, None]
        return GREEN + (YELLOW - GREEN) * low + (RED - YELLOW) * high

    @override
    def render(self) -> None:
        dt = frame_step(self.passed)
        target = min(1.0, self._volume * self.config.sensitivity)
        self.level += (target - self.level) * min(1.0, dt * 15)
        self._peak = max(self.level, self._peak - PEAK_FALL * dt)
        self._flash *= float(np.exp(-dt * 6))
        if self._latch.take(self.now):
            self._flash = 1.0
            # The fans take turns, the first one first
            self._flashing = self._beats % 2
            self._beats += 1

        aio = self._aio
        # Half a turn round the ring separates the bottom from the top
        along = (
            aio.angle if self.config.start == "From the top" else (aio.angle + 0.5) % 1
        )
        lit = np.where(along <= self.level, 1.0, EMPTY)
        gauge = self._gauge_colors(along) * lit[:, None]
        peak = np.abs(along - min(self._peak, 0.999)) < 1 / 32
        gauge = np.where(peak[:, None], WHITE, gauge)
        # The fans flash white in turn on the beat
        flashing = (aio.fan == self._flashing).astype(float) * self._flash
        fans = WHITE * (0.08 + 0.92 * flashing)[:, None]
        self.pixels = np.where(aio.pump[:, None], gauge, fans)
