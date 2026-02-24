# LoudScan

**Batch audio loudness analyser — compare LUFS, True Peak, LRA and RMS across your entire media library in one interactive HTML report.**

Drop a folder full of MP3s, WAVs, MP4s or any other common format and LoudScan will analyse every file with FFmpeg, then produce a self-contained HTML report and a CSV export so you can instantly spot which files are too loud, too quiet, or inconsistent.

---

## Why LoudScan?

When you're delivering audio for broadcast, streaming, podcast, or video production, consistent loudness matters. LoudScan lets you:

- **Audit a batch of files** without opening a DAW
- **Spot clipping instantly** — True Peak and Peak (dBFS) cells turn red if ≥ 0 dB
- **Compare every file pair** — all pairwise ΔMax values are ranked and colour-coded
- **See the big picture** — the "Globally same level?" indicator tells you at a glance whether your pool is balanced

---

## Features

- EBU R128 / ITU-R BS.1770 integrated loudness (LUFS_I), True Peak (dBTP) and Loudness Range (LRA)
- Raw Peak (dBFS) and RMS (dBFS) via FFmpeg `volumedetect` — single-pass, fast
- Interactive HTML report: dark theme, sortable tables, tooltip explanations, colour-coded metrics (Δ vs mean, Δ vs median, or Z-score)
- Clipping warnings (red highlight) for True Peak and Peak ≥ 0 dB
- Pairwise similarity table with 6 heuristic levels: **identical → negligible → slight → moderate → high → extreme**
- CSV export for further analysis in Excel, Python, etc.
- Recursive folder scan — works on nested folder structures
- GUI folder picker (tkinter) with CLI fallback

---

## Supported formats

`.mp3` `.mp4` `.m4a` `.wav` `.flac` `.ogg` `.mkv` `.mov` `.m4v`

---

## Requirements

- Python 3.8+
- [FFmpeg](https://ffmpeg.org/download.html) — must be in your `PATH`

No extra Python packages needed (standard library only).

---

## Installation

```bash
git clone https://github.com/YOUR_USERNAME/loudscan.git
cd loudscan
```

That's it. No `pip install` required.

---

## Usage

```bash
python sound_report.py
```

1. A folder picker dialog opens (or type the path if no GUI is available)
2. LoudScan scans the folder recursively and analyses every supported file
3. Two files are generated inside the selected folder:
   - `sound_report_DD-MM-YY_HH-MM.html` — open in any browser
   - `sound_report_DD-MM-YY_HH-MM.csv` — import into Excel / pandas

### Example output

```
Folder: /path/to/my/audio
Analysing loudness of 12 file(s)...
[1/12] track_01.wav
[2/12] track_02.wav
...
Done. Reports generated:
 - HTML: /path/to/my/audio/sound_report_24-02-26_14-30.html
 - CSV : /path/to/my/audio/sound_report_24-02-26_14-30.csv
```

---

## HTML report overview

| Section | What it shows |
|---|---|
| **KPI bar** | Total files, measured OK, pair count, worst pair |
| **Per-file metrics table** | LUFS_I, TruePeak, LRA, Peak, RMS — colour-coded, sortable |
| **Colouring selector** | Switch between Δ vs median / Δ vs mean / Z-score |
| **Pairwise table** | Every file pair, sorted by ΔMax, with similarity badge |
| **Distribution histogram** | Count of pairs per similarity level |

### Similarity scale

Based on `ΔMax = max(|ΔLUFS|, |ΔTruePeak|)`:

| Level | ΔMax |
|---|---|
| identical | < 0.10 dB |
| negligible | < 0.50 dB |
| slight | < 1.50 dB |
| moderate | < 3.00 dB |
| high | < 6.00 dB |
| extreme | ≥ 6.00 dB |

---

## Project structure

```
loudscan/
├── sound_report.py      # Entry point
└── lib/
    ├── ffmpeg_utils.py  # FFmpeg single-pass analysis
    ├── report.py        # Data processing + HTML/CSV generation
    ├── stats.py         # Median, std dev, similarity categories
    └── ui.py            # Folder picker (tkinter / CLI fallback)
```

---

## License

MIT — free to use, modify and distribute.

---

## Contributing

Issues and pull requests are welcome. If you encounter a file format that fails to analyse, please open an issue and include the FFmpeg version and file codec info (`ffprobe -v quiet -show_streams your_file`).
