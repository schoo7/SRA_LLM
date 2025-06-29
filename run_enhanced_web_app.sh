#!/bin/bash

# Enhanced SRA Web App Launcher
# This script starts the enhanced web interface with all bug fixes

echo "🚀 Starting Enhanced SRA Web App..."

# Configure PATH for Ollama (common installation locations)
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:$PATH"

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

# Check if virtual environment exists
if [ ! -d "sra_env" ]; then
    echo "❌ Virtual environment 'sra_env' not found!"
    echo "Please run the installer first: ./install_sra_analyzer.py"
    exit 1
fi

# Activate virtual environment
source sra_env/bin/activate

# Preserve PATH in virtual environment (important for Ollama access)
export PATH="$PATH"

# Check Ollama availability before starting web app
echo "🔍 Checking Ollama installation..."
if command -v ollama >/dev/null 2>&1; then
    echo "✅ Ollama found at: $(which ollama)"
    # Try to check if Ollama service is running
    if ollama list >/dev/null 2>&1; then
        echo "✅ Ollama service is running"
        # Show available models
        MODEL_COUNT=$(ollama list 2>/dev/null | tail -n +2 | wc -l)
        if [ "$MODEL_COUNT" -gt 0 ]; then
            echo "✅ $MODEL_COUNT AI model(s) available"
        else
            echo "⚠️  No AI models installed - you can install them through the web interface"
        fi
    else
        echo "⚠️  Ollama found but service may not be running"
        echo "   Starting Ollama service..."
        # Try to start Ollama service in background
        ollama serve >/dev/null 2>&1 &
        sleep 3
        # Check again
        if ollama list >/dev/null 2>&1; then
            echo "✅ Ollama service started successfully"
        else
            echo "❌ Failed to start Ollama service automatically"
            echo "   You may need to start it manually: ollama serve"
        fi
    fi
else
    echo "❌ Ollama not found in PATH"
    echo "   Common installation locations checked:"
    echo "   - /usr/local/bin/ollama"
    echo "   - /opt/homebrew/bin/ollama" 
    echo "   - $HOME/.ollama/bin/ollama"
    echo ""
    echo "   AI features will not work without Ollama"
    echo "   You can install Ollama from: https://ollama.ai"
fi

# Check if streamlit is installed
if ! command -v streamlit &> /dev/null; then
    echo "📦 Installing Streamlit..."
    pip install streamlit plotly pillow psutil watchdog
fi

# Kill any existing streamlit processes
pkill -f "streamlit run SRA_web_app" 2>/dev/null || true

# Function to open browser based on OS
open_browser() {
    local url="http://localhost:8502"
    echo "🌐 Opening browser automatically..."
    
    # Detect OS and open browser
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        open "$url"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        if command -v xdg-open &> /dev/null; then
            xdg-open "$url"
        elif command -v gnome-open &> /dev/null; then
            gnome-open "$url"
        fi
    elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
        # Windows
        start "$url"
    fi
}

# Start browser opener in background (after 3 seconds delay)
(sleep 3 && open_browser) &

# Start the enhanced web app
echo "🌐 Starting web interface on http://localhost:8502"
echo "📊 Features available:"
echo "   • Live progress tracking with animations"
echo "   • Automatic visualization generation"
echo "   • Interactive data explorer with filtering"
echo "   • Upload/load existing CSV files"
echo "   • Enhanced search finding more samples"
echo "   • Custom filename support for visualizations"
if command -v ollama >/dev/null 2>&1; then
    echo "   • AI model management and installation"
else
    echo "   • AI features (disabled - Ollama not found)"
fi
echo ""
echo "🔗 Browser will open automatically in 3 seconds..."
echo "📖 Or manually visit: http://localhost:8502"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Export PATH for the Streamlit process
export PATH="$PATH"
streamlit run SRA_web_app_enhanced.py --server.headless true --server.port 8502

echo "👋 Enhanced web app stopped." 