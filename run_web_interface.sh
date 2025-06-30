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

# Enhanced PATH configuration for Ollama and NCBI tools (system-wide first)
echo "🔧 Configuring PATH for Ollama and NCBI E-utilities..."
export PATH="/usr/local/bin:/opt/homebrew/bin:$HOME/edirect:~/.ollama/bin:$SCRIPT_DIR/ollama_local:$SCRIPT_DIR/bin:$SCRIPT_DIR/ncbi_tools/edirect:$PATH"

# Function to find Ollama binary
find_ollama_binary() {
    local ollama_paths=(
        "/usr/local/bin/ollama"
        "/opt/homebrew/bin/ollama"
        "~/.ollama/bin/ollama"
        "/Applications/Ollama.app/Contents/Resources/ollama"
        "$SCRIPT_DIR/ollama_local/ollama"
        "$SCRIPT_DIR/Ollama.app/Contents/Resources/ollama"
        "$SCRIPT_DIR/ollama_local/Ollama.app/Contents/Resources/ollama"
    )
    
    for path in "${ollama_paths[@]}"; do
        # Expand tilde manually for home directory
        expanded_path="${path/#\~/$HOME}"
        if [ -f "$expanded_path" ]; then
            echo "$expanded_path"
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

# Function to check NCBI E-utilities availability
check_ncbi_tools() {
    echo "🧬 Checking NCBI E-utilities availability..."
    
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
}

# Start Ollama service if needed
ensure_ollama_service

# Check NCBI tools availability
check_ncbi_tools

# Check if virtual environment exists
if [ ! -d "sra_env" ]; then
    echo "❌ Virtual environment not found!"
    echo "Please run install_mac.command first to set up the environment."
    exit 1
fi

# Activate virtual environment and preserve PATH
echo "🐍 Activating virtual environment..."
source "sra_env/bin/activate"

# Re-export PATH to ensure it's available in virtual environment (system-wide first)
export PATH="/usr/local/bin:/opt/homebrew/bin:$HOME/edirect:~/.ollama/bin:$SCRIPT_DIR/ollama_local:$SCRIPT_DIR/bin:$SCRIPT_DIR/ncbi_tools/edirect:$PATH"

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
