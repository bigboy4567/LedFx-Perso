"""The Corsair effects: the real layouts of the gear, and each effect doing what it says."""

import typing

import numpy as np
import pytest
from numpy.typing import NDArray

from ledfx.effects import Effect
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.fan_aurora import FanAurora
from ledfx.effects.fan_bounce import FanBounce
from ledfx.effects.fan_breathe import FanBreathe
from ledfx.effects.fan_butterfly import FanButterfly
from ledfx.effects.fan_cascade import FanCascade
from ledfx.effects.fan_chase import FanChase
from ledfx.effects.fan_dice import FanDice
from ledfx.effects.fan_fire import FanFire
from ledfx.effects.fan_lava import FanLava
from ledfx.effects.fan_meter import FanMeter
from ledfx.effects.fan_metronome import FanMetronome
from ledfx.effects.fan_pinwheel import FanPinwheel
from ledfx.effects.fan_planets import FanPlanets
from ledfx.effects.fan_pulse import FanPulse
from ledfx.effects.fan_rain import FanRain
from ledfx.effects.fan_relay import FanRelay
from ledfx.effects.fan_rotor import FanRotor
from ledfx.effects.fan_siren import FanSiren
from ledfx.effects.fan_sparks import FanSparks
from ledfx.effects.fan_spectrum import FanSpectrum
from ledfx.effects.fan_stack import FanStack
from ledfx.effects.fan_starfield import FanStarfield
from ledfx.effects.fan_storm import FanStorm
from ledfx.effects.fan_strobe import FanStrobe
from ledfx.effects.fan_timer import FanTimer
from ledfx.effects.fan_traffic_light import FanTrafficLight
from ledfx.effects.fan_vortex import FanVortex
from ledfx.effects.fan_yin_yang import FanYinYang
from ledfx.effects.key_aurora import KeyAurora
from ledfx.effects.key_breathe import KeyBreathe
from ledfx.effects.key_checkerboard import KeyCheckerboard
from ledfx.effects.key_comets import KeyComets
from ledfx.effects.key_equalizer import KeyEqualizer
from ledfx.effects.key_fire import KeyFire
from ledfx.effects.key_fireworks import KeyFireworks
from ledfx.effects.key_ghost_typist import KeyGhostTypist
from ledfx.effects.key_lava_lamp import KeyLavaLamp
from ledfx.effects.key_plasma import KeyPlasma
from ledfx.effects.key_pong import KeyPong
from ledfx.effects.key_radar import KeyRadar
from ledfx.effects.key_rain import KeyRain
from ledfx.effects.key_rainbow import KeyRainbow
from ledfx.effects.key_ripple import KeyRipple
from ledfx.effects.key_rows import KeyRows
from ledfx.effects.key_scanner import KeyScanner
from ledfx.effects.key_snake import KeySnake
from ledfx.effects.key_spectrogram import KeySpectrogram
from ledfx.effects.key_spiral import KeySpiral
from ledfx.effects.key_split import KeySplit
from ledfx.effects.key_spotlight import KeySpotlight
from ledfx.effects.key_storm import KeyStorm
from ledfx.effects.key_strobe import KeyStrobe
from ledfx.effects.key_twinkle import KeyTwinkle
from ledfx.effects.key_warp import KeyWarp
from ledfx.effects.key_wave import KeyWave
from ledfx.effects.mat_aurora import MatAurora
from ledfx.effects.mat_beat_counter import MatBeatCounter
from ledfx.effects.mat_breathe import MatBreathe
from ledfx.effects.mat_chase import MatChase
from ledfx.effects.mat_comets import MatComets
from ledfx.effects.mat_converge import MatConverge
from ledfx.effects.mat_fire import MatFire
from ledfx.effects.mat_fireworks import MatFireworks
from ledfx.effects.mat_flow import MatFlow
from ledfx.effects.mat_glitch import MatGlitch
from ledfx.effects.mat_halfpipe import MatHalfpipe
from ledfx.effects.mat_lava_lamp import MatLavaLamp
from ledfx.effects.mat_meter import MatMeter
from ledfx.effects.mat_pulse_line import MatPulseLine
from ledfx.effects.mat_rain import MatRain
from ledfx.effects.mat_rainbow import MatRainbow
from ledfx.effects.mat_ripples import MatRipples
from ledfx.effects.mat_siren import MatSiren
from ledfx.effects.mat_snake import MatSnake
from ledfx.effects.mat_sparkle import MatSparkle
from ledfx.effects.mat_spectrum import MatSpectrum
from ledfx.effects.mat_splash import MatSplash
from ledfx.effects.mat_split import MatSplit
from ledfx.effects.mat_strobe import MatStrobe
from ledfx.effects.mat_timer import MatTimer
from ledfx.effects.mouse_mood import MouseMood
from ledfx.effects.mouse_pulse import MousePulse
from ledfx.effects.pump_aurora import PumpAurora
from ledfx.effects.pump_beacon import PumpBeacon
from ledfx.effects.pump_beat_ring import PumpBeatRing
from ledfx.effects.pump_boil import PumpBoil
from ledfx.effects.pump_breathe import PumpBreathe
from ledfx.effects.pump_clock import PumpClock
from ledfx.effects.pump_collide import PumpCollide
from ledfx.effects.pump_compass import PumpCompass
from ledfx.effects.pump_drip import PumpDrip
from ledfx.effects.pump_eye import PumpEye
from ledfx.effects.pump_fireball import PumpFireball
from ledfx.effects.pump_galaxy import PumpGalaxy
from ledfx.effects.pump_gauge import PumpGauge
from ledfx.effects.pump_heart import PumpHeart
from ledfx.effects.pump_loop import PumpLoop
from ledfx.effects.pump_mandala import PumpMandala
from ledfx.effects.pump_note_wheel import PumpNoteWheel
from ledfx.effects.pump_orbit import PumpOrbit
from ledfx.effects.pump_radar import PumpRadar
from ledfx.effects.pump_sonar import PumpSonar
from ledfx.effects.pump_spectrum import PumpSpectrum
from ledfx.effects.pump_split import PumpSplit
from ledfx.effects.pump_strobe import PumpStrobe
from ledfx.effects.pump_swirl import PumpSwirl
from ledfx.effects.pump_tempo_dial import PumpTempoDial
from ledfx.effects.pump_thermometer import PumpThermometer
from ledfx.effects.pump_turbine import PumpTurbine
from ledfx.effects.ram_aurora import RamAurora
from ledfx.effects.ram_bar_counter import RamBarCounter
from ledfx.effects.ram_battery import RamBattery
from ledfx.effects.ram_blocks import RamBlocks
from ledfx.effects.ram_bounce import RamBounce
from ledfx.effects.ram_breathe import RamBreathe
from ledfx.effects.ram_center_pulse import RamCenterPulse
from ledfx.effects.ram_comets import RamComets
from ledfx.effects.ram_elevators import RamElevators
from ledfx.effects.ram_fire import RamFire
from ledfx.effects.ram_fireworks import RamFireworks
from ledfx.effects.ram_glitch import RamGlitch
from ledfx.effects.ram_lava_lamp import RamLavaLamp
from ledfx.effects.ram_meter import RamMeter
from ledfx.effects.ram_mirror_meter import RamMirrorMeter
from ledfx.effects.ram_plasma import RamPlasma
from ledfx.effects.ram_pong import RamPong
from ledfx.effects.ram_rain import RamRain
from ledfx.effects.ram_rising import RamRising
from ledfx.effects.ram_scanner import RamScanner
from ledfx.effects.ram_snake import RamSnake
from ledfx.effects.ram_sparkle import RamSparkle
from ledfx.effects.ram_stairs import RamStairs
from ledfx.effects.ram_strobe import RamStrobe
from ledfx.effects.ram_timer import RamTimer
from ledfx.effects.ram_waterfall import RamWaterfall
from ledfx.effects.ram_wave import RamWave
from ledfx.effects.rig_wave import RigWave
from ledfx.effects.utils.corsair import (
    BAR,
    CORSAIR_CATEGORY,
    FAN_HUB,
    FAN_RIM,
    G_KEY,
    KEY,
    LOGO,
    aio_layout,
    fan_layout,
    fan_xy,
    keyboard_layout,
    keyboard_rows,
    mat_height,
    mat_layout,
    ram_layout,
    rig_layout,
    stack_height,
)
from tests import test_custom_effects as custom
from tests.test_custom_effects import FakeAudio, frame, literal_options, run

CORSAIR_EFFECTS: list[type[AudioReactiveEffect]] = [
    FanRotor,
    FanMeter,
    FanCascade,
    PumpSwirl,
    PumpGauge,
    RamMeter,
    RamWave,
    KeyRipple,
    KeyEqualizer,
    MatSplash,
    MatMeter,
    RigWave,
    FanButterfly,
    FanChase,
    FanFire,
    FanLava,
    FanPinwheel,
    FanPlanets,
    FanPulse,
    FanSparks,
    FanStack,
    FanVortex,
    PumpBoil,
    PumpClock,
    PumpEye,
    PumpHeart,
    PumpNoteWheel,
    PumpRadar,
    PumpSplit,
    PumpTempoDial,
    PumpThermometer,
    PumpTurbine,
    RamBarCounter,
    RamBlocks,
    RamCenterPulse,
    RamElevators,
    RamFire,
    RamMirrorMeter,
    RamPlasma,
    RamRising,
    RamScanner,
    RamSparkle,
    KeyFire,
    KeyGhostTypist,
    KeyPlasma,
    KeyRadar,
    KeyRain,
    KeyRows,
    KeyScanner,
    KeySpotlight,
    KeyTwinkle,
    KeyWave,
    MatBeatCounter,
    MatChase,
    MatComets,
    MatConverge,
    MatFire,
    MatFlow,
    MatHalfpipe,
    MatSparkle,
    MatSplit,
    MousePulse,
    FanAurora,
    FanBounce,
    FanBreathe,
    FanDice,
    FanMetronome,
    FanRain,
    FanRelay,
    FanSiren,
    FanSpectrum,
    FanStarfield,
    FanStorm,
    FanStrobe,
    FanTimer,
    FanTrafficLight,
    FanYinYang,
    PumpAurora,
    PumpBeacon,
    PumpBeatRing,
    PumpBreathe,
    PumpCollide,
    PumpCompass,
    PumpDrip,
    PumpFireball,
    PumpGalaxy,
    PumpLoop,
    PumpMandala,
    PumpOrbit,
    PumpSonar,
    PumpSpectrum,
    PumpStrobe,
    RamAurora,
    RamBattery,
    RamBounce,
    RamBreathe,
    RamComets,
    RamFireworks,
    RamGlitch,
    RamLavaLamp,
    RamPong,
    RamRain,
    RamSnake,
    RamStairs,
    RamStrobe,
    RamTimer,
    RamWaterfall,
    KeyAurora,
    KeyBreathe,
    KeyCheckerboard,
    KeyComets,
    KeyFireworks,
    KeyLavaLamp,
    KeyPong,
    KeyRainbow,
    KeySnake,
    KeySpectrogram,
    KeySpiral,
    KeySplit,
    KeyStorm,
    KeyStrobe,
    KeyWarp,
    MatAurora,
    MatBreathe,
    MatFireworks,
    MatGlitch,
    MatLavaLamp,
    MatPulseLine,
    MatRain,
    MatRainbow,
    MatRipples,
    MatSiren,
    MatSnake,
    MatSpectrum,
    MatStrobe,
    MatTimer,
    MouseMood,
]
# The pixel counts of the gear as the bridge streams it, and of its two groups
GEAR_COUNTS = [16, 24, 40, 48, 112, 134, 262]

