@echo off
rem Builds dist\Stackyard.exe (single file, no console window).
cd /d "%~dp0"

python -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo PyInstaller is not installed. Installing it now...
    python -m pip install pyinstaller || goto :error
)

python -m PyInstaller --noconfirm --clean Stackyard.spec || goto :error

echo.
echo Build finished: %cd%\dist\Stackyard.exe
pause
exit /b 0

:error
echo.
echo Build failed. See the messages above.
pause
exit /b 1
