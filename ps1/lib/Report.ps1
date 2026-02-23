### C:\Users\jeanf\Desktop\Fichiers pour Jean\SoundReport\lib\Report.ps1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function New-SoundReportData {
  param(
    [Parameter(Mandatory)]
    [object[]]$Metrics
  )

    # Defensive: ensure $Metrics is always an array (foreach/return may yield a single object)
    if ($null -eq $Metrics) { $Metrics = @() } else { $Metrics = @($Metrics) }

  $ok = $Metrics | Where-Object { $null -ne $_.LUFS_I -and $null -ne $_.TruePeak_dBTP -and $null -ne $_.LRA }
  $err = $Metrics | Where-Object { $null -eq $_.LUFS_I -or  $null -eq $_.TruePeak_dBTP -or  $null -eq $_.LRA }

  # Ensure collections are arrays so `.Count` is available even for single-item results
  $ok  = @($ok)
  $err = @($err)

  if ($ok.Count -eq 0) {
    throw "Aucune mesure loudnorm exploitable (tous en erreur)."
  }

  $lufsVals = [double[]]($ok | ForEach-Object { $_.LUFS_I })
  $tpVals   = [double[]]($ok | ForEach-Object { $_.TruePeak_dBTP })
  $lraVals  = [double[]]($ok | ForEach-Object { $_.LRA })

  $stats = [pscustomobject]@{
    LUFS_I = [pscustomobject]@{
      mean = [double](($lufsVals | Measure-Object -Average).Average)
      median = [double](Get-Median -Values $lufsVals)
      std = [double](Get-StdDev -Values $lufsVals)
    }
    TruePeak_dBTP = [pscustomobject]@{
      mean = [double](($tpVals | Measure-Object -Average).Average)
      median = [double](Get-Median -Values $tpVals)
      std = [double](Get-StdDev -Values $tpVals)
    }
    LRA = [pscustomobject]@{
      mean = [double](($lraVals | Measure-Object -Average).Average)
      median = [double](Get-Median -Values $lraVals)
      std = [double](Get-StdDev -Values $lraVals)
    }
  }

  # Enrich file rows with deltas & z-scores (for the CSV)
  $filesEnriched = foreach ($m in $Metrics) {
    $isOk = ($null -ne $m.LUFS_I -and $null -ne $m.TruePeak_dBTP -and $null -ne $m.LRA)
    if (-not $isOk) {
      [pscustomobject]@{
        Section = "File"
        FileName = $m.FileName
        Ext = $m.Ext
        SizeBytes = $m.SizeBytes
        Path = $m.Path
        LUFS_I = $null
        TruePeak_dBTP = $null
        LRA = $null

        LUFS_DeltaMean = $null
        LUFS_DeltaMedian = $null
        LUFS_Z = $null

        TP_DeltaMean = $null
        TP_DeltaMedian = $null
        TP_Z = $null

        LRA_DeltaMean = $null
        LRA_DeltaMedian = $null
        LRA_Z = $null

        Error = $m.Error
      }
      continue
    }

    $lufs = [double]$m.LUFS_I
    $tp   = [double]$m.TruePeak_dBTP
    $lra  = [double]$m.LRA

    $lufsStd = [double]$stats.LUFS_I.std
    $tpStd   = [double]$stats.TruePeak_dBTP.std
    $lraStd  = [double]$stats.LRA.std

    $lufsZ = if ($lufsStd -gt 1e-9) { ($lufs - $stats.LUFS_I.mean) / $lufsStd } else { 0.0 }
    $tpZ   = if ($tpStd -gt 1e-9)   { ($tp   - $stats.TruePeak_dBTP.mean) / $tpStd } else { 0.0 }
    $lraZ  = if ($lraStd -gt 1e-9)  { ($lra  - $stats.LRA.mean) / $lraStd } else { 0.0 }

    [pscustomobject]@{
      Section = "File"
      FileName = $m.FileName
      Ext = $m.Ext
      SizeBytes = $m.SizeBytes
      Path = $m.Path
      LUFS_I = $lufs
      TruePeak_dBTP = $tp
      LRA = $lra

      LUFS_DeltaMean = ($lufs - $stats.LUFS_I.mean)
      LUFS_DeltaMedian = ($lufs - $stats.LUFS_I.median)
      LUFS_Z = $lufsZ

      TP_DeltaMean = ($tp - $stats.TruePeak_dBTP.mean)
      TP_DeltaMedian = ($tp - $stats.TruePeak_dBTP.median)
      TP_Z = $tpZ

      LRA_DeltaMean = ($lra - $stats.LRA.mean)
      LRA_DeltaMedian = ($lra - $stats.LRA.median)
      LRA_Z = $lraZ

      Error = $null
    }
  }

  # Pairwise comparisons (OK only)
  $pairs = New-Object System.Collections.Generic.List[object]
  for ($i = 0; $i -lt $ok.Count; $i++) {
    for ($j = $i + 1; $j -lt $ok.Count; $j++) {
      $a = $ok[$i]
      $b = $ok[$j]

      $dLUFS = [double]$b.LUFS_I - [double]$a.LUFS_I
      $dTP   = [double]$b.TruePeak_dBTP - [double]$a.TruePeak_dBTP
      $dMax  = [Math]::Max([Math]::Abs($dLUFS), [Math]::Abs($dTP))
      $cat   = Get-DiffCategory -DeltaLUFS $dLUFS -DeltaTP $dTP

      $pairs.Add([pscustomobject]@{
        Section = "Pair"
        A_File = $a.FileName
        B_File = $b.FileName
        A_Ext = $a.Ext
        B_Ext = $b.Ext
        A_LUFS_I = [double]$a.LUFS_I
        B_LUFS_I = [double]$b.LUFS_I
        dLUFS = $dLUFS
        A_TP_dBTP = [double]$a.TruePeak_dBTP
        B_TP_dBTP = [double]$b.TruePeak_dBTP
        dTP = $dTP
        dMaxAbs = $dMax
        Similarite = $cat
      }) | Out-Null
    }
  }

  # Global “same level” heuristic on pairs
  $levels = @("Egal", "imperceptible", "leger", "moyen", "élevé", "énorme")
  function Get-LevelIndexLocal([string]$s) {
    $ix = $levels.IndexOf($s)
    if ($ix -lt 0) { 999 } else { $ix }
  }

  $ratioLegerOrLess = 1.0
  $maxPair = $null
  $meanDelta = 0.0

  if ($pairs.Count -gt 0) {
    $ratioLegerOrLess = ($pairs | Where-Object { (Get-LevelIndexLocal $_.Similarite) -le (Get-LevelIndexLocal "leger") }).Count / [double]$pairs.Count
    $maxPair = $pairs | Sort-Object dMaxAbs -Descending | Select-Object -First 1
    $meanDelta = [double](($pairs | Measure-Object -Property dMaxAbs -Average).Average)
  }

  $globalSame = ($pairs.Count -le 0) -or ((($null -ne $maxPair) -and ($maxPair.dMaxAbs -le 1.5)) -and ($ratioLegerOrLess -ge 0.80))

  [pscustomobject]@{
    Metrics = $Metrics
    FilesOk = $ok
    FilesErr = $err
    Stats = $stats
    FilesEnriched = $filesEnriched
    Pairs = $pairs
    Summary = [pscustomobject]@{
      FilesTotal = $Metrics.Count
      FilesOk = $ok.Count
      FilesErr = $err.Count
      Pairs = $pairs.Count
      RatioLegerOrLess = $ratioLegerOrLess
      MeanDelta = $meanDelta
      MaxDelta = if ($null -ne $maxPair) { [double]$maxPair.dMaxAbs } else { $null }
      WorstPair = $maxPair
      GlobalSame = $globalSame
    }
  }
}

