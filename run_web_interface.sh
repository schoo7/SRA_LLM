#!/bin/bash
echo "🌐 SRA-LLM - Enhanced Web Interface"
echo "=================================="

cd "/Users/sc3525/Library/CloudStorage/OneDrive-YaleUniversity/LLM_sra/SRA_LLM"

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

# Activate virtual environment
source "/Users/sc3525/Library/CloudStorage/OneDrive-YaleUniversity/LLM_sra/SRA_LLM/sra_env/bin/activate"

# Preserve PATH in virtual environment (important for Ollama access)
export PATH="$PATH"

# Check Ollama availability
echo "🔍 Checking Ollama installation..."
if command -v ollama >/dev/null 2>&1; then
    echo "✅ Ollama found at: $(which ollama)"
    # Try to check if Ollama service is running
    if ollama list >/dev/null 2>&1; then
        echo "✅ Ollama service is running"
    else
        echo "⚠️  Ollama found but service may not be running"
        echo "   Starting Ollama service..."
        # Try to start Ollama service in background
        ollama serve >/dev/null 2>&1 &
        sleep 2
    fi
else
    echo "❌ Ollama not found in PATH"
    echo "   Common installation locations checked:"
    echo "   - /usr/local/bin/ollama"
    echo "   - /opt/homebrew/bin/ollama" 
    echo "   - $HOME/.ollama/bin/ollama"
    echo ""
    echo "   You can install Ollama from: https://ollama.ai"
fi

# Check if web app script exists
if [ ! -f "SRA_web_app_enhanced.py" ]; then
    echo "❌ Enhanced web app script not found!"
    echo "Please ensure SRA_web_app_enhanced.py is in the same directory."
    exit 1
fi

# Run the enhanced web interface
echo ""
echo "Starting enhanced web interface..."
echo "Your browser will open automatically at http://localhost:8502"
echo "Features: Real-time updates, interactive visualizations, data explorer"
echo ""

# Try to open browser automatically
if command -v open >/dev/null 2>&1; then
    sleep 3 && open http://localhost:8502 &
elif command -v xdg-open >/dev/null 2>&1; then
    sleep 3 && xdg-open http://localhost:8502 &
fi

# Export PATH for the Streamlit process
export PATH="$PATH"
streamlit run SRA_web_app_enhanced.py --server.port 8502
