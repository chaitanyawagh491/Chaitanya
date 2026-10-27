import os
import sys
from pathlib import Path
import win32com.client

def create_desktop_shortcut():
    project_dir = Path(__file__).parent.resolve()
    pythonw_exe = project_dir / ".venv" / "Scripts" / "pythonw.exe"
    if not pythonw_exe.exists():
        pythonw_exe = Path(sys.executable).parent / "pythonw.exe"
    
    main_script = project_dir / "main.py"
    icon_path = project_dir / "ui" / "icon.ico"
    
    shell = win32com.client.Dispatch("WScript.Shell")
    desktop_dirs = set()
    
    # Standard shell desktop folder
    try:
        shell_desktop = shell.SpecialFolders("Desktop")
        if shell_desktop and os.path.exists(shell_desktop):
            desktop_dirs.add(Path(shell_desktop))
    except Exception as e:
        print(f"Error resolving special folder Desktop: {e}")
        
    # Check user profile desktop
    user_profile = os.environ.get("USERPROFILE")
    if user_profile:
        direct_desktop = Path(user_profile) / "Desktop"
        if direct_desktop.exists():
            desktop_dirs.add(direct_desktop)
        onedrive_desktop = Path(user_profile) / "OneDrive" / "Desktop"
        if onedrive_desktop.exists():
            desktop_dirs.add(onedrive_desktop)
            
    created = []
    for d in desktop_dirs:
        shortcut_path = d / "PortalClient.lnk"
        try:
            shortcut = shell.CreateShortcut(str(shortcut_path))
            shortcut.TargetPath = str(pythonw_exe)
            shortcut.Arguments = f'"{main_script}"'
            shortcut.WorkingDirectory = str(project_dir)
            if icon_path.exists():
                shortcut.IconLocation = str(icon_path)
            shortcut.Description = "PortalClient - Visual Analyzer"
            shortcut.WindowStyle = 1  # Normal window
            shortcut.Save()
            created.append(shortcut_path)
            print(f"Created shortcut at: {shortcut_path}")
        except Exception as e:
            print(f"Failed to create shortcut at {shortcut_path}: {e}")
            
    return created

if __name__ == "__main__":
    shortcuts = create_desktop_shortcut()
    if shortcuts:
        print(f"Successfully configured {len(shortcuts)} shortcut(s).")
    else:
        print("Warning: No shortcuts were created.")
