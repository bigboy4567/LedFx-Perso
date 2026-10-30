"""The Custom category: every effect renders sane frames and does what it says."""

import typing
from typing import Protocol, cast
from unittest.mock import MagicMock

import numpy as np
import pytest
from numpy.typing import NDArray

from ledfx.effects import Effect
from ledfx.effects.accordion import Accordion
from ledfx.effects.additive_mix import AdditiveMix
from ledfx.effects.afterimage import Afterimage
from ledfx.effects.arpeggiator import Arpeggiator
from ledfx.effects.audio import AudioAnalysisSource, AudioReactiveEffect
from ledfx.effects.aurora import Aurora
from ledfx.effects.beat_counter import BeatCounter
from ledfx.effects.bitcrush import Bitcrush
from ledfx.effects.blacklight import Blacklight
from ledfx.effects.blinders import Blinders
from ledfx.effects.candles import Candles
from ledfx.effects.charge_up import ChargeUp
from ledfx.effects.chopper import Chopper
from ledfx.effects.chorus import Chorus
from ledfx.effects.color_jump import ColorJump
from ledfx.effects.color_organ import ColorOrgan
from ledfx.effects.confetti import Confetti
from ledfx.effects.dance_floor import DanceFloor
from ledfx.effects.dither import Dither
from ledfx.effects.doppler import Doppler
from ledfx.effects.drum_pads import DrumPads
from ledfx.effects.eclipse import Eclipse
from ledfx.effects.fiber_optic import FiberOptic
from ledfx.effects.filter_sweep import FilterSweep
from ledfx.effects.fireflies import Fireflies
from ledfx.effects.flame_jets import FlameJets
from ledfx.effects.freeze import Freeze
from ledfx.effects.god_rays import GodRays
from ledfx.effects.heartbeat import Heartbeat
from ledfx.effects.interference import Interference
from ledfx.effects.jacobs_ladder import JacobsLadder
from ledfx.effects.kaleidoscope import Kaleidoscope
from ledfx.effects.lens_flare import LensFlare
from ledfx.effects.lighthouse import Lighthouse
from ledfx.effects.lightning import Lightning
from ledfx.effects.magma import Magma
from ledfx.effects.neon_sign import NeonSign
from ledfx.effects.oil_slick import OilSlick
from ledfx.effects.overdrive import Overdrive
from ledfx.effects.palette_cycle import PaletteCycle
from ledfx.effects.palette_morph import PaletteMorph
from ledfx.effects.phaser import Phaser
from ledfx.effects.phone_paint import PhonePaint
from ledfx.effects.piano_keys import PianoKeys
from ledfx.effects.police_lights import PoliceLights
from ledfx.effects.polyrhythm import Polyrhythm
from ledfx.effects.rgb_split import RgbSplit
from ledfx.effects.riser import Riser
from ledfx.effects.sandstorm import Sandstorm
from ledfx.effects.section_strobe import SectionStrobe
from ledfx.effects.sidechain_pump import SidechainPump
from ledfx.effects.sound_locator import SoundLocator
from ledfx.effects.stage_wash import StageWash
from ledfx.effects.stutter import Stutter
from ledfx.effects.swell import Swell
from ledfx.effects.synthwave_sun import SynthwaveSun
from ledfx.effects.tape_stop import TapeStop
from ledfx.effects.trance_gate import TranceGate
from ledfx.effects.tug_of_war import TugOfWar
from ledfx.effects.tv_static import TvStatic
from ledfx.effects.utils.custom import (
    CUSTOM_CATEGORY,
    BeatLatch,
    TempoTracker,
    hue_colors,
    note_color,
    segment_widths,
)
from ledfx.effects.vibrating_string import VibratingString
from ledfx.effects.vinyl_scratch import VinylScratch
from ledfx.effects.wagon_wheel import WagonWheel
from ledfx.effects.wobble import Wobble

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
    Lightning,
    Aurora,
    Candles,
    BeatCounter,
    NeonSign,
    VibratingString,
    ColorOrgan,
    Polyrhythm,
    SidechainPump,
    TranceGate,
    Arpeggiator,
    Wobble,
    TapeStop,
    Phaser,
    Bitcrush,
    VinylScratch,
    Riser,
    Stutter,
    Swell,
    FilterSweep,
    Blinders,
    StageWash,
    FlameJets,
    Blacklight,
    DanceFloor,
    LensFlare,
    Lighthouse,
    Doppler,
    JacobsLadder,
    Magma,
    Freeze,
    Eclipse,
    RgbSplit,
    PaletteCycle,
    Accordion,
    PaletteMorph,
    TvStatic,
    Dither,
    AdditiveMix,
    Afterimage,
    SynthwaveSun,
    Chorus,
    Overdrive,
    FiberOptic,
    GodRays,
    OilSlick,
    Sandstorm,
    WagonWheel,
    Chopper,
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


