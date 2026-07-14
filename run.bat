@echo off
REM ============================================================================
REM  TokenOptimizer launcher
REM
REM  Double-click this file to open the desktop UI, or run it from a terminal
REM  with any tokenopt command, e.g.:
REM
REM      run.bat                                   (opens the UI)
REM      run.bat optimize-doc --file report.docx
REM      run.bat optimize-doc --file notes.txt --summarize
REM      run.bat demo
REM
REM  Uses the project's virtual environment directly - no activation needed.
REM ============================================================================

setlocal

REM Always run from this script's own folder, whatever the caller's cwd is.
cd /d "%~dp0"

set "PYTHON=%~dp0.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo [ERROR] Virtual environment not found at:
    echo         %PYTHON%
    echo.
    echo Create it and install the app first:
    echo         python -m venv .venv
    echo         .venv\Scripts\python.exe -m pip install -e .
    echo.
    pause
    exit /b 1
)

REM No arguments -> launch the desktop UI. Otherwise pass all args through.
if "%~1"=="" (
    "%PYTHON%" -m token_optimizer.cli ui
) else (
    "%PYTHON%" -m token_optimizer.cli %*
)

set "EXITCODE=%ERRORLEVEL%"

REM If launched by double-click (no args) and it errored, keep the window open.
if "%~1"=="" if not "%EXITCODE%"=="0" pause

endlocal & exit /b %EXITCODE%