E = typing.TypeVar("E", bound=AudioReactiveEffect)


def make(cls: type[E], count: int, **config: object) -> E:
    effect = custom.make(cls, count, **config)
    # No audio pipeline here: a fixed spectrum, the bass louder than the treble
    vars(effect)["melbank"] = lambda filtered=False, size=0: np.linspace(
        1.0, 0.2, size or 24
    )
    return effect


def test_corsair_effects_share_their_own_category() -> None:
    assert {
        cls
        for cls in Effect.registry().values()
        if getattr(cls, "CATEGORY", None) == CORSAIR_CATEGORY
    } == set(CORSAIR_EFFECTS)


@pytest.mark.parametrize("cls", CORSAIR_EFFECTS, ids=lambda cls: cls.__name__)
@pytest.mark.parametrize("count", [1, 2, 7, *GEAR_COUNTS, 37555])
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
                beat=hit, onset=hit, lows=0.8, mids=0.4, highs=0.3, bar=index / 30 % 4
            )
            pixels = frame(effect, audio)
            assert pixels.shape == (count, 3), config
            assert np.isfinite(pixels).all(), config
            assert pixels.min() >= 0, config
            assert pixels.max() <= 255, config
            lit = lit or pixels.max() > 0
        assert lit, f"{cls.__name__} {config} never lit up"


def test_keyboard_layout_is_the_k95_platinum() -> None:
    board = keyboard_layout(134)
    zones = board.zone.tolist()
    assert (
        zones.count(KEY),
        zones.count(BAR),
        zones.count(LOGO),
        zones.count(G_KEY),
    ) == (108, 19, 1, 6)
    # The light bar runs along the top, the G keys down the left edge
    assert board.y[board.zone == BAR].max() < 0.05
    assert board.x[board.zone == G_KEY].max() < 0.01
    # The bridge sends the keys column by column, from left to right
    assert (np.diff(board.x) >= -1e-9).all()


def test_fan_layout_is_three_fans_of_rim_and_hub() -> None:
    fans = fan_layout(48)
    for fan in range(3):
        mine = fans.fan == fan
        assert np.count_nonzero(mine & (fans.ring == FAN_RIM)) == 12
        assert np.count_nonzero(mine & (fans.ring == FAN_HUB)) == 4
    # The bridge sweeps the stack from the top: the first LED is the top of the top fan
    assert (fans.fan[0], fans.ring[0], fans.angle[0]) == (0, FAN_RIM, 0.0)


def test_aio_ram_and_mat_layouts() -> None:
    aio = aio_layout(24)
    assert aio.pump[:16].all()
    assert not aio.pump[16:].any()
    assert aio.fan[16:].tolist() == [0] * 4 + [1] * 4
    ram = ram_layout(40)
    assert ram.stick.tolist() == [stick for stick in range(4) for _ in range(10)]
    # Each stick is read from its top
    assert ram.height[0] == 1.0
    assert ram.height[9] == 0.0
    mat = mat_layout(16)
    assert mat.mouse.tolist() == [False] * 15 + [True]
    assert min(mat.along[:15]) == 0.0


def test_rig_layouts_follow_the_device_groups() -> None:
    every = rig_layout(262)
    assert every.stages == 5
    assert np.bincount(every.stage).tolist() == [134, 16, 48, 24, 40]
    inside = rig_layout(112)
    assert np.bincount(inside.stage).tolist() == [48, 24, 40]
    assert rig_layout(100).stages == 1


def brightest_angle(effect: FanRotor, fan: int) -> float:
    pixels = effect.pixels
    assert pixels is not None
    fans = effect._fans
    rim = np.flatnonzero((fans.fan == fan) & (fans.ring == FAN_RIM))
    return float(fans.angle[rim[np.argmax(pixels[rim].sum(axis=1))]])


def test_fan_rotor_spins_neighbouring_fans_opposite_ways() -> None:
    effect = make(FanRotor, 48, blades=1, turns_per_beat=1.0)
    frame(effect)
    effect._tempo.beats = 0.25
    frame(effect)
    # A quarter of a turn: clockwise on the top fan, the other way on the middle one
    assert brightest_angle(effect, 0) == pytest.approx(0.25, abs=0.09)
    assert brightest_angle(effect, 1) == pytest.approx(0.75, abs=0.09)


def rim_lit(pixels: NDArray[np.float64], fan: int, above: float = 100) -> int:
    fans = fan_layout(48)
    rim = (fans.fan == fan) & (fans.ring == FAN_RIM)
    return int(np.count_nonzero(pixels[rim].max(axis=1) > above))


def test_fan_meter_shows_a_band_on_each_fan() -> None:
    def fill(order: str) -> tuple[int, int]:
        effect = make(FanMeter, 48, order=order)
        # Each band is measured against its own recent peak: set all three first
        run(effect, 1, FakeAudio(lows=1.0, mids=1.0, highs=1.0))
        pixels = run(effect, 1, FakeAudio(lows=1.0, mids=0.0, highs=0.0))
        return rim_lit(pixels, 0), rim_lit(pixels, 2)

    top, bottom = fill("Bass at the top")
    assert top >= 10 > bottom
    top, bottom = fill("Treble at the top")
    assert bottom >= 10 > top


def test_fan_cascade_falls_from_the_top_fan_to_the_bottom_one() -> None:
    effect = make(FanCascade, 48, speed=10.0)
    early = frame(effect, FakeAudio(beat=True))
    assert rim_lit(early, 0, above=60) + 1 > rim_lit(early, 2, above=60)
    fans = fan_layout(48)
    top_hub = early[(fans.fan == 0) & (fans.ring == FAN_HUB)].sum()
    bottom_hub = early[(fans.fan == 2) & (fans.ring == FAN_HUB)].sum()
    assert top_hub > bottom_hub
    later = run(effect, 0.45)
    assert (
        later[(fans.fan == 2)].sum()
        > later[(fans.fan == 0) & (fans.ring == FAN_HUB)].sum()
    )


def test_pump_swirl_heats_up_with_loud_music() -> None:
    loud = make(PumpSwirl, 24, heat_up=3.0)
    pixels = run(loud, 2, FakeAudio(lows=1.0, mids=1.0, highs=1.0))
    assert loud.heat > 0.8
    assert pixels[:16, 0].sum() > pixels[:16, 2].sum()
    calm = make(PumpSwirl, 24, heat_up=3.0)
    pixels = run(calm, 2, FakeAudio(lows=0.0, mids=0.0, highs=0.0))
    assert pixels[:16, 2].sum() > pixels[:16, 0].sum()


def pump_lit(pixels: NDArray[np.float64]) -> int:
    return int(np.count_nonzero(pixels[:16].max(axis=1) > 100))


def test_pump_gauge_fills_with_the_volume_and_flashes_the_fans() -> None:
    quiet = run(make(PumpGauge, 24), 1, FakeAudio(lows=0.1, mids=0.1, highs=0.1))
    loud = run(make(PumpGauge, 24), 1, FakeAudio(lows=0.8, mids=0.8, highs=0.8))
    assert pump_lit(loud) > pump_lit(quiet) + 4
    effect = make(PumpGauge, 24)
    flash = frame(effect, FakeAudio(beat=True))
    # One radiator fan flashes white, the other stays dim
    assert flash[16:20].min() > 200
    assert flash[20:24].max() < 50


def test_ram_meter_gives_each_stick_its_band() -> None:
    effect = make(RamMeter, 40, peaks=False)
    run(effect, 1, FakeAudio(lows=1.0, mids=1.0, highs=1.0))
    pixels = run(effect, 1, FakeAudio(lows=1.0, mids=0.0, highs=0.0))
    lit = [
        int(np.count_nonzero(pixels[stick * 10 : stick * 10 + 10].max(axis=1) > 100))
        for stick in range(4)
    ]
    assert lit[0] >= 9
    assert lit[0] > lit[1] > lit[3]


def test_ram_wave_sets_each_stick_at_its_own_height() -> None:
    effect = make(RamWave, 40, spread=0.25)
    run(effect, 1, FakeAudio(lows=1.0, mids=1.0, highs=1.0))
    heights = effect.heights()
    assert np.ptp(heights) > 0.3
    pixels = effect.pixels
    assert pixels is not None
    # On each stick the brightest LED is where the wave is
    ram = ram_layout(40)
    for stick in range(4):
        mine = np.flatnonzero(ram.stick == stick)
        top = mine[np.argmax(pixels[mine].sum(axis=1))]
        assert abs(ram.height[top] - heights[stick]) <= 1 / 9 + 1e-9


