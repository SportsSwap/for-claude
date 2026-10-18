@echo off
rem Opens Sawnx, the Tax Return Assistant's website, on this laptop only. Double-click it,
rem or use the Sawnx shortcut setup.ps1 puts on the desktop. Close the black window to stop Sawnx.
if not exist "%~dp0.venv\Scripts\tra.exe" (
    echo The Tax Return Assistant isn't installed in this folder yet. Run setup first:
    echo     powershell -ExecutionPolicy Bypass -File .\setup.ps1
    pause
    exit /b 1
)
title Sawnx
"%~dp0.venv\Scripts\tra.exe" web %*
if errorlevel 1 pause
exit /b %errorlevel%