def test_hue_colors_wheel() -> None:
    np.testing.assert_allclose(
        hue_colors(np.array([0.0, 1 / 3, 2 / 3, 1.0])),
        [[255, 0, 0], [0, 255, 0], [0, 0, 255], [255, 0, 0]],
        atol=1e-9,
    )


def test_segment_widths_cover_the_strip() -> None:
    assert segment_widths(10, 3).tolist() == [3, 3, 4]
    assert segment_widths(2, 5).tolist() == [1, 1]


def test_tempo_tracker_counts_beats_from_the_bar_oscillator() -> None:
    tempo = TempoTracker()
    # Two seconds at 150 BPM: the bar oscillator climbs 2.5 beats a second
    for index in range(120):
        tempo.listen(cast(AudioAnalysisSource, FakeAudio(bar=index * 2.5 / 60 % 4)))
    assert tempo.beats == pytest.approx(119 * 2.5 / 60)
    assert tempo.rate == pytest.approx(2.5, rel=0.01)
    assert tempo.beat_length() == pytest.approx(0.4, rel=0.01)


def lit_pixels(pixels: NDArray[np.float64], above: float = 0) -> int:
    return int(np.count_nonzero(pixels.max(axis=1) > above))


def test_lightning_strikes_on_the_beat_and_dies_down() -> None:
    effect = make(Lightning, 200, sky_glow=False)
    assert run(effect, 0.5).max() == 0
    # The main bolt alone covers at least 15% of the strip
    assert lit_pixels(frame(effect, FakeAudio(beat=True))) >= 30
    assert run(effect, 1).max() < 1


def test_aurora_glows_brighter_with_the_mids() -> None:
    quiet = run(make(Aurora, 100, speed=0.0), 3, FakeAudio(mids=0.0)).sum()
    loud = run(make(Aurora, 100, speed=0.0), 3, FakeAudio(mids=1.0)).sum()
    assert loud > quiet * 2


def test_candles_burn_in_separate_flames() -> None:
    red = run(make(Candles, 60, candles=3, beat_flare=False), 1)[:, 0]
    for candle in range(3):
        flame = red[candle * 20 : (candle + 1) * 20]
        # Brightest in the middle of its own space, dark at the edges
        assert 7 <= flame.argmax() <= 12
        assert flame[0] < flame.max() * 0.3


def test_beat_counter_counts_in_binary_and_gray_code() -> None:
    for code, expected in (("Binary", [1, 0, 1, 0]), ("Gray", [1, 1, 1, 0])):
        effect = make(BeatCounter, 40, bits=4, code=code, gap=False)
        for _ in range(5):
            run(effect, 0.2, FakeAudio(beat=True))
        pixels = run(effect, 1)
        bits = [int(pixels[bit * 10 : (bit + 1) * 10].max() > 100) for bit in range(4)]
        assert bits == expected, code


def tube_peaks(pixels: NDArray[np.float64], tubes: int) -> NDArray[np.float64]:
    return pixels.reshape(tubes, -1, 3).max(axis=(1, 2))


def test_neon_sign_tube_stutters_back_on_after_a_beat() -> None:
    effect = make(NeonSign, 50, tubes=5, faulty=0.0)
    steady = tube_peaks(frame(effect, FakeAudio()), 5)
    struck = tube_peaks(frame(effect, FakeAudio(beat=True)), 5)
    assert np.count_nonzero(struck < steady * 0.2) == 1
    assert (tube_peaks(run(effect, 0.5), 5) > steady * 0.8).all()


def test_vibrating_string_rings_after_a_pluck() -> None:
    effect = make(VibratingString, 101, pluck="Center")
    assert run(effect, 0.5).max() <= 255 * 0.05
    frame(effect, FakeAudio(beat=True))
    # Plucked in the middle, a string rings in its odd harmonics only
    assert np.abs(effect._amplitudes[1::2]).max() < 1e-9
    assert effect._amplitudes[0] > 0
    assert run(effect, 0.1).max() > 100
    assert run(effect, 5).max() <= 255 * 0.05


