### C:\Users\jeanf\Desktop\Fichiers pour Jean\SoundReport\New-SoundReport.ps1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Relaunch in STA for WinForms dialogs
if ([Threading.Thread]::CurrentThread.ApartmentState -ne 'STA') {
  Write-Host "Relance en STA..." -ForegroundColor Yellow
  powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -File $PSCommandPath
  exit
}

$root = Split-Path -Parent $PSCommandPath
$lib = Join-Path $root "lib"

. (Join-Path $lib "Ui.ps1")
. (Join-Path $lib "Ffmpeg.ps1")
. (Join-Path $lib "Stats.ps1")
. (Join-Path $lib "Report.ps1")

if (-not (Test-CommandExists -Name "ffmpeg")) {
  throw "ffmpeg introuvable dans PATH."
}

$folder = Select-Folder
Write-Host "Dossier: $folder" -ForegroundColor Cyan

# Extensions supportées
$extensions = @("*.mp3", "*.mp4", "*.m4a", "*.wav", "*.flac", "*.ogg", "*.mkv", "*.mov", "*.m4v")
$files = foreach ($pat in $extensions) {
  Get-ChildItem -Path $folder -File -Filter $pat -ErrorAction SilentlyContinue
}
$files = $files | Sort-Object FullName -Unique
if ($null -eq $files -or $files.Count -eq 0) {
  throw "Aucun fichier supporté dans $folder"
}

Write-Host "Analyse loudness de $($files.Count) fichier(s)..." -ForegroundColor Cyan

$metrics = foreach ($f in $files) {
  Write-Host " - $($f.Name)"
  try {
    Get-LoudnessFromFile -Path $f.FullName
  } catch {
    [pscustomobject]@{
      FileName      = $f.Name
      Path          = $f.FullName
      Ext           = ([IO.Path]::GetExtension($f.Name).TrimStart("."))
      SizeBytes     = $f.Length
      LUFS_I        = $null
      TruePeak_dBTP = $null
      LRA           = $null
      Error         = $_.Exception.Message
    }
  }
}

$report = New-SoundReportData -Metrics $metrics
$out = Write-SoundReportOutputs -Folder $folder -Report $report

Write-Host "OK. Sorties générées :" -ForegroundColor Green
Write-Host " - HTML: $($out.HtmlPath)"
Write-Host " - CSV : $($out.CsvPath)"
