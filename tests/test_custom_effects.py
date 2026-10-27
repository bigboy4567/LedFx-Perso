"""The Custom category: every effect renders sane frames and does what it says."""

import typing
from typing import Protocol, cast
from unittest.mock import MagicMock

import numpy as np
import pytest
from numpy.typing import NDArray

from ledfx.effects import Effect
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.charge_up import ChargeUp
from ledfx.effects.color_jump import ColorJump
from ledfx.effects.confetti import Confetti
from ledfx.effects.drum_pads import DrumPads
from ledfx.effects.fireflies import Fireflies
from ledfx.effects.heartbeat import Heartbeat
from ledfx.effects.interference import Interference
from ledfx.effects.kaleidoscope import Kaleidoscope
from ledfx.effects.phone_paint import PhonePaint
from ledfx.effects.piano_keys import PianoKeys
from ledfx.effects.police_lights import PoliceLights
from ledfx.effects.section_strobe import SectionStrobe
from ledfx.effects.sound_locator import SoundLocator
from ledfx.effects.tug_of_war import TugOfWar
from ledfx.effects.utils.custom import CUSTOM_CATEGORY, BeatLatch, note_color

CUSTOM_EFFECTS: list[type[AudioReactiveEffect]] = [
    SectionStrobe,
    Heartbeat,
    Fireflies,
    PoliceLights,
    TugOfWar,
    Confetti,
    Kaleidoscope,
    ColorJump,
    Interference,
    ChargeUp,
    PianoKeys,
    DrumPads,
    SoundLocator,
]
# Custom effects that do not listen to the music, tested in their own files
QUIET_CUSTOM_EFFECTS: list[type[Effect]] = [PhonePaint]
FPS = 60


class FakeAudio:
    """The slice of AudioAnalysisSource the Custom effects read."""

    def __init__(
        self,
        beat: bool = False,
        onset: bool = False,
        lows: float = 0.5,
        mids: float = 0.5,
        highs: float = 0.5,
        bar: float = 0.0,
        pitch: float = 0.0,
        wave: NDArray[np.float64] | None = None,
    ) -> None:
        self.beat = beat
        self.hit = onset
        self.lows = lows
        self.mids = mids
        self.highs = highs
        self.bar = bar
        self.note = pitch
        # One analysis frame of a 220 Hz tone, unless a wave is given
        self.wave = wave if wave is not None else 0.3 * np.sin(np.arange(735) * 0.0313)

    def volume_beat_now(self) -> bool:
        return self.beat

    def onset(self) -> bool:
        return self.hit

    def lows_power(self, filtered: bool = True) -> float:
        return self.lows

    def mids_power(self, filtered: bool = True) -> float:
        return self.mids

    def high_power(self, filtered: bool = True) -> float:
        return self.highs

    def volume(self, filtered: bool = True) -> float:
        return (self.lows + self.mids + self.highs) / 3

    def bar_oscillator(self) -> float:
        return self.bar

    def beat_power(self, filtered: bool = True) -> float:
        return self.lows

    def bass_power(self, filtered: bool = True) -> float:
        return self.lows

    def pitch(self) -> float:
        return self.note

    def audio_sample(self, raw: bool = False) -> NDArray[np.float64]:
        return self.wave


E = typing.TypeVar("E", bound=AudioReactiveEffect)


class Activatable(Protocol):
    def on_activate(self, pixel_count: int) -> None: ...


def make(cls: type[E], count: int, **config: object) -> E:
    effect = cls(MagicMock(), cls.config_model().model_validate(config))
    # A fixed seed keeps every random effect, and so every test, reproducible
    if "_rng" in vars(effect):
        vars(effect)["_rng"] = np.random.default_rng(0)
    effect.pixels = np.zeros((count, 3))
    # What Effect.activate does, without subscribing to a real audio source.
    # Only the Custom effects themselves define on_activate, none of their bases.
    cast(Activatable, effect).on_activate(count)
    return effect


def frame(
    effect: AudioReactiveEffect, audio: FakeAudio | None = None
) -> NDArray[np.float64]:
    if audio is not None:
        effect.audio_data_updated(cast(AudioAnalysisSource, audio))
    effect.now += 1 / FPS
    effect.passed = 1 / FPS
    effect.render()
    pixels = effect.pixels
    assert pixels is not None
    return pixels


def run(
    effect: AudioReactiveEffect, seconds: float, audio: FakeAudio | None = None
) -> NDArray[np.float64]:
    """Play seconds of frames: the given audio on every frame, or quiet music."""
    pixels = frame(effect, audio or FakeAudio())
    for _ in range(int(seconds * FPS) - 1):
        pixels = frame(effect, audio if audio and not audio.beat else FakeAudio())
    return pixels


