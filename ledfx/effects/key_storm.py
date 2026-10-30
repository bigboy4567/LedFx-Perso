import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import (
    BAR,
    KEYBOARD_DEPTH,
    CorsairEffect,
    keyboard_layout,
)
from ledfx.effects.utils.custom import FloatArray, color_array

# A bolt zigzags down the board in this many steps, this far across at most each step
BOLT_STEPS = 8
ZIGZAG = 0.04
# The keys this close to the bolt light up, fully within half of it
BOLT_WIDTH = 0.04
# A flash dies this quickly, and flickers again this long after
FLASH = 10.0
FLICKER = 0.08
WHITE = np.array((255.0, 255.0, 255.0))


class KeyStorm(CorsairEffect):
    NAME = "Key Storm"

    class Config(CorsairEffect.Config):
        cloud_color: Color = Field("#28307A", description="Color of the storm clouds")

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        board = keyboard_layout(pixel_count)
        self._x: FloatArray = board.x
        self._y: FloatArray = board.y * KEYBOARD_DEPTH
        self._bar = board.zone == BAR
        self._bolt: FloatArray = np.zeros(pixel_count)
        self.flash = 0.0
        self._again = np.inf
        self._time = 0.0

    @override
    def config_updated(self, config: object) -> None:
        self._cloud = color_array(self.config.cloud_color)

    def _strike(self) -> None:
        """Draw a new bolt from the light bar to the front of the board."""
        steps = np.linspace(0, KEYBOARD_DEPTH, BOLT_STEPS + 1)
        across = (
            0.1
            + self._rng.random() * 0.8
            + np.cumsum(self._rng.uniform(-ZIGZAG, ZIGZAG, BOLT_STEPS + 1))
        )
        # The bolt's path, finely, so every key along it is caught
        fine = np.linspace(0, KEYBOARD_DEPTH, 60)
        path = np.interp(fine, steps, across)
        distance = np.hypot(self._x[:, None] - path, self._y[:, None] - fine).min(
            axis=1
        )
        # Full on the keys it runs through, fading on the ones beside them
        self._bolt = np.clip(2 - 2 * distance / BOLT_WIDTH, 0, 1)

    @override
    def render(self) -> None:
        dt = self.step()
        self._time += dt
        self.flash *= float(np.exp(-dt * FLASH))
        self._again -= dt
        # Each percussive hit strikes a bolt, which flickers once more
        if self.hit():
            self._strike()
            self.flash = 1.0
            self._again = FLICKER
        if self._again <= 0:
            self.flash = max(self.flash, 0.7)
            self._again = np.inf
        # The clouds rumble along the light bar and the top rows with the bass
        rumble = 0.5 + 0.5 * np.sin(self._x * 12 + self._time * 1.5)
        clouds = (
            (0.1 + 0.6 * rumble)
            * (0.3 + 0.7 * self.levels[0])
            * (1 - self._y / KEYBOARD_DEPTH * 0.8)
        )
        pixels = self._cloud * clouds[:, None]
        # The bolt lights white, and its flash lights up the clouds
        lit = np.maximum(self._bolt, np.where(self._bar, 0.5, 0.0)) * self.flash
        self.pixels = np.clip(pixels + (WHITE - pixels) * lit[:, None], 0, 255)