def test_key_ripple_spreads_from_the_middle_and_flashes_the_logo() -> None:
    effect = make(KeyRipple, 134, origin="Middle", speed=1.0)
    pixels = run(effect, 0.1, FakeAudio(onset=True))
    board = keyboard_layout(134)
    distance = np.hypot(board.x - 0.5, (board.y - 0.5) * 0.31)
    near, far = pixels[distance < 0.15].mean(), pixels[distance > 0.4].mean()
    assert near > far * 3
    assert pixels[board.zone == LOGO].min() > 100


def test_key_equalizer_stands_the_bass_taller_than_the_treble() -> None:
    effect = make(KeyEqualizer, 134, gain=1.0)
    pixels = run(effect, 0.5, FakeAudio(lows=0.3, mids=0.3, highs=0.3))
    board = keyboard_layout(134)
    keys = board.zone == KEY
    lit = pixels.max(axis=1) > 100
    left = np.count_nonzero(lit & keys & (board.x < 0.4)) / np.count_nonzero(
        keys & (board.x < 0.4)
    )
    right = np.count_nonzero(lit & keys & (board.x > 0.7)) / np.count_nonzero(
        keys & (board.x > 0.7)
    )
    assert left > right + 0.2
    # The light bar fills from the left with the volume
    bar = np.flatnonzero(board.zone == BAR)
    assert lit[bar[0]]
    assert not lit[bar[-1]]


def test_mat_splash_climbs_the_pad_from_the_bottom_and_colors_the_mouse() -> None:
    effect = make(MatSplash, 16, speed=1.0)
    early = run(effect, 0.15, FakeAudio(beat=True))
    mat = mat_layout(16)
    bottom = np.abs(mat.along - 0.5) < 0.15
    tips = np.abs(mat.along - 0.5) > 0.4
    assert early[bottom & ~mat.mouse].mean() > early[tips].mean()
    later = run(effect, 0.8)
    assert later[tips].mean() > later[bottom & ~mat.mouse].mean()
    assert early[mat.mouse].max() > 50


def test_mat_meter_rises_up_both_sides_with_the_volume() -> None:
    def lit(level: float) -> int:
        pixels = run(
            make(MatMeter, 16), 1, FakeAudio(lows=level, mids=level, highs=level)
        )
        return int(np.count_nonzero(pixels[:15].max(axis=1) > 100))

    assert lit(0.05) < 5
    assert lit(0.8) == 15


def test_rig_wave_runs_from_the_keyboard_to_the_ram() -> None:
    effect = make(RigWave, 262, speed=3.0, glow=False)
    rig = rig_layout(262)
    early = run(effect, 0.1, FakeAudio(beat=True))
    assert early[rig.stage == 0].max() > early[rig.stage == 4].max()
    later = run(effect, 1.4)
    assert later[rig.stage == 4].max() > later[rig.stage == 0].max()


# The ten more effects for each device


def plain_gradient(values: NDArray[np.float64]) -> NDArray[np.float64]:
    return np.full((np.size(values), 3), 255.0)


def plain(effect: E) -> E:
    """The effect with a white gradient, so brightness alone shows its pattern."""
    vars(effect)["get_gradient_color_vectorized1d"] = plain_gradient
    return effect


SILENCE = FakeAudio(lows=0.0, mids=0.0, highs=0.0)
LOUD = FakeAudio(lows=1.0, mids=1.0, highs=1.0)
BASS = FakeAudio(lows=1.0, mids=0.0, highs=0.0)
TREBLE = FakeAudio(lows=0.0, mids=0.0, highs=1.0)


def brightest(
    pixels: NDArray[np.float64], where: NDArray[np.float64], mask: NDArray[np.bool_]
) -> float:
    """Where, by the given measure, the brightest LED of the mask is."""
    chosen = np.flatnonzero(mask)
    return float(where[chosen[np.argmax(pixels[chosen].sum(axis=1))]])


def lit(pixels: NDArray[np.float64], above: float = 100) -> NDArray[np.bool_]:
    return pixels.max(axis=1) > above


def test_fan_vortex_turns_the_rim_and_the_hub_opposite_ways() -> None:
    effect = plain(make(FanVortex, 48, arms=1, turns_per_beat=1.0))
    run(effect, 0.1, SILENCE)
    effect.song.beats = 0.25
    pixels = frame(effect)
    fans = fan_layout(48)
    rim = (fans.fan == 0) & (fans.ring == FAN_RIM)
    hub = (fans.fan == 0) & (fans.ring == FAN_HUB)
    assert brightest(pixels, fans.angle, rim) == pytest.approx(0.25, abs=0.09)
    assert brightest(pixels, fans.angle, hub) == pytest.approx(0.75, abs=0.13)


def test_fan_pulse_spreads_from_the_hub_to_the_rim() -> None:
    effect = plain(make(FanPulse, 48, speed=2.0))
    fans = fan_layout(48)
    hub, rim = fans.ring == FAN_HUB, fans.ring == FAN_RIM
    early = frame(effect, FakeAudio(beat=True))
    assert early[hub].mean() > early[rim].mean() * 2
    later = run(effect, 0.6, SILENCE)
    assert later[rim].mean() > later[hub].mean()


def test_fan_pinwheel_snaps_a_slice_round_on_each_beat() -> None:
    effect = make(FanPinwheel, 48, slices=4, drift=0.0)
    flash = frame(effect, FakeAudio(beat=True))
    fans = fan_layout(48)
    assert flash[fans.ring == FAN_HUB].min() > 200
    run(effect, 1, SILENCE)
    assert effect._turn == pytest.approx(0.25, abs=0.01)


def test_fan_fire_burns_from_the_bottom_of_each_fan() -> None:
    loud = run(make(FanFire, 48, flicker=0.0), 1, BASS)
    quiet = run(make(FanFire, 48, flicker=0.0), 1, SILENCE)
    assert loud.sum() > quiet.sum() * 1.3
    fans = fan_layout(48)
    rim = fans.ring == FAN_RIM
    bottom = loud[rim & (np.abs(fans.angle - 0.5) < 0.05)]
    top = loud[rim & (fans.angle < 0.05)]
    assert bottom.sum() > top.sum() * 2


def test_fan_stack_fills_the_three_fans_from_the_bottom() -> None:
    quiet = run(make(FanStack, 48), 1, FakeAudio(lows=0.05, mids=0.05, highs=0.05))
    loud = run(make(FanStack, 48), 1, FakeAudio(lows=0.4, mids=0.4, highs=0.4))
    assert np.count_nonzero(lit(loud)) > np.count_nonzero(lit(quiet)) + 20
    fans = fan_layout(48)
    # Whatever is lit at a low volume is on the bottom fan
    assert lit(quiet)[fans.fan != 2].sum() <= lit(quiet)[fans.fan == 2].sum()


def test_fan_planets_moves_the_moons_with_the_song() -> None:
    effect = plain(make(FanPlanets, 48, moons=1, orbits_per_beat=0.25))
    fans = fan_layout(48)
    rim = (fans.fan == 0) & (fans.ring == FAN_RIM)
    before = brightest(run(effect, 0.1, SILENCE), fans.angle, rim)
    effect.song.beats = 1.0
    after = brightest(frame(effect), fans.angle, rim)
    assert abs((after - before + 0.5) % 1 - 0.5) == pytest.approx(0.25, abs=0.09)


@pytest.mark.parametrize("path, order", [("Down", [1, 2, 0]), ("Up", [1, 0, 2])])
def test_fan_chase_jumps_from_fan_to_fan_on_the_beat(
    path: str, order: list[int]
) -> None:
    effect = make(FanChase, 48, path=path)
    fans = fan_layout(48)
    seen: list[int] = []
    for _ in order:
        pixels = frame(effect, FakeAudio(beat=True))
        seen.append(int(np.argmax([pixels[fans.fan == fan].sum() for fan in range(3)])))
        run(effect, 0.3, SILENCE)
    assert seen == order


def test_fan_butterfly_opens_and_closes_its_wings_with_the_song() -> None:
    effect = plain(make(FanButterfly, 48, flaps_per_beat=0.5))
    fans = fan_layout(48)
    x, _ = fan_xy(fans)
    outer = np.abs(x) > 0.8
    run(effect, 0.05, LOUD)
    effect.song.beats = 0.5
    opened = frame(effect).copy()
    effect.song.beats = 1.5
    closed = frame(effect)
    assert opened[outer].sum() > closed[outer].sum() * 2


def test_fan_lava_swells_its_blobs_with_the_bass() -> None:
    loud = run(make(FanLava, 48, swell=2.0), 1, BASS)
    quiet = run(make(FanLava, 48, swell=2.0), 1, SILENCE)
    assert np.count_nonzero(lit(loud, 150)) > np.count_nonzero(lit(quiet, 150))


def test_fan_sparks_lights_rim_leds_on_each_hit() -> None:
    effect = make(FanSparks, 48, sparks_per_hit=5)
    before = run(effect, 0.2, SILENCE)
    assert np.count_nonzero(before.min(axis=1) > 200) == 0
    pixels = frame(effect, FakeAudio(onset=True))
    sparks = pixels.min(axis=1) > 200
    assert np.count_nonzero(sparks) == 5
    assert (fan_layout(48).ring[sparks] == FAN_RIM).all()


@pytest.mark.parametrize("top_led", [0, 4])
def test_pump_clock_points_its_hand_at_the_bar(top_led: int) -> None:
    effect = plain(make(PumpClock, 24, top_led=top_led))
    run(effect, 0.1, SILENCE)
    effect.song.beats = 1.0
    pixels = frame(effect)
    # A quarter of the bar: a quarter of a turn clockwise from the top LED
    assert int(np.argmax(pixels[:16].sum(axis=1))) == (top_led + 4) % 16
    assert pixels[16:].max() < 100
    effect.song.beats = 4.0
    assert frame(effect)[16:].min() > 200


def test_pump_radar_sweeps_with_the_bar_and_marks_hits() -> None:
    effect = make(PumpRadar, 24)
    run(effect, 0.1, SILENCE)
    effect.song.beats = 1.0
    pixels = frame(effect)
    assert int(np.argmax(pixels[:16, 1])) == 4
    frame(effect, FakeAudio(onset=True))
    for _ in range(2):
        effect.song.beats += 2.0
        pixels = frame(effect)
    # The sweep has passed the blip: it shows red on the green screen
    assert (pixels[:16, 0] > pixels[:16, 1]).any()


