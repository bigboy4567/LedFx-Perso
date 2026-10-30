import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, aio_layout, ring_gap
from ledfx.effects.utils.custom import FloatArray, color_array

# Blips on the screen at once, at most
MAX_BLIPS = 8
# The sweep leaves an afterglow this long behind it, as a share of a turn
AFTERGLOW = 0.3
BLIP = color_array("#FF3030")


class PumpRadar(CorsairEffect):
    NAME = "Pump Radar"

    class Config(CorsairEffect.Config):
        color: Color = Field("#20FF60", description="Color of the radar sweep")
        turns_per_bar: CoercedFloat = Field(
            1.0, description="Turns of the sweep per bar of the song", ge=0.25, le=4.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._aio = aio_layout(pixel_count)
        self._sweep = 0.0
        # Each blip: where round the screen it sits, and how bright it still is
        self._blips: FloatArray = np.zeros((0, 2))

    @override
    def config_updated(self, config: object) -> None:
        self._color = color_array(self.config.color)

    @override
    def render(self) -> None:
        dt = self.step()
        before = self._sweep
        self._sweep = (
            self._sweep + self.song_moved() / 4 * self.config.turns_per_bar + dt * 0.02
        ) % 1
        if self.hit():
            blip = np.array([[self._rng.random(), 0.0]])
            self._blips = np.concatenate((self._blips, blip))[-MAX_BLIPS:]
        if len(self._blips):
            # A blip lights up when the sweep passes over it, then fades
            passed = ((self._blips[:, 0] - before) % 1) <= ((self._sweep - before) % 1)
            self._blips[passed, 1] = 1.0
            self._blips[:, 1] *= float(np.exp(-dt * 1.5))

        aio = self._aio
        behind = (self._sweep - aio.angle) % 1
        trail = np.where(behind < AFTERGLOW, (1 - behind / AFTERGLOW) ** 2, 0.0)
        pixels = self._color * (0.05 + 0.95 * trail)[:, None]
        for at, glow in self._blips:
            near = np.exp(-((ring_gap(aio.angle, at) / 0.04) ** 2)) * glow
            np.maximum(pixels, BLIP * near[:, None], out=pixels)
        # The radiator fans glow faintly green, like the screen's bezel
        self.pixels = np.where(aio.pump[:, None], pixels, self._color * 0.08)
