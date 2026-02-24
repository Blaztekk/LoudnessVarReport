import csv
import json
import os
from datetime import datetime
from itertools import combinations
from typing import List, Optional

from .stats import get_median, get_stddev, get_diff_category, html_escape, format_num


def new_sound_report_data(metrics: list) -> dict:
    if metrics is None:
        metrics = []

    ok = [m for m in metrics if m.get("LUFS_I") is not None
          and m.get("TruePeak_dBTP") is not None
          and m.get("LRA") is not None]
    err = [m for m in metrics if m.get("LUFS_I") is None
           or m.get("TruePeak_dBTP") is None
           or m.get("LRA") is None]

    if not ok:
        raise RuntimeError("Aucune mesure loudnorm exploitable (tous en erreur).")

    lufs_vals = [float(m["LUFS_I"]) for m in ok]
    tp_vals = [float(m["TruePeak_dBTP"]) for m in ok]
    lra_vals = [float(m["LRA"]) for m in ok]
    peak_vals = [float(m["Peak_dBFS"]) for m in ok if m.get("Peak_dBFS") is not None]
    rms_vals  = [float(m["RMS_dBFS"])  for m in ok if m.get("RMS_dBFS")  is not None]

    def _mean(vals):
        return sum(vals) / len(vals)

    def _safe_stats(vals):
        if not vals:
            return {"mean": None, "median": None, "std": None}
        return {"mean": _mean(vals), "median": get_median(vals), "std": get_stddev(vals)}

    stats = {
        "LUFS_I": {
            "mean": _mean(lufs_vals),
            "median": get_median(lufs_vals),
            "std": get_stddev(lufs_vals),
        },
        "TruePeak_dBTP": {
            "mean": _mean(tp_vals),
            "median": get_median(tp_vals),
            "std": get_stddev(tp_vals),
        },
        "LRA": {
            "mean": _mean(lra_vals),
            "median": get_median(lra_vals),
            "std": get_stddev(lra_vals),
        },
        "Peak_dBFS": _safe_stats(peak_vals),
        "RMS_dBFS":  _safe_stats(rms_vals),
    }

    files_enriched = []
    for m in metrics:
        is_ok = (m.get("LUFS_I") is not None
                 and m.get("TruePeak_dBTP") is not None
                 and m.get("LRA") is not None)
        if not is_ok:
            files_enriched.append({
                "Section": "File",
                "FileName": m["FileName"],
                "Ext": m["Ext"],
                "SizeBytes": m["SizeBytes"],
                "Path": m["Path"],
                "LUFS_I": None,
                "TruePeak_dBTP": None,
                "LRA": None,
                "Peak_dBFS": None,
                "RMS_dBFS": None,
                "LUFS_DeltaMean": None,
                "LUFS_DeltaMedian": None,
                "LUFS_Z": None,
                "TP_DeltaMean": None,
                "TP_DeltaMedian": None,
                "TP_Z": None,
                "LRA_DeltaMean": None,
                "LRA_DeltaMedian": None,
                "LRA_Z": None,
                "Error": m.get("Error"),
            })
            continue

        lufs = float(m["LUFS_I"])
        tp = float(m["TruePeak_dBTP"])
        lra = float(m["LRA"])

        lufs_std = stats["LUFS_I"]["std"]
        tp_std = stats["TruePeak_dBTP"]["std"]
        lra_std = stats["LRA"]["std"]

        lufs_z = (lufs - stats["LUFS_I"]["mean"]) / lufs_std if lufs_std > 1e-9 else 0.0
        tp_z = (tp - stats["TruePeak_dBTP"]["mean"]) / tp_std if tp_std > 1e-9 else 0.0
        lra_z = (lra - stats["LRA"]["mean"]) / lra_std if lra_std > 1e-9 else 0.0

        files_enriched.append({
            "Section": "File",
            "FileName": m["FileName"],
            "Ext": m["Ext"],
            "SizeBytes": m["SizeBytes"],
            "Path": m["Path"],
            "LUFS_I": lufs,
            "TruePeak_dBTP": tp,
            "LRA": lra,
            "Peak_dBFS": m.get("Peak_dBFS"),
            "RMS_dBFS": m.get("RMS_dBFS"),
            "LUFS_DeltaMean": lufs - stats["LUFS_I"]["mean"],
            "LUFS_DeltaMedian": lufs - stats["LUFS_I"]["median"],
            "LUFS_Z": lufs_z,
            "TP_DeltaMean": tp - stats["TruePeak_dBTP"]["mean"],
            "TP_DeltaMedian": tp - stats["TruePeak_dBTP"]["median"],
            "TP_Z": tp_z,
            "LRA_DeltaMean": lra - stats["LRA"]["mean"],
            "LRA_DeltaMedian": lra - stats["LRA"]["median"],
            "LRA_Z": lra_z,
            "Error": None,
        })

    # Pairwise comparisons (OK only)
    pairs = []
    for a, b in combinations(ok, 2):
        d_lufs = float(b["LUFS_I"]) - float(a["LUFS_I"])
        d_tp = float(b["TruePeak_dBTP"]) - float(a["TruePeak_dBTP"])
        d_max = max(abs(d_lufs), abs(d_tp))
        cat = get_diff_category(d_lufs, d_tp)
        pairs.append({
            "Section": "Pair",
            "A_File": a["FileName"],
            "B_File": b["FileName"],
            "A_Ext": a["Ext"],
            "B_Ext": b["Ext"],
            "A_LUFS_I": float(a["LUFS_I"]),
            "B_LUFS_I": float(b["LUFS_I"]),
            "dLUFS": d_lufs,
            "A_TP_dBTP": float(a["TruePeak_dBTP"]),
            "B_TP_dBTP": float(b["TruePeak_dBTP"]),
            "dTP": d_tp,
            "dMaxAbs": d_max,
            "Similarite": cat,
        })

    # Global heuristic
    levels = ["Egal", "imperceptible", "leger", "moyen", "\u00e9lev\u00e9", "\u00e9norme"]

    def level_index(s):
        try:
            return levels.index(s)
        except ValueError:
            return 999

    ratio_leger_or_less = 1.0
    worst_pair = None
    mean_delta = 0.0

    if pairs:
        leger_idx = level_index("leger")
        count_leger = sum(1 for p in pairs if level_index(p["Similarite"]) <= leger_idx)
        ratio_leger_or_less = count_leger / len(pairs)
        worst_pair = max(pairs, key=lambda p: p["dMaxAbs"])
        mean_delta = sum(p["dMaxAbs"] for p in pairs) / len(pairs)

    global_same = (
        not pairs
        or (
            worst_pair is not None
            and worst_pair["dMaxAbs"] <= 1.5
            and ratio_leger_or_less >= 0.80
        )
    )

    return {
        "Metrics": metrics,
        "FilesOk": ok,
        "FilesErr": err,
        "Stats": stats,
        "FilesEnriched": files_enriched,
        "Pairs": pairs,
        "Summary": {
            "FilesTotal": len(metrics),
            "FilesOk": len(ok),
            "FilesErr": len(err),
            "Pairs": len(pairs),
            "RatioLegerOrLess": ratio_leger_or_less,
            "MeanDelta": mean_delta,
            "MaxDelta": worst_pair["dMaxAbs"] if worst_pair else None,
            "WorstPair": worst_pair,
            "GlobalSame": global_same,
        },
    }


