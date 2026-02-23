### C:\Users\jeanf\Desktop\Fichiers pour Jean\SoundReport\lib\Ui.ps1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Test-CommandExists {
  param([Parameter(Mandatory)] [string]$Name)
  [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Select-Folder {
  try {
    Add-Type -AssemblyName System.Windows.Forms | Out-Null

    $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
    $dialog.Description = "Choisis le dossier contenant les fichiers audio/vidéo"
    $dialog.ShowNewFolderButton = $false

    # Owner topmost to avoid the dialog being hidden behind the terminal
    $owner = New-Object System.Windows.Forms.Form
    $owner.TopMost = $true
    $owner.ShowInTaskbar = $false
    $owner.WindowState = 'Minimized'
    $owner.Opacity = 0
    $owner.Show()

    $result = $dialog.ShowDialog($owner)

    $owner.Close()
    $owner.Dispose()

    if ($result -eq [System.Windows.Forms.DialogResult]::OK -and -not [string]::IsNullOrWhiteSpace($dialog.SelectedPath)) {
      return $dialog.SelectedPath
    }
  } catch {
    # Fallback console input
  }

  Write-Host "UI indisponible. Saisis le chemin du dossier:" -ForegroundColor Yellow
  $p = Read-Host "Dossier"
  if ([string]::IsNullOrWhiteSpace($p)) { throw "Aucun dossier fourni." }
  if (-not (Test-Path $p)) { throw "Chemin invalide: $p" }
  (Resolve-Path $p).Path
}
