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
    """Test if NCBI tools can be executed with detailed diagnostics."""
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
                
                # Check file properties
                check_file_properties(tool_path)
                
                # Test if the tool actually works
                try:
                    print(f"  🔍 Testing execution of {tool}...")
                    test_result = subprocess.run([tool, "-help"], capture_output=True, text=True, timeout=15)
                    
                    if test_result.returncode == 0:
                        print(f"  ✅ {tool} is working correctly")
                        print(f"     Output length: {len(test_result.stdout)} characters")
                        working_tools.append(tool)
                    else:
                        print(f"  ❌ {tool} found but returned error code {test_result.returncode}")
                        if test_result.stderr:
                            print(f"     STDERR: {test_result.stderr.strip()}")
                        if test_result.stdout:
                            print(f"     STDOUT: {test_result.stdout.strip()[:200]}...")
                        
                        # Try to diagnose the problem
                        diagnose_execution_failure(tool_path, test_result)
                        
                except subprocess.TimeoutExpired:
                    print(f"  ❌ {tool} timed out (may be hanging or very slow)")
                    print(f"     This could indicate missing dependencies or network issues")
                except Exception as e:
                    print(f"  ❌ Error testing {tool}: {e}")
                    print(f"     Exception type: {type(e).__name__}")
                    
            else:
                print(f"  ❌ Not found in PATH")
                # Search for the tool in common locations
                search_for_tool(tool)
                
        except Exception as e:
            print(f"  ❌ Error checking {tool}: {e}")
        
        print()
    
    return working_tools

def check_file_properties(file_path):
    """Check detailed properties of a file."""
    try:
        file_path_obj = Path(file_path)
        
        # Check if file exists and is executable
        if file_path_obj.exists():
            print(f"     File exists: ✅")
            
            # Check permissions
            import stat
            file_stat = file_path_obj.stat()
            mode = file_stat.st_mode
            
            if mode & stat.S_IEXEC:
                print(f"     Executable: ✅")
            else:
                print(f"     Executable: ❌ (permissions: {stat.filemode(mode)})")
            
            # Check file size
            size = file_stat.st_size
            print(f"     File size: {size} bytes")
            if size < 1000:
                print(f"     ⚠️  File seems very small, might be corrupted or a symlink")
            
            # Check if it's a symlink
            if file_path_obj.is_symlink():
                target = file_path_obj.readlink()
                print(f"     Symlink target: {target}")
                if not target.exists():
                    print(f"     ❌ Symlink target does not exist!")
            
            # Try to read first few bytes to check file type
            try:
                with open(file_path, 'rb') as f:
                    first_bytes = f.read(20)
                    if first_bytes.startswith(b'#!/'):
                        print(f"     File type: Script (starts with shebang)")
                        # Read the shebang line
                        f.seek(0)
                        shebang = f.readline().decode('utf-8', errors='ignore').strip()
                        print(f"     Shebang: {shebang}")
                    elif first_bytes.startswith(b'\x7fELF'):
                        print(f"     File type: ELF executable")
                    elif first_bytes.startswith(b'\xcf\xfa\xed\xfe'):
                        print(f"     File type: Mach-O executable (macOS)")
                    else:
                        print(f"     File type: Unknown ({first_bytes[:10].hex()})")
            except Exception as e:
                print(f"     Could not read file: {e}")
                
        else:
            print(f"     File exists: ❌")
            
    except Exception as e:
        print(f"     Error checking file properties: {e}")

def diagnose_execution_failure(tool_path, test_result):
    """Diagnose why a tool execution failed."""
    print(f"  🔍 Diagnosing execution failure...")
    
    # Check if it's a dependency issue
    if "library" in test_result.stderr.lower() or "dylib" in test_result.stderr.lower():
        print(f"     Possible missing dependencies detected")
        
        # Try to check dependencies (macOS)
        try:
            otool_result = subprocess.run(["otool", "-L", tool_path], capture_output=True, text=True)
            if otool_result.returncode == 0:
                print(f"     Dependencies:")
                for line in otool_result.stdout.split('\n')[1:6]:  # Show first 5 deps
                    if line.strip():
                        print(f"       {line.strip()}")
        except:
            pass
    
    # Check if it's a permission issue
    if "permission denied" in test_result.stderr.lower():
        print(f"     Permission issue detected")
        try:
            subprocess.run(["chmod", "+x", tool_path], check=True)
            print(f"     Fixed execute permission")
        except:
            print(f"     Could not fix permissions")
    
    # Check if it's an architecture issue
    if "bad cpu type" in test_result.stderr.lower() or "exec format error" in test_result.stderr.lower():
        print(f"     Architecture mismatch detected")
        try:
            file_result = subprocess.run(["file", tool_path], capture_output=True, text=True)
            if file_result.returncode == 0:
                print(f"     File info: {file_result.stdout.strip()}")
        except:
            pass