def test_pump_heart_beats_lub_dub() -> None:
    effect = make(PumpHeart, 24)
    lub = frame(effect, FakeAudio(beat=True)).copy()
    between = run(effect, 0.1, SILENCE).copy()
    # The radiator fans echo the pump a moment later
    assert lub[16:, 0].max() < lub[:16, 0].max() / 3
    echo = run(effect, 0.034, SILENCE)
    assert echo[16:, 0].max() > echo[:16, 0].max()
    dub = run(effect, 0.05, SILENCE)
    assert lub[:16, 0].max() > dub[:16, 0].max() > between[:16, 0].max()


def test_pump_turbine_spins_up_with_the_music() -> None:
    loud = make(PumpTurbine, 24)
    loud_pixels = run(loud, 2, LOUD)
    quiet = make(PumpTurbine, 24)
    quiet_pixels = run(quiet, 2, SILENCE)
    assert loud.speed > 0.8
    assert quiet.speed < 0.2
    # The radiator fans are its speed gauge
    assert np.count_nonzero(lit(loud_pixels[16:], 60)) > np.count_nonzero(
        lit(quiet_pixels[16:], 60)
    )


def test_pump_thermometer_fills_the_ring_from_the_bottom() -> None:
    warm = run(make(PumpThermometer, 24), 3, FakeAudio(lows=0.2, mids=0.2, highs=0.2))
    # With the ring's top LED first, the bottom is LED 8
    assert lit(warm[8:9]).all()
    assert not lit(warm[0:1]).any()
    hot = run(make(PumpThermometer, 24), 3, LOUD)
    assert lit(hot[:16]).all()


@pytest.mark.parametrize("audio, side", [(BASS, "left"), (TREBLE, "right")])
def test_pump_eye_looks_towards_the_louder_end(audio: FakeAudio, side: str) -> None:
    pixels = run(make(PumpEye, 24, blink_every=32), 1, audio)
    iris = pixels[:16, 2] - pixels[:16, 0]
    right, left = iris[1:8].sum(), iris[9:16].sum()
    assert (left > right) if side == "left" else (right > left)


def test_pump_tempo_dial_reads_the_songs_tempo() -> None:
    def dial(rate: float) -> int:
        effect = make(PumpTempoDial, 24)
        effect.song.rate = rate
        return int(np.count_nonzero(lit(frame(effect)[:16], 60)))

    assert dial(3.0) > dial(1.0) + 8


def test_pump_boil_bubbles_more_as_it_gets_louder() -> None:
    loud = make(PumpBoil, 24)
    run(loud, 1, LOUD)
    quiet = make(PumpBoil, 24)
    run(quiet, 1, SILENCE)
    assert loud._bubbles.sum() > quiet._bubbles.sum() + 0.5


@pytest.mark.parametrize("note, top_led, led", [(60, 0, 0), (67, 0, 9), (60, 4, 4)])
def test_pump_note_wheel_lights_the_note_heard(
    note: int, top_led: int, led: int
) -> None:
    effect = make(PumpNoteWheel, 24, top_led=top_led)
    pixels = run(effect, 0.3, FakeAudio(pitch=note))
    assert int(np.argmax(pixels[:16].sum(axis=1))) == led


def test_pump_split_shows_the_bass_left_and_the_treble_right() -> None:
    pixels = run(make(PumpSplit, 24), 1, BASS)
    assert lit(pixels[9:16]).all()
    assert not lit(pixels[1:8]).any()
    assert pixels[16:20].max() > 200 > pixels[20:24].max()


def stick_sums(pixels: NDArray[np.float64]) -> list[float]:
    ram = ram_layout(40)
    return [float(pixels[ram.stick == stick].sum()) for stick in range(4)]


def test_ram_bar_counter_lights_the_stick_of_the_beat() -> None:
    effect = plain(make(RamBarCounter, 40))
    run(effect, 0.1, SILENCE)
    for beat in (2, 3, 0):
        effect.song.beats = 4.0 + beat
        assert int(np.argmax(stick_sums(frame(effect)))) == beat


def test_ram_fire_burns_from_the_bottom_of_the_sticks() -> None:
    loud = run(make(RamFire, 40, flicker=0.0), 1, BASS)
    quiet = run(make(RamFire, 40, flicker=0.0), 1, SILENCE)
    assert loud.sum() > quiet.sum() * 1.3
    ram = ram_layout(40)
    assert loud[ram.height == 0].sum() > loud[ram.height == 1].sum() * 2


def test_ram_elevators_send_a_car_to_its_floor_on_the_beat() -> None:
    effect = plain(make(RamElevators, 40))
    frame(effect, FakeAudio(beat=True))
    called = int(np.argmax(effect._floors))
    floor = float(effect._floors[called])
    assert floor > 0.2
    pixels = run(effect, 2, SILENCE)
    ram = ram_layout(40)
    assert brightest(pixels, ram.height, ram.stick == called) == pytest.approx(
        floor, abs=0.15
    )


def test_ram_center_pulse_spreads_from_the_middle_of_the_bank() -> None:
    effect = plain(make(RamCenterPulse, 40, speed=1.5))
    distance = effect._distance
    near, far = distance < 0.25, distance > 0.55
    early = run(effect, 0.1, FakeAudio(beat=True))
    assert early[near].mean() > early[far].mean()
    later = run(effect, 0.35, SILENCE)
    assert later[far].mean() > later[near].mean()


def test_ram_mirror_meter_spreads_the_bass_on_the_outer_sticks() -> None:
    pixels = run(plain(make(RamMirrorMeter, 40)), 1, BASS)
    ram = ram_layout(40)
    on = lit(pixels)
    outer = (ram.stick == 0) | (ram.stick == 3)
    assert on[outer].all()
    # The inner sticks get only a share of the bass, round their middles
    assert on[~outer].sum() < on[outer].sum() / 2
    assert not on[~outer & (ram.height > 0.9)].any()


def test_ram_scanner_runs_each_stick_a_little_behind_the_last() -> None:
    effect = plain(make(RamScanner, 40, beats_per_sweep=1.0, stagger=0.25))
    run(effect, 0.05, SILENCE)
    effect.song.beats = 0.6
    pixels = frame(effect)
    ram = ram_layout(40)
    assert brightest(pixels, ram.height, ram.stick == 0) == pytest.approx(0.6, abs=0.12)
    assert brightest(pixels, ram.height, ram.stick == 2) == pytest.approx(0.1, abs=0.12)


def test_ram_rising_bubbles_climb_the_sticks() -> None:
    effect = make(RamRising, 40)
    frame(effect, FakeAudio(beat=True, lows=0.0, mids=0.0, highs=0.0))
    assert len(effect._bubbles) == 2
    assert (effect._bubbles[:, 1] < 0.05).all()
    run(effect, 0.4, SILENCE)
    assert (effect._bubbles[:2, 1] > 0.15).all()


def test_ram_sparkle_lights_a_whole_stick_on_a_hit() -> None:
    effect = make(RamSparkle, 40)
    pixels = frame(effect, FakeAudio(onset=True, lows=0.0, mids=0.0, highs=0.0))
    flashed = pixels.min(axis=1) > 200
    assert np.count_nonzero(flashed) == 10
    assert np.unique(ram_layout(40).stick[flashed]).size == 1


def test_ram_blocks_stack_up_one_block_a_beat() -> None:
    effect = make(RamBlocks, 40, block_size=5)
    for _ in range(7):
        pixels = run(effect, 0.5, FakeAudio(beat=True))
    assert int(effect._stacked.sum()) == 35
    assert np.count_nonzero(lit(pixels, 50)) == 35
    run(effect, 0.42, FakeAudio(beat=True))
    # The bank is full: it flashes white, then empties
    assert effect._clearing > 0
    run(effect, 0.6, SILENCE)
    assert int(effect._stacked.sum()) == 0


def test_ram_plasma_glows_brighter_with_the_bass() -> None:
    loud = run(make(RamPlasma, 40), 1, BASS)
    quiet = run(make(RamPlasma, 40), 1, SILENCE)
    assert loud.sum() > quiet.sum() * 1.5


def board_mask(zone: int) -> NDArray[np.bool_]:
    return keyboard_layout(134).zone == zone


def test_key_rain_falls_from_the_back_of_the_board_to_the_front() -> None:
    effect = make(KeyRain, 134, rain=0.2)
    board = keyboard_layout(134)
    keys = board.zone == KEY
    early = run(
        effect, 0.15, FakeAudio(onset=True, lows=0.0, mids=0.0, highs=0.0)
    ).copy()
    later = run(effect, 0.5, SILENCE)
    assert brightest(early, board.y, keys) < brightest(later, board.y, keys)


def test_key_fire_burns_from_the_front_row() -> None:
    loud = run(make(KeyFire, 134, flicker=0.0), 1, BASS)
    quiet = run(make(KeyFire, 134, flicker=0.0), 1, SILENCE)
    assert loud.sum() > quiet.sum() * 1.2
    board = keyboard_layout(134)
    keys = board.zone == KEY
    assert (
        loud[keys & (board.y > 0.85)].mean() > loud[keys & (board.y < 0.3)].mean() * 2
    )


def test_key_wave_grows_taller_with_the_volume() -> None:
    loud = make(KeyWave, 134)
    run(loud, 1, LOUD)
    quiet = make(KeyWave, 134)
    run(quiet, 1, SILENCE)
    assert loud._height > quiet._height + 0.2


def test_key_spotlight_widens_with_the_volume_and_jumps_on_the_beat() -> None:
    loud = plain(make(KeySpotlight, 134))
    quiet = plain(make(KeySpotlight, 134))
    loud_pixels = run(loud, 1, LOUD)
    quiet_pixels = run(quiet, 1, SILENCE)
    assert np.count_nonzero(lit(loud_pixels)) > np.count_nonzero(lit(quiet_pixels)) * 2
    aim = loud._aim.copy()
    frame(loud, FakeAudio(beat=True))
    assert not np.allclose(loud._aim, aim)


