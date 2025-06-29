#!/bin/bash

# SRA-LLM Enhanced Web App Launcher
# ==================================
# Double-clickable macOS launcher for easy access
# Automatically sets up environment and opens browser

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

clear
echo "🧬 SRA-LLM Enhanced Web Interface"
echo "================================="
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

# Check for virtual environment
if [ ! -d "sra_env" ]; then
    echo "🔧 Virtual environment not found. Setting up..."
    echo ""
    
    # Check if Python is available
    if ! command -v python3 &> /dev/null; then
        echo "❌ Python 3 not found. Please install Python first:"
        echo "   Download from: https://python.org/downloads"
        echo ""
        read -p "Press Enter to exit..."
        exit 1
    fi
    
    # Auto-install if install_sra_analyzer.py is available
    if [ -f "install_sra_analyzer.py" ]; then
        echo "🚀 Running automatic installation..."
        python3 install_sra_analyzer.py
        
        if [ $? -ne 0 ]; then
            echo "❌ Installation failed. Please check error messages above."
            read -p "Press Enter to exit..."
            exit 1
        fi
    else
        echo "⚠️  Please run the installation first:"
        echo "   python3 install_sra_analyzer.py"
        echo ""
        read -p "Press Enter to exit..."
        exit 1
    fi
fi

# Check if run script exists
if [ ! -f "run_enhanced_web_app.sh" ]; then
    echo "❌ Error: run_enhanced_web_app.sh not found"
    echo "Please ensure all required files are present"
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

# Make sure run script is executable
chmod +x run_enhanced_web_app.sh

echo "🌐 Starting enhanced web interface..."
echo "📊 Features: Real-time updates, visualizations, data explorer"
echo "🔗 Browser will open automatically at: http://localhost:8502"
echo ""
echo "💡 To stop the application, press Ctrl+C in this window"
echo ""

# Run the enhanced web app script
./run_enhanced_web_app.sh

echo ""
echo "👋 SRA-LLM web interface stopped."
echo "📝 You can close this window now."
echo ""
read -p "Press Enter to exit..." 