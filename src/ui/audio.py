import threading
import time
import logging
from pathlib import Path

import soundfile
import cyal

from core import variables

logger = logging.getLogger(__name__)

_CONTEXT = cyal.Context(cyal.Device(), make_current=True, hrtf_soft=0)

class AudioManager:
    def __init__(self, volume_config_key):
        self.volume_config_key = volume_config_key
        logger.info("Initializing audio manager")
        logger.debug("Initializing context")
        self.context = _CONTEXT
        logger.debug("Initializing listener")
        self.listener = self.context.listener
        self.listener.gain = 0.7
        self.listener.orientation = [0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
        self.listener.position = [0, 0, 0]
        self.source_volume = variables.config.get(self.volume_config_key)
        self.buffer_cache = {}
        self.sources = {}
        self.is_fading = False

    def __del__(self):
        logger.info("Cleaning up audio manager")
        try:
            variables.config.set(self.volume_config_key, round(self.source_volume, 4))
            self.stop_all_audio()
        except Exception:
            logger.exception("Failed to clean up audio manager")
        for attribute in ("buffer_cache", "sources", "listener", "context"):
            if hasattr(self, attribute):
                delattr(self, attribute)

    def decrease_volume(self, delta=0.05):
        self.source_volume -= delta
        if self.source_volume < 0.0:
            self.source_volume = 0.0
        self.update_all_sources_volume()

    def increase_volume(self, delta=0.05):
        self.source_volume += delta
        if self.source_volume > 1.0:
            self.source_volume = 1.0
        self.update_all_sources_volume()

    def set_volume(self, volume):
        self.source_volume = volume
        if self.source_volume < 0.0:
            self.source_volume = 0.0
        if self.source_volume > 1.0:
            self.source_volume = 1.0
        self.update_all_sources_volume()

    def get_volume(self):
        return self.source_volume

    def update_all_sources_volume(self):
        for source in self.sources.values():
            source.gain = self.source_volume

    def play_audio(self, filename, looping=False, x=0.0, y=0.0, z=0.0):
        file_path = Path(variables.LOCAL_DATA_DIR) / "sounds" / filename
        if file_path in self.sources.keys():
            source = self.sources[file_path]
        else:
            source=self.context.gen_source()
            if file_path not in self.buffer_cache:
                file_object=soundfile.SoundFile(file_path, 'r')
                format=cyal.BufferFormat.MONO16 if file_object.channels==1 else cyal.BufferFormat.STEREO16
                buffer = self.context.gen_buffer()
                data=file_object.read(dtype='int16').tobytes()
                file_object.close()
                buffer.set_data(data, sample_rate=file_object.samplerate, format=format)
                self.buffer_cache[file_path] = buffer
            source.buffer=self.buffer_cache[file_path]
        if x == 0.0 and y == 0.0 and z == 0.0:
            source.spatialize = False
        else:
            source.spatialize = True
        source.position=[x, y, z]
        source.looping=looping
        source.gain = self.source_volume
        self.sources[file_path] = source
        source.play()
        return source

    def play_audio_for_specified_duration(self, filename, duration, **kwargs):
        source = self.play_audio(filename, looping=True, **kwargs)
        threading.Thread(target=self._stop_audio_after_duration, args=(source, duration), daemon=True).start()
        return source
    
    def _stop_audio_after_duration(self, source, duration):
        logger.debug(f"Stopping audio after {duration}s")
        time.sleep(duration)
        logger.debug("Stopping audio")
        source.stop()
        filepath = None
        for file_path, s in self.sources.items():
            if s == source:
                filepath = file_path
                break
        if filepath:
            del self.sources[filepath]

    def stop_all_audio(self):
        for source in self.sources.values():
            source.stop()
        self.sources = {}

    def fade_out_all_audio(self):
        self.is_fading = True
        threading.Thread(target=self._fade_out_all_audio, args=(self.sources.keys(),), daemon=True).start()

    def _fade_out_all_audio(self, filepaths):
        # make a copy of the list to avoid modifying the original list
        filepaths = list(filepaths)
        for file_path in filepaths:
            source = self.sources[file_path]
            source.gain = max(0.0, source.gain - 0.01)
        time.sleep(0.2)
        # check if all sources are silent
        subset_of_sources = [self.sources[source] for source in filepaths]
        if all(source.gain <= 0.01 for source in subset_of_sources):
            for filepath in filepaths:
                self.sources[filepath].stop()
                del self.sources[filepath]
            self.is_fading = False
        else:
            self._fade_out_all_audio(filepaths)

    def is_playing(self, source):
        return source.state == cyal.SourceState.PLAYING