def test_key_twinkle_flashes_keys_white_on_the_beat() -> None:
    effect = make(KeyTwinkle, 134, flashes_per_beat=10)
    before = run(effect, 0.3, SILENCE)
    assert np.count_nonzero(before.min(axis=1) > 250) == 0
    pixels = frame(effect, FakeAudio(beat=True))
    assert np.count_nonzero(pixels.min(axis=1) > 250) == 10


@pytest.mark.parametrize("beats, beam", [(1.0, 0.5), (2.5, 0.75), (3.5, 0.25)])
def test_key_scanner_sweeps_the_board_back_and_forth(beats: float, beam: float) -> None:
    effect = plain(make(KeyScanner, 134, beats_per_sweep=2.0))
    run(effect, 0.05, SILENCE)
    effect.song.beats = beats
    pixels = frame(effect)
    assert brightest(pixels, keyboard_layout(134).x, board_mask(KEY)) == pytest.approx(
        beam, abs=0.07
    )


def test_key_rows_stretch_the_bass_row_further_than_the_treble() -> None:
    effect = plain(make(KeyRows, 134, gain=1.0))
    pixels = run(effect, 0.5, LOUD)
    board = keyboard_layout(134)
    rows, count = keyboard_rows(board)
    on = lit(pixels)
    assert on[rows == count - 1].mean() > 0.9
    assert on[board.zone == BAR].mean() < 0.4


def test_key_ghost_typist_strikes_a_key_on_each_hit() -> None:
    effect = make(KeyGhostTypist, 134)
    pixels = frame(effect, FakeAudio(onset=True, lows=0.0, mids=0.0, highs=0.0))
    struck = lit(pixels)
    assert np.count_nonzero(struck) == 1
    assert board_mask(KEY)[struck].all()
    busy = make(KeyGhostTypist, 134)
    run(busy, 2, LOUD)
    assert np.count_nonzero(busy._pressed > 0.05) > 3


def test_key_plasma_glows_brighter_with_the_bass() -> None:
    effect = make(KeyPlasma, 134)
    loud = run(effect, 1, BASS).copy()
    assert not np.allclose(loud, frame(effect, BASS))
    quiet = run(make(KeyPlasma, 134), 1, SILENCE)
    assert loud.sum() > quiet.sum() * 1.5


@pytest.mark.parametrize("beats, right", [(1.0, True), (3.0, False)])
def test_key_radar_sweeps_round_the_board(beats: float, right: bool) -> None:
    effect = make(KeyRadar, 134)
    run(effect, 0.05, SILENCE)
    effect.song.beats = beats
    pixels = frame(effect)
    x = brightest(pixels, keyboard_layout(134).x, board_mask(KEY))
    assert (x > 0.6) if right else (x < 0.4)


MAT = mat_layout(16)
EDGE = ~MAT.mouse


def test_mat_chase_runs_tip_to_tip_and_flashes_the_mouse_midway() -> None:
    effect = plain(make(MatChase, 16, beats_per_lap=2.0))
    run(effect, 0.05, SILENCE)
    effect.song.beats = 0.5
    pixels = frame(effect)
    assert brightest(pixels, MAT.along, EDGE) == pytest.approx(0.25, abs=0.1)
    assert pixels[MAT.mouse].max() < 50
    effect.song.beats = 1.2
    assert frame(effect)[MAT.mouse].min() > 200


def test_mat_flow_speeds_up_with_the_music() -> None:
    loud = make(MatFlow, 16)
    run(loud, 1, LOUD)
    quiet = make(MatFlow, 16)
    run(quiet, 1, SILENCE)
    assert loud._speed > 0.8
    assert quiet._speed < 0.2


def test_mat_converge_runs_down_from_the_tips_and_bursts_at_the_mouse() -> None:
    effect = plain(make(MatConverge, 16, speed=2.0))
    height = mat_height(MAT)
    early = run(effect, 0.1, FakeAudio(beat=True))
    assert early[EDGE & (height > 0.7)].mean() > early[EDGE & (height < 0.3)].mean()
    assert early[MAT.mouse].max() < 50
    later = run(effect, 0.45, SILENCE)
    assert later[MAT.mouse].min() > 100


def test_mat_fire_burns_up_both_sides_from_the_bottom() -> None:
    loud = run(make(MatFire, 16, flicker=0.0), 1, BASS)
    quiet = run(make(MatFire, 16, flicker=0.0), 1, SILENCE)
    assert loud.sum() > quiet.sum() * 1.2
    height = mat_height(MAT)
    assert loud[EDGE & (height < 0.2)].mean() > loud[EDGE & (height > 0.8)].mean() * 1.5


def test_mat_sparkle_sparks_the_mouse_on_a_hit_and_the_edge_with_the_treble() -> None:
    effect = make(MatSparkle, 16)
    pixels = frame(effect, FakeAudio(onset=True, lows=0.0, mids=0.0, highs=0.0))
    assert pixels[MAT.mouse].min() > 250
    assert pixels[EDGE].max() == 0
    busy = make(MatSparkle, 16, density=4.0)
    run(busy, 1, TREBLE)
    assert np.count_nonzero(busy._sparkles[EDGE] > 0.05) >= 3


def test_mat_split_shows_the_bass_left_and_the_treble_right() -> None:
    pixels = run(make(MatSplit, 16), 1, BASS)
    on = lit(pixels)
    left, right = EDGE & (MAT.along < 0.45), EDGE & (MAT.along > 0.55)
    assert on[left].all()
    assert not on[right].any()
    assert not on[MAT.mouse].any()
    assert lit(run(make(MatSplit, 16), 1, LOUD))[MAT.mouse].all()


def test_mat_halfpipe_swings_higher_on_the_beat() -> None:
    def highest(effect: MatHalfpipe, audio: FakeAudio) -> float:
        reach = 0.0
        for index in range(100):
            pixels = frame(effect, audio if index == 0 else SILENCE)
            reach = max(reach, abs(brightest(pixels, MAT.along, EDGE) - 0.5))
        return reach

    kicked = plain(make(MatHalfpipe, 16, kick=0.6))
    calm = plain(make(MatHalfpipe, 16, kick=0.6))
    run(calm, 5, SILENCE)
    assert highest(kicked, FakeAudio(beat=True)) > highest(calm, SILENCE) + 0.2


def test_mat_beat_counter_fills_the_pad_beat_by_beat() -> None:
    effect = plain(make(MatBeatCounter, 16, beats_per_bar=4))
    run(effect, 0.3, SILENCE)
    effect.song.beats = 1.0
    on = lit(frame(effect))
    assert on[EDGE & (MAT.along < 0.45)].all()
    assert not on[EDGE & (MAT.along > 0.55)].any()
    assert not on[MAT.mouse].any()
    effect.song.beats = 4.0
    assert lit(frame(effect))[MAT.mouse].all()


def test_mouse_pulse_throbs_and_ripples_up_the_pad() -> None:
    effect = plain(make(MousePulse, 16))
    height = mat_height(MAT)
    early = frame(effect, FakeAudio(beat=True))
    assert early[MAT.mouse].min() > 200
    assert early[EDGE & (height > 0.8)].max() < 100
    later = run(effect, 0.4, SILENCE)
    middle = EDGE & (np.abs(height - 0.6) < 0.15)
    assert later[middle].mean() > later[EDGE & (height < 0.15)].mean()


def test_mat_comets_shoot_from_alternate_tips() -> None:
    effect = plain(make(MatComets, 16))
    pixels = frame(effect, FakeAudio(onset=True, lows=0.0, mids=0.0, highs=0.0))
    assert brightest(pixels, MAT.along, EDGE) < 0.1
    pixels = run(effect, 0.36, SILENCE)
    # Passing the middle of the pad, the comet sparkles the mouse
    assert pixels[MAT.mouse].min() > 150
    pixels = frame(effect, FakeAudio(onset=True, lows=0.0, mids=0.0, highs=0.0))
    assert effect._comets[-1, 1] == -1
    newest = EDGE & (MAT.along > 0.9)
    assert pixels[newest].max() > 200


# Fifteen more for each device


FANS = fan_layout(48)
RIM = FANS.ring == FAN_RIM
HUB = FANS.ring == FAN_HUB


def fan_sums(pixels: NDArray[np.float64], mask: NDArray[np.bool_] = RIM) -> list[float]:
    return [float(pixels[mask & (FANS.fan == fan)].sum()) for fan in range(3)]


def test_fan_metronome_swings_its_arm_with_the_beat() -> None:
    effect = make(FanMetronome, 48, color="#FFFFFF", swing=0.25)
    run(effect, 0.1, SILENCE)
    rim = RIM & (FANS.fan == 0)
    effect.song.beats = 0.5
    assert brightest(frame(effect), FANS.angle, rim) == pytest.approx(0.25)
    effect.song.beats = 1.5
    assert brightest(frame(effect), FANS.angle, rim) == pytest.approx(0.75)
    assert frame(effect, FakeAudio(beat=True))[HUB].min() > 200


def test_fan_spectrum_puts_the_bass_round_the_bottom_fan() -> None:
    sums = fan_sums(run(plain(make(FanSpectrum, 48, gain=1.0)), 0.5, LOUD))
    assert sums[2] > sums[1] > sums[0]


def test_fan_relay_hands_the_runner_from_fan_to_fan() -> None:
    effect = plain(make(FanRelay, 48, laps_per_beat=0.5))
    run(effect, 0.05, SILENCE)
    effect.song.beats = 0.5
    pixels = frame(effect)
    assert FANS.fan[np.argmax(pixels.sum(axis=1))] == 0
    assert brightest(pixels, FANS.angle, RIM & (FANS.fan == 0)) == pytest.approx(
        0.25, abs=0.09
    )
    effect.song.beats = 2.5
    assert FANS.fan[np.argmax(frame(effect).sum(axis=1))] == 1


