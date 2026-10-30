from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import FAN_HUB, CorsairEffect, fan_layout
from ledfx.effects.utils.custom import IntArray, color_array

# A pip lights the rim LEDs this close to it, as a share of a turn
PIP = 0.042
# The dice tumble this long before they settle
TUMBLE = 0.25


class FanDice(CorsairEffect, GradientEffect):
    NAME = "Fan Dice"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        six_color: Color = Field("#FFFFFF", description="Color a six lights its hub")

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._fans = fan_layout(pixel_count)
        self._faces: IntArray = np.ones(self._fans.count, dtype=int)
        self._rolled = np.inf

    @override
    def config_updated(self, config: object) -> None:
        self._six = color_array(self.config.six_color)

    @override
    def render(self) -> None:
        self._rolled += self.step()
        fans = self._fans
        # Each beat rolls a die on every fan; they tumble a moment, then settle
        if self.beat():
            self._rolled = 0.0
        if self._rolled < TUMBLE:
            self._faces = self._rng.integers(1, 7, size=fans.count)
        faces = self._faces[fans.fan]
        # The face's pips sit evenly round the rim, from the top
        spots = fans.angle * faces
        pips = np.abs(spots - np.round(spots)) / faces < PIP
        colors = self.get_gradient_color_vectorized1d(
            fans.fan / max(fans.count - 1, 1) * 0.999
        )
        settled = 1.0 if self._rolled >= TUMBLE else 0.5
        rim = colors * np.where(pips, settled, 0.02)[:, None]
        # A six lights its hub
        hub = np.where((faces == 6)[:, None], self._six * settled, colors * 0.08)
        self.pixels = np.where((fans.ring == FAN_HUB)[:, None], hub, rim)
