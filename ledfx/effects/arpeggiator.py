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
    IntArray,
    TempoTracker,
    frame_step,
    heard_note,
    note_color,
    segment_widths,
)

# The arpeggio climbs the major chord of the note heard: root, third, fifth, octave
CHORD = (0, 4, 7, 12)
# Played from middle C until a note is heard
DEFAULT_NOTE = 60.0

Order = Literal["Up", "Down", "Up and down", "Converge", "Random"]
Rate = Literal["Eighth notes", "Sixteenth notes"]
STEPS_PER_BEAT = {"Eighth notes": 2, "Sixteenth notes": 4}


class Arpeggiator(AudioReactiveEffect):
    NAME = "Arpeggiator"
    CATEGORY = CUSTOM_CATEGORY

    class Config(AudioReactiveEffect.Config):
        steps: CoercedInt = Field(
            8, description="Positions the arpeggio steps through", ge=3, le=16
        )
        order: Order = Field("Up", description="Order of the steps")
        rate: Rate = Field("Sixteenth notes", description="Speed of the steps")
        decay: CoercedFloat = Field(
            8.0, description="How fast a step fades after it plays", ge=1.0, le=30.0
        )
        gap: bool = Field(True, description="Dark pixels between the positions")

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._layout(pixel_count)
        self._step = -1
        self._note = DEFAULT_NOTE
        self._tempo = TempoTracker()

    def _layout(self, pixel_count: int) -> None:
        widths = segment_widths(pixel_count, self.config.steps)
        count = widths.size
        self._slot: IntArray = np.repeat(np.arange(count), widths)
        ends = np.cumsum(widths) - 1
        self._gap = np.zeros(pixel_count, dtype=bool)
        self._gap[ends[widths >= 3]] = True
        self._levels: FloatArray = np.zeros(count)
        self._colors: FloatArray = np.zeros((count, 3))

    @override
    def config_updated(self, config: object) -> None:
        if not hasattr(self, "_rng"):
            self._rng = np.random.default_rng()
        pixels = getattr(self, "pixels", None)
        if pixels is not None and hasattr(self, "_levels"):
            self._layout(len(pixels))

    @override
    def audio_data_updated(self, data: AudioAnalysisSource) -> None:
        self._tempo.listen(data)
        note = heard_note(data)
        if note is not None:
            self._note = note

    def slot(self, step: int) -> int:
        """Which position plays on this step of the arpeggio."""
        count = self._levels.size
        match self.config.order:
            case "Up":
                return step % count
            case "Down":
                return count - 1 - step % count
            case "Up and down":
                cycle = max(1, 2 * count - 2)
                place = step % cycle
                return place if place < count else cycle - place
            case "Converge":
                place = step % count
                return place // 2 if place % 2 == 0 else count - 1 - place // 2
            case "Random":
                return int(self._rng.integers(count))

    @override
    def render(self) -> None:
        self._levels *= float(np.exp(-frame_step(self.passed) * self.config.decay))
        step = int(self._tempo.beats * STEPS_PER_BEAT[self.config.rate])
        if step != self._step:
            self._step = step
            slot = self.slot(step)
            self._levels[slot] = 1.0
            self._colors[slot] = note_color(self._note + CHORD[step % len(CHORD)])

        pixels = (self._colors * self._levels[:, None])[self._slot]
        if self.config.gap:
            pixels[self._gap] = 0
        self.pixels = pixels
