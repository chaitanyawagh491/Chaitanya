import os
import customtkinter
from PyInstaller.utils.hooks import collect_data_files

customtkinter_path = os.path.dirname(customtkinter.__file__)
customtkinter_assets = (os.path.join(customtkinter_path, 'assets'), 'customtkinter/assets')

datas = [('ui/bg.png', 'ui'), ('ui/icon.ico', 'ui'), customtkinter_assets] + collect_data_files('customtkinter')

hiddenimports = [
    'pynput.keyboard._win32',
    'pynput.mouse._win32',
    'pystray._win32',
    'PIL._tkinter_finder',
    'engine.processor',
    'engine.hider',
    'engine.capture',
    'engine.detector',
    'engine.overlay',
    'utils.keys',
    'utils.alerts',
    'utils.log',
    'network.auth_client',
    'network.api_client',
    'network.security',
    'network.update_client',
    'services.quota_service',
    'services.diag_service',
    'services.env_service',
    'services.status_service',
    'ui.views.main',
    'ui.views.profile',
    'ui.views.settings',
    'ui.views.info',
    'ui.views.diag',
    'ui.views.admin.portal',
    'ui.views.login',
    'ui.components.side',
    'ui.tray',
    'ui.window',
    'win32crypt',
    'win32security',
    'win32api',
    'win32con',
    'win32gui',
    'win32process',
    'winotify',
    'bcrypt',
    'psutil',
    'cv2',
    'numpy',
    'customtkinter',
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='PortalClient',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='ui\\icon.ico',
)
