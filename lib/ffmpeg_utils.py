import json
import os
import re
import subprocess


def get_loudness_from_file(path: str) -> dict:
    """Analyse loudness + volume en un seul passage FFmpeg via filter_complex."""

    # Single-pass: split audio stream to loudnorm and volumedetect in parallel
    cmd = [
        "ffmpeg", "-hide_banner", "-nostats",
        "-i", path,
        "-filter_complex",
        "[0:a]asplit=2[a1][a2];"
        "[a1]loudnorm=print_format=json[out1];"
        "[a2]volumedetect[out2]",
        "-map", "[out1]", "-f", "null", "-",
        "-map", "[out2]", "-f", "null", "-",
    ]

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="replace",
    )

    output = result.stdout or ""

    # Parse loudnorm JSON (last JSON block in output)
    matches = re.findall(r"\{[\s\S]*?\}", output)
    if not matches:
        raise RuntimeError(f"Pas de JSON loudnorm pour: {path}")
    j = json.loads(matches[-1])

    # Parse volumedetect stats
    peak_m = re.search(r"max_volume:\s*([-\d.]+)\s*dB", output)
    rms_m  = re.search(r"mean_volume:\s*([-\d.]+)\s*dB", output)
    peak_dbfs = float(peak_m.group(1)) if peak_m else None
    rms_dbfs  = float(rms_m.group(1))  if rms_m  else None

    return {
        "FileName": os.path.basename(path),
        "Path": path,
        "Ext": os.path.splitext(path)[1].lower().lstrip("."),
        "SizeBytes": os.path.getsize(path),
        "LUFS_I": float(j["input_i"]),
        "TruePeak_dBTP": float(j["input_tp"]),
        "LRA": float(j["input_lra"]),
        "Peak_dBFS": peak_dbfs,
        "RMS_dBFS": rms_dbfs,
        "Error": None,
    }
