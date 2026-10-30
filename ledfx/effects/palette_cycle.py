from typing import Literal

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, CoercedInt
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.utils.custom import (
    CUSTOM_CATEGORY,
    FloatArray,
    TempoTracker,
    color_array,
    frame_step,
    volume_of,
)

# Palettes of old 8-bit and 16-bit art, cycled to make still pictures move
PALETTES: dict[str, tuple[str, ...]] = {
    "Rainbow": ("#FF0000", "#FFFF00", "#00FF00", "#00FFFF", "#0000FF", "#FF00FF"),
    "Fire": ("#200000", "#C00000", "#FF6000", "#FFE040", "#FF6000", "#C00000"),
    "Ice": ("#000830", "#0050C0", "#40C0FF", "#E0FFFF", "#40C0FF", "#0050C0"),
    "Sunset": ("#300040", "#C02060", "#FF7030", "#FFD060", "#FF7030", "#C02060"),
    "Toxic": ("#002000", "#20A000", "#C0FF00", "#20A000", "#002000", "#8000C0"),
}
# Colors in the cycled palette
STEPS = 256

Palette = Literal["Rainbow", "Fire", "Ice", "Sunset", "Toxic"]


class PaletteCycle(AudioReactiveEffect):
    NAME = "Palette Cycle"
    CATEGORY = CUSTOM_CATEGORY

    class Config(AudioReactiveEffect.Config):
        palette: Palette = Field(
            "Rainbow", description="Colors that cycle through the picture"
        )
        bands: CoercedInt = Field(
            4, description="Times the palette repeats along the strip", ge=1, le=20
        )
        cycles_per_bar: CoercedFloat = Field(
            1.0, description="Turns of the palette per bar of the song", ge=0.0, le=4.0
        )
        ripple: CoercedFloat = Field(
            0.3, description="How wavy the picture under the palette is", ge=0.0, le=1.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._u: FloatArray = np.arange(pixel_count) / max(pixel_count - 1, 1)
        self._drift = 0.0
        self._volume = 0.0
        self._tempo = TempoTracker()

    @override
    def config_updated(self, config: object) -> None:
        stops = np.array([color_array(c) for c in PALETTES[self.config.palette]])
        # A cyclic palette: the last color blends back into the first
        positions = np.arange(len(stops) + 1) / len(stops)
        looped = np.concatenate((stops, stops[:1]))
        grid = np.arange(STEPS) / STEPS
        self._lookup: FloatArray = np.stack(
            [np.interp(grid, positions, looped[:, c]) for c in range(3)], axis=1
        )

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._tempo.listen(data)
        self._volume = volume_of(data)

    @override
    def render(self) -> None:
        # The palette turns with the song, and slowly on its own when there is no tempo
        self._drift += frame_step(self.passed) * 0.02
        turn = self._tempo.beats / 4 * self.config.cycles_per_bar + self._drift
        u = self._u
        picture = u * self.config.bands + self.config.ripple * 0.3 * np.sin(
            2 * np.pi * u * 3
        )
        index = ((picture + turn) % 1 * STEPS).astype(int) % STEPS
        self.pixels = self._lookup[index] * (0.6 + 0.4 * min(1.0, self._volume * 2))
