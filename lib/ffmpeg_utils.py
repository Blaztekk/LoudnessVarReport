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

    # Pass 2 : volumedetect → Peak dBFS (max_volume) + RMS dBFS (mean_volume)
    cmd_vol = ["ffmpeg", "-hide_banner", "-nostats", "-i", path]
    if ext in VIDEO_EXTS:
        cmd_vol += ["-vn"]
    cmd_vol += ["-af", "volumedetect", "-f", "null", "-"]

    result_vol = subprocess.run(
        cmd_vol,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="replace",
    )
    vol_out = result_vol.stdout or ""

    peak_m = re.search(r"max_volume:\s*([-\d.]+)\s*dB", vol_out)
    rms_m  = re.search(r"mean_volume:\s*([-\d.]+)\s*dB", vol_out)
    peak_dbfs = float(peak_m.group(1)) if peak_m else None
    rms_dbfs  = float(rms_m.group(1))  if rms_m  else None

    return {
        "FileName": os.path.basename(path),
        "Path": path,
        "Ext": ext.lstrip("."),
        "SizeBytes": os.path.getsize(path),
        "LUFS_I": float(j["input_i"]),
        "TruePeak_dBTP": float(j["input_tp"]),
        "LRA": float(j["input_lra"]),
        "Peak_dBFS": peak_dbfs,
        "RMS_dBFS": rms_dbfs,
        "Error": None,
    }
