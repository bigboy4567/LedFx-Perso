from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, aio_layout
from ledfx.effects.utils.custom import FloatArray

# Comets at once, at most
MAX_COMETS = 5
# A comet goes this many times round before it burns out, its tail this long, in turns
LAPS = 2.0
TAIL = 0.3
FLASH = 6.0
WHITE = np.array((255.0, 255.0, 255.0))


class PumpComets(CorsairEffect, GradientEffect):
    NAME = "Pump Comets"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        speed: CoercedFloat = Field(
            1.5, description="Turns a second a comet makes", ge=0.3, le=5.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._aio = aio_layout(pixel_count)
        # Each comet: where it set off, its heading (1 clockwise), how far it has gone, its color
        self._comets: FloatArray = np.zeros((0, 4))
        self._launch = 0.0

    @override
    def render(self) -> None:
        dt = self.step()
        self._launch *= float(np.exp(-dt * FLASH))
        # Each percussive hit sends a comet round the ring, and flashes the radiator
        if self.hit():
            comet = np.array(
                [
                    [
                        self._rng.random(),
                        1.0 if self._rng.random() < 0.5 else -1.0,
                        0.0,
                        self._rng.random(),
                    ]
                ]
            )
            self._comets = np.concatenate((self._comets, comet))[-MAX_COMETS:]
            self._launch = 1.0
        if len(self._comets):
            self._comets[:, 2] += dt * self.config.speed
            self._comets = self._comets[self._comets[:, 2] < LAPS]
        aio = self._aio
        size = aio.angle.size
        pixels = np.zeros((size, 3))
        for start, heading, gone, hue in self._comets:
            behind = ((start + heading * gone - aio.angle) * heading) % 1
            level = np.where(aio.pump & (behind < TAIL), 1 - behind / TAIL, 0.0)
            level *= 1 - gone / LAPS
            color = self.get_gradient_color_vectorized1d(np.full(size, hue))
            color = color + (WHITE - color) * (level**6)[:, None]
            np.maximum(pixels, color * level[:, None], out=pixels)
        fans = WHITE * max(0.02, self._launch * 0.7)
        self.pixels = np.clip(np.where(aio.pump[:, None], pixels, fans), 0, 255)
