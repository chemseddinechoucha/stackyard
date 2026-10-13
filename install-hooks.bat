@echo off
rem Installs the git hooks that bump the version and update CHANGELOG.md / README.md on each commit.
cd /d "%~dp0"
python install_hooks.py
pause
