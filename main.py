import sys
import os
import logging
import traceback

if sys.platform == "win32" and os.getenv("HIDE_CONSOLE", "true").lower() == "true":
    try:
        import ctypes
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd != 0:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
    except Exception:
        pass

from core.guard import acquire, release, signal_restore_existing_instance, start_restore_listener

if not acquire():
    # If the client is already running and the user launches it again, activate the existing window
    # instead of displaying a confusing duplicate-instance dialog.
    signal_restore_existing_instance()
    sys.exit(0)

from config import config
from utils.log import setup_logger, configure_crash_hook, add_recent_event

setup_logger(config.LOG_FILE, debug_mode=config.DEBUG_MODE)
configure_crash_hook(config.CRASH_LOG_FILE, config.CURRENT_VERSION)

logger = logging.getLogger("Main")
add_recent_event("Application entry point reached")

def ensure_local_auth_server():
    """Ensure local authentication server is running in background if URL is localhost."""
    if "127.0.0.1" in config.AUTH_SERVER_URL or "localhost" in config.AUTH_SERVER_URL:
        import requests
        try:
            r = requests.get(f"{config.AUTH_SERVER_URL.rstrip('/')}/api/ping", timeout=1)
            if r.status_code == 200:
                return
        except Exception:
            pass
        import subprocess
        from pathlib import Path
        server_script = Path(__file__).parent / "server" / "app.py"
        if server_script.exists():
            try:
                creationflags = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW
                subprocess.Popen(
                    [sys.executable, str(server_script)],
                    cwd=str(Path(__file__).parent),
                    creationflags=creationflags
                )
                logger.info("Local background authentication server spawned.")
            except Exception as e:
                logger.warning(f"Could not auto-start local server: {e}")

ensure_local_auth_server()

from core.boot import BootSequence
import core.safe as safe_mode

seq = BootSequence(config.CURRENT_VERSION)

seq.begin("Configuration")
try:
    config.validate()
    seq.ok(f"Version {config.CURRENT_VERSION} | Debug: {config.DEBUG_MODE}")
except ValueError as e:
    seq.warn(str(e))
except Exception as e:
    seq.fail("Configuration load failed", e)

seq.begin("Storage")
try:
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    test_path = config.LOG_DIR / ".init_test"
    test_path.write_text("ok")
    test_path.unlink()
    seq.ok(f"Log directory: {config.LOG_DIR}")
except Exception as e:
    seq.fail("Log directory not writable", e)

seq.begin("Security")
try:
    from network.security import SecurityManager
    security = SecurityManager(config.LOG_DIR)
    if security.check_clock_rollback():
        seq.fail("Clock rollback detected — possible tampering attempt")
    elif not security.verify_config_integrity():
        seq.fail("Configuration file integrity check failed — file may be corrupted")
    else:
        security.save_security_metadata(int(__import__("time").time()))
        seq.ok("Clock and config integrity verified")
except Exception as e:
    seq.fail("Security check error", e)

seq.begin("Process Stealth")
try:
    from engine.hider import ProcessHider
    if config.HIDE_CONSOLE:
        ProcessHider.hide_console()
    seq.ok("Console hidden" if config.HIDE_CONSOLE else "Console visible (HIDE_CONSOLE=false)")
except Exception as e:
    seq.warn(f"Stealth config skipped: {e}")

seq.begin("Authentication Handler")
try:
    from network.auth_client import KeyAuthHandler
    handler = KeyAuthHandler(
        name="PortalCore",
        owner_id="portal",
        version=config.CURRENT_VERSION,
        data_dir=config.LOG_DIR
    )
    seq.ok("Auth handler initialized")
except Exception as e:
    seq.fail("Auth handler initialization failed", e)
    handler = None

seq.summary()
add_recent_event("Startup sequence complete")

if not seq.is_healthy():
    failed_phases = seq.get_failed_phases()
    reasons = [f"{p['phase']}: {p.get('message', p.get('error', 'Unknown'))}" for p in failed_phases]
    logger.warning(f"Startup failures detected. Launching in Safe Mode. Reasons: {reasons}")
    safe_mode.enable(reasons)

from ui.window import ActivationWindow
from ui.tray import StealthTray

_engine_instance = None
_tray_icon = None
_hotkey_manager = None

def on_authorized():
    logger.info("Authorization callback: session established.")
    add_recent_event("User authorized")
    _start_hotkey()
    _start_tray()
    app_window.after(5000, verify_hotkey_alive)

def on_logout():
    logger.info("Logout callback: returning to authentication view.")
    on_stop_engine()

def _restore_and_focus_window(tab: Optional[str] = None) -> None:
    def _do():
        try:
            app_window.deiconify()
            app_window.state("normal")
            app_window.lift()
            if sys.platform == "win32":
                import ctypes
                hwnd = app_window.winfo_id()
                root_hwnd = ctypes.windll.user32.GetAncestor(hwnd, 2)  # GA_ROOT = 2
                target = root_hwnd if root_hwnd else hwnd
                ctypes.windll.user32.ShowWindow(target, 9)  # SW_RESTORE
                ctypes.windll.user32.SetForegroundWindow(target)
            app_window.focus_force()
            if tab and hasattr(app_window, "_navigate_to"):
                app_window._navigate_to(tab)
        except Exception as e:
            logger.error(f"Error restoring window: {e}")
    app_window.after(0, _do)