def test_fan_breathe_breathes_the_hub_against_the_rim() -> None:
    effect = plain(make(FanBreathe, 48, beats_per_breath=4.0, spread=0.0))
    run(effect, 0.05, LOUD)
    effect.song.beats = 2.0
    pixels = frame(effect, LOUD)
    assert pixels[RIM].mean() > pixels[HUB].mean() * 3
    effect.song.beats = 4.0
    pixels = frame(effect, LOUD)
    assert pixels[HUB].mean() > pixels[RIM].mean() * 3


@pytest.mark.parametrize(
    "order, fans", [("Top to bottom", [1, 2, 0]), ("Bottom to top", [1, 0, 2])]
)
def test_fan_strobe_flashes_the_fans_in_order(order: str, fans: list[int]) -> None:
    effect = make(FanStrobe, 48, order=order)
    seen: list[int] = []
    for _ in fans:
        pixels = frame(effect, FakeAudio(beat=True))
        seen.append(int(np.argmax(fan_sums(pixels))))
        run(effect, 0.3, SILENCE)
    assert seen == fans
    pixels = frame(effect, FakeAudio(onset=True))
    assert pixels[HUB].min() > 200


def test_fan_strobe_can_flash_every_fan() -> None:
    pixels = frame(make(FanStrobe, 48, order="All"), FakeAudio(beat=True))
    assert pixels[RIM].min() > 200


def test_fan_dice_shows_each_fans_roll_in_pips() -> None:
    effect = plain(make(FanDice, 48))
    frame(effect, FakeAudio(beat=True))
    pixels = run(effect, 0.5, SILENCE)
    for fan in range(3):
        pips = np.count_nonzero(lit(pixels[RIM & (FANS.fan == fan)]))
        assert pips == effect._faces[fan]
        six = lit(pixels[HUB & (FANS.fan == fan)]).all()
        assert six == (effect._faces[fan] == 6)


def test_fan_bounce_drops_the_ball_and_the_beat_throws_it_up() -> None:
    effect = make(FanBounce, 48)
    run(effect, 0.6, SILENCE)
    low = effect.ball
    assert low < 0.5
    frame(effect, FakeAudio(beat=True))
    run(effect, 0.2, SILENCE)
    assert effect.ball > low + 0.1


def test_fan_rain_falls_down_the_stack() -> None:
    effect = make(FanRain, 48, rain=0.2)
    height = stack_height(FANS)
    early = brightest(
        run(effect, 0.1, FakeAudio(onset=True, lows=0.0, mids=0.0, highs=0.0)),
        height,
        np.ones(48, dtype=bool),
    )
    later = brightest(run(effect, 0.6, SILENCE), height, np.ones(48, dtype=bool))
    assert later < early


def test_fan_aurora_glows_with_the_music() -> None:
    loud = run(make(FanAurora, 48), 1, LOUD)
    quiet = run(make(FanAurora, 48), 1, SILENCE)
    assert loud.sum() > quiet.sum() * 1.5


def test_fan_yin_yang_splits_each_fan_in_two() -> None:
    pixels = run(make(FanYinYang, 48), 0.5, LOUD)
    white = pixels.min(axis=1) > 200
    for fan in range(3):
        assert np.count_nonzero(white[RIM & (FANS.fan == fan)]) == 6
        assert np.count_nonzero(white[HUB & (FANS.fan == fan)]) == 2


def test_fan_siren_spins_faster_when_loud() -> None:
    loud = make(FanSiren, 48)
    pixels = run(loud, 1, LOUD)
    quiet = make(FanSiren, 48)
    run(quiet, 1, SILENCE)
    assert loud._turn > quiet._turn * 2
    # Red on the top fan, blue on the one below
    top, middle = RIM & (FANS.fan == 0), RIM & (FANS.fan == 1)
    assert pixels[top, 0].sum() > pixels[top, 2].sum()
    assert pixels[middle, 2].sum() > pixels[middle, 0].sum()


def test_fan_starfield_shoots_a_star_on_a_hit_and_waxes_the_moon() -> None:
    effect = make(FanStarfield, 48)
    pixels = frame(effect, FakeAudio(onset=True, lows=0.0, mids=0.0, highs=0.0))
    assert pixels[RIM].min(axis=1).max() > 100
    bright = run(make(FanStarfield, 48), 0.5, BASS)[HUB].sum()
    dark = run(make(FanStarfield, 48), 0.5, SILENCE)[HUB].sum()
    assert bright > dark * 2


def test_fan_timer_runs_the_fans_down_one_after_another() -> None:
    effect = plain(make(FanTimer, 48, beats_per_fan=4.0))
    run(effect, 0.05, SILENCE)

    def rims_lit() -> list[int]:
        on = lit(frame(effect))
        return [int(np.count_nonzero(on[RIM & (FANS.fan == fan)])) for fan in range(3)]

    effect.song.beats = 2.0
    assert rims_lit() == [6, 12, 12]
    effect.song.beats = 6.0
    assert rims_lit() == [0, 6, 12]


@pytest.mark.parametrize("beats, fan", [(1.0, 2), (2.5, 1), (3.5, 0)])
def test_fan_traffic_light_goes_green_amber_red(beats: float, fan: int) -> None:
    effect = make(FanTrafficLight, 48)
    run(effect, 0.05, SILENCE)
    effect.song.beats = beats
    assert int(np.argmax(fan_sums(frame(effect)))) == fan


def test_fan_storm_strikes_a_fan_and_flickers_again() -> None:
    effect = make(FanStorm, 48)
    run(effect, 0.1, SILENCE)
    pixels = frame(effect, FakeAudio(onset=True))
    struck = pixels.min(axis=1) > 200
    assert np.unique(FANS.fan[struck]).size == 1
    assert np.count_nonzero(struck) == 16
    dimmed = run(effect, 0.05, SILENCE).max()
    again = run(effect, 0.04, SILENCE).max()
    assert again > dimmed


def rising(size: int) -> NDArray[np.float64]:
    return np.linspace(0.2, 1.0, size)


def treble_heavy(filtered: bool = False, size: int = 0) -> NDArray[np.float64]:
    return rising(size or 24)


def test_pump_compass_points_west_for_bass_and_east_for_treble() -> None:
    bassy = make(PumpCompass, 24)
    run(bassy, 2, LOUD)
    assert bassy.needle < -0.02
    bright = make(PumpCompass, 24)
    vars(bright)["melbank"] = treble_heavy
    run(bright, 2, LOUD)
    assert bright.needle > 0.02


def test_pump_beat_ring_fills_a_step_a_beat() -> None:
    effect = plain(make(PumpBeatRing, 24, beats_per_ring=16))
    run(effect, 0.05, SILENCE)
    effect.song.beats = 5.0
    pixels = frame(effect)
    assert pixels[5].min() > 250
    assert lit(pixels[:5], 100).all()
    assert not lit(pixels[6:16], 50).any()


def test_pump_orbit_flashes_the_fans_where_the_moons_meet() -> None:
    effect = make(PumpOrbit, 24)
    flashes = 0.0
    for _ in range(30):
        flashes = max(flashes, float(frame(effect, LOUD)[16:].max()))
    assert flashes > 150


def test_pump_spectrum_puts_the_bass_at_the_bottom() -> None:
    pixels = run(plain(make(PumpSpectrum, 24, gain=1.0)), 0.5, LOUD)
    assert pixels[8].sum() > pixels[0].sum() * 2
    assert pixels[16:20].sum() > pixels[20:24].sum()


def test_pump_breathe_breathes_the_pump_against_the_radiator() -> None:
    effect = plain(make(PumpBreathe, 24, beats_per_breath=4.0))
    run(effect, 0.05, LOUD)
    effect.song.beats = 2.0
    pixels = frame(effect, LOUD)
    assert pixels[:16].mean() > pixels[16:].mean() * 3


def test_pump_beacon_sweeps_with_the_bar_and_lights_the_fan_it_passes() -> None:
    effect = make(PumpBeacon, 24)
    run(effect, 0.05, SILENCE)
    effect.song.beats = 1.0
    pixels = frame(effect)
    assert int(np.argmax(pixels[:16].sum(axis=1))) == 4
    # A quarter turn round: the beam points at the fan on the right
    assert pixels[20:24].sum() > pixels[16:20].sum() * 3


def test_pump_galaxy_turns_faster_when_loud() -> None:
    loud = make(PumpGalaxy, 24)
    run(loud, 1, LOUD)
    quiet = make(PumpGalaxy, 24)
    run(quiet, 1, SILENCE)
    assert loud._turn > quiet._turn * 2


def test_pump_collide_bursts_where_the_pulses_meet() -> None:
    effect = make(PumpCollide, 24, speed=0.8)
    frame(effect, FakeAudio(onset=True, lows=0.0, mids=0.0, highs=0.0))
    assert len(effect._pulses) == 1
    assert run(effect, 0.2, SILENCE)[16:].max() < 20
    assert run(effect, 0.5, SILENCE)[16:].max() > 100


def test_pump_mandala_repeats_round_the_ring() -> None:
    pixels = run(make(PumpMandala, 24, folds=4), 0.5, LOUD)
    np.testing.assert_allclose(pixels[:16], np.roll(pixels[:16], 4, axis=0), atol=1e-6)


def test_pump_fireball_races_with_the_bass() -> None:
    loud = make(PumpFireball, 24)
    run(loud, 0.5, BASS)
    quiet = make(PumpFireball, 24)
    run(quiet, 0.5, SILENCE)
    assert loud.at > quiet.at + 0.3


def test_pump_aurora_glows_with_the_music() -> None:
    loud = run(make(PumpAurora, 24), 1, LOUD)
    quiet = run(make(PumpAurora, 24), 1, SILENCE)
    assert loud.sum() > quiet.sum() * 1.5


def test_pump_drip_lets_a_drop_go_on_the_beat_and_it_splashes_below() -> None:
    effect = make(PumpDrip, 24)
    run(effect, 1, SILENCE)
    assert effect.forming > 0.3
    frame(effect, FakeAudio(beat=True))
    assert effect.forming == 0
    assert effect._drops.size == 1
    assert run(effect, 0.3, SILENCE)[16:].max() < 20
    assert run(effect, 0.7, SILENCE)[16:].max() > 100


