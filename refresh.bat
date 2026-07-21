@echo off
REM One-click data refresh (scrape -> verify -> analyze -> dashboard -> publish).
REM First-time setup: see docs\SETUP_HK.md
cd /d %~dp0
set PYTHONUTF8=1
if exist .venv\Scripts\python.exe (set PY=.venv\Scripts\python.exe) else (set PY=python)
%PY% run_all.py --publish
pause
