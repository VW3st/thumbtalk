# Removes ThumbTalk, its shortcuts and (optionally) its settings and downloaded speech models.
#   irm https://raw.githubusercontent.com/VW3st/thumbtalk/main/uninstall.ps1 | iex
$ErrorActionPreference = "Continue"
Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" |
    Where-Object { $_.CommandLine -match "thumbtalk" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
$pyw = Join-Path (uv tool dir).Trim() "thumbtalk\Scripts\pythonw.exe"
if (Test-Path $pyw) { & $pyw -m thumbtalk --remove }
uv tool uninstall thumbtalk
$ans = Read-Host "Also delete your settings and word list? (y/N)"
if ($ans -match "^y") { Remove-Item "$env:APPDATA\ThumbTalk" -Recurse -Force -ErrorAction SilentlyContinue }
Write-Host "ThumbTalk removed. Speech models stay in $HOME\.cache\huggingface (delete that folder to free the space)."
