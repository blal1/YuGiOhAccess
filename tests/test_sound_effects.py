"""Every sound the duel asks for has to exist, and has to be playable.

A missing effect does not crash anything: ``play_duel_sound_effect`` logs one
warning and returns, so the duel carries on in silence. That is exactly why it
needs a test. Twenty-two effects were missing this way, including every phase
change, and nothing ever failed to say so.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
SOURCE = ROOT / "src"
DUEL_SOUNDS = SOURCE / "data" / "sounds" / "duel"
PLAYABLE_SUFFIXES = (".flac", ".wav", ".ogg", ".opus")

SINGLE_EFFECT = re.compile(r'play_duel_sound_effect\(\s*"([^"]+)"')
DIRECTORY_EFFECT = re.compile(r'play_random_duel_sound_effect_in_directory\(\s*"([^"]+)"')


def _names(pattern):
    found = set()
    for path in SOURCE.rglob("*.py"):
        found.update(pattern.findall(path.read_text(encoding="utf-8")))
    return sorted(found)


def _resolve(effect):
    for suffix in PLAYABLE_SUFFIXES:
        candidate = DUEL_SOUNDS / f"{effect}{suffix}"
        if candidate.exists():
            return candidate
    return None


@pytest.mark.parametrize("effect", _names(SINGLE_EFFECT))
def test_every_referenced_effect_has_a_file(effect):
    assert _resolve(effect) is not None, (
        f"play_duel_sound_effect({effect!r}) has no file in {DUEL_SOUNDS}. "
        f"Run scripts/build_sound_effects.py, or stop asking for it."
    )


@pytest.mark.parametrize("directory", _names(DIRECTORY_EFFECT))
def test_every_referenced_effect_directory_has_something_to_play(directory):
    path = DUEL_SOUNDS / directory
    assert path.is_dir(), f"{path} does not exist"
    playable = [item for item in path.iterdir() if item.suffix in PLAYABLE_SUFFIXES]
    assert playable, f"{path} holds nothing the audio manager can play"


def test_the_client_looks_for_the_suffixes_we_ship():
    """The resolver and this test have to agree on what counts as playable."""
    frame_source = (SOURCE / "ui" / "frame.py").read_text(encoding="utf-8")
    for suffix in PLAYABLE_SUFFIXES:
        assert f'"{suffix}"' in frame_source


@pytest.mark.parametrize("effect", _names(SINGLE_EFFECT))
def test_every_effect_decodes_the_way_the_audio_manager_reads_it(effect):
    """AudioManager reads int16 frames and picks a mono or stereo buffer."""
    soundfile = pytest.importorskip("soundfile")

    path = _resolve(effect)
    assert path is not None
    data = soundfile.SoundFile(str(path), "r")
    try:
        assert data.channels in (1, 2)
        assert data.samplerate > 0
        frames = data.read(dtype="int16")
    finally:
        data.close()
    assert len(frames) > 0, f"{path.name} is empty"
