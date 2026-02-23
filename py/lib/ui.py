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
            title="Choisis le dossier contenant les fichiers audio/vidéo",
            mustexist=True,
        )
        root.destroy()

        if folder and folder.strip():
            return os.path.realpath(folder)
    except Exception:
        pass

    print("UI indisponible. Saisis le chemin du dossier:", flush=True)
    p = input("Dossier: ").strip()
    if not p:
        raise RuntimeError("Aucun dossier fourni.")
    if not os.path.isdir(p):
        raise RuntimeError(f"Chemin invalide: {p}")
    return os.path.realpath(p)
