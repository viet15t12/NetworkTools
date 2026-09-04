@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1

rem =============================================================================
rem  setup_venv.bat — Tạo .venv bằng uv và cài thư viện từ file text
rem  Cách dùng: setup_venv.bat [packages_file] [venv_dir]
rem    packages_file : file text chứa tên thư viện (mặc định: packages.txt)
rem    venv_dir      : thư mục venv sẽ tạo    (mặc định: .venv)
rem =============================================================================

rem ---------- Tham số đầu vào ------------------------------------------------
set "PACKAGES_FILE=%~1"
if "%PACKAGES_FILE%"=="" set "PACKAGES_FILE=packages.txt"

set "VENV_DIR=%~2"
if "%VENV_DIR%"=="" set "VENV_DIR=.venv"

set "OUTPUT_FILE=venv_path.txt"

echo =============================================
echo   UV VENV SETUP
echo =============================================

rem ---------- Kiểm tra file packages -----------------------------------------
if not exist "%PACKAGES_FILE%" (
    echo [LOI] Khong tim thay file thu vien: "%PACKAGES_FILE%"
    echo       Tao file "%PACKAGES_FILE%" voi moi ten thu vien tren mot dong.
    exit /b 1
)

echo [1/4] Kiem tra uv...
where uv >nul 2>&1
if errorlevel 1 (
    echo [LOI] Khong tim thay "uv". Cai dat tai: https://docs.astral.sh/uv/
    exit /b 1
)
for /f "tokens=*" %%v in ('uv --version') do echo       %%v

rem ---------- Tạo virtual environment ----------------------------------------
echo [2/4] Tao virtual environment tai: %VENV_DIR%
uv venv "%VENV_DIR%"
if errorlevel 1 (
    echo [LOI] Khong the tao venv.
    exit /b 1
)

rem ---------- Lấy đường dẫn tuyệt đối ----------------------------------------
pushd "%VENV_DIR%"
set "VENV_ABS=%CD%"
popd
set "PYTHON_BIN=%VENV_ABS%\Scripts\python.exe"

rem ---------- Cài thư viện từ file -------------------------------------------
echo [3/4] Cai thu vien tu file: %PACKAGES_FILE%
echo ----------------------------------------------

if not exist "%PACKAGES_FILE%" (
    echo [LOI] Khong tim thay file %PACKAGES_FILE%
    exit /b 1
)

rem Sử dụng trực tiếp lệnh pip install -r của uv để đọc file chuẩn xác nhất
uv pip install --python "%PYTHON_BIN%" -r "%PACKAGES_FILE%"

if errorlevel 1 (
    echo [LOI] Cai dat thu vien that bai.
    exit /b 1
)

echo ----------------------------------------------

rem ---------- Xuất đường dẫn venv ra file ------------------------------------
echo [4/4] Ghi duong dan venv vao: %OUTPUT_FILE%
echo %VENV_ABS%> "%OUTPUT_FILE%"

rem ---------- Kiểm tra package <-> import ------------------------------------
set "CHECK_SCRIPT=%~dp0script\check_packages_imports.py"
if exist "%CHECK_SCRIPT%" (
    echo.
    echo [5/5] Kiem tra package ^<-^> import...
    "%PYTHON_BIN%" "%CHECK_SCRIPT%" --packages "%PACKAGES_FILE%"
)

echo.
echo =============================================
echo   HOAN THANH!
echo =============================================
echo   Venv   : %VENV_ABS%
echo   Python : %PYTHON_BIN%
echo   Duong dan da luu tai: %OUTPUT_FILE%
echo.
echo   Chay script Python bang venv:
echo     "%PYTHON_BIN%" your_script.py
echo.
echo   Hoac kich hoat venv thu cong:
echo     %VENV_ABS%\Scripts\activate.bat
echo =============================================

endlocal