def toggle_dashboard():
    def _toggle():
        try:
            is_visible_and_active = False
            if app_window.state() == "normal" and app_window.winfo_viewable():
                if sys.platform == "win32":
                    import ctypes
                    hwnd = app_window.winfo_id()
                    fg_hwnd = ctypes.windll.user32.GetForegroundWindow()
                    if fg_hwnd == hwnd:
                        is_visible_and_active = True
                    else:
                        curr = fg_hwnd
                        while curr:
                            if curr == hwnd:
                                is_visible_and_active = True
                                break
                            curr = ctypes.windll.user32.GetParent(curr)
                else:
                    is_visible_and_active = True
            if is_visible_and_active:
                app_window.withdraw()
                logger.info("Dashboard hidden via global shortcut.")
            else:
                _restore_and_focus_window()
                logger.info("Dashboard restored and focused via global shortcut.")
        except Exception as e:
            logger.error(f"Error toggling dashboard visibility: {e}")
    app_window.after(0, _toggle)

def verify_hotkey_alive():
    global _hotkey_manager
    if config.GLOBAL_SHORTCUT and not safe_mode.is_active():
        if _hotkey_manager is None or not _hotkey_manager.is_alive():
            logger.warning("Global hotkey listener was found dead or uninitialized. Restarting...")
            _start_hotkey()
    try:
        if app_window.winfo_exists():
            app_window.after(5000, verify_hotkey_alive)
    except Exception:
        pass

def on_start_engine():
    global _engine_instance
    if safe_mode.is_active():
        logger.warning("Engine start blocked — Safe Mode is active.")
        return
    try:
        from engine.processor import StealthSystem
        _engine_instance = StealthSystem(config, parent=app_window)
        _engine_instance.start()
        logger.info("Scanning engine started.")
        add_recent_event("Scanning engine started")
        app_window.after(150, lambda: app_window.withdraw())
        if _tray_icon:
            _tray_icon.update_status("Active")
    except Exception as e:
        logger.error(f"Engine start failed: {e}", exc_info=True)
        add_recent_event(f"Engine start FAILED: {e}")

def on_stop_engine():
    global _engine_instance
    if _engine_instance:
        try:
            _engine_instance.shutdown()
        except Exception as e:
            logger.warning(f"Engine shutdown error: {e}")
        _engine_instance = None
    try:
        app_window.after(0, lambda: app_window.deiconify())
    except Exception:
        pass
    if _tray_icon:
        _tray_icon.update_status("Standby")
    logger.info("Scanning engine stopped.")
    add_recent_event("Scanning engine stopped")

def _start_hotkey():
    global _hotkey_manager
    _stop_hotkey()
    if not config.GLOBAL_SHORTCUT:
        return
    try:
        from utils.keys import GlobalHotkeyManager
        _hotkey_manager = GlobalHotkeyManager(
            config.GLOBAL_SHORTCUT,
            toggle_dashboard
        )
        _hotkey_manager.start()
    except Exception as e:
        logger.warning(f"Hotkey registration failed for shortcut '{config.GLOBAL_SHORTCUT}': {e}")

def _stop_hotkey():
    global _hotkey_manager
    if _hotkey_manager:
        try:
            _hotkey_manager.stop()
        except Exception:
            pass
        _hotkey_manager = None

def on_shortcut_changed(new_shortcut: str):
    config.GLOBAL_SHORTCUT = new_shortcut
    config.save_to_disk()
    _start_hotkey()

def exit_application():
    logger.info("Shutting down application cleanly...")
    on_stop_engine()
    _stop_hotkey()
    _stop_tray()
    try:
        app_window.exit_application()
    except Exception:
        try:
            app_window.destroy()
        except Exception:
            pass

def _start_tray():
    global _tray_icon
    if _tray_icon is not None:
        return
    try:
        _tray_icon = StealthTray(
            on_open_client=lambda: _restore_and_focus_window(),
            on_hide_to_tray=lambda: app_window.after(0, app_window.withdraw),
            on_exit_app=lambda: app_window.after(0, exit_application),
        )
        _tray_icon.start()
        logger.info("System tray icon daemon started.")
    except Exception as e:
        logger.error(f"Failed to start system tray icon: {e}")

def _stop_tray():
    global _tray_icon
    if _tray_icon:
        try:
            _tray_icon.stop()
        except Exception as e:
            logger.warning(f"Error stopping tray icon: {e}")
        _tray_icon = None

if handler is None and not safe_mode.is_active():
    logger.critical("Auth handler unavailable and Safe Mode not triggered. Cannot launch.")
    sys.exit(1)

try:
    app_window = ActivationWindow(
        handler=handler,
        on_authorized=on_authorized,
        on_start_engine=on_start_engine,
        on_stop_engine=on_stop_engine,
        on_shortcut_changed=on_shortcut_changed,
        on_logout=on_logout,
    )
    # Start persistent system tray icon on launch
    _start_tray()
    # Listen for restore events from subsequent client launch attempts
    start_restore_listener(lambda: _restore_and_focus_window())
    add_recent_event("UI window created")
    logger.info("UI launched. Entering main loop.")
    app_window.mainloop()
except Exception as e:
    logger.critical(f"Fatal UI error: {e}", exc_info=True)
    from utils.log import write_crash_report
    write_crash_report(
        crash_log_file=config.CRASH_LOG_FILE,
        version=config.CURRENT_VERSION,
        module="Main",
        function="mainloop",
        error=e,
    )
finally:
    release()
    on_stop_engine()
    _stop_hotkey()
    _stop_tray()
    logger.info("Application exited cleanly.")