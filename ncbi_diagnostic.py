#!/usr/bin/env python3
"""
NCBI E-utilities Diagnostic Script
==================================
This script helps diagnose PATH issues with NCBI E-utilities installation.
Run this script to troubleshoot "esearch not found" errors.

Usage: python3 ncbi_diagnostic.py
"""

import os
import subprocess
import sys
from pathlib import Path
import platform


def print_header():
    """Print diagnostic header."""
    print("="*70)
    print("🔧 NCBI E-UTILITIES DIAGNOSTIC SCRIPT")
    print("="*70)
    print(f"Platform: {platform.system()} {platform.release()}")
    print(f"Architecture: {platform.machine()}")
    print(f"Python: {sys.version}")
    print("="*70)
    print()


def check_current_path():
    """Check current PATH configuration."""
    print("📍 CURRENT PATH CONFIGURATION")
    print("-" * 35)
    
    current_path = os.environ.get("PATH", "")
    if current_path:
        print("Current PATH entries:")
        for i, path_entry in enumerate(current_path.split(os.pathsep), 1):
            print(f"  {i:2d}. {path_entry}")
    else:
        print("❌ No PATH environment variable found!")
    print()


def check_ncbi_installation_locations():
    """Check common NCBI E-utilities installation locations."""
    print("📂 CHECKING INSTALLATION LOCATIONS")
    print("-" * 38)
    
    script_dir = Path(__file__).parent.absolute()
    home_dir = Path.home()
    
    locations_to_check = [
        ("/usr/local/bin", "Homebrew Intel Mac"),
        ("/opt/homebrew/bin", "Homebrew Apple Silicon Mac"),
        (str(home_dir / "edirect"), "Official NCBI installation"),
        (str(script_dir / "bin"), "Project local symlinks"),
        (str(script_dir / "ncbi_tools" / "edirect"), "Project local installation"),
        ("/usr/bin", "System binaries"),
        (str(home_dir / ".local" / "bin"), "User local binaries"),
    ]
    
    found_any = False
    
    for location, description in locations_to_check:
        location_path = Path(location)
        if location_path.exists():
            print(f"✅ {description}")
            print(f"   Path: {location}")
            
            # Check for specific NCBI tools
            ncbi_tools = ["esearch", "efetch", "elink", "einfo", "esummary"]
            found_tools = []
            
            for tool in ncbi_tools:
                tool_path = location_path / tool
                if tool_path.exists():
                    found_tools.append(tool)
            
            if found_tools:
                print(f"   Tools found: {', '.join(found_tools)}")
                found_any = True
            else:
                print(f"   No NCBI tools found in this location")
            print()
        else:
            print(f"❌ {description}")
            print(f"   Path: {location} (not found)")
            print()
    
    if not found_any:
        print("⚠️  No NCBI E-utilities found in any standard location!")
        print()


def test_ncbi_tools():
    """Test if NCBI tools can be executed."""
    print("🧪 TESTING NCBI TOOLS EXECUTION")
    print("-" * 34)
    
    required_tools = ["esearch", "efetch"]
    working_tools = []
    
    for tool in required_tools:
        print(f"Testing {tool}...")
        
        # Try to find the tool
        try:
            which_result = subprocess.run(["which", tool], capture_output=True, text=True)
            if which_result.returncode == 0:
                tool_path = which_result.stdout.strip()
                print(f"  ✅ Found at: {tool_path}")
                
                # Test if the tool actually works
                try:
                    test_result = subprocess.run([tool, "-help"], capture_output=True, text=True, timeout=10)
                    if test_result.returncode == 0:
                        print(f"  ✅ {tool} is working correctly")
                        working_tools.append(tool)
                    else:
                        print(f"  ❌ {tool} found but returned error code {test_result.returncode}")
                        if test_result.stderr:
                            print(f"     Error: {test_result.stderr.strip()}")
                except subprocess.TimeoutExpired:
                    print(f"  ❌ {tool} timed out (may be hanging)")
                except Exception as e:
                    print(f"  ❌ Error testing {tool}: {e}")
            else:
                print(f"  ❌ Not found in PATH")
                
        except Exception as e:
            print(f"  ❌ Error checking {tool}: {e}")
        
        print()
    
    return working_tools


