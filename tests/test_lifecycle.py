import pytest
import core.safe as safe_mode
from core.boot import BootSequence
import core.guard as guard

def test_safe_mode_lifecycle():
    assert safe_mode.is_active() is False
    assert len(safe_mode.get_reasons()) == 0
    
    safe_mode.enable(["Missing dependency test", "Invalid config"])
    assert safe_mode.is_active() is True
    reasons = safe_mode.get_reasons()
    assert "Missing dependency test" in reasons
    assert "Invalid config" in reasons
    
    safe_mode.disable()
    assert safe_mode.is_active() is False
    assert len(safe_mode.get_reasons()) == 0

def test_boot_sequence_lifecycle():
    boot = BootSequence("3.0.0")
    boot.begin("Init Config")
    boot.ok("Loaded defaults")
    assert boot.is_healthy() is True
    
    boot.begin("Check Network")
    boot.warn("High latency detected")
    assert boot.is_healthy() is True
    
    boot.begin("Security Handshake")
    boot.fail("Simulated authentication rejection")
    assert boot.is_healthy() is False
    assert len(boot.get_failed_phases()) == 1

def test_mutex_guard_acquire_and_release():
    acquired = guard.acquire()
    assert acquired is True
    guard.release()

def test_restore_event_signaling():
    acquired = guard.acquire()
    assert acquired is True
    try:
        received = []
        def on_restore():
            received.append(True)
            
        thread = guard.start_restore_listener(on_restore)
        assert thread is not None
        assert thread.is_alive()
        
        # Signal restore
        guard.signal_restore_existing_instance()
        
        # Wait for listener thread to trigger callback
        import time
        for _ in range(20):
            if received:
                break
            time.sleep(0.05)
            
        assert len(received) >= 1
    finally:
        guard.release()


def test_stealth_tray_menu_and_actions():
    from ui.tray import StealthTray
    actions = []
    
    tray = StealthTray(
        on_open_client=lambda: actions.append("open"),
        on_hide_to_tray=lambda: actions.append("hide"),
        on_exit_app=lambda: actions.append("exit")
    )
    
    img = tray.create_dynamic_icon()
    assert img is not None
    assert img.size[0] > 0
    
    tray.rebuild_menu()
    assert tray.current_menu is not None
    
    # Test safe callbacks directly
    tray._safe_call(tray.on_open_client)
    assert "open" in actions
    tray._safe_call(tray.on_hide_to_tray)
    assert "hide" in actions

