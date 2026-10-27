import os
import sys
import time
import requests
import subprocess
from pathlib import Path

# Ensure Tcl/Tk libraries are found across multiple sequential Tk instances on Windows
_tcl_base = Path(sys.base_prefix) / "tcl"
if (_tcl_base / "tcl8.6").exists():
    os.environ["TCL_LIBRARY"] = str(_tcl_base / "tcl8.6")
if (_tcl_base / "tk8.6").exists():
    os.environ["TK_LIBRARY"] = str(_tcl_base / "tk8.6")

import pytest
from config import config
from network.auth_client import KeyAuthHandler
from ui.window import ActivationWindow
from core.boot import BootSequence

def ensure_test_server():
    server_url = config.AUTH_SERVER_URL.rstrip('/')
    try:
        r = requests.get(f"{server_url}/api/ping", timeout=0.5)
        if r.status_code == 200:
            return
    except Exception:
        pass
    
    server_script = Path(__file__).parent.parent / "server" / "app.py"
    creationflags = 0x08000000 if sys.platform == "win32" else 0
    subprocess.Popen(
        [sys.executable, str(server_script)],
        cwd=str(server_script.parent.parent),
        creationflags=creationflags
    )
    for _ in range(25):
        try:
            r = requests.get(f"{server_url}/api/ping", timeout=0.5)
            if r.status_code == 200:
                break
        except Exception:
            pass
        time.sleep(0.1)

def test_activation_window_lifecycle_and_navigation():
    ensure_test_server()
    # Use real handler pointing to live server
    handler = KeyAuthHandler(
        name="PortalClient",
        owner_id="DevOwner",
        version=config.CURRENT_VERSION,
        data_dir=config.LOG_DIR
    )

    
    boot = BootSequence(config.CURRENT_VERSION)
    boot.begin("TestBoot")
    boot.ok("Ready")
    
    authorized_called = []
    
    app = ActivationWindow(
        handler=handler,
        on_authorized=lambda: authorized_called.append(True),
        on_start_engine=lambda: None,
        on_stop_engine=lambda: None,
        on_shortcut_changed=lambda s: None,
        on_logout=lambda: None,
    )
    
    try:
        # Verify app window initialized
        assert app.winfo_exists()
        assert app.title() == "Visual Analyzer"
        
        # Verify initial auth view shown
        assert app.is_authenticated is False
        
        # Test simulated login with admin credentials
        user_info = handler.login_username_password("admin", "admin123", remember=False)
        assert user_info.get("username") == "admin"
        assert user_info.get("role") == "admin"
        
        # Feed login to app window
        app._on_login_success({"user_data": user_info, "token": handler.session_token})
        assert app.is_authenticated is True
        assert app.is_admin is True
        assert len(authorized_called) == 1
        
        # Test navigation across all views
        for tab in ["dash", "sub", "pref", "notes", "diag", "admin"]:
            app._navigate_to(tab)
            assert app._current_tab == tab
            
        # Test logout flow
        app._logout()
        assert app.is_authenticated is False
        assert app.logged_in is False
        
    finally:
        try:
            app.update_idletasks()
        except Exception:
            pass
        app.destroy()

def test_activation_window_seamless_local_entry():
    handler = KeyAuthHandler(
        name="PortalClient",
        owner_id="DevOwner",
        version=config.CURRENT_VERSION,
        data_dir=config.LOG_DIR
    )
    
    authorized_called = []
    
    app = ActivationWindow(
        handler=handler,
        on_authorized=lambda: authorized_called.append(True),
        on_start_engine=lambda: None,
        on_stop_engine=lambda: None,
        on_shortcut_changed=lambda s: None,
        on_logout=lambda: None,
    )
    
    try:
        # Simulate local session result directly
        local_res = handler.get_or_create_local_session()
        assert local_res["success"] is True
        
        app._on_login_success(local_res)
        assert app.is_authenticated is True
        assert app.logged_in is True
        assert app._current_tab == "dash"
        assert len(authorized_called) == 1
    finally:
        try:
            app.update_idletasks()
        except Exception:
            pass
        app.destroy()

