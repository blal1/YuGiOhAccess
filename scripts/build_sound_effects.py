"""Build the duel sound effects the client asks for but does not ship.

The client announces what happens in a duel twice: once in words, and once as
a sound. Twenty-two of those sounds had no file, so ``play_duel_sound_effect``
logged one warning and stayed silent -- every destroy, every attack, every
phase change. This script produces them.

Two sources, and the difference matters:

* Files marked CC0 in the Lahrenheit EDOPro soundpack. Public domain, so they
  can be copied and altered freely. Pass ``--soundpack`` to point at a clone
  of https://github.com/Lahrenheit/EDOPRO-Soundpack.
* Everything else is synthesised here from scratch, so it belongs to this
  project and carries no conditions at all.

Nothing is taken from the Timtam MUD soundpack: its README states the effects
were taken from the Yu-Gi-Oh games and anime, and forbids their use in
unrelated projects.

Usage::

    python scripts/build_sound_effects.py --soundpack ../EDOPRO-Soundpack
    python scripts/build_sound_effects.py --check

Output is mono 44.1 kHz FLAC. Mono on purpose: OpenAL only positions mono
sources, and the client plays several of these at a position.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).parent.parent
DUEL_SOUNDS = ROOT / "src" / "data" / "sounds" / "duel"
SOURCE_DIR = ROOT / "src"

SAMPLE_RATE = 44100
# Short on purpose. A player hears these hundreds of times in a duel, and a
# long effect either talks over the screen reader or gets cut off by it.
MAX_SECONDS = 0.8
# Loudness the whole set is levelled to, and the peak no effect may pass.
# Picked to sit just under the existing duel effects, so a cue supports the
# screen reader rather than competing with it.
TARGET_RMS = 0.13
PEAK_CEILING = 0.8

RNG = np.random.default_rng(20240613)  # fixed, so rebuilds are identical


# ---------------------------------------------------------------- helpers ---

def load_mono(path: Path) -> np.ndarray:
    """Read a file as mono float at the project sample rate."""
    data, rate = sf.read(str(path), dtype="float64", always_2d=True)
    mono = data.mean(axis=1)
    if rate != SAMPLE_RATE:
        mono = resample(mono, len(mono) * SAMPLE_RATE / rate)
    return mono


def resample(signal: np.ndarray, length: float) -> np.ndarray:
    """Stretch or squeeze a signal to ``length`` samples by interpolation."""
    length = max(1, int(round(length)))
    if len(signal) < 2:
        return np.zeros(length)
    source = np.linspace(0.0, len(signal) - 1, num=length)
    return np.interp(source, np.arange(len(signal)), signal)


def change_speed(signal: np.ndarray, factor: float) -> np.ndarray:
    """Play a signal faster or slower, pitch and all, like a tape machine.

    Used to turn one swipe into a family of phase cues that a listener can
    tell apart without having to be told which is which.
    """
    return resample(signal, len(signal) / factor)


def trim_silence(signal: np.ndarray, threshold: float = 0.005) -> np.ndarray:
    loud = np.flatnonzero(np.abs(signal) > threshold)
    if loud.size == 0:
        return signal
    return signal[loud[0]:loud[-1] + 1]


def fade(signal: np.ndarray, in_ms: float = 3.0, out_ms: float = 25.0) -> np.ndarray:
    """Taper both ends, so nothing clicks when the buffer starts or stops."""
    signal = signal.copy()
    fade_in = min(int(SAMPLE_RATE * in_ms / 1000), len(signal) // 2)
    fade_out = min(int(SAMPLE_RATE * out_ms / 1000), len(signal) // 2)
    if fade_in:
        signal[:fade_in] *= np.linspace(0.0, 1.0, fade_in)
    if fade_out:
        signal[-fade_out:] *= np.linspace(1.0, 0.0, fade_out)
    return signal


def normalise(signal: np.ndarray, target_rms: float = TARGET_RMS,
              ceiling: float = PEAK_CEILING) -> np.ndarray:
    """Level an effect by loudness, then hold it under a peak ceiling.

    Matching peaks is not enough: a click and a sustained swipe with the same
    peak are nothing like as loud as each other, and this set is meant to be
    heard under a screen reader. So the loudness is matched first, and the
    ceiling only steps in for the sharpest transients.
    """
    if not signal.size:
        return signal
    rms = float(np.sqrt(np.mean(signal ** 2)))
    if rms > 1e-9:
        signal = signal * (target_rms / rms)
    highest = float(np.max(np.abs(signal)))
    if highest > ceiling:
        signal = signal * (ceiling / highest)
    return signal


def tame_transients(signal: np.ndarray, max_crest: float = 9.0) -> np.ndarray:
    """Round off the spikes on a very peaky recording.

    A card flip is nearly all click: its peak is enormous and its average is
    tiny, so levelling it by loudness runs into the peak ceiling long before
    it is as loud as the rest of the set, and the cue goes unheard. Softening
    the spike lets the body of the sound come up.
    """
    if not signal.size:
        return signal
    rms = float(np.sqrt(np.mean(signal ** 2)))
    peak = float(np.max(np.abs(signal)))
    if rms < 1e-9 or peak < 1e-9:
        return signal
    crest = peak / rms
    if crest <= max_crest:
        return signal
    drive = min(8.0, 2.0 * crest / max_crest)
    return np.tanh(drive * signal / peak) / np.tanh(drive)


def finish(signal: np.ndarray, max_seconds: float = MAX_SECONDS) -> np.ndarray:
    """Trim, shorten, taper and level a finished effect."""
    signal = trim_silence(signal)
    limit = int(SAMPLE_RATE * max_seconds)
    if len(signal) > limit:
        signal = signal[:limit]
    return normalise(tame_transients(fade(signal)))


def seconds(duration: float) -> np.ndarray:
    return np.arange(int(SAMPLE_RATE * duration)) / SAMPLE_RATE


# ------------------------------------------------------------ synthesisers --

def tone(frequency: float, duration: float, decay: float = 12.0,
         harmonics: tuple[float, ...] = (1.0, 0.35, 0.12)) -> np.ndarray:
    """A plain decaying tone with a couple of harmonics for body."""
    t = seconds(duration)
    wave = np.zeros_like(t)
    for index, gain in enumerate(harmonics, start=1):
        wave += gain * np.sin(2 * np.pi * frequency * index * t)
    return wave * np.exp(-decay * t)


def glide(start_hz: float, end_hz: float, duration: float,
          decay: float = 3.0) -> np.ndarray:
    """A tone that slides from one pitch to another."""
    t = seconds(duration)
    sweep = np.linspace(start_hz, end_hz, len(t))
    phase = 2 * np.pi * np.cumsum(sweep) / SAMPLE_RATE
    return np.sin(phase) * np.exp(-decay * t)


def noise(duration: float, decay: float = 18.0, colour: float = 0.0) -> np.ndarray:
    """Filtered noise. ``colour`` from 0 (bright) to 1 (dull)."""
    t = seconds(duration)
    raw = RNG.uniform(-1.0, 1.0, len(t))
    if colour > 0:
        # One pole low pass; cheap, and all these effects need is a tilt.
        filtered = np.empty_like(raw)
        state = 0.0
        for index, sample in enumerate(raw):
            state += (sample - state) * (1.0 - colour)
            filtered[index] = state
        raw = filtered
    return raw * np.exp(-decay * t)


def pluck(frequency: float, duration: float, damping: float = 0.996) -> np.ndarray:
    """Karplus-Strong string. Reads as a card being handled rather than a beep."""
    length = max(2, int(SAMPLE_RATE / frequency))
    buffer = RNG.uniform(-1.0, 1.0, length)
    total = int(SAMPLE_RATE * duration)
    out = np.empty(total)
    for index in range(total):
        out[index] = buffer[index % length]
        nxt = (index + 1) % length
        buffer[index % length] = damping * 0.5 * (buffer[index % length] + buffer[nxt])
    return out


def silence(duration: float) -> np.ndarray:
    return np.zeros(int(SAMPLE_RATE * duration))


def join(*parts: np.ndarray) -> np.ndarray:
    return np.concatenate([part for part in parts if part.size])


def mix(*parts: np.ndarray) -> np.ndarray:
    length = max(part.size for part in parts)
    total = np.zeros(length)
    for part in parts:
        total[:part.size] += part
    return total


# ----------------------------------------------------- the effects we make --

def synthesised() -> dict[str, np.ndarray]:
    """Effects with no free recording to draw on, built here.

    Each one is shaped around the thing it reports, so that the set can be
    told apart by ear: things that leave the field fall in pitch, things that
    come back rise, and anything the player must react to is short and bright.
    """
    return {
        # Something is being aimed at: two rising blips, urgent and dry.
        "aim": join(tone(880, 0.07, decay=28), silence(0.03), tone(1320, 0.09, decay=24)),
        # An xyz material comes off its monster: a short fall, then a click.
        "detach": join(tone(660, 0.09, decay=20), tone(440, 0.12, decay=18), noise(0.05, decay=45, colour=0.3)),
        # Card to the graveyard from the hand: paper, falling away.
        "discard": mix(noise(0.22, decay=13, colour=0.55), glide(520, 190, 0.22, decay=9)),
        # Card coming back to where it started: the same shape, upwards.
        "return": mix(noise(0.26, decay=9, colour=0.6), glide(260, 700, 0.26, decay=5)),
        # Control changes hands: two glides crossing over each other.
        "swapcontrol": mix(glide(700, 300, 0.30, decay=5), glide(300, 700, 0.30, decay=5)),
        # A tribute is given up: three notes down, deliberate and low.
        "tribute": join(pluck(440, 0.11), pluck(330, 0.12), pluck(220, 0.26)),
        # To the graveyard: a low thud with a short tail.
        "sendtograve": mix(tone(120, 0.34, decay=11, harmonics=(1.0, 0.2)), noise(0.07, decay=40, colour=0.75)),
        # Back into the deck: one card-sized click and a small rise.
        "sendtodeck": mix(noise(0.10, decay=30, colour=0.45), glide(330, 520, 0.16, decay=10)),
        # Back into the extra deck: the same idea, twice and higher, because
        # the two are easy to confuse and mean different things.
        "sendtoextradeck": join(
            mix(noise(0.07, decay=34, colour=0.4), glide(440, 660, 0.10, decay=12)),
            silence(0.02),
            mix(noise(0.07, decay=34, colour=0.4), glide(560, 840, 0.14, decay=12)),
        ),
    }


# Effects copied straight from a CC0 recording: (target, source file, trim).
DIRECT = (
    ("attack", "attack.wav", 0.8),
    ("shuffle", "shuffle.wav", 0.8),
    ("destroy", "damage.wav", 0.7),
    ("switch_flip", "flip.wav", 0.6),
    ("switch_facedown", "set.wav", 0.6),
)

# Effects built from a CC0 recording: the recording sets the family sound,
# and a short pitched signature after it says which member of the family this
# is. Speed alone was not enough. Reversing the swipe for "damage step over"
# produced something all but identical to the swipe for "damage step", and two
# cues that mean opposite things have to be told apart on the first hearing.
#
# (target, source, playback speed, signature)
DERIVED = (
    # The phases of a turn, low to high, in the order they happen.
    ("phase/standby", "phase.wav", 0.85, lambda: tone(330, 0.16, decay=14)),
    ("phase/main", "phase.wav", 1.00, lambda: tone(440, 0.16, decay=14)),
    # Battle gets two notes: it is the phase that changes what the player may
    # do, so it should stand out from the ones that merely pass by.
    ("phase/battle", "phase.wav", 1.18,
     lambda: join(tone(554, 0.09, decay=20), tone(659, 0.16, decay=16))),
    # Damage lands: a low thud under the swipe.
    ("phase/damage", "phase.wav", 1.35, lambda: tone(180, 0.20, decay=13, harmonics=(1.0, 0.25))),
    # Damage resolves: the same low voice, rising and settling.
    ("phase/damageend", "phase.wav", 1.35,
     lambda: join(tone(180, 0.09, decay=18, harmonics=(1.0, 0.25)),
                  tone(262, 0.18, decay=14, harmonics=(1.0, 0.25)))),
    # The turn closes: two notes down.
    ("phase/end", "phase.wav", 0.72,
     lambda: join(tone(392, 0.10, decay=18), tone(262, 0.22, decay=12))),
    # Attack and defence position: same card flip, opposite little gestures.
    ("switch_attack", "flip.wav", 1.20,
     lambda: join(tone(523, 0.07, decay=22), tone(659, 0.13, decay=18))),
    ("switch_defense", "flip.wav", 0.80,
     lambda: join(tone(523, 0.07, decay=22), tone(392, 0.15, decay=16))),
)

# What the credits of the source pack say about the files we take.
CC0_SOURCES = {
    "attack.wav": '"Draw sword#1.wav" by fielastro, CC0 (freesound.org/people/fielastro/sounds/423935/)',
    "shuffle.wav": '"Riffle Card Shuffle" by Kodack, CC0 (freesound.org/people/Kodack/sounds/256508/)',
    "damage.wav": '"Nasty Knife Stab 2.wav" by Aris621, CC0 (freesound.org/people/Aris621/sounds/478145/)',
    "flip.wav": '"flipCard.wav" by Splashdust, CC0 (freesound.org/people/Splashdust/sounds/84322/)',
    "set.wav": '"Paper slide" by Kingofgamers_cz, CC0 (freesound.org/people/Kingofgamers_cz/sounds/352914/)',
    "phase.wav": '"Fast swipe.wav" by ParadoxTheSock, CC0 (freesound.org/people/ParadoxTheSock/sounds/412595/)',
}


def build_from_soundpack(soundpack: Path) -> dict[str, np.ndarray]:
    effects: dict[str, np.ndarray] = {}
    for name, source, trim in DIRECT:
        effects[name] = finish(load_mono(soundpack / source), trim)
    for name, source, factor, signature in DERIVED:
        swipe = change_speed(load_mono(soundpack / source), factor)
        # The signature starts under the tail of the recording rather than
        # after it, so the cue stays one short sound instead of two.
        marker = signature()
        overlap = min(len(swipe) // 3, len(swipe))
        body = mix(swipe, join(silence((len(swipe) - overlap) / SAMPLE_RATE), 0.7 * marker))
        effects[name] = finish(body, 0.7)
    return effects


# ------------------------------------------------------------- the script ---

def referenced_effects() -> set[str]:
    """Every effect name the client asks ``play_duel_sound_effect`` for."""
    pattern = re.compile(r'play_duel_sound_effect\(\s*"([^"]+)"')
    names: set[str] = set()
    for path in SOURCE_DIR.rglob("*.py"):
        names.update(pattern.findall(path.read_text(encoding="utf-8")))
    return names


def effect_file(name: str) -> Path | None:
    for extension in (".flac", ".wav", ".ogg", ".opus"):
        candidate = DUEL_SOUNDS / f"{name}{extension}"
        if candidate.exists():
            return candidate
    return None


def missing_effects() -> list[str]:
    return sorted(name for name in referenced_effects() if effect_file(name) is None)


def write_effect(name: str, signal: np.ndarray) -> Path:
    path = DUEL_SOUNDS / f"{name}.flac"
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), signal.astype(np.float32), SAMPLE_RATE, format="FLAC", subtype="PCM_16")
    return path


def write_attribution(built_from_pack: bool) -> Path:
    lines = [
        "# Duel sound effects",
        "",
        "Rebuild with `python scripts/build_sound_effects.py --soundpack <path>`.",
        "",
        "## Synthesised for this project",
        "",
        "Generated by `scripts/build_sound_effects.py`. No third party material,",
        "no conditions attached.",
        "",
    ]
    lines += [f"- `{name}.flac`" for name in sorted(synthesised())]
    if built_from_pack:
        lines += [
            "",
            "## Derived from CC0 recordings",
            "",
            "Taken from the Lahrenheit EDOPro soundpack",
            "(https://github.com/Lahrenheit/EDOPRO-Soundpack), which credits each",
            "one to a CC0 original. CC0 waives copyright, so these may be copied",
            "and altered freely; the credit below is courtesy, not obligation.",
            "",
        ]
        for name, source, _trim in DIRECT:
            lines.append(f"- `{name}.flac` <- {CC0_SOURCES[source]}")
        for name, source, factor, _signature in DERIVED:
            lines.append(
                f"- `{name}.flac` <- {CC0_SOURCES[source]}, playback speed "
                f"x{factor:g}, with a pitched signature generated here"
            )
        lines += [
            "",
            "## Deliberately not used",
            "",
            "The Timtam Yu-Gi-Oh MUD soundpack",
            "(https://github.com/Timtam/yugioh-soundpack) matches these effect",
            "names almost exactly, but its README says the effects were taken from",
            "the Yu-Gi-Oh games and anime and forbids their use in unrelated",
            "projects. Nothing here comes from it.",
            "",
            "The soundpack above also ships `activate.wav`, `destroyed.wav` and",
            "`specialsummon.wav`, credited only as \"YGOPro Percy sound effects\"",
            "with no licence. Those are not used either.",
        ]
    path = DUEL_SOUNDS / "ATTRIBUTION.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--soundpack", type=Path,
                        help="clone of https://github.com/Lahrenheit/EDOPRO-Soundpack")
    parser.add_argument("--check", action="store_true",
                        help="report effects the client asks for but cannot play")
    args = parser.parse_args()

    if args.check:
        missing = missing_effects()
        if missing:
            print("Missing sound effects:")
            for name in missing:
                print(f"  {name}")
            return 1
        print(f"All {len(referenced_effects())} referenced sound effects are present.")
        return 0

    # Everything goes through the same finishing pass, wherever it came from:
    # trimmed, tapered and levelled to match the rest of the set.
    effects = {name: finish(signal) for name, signal in synthesised().items()}
    if args.soundpack:
        soundpack = args.soundpack.expanduser().resolve()
        if not soundpack.is_dir():
            print(f"ERROR: soundpack not found: {soundpack}", file=sys.stderr)
            return 1
        effects.update(build_from_soundpack(soundpack))
    else:
        print("No --soundpack given; building only the synthesised effects.")

    for name in sorted(effects):
        path = write_effect(name, effects[name])
        print(f"wrote {path.relative_to(ROOT)} ({len(effects[name]) / SAMPLE_RATE:.2f}s)")

    print(f"wrote {write_attribution(bool(args.soundpack)).relative_to(ROOT)}")

    missing = missing_effects()
    if missing:
        print(f"\nStill missing: {', '.join(missing)}")
        return 1
    print(f"\nAll {len(referenced_effects())} referenced sound effects are present.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