def test_pump_strobe_flashes_the_pump_on_beats_and_the_fans_on_hits() -> None:
    beat = frame(make(PumpStrobe, 24), FakeAudio(beat=True))
    assert beat[:16].min() > 200
    assert beat[16:].max() == 0
    hit = frame(make(PumpStrobe, 24), FakeAudio(onset=True))
    assert hit[16:].min() > 200
    assert hit[:16].max() == 0


def test_pump_loop_carries_each_pulse_from_the_pump_to_the_radiator() -> None:
    effect = make(PumpLoop, 24, speed=1.0)
    early = frame(effect, FakeAudio(beat=True, lows=0.0, mids=0.0, highs=0.0))
    assert early[0].max() > 200
    assert early[16:].max() < 50
    later = run(effect, 1.1, SILENCE)
    assert later[16:].max() > 100


def test_pump_sonar_pings_down_the_ring_and_finds_the_radiator() -> None:
    effect = make(PumpSonar, 24)
    early = frame(effect, FakeAudio(beat=True))
    assert early[0].max() > early[8].max()
    assert run(effect, 0.3, SILENCE)[16:].max() < 20
    assert run(effect, 0.3, SILENCE)[16:].max() > 100


RAM = ram_layout(40)


def test_ram_waterfall_lets_the_music_flow_down_the_sticks() -> None:
    effect = plain(make(RamWaterfall, 40, gain=1.0))
    early = run(effect, 0.05, LOUD).copy()
    top, bottom = RAM.height == 1, RAM.height == 0
    assert early[top & (RAM.stick == 0)].sum() > early[top & (RAM.stick == 3)].sum()
    assert early[bottom].max() < 10
    later = run(effect, 2, LOUD)
    assert later[bottom & (RAM.stick == 0)].max() > 100


def test_ram_rain_falls_and_splashes_at_the_bottom() -> None:
    effect = make(RamRain, 40, rain=0.2)
    frame(effect, FakeAudio(onset=True, lows=0.0, mids=0.0, highs=0.0))
    assert len(effect._drops) >= 2
    assert (effect._drops[:, 1] > 0.9).all()
    run(effect, 2, SILENCE)
    assert effect._puddles.max() > 0


def test_ram_breathe_runs_the_breath_across_the_sticks() -> None:
    effect = plain(make(RamBreathe, 40, beats_per_breath=4.0, spread=0.25))
    run(effect, 0.05, LOUD)
    effect.song.beats = 2.0
    sums = stick_sums(frame(effect, LOUD))
    assert sums[0] > sums[2] * 2


@pytest.mark.parametrize(
    "order, sticks",
    [("Ping pong", [1, 2, 3, 2, 1, 0]), ("Left to right", [1, 2, 3, 0])],
)
def test_ram_strobe_flashes_the_sticks_in_order(order: str, sticks: list[int]) -> None:
    effect = make(RamStrobe, 40, order=order)
    seen: list[int] = []
    for _ in sticks:
        seen.append(int(np.argmax(stick_sums(frame(effect, FakeAudio(beat=True))))))
        run(effect, 0.3, SILENCE)
    assert seen == sticks


def test_ram_snake_grows_a_led_each_beat() -> None:
    effect = plain(make(RamSnake, 40))
    assert np.count_nonzero(lit(run(effect, 0.2, SILENCE))) == 3
    frame(effect, FakeAudio(beat=True))
    assert np.count_nonzero(lit(run(effect, 0.2, SILENCE))) == 4


def test_ram_bounce_throws_the_bass_ball_highest() -> None:
    effect = make(RamBounce, 40)
    run(effect, 0.2, BASS)
    frame(effect, FakeAudio(beat=True, lows=1.0, mids=0.0, highs=0.0))
    run(effect, 0.25, BASS)
    assert effect.balls[0] > effect.balls[3] + 0.1


def test_ram_lava_lamp_glows_hotter_with_the_bass() -> None:
    loud = run(make(RamLavaLamp, 40), 1, BASS)
    quiet = run(make(RamLavaLamp, 40), 1, SILENCE)
    assert loud.sum() > quiet.sum()


def test_ram_aurora_glows_with_the_music() -> None:
    loud = run(make(RamAurora, 40), 1, LOUD)
    quiet = run(make(RamAurora, 40), 1, SILENCE)
    assert loud.sum() > quiet.sum() * 1.5


def test_ram_battery_charges_the_sticks_one_after_another() -> None:
    effect = make(RamBattery, 40, charge_rate=2.0)
    run(effect, 1.2, LOUD)
    assert effect.charges[:2].tolist() == [1.0, 1.0]
    assert effect.charges[3] == 0
    quiet = make(RamBattery, 40)
    run(quiet, 1, SILENCE)
    assert not quiet.charges.any()
    run(effect, 1.0, LOUD)
    # All charged: the bank flashes white, then empties
    assert effect._full > 0
    run(effect, 0.7, SILENCE)
    assert not effect.charges.any()


def test_ram_comets_climb_the_sticks() -> None:
    effect = make(RamComets, 40)
    early = run(effect, 0.1, FakeAudio(onset=True))
    low = brightest(early, RAM.height, np.ones(40, dtype=bool))
    later = run(effect, 0.3, SILENCE)
    assert brightest(later, RAM.height, np.ones(40, dtype=bool)) > low + 0.3


def test_ram_pong_keeps_the_ball_in_play() -> None:
    effect = make(RamPong, 40)
    for _ in range(4):
        run(effect, 1, FakeAudio(beat=True))
        assert 0 <= effect.across <= 3
        assert 0 <= effect.up <= 1
    assert effect._boost > 1


def test_ram_timer_runs_down_from_the_right_stick() -> None:
    effect = plain(make(RamTimer, 40, beats=16))
    # Past the flash of the first fill
    run(effect, 1.5, SILENCE)
    effect.song.beats = 4.0
    on = lit(frame(effect))
    assert on[RAM.stick < 3].all()
    assert not on[RAM.stick == 3].any()


def test_ram_stairs_turn_round_on_each_beat() -> None:
    effect = make(RamStairs, 40)
    run(effect, 1, LOUD)
    assert (np.diff(effect.steps) > 0).all()
    frame(effect, FakeAudio(beat=True, lows=1.0, mids=1.0, highs=1.0))
    run(effect, 1, LOUD)
    assert (np.diff(effect.steps) < 0).all()


def test_ram_glitch_inverts_a_stick_on_a_hit() -> None:
    effect = make(RamGlitch, 40)
    pixels = frame(effect, FakeAudio(onset=True, lows=0.0, mids=0.0, highs=0.0))
    inverted = pixels.min(axis=1) > 180
    assert np.count_nonzero(inverted) == 10
    assert np.unique(RAM.stick[inverted]).size == 1


def test_ram_fireworks_launch_on_the_beat_and_burst() -> None:
    effect = make(RamFireworks, 40)
    frame(effect, FakeAudio(beat=True))
    assert len(effect._rockets) == 1
    run(effect, 0.5, SILENCE)
    assert len(effect._rockets) == 0
    assert len(effect._bursts) == 1


BOARD = keyboard_layout(134)
KEYS = BOARD.zone == KEY


def test_key_warp_streams_faster_when_loud() -> None:
    loud = make(KeyWarp, 134)
    quiet = make(KeyWarp, 134)
    start = loud._distances.copy()
    frame(loud, LOUD)
    frame(quiet, SILENCE)
    # Leaving out any star that went off the board and was reborn
    loud_moved, quiet_moved = loud._distances - start, quiet._distances - start
    kept = (loud_moved > 0) & (quiet_moved > 0)
    assert loud_moved[kept].sum() > quiet_moved[kept].sum() * 2


def test_key_snake_grows_on_the_beat() -> None:
    effect = plain(make(KeySnake, 134))
    run(effect, 1, LOUD)
    assert len(effect.body) == 4
    frame(effect, FakeAudio(beat=True, lows=1.0, mids=1.0, highs=1.0))
    pixels = run(effect, 0.5, LOUD)
    assert len(effect.body) == 5
    assert np.count_nonzero(lit(pixels, 60)) >= 4


def test_key_fireworks_launch_from_the_front_and_burst() -> None:
    effect = make(KeyFireworks, 134)
    pixels = frame(effect, FakeAudio(beat=True))
    assert brightest(pixels, BOARD.y, KEYS) > 0.8
    run(effect, 0.7, SILENCE)
    assert len(effect._bursts) == 1


def test_key_aurora_hangs_from_the_light_bar() -> None:
    effect = make(KeyAurora, 134)
    total = np.zeros((134, 3))
    for _ in range(60):
        total += frame(effect, LOUD)
    assert total[KEYS & (BOARD.y < 0.3)].mean() > total[KEYS & (BOARD.y > 0.8)].mean()
    quiet = run(make(KeyAurora, 134), 1, SILENCE)
    assert total.sum() / 60 > quiet.sum() * 1.5


def test_key_spectrogram_scrolls_from_the_right() -> None:
    effect = plain(make(KeySpectrogram, 134, gain=1.0))
    early = run(effect, 0.1, LOUD).copy()
    right, left = KEYS & (BOARD.x > 0.95), KEYS & (BOARD.x < 0.5)
    assert early[right].mean() > early[left].mean() * 3
    later = run(effect, 3, LOUD)
    assert later[left].mean() > 50


def test_key_breathe_breathes_out_from_the_middle() -> None:
    effect = plain(make(KeyBreathe, 134, beats_per_breath=4.0, spread=0.6))
    run(effect, 0.05, LOUD)
    effect.song.beats = 2.0
    pixels = frame(effect, LOUD)
    distance = effect._distance
    assert pixels[distance < 0.2].mean() > pixels[distance > 0.8].mean() * 2


def test_key_strobe_flashes_a_third_each_beat_and_the_bar_on_hits() -> None:
    effect = make(KeyStrobe, 134)
    pixels = frame(effect, FakeAudio(beat=True))
    assert lit(pixels[KEYS & (BOARD.x < 0.3)]).all()
    assert not lit(pixels[KEYS & (BOARD.x > 0.4)]).any()
    assert lit(pixels[BOARD.zone == LOGO]).all()
    run(effect, 0.3, SILENCE)
    pixels = frame(effect, FakeAudio(beat=True))
    assert lit(pixels[KEYS & (BOARD.x > 0.37) & (BOARD.x < 0.63)]).all()
    pixels = frame(make(KeyStrobe, 134), FakeAudio(onset=True))
    assert lit(pixels[BOARD.zone == BAR]).all()
    assert not lit(pixels[KEYS]).any()


