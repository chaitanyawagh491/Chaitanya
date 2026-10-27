import time
import logging
from typing import Callable, Optional
from pynput.mouse import Listener

logger = logging.getLogger(__name__)

class InputDetector:
    def __init__(self, tap_window: float = 0.5, detection_radius: int = 50):
        self.tap_window = tap_window
        self.detection_radius = detection_radius
        self.tap_history = []
        self.last_tap_pos = None
        self.gesture_callback: Optional[Callable] = None
        self.listener = None
        self.running = False

    def set_callback(self, callback: Callable):
        self.gesture_callback = callback

    def _on_click(self, x, y, button, pressed):
        if not pressed:
            return
        current_time = time.time()
        if self.last_tap_pos:
            dx = x - self.last_tap_pos[0]
            dy = y - self.last_tap_pos[1]
            distance = (dx**2 + dy**2) ** 0.5
            if distance > self.detection_radius:
                self.tap_history.clear()
        self.tap_history.append((current_time, x, y))
        self.last_tap_pos = (x, y)
        self.tap_history = [
            tap for tap in self.tap_history
            if current_time - tap[0] < self.tap_window
        ]
        if len(self.tap_history) >= 3:
            if self.gesture_callback:
                self.gesture_callback()
            self.tap_history.clear()

    def start(self):
        self.running = True
        self.listener = Listener(on_click=self._on_click)
        self.listener.start()

    def stop(self):
        self.running = False
        if self.listener:
            self.listener.stop()
            self.listener = None
