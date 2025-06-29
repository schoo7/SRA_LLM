# 🚀 SRA-LLM Installation Guide

**Easy-to-follow instructions for installing SRA-LLM on your computer**

## 📋 What You'll Get

After installation, you'll have:
- **🖥️ Web Interface**: Point-and-click browser interface at `http://localhost:8502`
- **📊 Auto-Visualizations**: Publication-ready charts and graphs
- **🤖 AI Analysis**: Local LLM models for metadata processing
- **⚡ Real-time Updates**: Live progress tracking during analysis
- **📈 Data Explorer**: Interactive filtering and analysis tools

## 🎯 Quick Start (Recommended)

### Option 1: One-Click Installation

**For Windows:**
1. Download all project files to a folder (e.g., Desktop/SRA_LLM)
2. Right-click on `install_windows.bat` → "Run as administrator"
3. Wait for installation to complete (5-10 minutes)
4. Double-click `run_web_interface.bat` to start!

**For macOS:**
1. Download all project files to a folder
2. Double-click `Start_SRA_Web_App.command`
3. Browser opens automatically at `http://localhost:8502`

**For Linux/Any Platform:**
```bash
cd SRA_LLM
python3 install_sra_analyzer.py
```

### Option 2: Advanced Manual Installation

Follow the detailed steps below if you prefer manual control or the one-click method doesn't work.

---

## 🛠️ Manual Installation Steps

### Step 1: Install Python

**❓ What is Python?** Python is a programming language that our tool uses. You don't need to learn programming - just install it.

#### Windows:
1. Go to [python.org/downloads](https://python.org/downloads)
2. Download the latest Python 3.x version
3. **⚠️ CRITICAL**: During installation, check "Add Python to PATH"
4. Click "Install Now" and wait for completion

#### macOS:
1. Download Python from [python.org/downloads](https://python.org/downloads)
2. Open the `.pkg` file and follow the installer
3. Or use Homebrew: `brew install python@3.11`

#### Linux:
```bash
sudo apt update && sudo apt install python3 python3-pip python3-venv
```

**✅ Test Installation:**
Open Terminal/Command Prompt and type:
```bash
python3 --version
```
You should see something like "Python 3.11.x"

### Step 2: Install Ollama (AI Engine)

**❓ What is Ollama?** This is the AI system that reads scientific papers and extracts information.

#### All Platforms:
1. Visit [ollama.com](https://ollama.com)
2. Download for your operating system
3. Install following the instructions
4. Test by opening Terminal/Command Prompt and typing:
   ```bash
   ollama --version
   ```

### Step 3: Install NCBI E-utilities

**❓ What are NCBI E-utilities?** These tools let us download data from scientific databases.

#### Windows:
1. Download: [NCBI E-utilities for Windows](https://ftp.ncbi.nlm.nih.gov/entrez/entrezdirect/edirect.zip)
2. Extract to `C:\edirect`
3. Add `C:\edirect` to your PATH:
   - Search "Environment Variables" in Start menu
   - Edit "Path" → Add `C:\edirect`
   - Restart Command Prompt

#### macOS/Linux:
```bash
sh -c "$(curl -fsSL https://ftp.ncbi.nlm.nih.gov/entrez/entrezdirect/install-edirect.sh)"
```

**✅ Test Installation:**
```bash
esearch -db pubmed -query "cancer" | head
```

### Step 4: Set Up SRA-LLM

#### Create Project Directory:
```bash
# Navigate to where you want to install (e.g., Desktop)
cd ~/Desktop

# If you haven't already, download/clone the project
git clone https://github.com/schoo7/SRA_LLM.git
cd SRA_LLM
```

#### Create Virtual Environment:
```bash
python3 -m venv sra_env

# Activate it:
# Windows:
sra_env\Scripts\activate
# macOS/Linux:
source sra_env/bin/activate
```

#### Install Python Dependencies:
```bash
pip install -r requirements.txt
```

### Step 5: Download AI Models

Download the default AI model (this is automatic in the web interface, but you can do it manually):

```bash
ollama pull qwen3:8b
```

**Model Options:**
- `qwen3:8b` (8GB) - **Recommended** - Best balance of speed and accuracy
- `gemma3:4b` (3.3GB) - Faster, good for testing
- `gemma3:12b` (8.1GB) - Higher accuracy, slower

### Step 6: Start the Application

#### Method 1: Web Interface (Recommended)
```bash
streamlit run SRA_web_app_enhanced.py --server.port 8502
```
Then open your browser to: `http://localhost:8502`

#### Method 2: Command Line
```bash
python3 SRA_fetch_1LLM_improved.py --keywords keywords.csv --output my_results.csv
```

---

## 🖥️ Using the Web Interface

### Access the Interface
1. Open your browser
2. Go to `http://localhost:8502`
3. You'll see three tabs: **ANALYSIS**, **VISUALIZATIONS**, **DATA EXPLORER**

### Basic Usage

#### ANALYSIS Tab:
1. **Select AI Model**: Choose `qwen3:8b` (default)
2. **Enter Keywords**: Type research terms (e.g., "prostate cancer")
3. **Set Output File**: Choose filename for results
4. **Click "Start Analysis"**
5. **Watch Real-time Progress**: Live updates every 5 seconds

#### VISUALIZATIONS Tab:
- View auto-generated charts
- Species distributions, sequencing techniques
- Treatment word clouds
- Updates automatically during analysis

#### DATA EXPLORER Tab:
- Filter results by any column
- Generate custom charts
- Export filtered data
- Upload existing result files

---

## 🔧 Troubleshooting

### Common Issues

#### "qwen3:8b model not found"
```bash
ollama pull qwen3:8b
```

#### "esearch command not found"
- NCBI tools not installed or not in PATH
- Re-run NCBI installation
- Restart terminal/command prompt

#### "Port 8502 already in use"
```bash
# Kill existing Streamlit processes
pkill -f streamlit
# Or use different port
streamlit run SRA_web_app_enhanced.py --server.port 8503
```

#### "Module not found" errors
```bash
# Make sure virtual environment is activated
source sra_env/bin/activate  # macOS/Linux
sra_env\Scripts\activate     # Windows

# Reinstall dependencies
pip install -r requirements.txt
```

#### Web interface won't load
1. Check terminal for error messages
2. Ensure port 8502 is not blocked by firewall
3. Try different browser
4. Check if Python virtual environment is activated

#### Analysis stops or fails
1. Check internet connection (needed for NCBI data)
2. Verify Ollama is running: `ollama list`
3. Check if keywords are formatted correctly
4. Look at terminal output for specific errors

### Getting Help

- **GitHub Issues**: [SRA_LLM Issues](https://github.com/schoo7/SRA_LLM/issues)
- **Email**: siyuan.cheng@yale.edu
- **Documentation**: Check README.md for detailed feature descriptions

---

## 📊 Next Steps

### Try Example Analysis
1. Use the default `keywords.csv` file
2. Start with keywords like: "prostate cancer", "MDAPCA2B"
3. Expected results: 100+ samples with detailed metadata

### Customize for Your Research
1. Create your own `keywords.csv` file
2. Add your research terms (one per line)
3. Run analysis and explore visualizations

### Advanced Features
- **Command line usage** for automation
- **Custom AI models** for specific domains
- **HPC integration** for large-scale processing
- **Export options** for downstream analysis

---

**🎉 Congratulations! You now have SRA-LLM running on your system.**

**Quick test**: Open `http://localhost:8502`, enter "cancer" as a keyword, and start analysis to verify everything works!

---

*For more detailed information, see the main README.md file.* 