function Write-SoundReportOutputs {
  param(
    [Parameter(Mandatory)][string]$Folder,
    [Parameter(Mandatory)][pscustomobject]$Report
  )

  $ts = Get-Date -Format "yyyyMMdd_HHmmss"
  $htmlPath = Join-Path $Folder "sound_report_$ts.html"
  $csvPath  = Join-Path $Folder "sound_report_$ts.csv"

  # CSV brut: un seul fichier, 2 sections (File / Pair)
  $fileRows = $Report.FilesEnriched
  $pairRows = $Report.Pairs

  # Normalise rows into a superset schema for a single CSV
  $csvRows = New-Object System.Collections.Generic.List[object]

  foreach ($r in $fileRows) {
    $csvRows.Add([pscustomobject]@{
      Section = "File"
      FileName = $r.FileName
      Ext = $r.Ext
      SizeBytes = $r.SizeBytes
      Path = $r.Path

      LUFS_I = $r.LUFS_I
      TruePeak_dBTP = $r.TruePeak_dBTP
      LRA = $r.LRA

      LUFS_DeltaMean = $r.LUFS_DeltaMean
      LUFS_DeltaMedian = $r.LUFS_DeltaMedian
      LUFS_Z = $r.LUFS_Z

      TP_DeltaMean = $r.TP_DeltaMean
      TP_DeltaMedian = $r.TP_DeltaMedian
      TP_Z = $r.TP_Z

      LRA_DeltaMean = $r.LRA_DeltaMean
      LRA_DeltaMedian = $r.LRA_DeltaMedian
      LRA_Z = $r.LRA_Z

      A_File = $null
      B_File = $null
      dLUFS = $null
      dTP = $null
      dMaxAbs = $null
      Similarite = $null

      Error = $r.Error
    }) | Out-Null
  }

  foreach ($p in $pairRows) {
    $csvRows.Add([pscustomobject]@{
      Section = "Pair"
      FileName = $null
      Ext = $null
      SizeBytes = $null
      Path = $null

      LUFS_I = $null
      TruePeak_dBTP = $null
      LRA = $null

      LUFS_DeltaMean = $null
      LUFS_DeltaMedian = $null
      LUFS_Z = $null

      TP_DeltaMean = $null
      TP_DeltaMedian = $null
      TP_Z = $null

      LRA_DeltaMean = $null
      LRA_DeltaMedian = $null
      LRA_Z = $null

      A_File = $p.A_File
      B_File = $p.B_File
      dLUFS = $p.dLUFS
      dTP = $p.dTP
      dMaxAbs = $p.dMaxAbs
      Similarite = $p.Similarite

      Error = $null
    }) | Out-Null
  }

  $csvRows | Export-Csv -NoTypeInformation -Encoding UTF8 -Path $csvPath

  # HTML (joli) : construit depuis Stats + tables
  $html = New-SoundReportHtml -Folder $Folder -Report $Report -HtmlPath $htmlPath
  Set-Content -Path $htmlPath -Value $html -Encoding UTF8

  [pscustomobject]@{ HtmlPath = $htmlPath; CsvPath = $csvPath }
}

