# Tax Return Assistant - one-time setup on a Windows laptop.
#
# Run from this folder in PowerShell:
#     powershell -ExecutionPolicy Bypass -File .\setup.ps1
#
# It checks Python, creates a private Python environment in .venv, installs the
# tool, asks where client data should live (TRA_HOME), and runs `tra doctor`.

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

function Fail($message) {
    Write-Host ""
    Write-Host "SETUP STOPPED: $message" -ForegroundColor Red
    exit 1
}

# 1. Python 3.11 or later, via the Windows "py" launcher that python.org installs.
$py = Get-Command py -ErrorAction SilentlyContinue
if (-not $py) {
    Fail "Python isn't installed. Install Python 3.11 or later from https://www.python.org/downloads/ (tick 'Add python.exe to PATH'), or ask IT to, then run this again."
}
$version = & py -3 -c "import sys; print('%d.%d' % sys.version_info[:2])"
if ([version]$version -lt [version]"3.11") {
    Fail "Python $version found; version 3.11 or later is needed. Install it from https://www.python.org/downloads/."
}
Write-Host "Python $version found."

# 2. A private environment for the tool, and the tool itself.
if (-not (Test-Path ".venv")) {
    Write-Host "Creating .venv ..."
    & py -3 -m venv .venv
}
Write-Host "Installing the Tax Return Assistant (this takes a minute) ..."
& .\.venv\Scripts\python.exe -m pip install --quiet --upgrade pip
& .\.venv\Scripts\python.exe -m pip install --quiet -e .
if ($LASTEXITCODE -ne 0) { Fail "Installing the tool failed. Check the internet connection and try again." }

# 3. Where client data lives. Local disk only: not OneDrive, not inside this repository.
$default = "C:\TaxAssistant"
$current = [Environment]::GetEnvironmentVariable("TRA_HOME", "User")
if ($current) { $default = $current }
$answer = Read-Host "Folder for client data [$default]"
if ([string]::IsNullOrWhiteSpace($answer)) { $answer = $default }
$cloudRoots = @($env:OneDrive, $env:OneDriveCommercial, $env:OneDriveConsumer) | Where-Object { $_ }
$underCloudRoot = $cloudRoots | Where-Object { $answer.StartsWith($_, [StringComparison]::OrdinalIgnoreCase) }
if ($underCloudRoot -or $answer -match "(?i)onedrive|dropbox|google ?drive|my drive|shared drives|icloud|cloudstorage| - (shared )?documents") {
    Fail "That folder is synced to the cloud. Client data must stay on this computer. Choose a folder such as C:\TaxAssistant."
}
New-Item -ItemType Directory -Force -Path $answer | Out-Null
[Environment]::SetEnvironmentVariable("TRA_HOME", $answer, "User")
$env:TRA_HOME = $answer
Write-Host "TRA_HOME set to $answer (for your Windows account)."

# 4. Check everything.
Write-Host ""
& .\.venv\Scripts\tra.exe doctor

Write-Host ""
Write-Host "Done. Each time you open PowerShell to use the tool:" -ForegroundColor Green
Write-Host "    cd `"$PSScriptRoot`""
Write-Host "    .\.venv\Scripts\Activate.ps1"
Write-Host "If PowerShell refuses to run Activate.ps1, run this once:"
Write-Host "    Set-ExecutionPolicy -Scope CurrentUser RemoteSigned"
Write-Host ""
Write-Host "Try it safely with invented data:  tra demo --auto-confirm   then   tra prepare DEMO01"
Write-Host "Make sure the drive holding $answer is encrypted with BitLocker."
