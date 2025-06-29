@echo off
echo 🧬 SRA Metadata Analyzer - Windows Installer
echo =============================================
echo.

REM Check if we're running from the correct directory
if not exist "SRA_fetch_1LLM_improved.py" (
    echo ❌ ERROR: SRA_fetch_1LLM_improved.py not found!
    echo.
    echo Please ensure you're running this installer from the same directory
    echo that contains the SRA analysis scripts.
    echo.
    echo Required files:
    echo   • SRA_fetch_1LLM_improved.py
    echo   • visualize_results.py
    echo   • SRA_web_app_fixed.py
    echo   • install_sra_analyzer.py
    echo.
    pause
    exit /b 1
)

echo ✅ Found SRA analysis scripts in current directory
echo.

REM Check if Python is available
echo 🔍 Checking for Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python not found or not in PATH
    echo.
    echo This installer will help you install Python and all dependencies.
    echo Please follow the instructions carefully.
    echo.
) else (
    echo ✅ Python found!
    python --version
    echo.
)

echo 🚀 Starting comprehensive installation...
echo.
echo This will install:
echo   • Python (if needed)
echo   • All required Python packages
echo   • Ollama (AI model runner)
echo   • NCBI E-utilities
echo   • Create easy-to-use launcher scripts
echo.

pause

REM Check if install_sra_analyzer.py exists
if not exist "install_sra_analyzer.py" (
    echo ❌ ERROR: install_sra_analyzer.py not found!
    echo.
    echo Please ensure install_sra_analyzer.py is in the same directory.
    pause
    exit /b 1
)

REM Run the Python installer
echo 🔧 Running comprehensive installer...
echo.

REM Try to run with python command first
python install_sra_analyzer.py
if %errorlevel% neq 0 (
    echo.
    echo ❌ Installation failed or Python not available.
    echo.
    echo 📋 Manual Installation Steps:
    echo.
    echo 1. Download Python from: https://www.python.org/downloads/
    echo    ✓ IMPORTANT: Check "Add Python to PATH" during installation
    echo.
    echo 2. After Python is installed, run this installer again
    echo.
    echo 3. Or manually run: python install_sra_analyzer.py
    echo.
    pause
    exit /b 1
)

echo.
echo 🎉 Installation completed!
echo.
echo 📋 Quick Start:
echo   • Double-click "run_web_interface.bat" for web interface
echo   • Double-click "run_sra_analyzer.bat" for command line
echo.
echo 🤖 Don't forget to install an AI model:
echo   • Open Command Prompt
echo   • Run: ollama pull qwen3:8b
echo.

pause 