def write_sound_report_outputs(folder: str, report: dict) -> dict:
    ts = datetime.now().strftime("%d-%m-%y_%H-%M")
    html_path = os.path.join(folder, f"sound_report_{ts}.html")
    csv_path = os.path.join(folder, f"sound_report_{ts}.csv")

    # CSV
    fieldnames = [
        "Section", "FileName", "Ext", "SizeBytes",
        "LUFS_I", "TruePeak_dBTP", "LRA", "Peak_dBFS", "RMS_dBFS",
        "LUFS_DeltaMean", "LUFS_DeltaMedian", "LUFS_Z",
        "TP_DeltaMean", "TP_DeltaMedian", "TP_Z",
        "LRA_DeltaMean", "LRA_DeltaMedian", "LRA_Z",
        "A_File", "B_File", "dLUFS", "dTP", "dMaxAbs", "Similarite",
        "Error",
    ]

    csv_rows = []
    for r in report["FilesEnriched"]:
        csv_rows.append({
            "Section": "File",
            "FileName": r["FileName"],
            "Ext": r["Ext"],
            "SizeBytes": r["SizeBytes"],
            "LUFS_I": r["LUFS_I"],
            "TruePeak_dBTP": r["TruePeak_dBTP"],
            "LRA": r["LRA"],
            "Peak_dBFS": r.get("Peak_dBFS"),
            "RMS_dBFS": r.get("RMS_dBFS"),
            "LUFS_DeltaMean": r["LUFS_DeltaMean"],
            "LUFS_DeltaMedian": r["LUFS_DeltaMedian"],
            "LUFS_Z": r["LUFS_Z"],
            "TP_DeltaMean": r["TP_DeltaMean"],
            "TP_DeltaMedian": r["TP_DeltaMedian"],
            "TP_Z": r["TP_Z"],
            "LRA_DeltaMean": r["LRA_DeltaMean"],
            "LRA_DeltaMedian": r["LRA_DeltaMedian"],
            "LRA_Z": r["LRA_Z"],
            "A_File": None,
            "B_File": None,
            "dLUFS": None,
            "dTP": None,
            "dMaxAbs": None,
            "Similarite": None,
            "Error": r["Error"],
        })

    for p in report["Pairs"]:
        csv_rows.append({
            "Section": "Pair",
            "FileName": None,
            "Ext": None,
            "SizeBytes": None,
            "LUFS_I": None,
            "TruePeak_dBTP": None,
            "LRA": None,
            "Peak_dBFS": None,
            "RMS_dBFS": None,
            "LUFS_DeltaMean": None,
            "LUFS_DeltaMedian": None,
            "LUFS_Z": None,
            "TP_DeltaMean": None,
            "TP_DeltaMedian": None,
            "TP_Z": None,
            "LRA_DeltaMean": None,
            "LRA_DeltaMedian": None,
            "LRA_Z": None,
            "A_File": p["A_File"],
            "B_File": p["B_File"],
            "dLUFS": p["dLUFS"],
            "dTP": p["dTP"],
            "dMaxAbs": p["dMaxAbs"],
            "Similarite": p["Similarite"],
            "Error": None,
        })

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_rows)

    html_content = new_sound_report_html(folder, report, html_path)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return {"HtmlPath": html_path, "CsvPath": csv_path}


