#!/usr/bin/env python3
"""
Simple NCBI Tools Test Script
=============================
This script tests NCBI tools execution and provides detailed error information.
Use this on the computer having issues to get specific error details.

Usage: python3 test_ncbi_tools.py
"""

import os
import subprocess
import sys
from pathlib import Path
import stat


def test_specific_tool(tool_path):
    """Test a specific tool path with detailed diagnostics."""
    print(f"\n{'='*60}")
    print(f"TESTING: {tool_path}")
    print(f"{'='*60}")
    
    tool_path_obj = Path(tool_path)
    
    # 1. Check if file exists
    if not tool_path_obj.exists():
        print(f"❌ File does not exist: {tool_path}")
        return False
    
    print(f"✅ File exists")
    
    # 2. Check permissions
    file_stat = tool_path_obj.stat()
    mode = file_stat.st_mode
    
    print(f"📋 File permissions: {stat.filemode(mode)}")
    
    if mode & stat.S_IEXEC:
        print(f"✅ File is executable")
    else:
        print(f"❌ File is NOT executable")
        print(f"🔧 Trying to fix permissions...")
        try:
            os.chmod(tool_path, mode | stat.S_IEXEC)
            print(f"✅ Fixed permissions")
        except Exception as e:
            print(f"❌ Could not fix permissions: {e}")
            return False
    
    # 3. Check file size
    size = file_stat.st_size
    print(f"📏 File size: {size:,} bytes")
    
    if size < 1000:
        print(f"⚠️  File seems very small - might be corrupted")
    
    # 4. Check file type
    try:
        with open(tool_path, 'rb') as f:
            first_bytes = f.read(50)
            
        if first_bytes.startswith(b'#!/'):
            print(f"📄 File type: Script")
            # Read shebang
            with open(tool_path, 'r') as f:
                shebang = f.readline().strip()
                print(f"   Shebang: {shebang}")
                
                # Check if the interpreter exists
                if shebang.startswith('#!'):
                    interpreter = shebang[2:].split()[0]
                    if not Path(interpreter).exists():
                        print(f"❌ Interpreter not found: {interpreter}")
                        return False
                    else:
                        print(f"✅ Interpreter found: {interpreter}")
                        
        elif first_bytes.startswith(b'\x7fELF'):
            print(f"📄 File type: ELF executable (Linux)")
        elif first_bytes.startswith(b'\xcf\xfa\xed\xfe') or first_bytes.startswith(b'\xca\xfe\xba\xbe'):
            print(f"📄 File type: Mach-O executable (macOS)")
        else:
            print(f"📄 File type: Unknown or binary")
            print(f"   First bytes: {first_bytes[:20].hex()}")
            
    except Exception as e:
        print(f"❌ Could not read file: {e}")
        return False
    
    # 5. Check if it's a symlink
    if tool_path_obj.is_symlink():
        target = tool_path_obj.readlink()
        print(f"🔗 Symlink target: {target}")
        if not target.exists():
            print(f"❌ Symlink target does not exist!")
            return False
        else:
            print(f"✅ Symlink target exists")
    
    # 6. Test execution
    print(f"\n🧪 TESTING EXECUTION")
    print(f"-" * 20)
    
    try:
        print(f"Running: {tool_path} -help")
        result = subprocess.run(
            [str(tool_path), "-help"], 
            capture_output=True, 
            text=True, 
            timeout=30,
            cwd=str(tool_path_obj.parent)  # Run from tool's directory
        )
        
        print(f"Exit code: {result.returncode}")
        
        if result.returncode == 0:
            print(f"✅ Tool executed successfully!")
            print(f"📤 Output length: {len(result.stdout)} characters")
            
            # Show first few lines of output
            output_lines = result.stdout.split('\n')
            print(f"📄 First few lines of output:")
            for i, line in enumerate(output_lines[:5]):
                if line.strip():
                    print(f"   {i+1}: {line}")
            
            return True
        else:
            print(f"❌ Tool failed with exit code {result.returncode}")
            
            if result.stdout:
                print(f"📤 STDOUT:")
                for line in result.stdout.split('\n')[:10]:
                    if line.strip():
                        print(f"   {line}")
            
            if result.stderr:
                print(f"📥 STDERR:")
                for line in result.stderr.split('\n')[:10]:
                    if line.strip():
                        print(f"   {line}")
            
            return False
            
    except subprocess.TimeoutExpired:
        print(f"❌ Tool execution timed out (30 seconds)")
        print(f"   This suggests the tool is hanging or very slow")
        return False
        
    except FileNotFoundError as e:
        print(f"❌ File not found error: {e}")
        return False
        
    except PermissionError as e:
        print(f"❌ Permission error: {e}")
        return False
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        print(f"   Error type: {type(e).__name__}")
        return False


