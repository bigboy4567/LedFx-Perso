import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import KEYBOARD_DEPTH, CorsairEffect, keyboard_layout
from ledfx.effects.utils.custom import FloatArray, heat_colors

BLOBS = 5
# How big a blob is, as a share of the board's width
BLOB = 0.09


class KeyLavaLamp(CorsairEffect):
    NAME = "Key Lava Lamp"

    class Config(CorsairEffect.Config):
        speed: CoercedFloat = Field(
            0.3, description="How quickly the wax drifts", ge=0.05, le=2.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        board = keyboard_layout(pixel_count)
        self._x: FloatArray = board.x
        self._y: FloatArray = board.y * KEYBOARD_DEPTH
        # Every blob of wax wanders at its own pace across and up and down the board
        self._rates: FloatArray = 0.4 + self._rng.random((BLOBS, 2))
        self._phases: FloatArray = self._rng.random((BLOBS, 2)) * 2 * np.pi
        self._time = 0.0

    @override
    def render(self) -> None:
        # The music warms the lamp, and warm wax moves faster
        self._time += self.step() * self.config.speed * (0.5 + self.loudness)
        waves = 0.5 + 0.45 * np.sin(self._time * self._rates + self._phases)
        across = waves[:, 0]
        down = waves[:, 1] * KEYBOARD_DEPTH
        # The blobs melt into each other where they meet
        distance = np.hypot(self._x[:, None] - across, self._y[:, None] - down)
        wax = (BLOB / np.maximum(distance, 1e-3)) ** 2
        field = np.clip(wax.sum(axis=1), 0, 1)
        heat = 0.1 + 0.65 * field * (0.7 + 0.3 * self.levels[0])
        self.pixels = heat_colors(heat)
