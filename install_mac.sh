#!/bin/bash

echo "🧬 SRA Metadata Analyzer - macOS Installer"
echo "=========================================="
echo

# Check if we're running from the correct directory
if [ ! -f "SRA_fetch_1LLM_improved.py" ]; then
    echo "❌ ERROR: SRA_fetch_1LLM_improved.py not found!"
    echo
    echo "Please ensure you're running this installer from the same directory"
    echo "that contains the SRA analysis scripts."
    echo
    echo "Required files:"
    echo "  • SRA_fetch_1LLM_improved.py"
    echo "  • visualize_results.py"
    echo "  • SRA_web_app_fixed.py"
    echo "  • install_sra_analyzer.py"
    echo
    read -p "Press any key to exit..."
    exit 1
fi

echo "✅ Found SRA analysis scripts in current directory"
echo

# Check if Python is available
echo "🔍 Checking for Python installation..."
if command -v python3 >/dev/null 2>&1; then
    echo "✅ Python found!"
    python3 --version
    PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    echo "✅ Python found!"
    python --version
    PYTHON_CMD="python"
else
    echo "❌ Python not found"
    echo
    echo "This installer will help you install Python and all dependencies."
    echo "Please follow the instructions carefully."
    echo
    PYTHON_CMD=""
fi

echo
echo "🚀 Starting comprehensive installation..."
echo
echo "This will install:"
echo "  • Python (if needed)"
echo "  • All required Python packages"
echo "  • Ollama (AI model runner)"
echo "  • NCBI E-utilities"
echo "  • Create easy-to-use launcher scripts"
echo

read -p "Press Enter to continue..."

# Check if install_sra_analyzer.py exists
if [ ! -f "install_sra_analyzer.py" ]; then
    echo "❌ ERROR: install_sra_analyzer.py not found!"
    echo
    echo "Please ensure install_sra_analyzer.py is in the same directory."
    read -p "Press any key to exit..."
    exit 1
fi

# Run the Python installer
echo "🔧 Running comprehensive installer..."
echo

# Try to run with available Python command
if [ -n "$PYTHON_CMD" ]; then
    $PYTHON_CMD install_sra_analyzer.py
    INSTALL_RESULT=$?
else
    echo "❌ Python not available, attempting to install first..."
    
    # Check if Homebrew is available
    if command -v brew >/dev/null 2>&1; then
        echo "🍺 Installing Python via Homebrew..."
        brew install python@3.11
        PYTHON_CMD="python3"
        $PYTHON_CMD install_sra_analyzer.py
        INSTALL_RESULT=$?
    else
        echo "❌ Neither Python nor Homebrew found."
        INSTALL_RESULT=1
    fi
fi

if [ $INSTALL_RESULT -ne 0 ]; then
    echo
    echo "❌ Installation failed or Python not available."
    echo
    echo "📋 Manual Installation Steps:"
    echo
    echo "Option 1 - Install Homebrew (recommended):"
    echo "  1. Open Terminal"
    echo "  2. Run: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
    echo "  3. Run: brew install python@3.11"
    echo "  4. Run this installer again"
    echo
    echo "Option 2 - Download Python directly:"
    echo "  1. Visit: https://www.python.org/downloads/mac-osx/"
    echo "  2. Download and install Python 3.11 or newer"
    echo "  3. Run this installer again"
    echo
    echo "Option 3 - Manual setup:"
    echo "  Run: python3 install_sra_analyzer.py"
    echo
    read -p "Press any key to exit..."
    exit 1
fi

echo
echo "🎉 Installation completed!"
echo
echo "📋 Quick Start:"
echo "  • Double-click 'run_web_interface.sh' for web interface"
echo "  • Run './run_sra_analyzer.sh' for command line"
echo
echo "🤖 Don't forget to install an AI model:"
echo "  • Open Terminal"
echo "  • Run: ollama pull qwen3:8b"
echo

read -p "Press any key to finish..." 