from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, ram_layout
from ledfx.effects.utils.custom import FloatArray

# Rockets and bursts at once, at most
MAX_ROCKETS = 4
MAX_BURSTS = 4
# A burst lasts this long, spreading this far a second, and its sparks fall this fast
BURST_TIME = 1.2
SPREAD = 0.8
FALL = 0.3
# Sticks are this far apart, as a share of a stick's height
STICK_GAP = 0.35
WHITE = np.array((255.0, 255.0, 255.0))


class RamFireworks(CorsairEffect, GradientEffect):
    NAME = "RAM Fireworks"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        rocket_speed: CoercedFloat = Field(
            2.0, description="Stick heights a rocket climbs a second", ge=0.5, le=6.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._ram = ram_layout(pixel_count)
        # Each rocket: its stick, its height, where it bursts, and its color
        self._rockets: FloatArray = np.zeros((0, 4))
        # Each burst: its stick, its height, its age, and its color
        self._bursts: FloatArray = np.zeros((0, 4))

    @override
    def render(self) -> None:
        dt = self.step()
        ram = self._ram
        # Each beat launches a rocket up a stick
        if self.beat():
            rocket = np.array(
                [
                    [
                        self._rng.integers(ram.sticks),
                        0.0,
                        0.5 + self._rng.random() * 0.45,
                        self._rng.random(),
                    ]
                ]
            )
            self._rockets = np.concatenate((self._rockets, rocket))[-MAX_ROCKETS:]
        if len(self._rockets):
            self._rockets[:, 1] += dt * self.config.rocket_speed
            burst = self._rockets[:, 1] >= self._rockets[:, 2]
            if burst.any():
                new = self._rockets[burst][:, [0, 2, 1, 3]].copy()
                new[:, 2] = 0.0
                self._bursts = np.concatenate((self._bursts, new))[-MAX_BURSTS:]
            self._rockets = self._rockets[~burst]
        if len(self._bursts):
            self._bursts[:, 2] += dt
            self._bursts = self._bursts[self._bursts[:, 2] < BURST_TIME]

        size = ram.height.size
        pixels = np.zeros((size, 3))
        for stick, height, _, _ in self._rockets:
            near = np.where(
                ram.stick == stick,
                np.clip(1 - np.abs(ram.height - height) / 0.12, 0, 1),
                0.0,
            )
            np.maximum(pixels, WHITE * 0.8 * near[:, None], out=pixels)
        for stick, height, age, hue in self._bursts:
            # A ring of sparks spreading out from the burst, sinking as it fades
            distance = np.hypot(
                (ram.stick - stick) * STICK_GAP, ram.height - (height - age * FALL)
            )
            ring = np.exp(-(((distance - age * SPREAD) / 0.1) ** 2)) * (
                1 - age / BURST_TIME
            )
            color = self.get_gradient_color_vectorized1d(np.full(size, hue))
            # Fresh sparks burn white
            color = color + (WHITE - color) * max(0.0, 1 - age * 4)
            np.maximum(pixels, color * ring[:, None], out=pixels)
        self.pixels = np.clip(pixels, 0, 255)
