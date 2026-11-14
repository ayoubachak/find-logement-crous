"""Persistent ring buffer for the activity log: survives closing the tab and restarting the app."""
import os
import threading
import time
from collections import deque


class LogStore:
    def __init__(self, path, keep=500):
        self.path = path
        self.keep = keep
        self._lock = threading.Lock()
        self._items = deque(maxlen=keep)  # (seq, text)
        self._last_seq = 0
        self._since_trim = 0
        self._load()

    def _next_seq(self):
        # Strictly increasing and still increasing after an app restart (microseconds since epoch)
        self._last_seq = max(self._last_seq + 1, time.time_ns() // 1000)
        return self._last_seq

    def _load(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                lines = [line.rstrip("\n") for line in f if line.strip()]
        except OSError:
            return
        for line in lines[-self.keep:]:
            self._items.append((self._next_seq(), line))

    def _rewrite(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("".join(text + "\n" for _, text in self._items))
        os.replace(tmp, self.path)

    def add(self, text):
        """Store one line and return its sequence number."""
        text = " ".join(str(text).splitlines())
        with self._lock:
            seq = self._next_seq()
            self._items.append((seq, text))
            try:
                with open(self.path, "a", encoding="utf-8") as f:
                    f.write(text + "\n")
                self._since_trim += 1
                if self._since_trim >= self.keep:  # keep the file from growing forever
                    self._since_trim = 0
                    self._rewrite()
            except OSError:
                pass
        return seq

    def history(self):
        with self._lock:
            return [{"seq": seq, "message": text} for seq, text in self._items]
