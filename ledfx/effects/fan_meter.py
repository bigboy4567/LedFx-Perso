from typing import Literal

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.utils.corsair import CORSAIR_CATEGORY, FAN_HUB, fan_layout
from ledfx.effects.utils.custom import (
    FloatArray,
    PeakTracker,
    color_array,
    frame_step,
)

# The rim stays faintly lit beyond the level, so each fan still shows as a ring
EMPTY = 0.06
# The peak tick falls back this fast, in turns per second
PEAK_FALL = 0.4
WHITE = np.array((255.0, 255.0, 255.0))

Order = Literal["Bass at the top", "Treble at the top"]


class FanMeter(AudioReactiveEffect):
    NAME = "Fan Meter"
    CATEGORY = CORSAIR_CATEGORY

    class Config(AudioReactiveEffect.Config):
        bass_color: Color = Field("#FF1E3C", description="Color of the bass fan")
        mids_color: Color = Field("#28FF50", description="Color of the mids fan")
        treble_color: Color = Field("#2878FF", description="Color of the treble fan")
        order: Order = Field(
            "Bass at the top", description="Which band the top fan shows"
        )
        response: CoercedFloat = Field(
            12.0, description="How quickly the rims follow the music", ge=2.0, le=40.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._fans = fan_layout(pixel_count)
        self._levels: FloatArray = np.zeros(3)
        self._targets: FloatArray = np.zeros(3)
        self._peaks_shown: FloatArray = np.zeros(3)
        self._flash: FloatArray = np.zeros(3)
        self._peaks = PeakTracker(3)

    @override
    def config_updated(self, config: object) -> None:
        self._colors: FloatArray = np.array(
            [
                color_array(self.config.bass_color),
                color_array(self.config.mids_color),
                color_array(self.config.treble_color),
            ]
        )

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        bands = np.array(
            (data.lows_power(), data.mids_power(), data.high_power()), dtype=float
        )
        self._targets = np.clip(self._peaks.update(bands), 0, 1)

    @override
    def render(self) -> None:
        dt = frame_step(self.passed)
        rising = self._targets - self._levels > 0.25
        self._levels += (self._targets - self._levels) * min(
            1.0, dt * self.config.response
        )
        # A band that jumps up flashes its hub
        self._flash = np.where(rising, 1.0, self._flash * float(np.exp(-dt * 6)))
        self._peaks_shown = np.maximum(self._levels, self._peaks_shown - PEAK_FALL * dt)

        fans = self._fans
        band = np.minimum(fans.fan, 2)
        if self.config.order == "Treble at the top":
            band = 2 - band
        level = self._levels[band]
        # The rim fills clockwise from the top like a gauge, a white tick at the recent peak
        filled = np.where(fans.angle < level, 1.0, EMPTY)
        tick = np.abs(fans.angle - np.minimum(self._peaks_shown[band], 0.999)) < 1 / 24
        rim = self._colors[band] * filled[:, None]
        rim = np.where(
            tick[:, None] & (self._peaks_shown[band] > 0.05)[:, None], WHITE, rim
        )
        hub = self._colors[band] * (0.2 + 0.8 * self._flash[band])[:, None]
        self.pixels = np.where((fans.ring == FAN_HUB)[:, None], hub, rim)
