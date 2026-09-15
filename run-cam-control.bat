@echo off
:: Run cam-control from this checkout in its uv environment (Python 3.9 and pinned packages, set up on first run).
cd /d "%~dp0"
where uv >nul 2>&1
if errorlevel 1 (
    echo uv is not installed. Quick install: powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    pause
    exit /b 1
)
uv sync --frozen
if errorlevel 1 (
    pause
    exit /b 1
)
uv run --frozen control.py %*
if errorlevel 1 pause
