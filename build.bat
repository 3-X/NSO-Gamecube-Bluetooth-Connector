@echo off
setlocal enabledelayedexpansion

echo ============================================
echo   NSO GameCube Controller - Build Script
echo ============================================
echo.

:: Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python from https://python.org
    pause
    exit /b 1
)

:: Check for required packages
echo [1/4] Checking dependencies...

pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

pip show vgamepad >nul 2>&1
if errorlevel 1 (
    echo Installing vgamepad...
    pip install vgamepad
)

pip show bleak >nul 2>&1
if errorlevel 1 (
    echo Installing bleak...
    pip install bleak
)

echo Dependencies OK
echo.

:: Clean previous builds
echo [2/4] Cleaning previous builds...
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"
echo Clean complete
echo.

:: Build with PyInstaller (use python -m to avoid PATH issues)
echo [3/4] Building executable with PyInstaller...
echo This may take a few minutes...
echo.

python -m PyInstaller nso_gc_controller.spec --noconfirm

if errorlevel 1 (
    echo.
    echo [ERROR] PyInstaller build failed!
    pause
    exit /b 1
)

echo.
echo Build complete!
echo.

:: Check if Inno Setup is installed
echo [4/4] Checking for Inno Setup...

set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" (
    set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
) else if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" (
    set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
)

if defined ISCC (
    echo Found Inno Setup, building installer...
    echo.
    "%ISCC%" installer.iss

    if errorlevel 1 (
        echo.
        echo [WARNING] Installer build failed
        echo The standalone exe is still available in dist\
    ) else (
        echo.
        echo ============================================
        echo   BUILD COMPLETE!
        echo ============================================
        echo.
        echo Standalone exe: dist\NSO_GC_Controller.exe
        echo Installer:      installer_output\NSO_GC_Controller_Setup.exe
        echo.
    )
) else (
    echo.
    echo Inno Setup not found - skipping installer creation
    echo.
    echo To create an installer:
    echo   1. Download Inno Setup from https://jrsoftware.org/isdl.php
    echo   2. Install it
    echo   3. Run this script again
    echo.
    echo ============================================
    echo   BUILD COMPLETE!
    echo ============================================
    echo.
    echo Standalone exe: dist\NSO_GC_Controller.exe
    echo.
    echo You can distribute this exe directly, or create
    echo an installer by installing Inno Setup and running
    echo this script again.
    echo.
)

pause
