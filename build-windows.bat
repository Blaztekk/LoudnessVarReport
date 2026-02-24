@echo off
setlocal EnableDelayedExpansion

echo ============================================
echo  LoudScan - Windows Build
echo ============================================
echo.

:: Versioning (stored in version#)
set VERSION_OK=1
set CURRENT_VERSION=
set NEXT_VERSION=

if not exist "version#" (
    echo ERROR: version# not found. Building without version suffix.
    set VERSION_OK=0
) else (
    for /f "usebackq delims=" %%A in ("version#") do set CURRENT_VERSION=%%A
    set CURRENT_VERSION=%CURRENT_VERSION: =%

    for /f "tokens=1-3 delims=." %%a in ("%CURRENT_VERSION%") do (
        set MAJOR=%%a
        set MINOR=%%b
        set PATCH=%%c
    )

    if "%MAJOR%"=="" (
        echo ERROR: Invalid version in version#: "%CURRENT_VERSION%". Building without version suffix.
        set VERSION_OK=0
    )
    if "%MINOR%"=="" set VERSION_OK=0
    if "%PATCH%"=="" set VERSION_OK=0
    if "%VERSION_OK%"=="0" (
        echo ERROR: Invalid version in version#: "%CURRENT_VERSION%". Expected MAJOR.MINOR.PATCH (e.g. 1.0.1).
    )
)

if "%VERSION_OK%"=="1" (
    set MAJOR_BAD=
    set MINOR_BAD=
    set PATCH_BAD=

    for /f "delims=0123456789" %%i in ("%MAJOR%") do set MAJOR_BAD=%%i
    for /f "delims=0123456789" %%i in ("%MINOR%") do set MINOR_BAD=%%i
    for /f "delims=0123456789" %%i in ("%PATCH%") do set PATCH_BAD=%%i

    if not "%MAJOR_BAD%"=="" set VERSION_OK=0
    if not "%MINOR_BAD%"=="" set VERSION_OK=0
    if not "%PATCH_BAD%"=="" set VERSION_OK=0
)

if "%VERSION_OK%"=="1" (
    set /a PATCH_NUM=%PATCH%+1
    set NEXT_VERSION=%MAJOR%.%MINOR%.%PATCH_NUM%
    echo Current version: %CURRENT_VERSION%
    echo Next version   : %NEXT_VERSION%
) else (
    set LOUDSCAN_VERSION=
)

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
if "%VERSION_OK%"=="1" (
    set LOUDSCAN_VERSION=%NEXT_VERSION%
) else (
    set LOUDSCAN_VERSION=
)
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

:: Persist version bump only after a successful build
if "%VERSION_OK%"=="1" (
    >"version#" echo %NEXT_VERSION%
)

echo [3/3] Cleaning up temporary files...
rmdir /s /q .build_tmp 2>nul

echo.
echo ============================================
echo  Build complete!
if "%VERSION_OK%"=="1" (
    echo  Output: builds\windows\LoudScan-windows-%NEXT_VERSION%.exe
) else (
    echo  Output: builds\windows\LoudScan-windows.exe
)
echo ============================================
echo.
if "%VERSION_OK%"=="1" (
    echo Upload builds\windows\LoudScan-windows-%NEXT_VERSION%.exe to your GitHub Release.
) else (
    echo Upload builds\windows\LoudScan-windows.exe to your GitHub Release.
)
echo.
pause