def new_sound_report_html(folder: str, report: dict, html_path: str) -> str:
    stats = report["Stats"]
    stats_json = json.dumps(stats, ensure_ascii=False)

    levels = ["Egal", "imperceptible", "leger", "moyen", "\u00e9lev\u00e9", "\u00e9norme"]
    level_counts = {l: 0 for l in levels}
    for p in report["Pairs"]:
        s = p["Similarite"]
        if s in level_counts:
            level_counts[s] += 1

    hist_lines = "\n".join(
        f"<div class='badge'><span class='tag {l}'>{l}</span>"
        f"<span class='small'>{level_counts[l]} paire(s)</span></div>"
        for l in levels
    )

    wp = report["Summary"]["WorstPair"]
    if wp:
        worst_txt = (
            f"{html_escape(wp['A_File'])} \u2194 {html_escape(wp['B_File'])} "
            f"(\u0394Max={format_num(wp['dMaxAbs'])})"
        )
    else:
        worst_txt = "N/A (moins de 2 fichiers mesurables)"

    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    scale_text = (
        "Egal &lt;0.10 | imperceptible &lt;0.50 | leger &lt;1.50 | "
        "moyen &lt;3.00 | \u00e9lev\u00e9 &lt;6.00 | \u00e9norme \u22656.00 "
        "(dB, sur max(|\u0394LUFS|,|\u0394TruePeak|))"
    )

    def th_help(label, tip):
        lab = html_escape(label)
        t = html_escape(tip)
        return f"<span class='thhelp' data-tip='{t}'>{lab} <span class='q'>?</span></span>"

    th_lufs = th_help("LUFS_I", "Loudness int\u00e9gr\u00e9e (LUFS, EBU R128). Plus proche de 0 = plus fort (moyenne per\u00e7ue).")
    th_tp   = th_help("TruePeak (dBTP)", "Pic vrai estim\u00e9 (intersample). \u26a0 Rouge si \u2265 0 dB = saturation num\u00e9rique !")
    th_lra  = th_help("LRA", "Loudness Range (dynamique). Plus grand = plus dynamique.")
    th_peak = th_help("Peak (dBFS)", "Pic entier brut (volumedetect). \u26a0 Rouge si \u2265 0 dB = saturation num\u00e9rique !")
    th_rms  = th_help("RMS (dBFS)", "Niveau RMS moyen (volumedetect). \u00c9quivalent puissance moyenne per\u00e7ue.")
    th_dmax = th_help("\u0394Max", "Distance paires: \u0394Max = max(|\u0394LUFS|, |\u0394TruePeak|).")
    th_sim  = th_help("Similarit\u00e9", "Cat\u00e9gories heuristiques sur \u0394Max.")

    # Metrics rows
    metrics_rows_parts = []
    for m in sorted(report["Metrics"], key=lambda x: x["FileName"]):
        err_txt = html_escape(m["Error"]) if m.get("Error") else ""
        status = ("<span class='tag Erreur'>Erreur</span>" if err_txt
                  else "<span class='tag Egal'>OK</span>")
        size_mb = f"{m['SizeBytes'] / (1024 * 1024):.2f}"

        if not err_txt:
            lufs = format_num(float(m["LUFS_I"]))
            tp   = format_num(float(m["TruePeak_dBTP"]))
            lra  = format_num(float(m["LRA"]))
            tp_clip  = " data-clipping='1'" if float(m["TruePeak_dBTP"]) >= 0 else ""
            lufs_cell = f"<span class='metricbox' data-metric='LUFS_I' data-value='{lufs}'>{lufs}</span>"
            tp_cell   = f"<span class='metricbox' data-metric='TruePeak_dBTP' data-value='{tp}'{tp_clip}>{tp}</span>"
            lra_cell  = f"<span class='metricbox' data-metric='LRA' data-value='{lra}'>{lra}</span>"

            raw_peak = m.get("Peak_dBFS")
            raw_rms  = m.get("RMS_dBFS")
            if raw_peak is not None:
                peak_str  = format_num(float(raw_peak))
                peak_clip = " data-clipping='1'" if float(raw_peak) >= 0 else ""
                peak_cell = f"<span class='metricbox' data-metric='Peak_dBFS' data-value='{peak_str}'{peak_clip}>{peak_str}</span>"
            else:
                peak_cell = "<span class='metricbox dim'>\u2014</span>"
            if raw_rms is not None:
                rms_str  = format_num(float(raw_rms))
                rms_cell = f"<span class='metricbox' data-metric='RMS_dBFS' data-value='{rms_str}'>{rms_str}</span>"
            else:
                rms_cell = "<span class='metricbox dim'>\u2014</span>"
        else:
            lufs_cell = "<span class='metricbox dim'>\u2014</span>"
            tp_cell   = "<span class='metricbox dim'>\u2014</span>"
            lra_cell  = "<span class='metricbox dim'>\u2014</span>"
            peak_cell = "<span class='metricbox dim'>\u2014</span>"
            rms_cell  = "<span class='metricbox dim'>\u2014</span>"

        metrics_rows_parts.append(
            f"<tr>\n"
            f"  <td>{html_escape(m['FileName'])}</td>\n"
            f"  <td>{html_escape(m['Ext'])}</td>\n"
            f"  <td class='num'>{size_mb}</td>\n"
            f"  <td class='num'>{lufs_cell}</td>\n"
            f"  <td class='num'>{tp_cell}</td>\n"
            f"  <td class='num'>{lra_cell}</td>\n"
            f"  <td class='num'>{peak_cell}</td>\n"
            f"  <td class='num'>{rms_cell}</td>\n"
            f"  <td>{status}</td>\n"
            f"  <td style='max-width:520px; color:#ffb2b2;'>{err_txt}</td>\n"
            f"</tr>"
        )
    metrics_rows = "\n".join(metrics_rows_parts)

    # Pairs rows
    pairs_rows_parts = []
    for p in sorted(report["Pairs"], key=lambda x: -x["dMaxAbs"]):
        sim_cls = p["Similarite"]
        pairs_rows_parts.append(
            f"<tr>\n"
            f"  <td>{html_escape(p['A_File'])}</td>\n"
            f"  <td>{html_escape(p['B_File'])}</td>\n"
            f"  <td class='num'>{format_num(p['A_LUFS_I'])}</td>\n"
            f"  <td class='num'>{format_num(p['B_LUFS_I'])}</td>\n"
            f"  <td class='num'>{format_num(p['dLUFS'])}</td>\n"
            f"  <td class='num'>{format_num(p['A_TP_dBTP'])}</td>\n"
            f"  <td class='num'>{format_num(p['B_TP_dBTP'])}</td>\n"
            f"  <td class='num'>{format_num(p['dTP'])}</td>\n"
            f"  <td class='num'>{format_num(p['dMaxAbs'])}</td>\n"
            f"  <td><span class='tag {sim_cls}'>{sim_cls}</span></td>\n"
            f"</tr>"
        )

    if pairs_rows_parts:
        pairs_rows = "\n".join(pairs_rows_parts)
    else:
        pairs_rows = "<tr><td colspan='10' class='small'>Pas assez de fichiers mesur\u00e9s pour faire des paires.</td></tr>"

    global_same_txt = "Oui" if report["Summary"]["GlobalSame"] else "Non"

    css = """\
<style>
:root{
  --bg:#0b1020; --text:#e7ecff; --muted:#aab3d6; --border:rgba(255,255,255,.10); --accent:#7aa2ff;
  --Egal:#1f8a3b; --imperceptible:#4aa334; --leger:#b38a00; --moyen:#d66a00; --\u00e9lev\u00e9:#d13939; --\u00e9norme:#a31f1f; --Erreur:#666;
}
*{box-sizing:border-box}
body{margin:0; font-family:Segoe UI, Arial, sans-serif; background:linear-gradient(180deg,var(--bg),#070b18); color:var(--text)}
.container{max-width:1280px; margin:0 auto; padding:22px}
.header{display:flex; gap:16px; align-items:flex-start; justify-content:space-between; margin-bottom:16px}
.h-title{font-size:20px; font-weight:700; margin:0}
.h-sub{color:var(--muted); margin-top:6px; line-height:1.35}
.kpis{display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin:16px 0}
.card{background:rgba(255,255,255,.04); border:1px solid var(--border); border-radius:14px; padding:12px 14px}
.kpi-title{color:var(--muted); font-size:12px; margin:0 0 6px 0}
.kpi-value{font-size:18px; font-weight:700; margin:0}
.section{margin-top:16px}
.section h2{font-size:14px; margin:0 0 10px 0; color:var(--muted); font-weight:700; letter-spacing:.02em; text-transform:uppercase}
.tablewrap{background:rgba(255,255,255,.03); border:1px solid var(--border); border-radius:14px; overflow:auto}
table{width:100%; border-collapse:collapse; font-size:12.5px; min-width:1050px}
thead th{position:sticky; top:0; background:rgba(10,15,30,.95); backdrop-filter: blur(6px); border-bottom:1px solid var(--border); padding:10px; text-align:left; color:#d8defb; z-index:1}
tbody td{border-top:1px solid rgba(255,255,255,.06); padding:9px 10px; vertical-align:top}
tbody tr:hover{background:rgba(255,255,255,.04)}
.num{font-variant-numeric:tabular-nums; text-align:right}
.badge{display:inline-flex; align-items:center; gap:8px; padding:6px 10px; border-radius:999px; border:1px solid var(--border); background:rgba(255,255,255,.04); font-weight:600; font-size:12px}
.dot{width:10px; height:10px; border-radius:99px; background:var(--accent)}
.tag{display:inline-block; padding:4px 10px; border-radius:999px; font-weight:700; color:#fff; font-size:12px}
.tag.Egal{background:var(--Egal)}
.tag.imperceptible{background:var(--imperceptible)}
.tag.leger{background:var(--leger)}
.tag.moyen{background:var(--moyen)}
.tag.\u00e9lev\u00e9{background:var(--\u00e9lev\u00e9)}
.tag.\u00e9norme{background:var(--\u00e9norme)}
.tag.Erreur{background:var(--Erreur)}
.small{color:var(--muted); font-size:12px}
.grid2{display:grid; grid-template-columns: 1.3fr .7fr; gap:10px}
hr{border:none; border-top:1px solid rgba(255,255,255,.10); margin:12px 0}
.controls{display:flex; gap:10px; flex-wrap:wrap; align-items:center}
select{
  background:#12193a; color:var(--text);
  border:1px solid var(--border); border-radius:10px; padding:8px 10px;
  outline:none;
}
select option{background:#12193a; color:var(--text);}
select:focus{border-color:rgba(122,162,255,.7)}
th.sortable{cursor:pointer; user-select:none; white-space:nowrap;}
th.sortable:hover{background:rgba(122,162,255,.12);}
.sort-ind{opacity:.35; font-size:11px; margin-left:4px;}
th.sortable[data-sort="asc"] .sort-ind,
th.sortable[data-sort="desc"] .sort-ind{opacity:1; color:var(--accent);}
.help{color:var(--muted); font-size:12px; line-height:1.4}
.metricbox{
  display:inline-block;
  min-width:88px;
  text-align:right;
  padding:5px 10px;
  border-radius:10px;
  border:1px solid rgba(255,255,255,.22);
  background:rgba(255,255,255,.05);
  box-shadow: inset 0 0 0 1px rgba(0,0,0,.20);
  font-weight:700;
}
.metricbox.dim{opacity:.55; font-weight:600}
.metricbox.clip-warn{
  background:rgba(220,40,40,.38) !important;
  border-color:rgba(255,70,70,.92) !important;
  color:#ffaaaa !important;
}
.thhelp{
  display:inline-flex; align-items:center; gap:6px;
  cursor:help;
  border-bottom:1px dotted rgba(216,222,251,.55);
}
.thhelp .q{
  width:16px; height:16px; border-radius:99px;
  display:inline-flex; align-items:center; justify-content:center;
  border:1px solid rgba(255,255,255,.20);
  color:rgba(231,236,255,.85);
  font-size:11px; font-weight:800;
  background:rgba(255,255,255,.06);
}
.tooltip{
  position:absolute;
  opacity:0;
  pointer-events:none;
  transform: translateY(6px);
  transition: opacity .10s ease, transform .10s ease;
  background:rgba(0,0,0,.82);
  color:#fff;
  border:1px solid rgba(255,255,255,.20);
  border-radius:10px;
  padding:8px 10px;
  max-width:380px;
  font-size:12px;
  line-height:1.35;
  z-index:9999;
}
.footer{margin-top:18px; color:var(--muted); font-size:12px}
</style>"""

    js = f"""\
<script>
(() => {{
  const stats = {stats_json};

  const tip = document.createElement('div');
  tip.className = 'tooltip';
  document.body.appendChild(tip);

  function clamp(x, a, b){{ return Math.min(b, Math.max(a, x)); }}

  const C_GREEN = {{r:46,  g:204, b:113}};
  const C_BLUE  = {{r:52,  g:152, b:219}};
  const C_RED   = {{r:231, g:76,  b:60}};

  function mix(a, b, t){{
    return {{
      r: Math.round(a.r + (b.r - a.r) * t),
      g: Math.round(a.g + (b.g - a.g) * t),
      b: Math.round(a.b + (b.b - a.b) * t),
    }};
  }}
  function rgbCss(c, alpha){{
    return 'rgba(' + c.r + ',' + c.g + ',' + c.b + ',' + alpha + ')';
  }}
  function colorForT(t){{
    t = clamp(t, -1, 1);
    const mag = Math.abs(t);
    const u = Math.pow(mag, 0.75);
    const base = (t < 0) ? mix(C_GREEN, C_BLUE, u) : mix(C_GREEN, C_RED, u);
    return {{ bg: rgbCss(base, 0.28), border: rgbCss(base, 0.82) }};
  }}

  function getRef(method, metric){{
    if (!stats[metric]) return 0;
    const v = (method === "median") ? stats[metric].median : stats[metric].mean;
    return (v != null) ? v : 0;
  }}
  function getScale(method, metric){{
    if (!stats[metric]) return 1;
    const s = stats[metric].std || 0;
    if (method === "zscore") return 2.0;
    const fallback = (metric === "LRA") ? 2.0 : 1.0;
    return Math.max(2.0 * s, fallback);
  }}
  function computeDelta(method, metric, value){{
    if (!stats[metric]) return 0;
    const ref = getRef(method, metric);
    const std = (stats[metric].std != null) ? stats[metric].std : 0;
    if (method === "zscore"){{
      if (std <= 1e-9) return 0.0;
      return (value - ref) / std;
    }}
    return (value - ref);
  }}

  function applyColors(){{
    const method = document.getElementById("refMode").value;
    document.querySelectorAll(".metricbox[data-metric][data-value]").forEach(el => {{
      const metric = el.getAttribute("data-metric");
      const value = parseFloat(el.getAttribute("data-value"));
      const delta = computeDelta(method, metric, value);
      const scale = getScale(method, metric);
      const t = clamp(delta / scale, -1, 1);
      const c = colorForT(t);

      el.style.backgroundColor = c.bg;
      el.style.borderColor = c.border;

      const ref = getRef(method, metric);
      const std = stats[metric].std || 0;
      let tipText;
      if (method === "zscore"){{
        tipText = metric + ': value=' + value.toFixed(2) + ', mean=' + ref.toFixed(2) + ', std=' + std.toFixed(2) + ', z=' + delta.toFixed(2);
      }} else {{
        const refLabel = (method === "median") ? "median" : "mean";
        tipText = metric + ': value=' + value.toFixed(2) + ', ' + refLabel + '=' + ref.toFixed(2) + ', \u0394=' + delta.toFixed(2) + ' dB';
      }}
      el.title = tipText;
    }});

    const legend = document.getElementById("modeLegend");
    if (method === "zscore"){{
      legend.textContent = "Couleurs (z-score): bleu=en dessous de la moyenne, vert=proche, rouge=au dessus (\u00e9chelle \u2248 \u00b12\u03c3).";
    }} else if (method === "median"){{
      legend.textContent = "Couleurs (\u0394 vs m\u00e9diane): bleu=en dessous, vert=proche, rouge=au dessus (\u00e9chelle \u2248 \u00b12\u00d7\u03c3, fallback si \u03c3\u22480).";
    }} else {{
      legend.textContent = "Couleurs (\u0394 vs moyenne): bleu=en dessous, vert=proche, rouge=au dessus (\u00e9chelle \u2248 \u00b12\u00d7\u03c3, fallback si \u03c3\u22480).";
    }}

    // Saturation absolue : rouge si >= 0 dB (priorité maximale, écrase la coloration relative)
    document.querySelectorAll(".metricbox[data-clipping='1']").forEach(el => {{
      el.classList.add("clip-warn");
      el.title += " \u26a0 SATURATION \u2265 0 dB !";
    }});
    document.querySelectorAll(".metricbox:not([data-clipping='1'])").forEach(el => {{
      el.classList.remove("clip-warn");
    }});
  }}

  function showTooltip(e, text){{
    tip.textContent = text;
    tip.style.opacity = "1";
    tip.style.transform = "translateY(0)";
    const pad = 12;
    const rect = tip.getBoundingClientRect();
    let x = e.clientX + pad;
    let y = e.clientY + pad;
    if (x + rect.width > window.innerWidth - 8) x = window.innerWidth - rect.width - 8;
    if (y + rect.height > window.innerHeight - 8) y = window.innerHeight - rect.height - 8;
    tip.style.left = x + "px";
    tip.style.top = y + "px";
  }}
  function hideTooltip(){{
    tip.style.opacity = "0";
    tip.style.transform = "translateY(6px)";
  }}

  function sortTable(table, col, dir) {{
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    rows.sort((a, b) => {{
      const aText = (a.cells[col]?.textContent || '').trim();
      const bText = (b.cells[col]?.textContent || '').trim();
      const aNum = parseFloat(aText.replace(',','.'));
      const bNum = parseFloat(bText.replace(',','.'));
      const isNum = !isNaN(aNum) && !isNaN(bNum) && aText !== '' && bText !== '';
      if (isNum) return dir === 'asc' ? aNum - bNum : bNum - aNum;
      return dir === 'asc' ? aText.localeCompare(bText, 'fr') : bText.localeCompare(aText, 'fr');
    }});
    rows.forEach(r => tbody.appendChild(r));
  }}

  document.addEventListener("DOMContentLoaded", () => {{
    document.querySelectorAll('th.sortable').forEach(th => {{
      th.addEventListener('click', () => {{
        const table = th.closest('table');
        const col = Array.from(th.parentElement.children).indexOf(th);
        const dir = th.dataset.sort === 'asc' ? 'desc' : 'asc';
        table.querySelectorAll('th.sortable').forEach(t => {{
          t.dataset.sort = '';
          const ind = t.querySelector('.sort-ind');
          if (ind) ind.textContent = '↕';
        }});
        th.dataset.sort = dir;
        const ind = th.querySelector('.sort-ind');
        if (ind) ind.textContent = dir === 'asc' ? '↑' : '↓';
        sortTable(table, col, dir);
      }});
    }});

    document.querySelectorAll(".thhelp[data-tip]").forEach(el => {{
      const text = el.getAttribute("data-tip");
      el.addEventListener("mousemove", (e) => showTooltip(e, text));
      el.addEventListener("mouseenter", (e) => showTooltip(e, text));
      el.addEventListener("mouseleave", hideTooltip);
    }});

    const sel = document.getElementById("refMode");
    sel.addEventListener("change", applyColors);
    applyColors();
  }});
}})();
</script>"""

    html_out = f"""\
<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sound report</title>
{css}
</head>
<body>
  <div class="container">
    <div class="header">
      <div>
        <div class="badge"><span class="dot"></span> Rapport audio</div>
        <h1 class="h-title">Comparatif niveau sonore (ffmpeg loudnorm)</h1>
        <div class="h-sub">
          <div><b>Dossier</b> : {html_escape(folder)}</div>
          <div><b>G\u00e9n\u00e9r\u00e9</b> : {generated}</div>
          <div><b>\u00c9chelle paires</b> : {scale_text}</div>
        </div>
      </div>
      <div class="badge">
        <span class="small">Globalement m\u00eame niveau :</span>
        <span style="font-size:13px; font-weight:800;">{global_same_txt}</span>
      </div>
    </div>

    <div class="kpis">
      <div class="card"><div class="kpi-title">Fichiers d\u00e9tect\u00e9s</div><div class="kpi-value">{report["Summary"]["FilesTotal"]}</div></div>
      <div class="card"><div class="kpi-title">Fichiers mesur\u00e9s (OK)</div><div class="kpi-value">{report["Summary"]["FilesOk"]}</div></div>
      <div class="card"><div class="kpi-title">Comparaisons (paires)</div><div class="kpi-value">{report["Summary"]["Pairs"]}</div></div>
      <div class="card"><div class="kpi-title">Pire paire (\u0394Max)</div><div class="kpi-value" style="font-size:13px">{worst_txt}</div></div>
    </div>

    <div class="section">
      <h2>M\u00e9triques par fichier</h2>
      <div class="card" style="margin-bottom:10px">
        <div class="controls">
          <div class="small"><b>Coloration:</b></div>
          <select id="refMode" aria-label="Mode de r\u00e9f\u00e9rence">
            <option value="median" selected>M\u00e9diane (\u0394)</option>
            <option value="mean">Moyenne (\u0394)</option>
            <option value="zscore">Z-score (\u03c3)</option>
          </select>
          <div class="help" id="modeLegend"></div>
        </div>
      </div>

      <div class="tablewrap">
        <table>
          <thead>
            <tr>
              <th class="sortable">Fichier <span class="sort-ind">↕</span></th>
              <th class="sortable">Type <span class="sort-ind">↕</span></th>
              <th class="num sortable">Taille (MB) <span class="sort-ind">↕</span></th>
              <th class="num sortable">{th_lufs} <span class="sort-ind">↕</span></th>
              <th class="num sortable">{th_tp} <span class="sort-ind">↕</span></th>
              <th class="num sortable">{th_lra} <span class="sort-ind">↕</span></th>
              <th class="num sortable">{th_peak} <span class="sort-ind">↕</span></th>
              <th class="num sortable">{th_rms} <span class="sort-ind">↕</span></th>
              <th class="sortable">Statut <span class="sort-ind">↕</span></th>
              <th>Erreur</th>
            </tr>
          </thead>
          <tbody>
            {metrics_rows}
          </tbody>
        </table>
      </div>
    </div>

    <div class="section">
      <h2>Comparaisons 2 par 2</h2>
      <div class="card" style="margin-bottom:10px">
        <div class="kpi-title">Distribution des diff\u00e9rences (paires)</div>
        <div style="display:flex; flex-wrap:wrap; gap:8px; margin-top:6px">
          {hist_lines}
        </div>
        <div class="small" style="margin-top:8px">
          Heuristique "globalement m\u00eame niveau" = max(\u0394Max) \u2264 1.5 dB ET \u226580% des paires \u2264 "leger".
        </div>
      </div>
      <div class="tablewrap">
        <table>
          <thead>
            <tr>
              <th class="sortable">Fichier A <span class="sort-ind">↕</span></th><th class="sortable">Fichier B <span class="sort-ind">↕</span></th>
              <th class="num sortable">LUFS A <span class="sort-ind">↕</span></th><th class="num sortable">LUFS B <span class="sort-ind">↕</span></th><th class="num sortable">\u0394LUFS (B-A) <span class="sort-ind">↕</span></th>
              <th class="num sortable">TP A <span class="sort-ind">↕</span></th><th class="num sortable">TP B <span class="sort-ind">↕</span></th><th class="num sortable">\u0394TP (B-A) <span class="sort-ind">↕</span></th>
              <th class="num sortable">{th_dmax} <span class="sort-ind">↕</span></th>
              <th class="sortable">{th_sim} <span class="sort-ind">↕</span></th>
            </tr>
          </thead>
          <tbody>
            {pairs_rows}
          </tbody>
        </table>
      </div>
    </div>

    <div class="footer">
      G\u00e9n\u00e9r\u00e9 par ffmpeg loudnorm (analyse) \u2022 {html_escape(html_path)}
    </div>
  </div>

{js}
</body>
</html>"""

    return html_out
