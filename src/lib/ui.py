import shutil
import sys
import os
import subprocess
import platform
from typing import Optional, Tuple


def test_command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def _select_folder_via_os_dialog(title: str) -> Tuple[Optional[str], Optional[str]]:
    """Best-effort OS-native folder picker.

    Returns (path, reason). If path is None, reason is a short error message.
    """
    try:
        system = platform.system()

        if system == "Windows":
            # Use PowerShell + WinForms (no extra Python deps).
            ps = shutil.which("powershell") or shutil.which("pwsh")
            if not ps:
                return None, "PowerShell not found"

            cmd = [
                ps,
                "-NoProfile",
                "-Command",
                (
                    "Add-Type -AssemblyName System.Windows.Forms; "
                    "$f = New-Object System.Windows.Forms.FolderBrowserDialog; "
                    f"$f.Description = '{title.replace("'", "''")}'; "
                    "$f.ShowNewFolderButton = $false; "
                    "if ($f.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { "
                    "$f.SelectedPath }"
                ),
            ]
            r = subprocess.run(cmd, capture_output=True, text=True)
            out = (r.stdout or "").strip()
            if out:
                return os.path.realpath(out), None
            return None, "dialog cancelled"

        if system == "Darwin":
            if not test_command_exists("osascript"):
                return None, "osascript not found"
            script = f'POSIX path of (choose folder with prompt "{title}")'
            r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
            out = (r.stdout or "").strip()
            if out:
                return os.path.realpath(out), None
            return None, (r.stderr or "").strip() or "dialog cancelled"

        # Linux / other unix
        if test_command_exists("zenity"):
            r = subprocess.run(
                ["zenity", "--file-selection", "--directory", f"--title={title}"],
                capture_output=True,
                text=True,
            )
            out = (r.stdout or "").strip()
            if out:
                return os.path.realpath(out), None
            return None, "dialog cancelled"

        return None, "no supported GUI picker found"
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def select_folder() -> str:
    title = "Select the folder containing your audio/video files"
    gui_reason: Optional[str] = None

    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        folder = filedialog.askdirectory(
            title=title,
            mustexist=True,
        )
        root.destroy()

        if folder and folder.strip():
            return os.path.realpath(folder)

        gui_reason = "folder selection cancelled"
    except ImportError as e:
        gui_reason = f"tkinter not available ({e})"
    except Exception as e:
        gui_reason = f"{type(e).__name__}: {e}"

    if gui_reason:
        # Try OS-native dialog as a fallback before switching to plain CLI.
        folder, os_gui_reason = _select_folder_via_os_dialog(title)
        if folder:
            return folder

        details = gui_reason
        if os_gui_reason and os_gui_reason != "dialog cancelled":
            details = f"{gui_reason}; {os_gui_reason}"

        print(f"GUI unavailable ({details}). Enter the folder path:", flush=True)
        if platform.system() == "Darwin" and "tkinter" in gui_reason:
            print(
                "macOS hint: tkinter is included with the python.org installer, but may be missing with some Python builds (e.g. Homebrew).",
                flush=True,
            )
            print(
                "Try: brew install python-tk  (or reinstall Python from https://www.python.org/downloads/mac-osx/)",
                flush=True,
            )
    else:
        print("GUI unavailable. Enter the folder path:", flush=True)

    p = input("Folder: ").strip()
    if not p:
        raise RuntimeError("No folder provided.")
    if not os.path.isdir(p):
        raise RuntimeError(f"Invalid path: {p}")
    return os.path.realpath(p)
