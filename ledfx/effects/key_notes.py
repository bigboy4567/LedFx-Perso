import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, keyboard_layout
from ledfx.effects.utils.custom import FloatArray, IntArray, note_color

NOTES = 12
DIM = 0.03


class KeyNotes(CorsairEffect):
    NAME = "Key Notes"

    class Config(CorsairEffect.Config):
        fade: CoercedFloat = Field(
            1.5,
            description="How quickly a note's column fades once it stops",
            ge=0.3,
            le=6.0,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        board = keyboard_layout(pixel_count)
        # Twelve columns across the board, one for each note from C on the left
        self._note: IntArray = np.minimum((board.x * NOTES).astype(int), NOTES - 1)
        self._colors: FloatArray = np.array([note_color(note) for note in range(NOTES)])
        self.glow: FloatArray = np.zeros(NOTES)

    @override
    def render(self) -> None:
        self.glow *= float(np.exp(-self.step() * self.config.fade))
        heard = self.heard
        if heard is not None:
            note = round(heard) % NOTES
            self.glow[note] = max(self.glow[note], 0.4 + 0.6 * self.loudness)
        level = np.maximum(self.glow[self._note], DIM)
        self.pixels = self._colors[self._note] * level[:, None]
