#!/bin/bash

# Enhanced SRA Web App Launcher
# This script starts the enhanced web interface with all bug fixes

echo "🚀 Starting Enhanced SRA Web App..."

# Check if virtual environment exists
if [ ! -d "sra_env" ]; then
    echo "❌ Virtual environment 'sra_env' not found!"
    echo "Please run the installer first: ./install_sra_analyzer.py"
    exit 1
fi

# Activate virtual environment
source sra_env/bin/activate

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
echo ""
echo "🔗 Browser will open automatically in 3 seconds..."
echo "📖 Or manually visit: http://localhost:8502"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

streamlit run SRA_web_app_enhanced.py --server.headless true --server.port 8502

echo "👋 Enhanced web app stopped." 