def test_color_organ_lights_each_band_on_its_own_lamps() -> None:
    effect = make(ColorOrgan, 90, layout="Blocks")
    # Each band is measured against its own recent peak: set all three first
    run(effect, 1, FakeAudio(lows=1.0, mids=1.0, highs=1.0))
    pixels = run(effect, 1, FakeAudio(lows=1.0, mids=0.0, highs=0.0))
    assert pixels[:29, 0].min() > 150
    assert pixels[30:].max() < 30


def test_polyrhythm_lanes_pulse_their_own_counts_per_bar() -> None:
    effect = make(Polyrhythm, 60, rhythm="3 against 2", cursor=False)
    pulses = [0, 0]
    # A pulse is a jump in brightness; the first frame is not a jump
    previous = [255.0, 255.0]
    # Four beats a second is one bar a second; about four bars in all
    for index in range(240):
        pixels = frame(effect, FakeAudio(bar=index * 4 / 60 % 4))
        for lane in range(2):
            level = float(pixels[lane * 30 + 15].max())
            if level > previous[lane] * 1.5 + 10:
                pulses[lane] += 1
            previous[lane] = level
    assert pulses == [7, 11]


def test_sidechain_pump_ducks_on_the_kick_and_swells_back() -> None:
    effect = make(SidechainPump, 100, drift=0.0)
    steady = run(effect, 0.5).sum()
    assert frame(effect, FakeAudio(beat=True)).sum() < steady * 0.3
    assert run(effect, 1).sum() == pytest.approx(steady, rel=0.02)


def test_trance_gate_follows_its_pattern() -> None:
    effect = make(TranceGate, 50, pattern="Offbeat", smoothness=0.0)
    # The first sixteenth note of the offbeat pattern is shut, the third open
    effect._tempo.beats = 0.1
    assert frame(effect).max() == 0
    effect._tempo.beats = 0.6
    assert frame(effect).max() > 100


def test_arpeggiator_steps_up_the_chord_of_the_note() -> None:
    effect = make(Arpeggiator, 80, steps=8)
    for step in range(3):
        effect._tempo.beats = step / 4 + 0.01
        frame(effect)
        assert int(np.argmax(effect._levels)) == step
    # Root, then third: middle C, then E
    np.testing.assert_allclose(effect._colors[0], note_color(60))
    np.testing.assert_allclose(effect._colors[1], note_color(64))


def test_wobble_opens_with_the_bass_in_time() -> None:
    effect = make(Wobble, 100, rate="Quarter notes")
    run(effect, 1, FakeAudio(lows=1.0))
    effect._tempo.beats = 0.0
    closed = lit_pixels(frame(effect), above=20)
    effect._tempo.beats = 0.5
    assert lit_pixels(frame(effect), above=20) > closed * 3


def test_tape_stop_winds_down_in_a_break_and_back_up() -> None:
    effect = make(TapeStop, 100, stop_time=0.5)
    silence = FakeAudio(lows=0.0, mids=0.0, highs=0.0)
    run(effect, 2)
    assert effect._speed == 1.0
    run(effect, 1.5, silence)
    assert effect._speed == 0.0
    run(effect, 1)
    assert effect._speed == 1.0


def test_phaser_cuts_dark_notches() -> None:
    notched = frame(make(Phaser, 200, depth=1.0, resonance=0.0), FakeAudio())
    plain = frame(make(Phaser, 200, depth=0.0), FakeAudio())
    assert np.count_nonzero(notched.max(axis=1) < 20) > 10
    assert np.count_nonzero(plain.max(axis=1) < 20) == 0


def test_bitcrush_cuts_the_picture_into_blocks_and_few_colors() -> None:
    crushed = run(make(Bitcrush, 150, crush=1.0), 0.2, FakeAudio(highs=1.0))
    smooth = run(make(Bitcrush, 150, crush=0.0), 0.2, FakeAudio(highs=0.0))
    assert len(np.unique(crushed, axis=0)) * 3 < len(np.unique(smooth, axis=0))


def test_vinyl_scratch_drags_the_record_back_and_forth() -> None:
    effect = make(VinylScratch, 100)
    frame(effect, FakeAudio(beat=True))
    pulls = []
    for _ in range(30):
        frame(effect, FakeAudio())
        pulls.append(effect.pull())
    assert min(pulls) < -1
    assert max(pulls) > 1
    run(effect, 1)
    assert effect.pull() == 0


