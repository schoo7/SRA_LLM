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

# Configure PATH for Ollama and NCBI tools (system-wide first, then local)
export PATH="/usr/local/bin:/opt/homebrew/bin:$HOME/edirect:/usr/bin:/bin:$SCRIPT_DIR/ollama_local:$SCRIPT_DIR/bin:$SCRIPT_DIR/ncbi_tools/edirect:$PATH"

# Add common Ollama locations to PATH if they exist
if [ -d "/usr/local/bin" ]; then
    export PATH="/usr/local/bin:$PATH"
fi
if [ -d "/opt/homebrew/bin" ]; then
    export PATH="/opt/homebrew/bin:$PATH"
fi
if [ -d "$HOME/.ollama/bin" ]; then
    export PATH="$HOME/.ollama/bin:$PATH"
fi
if [ -d "$SCRIPT_DIR/ollama_local" ]; then
    export PATH="$SCRIPT_DIR/ollama_local:$PATH"
fi
if [ -d "$SCRIPT_DIR/bin" ]; then
    export PATH="$SCRIPT_DIR/bin:$PATH"
fi
if [ -d "$SCRIPT_DIR/ncbi_tools/edirect" ]; then
    export PATH="$SCRIPT_DIR/ncbi_tools/edirect:$PATH"
fi

# Check if Ollama is available
echo "🔍 Checking Ollama installation..."
if command -v ollama >/dev/null 2>&1; then
    echo "✅ Ollama found at: $(which ollama)"
    
    # Check if Ollama service is running
    if ollama list >/dev/null 2>&1; then
        echo "✅ Ollama service is running"
        
        # Check for models
        MODELS=$(ollama list 2>/dev/null | tail -n +2 | wc -l)
        if [ "$MODELS" -gt 0 ]; then
            echo "✅ $MODELS AI model(s) installed"
        else
            echo "⚠️  No AI models found - you can install them through the web interface"
        fi
    else
        echo "⚠️  Ollama found but service may not be running"
        echo "   Starting Ollama service..."
        # Try to start Ollama service in background
        ollama serve >/dev/null 2>&1 &
        sleep 2
        if ollama list >/dev/null 2>&1; then
            echo "✅ Ollama service started successfully"
        else
            echo "❌ Failed to start Ollama service - you may need to start it manually"
        fi
    fi
else
    echo "❌ Ollama not found in PATH"
    echo "   Installation locations checked:"
    echo "   - /usr/local/bin/ollama (standard)"
    echo "   - /opt/homebrew/bin/ollama (Homebrew)" 
    echo "   - $HOME/.ollama/bin/ollama (user)"
    echo "   - $SCRIPT_DIR/ollama_local/ollama (local)"
    echo ""
    echo "   AI features will not work without Ollama"
    echo "   You can install Ollama from: https://ollama.ai"
    echo "   Or re-run install_mac.command which will set up Ollama automatically"
fi

echo ""
echo "🧬 Checking NCBI E-utilities..."
if command -v esearch >/dev/null 2>&1 && command -v efetch >/dev/null 2>&1; then
    echo "✅ NCBI E-utilities found at: esearch=$(which esearch), efetch=$(which efetch)"
    
    # Test if tools work
    if timeout 10 esearch -help >/dev/null 2>&1; then
        echo "✅ NCBI E-utilities are working properly"
    else
        echo "⚠️ NCBI E-utilities found but may not be working properly"
    fi
else
    echo "❌ NCBI E-utilities not found in PATH"
    echo "   Installation locations checked:"
    echo "   - /usr/local/bin (Homebrew Intel)"
    echo "   - /opt/homebrew/bin (Homebrew Apple Silicon)"
    echo "   - $HOME/edirect (Official installation)"
    echo "   - $SCRIPT_DIR/bin (Local symlinks)"
    echo "   - $SCRIPT_DIR/ncbi_tools/edirect (Local installation)"
    echo ""
    echo "   🔧 To fix this issue:"
    echo "   1. Re-run install_mac.command to install NCBI tools system-wide"
    echo "   2. Or restart your terminal after installation"
    echo "   3. Data fetching will not work without NCBI E-utilities"
fi

echo ""
echo "🌐 Starting enhanced web interface..."
echo "📊 Features: Real-time updates, visualizations, data explorer"
echo "🔗 Browser will open automatically at: http://localhost:8502"
echo ""
echo "💡 To stop the application, press Ctrl+C in this window"
echo ""

# Export PATH for the enhanced web app script
export PATH="$PATH"

# Run the enhanced web app script
./run_enhanced_web_app.sh

echo ""
echo "👋 SRA-LLM web interface stopped."
echo "📝 You can close this window now."
echo ""
read -p "Press Enter to exit..." 