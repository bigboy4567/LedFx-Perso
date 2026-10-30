import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedInt
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, aio_layout, pump_turn, ring_gap
from ledfx.effects.utils.custom import FloatArray, hue_colors

NOTES = 12
# How fast a note's light fades once it is no longer heard
FADE = 1.5
DIM = 0.05


class PumpNoteWheel(CorsairEffect):
    NAME = "Pump Note Wheel"

    class Config(CorsairEffect.Config):
        top_led: CoercedInt = Field(
            0,
            description="Which LED of the pump's ring is at the top, where C sits",
            ge=0,
            le=15,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._aio = aio_layout(pixel_count)
        # How brightly each of the twelve notes still glows
        self._glow: FloatArray = np.zeros(NOTES)

    @override
    def render(self) -> None:
        self._glow *= float(np.exp(-self.step() * FADE))
        heard = self.heard
        if heard is not None:
            note = round(heard) % NOTES
            self._glow[note] = max(self._glow[note], 0.4 + 0.6 * self.loudness)

        aio = self._aio
        # The twelve notes round the wheel, C at the top, each in its own hue
        place = pump_turn(aio, self.config.top_led) * NOTES
        nearest = np.round(place).astype(int) % NOTES
        sharpness = np.clip(1 - ring_gap(place / NOTES, nearest / NOTES) * NOTES, 0, 1)
        hues = nearest / NOTES
        level = np.maximum(DIM, self._glow[nearest] * sharpness)
        pump = hue_colors(hues) * level[:, None]
        # The radiator fans show the loudest note's color
        loudest = int(np.argmax(self._glow))
        fans = hue_colors(np.full(aio.angle.size, loudest / NOTES)) * max(
            DIM, float(self._glow[loudest])
        )
        self.pixels = np.where(aio.pump[:, None], pump, fans)
