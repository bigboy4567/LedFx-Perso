from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, CoercedInt
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, aio_layout, pump_turn
from ledfx.effects.utils.custom import FloatArray

BANDS = 8
UNLIT = 0.03


class PumpSpectrum(CorsairEffect, GradientEffect):
    NAME = "Pump Spectrum"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        top_led: CoercedInt = Field(
            0, description="Which LED of the pump's ring is at the top", ge=0, le=15
        )
        gain: CoercedFloat = Field(
            1.5, description="How brightly the music lights the bands", ge=0.5, le=5.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._aio = aio_layout(pixel_count)
        self._bands: FloatArray = np.zeros(BANDS)
        self._shown: FloatArray = np.zeros(BANDS)

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        super().audio_data_updated(data)
        bands = self.melbank(filtered=True, size=BANDS)
        self._bands = np.clip(np.asarray(bands, dtype=float) * self.config.gain, 0, 1)

    @override
    def render(self) -> None:
        self._shown += (self._bands - self._shown) * min(1.0, self.step() * 15)
        aio = self._aio
        # Up both sides of the ring, the bass at the bottom, the treble at the top
        height = np.abs(pump_turn(aio, self.config.top_led) - 0.5) * 2
        band = np.minimum((height * BANDS).astype(int), BANDS - 1)
        colors = self.get_gradient_color_vectorized1d(band / (BANDS - 1) * 0.999)
        pump = colors * (UNLIT + (1 - UNLIT) * self._shown[band])[:, None]
        # The first radiator fan fills with the bass, the second with the treble
        level = np.where(aio.fan == 0, self._shown[0], self._shown[-1])
        fans = colors * np.where(aio.angle < level, 1.0, UNLIT)[:, None]
        self.pixels = np.where(aio.pump[:, None], pump, fans)
