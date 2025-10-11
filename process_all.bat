@echo off
setlocal EnableExtensions EnableDelayedExpansion
REM Batch-process all HTML files to create aggressive.flat outputs if missing
REM Double-click to run from project root.

REM Change to script directory
cd /d "%~dp0"

REM Prefer venv python if available
if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
) else (
  set "PY=python"
)

REM Verify Python is available
"%PY%" --version >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python not found! Please install Python or create a virtual environment in .venv
  pause
  exit /b 1
)

REM Optional: ensure dependencies (comment out if not needed)
if exist requirements.txt (
  echo [INFO] Ensuring dependencies are installed...
  "%PY%" -m pip install -r requirements.txt
  if errorlevel 1 (
    echo [WARNING] Failed to install dependencies. Please run: pip install -r requirements.txt
    echo.
  )
) else (
  echo [WARNING] requirements.txt not found in current directory
  echo [INFO] Required packages: beautifulsoup4, lxml, htmlmin
  echo [INFO] Install with: pip install beautifulsoup4 lxml htmlmin
  echo.
)

set /a processed=0
set /a skipped=0
set /a failed=0

for /r %%F in (*.html) do (
  set "fname=%%~nxF"
  set "out=%%~dpnF.aggressive.flat.html"

  REM Skip if source is already an aggressive.flat file
  set "chk=!fname:.aggressive.flat.html=!"
  if not "!chk!"=="!fname!" (
    echo [SKIP] Already flat: %%F
    set /a skipped+=1
  ) else if exist "!out!" (
    echo [SKIP] Exists: !out!
    set /a skipped+=1
  ) else (
    echo [RUN ] Aggressive flatten -> !out!
    "%PY%" minimize_html.py "%%F" --mode aggressive --flatten-inputs --keep-images -o "!out!"
    if errorlevel 1 (
      echo [FAIL] Error processing %%F
      set /a failed+=1
    ) else (
      set /a processed+=1
    )
  )
)

echo.
echo === Summary ===
echo Processed: %processed%
echo Skipped:   %skipped%
echo Failed:    %failed%

pause
