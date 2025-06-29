#!/bin/bash

# SRA-LLM Web Interface Launcher for macOS
# ========================================
# Double-clickable launcher for the web interface
# Run install_mac.command first if not already installed

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

clear
echo "🧬 SRA-LLM Web Interface Launcher"
echo "================================"
echo "📍 Working directory: $SCRIPT_DIR"
echo ""

# Check if we're in the right directory
if [ ! -f "SRA_web_app_enhanced.py" ]; then
    echo "❌ Error: SRA_web_app_enhanced.py not found"
    echo ""
    echo "This launcher should be in the same folder as:"
    echo "  • SRA_web_app_enhanced.py"
    echo "  • SRA_fetch_1LLM_improved.py"
    echo "  • requirements.txt"
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

# Check for virtual environment
if [ ! -d "sra_env" ]; then
    echo "❌ Virtual environment not found!"
    echo ""
    echo "🔧 You need to run the installer first:"
    echo "   • Double-click: install_mac.command"
    echo "   • This will set up Python, packages, and tools"
    echo ""
    read -p "Press Enter to exit..."
    exit 1
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

# Check if Ollama is available
echo "🔍 Checking Ollama installation..."
if command -v ollama >/dev/null 2>&1; then
    echo "✅ Ollama found"
    
    # Check for models
    MODELS=$(ollama list 2>/dev/null | tail -n +2 | wc -l)
    if [ "$MODELS" -gt 0 ]; then
        echo "✅ $MODELS AI model(s) installed"
    else
        echo "⚠️  No AI models found - you can install them through the web interface"
    fi
else
    echo "⚠️  Ollama not found - AI features may not work"
    echo "   Run install_mac.command to set up Ollama"
fi

echo ""
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