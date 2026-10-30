import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import KEYBOARD_DEPTH, CorsairEffect, keyboard_layout
from ledfx.effects.utils.custom import FloatArray, color_array

# Blips on the screen at once, at most
MAX_BLIPS = 8
# The sweep leaves an afterglow this long behind it, as a share of a turn
AFTERGLOW = 0.25
# A blip lights the keys within this distance of it, as a share of the board's width
BLIP_SIZE = 0.05
BLIP = color_array("#FF3030")


class KeyRadar(CorsairEffect):
    NAME = "Key Radar"

    class Config(CorsairEffect.Config):
        color: Color = Field("#20FF60", description="Color of the radar sweep")
        turns_per_bar: CoercedFloat = Field(
            1.0, description="Turns of the sweep per bar of the song", ge=0.25, le=4.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        board = keyboard_layout(pixel_count)
        self._x: FloatArray = board.x
        self._y: FloatArray = board.y * KEYBOARD_DEPTH
        # Each key's bearing from the middle of the board, 0 to 1 clockwise from straight up
        across = self._x - 0.5
        up = 0.5 * KEYBOARD_DEPTH - self._y
        self._bearing: FloatArray = np.arctan2(across, up) / (2 * np.pi) % 1
        self._sweep = 0.0
        # Each blip: where it is across and down the board, and how bright it still is
        self._blips: FloatArray = np.zeros((0, 3))

    @override
    def config_updated(self, config: object) -> None:
        self._color = color_array(self.config.color)

    @override
    def render(self) -> None:
        dt = self.step()
        before = self._sweep
        self._sweep = (
            self._sweep + self.song_moved() / 4 * self.config.turns_per_bar + dt * 0.02
        ) % 1
        if self.hit():
            blip = np.array(
                [[self._rng.random(), self._rng.random() * KEYBOARD_DEPTH, 0.0]]
            )
            self._blips = np.concatenate((self._blips, blip))[-MAX_BLIPS:]
        if len(self._blips):
            # A blip lights up when the sweep passes over its bearing, then fades
            bearings = np.arctan2(
                self._blips[:, 0] - 0.5, 0.5 * KEYBOARD_DEPTH - self._blips[:, 1]
            )
            bearings = bearings / (2 * np.pi) % 1
            passed = ((bearings - before) % 1) <= ((self._sweep - before) % 1)
            self._blips[passed, 2] = 1.0
            self._blips[:, 2] *= float(np.exp(-dt * 1.5))

        behind = (self._sweep - self._bearing) % 1
        trail = np.where(behind < AFTERGLOW, (1 - behind / AFTERGLOW) ** 2, 0.0)
        pixels = self._color * (0.04 + 0.96 * trail)[:, None]
        for x, y, glow in self._blips:
            near = (
                np.clip(1 - np.hypot(self._x - x, self._y - y) / BLIP_SIZE, 0, 1) * glow
            )
            np.maximum(pixels, BLIP * near[:, None], out=pixels)
        self.pixels = pixels
