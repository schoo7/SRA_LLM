#!/bin/bash
echo "🧬 SRA Metadata Analyzer"
echo "========================"

cd "/Users/sc3525/Library/CloudStorage/OneDrive-YaleUniversity/LLM_sra/SRA_LLM"

# Activate virtual environment
source "/Users/sc3525/Library/CloudStorage/OneDrive-YaleUniversity/LLM_sra/SRA_LLM/sra_env/bin/activate"

# Check if analysis script exists
if [ ! -f "SRA_fetch_1LLM_improved.py" ]; then
    echo "❌ Main analysis script not found!"
    echo "Please ensure SRA_fetch_1LLM_improved.py is in the same directory."
    exit 1
fi

# Run the main analysis script
echo "Starting analysis..."
python SRA_fetch_1LLM_improved.py "$@"