def test_riser_builds_with_a_rising_song_and_drops() -> None:
    effect = make(Riser, 100)
    run(effect, 30, FakeAudio(lows=0.1, mids=0.1, highs=0.1))
    assert effect.build < 0.2
    for step in range(30):
        level = 0.1 + 0.03 * step
        run(effect, 0.1, FakeAudio(lows=level, mids=level, highs=level))
    assert effect.build > 0.6
    frame(effect, FakeAudio(beat=True, lows=1.0, mids=1.0, highs=1.0))
    assert effect.build == 0
    assert effect._drop < 0.1


def test_stutter_repeats_a_slice_along_the_strip() -> None:
    effect = make(Stutter, 80, slice_size=0.125)
    pixels = frame(effect, FakeAudio(beat=True))
    np.testing.assert_allclose(pixels[:10], pixels[10:20])
    np.testing.assert_allclose(pixels[:10], pixels[70:80])
    flowing = run(effect, 1)
    assert not np.allclose(flowing[:10], flowing[10:20])


def test_swell_builds_toward_the_next_beat() -> None:
    effect = make(Swell, 100)
    sums = []
    for into in (0.3, 0.6, 0.95):
        effect._tempo.beats = 3 + into
        sums.append(frame(effect).sum())
    assert sums[0] < sums[1] < sums[2]


def test_filter_sweep_opens_with_bright_music() -> None:
    def lit(lows: float, highs: float) -> int:
        effect = make(FilterSweep, 100)
        # Each band is measured against its own recent peak: set all three first
        run(effect, 1, FakeAudio(lows=1.0, mids=1.0, highs=1.0))
        return lit_pixels(
            run(effect, 2, FakeAudio(lows=lows, mids=0.3, highs=highs)), above=30
        )

    assert lit(lows=0.1, highs=1.0) > lit(lows=1.0, highs=0.1) + 20


def test_blinders_fire_on_a_heavy_beat_and_cool_down() -> None:
    effect = make(Blinders, 80, blinders=4, pattern="All")
    assert (tube_peaks(frame(effect, FakeAudio(beat=True, lows=1.0)), 4) > 200).all()
    assert run(effect, 1.5).max() < 60
    alternate = make(Blinders, 80, blinders=4, pattern="Alternate")
    peaks = tube_peaks(frame(alternate, FakeAudio(beat=True, lows=1.0)), 4)
    assert peaks[0] > 200
    assert peaks[1] == 0


def test_stage_wash_moves_to_a_new_look_each_phrase() -> None:
    effect = make(StageWash, 80, bars=1, fade=0.1, bump=0.0)
    first = run(effect, 0.5).copy()
    effect._tempo.beats = 4.5
    assert not np.allclose(run(effect, 0.5), first)


def test_flame_jets_blast_on_the_beat_and_die_down() -> None:
    effect = make(FlameJets, 100, jets=4, size=0.1)
    assert run(effect, 0.3).max() == 0
    pixels = run(effect, 0.2, FakeAudio(beat=True))
    assert all(pixels[jet].max() > 150 for jet in (12, 37, 62, 87))
    assert pixels[25].max() < 30
    assert run(effect, 1.5).max() == 0


def test_blacklight_glows_violet_with_neon_spots() -> None:
    pixels = run(make(Blacklight, 300, spots=5), 1)
    background = np.median(pixels, axis=0)
    assert background[2] > background[1]
    assert pixels.max() > 80


def test_dance_floor_changes_its_tiles_on_the_beat() -> None:
    effect = make(DanceFloor, 60, tiles=6)
    before = frame(effect, FakeAudio()).copy()
    after = run(effect, 0.3, FakeAudio(beat=True))
    assert not np.allclose(before, after)
    # Each tile is one color, with a dark grout line at its end
    tiles = after.reshape(6, 10, 3)
    assert (tiles[:, :9] == tiles[:, :1]).all()
    assert tiles[:, 9].max() == 0


def test_lens_flare_sweeps_across_on_a_hit() -> None:
    effect = make(LensFlare, 200, sweep_time=1.0)
    assert run(effect, 0.2).max() == 0
    early = brightest(run(effect, 0.3, FakeAudio(beat=True)))
    late = brightest(run(effect, 0.4))
    assert abs(late - early) > 40
    assert run(effect, 1).max() == 0


def test_lighthouse_beam_sweeps_and_blazes_when_facing() -> None:
    effect = make(Lighthouse, 101, rotation="Steady", reach=0.3)
    effect._turns = 0.0
    pixels = frame(effect, FakeAudio())
    assert pixels[60:].sum() > pixels[:40].sum() * 5
    effect._turns = 0.25
    assert frame(effect, FakeAudio()).min() > 150