def literal_options(cls: type[Effect]) -> list[tuple[str, str]]:
    """Every (field, value) pair of the effect's choice settings."""
    options: list[tuple[str, str]] = []
    for name, field in cls.config_model().model_fields.items():
        if typing.get_origin(field.annotation) is typing.Literal:
            options += [(name, value) for value in typing.get_args(field.annotation)]
    return options


def test_custom_effects_share_their_own_category() -> None:
    assert CUSTOM_CATEGORY not in {
        getattr(cls, "CATEGORY", None)
        for cls in Effect.registry().values()
        if cls not in CUSTOM_EFFECTS and cls not in QUIET_CUSTOM_EFFECTS
    }
    assert {
        getattr(cls, "CATEGORY", None) for cls in CUSTOM_EFFECTS + QUIET_CUSTOM_EFFECTS
    } == {CUSTOM_CATEGORY}


@pytest.mark.parametrize("cls", CUSTOM_EFFECTS, ids=lambda cls: cls.__name__)
@pytest.mark.parametrize("count", [1, 2, 7, 16, 150, 37555])
def test_renders_valid_frames_with_every_option(
    cls: type[AudioReactiveEffect], count: int
) -> None:
    configs: list[dict[str, str]] = [{}]
    configs += [{name: value} for name, value in literal_options(cls)]
    for config in configs:
        effect = make(cls, count, **config)
        lit = False
        for index in range(90):
            hit = index % 15 == 0
            audio = FakeAudio(
                beat=hit,
                onset=hit,
                lows=0.8,
                mids=0.4,
                highs=0.3,
                bar=index / 30 % 4,
                pitch=60 + index % 24,
            )
            pixels = frame(effect, audio)
            assert pixels.shape == (count, 3), config
            assert np.isfinite(pixels).all(), config
            assert pixels.min() >= 0, config
            assert pixels.max() <= 255, config
            lit = lit or pixels.max() > 0
        assert lit, f"{cls.__name__} {config} never lit up"


def test_beat_latch_takes_each_hit_once_and_skips_echoes() -> None:
    latch = BeatLatch()
    latch.listen(cast(AudioAnalysisSource, FakeAudio(beat=True)), "Beat")
    assert latch.take(1.0)
    assert not latch.take(1.01)
    latch.listen(cast(AudioAnalysisSource, FakeAudio(beat=True)), "Beat")
    assert not latch.take(1.02)
    latch.listen(cast(AudioAnalysisSource, FakeAudio(beat=True)), "Percussion")
    assert not latch.take(2.0)


def test_heartbeat_pulses_twice_from_the_center() -> None:
    effect = make(Heartbeat, 101)
    resting = frame(effect).copy()
    pixels = run(effect, 0.05, FakeAudio(beat=True))
    assert pixels[50, 0] > pixels[0, 0]
    assert pixels[50, 0] > resting[50, 0]
    run(effect, 0.2)
    assert np.count_nonzero(effect._ages < 1) == 2
    single = make(Heartbeat, 101, double_beat=False)
    run(single, 0.3, FakeAudio(beat=True))
    assert np.count_nonzero(single._ages < 1) == 1


def test_fireflies_stay_on_the_strip_and_follow_the_count() -> None:
    effect = make(Fireflies, 50, drift=2.0)
    run(effect, 5)
    assert (effect._pos >= 0).all()
    assert (effect._pos <= 49).all()
    effect.update_config({"count": 7})
    assert effect._pos.size == 7


def test_police_lights_take_turns_on_each_beat() -> None:
    effect = make(PoliceLights, 100, mode="Flash")
    first = frame(effect, FakeAudio(bar=0.0))
    second = frame(effect, FakeAudio(bar=1.0))
    # Red on the first beat, blue on the next
    assert first[:50, 0].max() > 0
    assert first[50:].max() == 0
    assert second[:50].max() == 0
    assert second[50:, 2].max() > 0


def test_tug_of_war_front_follows_the_louder_band() -> None:
    fronts = []
    for lows, highs in ((1.0, 0.1), (0.1, 1.0)):
        effect = make(TugOfWar, 100)
        # Each band is measured against its own recent peak: set both peaks first
        run(effect, 1, FakeAudio(lows=1.0, highs=1.0))
        run(effect, 1, FakeAudio(lows=lows, highs=highs))
        fronts.append(effect._front)
    assert fronts[0] > 0.6
    assert fronts[1] < 0.4


