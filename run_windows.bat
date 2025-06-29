@echo off
echo 🧬 SRA-LLM Web Interface Launcher for Windows
echo ============================================
echo.

REM Get current directory
cd /d "%~dp0"
echo 📍 Working directory: %CD%
echo.

REM Check if we're in the right directory
if not exist "SRA_web_app_enhanced.py" (
    echo ❌ Error: SRA_web_app_enhanced.py not found
    echo.
    echo This launcher should be in the same folder as:
    echo   • SRA_web_app_enhanced.py
    echo   • SRA_fetch_1LLM_improved.py
    echo   • requirements.txt
    echo.
    pause
    exit /b 1
)

REM Check for virtual environment
if not exist "sra_env" (
    echo ❌ Virtual environment not found!
    echo.
    echo 🔧 You need to run the installer first:
    echo   • Right-click install_windows.bat → "Run as administrator"
    echo   • This will set up Python, packages, and tools
    echo.
    pause
    exit /b 1
)

REM Check if Python is available in virtual environment
if not exist "sra_env\Scripts\python.exe" (
    echo ❌ Python not found in virtual environment
    echo Please run install_windows.bat first
    echo.
    pause
    exit /b 1
)

REM Check if Ollama is available
echo 🔍 Checking Ollama installation...
ollama --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ⚠️  Ollama not found - AI features may not work
    echo   Run install_windows.bat to set up Ollama
    echo.
) else (
    echo ✅ Ollama found
    
    REM Check for models (count lines, subtract header)
    for /f %%i in ('ollama list 2^>nul ^| find /c /v ""') do set MODEL_COUNT=%%i
    if %MODEL_COUNT% gtr 1 (
        set /a ACTUAL_MODELS=%MODEL_COUNT%-1
        echo ✅ !ACTUAL_MODELS! AI model(s) installed
    ) else (
        echo ⚠️  No AI models found - you can install them through the web interface
    )
)

echo.
echo 🌐 Starting enhanced web interface...
echo 📊 Features: Real-time updates, visualizations, data explorer
echo 🔗 Browser will open automatically at: http://localhost:8502
echo.
echo 💡 To stop the application, press Ctrl+C in this window
echo.

REM Activate virtual environment
call "sra_env\Scripts\activate.bat"

REM Check if Streamlit is available
python -c "import streamlit" >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Streamlit not found in virtual environment
    echo Please run install_windows.bat to install dependencies
    pause
    exit /b 1
)

REM Start the web interface
echo 🚀 Launching SRA-LLM web interface...

REM Try to open browser automatically after 3 seconds
start "" timeout /t 3 /nobreak >nul 2>&1 && start "" http://localhost:8502

REM Run the enhanced web app
streamlit run SRA_web_app_enhanced.py --server.port 8502

echo.
echo 👋 SRA-LLM web interface stopped.
echo 📝 You can close this window now.
echo.
pause 