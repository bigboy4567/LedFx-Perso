import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedInt, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource
from ledfx.effects.utils.corsair import CorsairEffect, aio_layout, pump_turn, ring_gap
from ledfx.effects.utils.custom import color_array

BANDS = 24
# How wide the needle is, as a share of a turn
NEEDLE = 0.05
# The needle's spring: how hard it is pulled to its heading, and how it is damped
PULL = 40.0
DAMPING = 5.0
WHITE = np.array((255.0, 255.0, 255.0))


class PumpCompass(CorsairEffect):
    NAME = "Pump Compass"

    class Config(CorsairEffect.Config):
        top_led: CoercedInt = Field(
            0, description="Which LED of the pump's ring is at the top", ge=0, le=15
        )
        needle_color: Color = Field("#FF2020", description="Color of the needle's head")

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._aio = aio_layout(pixel_count)
        # Where the needle points, 0 at the top, a quarter turn either way at the ends
        self.needle = 0.0
        self._swing = 0.0
        self._heading = 0.0

    @override
    def config_updated(self, config: object) -> None:
        self._head = color_array(self.config.needle_color)

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        super().audio_data_updated(data)
        bands = np.clip(
            np.asarray(self.melbank(filtered=True, size=BANDS), dtype=float), 0, None
        )
        total = float(bands.sum())
        # West for the bass, north for the mids, east for the treble
        centre = (
            float((bands * np.linspace(0, 1, BANDS)).sum()) / total
            if total > 1e-6
            else 0.5
        )
        self._heading = (centre - 0.5) * 0.5

    @override
    def render(self) -> None:
        dt = self.step()
        self._swing += (
            (self._heading - self.needle) * PULL - self._swing * DAMPING
        ) * dt
        self.needle += self._swing * dt
        aio = self._aio
        place = pump_turn(aio, self.config.top_led)
        head = np.exp(-((ring_gap(place, self.needle) / NEEDLE) ** 2))
        tail = np.exp(-((ring_gap(place, self.needle + 0.5) / NEEDLE) ** 2)) * 0.3
        # Faint marks at the four points of the compass
        marks = (ring_gap(place * 4, np.round(place * 4)) < 0.1) * 0.05
        pump = self._head * head[:, None] + WHITE * np.maximum(tail, marks)[:, None]
        fans = self._head * (0.03 + 0.5 * self.loudness)
        self.pixels = np.clip(np.where(aio.pump[:, None], pump, fans), 0, 255)
