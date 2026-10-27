import logging
import threading
import queue
import time
from config import Config
from engine.detector import InputDetector
from engine.capture import ScreenCaptureManager
from network.api_client import ApiClient
from engine.overlay import OverlayController
from engine.hider import VisibilityController
from utils.log import log_exception, add_recent_event

logger = logging.getLogger(__name__)

class PipelineManager:
    def __init__(self, config: Config, parent=None):
        self.config = config
        self.parent = parent
        self.gesture_detector = InputDetector(
            config.TRIPLE_TAP_WINDOW,
            config.TAP_DETECTION_RADIUS
        )
        self.capture_manager = ScreenCaptureManager(config, parent=parent)
        if not self.config.CROP_BOX:
            self.capture_manager.request_screen_selection(parent=parent)
        self.api_handler = ApiClient(config)
        self.injection = OverlayController(config, parent=parent)
        self.task_queue = queue.Queue()
        self.processing = False
        self.running = True
        if config.HIDE_PROCESS:
            VisibilityController.hide_console()
            VisibilityController.hide_from_taskbar()

    def _process_pipeline(self) -> None:
        while self.running:
            try:
                self.task_queue.get(timeout=1)
                if self.processing:
                    continue
                self.processing = True

                # Drain any redundant triggers queued during busy period
                while not self.task_queue.empty():
                    try:
                        self.task_queue.get_nowait()
                    except Exception:
                        break

                add_recent_event("Pipeline trigger received")

                screenshot = self.capture_manager.capture_screen()
                if not screenshot:
                    self.injection.display_error("Screen capture failed. Check the capture coordinates and permissions.")
                    continue

                add_recent_event("Screen region captured")
                if self.parent and hasattr(self.parent, "_credit_service") and self.parent._credit_service:
                    ok, msg = self.parent._credit_service.check_and_consume()
                    if not ok:
                        self.injection.display_error("No resources available.")
                        if hasattr(self.parent, "_refresh_credits_background"):
                            self.parent._refresh_credits_background()
                        continue

                result = self.api_handler.query_with_details(screenshot)
                if result.success and result.text:
                    add_recent_event(f"Query returned: {len(result.text)} chars ({result.duration_sec:.2f}s)")
                    self.injection.display_response(result.text)
                else:
                    err_msg = result.error_message or "The AI returned no answer. Try capturing the question again."
                    add_recent_event(f"Query error: {err_msg}")
                    self.injection.display_error(err_msg)

                if self.parent and hasattr(self.parent, "_refresh_credits_background"):
                    self.parent._refresh_credits_background()
            except queue.Empty:
                continue
            except Exception as e:
                log_exception(logger, "PipelineManager", "_process_pipeline", e)
                try:
                    self.injection.display_error("AI analysis failed. Check Diagnostics or the application log for details.")
                except Exception:
                    pass
            finally:
                self.processing = False

    def trigger_analysis(self) -> bool:
        """Manually trigger analysis (e.g. from hotkey, test action, or gesture)."""
        if not self.processing:
            add_recent_event("Manual trigger initiated")
            self.task_queue.put(True)
            return True
        return False

    def _on_gesture_detected(self) -> None:
        if not self.processing:
            add_recent_event("Trigger detected")
            self.task_queue.put(True)


    def start(self) -> None:
        self.gesture_detector.set_callback(self._on_gesture_detected)
        processor = threading.Thread(
            target=self._process_pipeline,
            daemon=True,
            name="PipelineProcessor"
        )
        processor.start()
        gesture_thread = threading.Thread(
            target=self.gesture_detector.start,
            daemon=True,
            name="GestureListener"
        )
        gesture_thread.start()

    def shutdown(self) -> None:
        self.running = False
        self.gesture_detector.stop()

class StealthSystem(PipelineManager):
    pass
