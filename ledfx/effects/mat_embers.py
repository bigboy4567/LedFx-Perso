import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, mat_layout
from ledfx.effects.utils.custom import FloatArray, heat_colors

EMBERS = 8
# How long an ember is, as a share of the pad's edge
EMBER = 0.06


class MatEmbers(CorsairEffect):
    NAME = "Mat Embers"

    class Config(CorsairEffect.Config):
        drift: CoercedFloat = Field(
            0.1,
            description="How quickly the embers drift round the pad",
            ge=0.0,
            le=1.0,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        mat = mat_layout(pixel_count)
        self._along: FloatArray = mat.along
        self._mouse = mat.mouse
        # Each ember: where it is, which way it drifts, how fast it flickers and its phase
        self._places: FloatArray = self._rng.random(EMBERS)
        self._headings: FloatArray = np.where(self._rng.random(EMBERS) < 0.5, 1.0, -1.0)
        self._rates: FloatArray = 2 + self._rng.random(EMBERS) * 4
        self._phases: FloatArray = self._rng.random(EMBERS) * 2 * np.pi
        self._time = 0.0

    @override
    def render(self) -> None:
        dt = self.step()
        self._time += dt
        self._places = (
            self._places
            + self._headings * dt * self.config.drift * (0.5 + self.loudness)
        ) % 1
        # The bass fans the embers: they glow hotter
        glow = (0.5 + 0.5 * np.sin(self._time * self._rates + self._phases)) * (
            0.4 + 0.6 * self.levels[0]
        )
        heat = np.full(self._along.size, 0.06)
        for place, ember in zip(self._places, glow, strict=True):
            near = np.clip(1 - np.abs(self._along - place) / EMBER, 0, 1)
            np.maximum(heat, near * ember * 0.8, out=heat)
        # The mouse is the coal they rise from
        coal = 0.3 + 0.4 * self.levels[0] * (0.8 + 0.2 * np.sin(self._time * 7))
        self.pixels = heat_colors(np.where(self._mouse, coal, heat))
