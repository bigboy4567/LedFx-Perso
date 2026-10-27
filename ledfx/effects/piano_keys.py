import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, CoercedInt
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.utils.custom import (
    CUSTOM_CATEGORY,
    FloatArray,
    IntArray,
    frame_step,
    heard_note,
    note_color,
)

KEYS_PER_OCTAVE = 12
# Black keys within an octave, counted from C
BLACK_KEYS = (1, 3, 6, 8, 10)
# Unlit white keys glow faintly so the keyboard stays readable; black keys stay dark
IDLE_WHITE = 0.04


class PianoKeys(AudioReactiveEffect):
    NAME = "Piano Keys"
    CATEGORY = CUSTOM_CATEGORY

    class Config(AudioReactiveEffect.Config):
        octaves: CoercedInt = Field(
            2, description="Octaves of keys along the strip", ge=1, le=4
        )
        lowest_octave: CoercedInt = Field(
            3,
            description="Octave of the first key (middle C starts octave 4)",
            ge=1,
            le=6,
        )
        fold: bool = Field(
            True,
            description="Play notes outside the keyboard on the nearest octave instead of ignoring them",
        )
        decay: CoercedFloat = Field(
            3.0, description="How fast a key fades after its note", ge=0.5, le=15.0
        )
        show_keyboard: bool = Field(
            True, description="Show the unlit keys faintly, white and black"
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._layout(pixel_count)
        self._note: float | None = None

    def _layout(self, pixel_count: int) -> None:
        keys = self.config.octaves * KEYS_PER_OCTAVE
        count = max(1, min(keys, pixel_count))
        edges = np.linspace(0, pixel_count, count + 1).astype(int)
        self._widths: IntArray = np.diff(edges)
        self._levels: FloatArray = np.zeros(count)
        self._colors: FloatArray = np.array(
            [note_color(key) for key in range(count)], dtype=float
        )
        black = np.isin(np.arange(count) % KEYS_PER_OCTAVE, BLACK_KEYS)
        self._idle: FloatArray = np.where(black, 0.0, IDLE_WHITE * 255)

    @override
    def config_updated(self, config: object) -> None:
        pixels = getattr(self, "pixels", None)
        if pixels is not None and hasattr(self, "_levels"):
            self._layout(len(pixels))

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._note = heard_note(data)

    def _key(self, note: float) -> int | None:
        count = self._levels.size
        # MIDI number of the C that starts the lowest octave
        first = (self.config.lowest_octave + 1) * KEYS_PER_OCTAVE
        key = round(note) - first
        if 0 <= key < count:
            return key
        if not self.config.fold:
            return None
        # Same note, moved by whole octaves onto the nearest end of the keyboard
        pitch_class = key % KEYS_PER_OCTAVE
        top_octave = (count - 1) // KEYS_PER_OCTAVE * KEYS_PER_OCTAVE
        key = (top_octave if key >= count else 0) + pitch_class
        # A strip too short for a full octave wraps the notes around what it has
        return key if key < count else key % count

    @override
    def render(self) -> None:
        dt = frame_step(self.passed)
        self._levels *= float(np.exp(-dt * self.config.decay))
        if self._note is not None:
            key = self._key(self._note)
            if key is not None:
                self._levels[key] = 1.0

        lit = self._colors * self._levels[:, None]
        if self.config.show_keyboard:
            lit = np.maximum(lit, self._idle[:, None])
        self.pixels = np.repeat(lit, self._widths, axis=0)
