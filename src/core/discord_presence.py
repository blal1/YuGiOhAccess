import threading
import queue
import time
import logging
from pypresence import Presence
import pypresence

from core.i18n import _

logger = logging.getLogger(__name__)

class DiscordPresenceManager(threading.Thread):
    """
    Runs a separate thread for handling Discord Rich Presence updates.
    You can post update requests to the `update_queue` from anywhere
    in your game without blocking the main thread.
    """

    def __init__(self, client_id: str):
        logger.info("Initializing Discord Presence Manager")
        super().__init__()
        self.client_id = client_id
        self.update_queue: queue.Queue = queue.Queue()   # Thread-safe queue
        self.running = True
        self.rpc = None
        self.is_connected = False
        self.default_buttons = [
            {"label": _("Website"), "url": "https://yugiohaccess.com"},
            {"label": _("Discord Server"), "url": "https://discord.gg/6YcSEbYCJT"},
        ]
        logger.info("Discord Presence Manager initialized")

    def run(self):
        """
        This method is called when you start() the thread.
        It sets up the Presence connection and processes updates
        from the queue.
        """
        self.rpc = Presence(self.client_id)
        self.reconnect()

        while self.running:
            try:
                # Wait briefly for a new update request
                presence_data = self.update_queue.get(timeout=0.1)
                if presence_data is None:
                    # None can act as a sentinel to shut down
                    break
                logger.debug("Updating presence: %s", presence_data)
                if not self.is_connected:
                    logger.warning("Discord not connected. Attempting to reconnect.")
                    self.reconnect()
                if self.is_connected:
                    self.rpc.update(**presence_data)
            except queue.Empty:
                # No updates this cycle
                pass
            except pypresence.exceptions.PipeClosed:
                self.is_connected = False
                self.reconnect()
            except pypresence.exceptions.DiscordNotFound:
                self.is_connected = False
                self.reconnect()
            
            # Sleep or do other checks here as needed
            time.sleep(0.5)

        # Clean up when stopping (only if `stop()` is called explicitly)
        try:
            if self.rpc is not None and self.is_connected:
                self.rpc.clear()
                self.rpc.close()
        except (AssertionError, pypresence.exceptions.PipeClosed):
            logger.warning("Discord connection already closed")

    def reconnect(self):
        try:
            self.rpc.connect()
            self.is_connected = True
            logger.debug("Connected to Discord")
        except pypresence.exceptions.DiscordNotFound:
            logger.warning("Discord not found. Is Discord running?")
            self.is_connected = False
        except pypresence.exceptions.PipeClosed:
            logger.warning("Discord connection closed. Attempting to reconnect.")
            self.is_connected = False

    def update_presence(self, **presence_data):
        """
        Call this to post an update to the queue from any part of your game.
        For example:
            manager.update_presence(
                details="Playing level 2",
                state="Boss Fight!",
                large_image="mygame_large",
            )
        """
        if "buttons" not in presence_data:
            presence_data["buttons"] = self.default_buttons
        self.update_queue.put(presence_data)

    def stop(self):
        """
        Gracefully stop the presence thread.
        """
        self.running = False
        self.update_queue.put(None)  # Sentinel to unblock queue get() call