function New-SoundReportHtml {
  param(
    [Parameter(Mandatory)][string]$Folder,
    [Parameter(Mandatory)][pscustomobject]$Report,
    [Parameter(Mandatory)][string]$HtmlPath
  )

  $statsJson = ($Report.Stats | ConvertTo-Json -Depth 6)

  $levels = @("Egal", "imperceptible", "leger", "moyen", "élevé", "énorme")
  $levelCounts = @{}
  foreach ($l in $levels) { $levelCounts[$l] = 0 }
  foreach ($p in $Report.Pairs) { $levelCounts[$p.Similarite]++ }

  $histLines = foreach ($l in $levels) {
    $c = $levelCounts[$l]
    "<div class='badge'><span class='tag $l'>$l</span><span class='small'>$c paire(s)</span></div>"
  }

  $worstTxt = if ($null -ne $Report.Summary.WorstPair) {
    "$(ConvertTo-HtmlEscaped $Report.Summary.WorstPair.A_File) ↔ $(ConvertTo-HtmlEscaped $Report.Summary.WorstPair.B_File) (ΔMax=$(Format-Num $Report.Summary.WorstPair.dMaxAbs))"
  } else {
    "N/A (moins de 2 fichiers mesurables)"
  }

  $generated = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
  $scaleText = "Egal <0.10 | imperceptible <0.50 | leger <1.50 | moyen <3.00 | élevé <6.00 | énorme ≥6.00 (dB, sur max(|ΔLUFS|,|ΔTruePeak|))"

  function New-ThHelpHtmlLocal {
    param([Parameter(Mandatory)][string]$Label, [Parameter(Mandatory)][string]$Tip)
    $lab = ConvertTo-HtmlEscaped $Label
    $t = ConvertTo-HtmlEscaped $Tip
    "<span class='thhelp' data-tip='$t'>$lab <span class='q'>?</span></span>"
  }

  $thLUFS = New-ThHelpHtmlLocal -Label "LUFS_I" -Tip "Loudness intégrée (LUFS, EBU R128). Plus proche de 0 = plus fort (moyenne perçue)."
  $thTP   = New-ThHelpHtmlLocal -Label "TruePeak (dBTP)" -Tip "Pic vrai estimé (intersample). Plus proche de 0 = plus de risque de clipping."
  $thLRA  = New-ThHelpHtmlLocal -Label "LRA" -Tip "Loudness Range (dynamique). Plus grand = plus dynamique."
  $thDMax = New-ThHelpHtmlLocal -Label "ΔMax" -Tip "Distance paires: ΔMax = max(|ΔLUFS|, |ΔTruePeak|)."
  $thSim  = New-ThHelpHtmlLocal -Label "Similarité" -Tip "Catégories heuristiques sur ΔMax."

  # Metrics table rows (colored chips with tooltips)
  $metricsRows = foreach ($m in ($Report.Metrics | Sort-Object FileName)) {
    $errTxt = if (($m.PSObject.Properties.Name -contains "Error") -and $m.Error) { ConvertTo-HtmlEscaped $m.Error } else { "" }
    $status = if ($errTxt) { "<span class='tag Erreur'>Erreur</span>" } else { "<span class='tag Egal'>OK</span>" }
    $sizeMb = [Math]::Round(($m.SizeBytes / 1MB), 2).ToString([System.Globalization.CultureInfo]::InvariantCulture)

    if (-not $errTxt) {
      $lufs = Format-Num ([double]$m.LUFS_I)
      $tp   = Format-Num ([double]$m.TruePeak_dBTP)
      $lra  = Format-Num ([double]$m.LRA)

      $lufsCell = "<span class='metricbox' data-metric='LUFS_I' data-value='$lufs'>$lufs</span>"
      $tpCell   = "<span class='metricbox' data-metric='TruePeak_dBTP' data-value='$tp'>$tp</span>"
      $lraCell  = "<span class='metricbox' data-metric='LRA' data-value='$lra'>$lra</span>"
    } else {
      $lufsCell = "<span class='metricbox dim'>—</span>"
      $tpCell   = "<span class='metricbox dim'>—</span>"
      $lraCell  = "<span class='metricbox dim'>—</span>"
    }

    "<tr>
      <td>$(ConvertTo-HtmlEscaped $m.FileName)</td>
      <td>$(ConvertTo-HtmlEscaped $m.Ext)</td>
      <td class='num'>$sizeMb</td>
      <td class='num'>$lufsCell</td>
      <td class='num'>$tpCell</td>
      <td class='num'>$lraCell</td>
      <td>$status</td>
      <td style='max-width:520px; word-break:break-all;'>$(ConvertTo-HtmlEscaped $m.Path)</td>
      <td style='max-width:520px; color:#ffb2b2;'>$errTxt</td>
    </tr>"
  }

  $pairsRows = foreach ($p in ($Report.Pairs | Sort-Object dMaxAbs -Descending)) {
    "<tr>
      <td>$(ConvertTo-HtmlEscaped $p.A_File)</td>
      <td>$(ConvertTo-HtmlEscaped $p.B_File)</td>
      <td class='num'>$(Format-Num $p.A_LUFS_I)</td>
      <td class='num'>$(Format-Num $p.B_LUFS_I)</td>
      <td class='num'>$(Format-Num $p.dLUFS)</td>
      <td class='num'>$(Format-Num $p.A_TP_dBTP)</td>
      <td class='num'>$(Format-Num $p.B_TP_dBTP)</td>
      <td class='num'>$(Format-Num $p.dTP)</td>
      <td class='num'>$(Format-Num $p.dMaxAbs)</td>
      <td><span class='tag $($p.Similarite)'>$($p.Similarite)</span></td>
    </tr>"
  }

  $css = @"
<style>
:root{
  --bg:#0b1020; --text:#e7ecff; --muted:#aab3d6; --border:rgba(255,255,255,.10); --accent:#7aa2ff;
  --Egal:#1f8a3b; --imperceptible:#4aa334; --leger:#b38a00; --moyen:#d66a00; --élevé:#d13939; --énorme:#a31f1f; --Erreur:#666;
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
.tag.élevé{background:var(--élevé)}
.tag.énorme{background:var(--énorme)}
.tag.Erreur{background:var(--Erreur)}
.small{color:var(--muted); font-size:12px}
.grid2{display:grid; grid-template-columns: 1.3fr .7fr; gap:10px}
hr{border:none; border-top:1px solid rgba(255,255,255,.10); margin:12px 0}

.controls{display:flex; gap:10px; flex-wrap:wrap; align-items:center}
select{
  background:rgba(255,255,255,.05); color:var(--text);
  border:1px solid var(--border); border-radius:10px; padding:8px 10px;
  outline:none;
}
select:focus{border-color:rgba(122,162,255,.7)}
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
</style>
"@

  $js = @"
<script>
(() => {
  const stats = $statsJson;

  const tip = document.createElement('div');
  tip.className = 'tooltip';
  document.body.appendChild(tip);

  function clamp(x, a, b){ return Math.min(b, Math.max(a, x)); }

  // Diverging palette without yellow:
  const C_GREEN = {r:46,  g:204, b:113};
  const C_BLUE  = {r:52,  g:152, b:219};
  const C_RED   = {r:231, g:76,  b:60};

  function mix(a, b, t){
    return {
      r: Math.round(a.r + (b.r - a.r) * t),
      g: Math.round(a.g + (b.g - a.g) * t),
      b: Math.round(a.b + (b.b - a.b) * t),
    };
  }
  function rgbCss(c, alpha){
    return 'rgba(' + c.r + ',' + c.g + ',' + c.b + ',' + alpha + ')';
  }
  function colorForT(t){
    t = clamp(t, -1, 1);
    const mag = Math.abs(t);
    const u = Math.pow(mag, 0.75);
    const base = (t < 0) ? mix(C_GREEN, C_BLUE, u) : mix(C_GREEN, C_RED, u);
    return { bg: rgbCss(base, 0.28), border: rgbCss(base, 0.82) };
  }

  function getRef(method, metric){
    if (method === "median") return stats[metric].median;
    return stats[metric].mean;
  }
  function getScale(method, metric){
    const s = stats[metric].std || 0;
    if (method === "zscore") return 2.0;
    const fallback = (metric === "LRA") ? 2.0 : 1.0;
    return Math.max(2.0 * s, fallback);
  }
  function computeDelta(method, metric, value){
    const ref = getRef(method, metric);
    const std = stats[metric].std || 0;
    if (method === "zscore"){
      if (std <= 1e-9) return 0.0;
      return (value - ref) / std;
    }
    return (value - ref);
  }

  function applyColors(){
    const method = document.getElementById("refMode").value;
    document.querySelectorAll(".metricbox[data-metric][data-value]").forEach(el => {
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
      if (method === "zscore"){
        tipText = metric + ': value=' + value.toFixed(2) + ', mean=' + ref.toFixed(2) + ', std=' + std.toFixed(2) + ', z=' + delta.toFixed(2);
      } else {
        const refLabel = (method === "median") ? "median" : "mean";
        tipText = metric + ': value=' + value.toFixed(2) + ', ' + refLabel + '=' + ref.toFixed(2) + ', Δ=' + delta.toFixed(2) + ' dB';
      }
      el.title = tipText;
    });

    const legend = document.getElementById("modeLegend");
    if (method === "zscore"){
      legend.textContent = "Couleurs (z-score): bleu=en dessous de la moyenne, vert=proche, rouge=au dessus (échelle ≈ ±2σ).";
    } else if (method === "median"){
      legend.textContent = "Couleurs (Δ vs médiane): bleu=en dessous, vert=proche, rouge=au dessus (échelle ≈ ±2×σ, fallback si σ≈0).";
    } else {
      legend.textContent = "Couleurs (Δ vs moyenne): bleu=en dessous, vert=proche, rouge=au dessus (échelle ≈ ±2×σ, fallback si σ≈0).";
    }
  }

  function showTooltip(e, text){
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
  }
  function hideTooltip(){
    tip.style.opacity = "0";
    tip.style.transform = "translateY(6px)";
  }

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".thhelp[data-tip]").forEach(el => {
      const text = el.getAttribute("data-tip");
      el.addEventListener("mousemove", (e) => showTooltip(e, text));
      el.addEventListener("mouseenter", (e) => showTooltip(e, text));
      el.addEventListener("mouseleave", hideTooltip);
    });

    const sel = document.getElementById("refMode");
    sel.addEventListener("change", applyColors);
    applyColors();
  });
})();
</script>
"@

  @"
