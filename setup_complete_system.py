#!/usr/bin/env python3
"""
SRA Metadata Analyzer - Complete System Setup
This script ensures all necessary files are in place and creates samples if missing.
"""

import os
import sys
from pathlib import Path
import platform

def create_sample_keyword_file():
    """Create a sample keyword.csv file if it doesn't exist."""
    keyword_file = Path("keyword.csv")
    
    if not keyword_file.exists():
        print("📝 Creating sample keyword.csv file...")
        
        sample_keywords = [
            "SearchTerm",
            "prostate cancer",
            "breast cancer", 
            "BRCA1",
            "BRCA2",
            "TP53",
            "ChIP-seq",
            "RNA-seq",
            "single cell",
            "transcriptome"
        ]
        
        try:
            with open(keyword_file, 'w', newline='') as f:
                for keyword in sample_keywords:
                    f.write(f"{keyword}\n")
            
            print("✅ Created sample keyword.csv with example research terms")
            print("   You can edit this file to add your own keywords")
            return True
        except Exception as e:
            print(f"❌ Failed to create keyword.csv: {e}")
            return False
    else:
        print("✅ keyword.csv already exists")
        return True

def create_launcher_scripts():
    """Create launcher scripts if they don't exist."""
    system = platform.system().lower()
    
    if system == "windows":
        create_windows_launchers()
    else:
        create_unix_launchers()

def create_windows_launchers():
    """Create Windows launcher scripts."""
    
    # Web interface launcher
    web_launcher = Path("run_web_interface.bat")
    if not web_launcher.exists():
        web_content = '''@echo off
echo 🌐 SRA Metadata Analyzer - Web Interface
echo =======================================

cd /d "%~dp0"

if not exist "sra_env\\Scripts\\activate.bat" (
    echo ❌ Virtual environment not found!
    echo Please run the installer first: install_windows.bat
    pause
    exit /b 1
)

call "sra_env\\Scripts\\activate.bat"

if not exist "SRA_web_app_fixed.py" (
    echo ❌ Web app script not found!
    echo Please ensure SRA_web_app_fixed.py is in this directory.
    pause
    exit /b 1
)

echo Starting web interface...
echo Your browser will open at http://localhost:8501
streamlit run SRA_web_app_fixed.py

pause'''
        
        try:
            with open(web_launcher, 'w') as f:
                f.write(web_content)
            print("✅ Created run_web_interface.bat")
        except Exception as e:
            print(f"❌ Failed to create web launcher: {e}")
    
    # Command line launcher
    cli_launcher = Path("run_sra_analyzer.bat")
    if not cli_launcher.exists():
        cli_content = '''@echo off
echo 🧬 SRA Metadata Analyzer - Command Line
echo ====================================

cd /d "%~dp0"

if not exist "sra_env\\Scripts\\activate.bat" (
    echo ❌ Virtual environment not found!
    echo Please run the installer first: install_windows.bat
    pause
    exit /b 1
)

call "sra_env\\Scripts\\activate.bat"

if not exist "SRA_fetch_1LLM_improved.py" (
    echo ❌ Main analysis script not found!
    echo Please ensure SRA_fetch_1LLM_improved.py is in this directory.
    pause
    exit /b 1
)

if not exist "keyword.csv" (
    echo ❌ keyword.csv not found!
    echo Please create a keyword.csv file with your search terms.
    pause
    exit /b 1
)

echo Starting analysis...
echo.
echo Usage examples:
echo   Basic: python SRA_fetch_1LLM_improved.py --keywords keyword.csv --output results.csv
echo   Custom model: python SRA_fetch_1LLM_improved.py --keywords keyword.csv --output results.csv --model llama3.1:8b
echo.
python SRA_fetch_1LLM_improved.py --keywords keyword.csv --output result_prompt_fallback.csv

pause'''
        
        try:
            with open(cli_launcher, 'w') as f:
                f.write(cli_content)
            print("✅ Created run_sra_analyzer.bat")
        except Exception as e:
            print(f"❌ Failed to create CLI launcher: {e}")

def create_unix_launchers():
    """Create Unix launcher scripts."""
    
    # Web interface launcher
    web_launcher = Path("run_web_interface.sh")
    if not web_launcher.exists():
        web_content = '''#!/bin/bash
echo "🌐 SRA Metadata Analyzer - Web Interface"
echo "======================================="

cd "$(dirname "$0")"

if [ ! -f "sra_env/bin/activate" ]; then
    echo "❌ Virtual environment not found!"
    echo "Please run the installer first: ./install_mac.sh"
    read -p "Press any key to exit..."
    exit 1
fi

source "sra_env/bin/activate"

if [ ! -f "SRA_web_app_fixed.py" ]; then
    echo "❌ Web app script not found!"
    echo "Please ensure SRA_web_app_fixed.py is in this directory."
    read -p "Press any key to exit..."
    exit 1
fi

echo "Starting web interface..."
echo "Your browser will open at http://localhost:8501"
streamlit run SRA_web_app_fixed.py'''
        
        try:
            with open(web_launcher, 'w') as f:
                f.write(web_content)
            os.chmod(web_launcher, 0o755)
            print("✅ Created run_web_interface.sh")
        except Exception as e:
            print(f"❌ Failed to create web launcher: {e}")
    
    # Command line launcher
    cli_launcher = Path("run_sra_analyzer.sh")
    if not cli_launcher.exists():
        cli_content = '''#!/bin/bash
echo "🧬 SRA Metadata Analyzer - Command Line"
echo "===================================="

cd "$(dirname "$0")"

if [ ! -f "sra_env/bin/activate" ]; then
    echo "❌ Virtual environment not found!"
    echo "Please run the installer first: ./install_mac.sh"
    read -p "Press any key to exit..."
    exit 1
fi

source "sra_env/bin/activate"

if [ ! -f "SRA_fetch_1LLM_improved.py" ]; then
    echo "❌ Main analysis script not found!"
    echo "Please ensure SRA_fetch_1LLM_improved.py is in this directory."
    read -p "Press any key to exit..."
    exit 1
fi

if [ ! -f "keyword.csv" ]; then
    echo "❌ keyword.csv not found!"
    echo "Please create a keyword.csv file with your search terms."
    read -p "Press any key to exit..."
    exit 1
fi

echo "Starting analysis..."
echo
echo "Usage examples:"
echo "  Basic: python SRA_fetch_1LLM_improved.py --keywords keyword.csv --output results.csv"
echo "  Custom model: python SRA_fetch_1LLM_improved.py --keywords keyword.csv --output results.csv --model llama3.1:8b"
echo
python SRA_fetch_1LLM_improved.py --keywords keyword.csv --output result_prompt_fallback.csv'''
        
        try:
            with open(cli_launcher, 'w') as f:
                f.write(cli_content)
            os.chmod(cli_launcher, 0o755)
            print("✅ Created run_sra_analyzer.sh")
        except Exception as e:
            print(f"❌ Failed to create CLI launcher: {e}")

