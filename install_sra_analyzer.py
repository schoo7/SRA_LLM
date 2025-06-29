#!/usr/bin/env python3
"""
SRA Metadata Analyzer - Comprehensive Installer
Cross-platform installer for Windows and macOS that sets up everything needed.
"""

import os
import sys
import subprocess
import platform
import urllib.request
import shutil
import tempfile
import json
import time
from pathlib import Path
import zipfile

class SRAAnalyzerInstaller:
    def __init__(self):
        self.system = platform.system().lower()
        self.arch = platform.machine().lower()
        self.python_min_version = (3, 8)
        self.install_dir = Path.cwd()
        self.venv_dir = self.install_dir / "sra_env"
        
        # Color codes for cross-platform output
        self.colors = {
            'green': '\033[92m' if self.system != 'windows' else '',
            'red': '\033[91m' if self.system != 'windows' else '',
            'yellow': '\033[93m' if self.system != 'windows' else '',
            'blue': '\033[94m' if self.system != 'windows' else '',
            'end': '\033[0m' if self.system != 'windows' else ''
        }
        
        print(f"{self.colors['blue']}🧬 SRA Metadata Analyzer - Comprehensive Installer{self.colors['end']}")
        print("=" * 60)
        print(f"Detected OS: {platform.system()} {platform.release()}")
        print(f"Architecture: {self.arch}")
        print()

    def print_step(self, step_num, total_steps, message):
        """Print a formatted step message."""
        print(f"{self.colors['blue']}[{step_num}/{total_steps}] {message}{self.colors['end']}")

    def print_success(self, message):
        """Print a success message."""
        print(f"{self.colors['green']}✅ {message}{self.colors['end']}")

    def print_error(self, message):
        """Print an error message."""
        print(f"{self.colors['red']}❌ {message}{self.colors['end']}")

    def print_warning(self, message):
        """Print a warning message."""
        print(f"{self.colors['yellow']}⚠️ {message}{self.colors['end']}")

    def check_python_installation(self):
        """Check if Python is installed and meets minimum version requirements."""
        try:
            version = sys.version_info
            if version >= self.python_min_version:
                self.print_success(f"Python {version.major}.{version.minor}.{version.micro} found ✓")
                return True
            else:
                self.print_warning(f"Python {version.major}.{version.minor} found but minimum {self.python_min_version[0]}.{self.python_min_version[1]} required")
                return False
        except:
            self.print_error("Python not found")
            return False

    def install_python_windows(self):
        """Install Python on Windows."""
        print("\n📥 Installing Python for Windows...")
        
        # Download Python installer
        python_version = "3.11.8"
        if "64" in platform.machine() or "x86_64" in platform.machine():
            python_url = f"https://www.python.org/ftp/python/{python_version}/python-{python_version}-amd64.exe"
        else:
            python_url = f"https://www.python.org/ftp/python/{python_version}/python-{python_version}.exe"
        
        installer_path = Path.cwd() / f"python-{python_version}-installer.exe"
        
        try:
            print(f"Downloading Python {python_version}...")
            urllib.request.urlretrieve(python_url, installer_path)
            
            print("Running Python installer...")
            print("📋 IMPORTANT: When the installer opens:")
            print("   ✓ Check 'Add Python to PATH'")
            print("   ✓ Check 'Install for all users' (if you have admin rights)")
            print("   ✓ Click 'Install Now'")
            
            # Run installer
            subprocess.run([str(installer_path), "/quiet", "InstallAllUsers=1", "PrependPath=1", "Include_test=0"], check=True)
            
            # Clean up
            installer_path.unlink()
            self.print_success("Python installed successfully!")
            
            # Verify installation
            time.sleep(3)
            result = subprocess.run(["python", "--version"], capture_output=True, text=True)
            if result.returncode == 0:
                self.print_success(f"Python verification: {result.stdout.strip()}")
                return True
            else:
                self.print_error("Python installation verification failed")
                return False
                
        except Exception as e:
            self.print_error(f"Failed to install Python: {e}")
            return False

    def install_python_mac(self):
        """Install Python on macOS."""
        print("\n📥 Installing Python for macOS...")
        
        # Check if Homebrew is installed
        try:
            subprocess.run(["brew", "--version"], capture_output=True, check=True)
            homebrew_available = True
        except (subprocess.CalledProcessError, FileNotFoundError):
            homebrew_available = False
        
        if homebrew_available:
            print("Using Homebrew to install Python...")
            try:
                subprocess.run(["brew", "install", "python@3.11"], check=True)
                self.print_success("Python installed via Homebrew!")
                return True
            except subprocess.CalledProcessError as e:
                self.print_error(f"Homebrew installation failed: {e}")
        
        # Fallback: Download and install Python manually
        print("Installing Python from official installer...")
        python_version = "3.11.8"
        
        if "arm" in self.arch or "aarch64" in self.arch:
            python_url = f"https://www.python.org/ftp/python/{python_version}/python-{python_version}-macos11.pkg"
        else:
            python_url = f"https://www.python.org/ftp/python/{python_version}/python-{python_version}-macosx10.9.pkg"
        
        installer_path = Path.cwd() / f"python-{python_version}-installer.pkg"
        
        try:
            print(f"Downloading Python {python_version}...")
            urllib.request.urlretrieve(python_url, installer_path)
            
            print("Running Python installer...")
            subprocess.run(["sudo", "installer", "-pkg", str(installer_path), "-target", "/"], check=True)
            
            # Clean up
            installer_path.unlink()
            self.print_success("Python installed successfully!")
            return True
            
        except Exception as e:
            self.print_error(f"Failed to install Python: {e}")
            return False

    def create_virtual_environment(self):
        """Create a virtual environment."""
        print(f"\n🔧 Creating virtual environment at {self.venv_dir}...")
        
        try:
            if self.venv_dir.exists():
                print("Removing existing virtual environment...")
                shutil.rmtree(self.venv_dir)
            
            subprocess.run([sys.executable, "-m", "venv", str(self.venv_dir)], check=True)
            self.print_success("Virtual environment created!")
            return True
        except subprocess.CalledProcessError as e:
            self.print_error(f"Failed to create virtual environment: {e}")
            return False

    def get_venv_python(self):
        """Get the Python executable path in the virtual environment."""
        if self.system == "windows":
            return self.venv_dir / "Scripts" / "python.exe"
        else:
            return self.venv_dir / "bin" / "python"

    def get_venv_pip(self):
        """Get the pip executable path in the virtual environment."""
        if self.system == "windows":
            return self.venv_dir / "Scripts" / "pip.exe"
        else:
            return self.venv_dir / "bin" / "pip"

    def install_python_dependencies(self):
        """Install required Python packages."""
        print("\n📦 Installing Python dependencies...")
        
        pip_path = self.get_venv_pip()
        
        # Define requirements for enhanced SRA-LLM
        requirements = [
            # Core dependencies for data processing
            "tqdm>=4.64.0",              # Progress bars
            "requests>=2.31.0",          # HTTP requests for GEO data
            "pandas>=2.0.0",             # Data manipulation and analysis
            "numpy>=1.24.0",             # Numerical computing
            
            # Visualization dependencies
            "matplotlib>=3.7.0",         # Plotting and visualization
            "wordcloud>=1.9.0",          # Word cloud generation
            "plotly>=5.17.0",            # Interactive plotting
            
            # Web interface dependencies
            "streamlit>=1.28.0",         # Web app framework
            
            # LLM and AI dependencies
            "langchain-ollama>=0.1.0",   # Ollama integration for LangChain
            
            # Image processing for web interface
            "Pillow>=10.0.0",            # Image processing
            
            # System utilities
            "psutil>=5.9.0",             # System and process utilities
            "watchdog>=6.0.0",           # File monitoring for better Streamlit performance
        ]
        
        # Upgrade pip first
        try:
            subprocess.run([str(pip_path), "install", "--upgrade", "pip"], check=True)
            self.print_success("Pip upgraded successfully!")
        except subprocess.CalledProcessError as e:
            self.print_warning(f"Failed to upgrade pip: {e}")
        
        # Install requirements
        for requirement in requirements:
            try:
                print(f"Installing {requirement}...")
                subprocess.run([str(pip_path), "install", requirement], check=True)
            except subprocess.CalledProcessError as e:
                self.print_error(f"Failed to install {requirement}: {e}")
                return False
        
        self.print_success("All Python dependencies installed!")
        return True

    def install_ollama(self):
        """Install Ollama."""
        print("\n🤖 Installing Ollama...")
        
        if self.system == "windows":
            return self.install_ollama_windows()
        elif self.system == "darwin":
            return self.install_ollama_mac()
        else:
            self.print_error("Ollama installation not supported on this OS")
            return False

    def install_ollama_windows(self):
        """Install Ollama on Windows."""
        try:
            # Check if Ollama is already installed
            result = subprocess.run(["ollama", "--version"], capture_output=True, text=True)
            if result.returncode == 0:
                self.print_success("Ollama already installed!")
                return True
        except FileNotFoundError:
            pass
        
        print("Downloading Ollama for Windows...")
        ollama_url = "https://ollama.com/download/OllamaSetup.exe"
        installer_path = Path.cwd() / "OllamaSetup.exe"
        
        try:
            urllib.request.urlretrieve(ollama_url, installer_path)
            
            print("Running Ollama installer...")
            print("📋 The Ollama installer will open automatically.")
            print("   Just follow the installation wizard.")
            
            subprocess.run([str(installer_path)], check=True)
            installer_path.unlink()
            
            self.print_success("Ollama installation completed!")
            return True
            
        except Exception as e:
            self.print_error(f"Failed to install Ollama: {e}")
            return False

    def install_ollama_mac(self):
        """Install Ollama on macOS."""
        try:
            # Check if Ollama is already installed
            result = subprocess.run(["ollama", "--version"], capture_output=True, text=True)
            if result.returncode == 0:
                self.print_success("Ollama already installed!")
                return True
        except FileNotFoundError:
            pass
        
        # Try Homebrew first
        try:
            subprocess.run(["brew", "--version"], capture_output=True, check=True)
            print("Installing Ollama via Homebrew...")
            subprocess.run(["brew", "install", "ollama"], check=True)
            self.print_success("Ollama installed via Homebrew!")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        # Fallback: Download installer
        print("Downloading Ollama for macOS...")
        ollama_url = "https://ollama.com/download/Ollama-darwin.zip"
        
        installer_path = Path.cwd() / "Ollama-darwin.zip"
        
        try:
            urllib.request.urlretrieve(ollama_url, installer_path)
            
            # Extract and install
            with zipfile.ZipFile(installer_path, 'r') as zip_ref:
                zip_ref.extractall(Path.cwd())
            
            print("📋 Please drag Ollama.app to your Applications folder")
            print("   Then run 'ollama' from Terminal to complete setup")
            
            installer_path.unlink()
            self.print_success("Ollama downloaded!")
            return True
            
        except Exception as e:
            self.print_error(f"Failed to install Ollama: {e}")
            return False

    def install_ncbi_tools(self):
        """Install NCBI E-utilities."""
        print("\n🧬 Installing NCBI E-utilities...")
        
        if self.system == "windows":
            return self.install_ncbi_tools_windows()
        elif self.system == "darwin":
            return self.install_ncbi_tools_mac()
        else:
            self.print_error("NCBI tools installation not supported on this OS")
            return False

    def install_ncbi_tools_windows(self):
        """Install NCBI E-utilities on Windows."""
        try:
            # Check if already installed
            result = subprocess.run(["efetch", "-help"], capture_output=True, text=True)
            if result.returncode == 0:
                self.print_success("NCBI E-utilities already installed!")
                return True
        except FileNotFoundError:
            pass
        
        print("Installing NCBI E-utilities for Windows...")
        
        # Create tools directory
        tools_dir = self.install_dir / "ncbi_tools"
        tools_dir.mkdir(exist_ok=True)
        
        # Download E-utilities
        eutils_url = "https://ftp.ncbi.nlm.nih.gov/entrez/entrezdirect/versions/current/edirect_pc.exe"
        installer_path = tools_dir / "edirect_pc.exe"
        
        try:
            urllib.request.urlretrieve(eutils_url, installer_path)
            
            # Run installer
            os.chdir(tools_dir)
            subprocess.run([str(installer_path)], check=True)
            
            # Add to PATH
            eutils_path = tools_dir / "edirect"
            self.add_to_path_windows(str(eutils_path))
            
            self.print_success("NCBI E-utilities installed!")
            return True
            
        except Exception as e:
            self.print_error(f"Failed to install NCBI E-utilities: {e}")
            return False

    def install_ncbi_tools_mac(self):
        """Install NCBI E-utilities on macOS."""
        try:
            # Check if already installed
            result = subprocess.run(["efetch", "-help"], capture_output=True, text=True)
            if result.returncode == 0:
                self.print_success("NCBI E-utilities already installed!")
                return True
        except FileNotFoundError:
            pass
        
        print("Installing NCBI E-utilities for macOS...")
        
        # Create tools directory
        tools_dir = self.install_dir / "ncbi_tools"
        tools_dir.mkdir(exist_ok=True)
        
        # Download and install E-utilities
        try:
            os.chdir(tools_dir)
            subprocess.run([
                "bash", "-c", 
                "curl -s https://ftp.ncbi.nlm.nih.gov/entrez/entrezdirect/install-edirect.sh | bash"
            ], check=True)
            
            # Add to PATH
            eutils_path = tools_dir / "edirect"
            self.add_to_path_mac(str(eutils_path))
            
            self.print_success("NCBI E-utilities installed!")
            return True
            
        except Exception as e:
            self.print_error(f"Failed to install NCBI E-utilities: {e}")
            return False

    def add_to_path_windows(self, path):
        """Add directory to Windows PATH."""
        try:
            print(f"📋 Please add this to your PATH manually: {path}")
            print("   Instructions:")
            print("   1. Open System Properties > Environment Variables")
            print("   2. Edit the PATH variable")
            print(f"   3. Add: {path}")
        except Exception as e:
            self.print_warning(f"Could not modify PATH automatically: {e}")

    def add_to_path_mac(self, path):
        """Add directory to macOS PATH."""
        try:
            shell_rc = Path.home() / ".zshrc"
            if not shell_rc.exists():
                shell_rc = Path.home() / ".bash_profile"
            
            with open(shell_rc, "a") as f:
                f.write(f'\nexport PATH="{path}:$PATH"\n')
            
            print(f"Added {path} to {shell_rc}")
            print("Please run 'source ~/.zshrc' or restart your terminal")
            
        except Exception as e:
            self.print_warning(f"Could not modify PATH automatically: {e}")

    def create_launcher_scripts(self):
        """Create easy-to-use launcher scripts."""
        print("\n🚀 Creating launcher scripts...")
        
        # Python executable in venv
        venv_python = self.get_venv_python()
        
        if self.system == "windows":
            # Windows batch file
            launcher_content = f"""@echo off
echo 🧬 SRA Metadata Analyzer
echo ========================

cd /d "{self.install_dir}"

REM Activate virtual environment
call "{self.venv_dir}\\Scripts\\activate.bat"

REM Check if analysis script exists
if not exist "SRA_fetch_1LLM_improved.py" (
    echo ❌ Main analysis script not found!
    echo Please ensure SRA_fetch_1LLM_improved.py is in the same directory.
    pause
    exit /b 1
)

REM Run the main analysis script
echo Starting analysis...
python SRA_fetch_1LLM_improved.py %*

pause
"""
            launcher_path = self.install_dir / "run_sra_analyzer.bat"
            
            # Web app launcher
            web_launcher_content = f"""@echo off
echo 🌐 SRA-LLM - Enhanced Web Interface
echo ==================================

cd /d "{self.install_dir}"

REM Activate virtual environment
call "{self.venv_dir}\\Scripts\\activate.bat"

REM Check if web app script exists
if not exist "SRA_web_app_enhanced.py" (
    echo ❌ Enhanced web app script not found!
    echo Please ensure SRA_web_app_enhanced.py is in the same directory.
    pause
    exit /b 1
)

REM Run the enhanced web interface
echo Starting enhanced web interface...
echo Your browser will open automatically at http://localhost:8502
echo Features: Real-time updates, interactive visualizations, data explorer
streamlit run SRA_web_app_enhanced.py --server.port 8502

pause
"""
            web_launcher_path = self.install_dir / "run_web_interface.bat"
            
        else:  # macOS/Linux
            # Shell script
            launcher_content = f"""#!/bin/bash
echo "🧬 SRA Metadata Analyzer"
echo "========================"

cd "{self.install_dir}"

# Activate virtual environment
source "{self.venv_dir}/bin/activate"

# Check if analysis script exists
if [ ! -f "SRA_fetch_1LLM_improved.py" ]; then
    echo "❌ Main analysis script not found!"
    echo "Please ensure SRA_fetch_1LLM_improved.py is in the same directory."
    exit 1
fi

# Run the main analysis script
echo "Starting analysis..."
python SRA_fetch_1LLM_improved.py "$@"
"""
            launcher_path = self.install_dir / "run_sra_analyzer.sh"
            
            # Web app launcher
            web_launcher_content = f"""#!/bin/bash
echo "🌐 SRA-LLM - Enhanced Web Interface"
echo "=================================="

cd "{self.install_dir}"

# Activate virtual environment
source "{self.venv_dir}/bin/activate"

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
"""
            web_launcher_path = self.install_dir / "run_web_interface.sh"
        
        # Write launcher files
        try:
            with open(launcher_path, "w") as f:
                f.write(launcher_content)
            
            with open(web_launcher_path, "w") as f:
                f.write(web_launcher_content)
            
            # Make executable on Unix systems
            if self.system != "windows":
                os.chmod(launcher_path, 0o755)
                os.chmod(web_launcher_path, 0o755)
            
            self.print_success(f"Launcher scripts created:")
            print(f"   📄 {launcher_path.name} - Command line interface")
            print(f"   🌐 {web_launcher_path.name} - Web interface")
            return True
            
        except Exception as e:
            self.print_error(f"Failed to create launcher scripts: {e}")
            return False

    def create_requirements_file(self):
        """Create requirements.txt file."""
        requirements_content = """# SRA-LLM - Enhanced Requirements
# ================================
# This file lists all Python packages required for the enhanced SRA-LLM
# Install with: pip install -r requirements.txt

# Core dependencies for data processing
tqdm>=4.64.0              # Progress bars
requests>=2.31.0          # HTTP requests for GEO data
pandas>=2.0.0             # Data manipulation and analysis
numpy>=1.24.0             # Numerical computing

# Visualization dependencies
matplotlib>=3.7.0         # Plotting and visualization
wordcloud>=1.9.0          # Word cloud generation
plotly>=5.17.0            # Interactive plotting

# Web interface dependencies
streamlit>=1.28.0         # Web app framework

# LLM and AI dependencies
langchain-ollama>=0.1.0   # Ollama integration for LangChain

# Image processing for web interface
Pillow>=10.0.0            # Image processing

# System utilities
psutil>=5.9.0             # System and process utilities
watchdog>=6.0.0           # File monitoring for better Streamlit performance
"""
        
        try:
            with open(self.install_dir / "requirements.txt", "w") as f:
                f.write(requirements_content)
            self.print_success("requirements.txt created")
            return True
        except Exception as e:
            self.print_error(f"Failed to create requirements.txt: {e}")
            return False

    def run_installation(self):
        """Run the complete installation process."""
        total_steps = 8
        
        # Step 1: Check Python
        self.print_step(1, total_steps, "Checking Python installation")
        if not self.check_python_installation():
            print("\n🔧 Python installation required...")
            if self.system == "windows":
                if not self.install_python_windows():
                    return False
            elif self.system == "darwin":
                if not self.install_python_mac():
                    return False
            else:
                self.print_error("Automatic Python installation not supported on this OS")
                return False
        
        # Step 2: Create virtual environment
        self.print_step(2, total_steps, "Creating virtual environment")
        if not self.create_virtual_environment():
            return False
        
        # Step 3: Install Python dependencies
        self.print_step(3, total_steps, "Installing Python dependencies")
        if not self.install_python_dependencies():
            return False
        
        # Step 4: Install Ollama
        self.print_step(4, total_steps, "Installing Ollama")
        if not self.install_ollama():
            self.print_warning("Ollama installation failed - you can install it manually later")
        
        # Step 5: Install NCBI tools
        self.print_step(5, total_steps, "Installing NCBI E-utilities")
        if not self.install_ncbi_tools():
            self.print_warning("NCBI tools installation failed - you can install them manually later")
        
        # Step 6: Create requirements file
        self.print_step(6, total_steps, "Creating requirements file")
        self.create_requirements_file()
        
        # Step 7: Create launcher scripts
        self.print_step(7, total_steps, "Creating launcher scripts")
        if not self.create_launcher_scripts():
            return False
        
        # Step 8: Final setup
        self.print_step(8, total_steps, "Finalizing installation")
        self.print_installation_summary()
        
        return True

    def print_installation_summary(self):
        """Print installation summary and next steps."""
        print(f"\n{self.colors['green']}🎉 Installation Complete!{self.colors['end']}")
        print("=" * 60)
        
        print("\n📋 Next Steps:")
        print("1. Make sure these files are in the same directory:")
        print("   • SRA_fetch_1LLM_improved.py")
        print("   • visualize_results.py") 
        print("   • SRA_web_app_fixed.py")
        print("   • keyword.csv (your keywords file)")
        
        print("\n🚀 How to Run:")
        if self.system == "windows":
            print("   • Double-click 'run_web_interface.bat' for web interface")
            print("   • Double-click 'run_sra_analyzer.bat' for command line")
        else:
            print("   • Double-click 'run_web_interface.sh' for web interface")
            print("   • Run './run_sra_analyzer.sh' for command line")
        
        print("\n🤖 Ollama Setup (if needed):")
        print("1. Open Terminal/Command Prompt")
        print("2. Run: ollama pull qwen3:8b")
        print("3. This downloads the AI model (may take a few minutes)")
        
        print("\n📚 Documentation:")
        print("• README.md - Complete usage instructions")
        print("• PROCESS_MANAGEMENT_GUIDE.md - Advanced usage")
        
        print(f"\n{self.colors['blue']}🎯 You're all set! Happy analyzing!{self.colors['end']}")

def main():
    """Main installer function."""
    installer = SRAAnalyzerInstaller()
    
    try:
        if installer.run_installation():
            sys.exit(0)
        else:
            installer.print_error("Installation failed!")
            sys.exit(1)
    except KeyboardInterrupt:
        installer.print_warning("Installation cancelled by user")
        sys.exit(1)
    except Exception as e:
        installer.print_error(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 