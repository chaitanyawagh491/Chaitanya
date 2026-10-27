import logging
from pynput import keyboard

logger = logging.getLogger("HotkeyManager")

class GlobalHotkeyManager:
    def __init__(self, shortcut: str, callback: callable):
        self.shortcut = shortcut
        self.callback = callback
        self.hotkey_listener = None

    def is_alive(self) -> bool:
        return self.hotkey_listener is not None and self.hotkey_listener.is_alive()

    def start(self):
        self.stop()
        pynput_shortcut = self._to_pynput(self.shortcut)
        hotkey_dict = {}
        hotkey_dict[pynput_shortcut] = self.callback
        if "<shift>" in pynput_shortcut:
            parts = pynput_shortcut.split('+')
            alt_parts = []
            for part in parts:
                if len(part) == 1 and part.isalpha():
                    alt_parts.append(part.upper())
                else:
                    alt_parts.append(part)
            alt_shortcut = '+'.join(alt_parts)
            if alt_shortcut != pynput_shortcut:
                hotkey_dict[alt_shortcut] = self.callback
        else:
            parts = pynput_shortcut.split('+')
            alt_parts = []
            for part in parts:
                if len(part) == 1 and part.isalpha():
                    alt_parts.append(part.lower())
                else:
                    alt_parts.append(part)
            alt_shortcut = '+'.join(alt_parts)
            if alt_shortcut != pynput_shortcut:
                hotkey_dict[alt_shortcut] = self.callback
        try:
            self.hotkey_listener = keyboard.GlobalHotKeys(hotkey_dict)
            self.hotkey_listener.start()
            logger.info(f"Global hotkey listener started for shortcut: {self.shortcut}")
        except Exception as e:
            logger.error(f"Failed to start global hotkey listener for shortcut '{self.shortcut}': {e}")

    def stop(self):
        if self.hotkey_listener:
            try:
                self.hotkey_listener.stop()
            except Exception as e:
                logger.error(f"Error while stopping global hotkey listener: {e}")
            self.hotkey_listener = None
            logger.info("Global hotkey listener stopped.")

    def update_shortcut(self, new_shortcut: str):
        self.shortcut = new_shortcut
        self.start()

    def _to_pynput(self, shortcut_str: str) -> str:
        parts = shortcut_str.lower().split('+')
        pynput_parts = []
        for part in parts:
            part = part.strip()
            if part == 'ctrl':
                pynput_parts.append('<ctrl>')
            elif part == 'shift':
                pynput_parts.append('<shift>')
            elif part == 'alt':
                pynput_parts.append('<alt>')
            else:
                pynput_parts.append(part)
        return '+'.join(pynput_parts)
