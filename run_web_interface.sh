#!/bin/bash
echo "🌐 SRA-LLM - Enhanced Web Interface"
echo "=================================="

cd "/Users/sc3525/Library/CloudStorage/OneDrive-YaleUniversity/LLM_sra/SRA_LLM"

# Activate virtual environment
source "/Users/sc3525/Library/CloudStorage/OneDrive-YaleUniversity/LLM_sra/SRA_LLM/sra_env/bin/activate"

# Check if web app script exists
if [ ! -f "SRA_web_app_enhanced.py" ]; then
    echo "❌ Enhanced web app script not found!"
    echo "Please ensure SRA_web_app_enhanced.py is in the same directory."
    exit 1
fi

# Run the enhanced web interface
echo "Starting enhanced web interface..."
echo "Your browser will open automatically at http://localhost:8502"
echo "Features: Real-time updates, interactive visualizations, data explorer"

# Try to open browser automatically
if command -v open >/dev/null 2>&1; then
    sleep 3 && open http://localhost:8502 &
elif command -v xdg-open >/dev/null 2>&1; then
    sleep 3 && xdg-open http://localhost:8502 &
fi

streamlit run SRA_web_app_enhanced.py --server.port 8502
