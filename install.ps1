# Holdtalk installer for Windows.
#   irm https://raw.githubusercontent.com/VW3st/holdtalk/main/install.ps1 | iex
# Installs uv (a small Python manager) if needed, then Holdtalk with its own private Python.
# Nothing is installed system-wide and no admin rights are needed.
param([string]$Source = "git+https://github.com/VW3st/holdtalk")
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
function Say($t) { Write-Host "  $t" -ForegroundColor Cyan }

Write-Host ""
Write-Host "  Installing Holdtalk" -ForegroundColor White
Write-Host ""

# 1. uv
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Say "Installing uv..."
    powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex" | Out-Null
    $env:Path = "$HOME\.local\bin;$env:Path"
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { throw "uv did not install. See https://docs.astral.sh/uv/ and run this again." }
}

# 2. NVIDIA card? Then add the GPU speed-up
$nvidia = @(Get-CimInstance Win32_VideoController -ErrorAction SilentlyContinue | Where-Object { $_.Name -match "NVIDIA" }).Count -gt 0
$pkg = if ($nvidia) { "holdtalk[cuda] @ $Source" } else { "holdtalk @ $Source" }
if ($nvidia) { Say "NVIDIA graphics card found: installing the fast GPU version." }
else { Say "No NVIDIA card found: installing the CPU version (works everywhere, a bit slower)." }

# 3. Stop a running copy so files can be replaced
Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match "holdtalk" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

# 4. Install
Say "Downloading and installing (a few minutes the first time)..."
uv tool install --python 3.12 --force --reinstall-package holdtalk $pkg
if ($LASTEXITCODE -ne 0) { throw "Install failed (see the messages above)." }

# 5. Shortcuts + start
$toolDir = (uv tool dir).Trim()
$pyw = Join-Path $toolDir "holdtalk\Scripts\pythonw.exe"
if (-not (Test-Path $pyw)) { throw "Could not find the installed app at $pyw" }
& $pyw -m holdtalk --setup
Start-Process $pyw -ArgumentList "-m holdtalk"

Write-Host ""
Write-Host "  Done. Holdtalk is running (microphone icon next to the clock)." -ForegroundColor Green
Write-Host "  Hold your mouse Back button, talk, let go. The speech model downloads on first start (about 1.6 GB on GPU)."
Write-Host "  Click the tray icon for settings."
Write-Host ""
