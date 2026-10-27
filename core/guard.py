import sys
import logging
import threading

logger = logging.getLogger(__name__)
_MUTEX_NAME = "Global\\VisualAnalyzerSystem_SingleInstanceMutex"
_RESTORE_EVENT_NAME = "Global\\VisualAnalyzerSystem_RestoreEvent"
_mutex_handle = None
_restore_event_handle = None
_stop_listener = threading.Event()
_listener_thread = None

def acquire() -> bool:
    global _mutex_handle, _restore_event_handle
    if sys.platform != "win32":
        return True
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        _mutex_handle = kernel32.CreateMutexW(None, False, _MUTEX_NAME)
        if _mutex_handle == 0:
            return True
        last_error = kernel32.GetLastError()
        ERROR_ALREADY_EXISTS = 183
        if last_error == ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(_mutex_handle)
            _mutex_handle = None
            return False
        # Successfully acquired primary lock — create restore notification event
        _restore_event_handle = kernel32.CreateEventW(None, False, False, _RESTORE_EVENT_NAME)
        return True
    except Exception as e:
        logger.error(f"Guard error: {e}")
        return True

def start_restore_listener(callback) -> None:
    global _listener_thread, _stop_listener
    if sys.platform != "win32" or _restore_event_handle is None:
        return
    _stop_listener.clear()

    def _loop():
        import ctypes
        kernel32 = ctypes.windll.kernel32
        while not _stop_listener.is_set():
            # Wait up to 1000ms so thread can check _stop_listener and terminate cleanly
            res = kernel32.WaitForSingleObject(_restore_event_handle, 1000)
            if res == 0:  # WAIT_OBJECT_0
                logger.info("Restore signal received from another instance.")
                try:
                    callback()
                except Exception as e:
                    logger.error(f"Error executing restore callback: {e}")

    _listener_thread = threading.Thread(target=_loop, daemon=True, name="SingleInstanceRestoreListener")
    _listener_thread.start()
    return _listener_thread


def signal_restore_existing_instance() -> bool:
    if sys.platform != "win32":
        return False
    signaled = False
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32
        try:
            # Grant permission for the target process to take the foreground
            user32.AllowSetForegroundWindow(0xFFFFFFFF)  # ASFW_ANY
        except Exception:
            pass
        EVENT_MODIFY_STATE = 0x0002
        h_event = kernel32.OpenEventW(EVENT_MODIFY_STATE, False, _RESTORE_EVENT_NAME)
        if h_event:
            kernel32.SetEvent(h_event)
            kernel32.CloseHandle(h_event)
            signaled = True
    except Exception as e:
        logger.error(f"Error signaling restore event: {e}")
    # Also attempt direct window elevation fallback
    focus_existing_instance()
    return signaled

def release() -> None:
    global _mutex_handle, _restore_event_handle, _listener_thread
    _stop_listener.set()
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            if _restore_event_handle is not None:
                kernel32.CloseHandle(_restore_event_handle)
                _restore_event_handle = None
            if _mutex_handle is not None:
                kernel32.ReleaseMutex(_mutex_handle)
                kernel32.CloseHandle(_mutex_handle)
                _mutex_handle = None
        except Exception as e:
            logger.warning(f"Guard release error: {e}")

def show_already_running_dialog() -> str:
    # Retained for backward-compatibility with tests; normal launch uses direct activation
    try:
        import customtkinter as ctk
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        root = ctk.CTk()
        root.title("Visual Analyzer")
        root.geometry("420x200")
        root.resizable(False, False)
        root.configure(fg_color="#0A0B10")
        root.attributes("-topmost", True)
        root.update_idletasks()
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        x = (sw - 420) // 2
        y = (sh - 200) // 2
        root.geometry(f"420x200+{x}+{y}")
        result = {"action": "exit"}

        ctk.CTkLabel(
            root,
            text="⚡ Portal Connection",
            font=ctk.CTkFont(family="Segoe UI Variable", size=18, weight="bold"),
            text_color="#6366F1"
        ).pack(pady=(24, 4))

        ctk.CTkLabel(
            root,
            text="The portal client is already active in the background.",
            font=ctk.CTkFont(family="Segoe UI Variable", size=12),
            text_color="#9CA3AF"
        ).pack(pady=(0, 20))

        btn_frame = ctk.CTkFrame(root, fg_color="transparent")
        btn_frame.pack(fill="x", padx=30)

        def on_open():
            result["action"] = "focus"
            root.destroy()

        def on_exit():
            result["action"] = "exit"
            root.destroy()

        ctk.CTkButton(
            btn_frame,
            text="Open Client",
            fg_color="#6366F1",
            hover_color="#4F46E5",
            height=36,
            corner_radius=10,
            command=on_open
        ).pack(side="left", expand=True, padx=(0, 8))

        ctk.CTkButton(
            btn_frame,
            text="Exit",
            fg_color="transparent",
            border_width=1,
            border_color="#374151",
            text_color="#9CA3AF",
            hover_color="#1F2937",
            height=36,
            corner_radius=10,
            command=on_exit
        ).pack(side="right", expand=True, padx=(8, 0))

        root.mainloop()
        return result["action"]
    except Exception as e:
        logger.error(f"Guard dialog error: {e}")
        return "exit"

def focus_existing_instance() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        import ctypes.wintypes
        user32 = ctypes.windll.user32
        HWND_FOUND = ctypes.wintypes.HWND(0)

        def enum_callback(hwnd, lparam):
            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            # Find any Visual Analyzer window regardless of visibility state
            if "Visual Analyzer" in buf.value:
                HWND_FOUND.value = hwnd
                return False
            return True

        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
        user32.EnumWindows(EnumWindowsProc(enum_callback), 0)
        if HWND_FOUND.value:
            SW_RESTORE = 9
            root_hwnd = user32.GetAncestor(HWND_FOUND.value, 2)  # GA_ROOT
            target = root_hwnd if root_hwnd else HWND_FOUND.value
            user32.ShowWindow(target, SW_RESTORE)
            user32.SetForegroundWindow(target)
            return True
        return False
    except Exception as e:
        logger.error(f"Guard focus error: {e}")
        return False

