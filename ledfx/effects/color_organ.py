from typing import Literal

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, CoercedInt
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.utils.custom import (
    CUSTOM_CATEGORY,
    FloatArray,
    IntArray,
    PeakTracker,
    color_array,
    frame_step,
    segment_widths,
)

# Red lamps for the bass, green for the mids, blue for the treble
LAMPS = np.array([color_array(c) for c in ("#FF0000", "#00FF00", "#0040FF")])
# A filament heats up this fast, per second; how fast it cools is a setting
HEAT_UP = 25.0
# A dim filament glows orange whatever the color of its glass
FILAMENT = color_array("#FF7820")

Layout = Literal["Alternating", "Blocks"]


class ColorOrgan(AudioReactiveEffect):
    NAME = "Color Organ"
    CATEGORY = CUSTOM_CATEGORY

    class Config(AudioReactiveEffect.Config):
        layout: Layout = Field(
            "Alternating",
            description="Alternating: red, green and blue lamps take turns. Blocks: one block per color",
        )
        lamp_width: CoercedInt = Field(
            4, description="Pixels per lamp when alternating", ge=1, le=40
        )
        cool_down: CoercedFloat = Field(
            6.0,
            description="How fast a lamp dims after its band goes quiet. Lower -> lazier bulbs",
            ge=1.0,
            le=30.0,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._layout(pixel_count)
        self._levels: FloatArray = np.zeros(3)
        self._targets: FloatArray = np.zeros(3)
        self._peaks = PeakTracker(3, fade=0.3)

    def _layout(self, pixel_count: int) -> None:
        if self.config.layout == "Blocks":
            widths = segment_widths(pixel_count, 3)
        else:
            lamps = max(1, pixel_count // self.config.lamp_width)
            widths = segment_widths(pixel_count, lamps)
        self._lamp: IntArray = np.repeat(np.arange(widths.size) % 3, widths)
        ends = np.cumsum(widths) - 1
        self._gap = np.zeros(pixel_count, dtype=bool)
        self._gap[ends[widths >= 3]] = True

    @override
    def config_updated(self, config: object) -> None:
        pixels = getattr(self, "pixels", None)
        if pixels is not None and hasattr(self, "_lamp"):
            self._layout(len(pixels))

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        bands = np.array(
            (data.lows_power(), data.mids_power(), data.high_power()), dtype=float
        )
        self._targets = np.clip(self._peaks.update(bands), 0, 1)

    @override
    def render(self) -> None:
        dt = frame_step(self.passed)
        # Bulbs light quickly but fade lazily, like old incandescent lamps
        rate = np.where(self._targets > self._levels, HEAT_UP, self.config.cool_down)
        self._levels += (self._targets - self._levels) * np.minimum(1.0, dt * rate)
        level = self._levels[:, None]
        lamps = LAMPS * level**1.5 + FILAMENT * 0.25 * level * (1 - level)
        pixels = lamps[self._lamp]
        pixels[self._gap] = 0
        self.pixels = np.clip(pixels, 0, 255)
