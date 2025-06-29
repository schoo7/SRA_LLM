#!/bin/bash

# SRA-LLM Complete Installer for macOS
# ====================================
# Double-clickable installer that sets up everything
# Does NOT auto-open browser - use run_mac.command for that

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

clear
echo "🧬 SRA-LLM Complete Installer for macOS"
echo "======================================="
echo "📍 Working directory: $SCRIPT_DIR"
echo ""

# Check if we're in the right directory
if [ ! -f "SRA_web_app_enhanced.py" ]; then
    echo "❌ Error: SRA_web_app_enhanced.py not found"
    echo ""
    echo "This script should be in the same folder as:"
    echo "  • SRA_web_app_enhanced.py"
    echo "  • SRA_fetch_1LLM_improved.py"
    echo "  • requirements.txt"
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

# Check if Python is properly installed first
echo "🔍 Checking Python installation..."
if command -v python3 >/dev/null 2>&1; then
    PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
    echo "✅ Python $PYTHON_VERSION found"
    PYTHON_OK=true
else
    echo "❌ Python 3 not found"
    PYTHON_OK=false
fi

# Check if virtual environment already exists
if [ -d "sra_env" ]; then
    echo "✅ Virtual environment already exists"
    VENV_EXISTS=true
else
    echo "🔧 Virtual environment not found - will create during installation"
    VENV_EXISTS=false
fi

echo ""
echo "🚀 Starting comprehensive installation..."
echo ""
echo "This installer will set up:"
echo "  • Python (if needed)"
echo "  • Virtual environment"
echo "  • All required Python packages"
echo "  • Ollama (AI model runner)"
echo "  • NCBI E-utilities"
echo "  • Easy launcher scripts"
echo ""

if [ "$PYTHON_OK" = true ] && [ "$VENV_EXISTS" = true ]; then
    echo "💡 Note: Python and virtual environment already exist"
    echo "   Installation will skip these steps and update packages"
fi

echo ""
read -p "Press Enter to continue with installation..."

# Auto-install if install_sra_analyzer.py is available
if [ -f "install_sra_analyzer.py" ]; then
    echo "🔧 Running comprehensive installer..."
    echo ""
    
    # Run the installer
    if [ "$PYTHON_OK" = true ]; then
        python3 install_sra_analyzer.py
        INSTALL_RESULT=$?
    else
        echo "❌ Python not available. Installing Python first..."
        # Check if Homebrew is available
        if command -v brew >/dev/null 2>&1; then
            echo "🍺 Installing Python via Homebrew..."
            brew install python@3.11
            python3 install_sra_analyzer.py
            INSTALL_RESULT=$?
        else
            echo "❌ Homebrew not found. Please install Python manually:"
            echo "   1. Install Homebrew: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
            echo "   2. Install Python: brew install python@3.11"
            echo "   3. Run this installer again"
            echo ""
            read -p "Press Enter to exit..."
            exit 1
        fi
    fi
    
    if [ $INSTALL_RESULT -ne 0 ]; then
        echo ""
        echo "❌ Installation failed. Please check error messages above."
        echo ""
        read -p "Press Enter to exit..."
        exit 1
    fi
else
    echo "❌ Error: install_sra_analyzer.py not found"
    echo "Please ensure all required files are present"
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi
echo ""
echo "🎉 Installation completed successfully!"
echo ""
echo "📋 What was installed:"
echo "  ✅ Python virtual environment (sra_env/)"
echo "  ✅ All required Python packages"
echo "  ✅ Ollama (AI model runner)"
echo "  ✅ NCBI E-utilities"
echo "  ✅ Easy launcher scripts"
echo ""
echo "🚀 Next Steps:"
echo ""
echo "1. 🖥️  Start the Web Interface:"
echo "   • Double-click: run_mac.command"
echo "   • Browser will open at: http://localhost:8502"
echo ""
echo "2. 🤖 Install AI Models (through Web UI):"
echo "   • The web interface will show available models"
echo "   • Click 'Install' next to qwen3:8b (recommended)"
echo "   • Models download automatically in the background"
echo ""
echo "3. 📊 Start Analyzing:"
echo "   • Enter keywords like 'prostate cancer' or 'MDAPCA2B'"
echo "   • Watch real-time progress and visualizations"
echo ""
echo "💡 The installer is complete. Use run_mac.command to start the web interface."
echo ""
read -p "Press Enter to finish..."
exit 0 