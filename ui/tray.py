import logging
import threading
from pathlib import Path
from typing import Callable, Optional
from PIL import Image, ImageDraw
import pystray

logger = logging.getLogger("TrayIcon")

class StealthTray:
    def __init__(
        self,
        on_open_client: Callable[[], None],
        on_hide_to_tray: Callable[[], None],
        on_exit_app: Callable[[], None],
    ):
        self.on_open_client = on_open_client
        self.on_hide_to_tray = on_hide_to_tray
        self.on_exit_app = on_exit_app
        self.icon: Optional[pystray.Icon] = None
        self.running: bool = False
        self.current_menu: Optional[pystray.Menu] = None
        self.tray_thread: Optional[threading.Thread] = None

    def create_dynamic_icon(self) -> Image.Image:
        icon_path = Path(__file__).parent / "icon.ico"
        if icon_path.exists():
            try:
                return Image.open(icon_path)
            except Exception:
                pass
        width = 64
        height = 64
        image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.ellipse([8, 8, 56, 56], fill=None, outline=(99, 102, 241, 120), width=4)
        draw.ellipse([16, 16, 48, 48], fill=(99, 102, 241, 255))
        draw.ellipse([24, 24, 40, 40], fill=(255, 255, 255, 255))
        return image

    def setup_tray(self) -> None:
        self.rebuild_menu()
        img = self.create_dynamic_icon()
        self.icon = pystray.Icon(
            "portal_client",
            icon=img,
            title="Visual Analyzer",
            menu=self.current_menu
        )
        logger.info("Starting system tray loop...")
        self.icon.run()

    def rebuild_menu(self) -> None:
        self.current_menu = pystray.Menu(
            pystray.MenuItem("Open Client", lambda: self._safe_call(self.on_open_client), default=True),
            pystray.MenuItem("Hide to Tray", lambda: self._safe_call(self.on_hide_to_tray)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", lambda: self.handle_exit()),
        )
        if self.icon:
            self.icon.menu = self.current_menu

    def _safe_call(self, func: Optional[Callable[[], None]]) -> None:
        if func:
            try:
                func()
            except Exception as e:
                logger.error(f"Error in tray menu action: {e}")

    def update_status(self, new_status: str) -> None:
        # Backward-compatible hook for engine status updates
        pass

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self.tray_thread = threading.Thread(target=self.setup_tray, daemon=True, name="TrayDaemon")
        self.tray_thread.start()

    def stop(self) -> None:
        self.running = False
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
            self.icon = None
            logger.info("System tray icon stopped.")

    def handle_exit(self) -> None:
        logger.info("System tray 'Exit' clicked. Initiating termination.")
        self.stop()
        if self.on_exit_app:
            self.on_exit_app()

