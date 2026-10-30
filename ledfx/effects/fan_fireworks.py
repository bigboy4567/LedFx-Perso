from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import (
    FAN_HUB,
    CorsairEffect,
    fan_layout,
    fan_xy,
    stack_height,
)
from ledfx.effects.utils.custom import FloatArray

# Rockets and bursts at once, at most
MAX_ROCKETS = 3
MAX_BURSTS = 3
# A burst fades over this long
BURST_TIME = 1.0
WHITE = np.array((255.0, 255.0, 255.0))


class FanFireworks(CorsairEffect, GradientEffect):
    NAME = "Fan Fireworks"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        rocket_speed: CoercedFloat = Field(
            1.5, description="Stack heights a rocket climbs a second", ge=0.5, le=5.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        fans = fan_layout(pixel_count)
        self._fans = fans
        x, _ = fan_xy(fans)
        self._middle = np.abs(x) < 0.3
        self._height: FloatArray = stack_height(fans)
        self._sparkle: FloatArray = self._rng.random(pixel_count)
        # Each rocket: the fan it bursts in, its height up the stack, and its color
        self._rockets: FloatArray = np.zeros((0, 3))
        # Each burst: its fan, its age, and its color
        self._bursts: FloatArray = np.zeros((0, 3))

    def _centre(self, fan: float) -> float:
        """How high up the stack the middle of a fan is."""
        count = self._fans.count
        return (count - 1 - fan + 0.5) / count

    @override
    def render(self) -> None:
        dt = self.step()
        fans = self._fans
        # Each beat a rocket climbs up the middle of the stack and bursts in a fan
        if self.beat():
            rocket = np.array(
                [[self._rng.integers(fans.count), 0.0, self._rng.random()]]
            )
            self._rockets = np.concatenate((self._rockets, rocket))[-MAX_ROCKETS:]
        if len(self._rockets):
            self._rockets[:, 1] += dt * self.config.rocket_speed
            burst = np.array(
                [height >= self._centre(fan) for fan, height, _ in self._rockets]
            )
            if burst.any():
                new = self._rockets[burst].copy()
                new[:, 1] = 0.0
                self._bursts = np.concatenate((self._bursts, new))[-MAX_BURSTS:]
            self._rockets = self._rockets[~burst]
        if len(self._bursts):
            self._bursts[:, 1] += dt
            self._bursts = self._bursts[self._bursts[:, 1] < BURST_TIME]
        self._sparkle = (self._sparkle + dt * 4) % 1

        size = self._height.size
        pixels = np.zeros((size, 3))
        for _, height, _ in self._rockets:
            near = self._middle * np.clip(
                1 - np.abs(self._height - height) / 0.08, 0, 1
            )
            np.maximum(pixels, WHITE * 0.8 * near[:, None], out=pixels)
        hub = fans.ring == FAN_HUB
        for fan, age, hue in self._bursts:
            mine = fans.fan == fan
            # The hub flashes white, then the sparks fly out to the rim and twinkle away
            flash = np.where(mine & hub, np.exp(-age * 8), 0.0)
            twinkle = 0.5 + 0.5 * (self._sparkle > 0.4)
            sparks = np.where(
                mine & ~hub & (age > 0.05), twinkle * (1 - age / BURST_TIME), 0.0
            )
            color = self.get_gradient_color_vectorized1d(np.full(size, hue))
            np.maximum(pixels, color * sparks[:, None], out=pixels)
            np.maximum(pixels, WHITE * flash[:, None], out=pixels)
        self.pixels = pixels
