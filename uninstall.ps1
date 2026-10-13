# Removes Holdtalk, its shortcuts and (optionally) its settings and downloaded speech models.
#   irm https://raw.githubusercontent.com/VW3st/holdtalk/main/uninstall.ps1 | iex
$ErrorActionPreference = "Continue"
Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" |
    Where-Object { $_.CommandLine -match "holdtalk" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
$pyw = Join-Path (uv tool dir).Trim() "holdtalk\Scripts\pythonw.exe"
if (Test-Path $pyw) { & $pyw -m holdtalk --remove }
uv tool uninstall holdtalk
$ans = Read-Host "Also delete your settings and word list? (y/N)"
if ($ans -match "^y") { Remove-Item "$env:APPDATA\Holdtalk" -Recurse -Force -ErrorAction SilentlyContinue }
Write-Host "Holdtalk removed. Speech models stay in $HOME\.cache\huggingface (delete that folder to free the space)."
