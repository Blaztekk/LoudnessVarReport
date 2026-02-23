### C:\Users\jeanf\Desktop\Fichiers pour Jean\SoundReport\lib\Stats.ps1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-Median {
  param([Parameter(Mandatory)][double[]]$Values)
  $sorted = $Values | Sort-Object
  $n = $sorted.Count
  if ($n -eq 0) { return $null }
  if ($n % 2 -eq 1) { return $sorted[[int]($n / 2)] }
  return ($sorted[($n / 2) - 1] + $sorted[$n / 2]) / 2.0
}

function Get-StdDev {
  param([Parameter(Mandatory)][double[]]$Values)
  $n = $Values.Count
  if ($n -lt 2) { return 0.0 }
  $mean = ($Values | Measure-Object -Average).Average
  $sum = 0.0
  foreach ($x in $Values) {
    $d = $x - $mean
    $sum += ($d * $d)
  }
  # sample stddev
  [Math]::Sqrt($sum / ($n - 1))
}

function Get-DiffCategory {
  param(
    [Parameter(Mandatory)][double]$DeltaLUFS,
    [Parameter(Mandatory)][double]$DeltaTP
  )
  $d = [Math]::Max([Math]::Abs($DeltaLUFS), [Math]::Abs($DeltaTP))
  if     ($d -lt 0.10) { "Egal" }
  elseif ($d -lt 0.50) { "imperceptible" }
  elseif ($d -lt 1.50) { "leger" }
  elseif ($d -lt 3.00) { "moyen" }
  elseif ($d -lt 6.00) { "élevé" }
  else                 { "énorme" }
}

function ConvertTo-HtmlEscaped {
  param([Parameter(Mandatory)][string]$s)
  [System.Net.WebUtility]::HtmlEncode($s)
}

function Format-Num {
  param(
    [Parameter(Mandatory)][double]$v,
    [int]$digits = 2
  )
  [Math]::Round($v, $digits).ToString("0." + ("0" * $digits), [System.Globalization.CultureInfo]::InvariantCulture)
}