def search_for_tool(tool_name):
    """Search for a tool in common locations."""
    print(f"  🔍 Searching for {tool_name} in common locations...")
    
    search_paths = [
        "/usr/local/bin",
        "/opt/homebrew/bin",
        str(Path.home() / "edirect"),
        "/usr/bin",
        str(Path.home() / "Downloads"),
        ".",
        "./bin",
        "./ncbi_tools/edirect"
    ]
    
    found_locations = []
    
    for search_path in search_paths:
        try:
            search_path_obj = Path(search_path)
            if search_path_obj.exists():
                # Look for the tool
                tool_files = list(search_path_obj.glob(f"**/{tool_name}"))
                for tool_file in tool_files:
                    found_locations.append(str(tool_file))
                    print(f"     Found: {tool_file}")
        except:
            pass
    
    if not found_locations:
        print(f"     No instances of {tool_name} found in common locations")
    
    return found_locations


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


def test_all_found_tools():
    """Test all found instances of NCBI tools, not just the ones in PATH."""
    print("🔍 TESTING ALL FOUND TOOL INSTANCES")
    print("-" * 38)
    
    tools_to_test = ["esearch", "efetch"]
    all_working_tools = []
    
    for tool in tools_to_test:
        print(f"Searching for all instances of {tool}...")
        found_tools = search_for_tool(tool)
        
        if found_tools:
            for tool_path in found_tools:
                print(f"\n  Testing: {tool_path}")
                
                # Check file properties
                check_file_properties(tool_path)
                
                # Test execution
                try:
                    print(f"  🔍 Testing execution...")
                    test_result = subprocess.run([tool_path, "-help"], capture_output=True, text=True, timeout=15)
                    
                    if test_result.returncode == 0:
                        print(f"  ✅ This instance of {tool} is working!")
                        print(f"     Output length: {len(test_result.stdout)} characters")
                        all_working_tools.append(tool_path)
                    else:
                        print(f"  ❌ This instance failed with error code {test_result.returncode}")
                        if test_result.stderr:
                            print(f"     STDERR: {test_result.stderr.strip()}")
                        diagnose_execution_failure(tool_path, test_result)
                        
                except subprocess.TimeoutExpired:
                    print(f"  ❌ This instance timed out")
                except Exception as e:
                    print(f"  ❌ Error testing this instance: {e}")
        else:
            print(f"  No instances of {tool} found")
        
        print()
    
    return all_working_tools

def main():
    """Run complete diagnostic."""
    print_header()
    
    check_current_path()
    check_ncbi_installation_locations()
    working_tools = test_ncbi_tools()
    
    # If PATH tools don't work, test all found instances
    if len(working_tools) < 2:
        print("\n" + "="*70)
        print("PATH tools not working. Testing all found instances...")
        print("="*70)
        all_working_tools = test_all_found_tools()
        
        if all_working_tools:
            print("🔧 WORKING TOOL INSTANCES FOUND:")
            for tool_path in all_working_tools:
                print(f"   {tool_path}")
            print("\n💡 SOLUTION: Add the working tool directory to your PATH")
            working_dir = str(Path(all_working_tools[0]).parent)
            print(f"   export PATH=\"{working_dir}:$PATH\"")
            print(f"   Or copy tools to a directory already in PATH")
    
    check_shell_profiles()
    
    print("\n📊 DIAGNOSTIC SUMMARY")
    print("-" * 21)
    
    if len(working_tools) >= 2:
        print("🎉 SUCCESS: NCBI E-utilities are properly installed and working!")
        print(f"   Working tools: {', '.join(working_tools)}")
        print("   You should be able to run SRA-LLM without issues.")
    else:
        print("❌ PROBLEM: NCBI E-utilities are not properly installed or accessible")
        print(f"   Working tools in PATH: {working_tools if working_tools else 'None'}")
        print("   The SRA-LLM script will fail to download data.")
        print()
        provide_installation_recommendations()
    
    print()
    print("="*70)


if __name__ == "__main__":
    main() 