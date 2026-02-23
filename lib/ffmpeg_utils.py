import json
import os
import re
import subprocess


VIDEO_EXTS = {".mp4", ".m4v", ".mov", ".mkv"}


def get_loudness_from_file(path: str) -> dict:
    ext = os.path.splitext(path)[1].lower()

    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-i", path]
    if ext in VIDEO_EXTS:
        cmd += ["-vn"]
    cmd += ["-af", "loudnorm=print_format=json", "-f", "null", "-"]

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="replace",
    )

    output = result.stdout or ""

    matches = re.findall(r"\{[\s\S]*?\}", output)
    if not matches:
        raise RuntimeError(f"Pas de JSON loudnorm pour: {path}")

    j = json.loads(matches[-1])

    return {
        "FileName": os.path.basename(path),
        "Path": path,
        "Ext": ext.lstrip("."),
        "SizeBytes": os.path.getsize(path),
        "LUFS_I": float(j["input_i"]),
        "TruePeak_dBTP": float(j["input_tp"]),
        "LRA": float(j["input_lra"]),
        "Error": None,
    }
