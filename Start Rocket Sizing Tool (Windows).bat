@echo off
rem Rocket Engine Sizing Tool - Windows launcher.
rem Double-click to start. The first launch sets everything up (a few minutes).
setlocal
rem Download layout: program files in a "Resources" folder next to this file.
if exist "%~dp0Resources\desktop.py" (cd /d "%~dp0Resources") else (cd /d "%~dp0")
title Rocket Engine Sizing Tool

if exist ".venv\Scripts\python.exe" goto check

echo First launch: setting up the app. This takes a few minutes.
echo.
set "PY="
py -3.12 --version >nul 2>&1 && set "PY=py -3.12"
if not defined PY py -3 --version >nul 2>&1 && set "PY=py -3"
if not defined PY python --version >nul 2>&1 && set "PY=python"
if not defined PY goto nopython
%PY% -m venv .venv
if errorlevel 1 goto failed

:check
".venv\Scripts\python.exe" -c "import streamlit, pandas, rocketcea, webview" >nul 2>&1
if not errorlevel 1 goto run
echo Installing components...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed

:run
rem pythonw runs the app without a console window
start "" ".venv\Scripts\pythonw.exe" desktop.py
exit /b 0

:nopython
echo Python was not found.
echo Install Python 3.12 from https://www.python.org/downloads/windows/
echo and tick "Add python.exe to PATH" during setup, then run this file again.
echo.
pause
exit /b 1

:failed
echo.
echo Setup failed. See the messages above, or app.log in the Resources folder.
pause
exit /b 1
