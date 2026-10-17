@echo off
rem Runs the Tax Return Assistant that setup.ps1 installed, without activating .venv.
rem PowerShell's script policy (which blocks Activate.ps1) doesn't apply to .cmd files.
rem In PowerShell, from this folder:  .\tra doctor
if not exist "%~dp0.venv\Scripts\tra.exe" (
    echo The Tax Return Assistant isn't installed in this folder yet. Run setup first:
    echo     powershell -ExecutionPolicy Bypass -File .\setup.ps1
    exit /b 1
)
"%~dp0.venv\Scripts\tra.exe" %*
exit /b %errorlevel%
