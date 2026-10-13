@echo off
rem Starts Stackyard with a console (useful to see Python errors). Double-click stackyard.pyw for no console.
cd /d "%~dp0"
python stackyard.pyw
if errorlevel 1 pause
