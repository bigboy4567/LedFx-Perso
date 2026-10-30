import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, mat_height, mat_layout
from ledfx.effects.utils.custom import FloatArray, color_array

# A bolt runs down a side this fast; its flash dies this quickly and flickers again this long after
BOLT_SPEED = 10.0
FLASH = 8.0
FLICKER = 0.1
WHITE = np.array((255.0, 255.0, 255.0))


class MatStorm(CorsairEffect):
    NAME = "Mat Storm"

    class Config(CorsairEffect.Config):
        cloud_color: Color = Field("#28307A", description="Color of the storm clouds")

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        mat = mat_layout(pixel_count)
        self._along: FloatArray = mat.along
        self._height: FloatArray = mat_height(mat)
        self._right = mat.along > 0.5
        self._mouse = mat.mouse
        self._struck_right = False
        self.since = np.inf
        self._time = 0.0

    @override
    def config_updated(self, config: object) -> None:
        self._cloud = color_array(self.config.cloud_color)

    @override
    def render(self) -> None:
        dt = self.step()
        self._time += dt
        self.since += dt
        # Each percussive hit sends a bolt down one side of the pad, from its tip to the mouse
        if self.hit():
            self._struck_right = bool(self._rng.random() < 0.5)
            self.since = 0.0
        churn = 0.5 + 0.5 * np.sin(self._along * 8 + self._time * 1.3)
        clouds = (0.1 + 0.5 * churn) * (0.3 + 0.7 * self.levels[0])
        pixels = self._cloud * clouds[:, None]
        reached = 1 - self.since * BOLT_SPEED
        flash = min(
            1.0,
            np.exp(-self.since * FLASH) + 0.7 * np.exp(-abs(self.since - FLICKER) * 30),
        )
        bolt = (self._right == self._struck_right) & (self._height >= reached)
        # The mouse lights when the bolt reaches the ground
        grounded = reached <= 0
        lit = np.where(
            self._mouse, flash if grounded else 0.0, np.where(bolt, flash, 0.0)
        )
        self.pixels = np.clip(pixels + (WHITE - pixels) * lit[:, None], 0, 255)
