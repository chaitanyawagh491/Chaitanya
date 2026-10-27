# PortalClient (PortalCore) - Visual Analyzer Desktop Application

A production-grade Windows desktop application built with Python, CustomTkinter, and OpenCV, designed for real-time visual screen capture, multi-provider AI vision analysis (Google Gemini, OpenAI, OpenRouter), local Flask-based authentication and device hardware (HWID) licensing.

---

## 1. System Requirements & Architecture

- **Operating System**: Windows 10 / Windows 11 (64-bit)
- **Python Version**: Python 3.12+ (Tested and verified on Python 3.14 64-bit)
- **Key Frameworks**:
  - `customtkinter`: Modern dark-mode UI with custom glassmorphic styling
  - `opencv-python`, `Pillow`, `numpy`: High-performance screen capture and image processing
  - `pynput`: Global hotkey listener (e.g., `<ctrl>+<alt>+a` or `Ctrl+Shift+S`)
  - `pystray`: Windows system tray icon and background lifecycle management
  - `pywin32`: Windows DPAPI secret encryption (`win32crypt`) and window foreground management
  - `Flask`, `sqlite3`, `bcrypt`: Local authentication, hardware fingerprinting, and administration service

```
axiom-ghost/
├── core/                   # Engine lifecycle, mutex guard, and safe-mode manager
├── display/                # Transparent canvas and response overlay renderer
├── engine/                 # Screen capture, detector, hider, and pipeline processor
├── helpers/                # Encryption and system utility functions
├── network/                # Multi-provider AI vision client, AuthClient, security
├── services/               # Diagnostic, status, quota, and environment services
├── server/                 # Local Flask backend, SQLite DB, admin endpoints
├── ui/                     # CustomTkinter dashboard, views, components, and tray
├── utils/                  # Global hotkeys, logging, alerts, and crash reporting
├── tests/                  # Automated pytest verification test suite
├── main.py                 # Desktop application entry point
├── config.py               # Settings manager with Windows DPAPI encryption
├── requirements.txt        # Python package dependencies
├── main.spec               # PyInstaller executable build specification
├── .env.example            # Documented environment variable template
└── .env                    # Local runtime environment configuration
```

---

## 2. Installation and Environment Setup

1. **Clone or navigate to the project directory**:
   ```powershell
   cd "C:\Users\chaiw\Downloads\axiom-ghost\axiom-ghost"
   ```

2. **Create and activate a virtual environment**:
   ```powershell
   # Create environment using your installed Python interpreter
   py -3.12 -m venv .venv
   # (Or use the active Python 3.14 on this machine: python -m venv .venv)

   .\.venv\Scripts\Activate.ps1
   ```

3. **Install dependencies**:
   ```powershell
   python -m pip install --upgrade pip setuptools wheel
   python -m pip install -r requirements.txt
   python -m pip install bcrypt flask pyinstaller pytest
   ```

---

## 3. Configuration (`.env` and Preferences)

1. Copy `.env.example` to `.env`:
   ```powershell
   Copy-Item .env.example .env
   ```

2. **Configure AI Vision Provider Keys**:
   - Provide an API key for your preferred AI provider in `.env` (or via the **Preferences** tab inside the app):
     - `GEMINI_API_KEY`: Google Gemini API key
     - `OPENAI_API_KEY`: OpenAI API key
     - `OPENROUTER_API_KEY`: OpenRouter API key
   - **Security**: When API keys are saved inside the application Preferences UI, they are automatically protected at rest using **Windows DPAPI** (`win32crypt.CryptProtectData`). All keys are redacted from logs and crash reports (`[REDACTED_API_KEY]`).

3. **Key Runtime Variables**:
   - `AUTH_SERVER_URL`: URL of the local or remote authentication server (default: `http://127.0.0.1:5000`)
   - `TRIPLE_TAP_WINDOW`: Click window duration in seconds (default: `0.5`)
   - `RESPONSE_DURATION`: Overlay display duration in seconds (default: `2.0`)
   - `HIDE_CONSOLE`: Set to `false` for terminal debugging output, `true` for silent production launch

