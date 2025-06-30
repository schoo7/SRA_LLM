#!/usr/bin/env python3
"""
NCBI E-utilities Quick Installer
=================================
This script installs NCBI E-utilities using the official method.
Run this if you're getting "esearch not found" errors.

Usage: python3 install_ncbi_tools.py
"""

import os
import subprocess
import sys
import platform
from pathlib import Path


def print_header():
    """Print installer header."""
    print("="*60)
    print("🧬 NCBI E-UTILITIES QUICK INSTALLER")
    print("="*60)
    print(f"Platform: {platform.system()} {platform.release()}")
    print("This will install NCBI E-utilities to $HOME/edirect")
    print("="*60)
    print()


def install_ncbi_tools():
    """Install NCBI E-utilities using the official method."""
    system = platform.system().lower()
    
    print("📥 Installing NCBI E-utilities...")
    print()
    
    if system in ["darwin", "linux"]:  # macOS or Linux
        install_unix_like()
    elif system == "windows":
        install_windows()
    else:
        print(f"❌ Unsupported system: {system}")
        return False
    
    return True


def install_unix_like():
    """Install on Unix-like systems (macOS, Linux)."""
    print("Using official NCBI installation method...")
    
    # Check if curl is available
    try:
        subprocess.run(["curl", "--version"], capture_output=True, check=True)
        has_curl = True
    except (subprocess.CalledProcessError, FileNotFoundError):
        has_curl = False
    
    # Check if wget is available  
    try:
        subprocess.run(["wget", "--version"], capture_output=True, check=True)
        has_wget = True
    except (subprocess.CalledProcessError, FileNotFoundError):
        has_wget = False
    
    if not has_curl and not has_wget:
        print("❌ Neither curl nor wget is available")
        print("Please install curl or wget first, then try again")
        return False
    
    try:
        if has_curl:
            print("Using curl to download and install...")
            install_cmd = 'sh -c "$(curl -fsSL https://ftp.ncbi.nlm.nih.gov/entrez/entrezdirect/install-edirect.sh)"'
        else:
            print("Using wget to download and install...")
            install_cmd = 'sh -c "$(wget -q https://ftp.ncbi.nlm.nih.gov/entrez/entrezdirect/install-edirect.sh -O -)"'
        
        print(f"Running: {install_cmd}")
        print()
        
        # Run the installation command
        result = subprocess.run(["bash", "-c", install_cmd], check=True)
        
        print("\n✅ Installation completed!")
        
        # Check if edirect directory was created
        edirect_path = Path.home() / "edirect"
        if edirect_path.exists():
            print(f"✅ NCBI tools installed to: {edirect_path}")
            
            # List installed tools
            tools = list(edirect_path.glob("e*"))
            if tools:
                print(f"✅ Available tools: {[t.name for t in tools[:5]]}...")
            
            # Update shell profiles
            update_shell_profiles()
            
            return True
        else:
            print("⚠️  Installation completed but edirect directory not found")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"❌ Installation failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def install_windows():
    """Install on Windows systems."""
    print("For Windows, please use one of these methods:")
    print()
    print("1. Windows Subsystem for Linux (WSL):")
    print("   - Open WSL terminal")
    print('   - Run: sh -c "$(curl -fsSL https://ftp.ncbi.nlm.nih.gov/entrez/entrezdirect/install-edirect.sh)"')
    print()
    print("2. Git Bash:")
    print("   - Open Git Bash terminal")
    print('   - Run: sh -c "$(curl -fsSL https://ftp.ncbi.nlm.nih.gov/entrez/entrezdirect/install-edirect.sh)"')
    print()
    print("3. PowerShell with Windows package manager:")
    print("   - This method is not yet implemented")
    print()
    print("❌ Automatic Windows installation not yet supported")
    print("Please use WSL or Git Bash for now")
    return False


def update_shell_profiles():
    """Update shell profiles to include edirect in PATH."""
    print("\n🔧 Updating shell profiles...")
    
    home_dir = Path.home()
    edirect_path = str(home_dir / "edirect")
    path_export = f'export PATH="{edirect_path}:$PATH"'
    
    # Shell profiles to update
    shell_profiles = [
        home_dir / ".bashrc",
        home_dir / ".bash_profile",
        home_dir / ".zshrc",
        home_dir / ".profile",
    ]
    
    updated_profiles = []
    
    for profile in shell_profiles:
        try:
            # Check if PATH export already exists
            if profile.exists():
                content = profile.read_text()
                if edirect_path in content:
                    print(f"✅ {profile.name}: Already contains edirect PATH")
                    continue
            
            # Add PATH export
            with open(profile, "a") as f:
                f.write(f"\n# Added by NCBI E-utilities installer\n")
                f.write(f"{path_export}\n")
            
            print(f"✅ Updated {profile.name}")
            updated_profiles.append(profile.name)
            
        except Exception as e:
            print(f"⚠️  Could not update {profile.name}: {e}")
    
    if updated_profiles:
        print(f"\n✅ Updated shell profiles: {', '.join(updated_profiles)}")
        print("🔄 Please restart your terminal or run:")
        print("   source ~/.bashrc  (Linux)")
        print("   source ~/.zshrc   (macOS)")
    else:
        print("\n⚠️  No shell profiles were updated")


def verify_installation():
    """Verify that the installation was successful."""
    print("\n🧪 Verifying installation...")
    
    # Update PATH for this session
    home_dir = Path.home()
    edirect_path = str(home_dir / "edirect")
    current_path = os.environ.get("PATH", "")
    if edirect_path not in current_path:
        os.environ["PATH"] = f"{edirect_path}:{current_path}"
    
    # Test tools
    required_tools = ["esearch", "efetch"]
    working_tools = []
    
    for tool in required_tools:
        try:
            # Try to find and test the tool
            result = subprocess.run([tool, "-help"], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print(f"✅ {tool}: Working correctly")
                working_tools.append(tool)
            else:
                print(f"❌ {tool}: Found but not working properly")
        except FileNotFoundError:
            print(f"❌ {tool}: Not found in PATH")
        except subprocess.TimeoutExpired:
            print(f"❌ {tool}: Timed out")
        except Exception as e:
            print(f"❌ {tool}: Error - {e}")
    
    if len(working_tools) == len(required_tools):
        print("\n🎉 SUCCESS! NCBI E-utilities are installed and working!")
        print("You can now run SRA-LLM without PATH errors.")
        return True
    else:
        print(f"\n⚠️  Partial success: {len(working_tools)}/{len(required_tools)} tools working")
        print("You may need to restart your terminal or check your PATH manually.")
        return False


def main():
    """Main installer function."""
    print_header()
    
    # Check if tools are already installed
    try:
        subprocess.run(["esearch", "-help"], capture_output=True, check=True, timeout=5)
        print("✅ NCBI E-utilities are already installed and working!")
        print("No installation needed.")
        return
    except:
        pass  # Tools not available, proceed with installation
    
    print("NCBI E-utilities not found. Installing...")
    print()
    
    if install_ncbi_tools():
        verify_installation()
    else:
        print("\n❌ Installation failed!")
        print()
        print("Manual installation instructions:")
        print("1. Open terminal")
        print('2. Run: sh -c "$(curl -fsSL https://ftp.ncbi.nlm.nih.gov/entrez/entrezdirect/install-edirect.sh)"')
        print("3. Restart terminal")
        print("4. Test with: esearch -help")
    
    print("\n" + "="*60)


if __name__ == "__main__":
    main() 