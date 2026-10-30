from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import FAN_RIM, CorsairEffect, fan_layout
from ledfx.effects.utils.custom import FloatArray

# Comets at once, at most
MAX_COMETS = 6
# A comet goes this many times round before it burns out, its tail this long, in turns
LAPS = 1.5
TAIL = 0.3
WHITE = np.array((255.0, 255.0, 255.0))


class FanComets(CorsairEffect, GradientEffect):
    NAME = "Fan Comets"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        speed: CoercedFloat = Field(
            1.5, description="Turns a second a comet makes", ge=0.3, le=5.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._fans = fan_layout(pixel_count)
        # Each comet: its fan, where it set off, its heading (1 clockwise), how far it has gone, color
        self._comets: FloatArray = np.zeros((0, 5))

    @override
    def render(self) -> None:
        dt = self.step()
        fans = self._fans
        # Each percussive hit sends a comet round a rim, one way or the other
        if self.hit():
            comet = np.array(
                [
                    [
                        self._rng.integers(fans.count),
                        self._rng.random(),
                        1.0 if self._rng.random() < 0.5 else -1.0,
                        0.0,
                        self._rng.random(),
                    ]
                ]
            )
            self._comets = np.concatenate((self._comets, comet))[-MAX_COMETS:]
        if len(self._comets):
            self._comets[:, 3] += dt * self.config.speed
            self._comets = self._comets[self._comets[:, 3] < LAPS]
        size = fans.angle.size
        pixels = np.zeros((size, 3))
        rim = fans.ring == FAN_RIM
        for fan, start, heading, gone, hue in self._comets:
            head = start + heading * gone
            behind = ((head - fans.angle) * heading) % 1
            on = rim & (fans.fan == fan) & (behind < TAIL)
            # The comet fades as it burns out
            level = np.where(on, 1 - behind / TAIL, 0.0) * (1 - gone / LAPS)
            color = self.get_gradient_color_vectorized1d(np.full(size, hue))
            color = color + (WHITE - color) * (level**6)[:, None]
            np.maximum(pixels, color * level[:, None], out=pixels)
        self.pixels = np.clip(pixels, 0, 255)