def provide_installation_recommendations():
    """Provide installation recommendations based on platform."""
    print("💡 INSTALLATION RECOMMENDATIONS")
    print("-" * 35)
    
    system = platform.system().lower()
    
    if system == "darwin":  # macOS
        print("For macOS, try these methods in order:")
        print()
        print("1. Official NCBI Installation (RECOMMENDED):")
        print('   sh -c "$(curl -fsSL https://ftp.ncbi.nlm.nih.gov/entrez/entrezdirect/install-edirect.sh)"')
        print("   This installs to $HOME/edirect")
        print()
        print("2. Using Homebrew (if available):")
        print("   brew install ncbi-edirect")
        print()
        print("3. Using the SRA-LLM installer:")
        print("   python3 install_sra_analyzer.py")
        print()
        
    elif system == "linux":
        print("For Linux, try these methods:")
        print()
        print("1. Official NCBI Installation (RECOMMENDED):")
        print('   sh -c "$(curl -fsSL https://ftp.ncbi.nlm.nih.gov/entrez/entrezdirect/install-edirect.sh)"')
        print("   Or with wget:")
        print('   sh -c "$(wget -q https://ftp.ncbi.nlm.nih.gov/entrez/entrezdirect/install-edirect.sh -O -)"')
        print()
        print("2. Using the SRA-LLM installer:")
        print("   python3 install_sra_analyzer.py")
        print()
        
    elif system == "windows":
        print("For Windows, try these methods:")
        print()
        print("1. Using WSL (Windows Subsystem for Linux):")
        print('   sh -c "$(curl -fsSL https://ftp.ncbi.nlm.nih.gov/entrez/entrezdirect/install-edirect.sh)"')
        print()
        print("2. Using Git Bash or Cygwin:")
        print('   sh -c "$(curl -fsSL https://ftp.ncbi.nlm.nih.gov/entrez/entrezdirect/install-edirect.sh)"')
        print()
        print("3. Using the SRA-LLM installer:")
        print("   python3 install_sra_analyzer.py")
        print()
    
    print("After installation:")
    print("• Restart your terminal")
    print("• Or run: source ~/.bashrc (Linux) or source ~/.zshrc (macOS)")
    print("• Run this diagnostic script again to verify")
    print()


def check_shell_profiles():
    """Check shell profile files for PATH modifications."""
    print("📝 CHECKING SHELL PROFILES")
    print("-" * 28)
    
    home_dir = Path.home()
    shell_profiles = [
        home_dir / ".bashrc",
        home_dir / ".bash_profile",
        home_dir / ".zshrc",
        home_dir / ".profile",
    ]
    
    edirect_references = []
    
    for profile in shell_profiles:
        if profile.exists():
            try:
                content = profile.read_text()
                if "edirect" in content.lower():
                    print(f"✅ {profile.name}: Contains edirect references")
                    # Show relevant lines
                    lines = content.split('\n')
                    for i, line in enumerate(lines, 1):
                        if "edirect" in line.lower():
                            print(f"   Line {i}: {line.strip()}")
                            edirect_references.append((profile.name, line.strip()))
                else:
                    print(f"❌ {profile.name}: No edirect references")
            except Exception as e:
                print(f"⚠️  {profile.name}: Error reading file ({e})")
        else:
            print(f"❌ {profile.name}: File does not exist")
    
    print()
    
    if edirect_references:
        print("Found PATH modifications:")
        for profile, line in edirect_references:
            print(f"  {profile}: {line}")
    else:
        print("⚠️  No edirect PATH modifications found in shell profiles")
    
    print()


def main():
    """Run complete diagnostic."""
    print_header()
    
    check_current_path()
    check_ncbi_installation_locations()
    working_tools = test_ncbi_tools()
    check_shell_profiles()
    
    print("📊 DIAGNOSTIC SUMMARY")
    print("-" * 21)
    
    if len(working_tools) >= 2:
        print("🎉 SUCCESS: NCBI E-utilities are properly installed and working!")
        print(f"   Working tools: {', '.join(working_tools)}")
        print("   You should be able to run SRA-LLM without issues.")
    else:
        print("❌ PROBLEM: NCBI E-utilities are not properly installed or accessible")
        print(f"   Working tools: {working_tools if working_tools else 'None'}")
        print("   The SRA-LLM script will fail to download data.")
        print()
        provide_installation_recommendations()
    
    print()
    print("="*70)


if __name__ == "__main__":
    main() 