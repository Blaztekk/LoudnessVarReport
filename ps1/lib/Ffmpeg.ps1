### C:\Users\jeanf\Desktop\Fichiers pour Jean\SoundReport\lib\Ffmpeg.ps1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-LoudnessFromFile {
  param([Parameter(Mandatory)] [string]$Path)

  $ext = [IO.Path]::GetExtension($Path).ToLowerInvariant()
  $vn = @()
  if ($ext -in @(".mp4", ".m4v", ".mov", ".mkv")) { $vn = @("-vn") }

  # ffmpeg logs to stderr; capture all output
  $ffArgs = @("-hide_banner", "-nostats", "-i", $Path) + $vn + @(
    "-af", "loudnorm=print_format=json",
    "-f", "null",
    "-"
  )

  $out = & ffmpeg @ffArgs 2>&1 | Out-String
  $jsonMatches = [regex]::Matches($out, "\{[\s\S]*?\}")
  if ($jsonMatches.Count -lt 1) {
    throw "Pas de JSON loudnorm pour: $Path"
  }

  $j = ($jsonMatches[$jsonMatches.Count - 1].Value | ConvertFrom-Json)

  [pscustomobject]@{
    FileName      = [IO.Path]::GetFileName($Path)
    Path          = $Path
    Ext           = $ext.TrimStart(".")
    SizeBytes     = (Get-Item $Path).Length
    LUFS_I        = [double]$j.input_i
    TruePeak_dBTP = [double]$j.input_tp
    LRA           = [double]$j.input_lra
    Error         = $null
  }
}
