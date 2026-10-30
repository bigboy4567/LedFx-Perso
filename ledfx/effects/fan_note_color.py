import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import FAN_HUB, CorsairEffect, fan_layout
from ledfx.effects.utils.custom import FloatArray, note_color

# Each new note flashes the hubs, which then fade this fast
FLASH = 5.0
WHITE = np.array((255.0, 255.0, 255.0))


class FanNoteColor(CorsairEffect):
    NAME = "Fan Note Color"

    class Config(CorsairEffect.Config):
        response: CoercedFloat = Field(
            4.0, description="How quickly the color follows the notes", ge=0.5, le=20.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._fans = fan_layout(pixel_count)
        self.color: FloatArray = np.full(3, 60.0)
        self._note = -1
        self._flash = 0.0

    @override
    def render(self) -> None:
        dt = self.step()
        self._flash *= float(np.exp(-dt * FLASH))
        heard = self.heard
        # The fans take the color of the note being played, C red, each semitone further round
        if heard is not None:
            self.color += (note_color(heard) - self.color) * min(
                1.0, dt * self.config.response
            )
            note = round(heard) % 12
            if note != self._note:
                self._note = note
                self._flash = 1.0
        fans = self._fans
        rim = np.tile(self.color * (0.15 + 0.85 * self.loudness), (fans.angle.size, 1))
        hub = self.color + (WHITE - self.color) * self._flash * 0.7
        self.pixels = np.where((fans.ring == FAN_HUB)[:, None], hub, rim)