def test_key_lava_lamp_glows_hotter_with_the_bass() -> None:
    loud = run(make(KeyLavaLamp, 134), 1, BASS)
    quiet = run(make(KeyLavaLamp, 134), 1, SILENCE)
    assert loud.sum() > quiet.sum()


def test_key_pong_paddles_follow_the_ball() -> None:
    effect = make(KeyPong, 134)
    pixels = run(effect, 3, FakeAudio(beat=True))
    assert effect._top <= effect.ball[1] <= effect._bottom
    assert 0 < effect.ball[0] < 1
    assert np.abs(effect.paddles - effect.ball[1]).max() < 0.1
    assert lit(pixels[BOARD.x < 0.06], 150).any()


def test_key_rainbow_flows_with_the_song() -> None:
    effect = make(KeyRainbow, 134, tilt=0.0)
    before = run(effect, 0.05, SILENCE).copy()
    effect.song.beats = 1.0
    after = frame(effect)
    assert not np.allclose(before, after)
    # Upright bands: the keys in a column share a color
    column = np.flatnonzero(np.isclose(BOARD.x, BOARD.x[KEYS][0]))
    assert np.allclose(after[column], after[column[0]])


def test_key_storm_strikes_from_the_light_bar_to_the_front() -> None:
    pixels = frame(make(KeyStorm, 134), FakeAudio(onset=True))
    bolt = pixels.min(axis=1) > 150
    assert bolt[BOARD.y < 0.3].any()
    assert bolt[BOARD.y > 0.7].any()


def test_key_comets_fly_along_one_row() -> None:
    effect = make(KeyComets, 134)
    frame(effect, FakeAudio(onset=True, lows=0.0, mids=0.0, highs=0.0))
    pixels = run(effect, 0.2, SILENCE)
    rows, _ = keyboard_rows(BOARD)
    on = lit(pixels, 50)
    assert on.any()
    assert np.unique(rows[on]).size == 1


def test_key_split_fills_the_bass_from_the_left_edge() -> None:
    pixels = run(make(KeySplit, 134), 1, BASS)
    on = lit(pixels)
    assert on[KEYS & (BOARD.x < 0.45)].all()
    assert not on[KEYS & (BOARD.x > 0.55)].any()


def test_key_spiral_turns_with_the_song() -> None:
    effect = make(KeySpiral, 134)
    before = run(effect, 0.05, LOUD).copy()
    effect.song.beats = 1.0
    assert not np.allclose(before, frame(effect, LOUD))


def test_key_checkerboard_swaps_its_squares_on_the_beat() -> None:
    effect = make(KeyCheckerboard, 134)
    first = effect.squares()
    assert first.any()
    assert not first.all()
    before = frame(effect, SILENCE).copy()
    after = frame(effect, FakeAudio(beat=True))
    # A pink square turns blue
    key = int(np.flatnonzero(first)[0])
    assert before[key, 0] > before[key, 2]
    assert after[key, 2] > after[key, 0]


HEIGHT = mat_height(MAT)


def test_mat_breathe_fills_the_pad_from_the_bottom() -> None:
    effect = plain(make(MatBreathe, 16, beats_per_breath=4.0))
    run(effect, 0.05, SILENCE)
    effect.song.beats = 1.0
    on = lit(frame(effect))
    assert on[EDGE & (HEIGHT < 0.3)].all()
    assert not on[EDGE & (HEIGHT > 0.7)].any()
    effect.song.beats = 2.0
    assert lit(frame(effect)).all()


def test_mat_strobe_flashes_the_sides_in_turn_and_the_mouse_on_hits() -> None:
    effect = make(MatStrobe, 16)
    left, right = EDGE & (MAT.along < 0.45), EDGE & (MAT.along > 0.55)
    first = frame(effect, FakeAudio(beat=True))
    assert lit(first[left]).all()
    assert not lit(first[right]).any()
    run(effect, 0.3, SILENCE)
    second = frame(effect, FakeAudio(beat=True))
    assert lit(second[right]).all()
    assert not lit(second[MAT.mouse]).any()
    assert lit(frame(effect, FakeAudio(onset=True))[MAT.mouse]).all()


def test_mat_rain_pools_round_the_mouse() -> None:
    effect = make(MatRain, 16, rain=0.2)
    frame(effect, FakeAudio(onset=True, lows=0.0, mids=0.0, highs=0.0))
    assert len(effect._drops) >= 2
    pixels = run(effect, 2, SILENCE)
    assert effect.pool > 0
    assert pixels[MAT.mouse].max() > 10


def test_mat_aurora_glows_with_the_music() -> None:
    loud = run(make(MatAurora, 16), 1, LOUD)
    quiet = run(make(MatAurora, 16), 1, SILENCE)
    assert loud.sum() > quiet.sum() * 1.5


def test_mat_spectrum_puts_the_bass_at_the_bottom() -> None:
    pixels = run(plain(make(MatSpectrum, 16, gain=1.0)), 0.5, LOUD)
    assert (
        pixels[EDGE & (HEIGHT < 0.2)].mean() > pixels[EDGE & (HEIGHT > 0.8)].mean() * 2
    )


def test_mat_lava_lamp_glows_hotter_with_the_music() -> None:
    loud = run(make(MatLavaLamp, 16), 1, LOUD)
    quiet = run(make(MatLavaLamp, 16), 1, SILENCE)
    assert loud.sum() > quiet.sum()


def test_mat_snake_grows_on_the_beat_and_crosses_under_the_mouse() -> None:
    effect = make(MatSnake, 16)
    frame(effect, FakeAudio(beat=True, lows=1.0, mids=1.0, highs=1.0))
    assert effect.length == pytest.approx(0.16)
    passing = 0.0
    for _ in range(60):
        passing = max(passing, float(frame(effect, LOUD)[MAT.mouse].max()))
    assert passing > 200


def test_mat_rainbow_jolts_round_on_the_beat() -> None:
    effect = make(MatRainbow, 16, jump=0.2)
    run(effect, 0.1, SILENCE)
    before = effect.shift
    frame(effect, FakeAudio(beat=True))
    run(effect, 0.5, SILENCE)
    assert effect.shift - before == pytest.approx(0.2, abs=0.03)


def test_mat_pulse_line_writes_a_spike_on_the_beat() -> None:
    effect = make(MatPulseLine, 16, color="#00FF00")
    run(effect, 0.1, SILENCE)
    effect.song.beats = 0.5
    pixels = frame(effect, FakeAudio(beat=True))
    spiked = EDGE & (MAT.along > 0.02) & (MAT.along <= 0.12)
    assert pixels[spiked].min() > 200
    assert pixels[MAT.mouse].min() > 200


def test_mat_ripples_spread_and_reach_the_mouse() -> None:
    effect = make(MatRipples, 16)
    frame(effect, FakeAudio(onset=True, lows=0.0, mids=0.0, highs=0.0))
    assert len(effect._ripples) == 1
    flash = 0.0
    for _ in range(90):
        flash = max(flash, float(frame(effect, SILENCE)[MAT.mouse].max()))
    assert flash > 150


def test_mat_glitch_inverts_the_pad_on_a_hit() -> None:
    pixels = frame(
        make(MatGlitch, 16), FakeAudio(onset=True, lows=0.0, mids=0.0, highs=0.0)
    )
    assert pixels[EDGE].min() > 180


@pytest.mark.parametrize("audio, red", [(BASS, True), (TREBLE, False)])
def test_mouse_mood_turns_red_for_bass_and_blue_for_treble(
    audio: FakeAudio, red: bool
) -> None:
    mouse = run(make(MouseMood, 16), 3, audio)[MAT.mouse][0]
    assert (mouse[0] > mouse[2]) if red else (mouse[2] > mouse[0])


def test_mat_timer_runs_the_pad_down_from_the_right() -> None:
    effect = plain(make(MatTimer, 16, beats=8))
    run(effect, 0.3, SILENCE)
    effect.song.beats = 4.0
    on = lit(frame(effect))
    assert on[EDGE & (MAT.along < 0.45)].all()
    assert not on[EDGE & (MAT.along > 0.55)].any()
    assert not on[MAT.mouse].any()
    effect.song.beats = 8.0
    assert lit(frame(effect))[MAT.mouse].all()


def test_mat_fireworks_launch_from_the_mouse_and_burst_at_a_tip() -> None:
    effect = make(MatFireworks, 16)
    assert frame(effect, FakeAudio(beat=True))[MAT.mouse].min() > 200
    pixels = run(effect, 0.6, SILENCE)
    assert len(effect._bursts) == 1
    assert pixels[EDGE & (HEIGHT > 0.8)].max() > 50


def test_mat_siren_flashes_one_side_at_a_time() -> None:
    effect = make(MatSiren, 16)
    left, right = EDGE & (MAT.along < 0.45), EDGE & (MAT.along > 0.55)
    sides: set[str] = set()
    for _ in range(120):
        on = lit(frame(effect, SILENCE))
        assert not (on[left].any() and on[right].any())
        sides |= {"left"} if on[left].any() else set()
        sides |= {"right"} if on[right].any() else set()
    assert sides == {"left", "right"}


def test_ram_meter_takes_its_colors_from_the_settings() -> None:
    effect = make(
        RamMeter,
        40,
        bottom_color="#0000FF",
        middle_color="#0000FF",
        top_color="#0000FF",
        peak_color="#00FF00",
    )
    pixels = run(effect, 1, LOUD)
    ram = ram_layout(40)
    # The full sticks are blue all the way up, but for the green peak dots
    peaks = pixels[:, 1] > 200
    assert np.unique(ram.stick[peaks]).size == 4
    assert (pixels[~peaks, 2] > 200).all()
    assert pixels[~peaks, :2].max() == 0
