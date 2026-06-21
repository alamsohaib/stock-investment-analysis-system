@echo off
title PSX Investment Analysis System
cd /d "%~dp0"
echo Starting PSX Investment Analysis System...
echo (A browser window will open automatically. Keep this window open while you use it.)
echo.
python run.py
if errorlevel 1 (
  echo.
  echo Could not start. Make sure Python is installed and on your PATH.
  echo Download Python from https://www.python.org/downloads/
  pause
)