<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sound report</title>
$css
</head>
<body>
  <div class="container">
    <div class="header">
      <div>
        <div class="badge"><span class="dot"></span> Rapport audio</div>
        <h1 class="h-title">Comparatif niveau sonore (ffmpeg loudnorm)</h1>
        <div class="h-sub">
          <div><b>Dossier</b> : $(ConvertTo-HtmlEscaped $Folder)</div>
          <div><b>Généré</b> : $generated</div>
          <div><b>Échelle paires</b> : $scaleText</div>
        </div>
      </div>
      <div class="badge">
        <span class="small">Globalement même niveau :</span>
        <span style="font-size:13px; font-weight:800;">$(if ($Report.Summary.GlobalSame) { "Oui" } else { "Non" })</span>
      </div>
    </div>

    <div class="kpis">
      <div class="card"><div class="kpi-title">Fichiers détectés</div><div class="kpi-value">$($Report.Summary.FilesTotal)</div></div>
      <div class="card"><div class="kpi-title">Fichiers mesurés (OK)</div><div class="kpi-value">$($Report.Summary.FilesOk)</div></div>
      <div class="card"><div class="kpi-title">Comparaisons (paires)</div><div class="kpi-value">$($Report.Summary.Pairs)</div></div>
      <div class="card"><div class="kpi-title">Pire paire (ΔMax)</div><div class="kpi-value" style="font-size:13px">$worstTxt</div></div>
    </div>

    <div class="section">
      <div class="card">
        <div class="kpi-title">Distribution des différences (paires)</div>
        <div style="display:flex; flex-wrap:wrap; gap:8px; margin-top:6px">
          $($histLines -join "`n")
        </div>
        <div class="small" style="margin-top:8px">
          Heuristique "globalement même niveau" = max(ΔMax) ≤ 1.5 dB ET ≥80% des paires ≤ "leger".
        </div>
      </div>
    </div>

    <div class="section">
      <h2>Métriques par fichier</h2>
      <div class="card" style="margin-bottom:10px">
        <div class="controls">
          <div class="small"><b>Coloration:</b></div>
          <select id="refMode" aria-label="Mode de référence">
            <option value="median" selected>Médiane (Δ)</option>
            <option value="mean">Moyenne (Δ)</option>
            <option value="zscore">Z-score (σ)</option>
          </select>
          <div class="help" id="modeLegend"></div>
        </div>
      </div>

      <div class="tablewrap">
        <table>
          <thead>
            <tr>
              <th>Fichier</th>
              <th>Type</th>
              <th class="num">Taille (MB)</th>
              <th class="num">$thLUFS</th>
              <th class="num">$thTP</th>
              <th class="num">$thLRA</th>
              <th>Statut</th>
              <th>Chemin</th>
              <th>Erreur</th>
            </tr>
          </thead>
          <tbody>
            $($metricsRows -join "`n")
          </tbody>
        </table>
      </div>
    </div>

    <div class="section">
      <h2>Comparaisons 2 par 2</h2>
      <div class="tablewrap">
        <table>
          <thead>
            <tr>
              <th>Fichier A</th><th>Fichier B</th>
              <th class="num">LUFS A</th><th class="num">LUFS B</th><th class="num">ΔLUFS (B-A)</th>
              <th class="num">TP A</th><th class="num">TP B</th><th class="num">ΔTP (B-A)</th>
              <th class="num">$thDMax</th>
              <th>$thSim</th>
            </tr>
          </thead>
          <tbody>
            $(if ($Report.Pairs.Count -gt 0) { $pairsRows -join "`n" } else { "<tr><td colspan='10' class='small'>Pas assez de fichiers mesurés pour faire des paires.</td></tr>" })
          </tbody>
        </table>
      </div>
    </div>

    <div class="footer">
      Généré par ffmpeg loudnorm (analyse) • $(ConvertTo-HtmlEscaped $HtmlPath)
    </div>
  </div>

$js
</body>
</html>
"@
}
