@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Horde Watcher - EXE Builder
where py >nul 2>&1
if not errorlevel 1 (set "PY=py -3") else (set "PY=python")
echo [1/3] Installing build tools and dependencies...
%PY% -m pip install --upgrade pyinstaller customtkinter Pillow requests
if errorlevel 1 goto failed
echo [2/3] Building Windows application...
%PY% -m PyInstaller --noconfirm --clean --onefile --windowed --name HordeWatcher --icon horde.ico --add-data "horde_logo.png;." --add-data "horde.ico;." --collect-all customtkinter horde_watcher.py
if errorlevel 1 goto failed
echo [3/3] Done!
echo.
echo Your app: %~dp0dist\HordeWatcher.exe
echo You can copy this EXE anywhere.
pause
exit /b 0
:failed
echo.
echo Build failed. Copy the error from this window.
pause
exit /b 1
