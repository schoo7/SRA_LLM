#!/usr/bin/env python3
"""
Advanced Ollama and SRA Process Cleanup Script
Stops all running Ollama model processes and SRA analysis scripts
"""

import os
import sys
import subprocess
import time
import argparse

def cleanup_ollama_processes(verbose=True):
    """Clean up any orphaned Ollama model processes and SRA script processes."""
    if verbose:
        print("🧹 Starting comprehensive Ollama and SRA cleanup...")
    
    cleaned_processes = []
    
    try:
        # Method 1: Clean up all Ollama runner processes
        if verbose:
            print("🔍 Searching for Ollama runner processes...")
        
        result = subprocess.run(['pgrep', '-f', 'ollama runner'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            pids = [pid.strip() for pid in result.stdout.strip().split('\n') if pid.strip()]
            if verbose:
                print(f"📋 Found {len(pids)} Ollama runner processes: {pids}")
            
            for pid in pids:
                try:
                    # Get process info before killing
                    ps_result = subprocess.run(['ps', '-p', pid, '-o', 'pid,ppid,command'], 
                                             capture_output=True, text=True)
                    if ps_result.returncode == 0:
                        process_info = ps_result.stdout.strip().split('\n')[-1]
                        if verbose:
                            print(f"🎯 Terminating Ollama process {pid}: {process_info}")
                        
                        # Graceful termination first
                        subprocess.run(['kill', '-TERM', pid], timeout=5)
                        time.sleep(2)
                        
                        # Check if still running
                        check_result = subprocess.run(['ps', '-p', pid], 
                                                    capture_output=True, text=True)
                        if check_result.returncode == 0:
                            if verbose:
                                print(f"💀 Force killing stubborn process {pid}...")
                            subprocess.run(['kill', '-KILL', pid], timeout=5)
                        
                        cleaned_processes.append(f"Ollama runner {pid}")
                        
                except (subprocess.TimeoutExpired, subprocess.CalledProcessError, ValueError):
                    if verbose:
                        print(f"⚠️  Process {pid} already gone or can't be killed")
        else:
            if verbose:
                print("✅ No Ollama runner processes found")
        
        # Method 2: Clean up SRA script processes (but not current process)
        current_pid = os.getpid()
        if verbose:
            print(f"🔍 Searching for SRA script processes (excluding current PID {current_pid})...")
        
        sra_result = subprocess.run(['pgrep', '-f', 'SRA_fetch_1LLM_improved.py'], 
                                  capture_output=True, text=True)
        if sra_result.returncode == 0:
            sra_pids = [pid.strip() for pid in sra_result.stdout.strip().split('\n') 
                       if pid.strip() and int(pid) != current_pid]
            if sra_pids:
                if verbose:
                    print(f"📋 Found {len(sra_pids)} SRA script processes: {sra_pids}")
                
                for pid in sra_pids:
                    try:
                        # Get process info
                        ps_result = subprocess.run(['ps', '-p', pid, '-o', 'pid,ppid,command'], 
                                                 capture_output=True, text=True)
                        if ps_result.returncode == 0:
                            process_info = ps_result.stdout.strip().split('\n')[-1]
                            if verbose:
                                print(f"🎯 Terminating SRA script {pid}: {process_info}")
                            
                            subprocess.run(['kill', '-TERM', pid], timeout=5)
                            time.sleep(2)
                            
                            # Force kill if still running
                            check_result = subprocess.run(['ps', '-p', pid], 
                                                        capture_output=True, text=True)
                            if check_result.returncode == 0:
                                if verbose:
                                    print(f"💀 Force killing SRA script {pid}...")
                                subprocess.run(['kill', '-KILL', pid], timeout=5)
                            
                            cleaned_processes.append(f"SRA script {pid}")
                            
                    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, ValueError):
                        if verbose:
                            print(f"⚠️  SRA process {pid} already gone or can't be killed")
            else:
                if verbose:
                    print("✅ No other SRA script processes found")
        else:
            if verbose:
                print("✅ No SRA script processes found")
        
        # Method 3: Kill processes using Ollama port
        if verbose:
            print("🔍 Checking for processes using Ollama port 11434...")
        
        try:
            port_result = subprocess.run(['lsof', '-ti', ':11434'], 
                                       capture_output=True, text=True)
            if port_result.returncode == 0:
                port_pids = [pid.strip() for pid in port_result.stdout.strip().split('\n') if pid.strip()]
                if verbose:
                    print(f"📋 Found {len(port_pids)} processes using port 11434: {port_pids}")
                
                for pid in port_pids:
                    try:
                        if verbose:
                            print(f"🎯 Terminating process using Ollama port: {pid}")
                        subprocess.run(['kill', '-TERM', pid], timeout=5)
                        cleaned_processes.append(f"Port 11434 process {pid}")
                    except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                        if verbose:
                            print(f"⚠️  Port process {pid} already gone")
            else:
                if verbose:
                    print("✅ No processes using port 11434")
        except FileNotFoundError:
            if verbose:
                print("⚠️  lsof command not available, skipping port cleanup")
        
        # Method 4: Clean up PID files
        pid_files = ["sra_script.pid"]
        for pid_file in pid_files:
            if os.path.exists(pid_file):
                if verbose:
                    print(f"🗑️  Removing PID file: {pid_file}")
                os.remove(pid_file)
                cleaned_processes.append(f"PID file {pid_file}")
        
        # Final status report
        if verbose:
            print("\n" + "="*50)
            print("🏁 CLEANUP SUMMARY")
            print("="*50)
            
            if cleaned_processes:
                print(f"✅ Successfully cleaned up {len(cleaned_processes)} items:")
                for item in cleaned_processes:
                    print(f"   • {item}")
            else:
                print("✅ No processes needed cleanup - system was already clean")
            
            print("\n🔍 Final system status:")
            # Show remaining Ollama processes
            final_check = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
            if final_check.returncode == 0:
                ollama_lines = [line for line in final_check.stdout.split('\n') 
                              if 'ollama' in line.lower() and 'grep' not in line]
                if ollama_lines:
                    print(f"⚠️  {len(ollama_lines)} Ollama processes still running:")
                    for line in ollama_lines:
                        print(f"   {line.strip()}")
                else:
                    print("✅ No Ollama processes running")
            
            print("="*50)
        
        return len(cleaned_processes) > 0
        
    except Exception as e:
        if verbose:
            print(f"❌ Error during cleanup: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Clean up Ollama and SRA processes")
    parser.add_argument("-q", "--quiet", action="store_true", 
                       help="Run quietly without verbose output")
    parser.add_argument("--force", action="store_true",
                       help="Force cleanup without confirmation")
    
    args = parser.parse_args()
    
    if not args.quiet:
        print("🧬 Advanced Ollama & SRA Process Cleanup Tool")
        print("=" * 50)
    
    if not args.force and not args.quiet:
        response = input("⚠️  This will stop all running Ollama and SRA processes. Continue? (y/N): ")
        if response.lower() not in ['y', 'yes']:
            print("❌ Cleanup cancelled by user")
            return 1
    
    success = cleanup_ollama_processes(verbose=not args.quiet)
    
    if success:
        if not args.quiet:
            print("\n🎉 Cleanup completed successfully!")
        return 0
    else:
        if not args.quiet:
            print("\n⚠️  Cleanup completed with some issues")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 