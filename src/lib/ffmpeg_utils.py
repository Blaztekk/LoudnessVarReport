import os
import re
import subprocess


def get_loudness_from_file(path: str) -> dict:
    """Analyse loudness + volume en un seul passage FFmpeg via filter_complex."""

    # Single-pass: split audio stream to ebur128 and volumedetect in parallel.
    # ebur128=peak=true gives Integrated (I), Momentary (M), Short-Term (S),
    # Loudness Range (LRA), and True Peak — all per EBU R128 / ITU-R BS.1770.
    cmd = [
        "ffmpeg", "-hide_banner", "-nostats",
        "-i", path,
        "-filter_complex",
        "[0:a]asplit=2[a1][a2];"
        "[a1]ebur128=peak=true[out1];"
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

    # --- ebur128 summary (printed at end of stream) ---
    summary_m = re.search(r"Summary:(.*)", output, re.DOTALL)
    summary = summary_m.group(1) if summary_m else ""

    lufs_i_m = re.search(r"I:\s*([-\d.]+)\s*LUFS", summary)
    lra_m    = re.search(r"LRA:\s*([\d.]+)\s*LU", summary)
    tp_m     = re.search(r"Peak:\s*([-\d.]+)\s*dBFS", summary)

    if not lufs_i_m:
        raise RuntimeError(f"No ebur128 output for: {path}")

    lufs_i    = float(lufs_i_m.group(1))
    lra       = float(lra_m.group(1)) if lra_m else None
    true_peak = float(tp_m.group(1))  if tp_m  else None

    # --- Max Momentary and Short-Term from per-frame lines ---
    # Per-frame format: "t: 0.40  M: -18.2  S: -21.0  I: -19.1 LUFS ..."
    def _max_lufs(pattern: str):
        raw = re.findall(pattern, output)
        vals = []
        for v in raw:
            if v.lower() != "-inf":
                try:
                    vals.append(float(v))
                except ValueError:
                    pass
        return max(vals) if vals else None

    lufs_m = _max_lufs(r"\sM:\s+([-\d.]+|-inf)")
    lufs_s = _max_lufs(r"\sS:\s+([-\d.]+|-inf)")

    # --- volumedetect stats ---
    peak_m = re.search(r"max_volume:\s*([-\d.]+)\s*dB", output)
    rms_m  = re.search(r"mean_volume:\s*([-\d.]+)\s*dB", output)
    peak_dbfs = float(peak_m.group(1)) if peak_m else None
    rms_dbfs  = float(rms_m.group(1))  if rms_m  else None

    return {
        "FileName": os.path.basename(path),
        "Path": path,
        "Ext": os.path.splitext(path)[1].lower().lstrip("."),
        "SizeBytes": os.path.getsize(path),
        "LUFS_I": lufs_i,
        "LUFS_M": lufs_m,
        "LUFS_S": lufs_s,
        "TruePeak_dBTP": true_peak,
        "LRA": lra,
        "Peak_dBFS": peak_dbfs,
        "RMS_dBFS": rms_dbfs,
        "Error": None,
    }
