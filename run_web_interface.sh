#!/bin/bash

# SRA-LLM Enhanced Web Interface Launcher
# ======================================
# Includes PATH configuration and Ollama service management
# Prevents "No models found" issues after analysis completion

echo "🌐 SRA-LLM - Enhanced Web Interface"
echo "=================================="

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

echo "📍 Working directory: $SCRIPT_DIR"

# Enhanced PATH configuration for Ollama detection
echo "🔧 Configuring PATH for Ollama..."
export PATH="/usr/local/bin:/opt/homebrew/bin:~/.ollama/bin:$PATH"

# Function to find Ollama binary
find_ollama_binary() {
    local ollama_paths=(
        "/usr/local/bin/ollama"
        "/opt/homebrew/bin/ollama"
        "~/.ollama/bin/ollama"
        "/Applications/Ollama.app/Contents/Resources/ollama"
    )
    
    for path in "${ollama_paths[@]}"; do
        if [ -f "$path" ]; then
            echo "$path"
            return 0
        fi
    done
    return 1
}

# Function to check and start Ollama service
ensure_ollama_service() {
    echo "🔍 Checking Ollama service status..."
    
    # Check if Ollama service is running (port 11434)
    if ! curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
        echo "🚀 Starting Ollama service..."
        
        # Find Ollama binary
        OLLAMA_BIN=$(find_ollama_binary)
        if [ $? -eq 0 ]; then
            echo "✅ Found Ollama at: $OLLAMA_BIN"
            # Start Ollama service in background
            nohup "$OLLAMA_BIN" serve > /dev/null 2>&1 &
            sleep 3
            
            # Verify service started
            if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
                echo "✅ Ollama service started successfully"
            else
                echo "⚠️ Ollama service may need more time to start"
            fi
        else
            echo "⚠️ Ollama binary not found in standard locations"
            echo "   Models may not be available until Ollama is properly installed"
        fi
    else
        echo "✅ Ollama service is already running"
    fi
}

# Start Ollama service if needed
ensure_ollama_service

# Check if virtual environment exists
if [ ! -d "sra_env" ]; then
    echo "❌ Virtual environment not found!"
    echo "Please run install_mac.command first to set up the environment."
    exit 1
fi

# Activate virtual environment and preserve PATH
echo "🐍 Activating virtual environment..."
source "sra_env/bin/activate"

# Re-export PATH to ensure it's available in virtual environment
export PATH="/usr/local/bin:/opt/homebrew/bin:~/.ollama/bin:$PATH"

# Check if web app script exists
if [ ! -f "SRA_web_app_enhanced.py" ]; then
    echo "❌ Enhanced web app script not found!"
    echo "Please ensure SRA_web_app_enhanced.py is in the same directory."
    exit 1
fi

# Final Ollama verification before starting web interface
echo "🔍 Final Ollama service verification..."
if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
    echo "✅ Ollama service confirmed running"
else
    echo "⚠️ Ollama service not responding - models may not be available"
    echo "   You can still use the web interface to install and manage models"
fi

# Run the enhanced web interface
echo ""
echo "🚀 Starting enhanced web interface..."
echo "Features: Real-time updates, interactive visualizations, data explorer"
echo "Your browser will open automatically at http://localhost:8502"
echo ""

# Try to open browser automatically after a short delay
if command -v open >/dev/null 2>&1; then
    (sleep 3 && open http://localhost:8502) &
elif command -v xdg-open >/dev/null 2>&1; then
    (sleep 3 && xdg-open http://localhost:8502) &
fi

# Start Streamlit with the enhanced web app
streamlit run SRA_web_app_enhanced.py --server.port 8502