def test_confetti_bursts_on_hits_and_fades() -> None:
    effect = make(
        Confetti, 300, trigger="Percussion", sparkles_per_hit=10, twinkle=False
    )
    pixels = frame(effect, FakeAudio(onset=True))
    assert 0 < np.count_nonzero(pixels.max(axis=1)) <= 10
    pixels = run(effect, 3)
    assert pixels.max() < 1


def brightest(pixels: NDArray[np.float64]) -> int:
    return int(np.argmax(pixels.sum(axis=1)))


def test_kaleidoscope_repeats_in_mirrored_copies() -> None:
    effect = make(Kaleidoscope, 60, mirrors=6)
    pixels = run(effect, 0.5)
    # Copies two apart run the same way and match exactly
    np.testing.assert_allclose(pixels[0:10], pixels[20:30])
    # Neighbouring copies are mirror images of each other
    np.testing.assert_allclose(pixels[1:10], pixels[19:10:-1])


def test_color_jump_moves_along_the_gradient_on_each_beat() -> None:
    effect = make(ColorJump, 50, jump=0.25, floor=0.3)
    calm = run(effect, 1).copy()
    hue = effect._hue
    hit = frame(effect, FakeAudio(beat=True))
    assert effect._hue == pytest.approx(hue + 0.25, abs=0.01)
    assert hit.max() > calm.max()


def test_interference_colors_follow_their_bands() -> None:
    bass = run(make(Interference, 100), 1, FakeAudio(lows=1.0, highs=0.0))
    treble = run(make(Interference, 100), 1, FakeAudio(lows=0.0, highs=1.0))
    # The bass wave is pink (red-heavy), the treble wave aqua (green-heavy)
    assert bass[:, 0].sum() > bass[:, 1].sum()
    assert treble[:, 1].sum() > treble[:, 0].sum()


def test_charge_up_builds_and_bursts() -> None:
    effect = make(ChargeUp, 100, charge_per_beat=0.3, leak=0.0)
    run(effect, 0.5, FakeAudio(beat=True, lows=0.5))
    assert effect._charge == pytest.approx(0.3)
    for _ in range(3):
        run(effect, 0.5, FakeAudio(beat=True, lows=0.5))
    assert effect._charge == 0.0
    assert effect._boom > 0


def test_note_color_wheel() -> None:
    np.testing.assert_allclose(note_color(60), (255, 0, 0))
    np.testing.assert_allclose(note_color(72), note_color(60))
    assert not np.allclose(note_color(67), note_color(60))


def test_piano_keys_light_the_note_played() -> None:
    effect = make(PianoKeys, 240, octaves=2, lowest_octave=3, show_keyboard=False)
    # C4 is the first key of the second octave: key 12 of 24, ten pixels each
    pixels = frame(effect, FakeAudio(pitch=60))
    assert np.flatnonzero(pixels.max(axis=1)).tolist() == list(range(120, 130))
    np.testing.assert_allclose(pixels[125], note_color(60))


def test_piano_keys_fold_or_ignore_notes_off_the_keyboard() -> None:
    folded = make(PianoKeys, 24, octaves=2, lowest_octave=3, show_keyboard=False)
    ignored = make(PianoKeys, 24, octaves=2, lowest_octave=3, fold=False)
    # F#6 is above the keyboard: it plays as the F# of the top octave
    assert np.flatnonzero(frame(folded, FakeAudio(pitch=90)).max(axis=1)).tolist() == [
        18
    ]
    keyboard = frame(ignored, FakeAudio()).copy()
    np.testing.assert_allclose(frame(ignored, FakeAudio(pitch=90)), keyboard)


def test_drum_pads_light_the_drum_that_was_hit() -> None:
    effect = make(DrumPads, 90)
    pixels = frame(effect, FakeAudio(beat=True))
    assert pixels[:30].max() > 0
    assert pixels[30:].max() == 0
    pixels = run(effect, 2, FakeAudio(onset=True, lows=0.0, mids=0.0, highs=1.0))
    assert pixels[60:].max() > 0


def test_sound_locator_follows_the_timbre() -> None:
    bass = brightest(
        run(make(SoundLocator, 100), 2, FakeAudio(lows=1.0, mids=0.0, highs=0.0))
    )
    treble = brightest(
        run(make(SoundLocator, 100), 2, FakeAudio(lows=0.0, mids=0.0, highs=1.0))
    )
    assert bass < 30
    assert treble > 75
