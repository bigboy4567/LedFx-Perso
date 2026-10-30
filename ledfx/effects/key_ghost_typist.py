import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import KEY, CorsairEffect, keyboard_layout
from ledfx.effects.utils.custom import FloatArray, IntArray, color_array

# How quickly a pressed key fades
FADE = 3.0
# A typist's next key is usually close to the last one, this far across the board
REACH = 0.25
WHITE = np.array((255.0, 255.0, 255.0))


class KeyGhostTypist(CorsairEffect):
    NAME = "Key Ghost Typist"

    class Config(CorsairEffect.Config):
        color: Color = Field(
            "#8040FF", description="Color the pressed keys fade through"
        )
        typing_speed: CoercedFloat = Field(
            6.0, description="Keys a second when the music is loud", ge=1.0, le=20.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        board = keyboard_layout(pixel_count)
        self._x: FloatArray = board.x
        self._keys: IntArray = np.flatnonzero(board.zone == KEY)
        self._pressed: FloatArray = np.zeros(pixel_count)
        self._last = int(self._keys[0]) if self._keys.size else 0

    @override
    def config_updated(self, config: object) -> None:
        self._color = color_array(self.config.color)

    def _press(self) -> None:
        keys = self._keys
        if not keys.size:
            return
        # Prefer a key near the last one, as fingers on a keyboard do
        near = keys[np.abs(self._x[keys] - self._x[self._last]) < REACH]
        pool = near if near.size > 1 and self._rng.random() < 0.8 else keys
        self._last = int(self._rng.choice(pool))
        self._pressed[self._last] = 1.0

    @override
    def render(self) -> None:
        dt = self.step()
        self._pressed *= float(np.exp(-dt * FADE))
        # Typing in bursts with the music, and a key struck on every percussive hit
        if self._rng.random() < self.config.typing_speed * self.loudness * dt:
            self._press()
        if self.hit():
            self._press()
        pressed = self._pressed[:, None]
        # A key flashes white as it is struck, then fades through the color
        pixels = self._color * pressed + (WHITE - self._color) * pressed**6
        self.pixels = np.clip(pixels, 0, 255)
