#!/usr/bin/env python3
"""SoundReport - Analyse et comparaison des niveaux sonores via ffmpeg loudnorm."""

import os
import sys

# Add script directory to path so relative imports work when run directly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib.ui import test_command_exists, select_folder
from lib.ffmpeg_utils import get_loudness_from_file
from lib.report import new_sound_report_data, write_sound_report_outputs

SUPPORTED_EXTS = {".mp3", ".mp4", ".m4a", ".wav", ".flac", ".ogg", ".mkv", ".mov", ".m4v"}


def main():
    if not test_command_exists("ffmpeg"):
        print("ERREUR: ffmpeg introuvable dans PATH.", file=sys.stderr)
        sys.exit(1)

    folder = select_folder()
    print(f"Dossier: {folder}")

    # Collect supported files recursively
    files = []
    for root, _, filenames in os.walk(folder):
        for name in filenames:
            ext = os.path.splitext(name)[1].lower()
            if ext in SUPPORTED_EXTS:
                files.append(os.path.join(root, name))

    files.sort()

    if not files:
        print(f"ERREUR: Aucun fichier supporté dans {folder}", file=sys.stderr)
        sys.exit(1)

    total = len(files)
    print(f"Analyse loudness de {total} fichier(s)...")

    metrics = []
    for i, path in enumerate(files):
        name = os.path.basename(path)
        ext = os.path.splitext(name)[1].lstrip(".")
        size = os.path.getsize(path)
        print(f"[{i + 1}/{total}] {name}")
        try:
            m = get_loudness_from_file(path)
            metrics.append(m)
        except Exception as e:
            metrics.append({
                "FileName": name,
                "Path": path,
                "Ext": ext,
                "SizeBytes": size,
                "LUFS_I": None,
                "TruePeak_dBTP": None,
                "LRA": None,
                "Peak_dBFS": None,
                "RMS_dBFS": None,
                "Error": str(e),
            })

    report = new_sound_report_data(metrics)
    out = write_sound_report_outputs(folder, report)

    print("OK. Sorties générées :")
    print(f" - HTML: {out['HtmlPath']}")
    print(f" - CSV : {out['CsvPath']}")


if __name__ == "__main__":
    main()
