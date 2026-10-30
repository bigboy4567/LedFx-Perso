import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.utils.corsair import CORSAIR_CATEGORY, ram_layout
from ledfx.effects.utils.custom import (
    FloatArray,
    PeakTracker,
    color_array,
    frame_step,
)

# Each stick shows a band from bass to treble; between the three measured bands
# the inner sticks blend their neighbours
BAND_MIX = np.array(
    ((1.0, 0.0, 0.0), (0.5, 0.5, 0.0), (0.0, 0.5, 0.5), (0.0, 0.0, 1.0))
)
PEAK_FALL = 0.5


class RamMeter(AudioReactiveEffect):
    NAME = "RAM Meter"
    CATEGORY = CORSAIR_CATEGORY

    class Config(AudioReactiveEffect.Config):
        response: CoercedFloat = Field(
            15.0, description="How quickly the sticks follow the music", ge=2.0, le=40.0
        )
        peaks: bool = Field(True, description="A dot marks each stick's recent peak")
        bottom_color: Color = Field(
            "#00FF40", description="Color at the bottom of the sticks"
        )
        middle_color: Color = Field(
            "#FFD000", description="Color part way up the sticks"
        )
        top_color: Color = Field(
            "#FF1000", description="Color at the top of the sticks"
        )
        peak_color: Color = Field("#FFFFFF", description="Color of the peak dots")

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._ram = ram_layout(pixel_count)
        sticks = self._ram.sticks
        self.levels: FloatArray = np.zeros(sticks)
        self._targets: FloatArray = np.zeros(sticks)
        self._peaks_shown: FloatArray = np.zeros(sticks)
        self._peaks = PeakTracker(3)

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        bands = np.array(
            (data.lows_power(), data.mids_power(), data.high_power()), dtype=float
        )
        level = np.clip(self._peaks.update(bands), 0, 1)
        mix = BAND_MIX[np.round(np.linspace(0, 3, self._ram.sticks)).astype(int)]
        self._targets = mix @ level

    @override
    def config_updated(self, config: object) -> None:
        self._bottom = color_array(self.config.bottom_color)
        self._middle = color_array(self.config.middle_color)
        self._top = color_array(self.config.top_color)
        self._peak = color_array(self.config.peak_color)

    @override
    def render(self) -> None:
        dt = frame_step(self.passed)
        self.levels += (self._targets - self.levels) * min(
            1.0, dt * self.config.response
        )
        self._peaks_shown = np.maximum(self.levels, self._peaks_shown - PEAK_FALL * dt)

        ram = self._ram
        height = ram.height
        level = self.levels[ram.stick]
        # The bottom color, blending into the middle one, then into the top one
        low = np.clip(height / 0.6, 0, 1)[:, None]
        high = np.clip((height - 0.6) / 0.4, 0, 1)[:, None]
        colors = (
            self._bottom
            + (self._middle - self._bottom) * low
            + (self._top - self._middle) * high
        )
        lit = height <= level + 1e-9
        pixels = colors * np.where(lit, 1.0, 0.04)[:, None]
        if self.config.peaks:
            # The LED of each stick nearest its recent peak
            shown = self._peaks_shown[ram.stick]
            distance = np.abs(height - shown)
            nearest = np.full(ram.sticks, np.inf)
            np.minimum.at(nearest, ram.stick, distance)
            peak = (distance == nearest[ram.stick]) & (shown > 0.05)
            pixels = np.where(peak[:, None], self._peak, pixels)
        self.pixels = pixels
