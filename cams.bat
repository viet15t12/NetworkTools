@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if "%~1"=="" goto menu
if /I "%~1"=="sync" goto sync
if /I "%~1"=="build" goto build
if /I "%~1"=="setup" goto setup
if /I "%~1"=="check" goto check
if /I "%~1"=="run" goto run
if /I "%~1"=="all" goto all
echo Usage: %~nx0 [sync^|build^|setup^|check^|run^|all]
exit /b 2

:sync
where uv >nul 2>nul
if errorlevel 1 (
    echo ERROR: uv is not installed or is not available in PATH.
    echo Install uv from https://docs.astral.sh/uv/ and run this script again.
    exit /b 1
)
uv --version
echo Synchronizing application and Cython build dependencies...
uv sync --extra speed
exit /b %errorlevel%

:build
where uv >nul 2>nul
if errorlevel 1 (
    echo ERROR: uv is not installed or is not available in PATH.
    echo Install uv from https://docs.astral.sh/uv/ and run this script again.
    exit /b 1
)
uv --version
uv run --extra speed python -c "from Cython.Build import cythonize" >nul 2>nul
if errorlevel 1 (
    echo WARNING: The native Cython compiler package cannot be loaded.
    echo Retrying with Cython's pure-Python compiler for Windows compatibility...
    set "NO_CYTHON_COMPILE=true"
    uv sync --extra speed --reinstall-package cython --no-binary-package cython --no-cache
    if errorlevel 1 (
        echo ERROR: Could not install the pure-Python Cython compiler.
        exit /b 1
    )
    uv run --extra speed python -c "from Cython.Build import cythonize" >nul 2>nul
    if errorlevel 1 (
        echo ERROR: Cython still cannot be loaded after the compatibility retry.
        exit /b 1
    )
)
echo Building optional Cython acceleration modules...
uv run --extra speed python setup_cython.py build_ext --inplace --force
if errorlevel 1 exit /b %errorlevel%
uv run --extra speed python -c "from pathlib import Path; from features.devices.sync import _engine; p=Path(_engine.__file__); print(f'sync engine: {p}'); raise SystemExit(0 if p.suffix in {'.so', '.pyd'} else 1)"
exit /b %errorlevel%

:setup
"%ComSpec%" /d /c ""%~f0" sync"
if errorlevel 1 exit /b %errorlevel%
"%ComSpec%" /d /c ""%~f0" build"
if not errorlevel 1 exit /b 0
echo.
echo WARNING: Optional Cython acceleration could not be built or loaded.
echo CAMS will use the built-in Python sync engine instead.
for %%F in ("features\devices\sync\_engine*.pyd" "features\devices\sync\_engine*.so") do if exist "%%~fF" (
    move /Y "%%~fF" "%%~fF.disabled" >nul
    echo Disabled unusable extension: %%~nxF
)
uv run --extra speed python -c "from pathlib import Path; from features.devices.sync import _engine; p=Path(_engine.__file__); print(f'sync engine fallback: {p}'); raise SystemExit(0 if p.suffix == '.py' else 1)"
if errorlevel 1 (
    echo ERROR: The Python sync engine fallback could not be loaded.
    exit /b 1
)
exit /b 0

:check
where uv >nul 2>nul
if errorlevel 1 (
    echo ERROR: uv is not installed or is not available in PATH.
    echo Install uv from https://docs.astral.sh/uv/ and run this script again.
    exit /b 1
)
uv --version
uv run --extra speed python -c "from pathlib import Path; from features.devices.sync import _engine; p=Path(_engine.__file__); print(f'sync engine: {p}'); raise SystemExit(0 if p.suffix in {'.so', '.pyd'} else 1)"
exit /b %errorlevel%

:run
where uv >nul 2>nul
if errorlevel 1 (
    echo ERROR: uv is not installed or is not available in PATH.
    echo Install uv from https://docs.astral.sh/uv/ and run this script again.
    exit /b 1
)
uv --version
echo Starting CAMS...
uv run --extra speed python main.py
exit /b %errorlevel%

:all
"%ComSpec%" /d /c ""%~f0" setup"
if errorlevel 1 exit /b %errorlevel%
"%ComSpec%" /d /c ""%~f0" run"
exit /b %errorlevel%

:menu
echo.
echo CAMS
echo   1^) Sync dependencies
echo   2^) Build and verify Cython
echo   3^) Full setup ^(sync + optional Cython^)
echo   4^) Check Cython status
echo   5^) Run application
echo   6^) Full setup and run
echo   0^) Exit
choice /C 1234560 /N /M "Select: "
if errorlevel 7 exit /b 0
if errorlevel 6 goto all
if errorlevel 5 goto run
if errorlevel 4 goto check
if errorlevel 3 goto setup
if errorlevel 2 goto build
if errorlevel 1 goto sync