def test_doppler_waves_crowd_blue_ahead_and_stretch_red_behind() -> None:
    effect = make(Doppler, 200, speed=0.6)
    effect.source, effect.heading = 0.2, 1.0
    pixels = run(effect, 0.5)
    at = int(effect.source * 199)
    ahead, behind = pixels[at + 12 : at + 70], pixels[at - 70 : at - 12]
    assert ahead[:, 2].sum() > ahead[:, 0].sum()
    assert behind[:, 0].sum() > behind[:, 2].sum()


def test_jacobs_ladder_arc_climbs_and_pops() -> None:
    effect = make(JacobsLadder, 100, climb_time=1.0)
    first = brightest(run(effect, 0.3))
    assert brightest(run(effect, 0.3)) > first + 10
    popped = False
    for _ in range(120):
        frame(effect, FakeAudio())
        popped |= effect._pop > 0
    assert popped


def test_magma_cracks_open_with_the_bass() -> None:
    hot = run(make(Magma, 200), 1, FakeAudio(lows=1.0)).sum()
    cool = run(make(Magma, 200), 1, FakeAudio(lows=0.0)).sum()
    assert hot > cool * 1.5


def test_freeze_creeps_in_when_quiet_and_melts_when_loud() -> None:
    effect = make(Freeze, 100, speed=0.5)
    loud = FakeAudio(lows=1.0, mids=1.0, highs=1.0)
    run(effect, 1, loud)
    assert effect.frost == 0
    run(effect, 1, FakeAudio(lows=0.0, mids=0.0, highs=0.0))
    assert effect.frost > 0.3
    run(effect, 1, loud)
    assert effect.frost == 0


def test_eclipse_hides_the_sun_and_shows_the_corona() -> None:
    effect = make(Eclipse, 101, passage=1, sun_size=0.3)
    # The moon starts well clear of the sun, and covers it half way through the bar
    effect._tempo.beats = 0.0
    clear = frame(effect, FakeAudio()).copy()
    assert clear[50].min() > 150
    effect._tempo.beats = 2.0
    total = frame(effect, FakeAudio())
    assert total[50].max() < 20
    assert total[30].max() > clear[30].max()


def test_rgb_split_pulls_red_and_blue_apart_on_the_beat() -> None:
    effect = make(RgbSplit, 120, jitter=0.0, speed=0.0)
    calm = frame(effect, FakeAudio())
    assert (calm[:, 0] == calm[:, 2]).all()
    split = frame(effect, FakeAudio(beat=True))
    assert not np.allclose(split[:, 0], split[:, 2])


def test_palette_cycle_turns_the_colors_with_the_song() -> None:
    effect = make(PaletteCycle, 100)
    first = frame(effect, FakeAudio()).copy()
    effect._tempo.beats += 2.0
    assert not np.allclose(frame(effect, FakeAudio()), first)


def test_accordion_squeezes_on_the_beat_and_springs_back() -> None:
    effect = make(Accordion, 100, squeeze=1.0)
    still = FakeAudio(lows=0.0)
    run(effect, 1, still)
    frame(effect, FakeAudio(beat=True, lows=0.0))
    run(effect, 0.1, still)
    assert effect.stretch < -0.1
    run(effect, 3, still)
    assert effect.stretch == pytest.approx(0.0, abs=0.02)


def test_palette_morph_moves_to_new_colors_each_phrase() -> None:
    effect = make(PaletteMorph, 90, bars=1, fade=0.5, drift=0.0)
    first = run(effect, 0.5).copy()
    effect._tempo.beats = 4.2
    assert not np.allclose(run(effect, 1), first)


def test_tv_static_snow_grows_with_the_music() -> None:
    def brightness(level: float) -> float:
        effect = make(TvStatic, 300, roll=False, color_bursts=False)
        return float(
            run(effect, 1, FakeAudio(lows=level, mids=level, highs=level)).mean()
        )

    assert brightness(1.0) > brightness(0.0) * 3


def test_dither_shows_only_ink_and_paper_and_swaps_them_on_the_beat() -> None:
    effect = make(Dither, 64)
    pixels = frame(effect, FakeAudio())
    assert {tuple(p) for p in pixels} <= {(0, 255, 156), (0, 26, 16)}
    lit = (pixels == (0, 255, 156)).all(axis=1)
    swapped = (frame(effect, FakeAudio(beat=True)) == (0, 255, 156)).all(axis=1)
    assert (swapped != lit).mean() > 0.8


