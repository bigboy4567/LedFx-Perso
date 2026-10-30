import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.utils.custom import (
    CUSTOM_CATEGORY,
    FloatArray,
    frame_step,
)

# Wavelengths of red, green and blue light, in nanometres, and the oil's refractive index
WAVELENGTHS = np.array((650.0, 532.0, 450.0))
REFRACTION = 1.45


class OilSlick(AudioReactiveEffect):
    NAME = "Oil Slick"
    CATEGORY = CUSTOM_CATEGORY

    class Config(AudioReactiveEffect.Config):
        thickness: CoercedFloat = Field(
            500.0,
            description="Thickness of the film, in nanometres; thicker films show finer colors",
            ge=150.0,
            le=1500.0,
        )
        flow: CoercedFloat = Field(
            0.5, description="How fast the film flows", ge=0.0, le=3.0
        )
        ripple: CoercedFloat = Field(
            0.6, description="How much the bass ripples the film", ge=0.0, le=1.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._u: FloatArray = np.arange(pixel_count) / max(pixel_count - 1, 1)
        self._time = 0.0
        self._ripple = 0.0
        self._lows = 0.0

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._lows = float(data.lows_power())

    def film(self) -> FloatArray:
        """Thickness of the film along the strip, in nanometres."""
        u, t, flow = self._u, self._time, self.config.flow
        swell = 0.6 * np.sin(2 * np.pi * (u * 1.3 + t * 0.05 * flow))
        swell += 0.3 * np.sin(2 * np.pi * (u * 3.7 - t * 0.11 * flow) + 1)
        swell += self._ripple * 0.3 * np.sin(2 * np.pi * (u * 9 - t * 2))
        return self.config.thickness * (1 + 0.5 * swell)

    @override
    def render(self) -> None:
        dt = frame_step(self.passed)
        self._time += dt
        target = self.config.ripple * self._lows
        self._ripple += (target - self._ripple) * min(1.0, dt * 6)
        # Light reflected off the top and the bottom of the film interferes: each
        # thickness lets some colors through and cancels others
        path = 4 * np.pi * REFRACTION * self.film()[:, None] / WAVELENGTHS[None, :]
        intensity = 0.5 + 0.5 * np.cos(path)
        self.pixels = 255 * intensity**2
