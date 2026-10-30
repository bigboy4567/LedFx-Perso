from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, CoercedInt
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import KEYBOARD_DEPTH, CorsairEffect, keyboard_layout
from ledfx.effects.utils.custom import FloatArray

# Each move is about a key across
STEP = 0.045
# A segment of the snake lights the keys this close to it
BODY = 0.045
SHORTEST = 4
FLASH = 5.0
WHITE = np.array((255.0, 255.0, 255.0))
HEADINGS = np.array(((1.0, 0.0), (0.0, 1.0), (-1.0, 0.0), (0.0, -1.0)))


class KeySnake(CorsairEffect, GradientEffect):
    NAME = "Key Snake"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        moves_per_second: CoercedFloat = Field(
            8.0,
            description="Keys the snake moves a second at full volume",
            ge=2.0,
            le=30.0,
        )
        longest: CoercedInt = Field(
            20,
            description="How long the snake grows before it starts again",
            ge=6,
            le=40,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        board = keyboard_layout(pixel_count)
        self._x: FloatArray = board.x
        self._y: FloatArray = board.y * KEYBOARD_DEPTH
        # The snake keeps between the light bar and the front row
        self._top, self._bottom = (
            (float(self._y.min()), float(self._y.max())) if self._y.size else (0.0, 0.0)
        )
        # The snake's segments, the head first
        self.body: FloatArray = np.array(
            [[0.5, float(np.median(self._y)) if self._y.size else 0.0]]
        )
        self._heading = 0
        self.length = SHORTEST
        self._due = 0.0
        self._flash = 0.0

    def _move(self) -> None:
        # Now and then the snake turns; at the edge of the board it must
        if self._rng.random() < 0.15:
            self._heading = (self._heading + self._rng.choice((1, 3))) % 4
        for _ in range(4):
            head = self.body[0] + HEADINGS[self._heading] * STEP
            if 0 <= head[0] <= 1 and self._top - 1e-9 <= head[1] <= self._bottom + 1e-9:
                break
            self._heading = (self._heading + self._rng.choice((1, 3))) % 4
        else:
            head = self.body[0]
        self.body = np.concatenate(([head], self.body))[: self.length]

    @override
    def render(self) -> None:
        dt = self.step()
        self._flash *= float(np.exp(-dt * FLASH))
        # Each beat it grows; once it is as long as it gets, it flashes and starts again
        if self.beat():
            self.length += 1
            if self.length > self.config.longest:
                self.length = SHORTEST
                self.body = self.body[:SHORTEST]
                self._flash = 1.0
        self._due += dt * self.config.moves_per_second * (0.3 + 0.7 * self.loudness)
        for _ in range(min(int(self._due), 10)):
            self._move()
        self._due -= int(self._due)
        segments = len(self.body)
        distance = np.hypot(
            self._x[:, None] - self.body[:, 0], self._y[:, None] - self.body[:, 1]
        )
        # The head is brightest, the tail fades
        fade = 1 - 0.7 * np.arange(segments) / max(segments, 1)
        near = np.clip(1 - distance / BODY, 0, 1) * fade
        level = near.max(axis=1)
        nearest = near.argmax(axis=1)
        colors = self.get_gradient_color_vectorized1d(
            nearest / max(segments - 1, 1) * 0.999
        )
        pixels = colors * np.maximum(level, 0.02)[:, None]
        self.pixels = pixels + (WHITE - pixels) * self._flash * 0.6