def test_additive_mix_lights_meet_and_turn_white_when_loud() -> None:
    effect = make(AdditiveMix, 101, wander=0.0)
    pixels = run(effect, 1, FakeAudio(lows=1.0, mids=1.0, highs=1.0))
    assert pixels[50].min() > 200
    bass = make(AdditiveMix, 101, wander=0.0)
    run(bass, 1, FakeAudio(lows=1.0, mids=0.0, highs=0.0))
    # Only the red light moves toward the middle; blue stays at its own spot
    assert bass.positions()[0] > 0.45
    assert bass.positions()[2] > 0.7


def test_afterimage_flash_leaves_its_opposite_color() -> None:
    effect = make(Afterimage, 100, flash_time=0.1, size=0.4)
    flash = frame(effect, FakeAudio(beat=True)).copy()
    center = round(float(effect._centers[np.argmin(effect._ages)]) * 99)
    color = flash[center]
    ghost = run(effect, 0.3)[center]
    assert 0 < ghost.max() < color.max()
    np.testing.assert_allclose(ghost / ghost.max() * 255, 255 - color, atol=1)


def test_synthwave_sun_is_sliced_below_and_whole_above() -> None:
    effect = make(SynthwaveSun, 200, sun_size=0.8, slices=6)
    pixels = frame(effect, FakeAudio())
    v = effect.height()
    assert (pixels[(v > 0.6) & (v < 1)].max(axis=1) > 150).all()
    assert (pixels[(v > 0) & (v < 0.5)].max(axis=1) < 60).any()


def test_chorus_voices_drift_apart() -> None:
    together = run(make(Chorus, 100, detune=0.0), 0.5)
    apart = run(make(Chorus, 100, detune=0.2), 0.5)
    assert not np.allclose(together, apart)


def test_overdrive_flattens_waves_into_hard_bands_when_loud() -> None:
    def midtones(level: float) -> int:
        effect = make(Overdrive, 200, clip_glow=False)
        pixels = run(effect, 0.5, FakeAudio(lows=level, mids=level, highs=level))
        brightness = pixels.max(axis=1)
        return int(np.count_nonzero((brightness > 60) & (brightness < 190)))

    assert midtones(1.0) < midtones(0.0) / 2


def test_fiber_optic_tips_take_the_colors_of_the_turning_wheel() -> None:
    effect = make(FiberOptic, 400, fibers=20, sparkle=0.0)
    assert 10 <= lit_pixels(frame(effect, FakeAudio()), above=60) <= 80
    before = effect.colors().copy()
    run(effect, 1)
    assert not np.allclose(effect.colors(), before)


def test_god_rays_shine_from_the_sun_and_peek_on_the_beat() -> None:
    effect = make(GodRays, 100)
    calm = run(effect, 0.5).copy()
    assert calm[:10].sum() > calm[-10:].sum() * 3
    assert frame(effect, FakeAudio(beat=True)).sum() > calm.sum()


def test_oil_slick_shows_iridescent_colors() -> None:
    pixels = frame(make(OilSlick, 200), FakeAudio())
    spread = pixels.max(axis=1) - pixels.min(axis=1)
    assert (spread > 100).mean() > 0.3


def test_sandstorm_gusts_with_the_bass() -> None:
    def travelled(lows: float) -> float:
        effect = make(Sandstorm, 100, grains=50)
        start = effect.grains.copy()
        run(effect, 0.5, FakeAudio(lows=lows))
        return float(np.mean((effect.grains - start) % 1))

    assert travelled(1.0) > travelled(0.0) * 2


def test_wagon_wheel_flashes_with_the_strobe_and_freezes_between() -> None:
    effect = make(WagonWheel, 100, flashes_per_beat=2)
    effect._tempo.beats = 0.1
    flash = frame(effect, FakeAudio()).copy()
    dim = frame(effect, FakeAudio())
    assert dim.max() < flash.max()
    # Between flashes the spokes do not move: only the flash fades
    np.testing.assert_allclose(dim / dim.max(), flash / flash.max())


def test_chopper_rearranges_the_slices_on_the_beat() -> None:
    for move, expected in (
        ("Reverse", [3, 2, 1, 0]),
        ("Rotate", [3, 0, 1, 2]),
        ("Swap pairs", [1, 0, 3, 2]),
    ):
        effect = make(Chopper, 80, slices=4, move=move)
        run(effect, 0.3, FakeAudio(beat=True))
        assert effect.order.tolist() == expected, move