def find_ncbi_tools():
    """Find all NCBI tools on the system."""
    print("🔍 SEARCHING FOR NCBI TOOLS")
    print("="*40)
    
    # Based on user's information
    search_locations = [
        "/users/llchsy/edirect",  # User mentioned this location
        str(Path.home() / "edirect"),  # Standard location
        str(Path.home() / "Downloads" / "SRA_LLM-main"),  # User mentioned this
        "/usr/local/bin",
        "/opt/homebrew/bin",
        "./bin",
        "./ncbi_tools/edirect"
    ]
    
    tools_to_find = ["esearch", "efetch"]
    found_tools = {}
    
    for tool in tools_to_find:
        found_tools[tool] = []
        print(f"\nSearching for {tool}...")
        
        for location in search_locations:
            try:
                location_path = Path(location)
                if location_path.exists():
                    # Direct check
                    tool_path = location_path / tool
                    if tool_path.exists():
                        found_tools[tool].append(str(tool_path))
                        print(f"  ✅ Found: {tool_path}")
                    
                    # Recursive search
                    for found_file in location_path.rglob(tool):
                        if str(found_file) not in found_tools[tool]:
                            found_tools[tool].append(str(found_file))
                            print(f"  ✅ Found: {found_file}")
                            
            except Exception as e:
                print(f"  ⚠️  Error searching {location}: {e}")
    
    return found_tools


def main():
    """Main function."""
    print("🧬 NCBI TOOLS EXECUTION TEST")
    print("="*50)
    print(f"Platform: {os.name}")
    print(f"Python: {sys.version}")
    print(f"Working directory: {os.getcwd()}")
    print()
    
    # Find all tools
    found_tools = find_ncbi_tools()
    
    # Test each found tool
    working_tools = []
    failed_tools = []
    
    for tool_name, tool_paths in found_tools.items():
        if not tool_paths:
            print(f"\n❌ No instances of {tool_name} found")
            continue
            
        print(f"\n📋 Found {len(tool_paths)} instance(s) of {tool_name}")
        
        for tool_path in tool_paths:
            if test_specific_tool(tool_path):
                working_tools.append(tool_path)
            else:
                failed_tools.append(tool_path)
    
    # Summary
    print(f"\n" + "="*60)
    print(f"SUMMARY")
    print(f"="*60)
    
    if working_tools:
        print(f"✅ WORKING TOOLS ({len(working_tools)}):")
        for tool in working_tools:
            print(f"   {tool}")
        
        # Provide PATH solution
        working_dirs = set(str(Path(tool).parent) for tool in working_tools)
        if working_dirs:
            print(f"\n💡 SOLUTION - Add to your PATH:")
            for dir_path in working_dirs:
                print(f"   export PATH=\"{dir_path}:$PATH\"")
    
    if failed_tools:
        print(f"\n❌ FAILED TOOLS ({len(failed_tools)}):")
        for tool in failed_tools:
            print(f"   {tool}")
    
    if not working_tools:
        print(f"\n❌ NO WORKING TOOLS FOUND")
        print(f"   You need to install NCBI E-utilities")
        print(f"   Run: python3 install_ncbi_tools.py")


if __name__ == "__main__":
    main() 