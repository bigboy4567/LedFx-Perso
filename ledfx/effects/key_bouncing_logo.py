import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import KEYBOARD_DEPTH, CorsairEffect, keyboard_layout
from ledfx.effects.utils.custom import FloatArray, hue_colors

# Half the logo's width and height, as shares of the board's width
HALF_WIDTH = 0.07
HALF_HEIGHT = 0.05
FLASH = 3.0
WHITE = np.array((255.0, 255.0, 255.0))


class KeyBouncingLogo(CorsairEffect):
    NAME = "Key Bouncing Logo"

    class Config(CorsairEffect.Config):
        speed: CoercedFloat = Field(
            0.25, description="Board widths the logo travels a second", ge=0.05, le=1.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        board = keyboard_layout(pixel_count)
        self._x: FloatArray = board.x
        self._y: FloatArray = board.y * KEYBOARD_DEPTH
        self.logo: FloatArray = np.array((0.3, KEYBOARD_DEPTH / 2))
        self._heading: FloatArray = np.array((1.0, 0.45))
        self.hue = 0.0
        self.corner = 0.0

    @override
    def render(self) -> None:
        dt = self.step()
        self.corner *= float(np.exp(-dt * FLASH))
        self.logo += self._heading * dt * self.config.speed * (0.5 + self.loudness)
        # Off each edge it bounces and changes color; hitting a corner exactly lights the board
        bounced = 0
        for axis, (low, high) in enumerate(
            (
                (HALF_WIDTH, 1 - HALF_WIDTH),
                (HALF_HEIGHT, max(HALF_HEIGHT, KEYBOARD_DEPTH - HALF_HEIGHT)),
            )
        ):
            if not low <= self.logo[axis] <= high:
                self.logo[axis] = np.clip(self.logo[axis], low, high)
                self._heading[axis] = -self._heading[axis]
                bounced += 1
        if bounced:
            self.hue = (self.hue + 0.17 + self._rng.random() * 0.3) % 1
        if bounced == 2:
            self.corner = 1.0
        inside = (np.abs(self._x - self.logo[0]) <= HALF_WIDTH) & (
            np.abs(self._y - self.logo[1]) <= HALF_HEIGHT
        )
        logo = hue_colors(np.full(self._x.size, self.hue))
        pixels = logo * np.where(inside, 1.0, 0.02)[:, None]
        self.pixels = pixels + (WHITE - pixels) * self.corner * 0.5
