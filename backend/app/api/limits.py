"""A simple limit on how often one visitor can start a split. Each start reads a bill with
Gemini, so without a limit anyone who finds the public URL could use up the API quota."""

import threading
import time
from collections import deque


class RateLimit:
    """At most `limit` uses per `window_seconds` for each key (here, a visitor's IP address).

    Kept in memory: enough for the single server we run; it starts empty after a restart.
    """

    def __init__(self, limit: int, window_seconds: float):
        self.limit = limit
        self.window_seconds = window_seconds
        self.uses: dict[str, deque[float]] = {}
        self.lock = threading.Lock()  # endpoints run on several threads at once

    def allow(self, key: str, now: float | None = None) -> bool:
        """Record a use and return True, or return False if the key is already at its limit."""
        now = time.monotonic() if now is None else now
        with self.lock:
            uses = self.uses.setdefault(key, deque())
            while uses and uses[0] <= now - self.window_seconds:  # forget uses outside the window
                uses.popleft()
            if len(uses) >= self.limit:
                return False
            uses.append(now)
            return True
