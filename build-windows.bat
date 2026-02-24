@echo off
setlocal EnableDelayedExpansion

echo ============================================
echo  LoudScan - Windows Build
echo ============================================
echo.

:: Locate Python
where py >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON=py
) else (
    where python >nul 2>&1
    if %errorlevel% equ 0 (
        set PYTHON=python
    ) else (
        echo ERROR: Python not found. Install from https://www.python.org/downloads/
        exit /b 1
    )
)

echo [1/3] Installing build dependencies...
%PYTHON% -m pip install -r requirements-dev.txt --quiet
if %errorlevel% neq 0 (
    echo ERROR: pip install failed.
    exit /b 1
)

echo [2/3] Building executable...
%PYTHON% -m PyInstaller ^
    --clean ^
    --noconfirm ^
    --distpath builds\windows ^
    --workpath .build_tmp ^
    loudscan.spec

if %errorlevel% neq 0 (
    echo ERROR: PyInstaller build failed.
    exit /b 1
)

echo [3/3] Cleaning up temporary files...
rmdir /s /q .build_tmp 2>nul

echo.
echo ============================================
echo  Build complete!
echo  Output: builds\windows\LoudScan-windows.exe
echo ============================================
echo.
echo Upload builds\windows\LoudScan-windows.exe to your GitHub Release.
echo.
pause