---

## 4. Starting the Local Authentication Server

Before launching the desktop client, start the backend authentication server:

```powershell
# 1. Initialize the SQLite database and seed admin account
python server\db.py

# 2. Start the Flask authentication server
python server\app.py
```

The server initializes at `http://127.0.0.1:5000`.
- **Default Administrator Credentials**:
  - **Username**: `admin`
  - **Password**: `admin123` (or set custom via `ADMIN_PASSWORD` environment variable)
  - **Role**: `admin` (unlimited credits)

---

## 5. Running the Desktop Application

Open a second terminal, activate the virtual environment, and run:

```powershell
.\.venv\Scripts\Activate.ps1
python main.py
```

### Application Features & Verified Workflows:
- **Startup Diagnostics**: Automated 5-phase boot sequence (Config, Storage, Security, Process Stealth, Auth Handler).
- **Authentication**: Login with `admin` / `admin123` or register new users with an invite key.
- **Hardware Binding**: HWID is automatically extracted from Windows MachineGuid / SID and bound to the account.
- **Navigation**: Switch between Dashboard, Account & Devices, Preferences, Release Notes, Diagnostics, and Admin Portal.
- **Visual Engine**: Start and stop real-time capture engine (`on_start_engine` / `on_stop_engine`).
- **Global Hotkey**: Press `<ctrl>+<alt>+a` or `Ctrl+Shift+S` anywhere in Windows to toggle visibility.
- **System Tray**: Left-click tray icon or use menu items ("Open Dashboard", "Open Settings", "License Information", "Restart Engine", "Exit") with foreground window elevation.

---

## 6. Running Automated Tests

Run the complete automated test suite verifying all modules:

```powershell
# Check Python syntax across all modules
python -m compileall -q .

# Run all 21 automated unit and integration tests
python -m pytest -v
```

---

## 7. Packaging Standalone Windows Executable

To build the standalone `.exe` using PyInstaller:

```powershell
python -m PyInstaller --clean --noconfirm main.spec
```

The compiled standalone executable will be located at:
`dist\PortalClient\PortalClient.exe` (or `dist\PortalClient.exe`)

---

## 8. Summary of Repairs & Defect Fixes

1. **Runtime Dependencies**: Added `bcrypt>=4.0.0` and `Flask>=3.0.0` to `requirements.txt`.
2. **Log Redaction**: Fixed `SensitiveInfoFormatter` in `utils/log.py` to dynamically inspect `config.API_KEYS.values()` to eliminate `AttributeError` and guarantee API keys are redacted.
3. **Encrypted Storage**: Upgraded `config.py` from plaintext JSON storage to **Windows DPAPI** (`win32crypt.CryptProtectData` / `CryptUnprotectData`) with automatic migration of legacy plaintext keys.
4. **Gemini REST Prefix**: Fixed URL generation in `network/api_client.py` by stripping redundant `models/` prefix to prevent HTTP 404 errors.
5. **Thread-Safe Capture**: Fixed Tkinter cross-thread GUI alert in `engine/capture.py` by adding main thread checks and fallback to full-screen capture.
6. **Safe-Mode Sidebar Layout**: Refactored `ui/components/side.py` with a dedicated header container `_header_frame` to prevent the Safe Mode banner from overlapping the title label.
7. **Windows Tray Foreground Restoration**: Updated `main.py` tray actions to use Windows `ShowWindow(hwnd, 9)` (SW_RESTORE) and `SetForegroundWindow(hwnd)` for reliable foreground elevation.
8. **PyInstaller Spec**: Configured full `hiddenimports` in `main.spec` and bundled all CustomTkinter themes/fonts/icons via `collect_data_files('customtkinter')`.
9. **Consistent Database Initialization**: Synchronized schema and administrator seeding between `server/app.py` and `server/db.py`.
10. **Cached Credentials Translation**: Fixed Windows text-mode newline corruption in `network/auth_client.py` by enforcing `newline=""` on raw encrypted byte streams.
