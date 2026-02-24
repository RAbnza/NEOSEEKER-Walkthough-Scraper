[CmdletBinding()]
param(
  [string]$DefaultStartUrl = "https://www.neoseeker.com/the-legend-of-heroes-trails-in-the-sky-the-1st/Prologue",
  [string]$DefaultOutputPdf = "output/trails-in-the-sky-1st.pdf",
  [int]$DefaultMaxPages = 400,
  [double]$DefaultDelaySeconds = 1.0,
  [int]$DefaultCdpPort = 9222,
  [string]$PythonExe = "",
  [switch]$Diagnostics
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-RepoRoot {
  # scripts/ is one level below repo root
  return (Resolve-Path (Join-Path $PSScriptRoot ".."))
}

function Resolve-Python {
  param([string]$Preferred)

  if ($Preferred -and (Test-Path $Preferred)) {
    return $Preferred
  }

  $cmd = Get-Command python -ErrorAction SilentlyContinue
  if ($cmd) {
    return $cmd.Source
  }

  $cmd = Get-Command py -ErrorAction SilentlyContinue
  if ($cmd) {
    return $cmd.Source
  }

  return $null
}

function Pause-User {
  param([string]$Message = "Press Enter to continue")
  [void](Read-Host $Message)
}

function Format-YesNo {
  param([bool]$Value)
  if ($Value) { return "YES" }
  return "NO"
}

function Write-Divider {
  param(
    [string]$Char = "=",
    [int]$Width = 72,
    [ConsoleColor]$Color = [ConsoleColor]::DarkGray
  )
  $line = ($Char * $Width)
  Write-Host $line -ForegroundColor $Color
}

function Kill-Chrome {
  Write-Host "Stopping all Chrome processes..." -ForegroundColor Yellow
  Get-Process chrome -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
  Start-Sleep -Seconds 1
  $count = @(Get-Process chrome -ErrorAction SilentlyContinue).Count
  Write-Host "Chrome processes remaining: $count"
}

function Start-ChromeCdp {
  param(
    [int]$Port,
    [string]$ProfileDir
  )

  $chromeExe = "C:\Program Files\Google\Chrome\Application\chrome.exe"
  if (-not (Test-Path $chromeExe)) {
    $chromeExe = "$env:ProgramFiles(x86)\Google\Chrome\Application\chrome.exe"
  }

  if (-not (Test-Path $chromeExe)) {
    throw "Chrome.exe not found in Program Files. Install Google Chrome or update the path in this script."
  }

  New-Item -ItemType Directory -Path $ProfileDir -Force | Out-Null
  Write-Host "Starting Chrome with CDP on port $Port" -ForegroundColor Green
  Write-Host "Profile dir: $ProfileDir"

  Start-Process -FilePath $chromeExe -ArgumentList @("--remote-debugging-port=$Port", "--user-data-dir=$ProfileDir") | Out-Null
  Start-Sleep -Seconds 2
}

function Find-ChromeExe {
  $chromeExe = "C:\Program Files\Google\Chrome\Application\chrome.exe"
  if (Test-Path $chromeExe) { return $chromeExe }
  $chromeExe = "$env:ProgramFiles(x86)\Google\Chrome\Application\chrome.exe"
  if (Test-Path $chromeExe) { return $chromeExe }
  return $null
}

function Test-Cdp {
  param([int]$Port)

  $url = "http://127.0.0.1:$Port/json/version"
  try {
    $resp = Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 5
    Write-Host "CDP OK: $url" -ForegroundColor Green
    return $true
  } catch {
    Write-Host "CDP NOT reachable: $url" -ForegroundColor Red
    Write-Host $_.Exception.Message
    return $false
  }
}

function Test-CdpQuiet {
  param([int]$Port)

  $url = "http://127.0.0.1:$Port/json/version"
  try {
    [void](Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 2)
    return $true
  } catch {
    return $false
  }
}

function Get-ChromeRunning {
  return (@(Get-Process chrome -ErrorAction SilentlyContinue).Count -gt 0)
}

function Run-Scraper {
  param(
    [string]$Python,
    [int]$Port,
    [string]$StartUrl,
    [string]$OutputPdf,
    [int]$MaxPages,
    [double]$DelaySeconds,
    [switch]$OfflineAssets
  )

  if (-not $Python) {
    throw "Python is not configured. Use option 6 (Edit settings) to set a Python path, or pass -PythonExe <path> when starting the menu."
  }

  $repoRoot = Get-RepoRoot
  $cdpUrl = "http://127.0.0.1:$Port"

  Write-Host "Running scraper..." -ForegroundColor Green
  Write-Host "CDP: $cdpUrl"
  Write-Host "Start: $StartUrl"
  Write-Host "Output: $OutputPdf"

  Push-Location $repoRoot
  try {
    $args = @(
      "-m", "walkthrough_scraper",
      "--cdp-url", $cdpUrl,
      "--start", $StartUrl,
      "--output", $OutputPdf,
      "--max-pages", "$MaxPages",
      "--delay", "$DelaySeconds"
    )

    if ($OfflineAssets) {
      $args += "--offline-assets"
    }

    & $Python @args
    return $LASTEXITCODE

  } finally {
    Pop-Location
  }
}

function Show-Menu {
  param(
    [int]$Port,
    [string]$ProfileDir,
    [string]$Python,
    [string]$StartUrl,
    [string]$OutputPdf,
    [int]$MaxPages,
    [double]$DelaySeconds,
    [bool]$OfflineAssets
  )

  try { Clear-Host } catch { }

  Write-Divider -Char "="
  Write-Host "WALKTHROUGH SCRAPER" -ForegroundColor Cyan
  Write-Host "made by Rendel Abainza" -ForegroundColor DarkGray
  Write-Divider -Char "="
  Write-Host ""

  $cdpOk = Test-CdpQuiet -Port $Port
  $chromeRunning = Get-ChromeRunning
  $cdpStatus = if ($cdpOk) { "OK" } else { "NOT REACHABLE" }
  $cdpColor = if ($cdpOk) { "Green" } else { "Red" }
  $chromeStatus = if ($chromeRunning) { "RUNNING" } else { "NOT RUNNING" }
  $chromeColor = if ($chromeRunning) { "Green" } else { "DarkGray" }

  Write-Host "STATUS" -ForegroundColor Cyan
  Write-Divider -Char "-"
  Write-Host ("CDP endpoint   : {0}" -f $cdpStatus) -ForegroundColor $cdpColor
  Write-Host ("Chrome         : {0}" -f $chromeStatus) -ForegroundColor $chromeColor
  Write-Host ""

  Write-Host "SETTINGS" -ForegroundColor Cyan
  Write-Divider -Char "-"
  if ($Python) {
    Write-Host ("Python         : {0}" -f $Python)
  } else {
    Write-Host "Python         : (NOT FOUND)" -ForegroundColor Yellow
    Write-Host "                 Use option 6, or pass -PythonExe <path> when launching the menu." -ForegroundColor Yellow
  }
  Write-Host ("CDP port       : {0}" -f $Port)
  Write-Host ("Profile dir    : {0}" -f $ProfileDir)
  Write-Host ("Start URL      : {0}" -f $StartUrl)
  Write-Host ("Output PDF     : {0}" -f $OutputPdf)
  Write-Host ("Max pages      : {0}" -f $MaxPages)
  Write-Host ("Delay (seconds): {0}" -f $DelaySeconds)
  Write-Host ("Offline assets : {0}" -f (Format-YesNo -Value $OfflineAssets))

  Write-Host ""
  Write-Host "MENU" -ForegroundColor Cyan
  Write-Divider -Char "-"
  Write-Host "  [1] Kill all Chrome processes"
  Write-Host "  [2] Start Chrome with CDP"
  Write-Host "  [3] Test CDP endpoint"
  Write-Host "  [4] Run scraper"
  Write-Host "  [5] Open output folder"
  Write-Host "  [6] Edit settings"
  Write-Host "  [0] Exit"
  Write-Host ""
}

# Main
$repoRoot = Get-RepoRoot
$resolvedPython = Resolve-Python -Preferred $PythonExe

$port = $DefaultCdpPort
$profileDir = Join-Path $env:TEMP "chrome-cdp-profile"
$startUrl = $DefaultStartUrl
$outputPdf = $DefaultOutputPdf
$maxPages = $DefaultMaxPages
$delaySeconds = $DefaultDelaySeconds
$offlineAssets = $true

if ($Diagnostics) {
  Write-Host "walkthrough-scraper diagnostics" -ForegroundColor Cyan
  Write-Host "Repo root: $repoRoot"
  Write-Host "Preferred PythonExe: $PythonExe"
  Write-Host "Preferred PythonExe exists: $(Test-Path $PythonExe)"
  Write-Host "Resolved Python: $resolvedPython"
  Write-Host "Python on PATH: $([bool](Get-Command python -ErrorAction SilentlyContinue))"
  Write-Host "py launcher present: $([bool](Get-Command py -ErrorAction SilentlyContinue))"
  $chromeExe = Find-ChromeExe
  Write-Host "Chrome exe: $chromeExe"
  Write-Host "CDP check URL: http://127.0.0.1:$port/json/version"
  Write-Host "Output PDF: $outputPdf"
  if (-not $chromeExe) {
    Write-Error "Chrome.exe not found. Install Google Chrome or update the path in scripts/walkthrough_menu.ps1."
    exit 1
  }
  if (-not $resolvedPython) {
    Write-Error "Python not found. Install Python 3.12+ or pass -PythonExe <path>."
    exit 1
  }
  Write-Host "OK" -ForegroundColor Green
  exit 0
}

# If Python couldn't be resolved, still allow using the menu for Chrome/CDP steps.
if (-not $resolvedPython) {
  Write-Host "Warning: Python not found. You can still start/test CDP, but option 4 (Run scraper) will fail until Python is configured." -ForegroundColor Yellow
}

:MainLoop while ($true) {
  Show-Menu -Port $port -ProfileDir $profileDir -Python $resolvedPython -StartUrl $startUrl -OutputPdf $outputPdf -MaxPages $maxPages -DelaySeconds $delaySeconds -OfflineAssets $offlineAssets
  try {
    $choice = Read-Host "Select an option"
  } catch {
    Write-Host "" 
    Write-Host "This menu requires an interactive PowerShell host (Read-Host)." -ForegroundColor Red
    Write-Host "If you ran it via a non-interactive runner (task, pipe, automation), run it in a normal terminal instead." -ForegroundColor Yellow
    Write-Host "Quick check: powershell -ExecutionPolicy Bypass -File \"scripts/walkthrough_menu.ps1\" -Diagnostics" -ForegroundColor Yellow
    exit 1
  }

  try {
    switch ($choice) {
      "1" {
        Kill-Chrome
        Pause-User
      }
      "2" {
        Start-ChromeCdp -Port $port -ProfileDir $profileDir
        Write-Host "Tip: complete Neoseeker verification in the opened Chrome." -ForegroundColor Yellow
        Pause-User
      }
      "3" {
        [void](Test-Cdp -Port $port)
        Pause-User
      }
      "4" {
        if (-not (Test-Cdp -Port $port)) {
          Write-Host "CDP is not reachable. Start Chrome with CDP first (option 2)." -ForegroundColor Yellow
          Pause-User
          break
        }

        Write-Host "Launching scraper now... (this may take a while)" -ForegroundColor Green
        $exitCode = Run-Scraper -Python $resolvedPython -Port $port -StartUrl $startUrl -OutputPdf $outputPdf -MaxPages $maxPages -DelaySeconds $delaySeconds -OfflineAssets:($offlineAssets)
        if ($exitCode -eq $null) { $exitCode = $LASTEXITCODE }

        if ($exitCode -eq 0) {
          Write-Host "Scraper finished successfully." -ForegroundColor Green
        } else {
          Write-Host "Scraper finished with exit code $exitCode." -ForegroundColor Red
          Write-Host "If it ended immediately, scroll up for the Python error output." -ForegroundColor Yellow
        }

        Pause-User "Press Enter to return to menu"
      }
      "5" {
        $outPath = Join-Path $repoRoot (Split-Path $outputPdf -Parent)
        if (-not (Test-Path $outPath)) {
          New-Item -ItemType Directory -Path $outPath -Force | Out-Null
        }
        Start-Process explorer.exe $outPath
        Pause-User
      }
      "6" {
        $portIn = Read-Host "CDP port [$port]"
        if ($portIn) { $port = [int]$portIn }

        $startIn = Read-Host "Start URL [$startUrl]"
        if ($startIn) { $startUrl = $startIn }

        $outIn = Read-Host "Output PDF [$outputPdf]"
        if ($outIn) { $outputPdf = $outIn }

        $maxIn = Read-Host "Max pages [$maxPages]"
        if ($maxIn) { $maxPages = [int]$maxIn }

        $delayIn = Read-Host "Delay seconds [$delaySeconds]"
        if ($delayIn) { $delaySeconds = [double]$delayIn }

        $offIn = Read-Host "Offline assets (true/false) [$offlineAssets]"
        if ($offIn) { $offlineAssets = [bool]::Parse($offIn) }

        Pause-User
      }
      "0" {
        Write-Host "Exiting..." -ForegroundColor Cyan
        break MainLoop
      }
      default {
        Write-Host "Unknown option: $choice" -ForegroundColor Yellow
        Pause-User
      }
    }
  } catch {
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    Pause-User
  }
}
