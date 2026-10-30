from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import FAN_HUB, FAN_RIM, CorsairEffect, fan_layout
from ledfx.effects.utils.custom import FloatArray

SHORTEST = 3
LONGEST = 24
FLASH = 5.0
WHITE = np.array((255.0, 255.0, 255.0))


class FanSnake(CorsairEffect, GradientEffect):
    NAME = "Fan Snake"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        steps_per_beat: CoercedFloat = Field(
            3.0,
            description="LEDs the snake moves per beat of the song",
            ge=1.0,
            le=12.0,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        fans = fan_layout(pixel_count)
        self._fans = fans
        rim = fans.ring == FAN_RIM
        # The rims one after the other make the snake's track, counted in rim LEDs
        self._per_fan = max(1, int(np.count_nonzero(rim & (fans.fan == 0))))
        self._track: FloatArray = (fans.fan + fans.angle) * self._per_fan
        self._cells = fans.count * self._per_fan
        self.head = 0.0
        self.length = SHORTEST
        # Where the snake's food sits on the track
        self.food = float(self._rng.integers(self._cells))
        self._flash = 0.0

    @override
    def render(self) -> None:
        dt = self.step()
        self._flash *= float(np.exp(-dt * FLASH))
        before = self.head
        self.head = (
            self.head + self.song_moved() * self.config.steps_per_beat + dt * 1.5
        ) % self._cells
        # Reaching the food makes the snake grow and the hubs flash; the food moves on
        if (self.food - before) % self._cells <= (self.head - before) % self._cells:
            self.length = self.length + 1 if self.length < LONGEST else SHORTEST
            self.food = float(self._rng.integers(self._cells))
            self._flash = 1.0
        fans = self._fans
        behind = (np.floor(self.head) - np.round(self._track)) % self._cells
        body = behind < self.length
        colors = self.get_gradient_color_vectorized1d(
            np.clip(behind / self.length, 0, 1) * 0.999
        )
        level = np.where(body, 1 - 0.7 * behind / self.length, 0.02)
        pixels = colors * level[:, None]
        # The food blinks
        food = np.abs(self._track - self.food) < 0.5
        blink = 0.8 if self.now * 4 % 1 < 0.5 else 0.3
        pixels = np.where((food & ~body)[:, None], WHITE * blink, pixels)
        hub = WHITE * max(0.03, self._flash * 0.8)
        self.pixels = np.where((fans.ring == FAN_HUB)[:, None], hub, pixels)
