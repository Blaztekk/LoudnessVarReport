import shutil
import sys
import os


def test_command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def select_folder() -> str:
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
    except Exception:
        pass

    print("GUI unavailable. Enter the folder path:", flush=True)
    p = input("Folder: ").strip()
    if not p:
        raise RuntimeError("No folder provided.")
    if not os.path.isdir(p):
        raise RuntimeError(f"Invalid path: {p}")
    return os.path.realpath(p)
