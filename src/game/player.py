import logging
import threading
import time
import random
from pathlib import Path

from core import utils
from core import variables

from game.edo import default_values

logger = logging.getLogger(__name__)

class CountdownTimer:
    def __init__(self, seconds):
        self.initial_seconds = seconds
        self.seconds = seconds
        self.lock = threading.Lock()
        self.running = False
        # A daemon thread: a duel clock has nothing to finish. As a normal
        # thread it kept the whole process alive for the rest of the turn
        # after the window had closed, so quitting mid duel appeared to hang.
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        self.running = True
        while self.running:
            time.sleep(1)
            with self.lock:
                if self.seconds > 0:
                    self.seconds -= 1
                self.handle_potential_sfx()
                if self.seconds == 0:
                    self.running = False

    def update(self, seconds):
        with self.lock:
            self.seconds = seconds
            if not self.running:
                self.running = True
                self.thread = threading.Thread(target=self._run, daemon=True)
                self.thread.start()

    def get_remaining_time(self):
        with self.lock:
            return self.seconds

    def stop(self):
        # The join has to happen outside the lock: the counting thread takes
        # the same lock on every tick, so waiting for it while holding the
        # lock is a deadlock, and stop() never returned.
        with self.lock:
            self.running = False
        self.thread.join()

    def handle_potential_sfx(self):
        # Runs on the clock thread, where there may no longer be a window to
        # play a sound through: the duel can end, or the application close,
        # between two ticks. Letting that escape killed the thread, and with
        # it the countdown the player is relying on.
        try:
            if self.seconds == 0:
                utils.get_ui_stack().play_duel_sound_effect("timer/zero")
            if self.seconds == 30:
                utils.get_ui_stack().play_duel_sound_effect("timer/30")
            if self.seconds <= 10:
                # check if it's even or odd
                if self.seconds % 2 == 0:
                    utils.get_ui_stack().play_duel_sound_effect("timer/even", x=-6.0)
                else:
                    utils.get_ui_stack().play_duel_sound_effect("timer/odd", x=-6.0)
        except Exception:
            logger.debug("No window to play the turn timer through", exc_info=True)

