import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, mat_layout
from ledfx.effects.utils.custom import hue_colors

# The mood's hue runs from red for the bass to blue for the treble
BASS_HUE = 0.0
TREBLE_HUE = 0.66
PULSE = 5.0


class MouseMood(CorsairEffect):
    NAME = "Mouse Mood"

    class Config(CorsairEffect.Config):
        response: CoercedFloat = Field(
            1.5, description="How quickly the mood follows the music", ge=0.2, le=10.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._mouse = mat_layout(pixel_count).mouse
        self.mood = 0.33
        self._pulse = 0.0

    @override
    def render(self) -> None:
        dt = self.step()
        self._pulse *= float(np.exp(-dt * PULSE))
        if self.beat():
            self._pulse = 1.0
        lows, _, highs = self.levels
        # Red when the bass leads, blue when the treble does, green in between
        balance = (highs - lows) / max(lows + highs, 0.05)
        target = BASS_HUE + (TREBLE_HUE - BASS_HUE) * (0.5 + 0.5 * balance)
        self.mood += (target - self.mood) * min(1.0, dt * self.config.response)
        size = self._mouse.size
        mouse = hue_colors(np.full(size, self.mood)) * (0.3 + 0.7 * self.loudness)
        # The pad glows in the opposite color, swelling on each beat
        pad = hue_colors(np.full(size, (self.mood + 0.5) % 1)) * (
            0.1 + 0.3 * self._pulse
        )
        self.pixels = np.where(self._mouse[:, None], mouse, pad)
