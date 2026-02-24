import shutil
import sys
import os


def test_command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def select_folder() -> str:
    gui_reason: str | None = None

    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        folder = filedialog.askdirectory(
            title="Select the folder containing your audio/video files",
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
        print(f"GUI unavailable ({gui_reason}). Enter the folder path:", flush=True)
        if sys.platform == "darwin" and "tkinter" in gui_reason:
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