# this class is just to hold different attributes for the player during a duel
class Player:
    def __init__(self, your_starting_lifepoints, opponent_starting_lifepoints):
        self.lifepoints = your_starting_lifepoints
        self.opponent_lifepoints = opponent_starting_lifepoints
        # Bumped every time the duel replaces what the player may do. A menu
        # built from one generation must not act during the next: the lists it
        # indexed into have been thrown away and rebuilt.
        self.state_generation = 0
        self.handle_potential_music_change(initial=True)
        self._chaining_cards = []
        # The chain that is actually building, link by link; distinct from
        # chaining_cards, which holds the options the player may chain with.
        self.chain_stack = []
        self._summonable = []
        self._special_summonable = []
        self._repositionable = []
        self._monster_settable = []
        self._spell_settable = []
        self._activatable = []
        # Set here as well as in clear_all: the field can be walked between the
        # duel starting and the first prompt arriving, and reading a zone asks
        # every one of these lists whether the card is in it.
        self._attackable = []
        self._can_go_to_battle_phase = 0
        self._can_go_to_main_phase2 = 0
        self._can_go_to_end_phase = 0
        self._can_shuffle = 0
        self._turn_timer = None
        self.turn_timer = default_values.HOST_INFO.time_limit_in_seconds

    def update_lifepoints(self, new_lifepoints, opponent=False):
        lpsource = None
        if opponent:
            difference = abs(new_lifepoints- self.opponent_lifepoints)
            if new_lifepoints > self.opponent_lifepoints:
                utils.get_ui_stack().play_duel_sound_effect("lpearn")
        else:
            difference = abs(new_lifepoints- self.lifepoints)
            if new_lifepoints > self.lifepoints:
                utils.get_ui_stack().play_duel_sound_effect("lpearn")
        divident = 1500
        logger.debug(f"Life points updated, new life points: {new_lifepoints}, difference: {difference}")
        if opponent:
            lpsource = utils.get_ui_stack().sound_effects_audio_manager.play_audio_for_specified_duration("duel/lp.flac", difference/divident)
            self.opponent_lifepoints = new_lifepoints
        else:
            lpsource = utils.get_ui_stack().sound_effects_audio_manager.play_audio_for_specified_duration("duel/lp.flac", difference/divident)
            self.lifepoints = new_lifepoints
        self.handle_potential_music_change()
        return lpsource
    
    def handle_potential_music_change(self, initial=False):
        if initial:
            logger.debug("Handling potential music change on initial player creation")
            music_files = list(Path(variables.LOCAL_DATA_DIR / "sounds" / "music" / "duel_standard").iterdir())
            random_music_file = random.choice(music_files)
            self.duel_music =utils.get_ui_stack().music_audio_manager.play_audio(f"music/duel_standard/{random_music_file.name}", looping=True)
            self.duel_music_filepath = Path(random_music_file)
            return
        # if player lp is less than half of opponent lp, and we aren't already playing the low lp music, play it
        if self.lifepoints < self.opponent_lifepoints / 2 and self.duel_music_filepath.parent.name != "duel_losing":
            logger.debug("Handling potential music change, playing losing music")
            music_files = list(Path(variables.LOCAL_DATA_DIR / "sounds" / "music" / "duel_losing").iterdir())
            random_music_file = random.choice(music_files)
            self.duel_music.stop()
            self.duel_music =utils.get_ui_stack().music_audio_manager.play_audio(f"music/duel_losing/{random_music_file.name}", looping=True)
            self.duel_music_filepath = Path(random_music_file)
            return
        # if player lp is more than double opponent lp, and we aren't already playing the winning music, play it
        if self.lifepoints > self.opponent_lifepoints * 2 and self.duel_music_filepath.parent.name != "duel_winning":
            logger.debug("Handling potential music change, playing winning music")
            music_files = list(Path(variables.LOCAL_DATA_DIR / "sounds" / "music" / "duel_winning").iterdir())
            random_music_file = random.choice(music_files)
            self.duel_music.stop()
            self.duel_music =utils.get_ui_stack().music_audio_manager.play_audio(f"music/duel_winning/{random_music_file.name}", looping=True)
            self.duel_music_filepath = Path(random_music_file)
            return
        # if we are not playing a standard music play it, and player lp is not less than half of opponent lp or more than double opponent lp
        if self.duel_music_filepath.parent.name != "duel_standard" and self.lifepoints >= self.opponent_lifepoints / 2 and self.lifepoints <= self.opponent_lifepoints * 2:
            logger.debug("Handling potential music change, playing standard music")
            music_files = list(Path(variables.LOCAL_DATA_DIR / "sounds" / "music" / "duel_standard").iterdir())
            random_music_file = random.choice(music_files)
            self.duel_music.stop()
            self.duel_music =utils.get_ui_stack().music_audio_manager.play_audio(f"music/duel_standard/{random_music_file.name}", looping=True)
            self.duel_music_filepath = Path(random_music_file)
            return
        

    def clear_all(self):
        self.state_generation = getattr(self, "state_generation", 0) + 1
        self.chaining_cards = []
        self.chain_stack = []
        self.summonable = []
        self.special_summonable = []
        self.repositionable = []
        self.monster_settable = []
        self.spell_settable = []
        self.activatable = []
        self.attackable = []
        self.can_go_to_battle_phase = 0
        self.can_go_to_main_phase2 = 0
        self.can_go_to_end_phase = 0
        self.can_shuffle = 0

    @property
    def turn_timer(self):
        return self._turn_timer
    
    @turn_timer.setter
    def turn_timer(self, value):
        # if the old value is a turn timer, update it
        # if it's none, instantiate a new one
        if self._turn_timer:
            self._turn_timer.update(value)
        else:
            self._turn_timer = CountdownTimer(value)

    # make getters and setters for all these attributes
    @property
    def chaining_cards(self):
        return self._chaining_cards
    
    @chaining_cards.setter
    def chaining_cards(self, value):
        if not isinstance(value, list):
            raise ValueError("chaining cards must be a list")
        self._chaining_cards = value
        
    @property
    def summonable(self):
        return self._summonable

    @summonable.setter
    def summonable(self, value):
        if not isinstance(value, list):
            raise ValueError("summonable must be a list")
        self._summonable = value

    @property
    def special_summonable(self):
        return self._special_summonable
    
    @special_summonable.setter
    def special_summonable(self, value):
        if not isinstance(value, list):
            raise ValueError("special summonable must be a list")
        self._special_summonable = value

    @property
    def repositionable(self):
        return self._repositionable
    
    @repositionable.setter
    def repositionable(self, value):
        if not isinstance(value, list):
            raise ValueError("repositionable must be a list")
        self._repositionable = value

    @property
    def monster_settable(self):
        return self._monster_settable
    
    @monster_settable.setter
    def monster_settable(self, value):
        if not isinstance(value, list):
            raise ValueError("monster settable must be a list")
        self._monster_settable = value

    @property
    def spell_settable(self):
        return self._spell_settable
    
    @spell_settable.setter
    def spell_settable(self, value):
        if not isinstance(value, list):
            raise ValueError("spell settable must be a list")
        self._spell_settable = value

    @property
    def activatable(self):
        return self._activatable
    
    @activatable.setter
    def activatable(self, value):
        if not isinstance(value, list):
            raise ValueError("activatable must be a list")
        self._activatable = value

    @property
    def attackable(self):
        return self._attackable
    
    @attackable.setter
    def attackable(self, value):
        if not isinstance(value, list):
            raise ValueError("attackable must be a list")
        self._attackable = value

    @property
    def can_go_to_battle_phase(self):
        return self._can_go_to_battle_phase
    
    @can_go_to_battle_phase.setter
    def can_go_to_battle_phase(self, value):
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError("can go to battle phase must be an int or bool")
        self._can_go_to_battle_phase = bool(value)

    @property
    def can_go_to_main_phase2(self):
        return self._can_go_to_main_phase2
    
    @can_go_to_main_phase2.setter
    def can_go_to_main_phase2(self, value):
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError("can go to main phase 2 must be an int or bool")
        self._can_go_to_main_phase2 = bool(value)

    @property
    def can_go_to_end_phase(self):
        return self._can_go_to_end_phase
    
    @can_go_to_end_phase.setter
    def can_go_to_end_phase(self, value):
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError("can go to end phase must be an int or bool")
        self._can_go_to_end_phase = bool(value)

    @property
    def can_shuffle(self):
        return self._can_shuffle
    
    @can_shuffle.setter
    def can_shuffle(self, value):
        self._can_shuffle = value