def check_required_files():
    """Check if all required files are present."""
    required_files = [
        "SRA_fetch_1LLM_improved.py",
        "visualize_results.py", 
        "SRA_web_app_fixed.py",
        "install_sra_analyzer.py"
    ]
    
    missing_files = []
    for file in required_files:
        if not Path(file).exists():
            missing_files.append(file)
    
    if missing_files:
        print("❌ Missing required files:")
        for file in missing_files:
            print(f"   • {file}")
        print("\nPlease ensure all files are in the same directory.")
        return False
    else:
        print("✅ All required files found")
        return True

def create_startup_guide():
    """Create a simple startup guide."""
    guide_file = Path("START_HERE.txt")
    
    if not guide_file.exists():
        system = platform.system().lower()
        
        if system == "windows":
            guide_content = """🧬 SRA Metadata Analyzer - Quick Start Guide

STEP 1: INSTALL EVERYTHING
Double-click: install_windows.bat
(This may take 10-30 minutes)

STEP 2: INSTALL AI MODEL
Open Command Prompt and run:
ollama pull qwen3:8b

STEP 3: START ANALYZING
For Web Interface (Recommended):
Double-click: run_web_interface.bat

For Command Line (Advanced):
Double-click: run_sra_analyzer.bat

TROUBLESHOOTING:
- If installation fails, try running as Administrator
- If Python not found, install from python.org
- Check INSTALLATION_GUIDE.md for detailed help

SUPPORT:
- Read README.md for usage instructions
- Check INSTALLATION_GUIDE.md for setup help
- Ensure all files are in the same folder

Happy analyzing! 🚀"""
        else:
            guide_content = """🧬 SRA Metadata Analyzer - Quick Start Guide

STEP 1: INSTALL EVERYTHING
Double-click: install_mac.sh
(This may take 10-30 minutes)

STEP 2: INSTALL AI MODEL
Open Terminal and run:
ollama pull qwen3:8b

STEP 3: START ANALYZING
For Web Interface (Recommended):
Double-click: run_web_interface.sh

For Command Line (Advanced):
Run in Terminal: ./run_sra_analyzer.sh

TROUBLESHOOTING:
- If permission denied, run: chmod +x install_mac.sh
- If Python not found, install via Homebrew or python.org
- Check INSTALLATION_GUIDE.md for detailed help

SUPPORT:
- Read README.md for usage instructions
- Check INSTALLATION_GUIDE.md for setup help
- Ensure all files are in the same folder

Happy analyzing! 🚀"""
        
        try:
            with open(guide_file, 'w') as f:
                f.write(guide_content)
            print("✅ Created START_HERE.txt with quick start guide")
        except Exception as e:
            print(f"❌ Failed to create startup guide: {e}")

def main():
    """Main setup function."""
    print("🧬 SRA Metadata Analyzer - Complete System Setup")
    print("=" * 55)
    print()
    
    # Check if we're in the right directory
    if not check_required_files():
        input("Press Enter to exit...")
        return False
    
    # Create all necessary files
    print("\n🔧 Setting up system files...")
    
    # Create sample files
    create_sample_keyword_file()
    
    # Create launcher scripts
    print("\n🚀 Creating launcher scripts...")
    create_launcher_scripts()
    
    # Create startup guide
    print("\n📚 Creating documentation...")
    create_startup_guide()
    
    print(f"\n✅ System setup complete!")
    print("\n📋 Next steps:")
    print("1. Run the installer:")
    
    system = platform.system().lower()
    if system == "windows":
        print("   • Double-click: install_windows.bat")
        print("2. After installation, start the web interface:")
        print("   • Double-click: run_web_interface.bat")
    else:
        print("   • Double-click: install_mac.sh")
        print("2. After installation, start the web interface:")
        print("   • Double-click: run_web_interface.sh")
    
    print("3. Install an AI model:")
    print("   • Open Terminal/Command Prompt")
    print("   • Run: ollama pull qwen3:8b")
    
    print("\n📖 For detailed instructions, see:")
    print("   • START_HERE.txt - Quick start guide")
    print("   • INSTALLATION_GUIDE.md - Comprehensive setup")
    print("   • README.md - Usage instructions")
    
    print("\n🎯 You're ready to begin installation!")
    
    if system == "windows":
        input("Press Enter to finish...")
    else:
        input("Press Enter to finish...")
    
    return True

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n❌ Setup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        sys.exit(1) 