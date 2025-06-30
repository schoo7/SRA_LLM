#!/usr/bin/env python3

import argparse
import csv
import json
import os
import subprocess
import sys
import time
import threading
import re
from typing import Dict, Any, List, Optional, Iterator
from tqdm import tqdm
import signal
import tempfile
import atexit
from pathlib import Path

# ==========================================
# PATH CONFIGURATION FOR NCBI E-UTILITIES
# ==========================================
def cleanup_broken_symlinks():
    """Remove broken NCBI tool symlinks that interfere with working installation."""
    script_dir = Path(__file__).parent.absolute()
    bin_dir = script_dir / "bin"
    
    if bin_dir.exists():
        print("INFO: Found local bin directory with potential broken symlinks", file=sys.stderr)
        
        # Check if symlinks are broken by testing multiple methods
        should_remove = False
        
        # Method 1: Check if esearch symlink exists (as symlink, not target)
        esearch_symlink = bin_dir / "esearch"
        if esearch_symlink.is_symlink():
            target = esearch_symlink.resolve()
            if not target.exists():
                print("INFO: Detected broken symlink (target does not exist)", file=sys.stderr)
                should_remove = True
            else:
                # Method 2: Test if the symlink actually works
                try:
                    result = subprocess.run([str(esearch_symlink), "-help"], 
                                          capture_output=True, text=True, timeout=5)
                    if result.returncode != 0:
                        print("INFO: Detected broken symlinks (execution failed)", file=sys.stderr)
                        should_remove = True
                    else:
                        print("INFO: Symlinks appear to be working, keeping them", file=sys.stderr)
                except Exception as e:
                    print(f"INFO: Error testing symlinks ({e}), assuming broken", file=sys.stderr)
                    should_remove = True
        elif esearch_symlink.exists():
            # It's a regular file, test if it works
            try:
                result = subprocess.run([str(esearch_symlink), "-help"], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode != 0:
                    print("INFO: Detected non-working NCBI tools in bin directory", file=sys.stderr)
                    should_remove = True
                else:
                    print("INFO: NCBI tools in bin directory appear to be working", file=sys.stderr)
            except Exception as e:
                print(f"INFO: Error testing NCBI tools in bin directory ({e}), assuming broken", file=sys.stderr)
                should_remove = True
        
        # Remove the bin directory if symlinks are broken
        if should_remove:
            import shutil
            try:
                shutil.rmtree(bin_dir)
                print("✅ Removed broken symlinks directory", file=sys.stderr)
            except Exception as remove_error:
                print(f"WARNING: Could not remove bin directory: {remove_error}", file=sys.stderr)

def configure_ncbi_tools_path():
    """Configure PATH to include NCBI E-utilities installation locations."""
    print("INFO: Configuring PATH for NCBI E-utilities...", file=sys.stderr)
    
    # First, clean up any broken symlinks
    cleanup_broken_symlinks()
    
    # Get current script directory
    script_dir = Path(__file__).parent.absolute()
    home_dir = Path.home()
    
    # Priority order for NCBI tools locations
    ncbi_paths = [
        str(home_dir / "edirect"),                  # Official installation (highest priority)
        "/usr/local/bin",                           # Homebrew Intel
        "/opt/homebrew/bin",                        # Homebrew Apple Silicon  
        str(script_dir / "ncbi_tools" / "edirect"), # Local installation fallback
        # Note: Removed local symlinks as they're unreliable due to dependency issues
    ]
    
    # Get current PATH and clean it up
    current_path = os.environ.get("PATH", "")
    path_parts = current_path.split(os.pathsep) if current_path else []
    
    # Remove problematic paths (broken symlinks in project bin directory)
    problematic_paths = [
        str(script_dir / "bin"),  # Remove broken symlinks directory
    ]
    
    # Clean up PATH by removing problematic paths and duplicates
    cleaned_path_parts = []
    for path in path_parts:
        # Skip problematic paths and duplicates
        if path not in problematic_paths and path not in cleaned_path_parts:
            cleaned_path_parts.append(path)
    
    # Add NCBI paths to the beginning (highest priority)
    for ncbi_path in reversed(ncbi_paths):  # Reverse to maintain priority order
        if ncbi_path not in cleaned_path_parts:
            cleaned_path_parts.insert(0, ncbi_path)
    
    # Update PATH environment variable
    new_path = os.pathsep.join(cleaned_path_parts)
    os.environ["PATH"] = new_path
    
    print(f"INFO: Updated PATH with NCBI tool locations", file=sys.stderr)
    print(f"INFO: Priority paths: {ncbi_paths}", file=sys.stderr)
    print(f"INFO: Removed problematic paths: {problematic_paths}", file=sys.stderr)
    
    # Verify NCBI tools availability
    return verify_ncbi_tools()

def verify_ncbi_tools():
    """Verify that NCBI tools are available and working."""
    print("INFO: Verifying NCBI E-utilities availability...", file=sys.stderr)
    
    required_tools = ["esearch", "efetch"]
    available_tools = []
    
    for tool in required_tools:
        try:
            # Try to find the tool
            result = subprocess.run(["which", tool], capture_output=True, text=True)
            if result.returncode == 0:
                tool_path = result.stdout.strip()
                print(f"INFO: Found {tool} at: {tool_path}", file=sys.stderr)
                
                # Test if the tool actually works
                test_result = subprocess.run([tool, "-help"], capture_output=True, text=True, timeout=10)
                if test_result.returncode == 0:
                    available_tools.append(tool)
                    print(f"INFO: {tool} is working correctly", file=sys.stderr)
                else:
                    print(f"WARNING: {tool} found but not working properly", file=sys.stderr)
            else:
                print(f"WARNING: {tool} not found in PATH", file=sys.stderr)
                
        except Exception as e:
            print(f"WARNING: Error checking {tool}: {e}", file=sys.stderr)
    
    if len(available_tools) == len(required_tools):
        print("✅ All NCBI E-utilities are available and working!", file=sys.stderr)
        return True
    else:
        print("❌ Some NCBI E-utilities are missing or not working", file=sys.stderr)
        print_ncbi_diagnostic_info()
        return False

def print_ncbi_diagnostic_info():
    """Print diagnostic information for troubleshooting NCBI tools."""
    print("\n" + "="*60, file=sys.stderr)
    print("🔧 NCBI E-UTILITIES DIAGNOSTIC INFORMATION", file=sys.stderr)
    print("="*60, file=sys.stderr)
    
    # Show current PATH
    current_path = os.environ.get("PATH", "")
    print(f"Current PATH: {current_path}", file=sys.stderr)
    
    # Check installation locations
    print("\nChecking installation locations:", file=sys.stderr)
    script_dir = Path(__file__).parent.absolute()
    home_dir = Path.home()
    
    locations_to_check = [
        (str(home_dir / "edirect"), "Official installation"),
        ("/usr/local/bin", "Homebrew Intel"),
        ("/opt/homebrew/bin", "Homebrew Apple Silicon"),
        (str(script_dir / "ncbi_tools" / "edirect"), "Local installation"),
        # Note: Removed local symlinks as they're unreliable due to dependency issues
    ]
    
    for location, description in locations_to_check:
        location_path = Path(location)
        if location_path.exists():
            print(f"✅ {description}: {location} (exists)", file=sys.stderr)
            # Check for specific tools
            for tool in ["esearch", "efetch"]:
                tool_path = location_path / tool
                if tool_path.exists():
                    print(f"   - {tool}: found", file=sys.stderr)
                else:
                    print(f"   - {tool}: missing", file=sys.stderr)
        else:
            print(f"❌ {description}: {location} (not found)", file=sys.stderr)
    
    # Check for broken symlinks in project bin directory
    broken_symlinks_detected = False
    bin_dir = script_dir / "bin"
    if bin_dir.exists():
        broken_symlinks_detected = True
    
    print("\n🔧 TROUBLESHOOTING STEPS:", file=sys.stderr)
    if broken_symlinks_detected:
        print("1. **IMMEDIATE FIX** - Remove broken symlinks:", file=sys.stderr)
        print(f"   rm -rf {bin_dir}", file=sys.stderr)
        print("   (This removes the directory with broken symlinks that interfere with working tools)", file=sys.stderr)
        print("", file=sys.stderr)
    print("2. Re-run the installer: python3 install_sra_analyzer.py", file=sys.stderr)
    print("3. Or manually install NCBI E-utilities:", file=sys.stderr)
    print('   sh -c "$(curl -fsSL https://ftp.ncbi.nlm.nih.gov/entrez/entrezdirect/install-edirect.sh)"', file=sys.stderr)
    print("4. Restart your terminal after installation", file=sys.stderr)
    print("5. Check that $HOME/edirect is in your PATH", file=sys.stderr)
    print("="*60 + "\n", file=sys.stderr)

# Configure NCBI tools PATH at script startup
NCBI_TOOLS_AVAILABLE = configure_ncbi_tools_path()

# Global variables for cleanup
_ollama_processes = []
_cleanup_registered = False

def register_cleanup():
    """Register cleanup handlers for graceful shutdown."""
    global _cleanup_registered
    if not _cleanup_registered:
        atexit.register(cleanup_ollama_processes)
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        _cleanup_registered = True
        print("INFO: Cleanup handlers registered", file=sys.stderr)

def signal_handler(signum, frame):
    """Handle termination signals."""
    print(f"\nINFO: Received signal {signum}, cleaning up...", file=sys.stderr)
    cleanup_ollama_processes()
    sys.exit(0)

def cleanup_ollama_processes():
    """Clean up any orphaned Ollama model processes and SRA script processes."""
    print("🧹 Starting comprehensive cleanup...", file=sys.stderr)
    
    try:
        # Method 1: Clean up qwen3 model processes
        print("INFO: Searching for qwen3 model processes...", file=sys.stderr)
        result = subprocess.run(['pgrep', '-f', 'ollama runner.*qwen3'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            pids = result.stdout.strip().split('\n')
            print(f"INFO: Found Ollama qwen3 processes: {pids}", file=sys.stderr)
            for pid in pids:
                if pid.strip():
                    try:
                        print(f"INFO: Terminating Ollama process {pid}...", file=sys.stderr)
                        subprocess.run(['kill', '-TERM', pid], timeout=5)
                        time.sleep(2)
                        # Check if still running, force kill
                        check_result = subprocess.run(['ps', '-p', pid], 
                                                    capture_output=True, text=True)
                        if check_result.returncode == 0:
                            print(f"INFO: Force killing Ollama process {pid}...", file=sys.stderr)
                            subprocess.run(['kill', '-KILL', pid], timeout=5)
                    except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                        pass  # Process already gone or can't be killed
        else:
            print("INFO: No qwen3 model processes found.", file=sys.stderr)
        
        # Method 2: Clean up other SRA script processes (but not current process)
        current_pid = os.getpid()
        print("INFO: Searching for other SRA script processes...", file=sys.stderr)
        sra_result = subprocess.run(['pgrep', '-f', 'SRA_fetch_1LLM_improved.py'], 
                                  capture_output=True, text=True)
        if sra_result.returncode == 0:
            sra_pids = sra_result.stdout.strip().split('\n')
            for pid in sra_pids:
                if pid.strip() and int(pid) != current_pid:
                    try:
                        print(f"INFO: Terminating other SRA script process {pid}...", file=sys.stderr)
                        subprocess.run(['kill', '-TERM', pid], timeout=5)
                        time.sleep(2)
                        # Force kill if still running
                        check_result = subprocess.run(['ps', '-p', pid], 
                                                    capture_output=True, text=True)
                        if check_result.returncode == 0:
                            print(f"INFO: Force killing SRA script process {pid}...", file=sys.stderr)
                            subprocess.run(['kill', '-KILL', pid], timeout=5)
                    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, ValueError):
                        pass  # Process already gone or can't be killed
        else:
            print("INFO: No other SRA script processes found.", file=sys.stderr)
        
        # Method 3: Kill by port if port-based cleanup is needed
        try:
            # Find processes using typical Ollama ports
            port_result = subprocess.run(['lsof', '-ti', ':11434'], 
                                       capture_output=True, text=True)
            if port_result.returncode == 0:
                pids = port_result.stdout.strip().split('\n')
                for pid in pids:
                    if pid.strip():
                        try:
                            print(f"INFO: Terminating Ollama on port 11434: {pid}", file=sys.stderr)
                            subprocess.run(['kill', '-TERM', pid], timeout=5)
                        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                            pass
        except FileNotFoundError:
            pass  # lsof not available
        
        print("✅ Comprehensive cleanup completed!", file=sys.stderr)
        
        # Show final status
        print("INFO: Final process status:", file=sys.stderr)
        status_result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        if status_result.returncode == 0:
            ollama_processes = []
            for line in status_result.stdout.split('\n'):
                if 'ollama' in line and 'grep' not in line:
                    ollama_processes.append(line.strip())
            
            if ollama_processes:
                print("INFO: Remaining Ollama processes:", file=sys.stderr)
                for proc in ollama_processes:
                    print(f"  {proc}", file=sys.stderr)
            else:
                print("INFO: No Ollama processes running.", file=sys.stderr)
        
    except Exception as e:
        print(f"WARNING: Error during comprehensive cleanup: {e}", file=sys.stderr)

def restart_ollama_service():
    """Restart Ollama service after cleanup to ensure it's available for future runs."""
    print("🔄 Restarting Ollama service...", file=sys.stderr)
    
    try:
        # Check if Ollama is already running
        check_result = subprocess.run(['pgrep', 'ollama'], capture_output=True, text=True)
        if check_result.returncode == 0:
            print("INFO: Ollama service is already running", file=sys.stderr)
            return True
        
        # Try to start Ollama service
        print("INFO: Starting Ollama service...", file=sys.stderr)
        
        # Method 1: Try to start Ollama directly
        try:
            start_result = subprocess.run(['ollama', 'serve'], 
                                        capture_output=True, text=True, timeout=10)
            if start_result.returncode == 0:
                print("✅ Ollama service started successfully", file=sys.stderr)
                return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        # Method 2: Try to start with background process
        try:
            # Start Ollama in background
            subprocess.Popen(['ollama', 'serve'], 
                           stdout=subprocess.DEVNULL, 
                           stderr=subprocess.DEVNULL)
            time.sleep(3)  # Give it time to start
            
            # Check if it's running
            check_result = subprocess.run(['pgrep', 'ollama'], capture_output=True, text=True)
            if check_result.returncode == 0:
                print("✅ Ollama service started in background", file=sys.stderr)
                return True
        except Exception as e:
            print(f"WARNING: Failed to start Ollama in background: {e}", file=sys.stderr)
        
        # Method 3: Check if Ollama is available via system service
        try:
            # Try to list models to see if service is available
            list_result = subprocess.run(['ollama', 'list'], 
                                       capture_output=True, text=True, timeout=10)
            if list_result.returncode == 0:
                print("✅ Ollama service is available", file=sys.stderr)
                return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        print("⚠️ Could not restart Ollama service automatically", file=sys.stderr)
        print("INFO: Ollama will be started automatically on next script run", file=sys.stderr)
        return False
        
    except Exception as e:
        print(f"WARNING: Error restarting Ollama service: {e}", file=sys.stderr)
        return False

def create_pid_file():
    """Create a PID file for this script to help with cleanup."""
    try:
        pid_file = "sra_script.pid"
        with open(pid_file, 'w') as f:
            f.write(str(os.getpid()))
        print(f"INFO: Created PID file: {pid_file}", file=sys.stderr)
        return pid_file
    except Exception as e:
        print(f"WARNING: Could not create PID file: {e}", file=sys.stderr)
        return None

def remove_pid_file(pid_file):
    """Remove the PID file."""
    try:
        if pid_file and os.path.exists(pid_file):
            os.remove(pid_file)
            print(f"INFO: Removed PID file: {pid_file}", file=sys.stderr)
    except Exception as e:
        print(f"WARNING: Could not remove PID file: {e}", file=sys.stderr)

# KeywordProvider class (inline to avoid import issues)
class KeywordProvider:
    """Provides keywords from CSV file."""
    def __init__(self, csv_path: str, column_name: Optional[str] = None):
        self.csv_path = csv_path
        self.column_name = column_name
        
    def get_keywords(self) -> List[str]:
        """Read keywords from CSV file."""
        keywords = []
        try:
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                # Always skip the first row (header)
                header = next(reader)  # Skip header row
                print(f"DEBUG: KeywordProvider skipping header: {header}", file=sys.stderr)
                
                if self.column_name:
                    # Find column index from header
                    col_idx = header.index(self.column_name)
                    keywords = [row[col_idx].strip() for row in reader if len(row) > col_idx and row[col_idx].strip()]
                else:
                    # Use first column, skip header
                    keywords = [row[0].strip() for row in reader if row and row[0].strip()]
        except Exception as e:
            print(f"ERROR: Failed to read keywords from {self.csv_path}: {e}", file=sys.stderr)
        
        unique_keywords = list(dict.fromkeys(keywords))  # Remove duplicates while preserving order
        print(f"INFO: Loaded {len(unique_keywords)} unique keywords from '{self.csv_path}'. First 5: {unique_keywords[:5]}", file=sys.stderr)
        return unique_keywords

# Configuration
BATCH_SIZE = 10
RETRY_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 2
ENTREZ_TIMEOUT = 1800  # Increased to 30 minutes to allow large runinfo downloads
# Reduced exclusion list - only exclude clearly irrelevant or low-quality strategies
EXCLUDED_LIBRARY_STRATEGIES = {
    'WGA', 'CLONE', 'POOLCLONE', 'CLONEEND', 'FINISHING',
    'Synthetic-Long-Read', 'FAIRE-seq', 'SELEX', 'RIP-Seq', 'ChIA-PET', 'MNase-Seq', 
    'DNase-Hypersensitivity', 'EST', 'FL-cDNA', 'CTS', 'MRE-Seq', 'MeDIP-Seq', 'MBD-Seq', 
    'Tn-Seq', 'VALIDATION', 'OTHER'
    # Removed: 'AMPLICON', 'Targeted-Capture', 'Hi-C', 'Bisulfite-Seq' 
    # These are commonly used in genomics research and should not be excluded
}

OUTPUT_COLUMNS = [
    "sra_experiment_id", "gse_accession", "gsm_accession", "species", "sequencing_technique",
    "sample_type", "cell_line_name", "tissue_type", "disease_description", "treatment",
    "is_chipseq_related_experiment", "chipseq_antibody_target",
    "scientific_sample_summary"
]

class SimpleLLMProcessor:
    """Simplified LLM processor optimized for qwen3:8b model."""
    
    def __init__(self, model_name: str = "qwen3:8b", fresh_instance_per_sample: bool = True):
        self.model_name = model_name
        self.fresh_instance_per_study = fresh_instance_per_sample  # Rename for clarity
        self.llm = None
        self._current_study_id = None
        self._current_study_llm = None
        self._study_sample_count = 0
        self._study_context = {}  # Store study-level context for LLM guidance
        self._study_summary = None  # Store study-level summary to reuse
        
        if not self.fresh_instance_per_study:
            self._initialize_llm()
    
    def _initialize_llm(self):
        """Initialize the LLM connection once."""
        try:
            from langchain_ollama import OllamaLLM
            self.llm = OllamaLLM(model=self.model_name)
            print(f"🤖 Initialized {self.model_name} model", file=sys.stderr)
        except Exception as e:
            print(f"Error initializing LLM: {e}", file=sys.stderr)
            self.llm = None
    
    def _get_fresh_llm_instance(self):
        """Create a fresh LLM instance."""
        try:
            from langchain_ollama import OllamaLLM
            return OllamaLLM(model=self.model_name)
        except Exception as e:
            print(f"Error creating fresh LLM instance: {e}", file=sys.stderr)
            return None
    
    def _get_llm_for_sample(self, sample_id: str):
        """Get LLM instance for a sample - fresh per sample or persistent."""
        return self.llm  # Simplified for now, will implement study logic in get_llm_for_study
    
    def _extract_study_id(self, srx_id: str, gse_id: str = "N/A") -> str:
        """Extract study identifier from SRX ID or GSE ID."""
        if gse_id and gse_id != "N/A":
            return gse_id
        # Use SRX prefix for sequential grouping (e.g., SRX29141268 -> SRX291412)
        if srx_id.startswith(('SRX', 'ERX', 'DRX')):
            return srx_id[:8]  # Group by first 8 characters for sequential studies
        return srx_id
    
    def get_llm_for_study(self, srx_id: str, gse_id: str = "N/A") -> tuple:
        """Get LLM instance for a study with refresh logic and context sharing."""
        study_id = self._extract_study_id(srx_id, gse_id)
        
        if not self.fresh_instance_per_study:
            return self.llm, {}
        
        # Check if we need a fresh instance
        need_refresh = False
        preserve_context = True
        
        if self._current_study_id != study_id:
            # New study
            need_refresh = True
            preserve_context = False
            self._study_sample_count = 0
            self._study_context = {}
            self._study_summary = None  # Reset summary for new study
            print(f"🔄 New study detected: {study_id} (from {srx_id})", file=sys.stderr)
        elif self._study_sample_count >= 30:
            # Large study - refresh every 30 samples but preserve context for consistency
            need_refresh = True
            preserve_context = True
            self._study_sample_count = 0
            print(f"🔄 Refreshing LLM for large study {study_id} (sample #{self._study_sample_count}) - preserving context", file=sys.stderr)
        
        if need_refresh:
            print(f"✨ Creating fresh LLM instance for study: {study_id}", file=sys.stderr)
            self._current_study_llm = self._get_fresh_llm_instance()
            self._current_study_id = study_id
            if self._current_study_llm:
                print(f"✅ Fresh LLM instance ready for study: {study_id}", file=sys.stderr)
                if preserve_context and self._study_context:
                    print(f"🔗 Preserving study context for consistency: {len(self._study_context)} fields", file=sys.stderr)
            else:
                print(f"❌ Failed to create fresh LLM instance for study: {study_id}", file=sys.stderr)
        
        self._study_sample_count += 1
        return self._current_study_llm, self._study_context
    
    def update_study_context(self, key: str, value: str, sequencing_technique: str = None):
        """Update study-level context for sharing between samples."""
        if value and value != "N/A":
            # Store as guidance, not forced inheritance
            if key not in self._study_context:
                self._study_context[key] = []
            if value not in self._study_context[key]:
                self._study_context[key].append(value)
            
            # Special handling for instrument_model - group by sequencing technique
            if key == 'instrument_model' and sequencing_technique and sequencing_technique != "N/A":
                instrument_key = f"instrument_model_{sequencing_technique}"
                if instrument_key not in self._study_context:
                    self._study_context[instrument_key] = []
                if value not in self._study_context[instrument_key]:
                    self._study_context[instrument_key].append(value)
    
    def get_study_summary(self) -> str:
        """Get the study-level summary if available."""
        return self._study_summary if self._study_summary else "N/A"
    
    def set_study_summary(self, summary: str):
        """Set the study-level summary for reuse."""
        if summary and summary != "N/A":
            self._study_summary = summary
    
    def invoke(self, prompt: str, sample_id: str = "default") -> Optional[str]:
        """Invoke the LLM with a prompt, with retry logic for connection issues."""
        # For backward compatibility, use persistent instance if no study context
        llm_instance = self.llm if hasattr(self, 'llm') and self.llm else self._get_fresh_llm_instance()
        if not llm_instance:
            return None

        for attempt in range(3):  # Try up to 3 times
            try:
                response = llm_instance.invoke(prompt)
                return response.content if hasattr(response, 'content') else str(response)
            except Exception as e:
                if attempt < 2:  # Don't print warning on last attempt
                    print(f"Warning: LLM invocation failed (attempt {attempt+1}): {e}", file=sys.stderr)
                    time.sleep(1)  # Brief pause before retry
                else:
                    print(f"Warning: LLM invocation failed after 3 attempts: {e}", file=sys.stderr)
        return None

    def _parse_llm_response(self, response_text: str) -> Dict[str, str]:
        """Parse LLM response into structured data."""
        result = {
            'species': 'N/A',
            'sequencing_technique': 'N/A', 
            'sample_type': 'N/A',
            'cell_line_name': 'N/A',
            'tissue_type': 'N/A',
            'disease_description': 'N/A',
            'treatment': 'N/A',
            'instrument_model': 'N/A',
            'is_chipseq_related_experiment': 'no',
            'chipseq_antibody_target': 'N/A',
            'scientific_sample_summary': 'N/A'
        }
        
        # Parse the structured response
        lines = response_text.strip().split('\n')
        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower()
                value = value.strip()
                
                if key == 'species':
                    result['species'] = value
                elif key == 'sequencing_technique':
                    result['sequencing_technique'] = value
                elif key == 'sample_type':
                    result['sample_type'] = value
                elif key == 'cell_line_name':
                    result['cell_line_name'] = value
                elif key == 'tissue_type':
                    result['tissue_type'] = value
                elif key == 'disease_description':
                    result['disease_description'] = value
                elif key == 'treatment':
                    result['treatment'] = value
                elif key == 'instrument_model':
                    result['instrument_model'] = value
                elif key == 'is_chipseq_related_experiment':
                    result['is_chipseq_related_experiment'] = value.lower()
                elif key == 'chipseq_antibody_target':
                    result['chipseq_antibody_target'] = value
                elif key == 'scientific_sample_summary':
                    result['scientific_sample_summary'] = value
        
        return result

class EntrezClient:
    """A client for interacting with NCBI Entrez services."""
    
    def __init__(self):
        pass

    def efetch_sra_experiment_xml(self, sra_experiment_id: str) -> Optional[str]:
        """Fetches SRA Experiment XML for a given SRA Experiment ID."""
        if not sra_experiment_id:
            return None

        command = ["efetch", "-db", "sra", "-id", sra_experiment_id, "-format", "xml"]
        for attempt in range(RETRY_ATTEMPTS):
            try:
                process = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=True,
                )
                return process.stdout
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
                print(f"Warning: efetch for {sra_experiment_id} failed (attempt {attempt + 1}): {e}", file=sys.stderr)
                time.sleep(RETRY_DELAY_SECONDS)
        
        print(f"Error: Failed to fetch XML for {sra_experiment_id} after {RETRY_ATTEMPTS} attempts.", file=sys.stderr)
        return None

def build_prompt(xml_text: str, geo_summary: str, srx_id: str, gse_id: str = "N/A", gsm_id: str = "N/A", keyword: str = "N/A", study_context: Dict[str, str] = {}) -> str:
    """Build a comprehensive expert-level prompt for biomedical metadata extraction."""
    
    # Add study context information
    context_info = ""
    if study_context:
        context_info = f"\n**STUDY CONTEXT** (CRITICAL: maintain consistency with previous samples in this study):\n"
        context_info += "**CONSISTENCY RULE**: Same study samples should have similar characteristics unless explicitly different.\n"
        for key, value in study_context.items():
            if isinstance(value, list):
                # Special formatting for instrument model by technique
                if key.startswith('instrument_model_'):
                    technique = key.replace('instrument_model_', '')
                    context_info += f"- Previous instrument for {technique}: {', '.join(value)} (MAINTAIN CONSISTENCY)\n"
                elif key == 'cell_line_name':
                    context_info += f"- Previous {key} values: {', '.join(value)} (SAME STUDY = LIKELY SAME CELL LINE)\n"
                elif key == 'sample_type':
                    context_info += f"- Previous {key} values: {', '.join(value)} (SAME STUDY = LIKELY SAME SAMPLE TYPE)\n"
                elif key == 'species':
                    context_info += f"- Previous {key} values: {', '.join(value)} (SAME STUDY = SAME SPECIES)\n"
                else:
                    context_info += f"- Previous {key} values: {', '.join(value)}\n"
            else:
                context_info += f"- {key}: {value}\n"
    
    prompt = f"""You are an expert biomedical data curator with deep knowledge of SRA/GEO databases, genomics, and cell biology. Extract comprehensive metadata from the provided data with scientific precision.

=== CRITICAL EXTRACTION PRIORITIES ===

1. **CELL LINE DETECTION** (Expert Knowledge Required):
   - Look for standard cell line names in ALL text fields: sample titles, descriptions, protocols
   - **LIBRARY NAMES**: Pay special attention to LibraryName field in SRA data
   - Common patterns: "LNP" = LNCaP, "LNP_2" = LNCaP, "LNP-BICA_1" = LNCaP
   - Library naming conventions: "VCP" = VCaP, "PC3" = PC3, "DU145" = DU145
   - Common prostate cancer cell lines: LNCaP, VCaP, PC3, DU145, 22Rv1, C4-2, RWPE-1, PNT2
   - Common breast cancer cell lines: MCF7, T47D, MDA-MB-231, BT474, SKBR3, ZR-75-1
   - Cell lines may appear in sample names like "GSM9008763: sgOGDHL_1_Enza 2" (extract LNCaP from context)
   - Cell lines may be abbreviated or modified: "C42" = "C4-2", "22RV1" = "22Rv1"
   - **USE STUDY CONTEXT**: If previous samples in this study identified a cell line, this sample likely uses the same cell line
   - **STUDY GUIDANCE**: Use previous samples as hints, but analyze each sample independently
   - **Multiple cell lines possible**: Same study may use different cell lines (e.g., LNCaP vs VCaP comparison)
   - If tissue type is mentioned but no cell line, sample_type should be "tissue" not "cell line"

2. **TREATMENT EXTRACTION** (Multi-component Analysis):
   - **PRIMARY SOURCE**: GSM sample titles (e.g., "GSM9008763: sgOGDHL_1_Enza 2")
   - **SECONDARY SOURCE**: GEO genotype fields, experiment titles, protocols, characteristics
   - **GENOTYPE FIELD ANALYSIS** (Critical for genetic modifications):
     * Look for "genotype:" tags in GEO data
     * Examples: "genotype: CTNNB1 overexpression" → "CTNNB1_overexpression"
     * Examples: "genotype: TP53 knockout" → "TP53_knockout"
     * Examples: "genotype: wild-type" → "WT" or "control"
     * Examples: "genotype: sgRNA targeting OGDHL" → "OGDHL_knockout"
   - **GENETIC MODIFICATIONS**:
     * "sgGENE" patterns = CRISPR knockout: "sgOGDHL_1" → "OGDHL_knockout"
     * "siGENE" patterns = RNAi knockdown: "siTP53" → "TP53_knockdown"  
     * "shGENE" patterns = shRNA knockdown: "shMYC" → "MYC_knockdown"
     * Remove numerical suffixes: "sgOGDHL_1" → "OGDHL_knockout" (not "OGDHL_1_knockout")
     * Parse genotype descriptions: "GENE overexpression" → "GENE_overexpression"
     * Parse genotype descriptions: "GENE knockout" → "GENE_knockout"
   - **DRUG TREATMENTS**:
     * "Enza" = "Enzalutamide", "DOX" = "Doxorubicin", "Tam" = "Tamoxifen"
     * "JQ1", "PRT2527", "ARN-509", "MDV3100" = use exact compound names
     * Concentrations/durations: extract if present but don't fabricate
   - **CONTROLS**:
     * "Ctrl", "Control", "DMSO", "Vehicle" = "control"
     * "siControl", "siNC", "shControl" = "control" (negative controls)
   - **COMBINATION TREATMENTS**: Use " + " separator
     * "sgOGDHL_1_Enza" → "OGDHL_knockout + Enzalutamide"
     * "siTP53_DOX" → "TP53_knockdown + Doxorubicin"
   - **SAMPLE TYPE CONSIDERATIONS**:
     * **CELL LINES**: Treatments are common and important (drugs, genetic modifications)
     * **TISSUE/PDX**: Treatments are less common, often just sample collection conditions
     * **PDX CAUTION**: Patient-derived xenografts rarely have drug treatments - be very conservative
     * If tissue/PDX samples don't clearly show treatment, use "N/A" rather than guessing
   - **STUDY GUIDANCE**: Previous treatments in this study can guide detection of similar patterns
   - **INDEPENDENT ANALYSIS**: Each sample should be analyzed independently despite study context

3. **SPECIES IDENTIFICATION**:
   - Use full scientific names: "Homo sapiens", "Mus musculus", "Rattus norvegicus"
   - Infer from cell line context: LNCaP/VCaP/PC3 = human, NIH3T3 = mouse

4. **SEQUENCING TECHNIQUE**:
   - RNA-Seq, ChIP-Seq, ATAC-Seq, scRNA-Seq, WGS, WES, Bisulfite-Seq
   - Infer from library strategy and experiment type

5. **SAMPLE TYPE CLASSIFICATION**:
   - "Cell Line" = if cell line name identified (LNCaP, VCaP, PC3, etc.)
   - "Tissue" = if tissue mentioned without cell line (primary tissue samples)
   - "PDX" = if Patient-Derived Xenograft mentioned (PDX, xenograft, patient-derived)
   - "Primary Cells" = if primary cells mentioned
   - **STUDY GUIDANCE**: Same study likely uses same sample type (all tissue, all PDX, or all cell lines)
   - Be precise based on actual sample source

6. **DISEASE DESCRIPTION**:
   - Extract specific cancer types: "Prostate cancer", "Breast cancer", "Lung adenocarcinoma"
   - Include stage/grade if mentioned: "Metastatic prostate cancer"
   - Use "N/A" for healthy controls or unclear cases

7. **INSTRUMENT MODEL DETECTION**:
   - Extract sequencing instrument from SRA XML: Illumina HiSeq, NovaSeq, MiSeq, NextSeq, etc.
   - **STUDY + TECHNIQUE GUIDANCE**: If previous samples in this study used the same sequencing technique, they likely used the same instrument
   - Look for INSTRUMENT tags in SRA XML data
   - **STANDARDIZE NAMES**: Always include manufacturer prefix
     * "HiSeq 2000/2500" → "Illumina HiSeq 2000/2500"
     * "NextSeq550" → "Illumina NextSeq 550"
     * "NovaSeq 6000" → "Illumina NovaSeq 6000"
   - **TECHNIQUE-SPECIFIC SHARING**: Same study + same sequencing technique = likely same instrument

8. **CHIP-SEQ SPECIFIC**:
   - is_chipseq_related_experiment: "yes" only if ChIP-Seq confirmed
   - chipseq_antibody_target: Extract target protein/histone mark (AR, H3K27ac, H3K4me3, etc.)

9. **SCIENTIFIC SUMMARY**:
   - 2-4 sentences describing the biological question and experimental approach
   - Include cell line, treatment, and research objective
   - Be specific about the biological context
   - **STUDY EFFICIENCY**: If study context shows similar samples, you may provide a general study-level summary
   - **REUSE GUIDANCE**: Focus on the overall study goals rather than sample-specific details

3. **DISEASE/CONDITION IDENTIFICATION**:
   - Look for disease mentions in titles, descriptions, protocols
   - Common terms: cancer, tumor, carcinoma, adenocarcinoma, metastasis
   - **SEARCH CONTEXT**: Samples found via "{keyword}" search likely relate to this condition
   - Be specific: "prostate cancer" not just "cancer", "breast adenocarcinoma" not "tumor"

10. **FALLBACK TREATMENT FROM SAMPLE NAME**: If no explicit treatment in XML/GSM text, inspect sample/FASTQ titles. Extract tokens (split by "_", "-", or whitespace) that look like drug names or genetic labels. Ignore generic tokens such as rep, repeat, replicate, sample, ctrl, control, untreated, numbers-only tokens, or known cell-line names (e.g., LNCaP, PC3, DU145, 22Rv1, VCaP, C4-2). If no valid token remains, output "N/A".

=== DATA SOURCES TO ANALYZE ===

**SRA Experiment XML:**
{xml_text[:1500]}

**GEO Data Summary:**
{geo_summary[:800]}

+{context_info}
+
**Context Information:**
- SRA ID: {srx_id}
- GSE: {gse_id}
- GSM: {gsm_id}
- Search keyword: {keyword}

=== DATA ANALYSIS INSTRUCTIONS ===

**Step 1: Parse ALL available text sources:**
- XML experiment/sample titles and descriptions
- GEO summary text (GSM descriptions)
+- XML SAMPLE_ATTRIBUTES with TAG="genotype" or "characteristics"
+- Look for genotype information in both structured XML tags and free text
- Protocol descriptions and experimental design notes

=== RESPONSE FORMAT ===
Respond with EXACTLY these key:value pairs, one per line:

Species: [Full scientific name]
Sequencing_technique: [RNA-Seq|ChIP-Seq|ATAC-Seq|WGS|OTHER]
Sample_type: [Cell Line|Tissue|PDX|Primary Cells|Other]
Cell_line_name: [Standard cell line name or N/A]
Tissue_type: [Specific tissue/organ or N/A]
Disease_description: [Specific disease or N/A]
Treatment: [Standardized treatment terms with + for combinations or N/A]
Is_chipseq_related_experiment: [yes|no]
Chipseq_antibody_target: [Target protein/mark or N/A]
Scientific_sample_summary: [2-4 sentence biological summary]

=== VALIDATION CHECKLIST ===
Before responding, verify:
1. Did I check GSM sample titles for cell lines and treatments?
2. Did I properly parse genetic modifications (sg/si/sh prefixes)?
3. Did I combine multiple treatments with " + " when both are present?
4. Did I use standard cell line nomenclature?
5. Did I correctly identify PDX samples and distinguish from regular tissue?
6. Did I avoid assigning treatments to PDX/tissue samples without clear evidence?
7. Did I standardize instrument names with manufacturer prefix?
8. Is my scientific summary biologically accurate and specific?
9. Did I avoid fabricating any information not present in the data?

**CRITICAL ANTI-HALLUCINATION RULES:**
1. **NEVER fabricate treatments** - If sample names like "LB3", "L3" contain no treatment info, use "N/A"
2. **NEVER assume genetic modifications** without explicit evidence (sg/si/sh prefixes or genotype fields)
3. **NEVER invent drug names** not explicitly mentioned in the data
4. **PDX TREATMENT CAUTION**: Patient-derived xenografts (PDX) rarely have drug treatments - be extremely conservative
5. **TISSUE/PDX vs CELL LINE**: Only cell lines commonly have treatments; tissue/PDX samples usually don't
6. **USE SEARCH CONTEXT**: If samples were found via "{keyword}" search, consider this for disease_description
7. **NEVER default to "Enzalutamide" or any other drug unless it is **explicitly** present in the sample metadata (XML or GSM text)**
8. **BE CONSERVATIVE**: If no treatment/genetic modification is explicitly mentioned, return "N/A"
9. Did I avoid fabricating any information not present in the data?

Extract metadata with scientific precision:

**EXAMPLE EXTRACTIONS:**

**Treatment Examples:**
- "GSM9008763: sgOGDHL_1_Enza 2" → "OGDHL_knockout + Enzalutamide"
- "LNCaP_PRT2527_rep2_s" → "PRT2527"
- "VCaP_Ctrl_rep2" → "control"
+- XML: "<TAG>genotype</TAG><VALUE>CTNNB1 overexpression</VALUE>" → "CTNNB1_overexpression"
+- XML: "<TAG>genotype</TAG><VALUE>wild-type</VALUE>" → "control"
+- XML: "<TAG>characteristics</TAG><VALUE>treatment: Enzalutamide 10uM</VALUE>" → "Enzalutamide"

**Sample Type & Treatment Examples:**
- "Prostate cancer tissue (PDX)" → Sample_type: "PDX", Tissue_type: "Prostate cancer tissue (PDX)"
- "prostate cancer-associated fibroblasts" → Sample_type: "Tissue", Tissue_type: "Prostate cancer-associated fibroblasts"
- "LNCaP cells treated with Enzalutamide" → Sample_type: "Cell Line", Treatment: "Enzalutamide"
- "PDX model" with no treatment mentioned → Sample_type: "PDX", Treatment: "N/A"
- **PDX CONSERVATIVE RULE**: PDX samples rarely have drug treatments - only extract if explicitly stated

**Instrument Model Examples:**
- If study context shows "Previous instrument for RNA-Seq: Illumina NovaSeq 6000" and current sample is RNA-Seq → likely "Illumina NovaSeq 6000"
- If study context shows "Previous instrument for ChIP-Seq: Illumina HiSeq 2500" but current sample is RNA-Seq → check XML for instrument, don't assume same
- "HiSeq 2000/2500" → standardize to "Illumina HiSeq 2000/2500"
- Same study + different technique = analyze independently
"""
    
    return prompt

def extract_geo_accessions(xml_text: str) -> Dict[str, str]:
    """Extract GSE and GSM accessions from SRA XML."""
    gse_patterns = [
        r'<STUDY_REF accession="(GSE\d+)"',
        r'<EXTERNAL_ID namespace="GEO">(GSE\d+)</EXTERNAL_ID>',
        r'alias="(GSE\d+)"',
        r'GSE(\d+)',
    ]
    
    gsm_patterns = [
        r'<EXPERIMENT alias="(GSM\d+)',
        r'<EXTERNAL_ID namespace="GEO">(GSM\d+)</EXTERNAL_ID>',
        r'<SAMPLE alias="(GSM\d+)"',
        r'sample_name="(GSM\d+)"',
        r'<LIBRARY_NAME>(GSM\d+)</LIBRARY_NAME>',
        r'GSM(\d+)',
    ]
    
    gse_id = "N/A"
    gsm_id = "N/A"
    
    for pattern in gse_patterns:
        match = re.search(pattern, xml_text)
        if match:
            if pattern.endswith(r'(\d+)'):
                gse_id = f"GSE{match.group(1)}"
            else:
                gse_id = match.group(1)
            break
                            
    for pattern in gsm_patterns:
        match = re.search(pattern, xml_text)
        if match:
            if pattern.endswith(r'(\d+)'):
                gsm_id = f"GSM{match.group(1)}"
            else:
                gsm_id = match.group(1)
            break
                                
    return {"gse": gse_id, "gsm": gsm_id}

def fetch_geo_soft_brief(gsm_id: str) -> str:
    """Fetch brief GEO SOFT text for a GSM accession."""
    if gsm_id == "N/A":
        return "N/A"
    
    import requests
    url = f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={gsm_id}&form=text&view=brief"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.text[:1500]
    except Exception:
        pass
    return "N/A"

def detect_cell_line_from_text(text: str) -> str:
    """Detect cell line from text using comprehensive patterns."""
    if not text or text == "N/A":
        return "N/A"
        
    text_lower = str(text).lower()
    
    cell_line_patterns = {
        'lncap': 'LNCaP', 'pc3': 'PC3', 'pc-3': 'PC3', 'du145': 'DU145', 'du-145': 'DU145',
        '22rv1': '22Rv1', 'vcap': 'VCaP', 'c4-2': 'C4-2', 'c42': 'C4-2', 'mcf-7': 'MCF-7', 
        'mcf7': 'MCF-7', 't47d': 'T47D', 'mda-mb-231': 'MDA-MB-231', 'hela': 'HeLa', 
        'hek293': 'HEK293', '293t': '293T', 'a549': 'A549', 'hct116': 'HCT116',
    }
    
    for pattern, standard_name in cell_line_patterns.items():
        if re.search(rf'\b{re.escape(pattern)}\b', text_lower):
            return standard_name
    
    generic_patterns = [
        r'\b([A-Z0-9\-]+)\s+cells?\b', r'\bcell\s+line\s+([A-Z0-9\-]+)\b'
    ]
    
    for pattern in generic_patterns:
        matches = re.finditer(pattern, str(text))
        for match in matches:
            candidate = match.group(1).strip().upper()
            if len(candidate) > 2 and candidate not in ['CANCER', 'CELLS', 'PROSTATE']:
                return candidate
        
    return "N/A"

def detect_treatment_from_text(text: str) -> str:
    """Detect treatment from text using comprehensive patterns for multiple treatments."""
    if not text or text == "N/A":
        return "WT"
        
    text_lower = str(text).lower()
    original_text = str(text)
        
    # Enhanced control patterns - check for specific control indicators
    control_patterns = [
        r'\bcontrol\b', r'\bvehicle\b', r'\bpbs\b', r'\bsinc\b', r'\bsicontrol\b', 
        r'\bshcontrol\b', r'\bscrambled\b', r'\bnegative control\b', r'\buntreated\b',
        r'\bwild[-_]?type\b', r'\bwt\b', r'\bctrl\b', r'_ctrl\b', r'ctrl_', r'\bdmso\b(?!\s*\d)',
        r'\bmock\b', r'\bplacebo\b', r'\bbaseline\b'
    ]
    
    # Check for DMSO-only treatment (vehicle control)
    dmso_only_patterns = [
        r'\btreated with dmso\b', r'\bdmso control\b', r'\bdmso vehicle\b',
        r'\bdmso or \d+', r'dmso.*control'
    ]
    is_dmso_control = any(re.search(pattern, text_lower) for pattern in dmso_only_patterns)
    
    has_control = any(re.search(pattern, text_lower) for pattern in control_patterns)
        
    # Enhanced knockout patterns
    knockout_patterns = [
        r'\bsg([A-Z][A-Z0-9_]+)\b', r'\b([A-Z][A-Z0-9]+)[_\-]knockout\b', 
        r'\bko[_\-]([A-Z][A-Z0-9]+)\b', r'\b([A-Z][A-Z0-9]+)\s+knockout\b'
    ]
    knockout_genes = set()
    for pattern in knockout_patterns:
        matches = re.finditer(pattern, original_text)
        for match in matches:
            gene = match.group(1).strip().upper().split('_')[0]
            if len(gene) > 1 and gene not in ['SI', 'SH', 'RNA', 'WERE', 'THE', 'AND']:
                knockout_genes.add(gene)
        
    # Enhanced knockdown patterns
    knockdown_patterns = [
        r'\bsi([A-Z][A-Z0-9]+)\b', r'\bsh([A-Z][A-Z0-9]+)\b', 
        r'\b([A-Z][A-Z0-9]+)[_\-]knockdown\b', r'\b([A-Z][A-Z0-9]+)\s+knockdown\b'
    ]
    knockdown_genes = set()
    for pattern in knockdown_patterns:
        matches = re.finditer(pattern, original_text)
        for match in matches:
            gene = match.group(1).strip().upper()
            if len(gene) > 1 and gene not in ['SI', 'SH', 'RNA', 'WERE', 'THE', 'AND']:
                knockdown_genes.add(gene)
        
    # Enhanced overexpression patterns - specifically look for XML tags and sample names
    overexpression_patterns = [
        r'<TAG>genotype</TAG>\s*<VALUE>([A-Z][A-Z0-9]+)\s+overexpression</VALUE>',  # XML genotype tag
        r'genotype:\s*([A-Z][A-Z0-9]+)\s+overexpression',  # GEO format
        r'\b([A-Z][A-Z0-9]+)[_\-]overexpress\w*\b', 
        r'\boverexpress\w*\s+([A-Z][A-Z0-9]+)\b',
        r'\b([A-Z][A-Z0-9]+)\s+overexpression\b',
        r'<TITLE>.*?([A-Z][A-Z0-9]+)\s+overexpression.*?</TITLE>',  # Title tags
        r'TITLE>.*?([A-Z][A-Z0-9]+)\s+\d+</TITLE>'  # Sample titles like "CTNNB1 1"
    ]
    
    # Enhanced genotype patterns for complex genotypes like CK5PIP
    genotype_patterns = [
        r'<TAG>genotype</TAG>\s*<VALUE>([A-Z0-9]+[A-Z0-9]*)</VALUE>',  # XML genotype tag
        r'genotype:\s*([A-Z0-9]+[A-Z0-9]*)',  # GEO format genotype
        r'\bgenotype[:\s]+([A-Z0-9]+[A-Z0-9]*)\b',  # General genotype pattern
        r'\b(CK5PIP|CK5[A-Z0-9]*)\b',  # Specific CK5 patterns
        r'\b([A-Z]{2,}[0-9]+[A-Z]*)\b'  # Complex genotype patterns like CK5PIP
    ]
    overexpression_genes = set()
    for pattern in overexpression_patterns:
        matches = re.finditer(pattern, original_text, re.IGNORECASE)
        for match in matches:
            gene = match.group(1).strip().upper()
            if len(gene) > 1 and gene not in ['CELLS', 'CELL', 'LINE', 'SAMPLE', 'CAUSED', 'DATASET']:
                overexpression_genes.add(gene)
    
    # Process genotype patterns for complex genotypes
    genotype_treatments = set()
    for pattern in genotype_patterns:
        matches = re.finditer(pattern, original_text, re.IGNORECASE)
        for match in matches:
            genotype = match.group(1).strip().upper()
            if len(genotype) > 2 and genotype not in ['CELLS', 'CELL', 'LINE', 'SAMPLE', 'WILD', 'TYPE', 'WT']:
                # Special handling for known genotype patterns
                if 'CK5' in genotype or genotype == 'CK5PIP':
                    genotype_treatments.add(genotype)
                elif len(genotype) >= 4 and any(c.isdigit() for c in genotype):  # Complex genotypes with numbers
                    genotype_treatments.add(genotype)
        
    # Enhanced drug/compound patterns
    drug_patterns = [
        r'\btreated with ([a-zA-Z0-9\-]+)', r'\b([a-zA-Z0-9\-]+)[-_\s]treated\b',
        r'\benzalutamide\b', r'\benza\b', r'\bprt2527\b', r'\bjq1\b',
        r'(\d+)\s*nm\s+([a-zA-Z0-9\-]+)',  # "100 nM PRT2527"
        r'([a-zA-Z0-9\-]+)\s+(\d+)\s*nm',  # "PRT2527 100 nM"
        r'compound.*?([a-zA-Z0-9\-]+)',
        r'drug.*?([a-zA-Z0-9\-]+)'
    ]
    treated_compounds = set()
    for pattern in drug_patterns:
        matches = re.finditer(pattern, text_lower)
        for match in matches:
            if len(match.groups()) >= 2:  # Concentration patterns
                compound = match.group(2) if match.group(2).isalpha() else match.group(1)
            else:
                compound = match.group(1) if match.groups() else match.group(0)
            
            compound = compound.strip()
            if compound and len(compound) > 1:
                if 'enza' in compound: treated_compounds.add('Enzalutamide')
                elif 'prt2527' in compound: treated_compounds.add('PRT2527')
                elif 'jq1' in compound: treated_compounds.add('JQ1')
                elif compound not in ['dmso', 'were', 'the', 'and', 'with'] and compound.isalpha():
                    treated_compounds.add(compound.upper())

    # Build treatment list with priority
    treatments = []
    
    # Add gene modifications first
    treatments.extend([f"{g}_knockout" for g in sorted(knockout_genes)])
    treatments.extend([f"{g}_knockdown" for g in sorted(knockdown_genes)])
    treatments.extend([f"{g}_overexpression" for g in sorted(overexpression_genes)])
    
    # Add genotype treatments (like CK5PIP)
    treatments.extend(sorted(genotype_treatments))
        
    # Add compound treatments
    treatments.extend([f"{c}_treated" for c in sorted(treated_compounds)])
    
    # Handle DMSO control case
    if is_dmso_control and not treatments:
        return "DMSO_control"
    
    # Return treatments or control status
    if treatments:
        return " + ".join(treatments[:2])  # Limit to 2 main treatments
    
    return "control" if has_control else "WT"

def detect_chipseq_info(text: str) -> tuple[str, str]:
    """Detect ChIP-seq related information from text."""
    if not text or text == "N/A":
        return "no", "N/A"
    
    text_lower = str(text).lower()
    
    is_chipseq = "no"
    if any(term in text_lower for term in ["chip-seq", "chipseq"]):
        is_chipseq = "yes"
    
    antibody_target = "N/A"
    if is_chipseq == "yes":
        target_patterns = [
            r'anti-([A-Z0-9]+)', r'chip-seq\s+for\s+([A-Z0-9]+)', 
            r'([A-Z0-9]+)\s+chip-seq', r'(H3K\d+[a-z0-9]*)'
        ]
        for pattern in target_patterns:
            match = re.search(pattern, str(text), re.IGNORECASE)
            if match:
                target = match.group(1).strip().upper()
                if len(target) > 1 and target not in ['INPUT', 'IGG']:
                    antibody_target = target
                    break
    
    return is_chipseq, antibody_target

def llm_single_call(prompt: str, llm_proc: SimpleLLMProcessor, sample_id: str = "default") -> Optional[str]:
    """Invoke the underlying Ollama model with the raw prompt and return the response text."""
    return llm_proc.invoke(prompt, sample_id)

def process_single_srx(srx_id: str, keyword: str, llm_proc: SimpleLLMProcessor, entrez: EntrezClient) -> Optional[List[str]]:
    """Fetch SRA XML, extract metadata using LLM with study-based context sharing."""
    xml_content = entrez.efetch_sra_experiment_xml(srx_id)
    if not xml_content:
        return None
    
    geo_ids = extract_geo_accessions(xml_content)
    geo_summary = fetch_geo_soft_brief(geo_ids["gsm"])

    gse_id, gsm_id = geo_ids["gse"], geo_ids["gsm"]

    # -----------------------------
    # STUDY-BASED LLM PROCESSING
    # -----------------------------
    
    # Get study-specific LLM instance and context
    if hasattr(llm_proc, 'get_llm_for_study'):
        llm_instance, study_context = llm_proc.get_llm_for_study(srx_id, gse_id)
    else:
        llm_instance = llm_proc.llm
        study_context = {}

    # Build comprehensive prompt with study context
    prompt = build_prompt(xml_content, geo_summary, srx_id, gse_id, gsm_id, keyword, study_context)
    
    # Use study-specific LLM instance
    if llm_instance:
        try:
            llm_response = llm_instance.invoke(prompt)
            llm_response = llm_response.content if hasattr(llm_response, 'content') else str(llm_response)
        except Exception as e:
            print(f"Warning: Study LLM invocation failed for {srx_id}: {e}", file=sys.stderr)
            llm_response = None
    else:
        llm_response = None

    # Default placeholders for all fields
    parsed_data = {k: "N/A" for k in [
        'species', 'sequencing_technique', 'sample_type', 'cell_line_name', 'tissue_type',
        'disease_description', 'treatment', 'instrument_model', 'is_chipseq_related_experiment',
        'chipseq_antibody_target', 'scientific_sample_summary']}

    # Parse LLM structured response if available
    if llm_response:
        parsed_data.update(llm_proc._parse_llm_response(llm_response))
        
        # STUDY CONSISTENCY VALIDATION
        # Check for major inconsistencies within the same study
        if hasattr(llm_proc, '_study_context') and llm_proc._study_context:
            study_context = llm_proc._study_context
            
            # Validate species consistency
            if 'species' in study_context and parsed_data['species'] != 'N/A':
                prev_species = study_context['species']
                if isinstance(prev_species, list) and len(prev_species) == 1:
                    expected_species = prev_species[0]
                    if parsed_data['species'] != expected_species:
                        print(f"🔧 Species consistency fix for {srx_id}: '{parsed_data['species']}' → '{expected_species}' (same study)", file=sys.stderr)
                        parsed_data['species'] = expected_species
            
            # Validate cell line consistency for cell line studies
            if 'cell_line_name' in study_context and parsed_data['sample_type'] == 'Cell Line':
                prev_cell_lines = study_context['cell_line_name']
                if isinstance(prev_cell_lines, list) and len(prev_cell_lines) == 1:
                    expected_cell_line = prev_cell_lines[0]
                    if parsed_data['cell_line_name'] != expected_cell_line and parsed_data['cell_line_name'] == 'N/A':
                        print(f"🔧 Cell line consistency fix for {srx_id}: 'N/A' → '{expected_cell_line}' (same study)", file=sys.stderr)
                        parsed_data['cell_line_name'] = expected_cell_line

    # Handle study-level summary generation and reuse
    if hasattr(llm_proc, 'get_study_summary'):
        existing_summary = llm_proc.get_study_summary()
        if existing_summary != "N/A":
            # Reuse existing study summary
            parsed_data['scientific_sample_summary'] = existing_summary
            print(f"♻️ Reusing study summary for {srx_id}", file=sys.stderr)
        elif parsed_data['scientific_sample_summary'] != "N/A":
            # Save new summary for the study
            llm_proc.set_study_summary(parsed_data['scientific_sample_summary'])
            print(f"💾 Saved study summary from {srx_id}", file=sys.stderr)

    # Update study context for future samples in this study
    if hasattr(llm_proc, 'update_study_context'):
        if parsed_data['cell_line_name'] != 'N/A':
            llm_proc.update_study_context('cell_line_name', parsed_data['cell_line_name'])
        if parsed_data['species'] != 'N/A':
            llm_proc.update_study_context('species', parsed_data['species'])
        if parsed_data['sequencing_technique'] != 'N/A':
            llm_proc.update_study_context('sequencing_technique', parsed_data['sequencing_technique'])
        if parsed_data['sample_type'] != 'N/A':
            llm_proc.update_study_context('sample_type', parsed_data['sample_type'])
        if parsed_data['disease_description'] != 'N/A':
            llm_proc.update_study_context('disease_description', parsed_data['disease_description'])
        if parsed_data['treatment'] != 'N/A':
            llm_proc.update_study_context('treatment', parsed_data['treatment'])

    # Normalise boolean field
    is_chipseq = parsed_data['is_chipseq_related_experiment'].lower() if parsed_data['is_chipseq_related_experiment'] != 'N/A' else 'no'

    # Build final result list in correct order
    result = [
        srx_id,
        gse_id,
        gsm_id,
        parsed_data['species'],
        parsed_data['sequencing_technique'],
        parsed_data['sample_type'],
        parsed_data['cell_line_name'],
        parsed_data['tissue_type'],
        parsed_data['disease_description'],
        parsed_data['treatment'],
        is_chipseq,
        parsed_data['chipseq_antibody_target'],
        parsed_data['scientific_sample_summary']
    ]
    return result

def start_streaming_download(keyword: str, file_path: str) -> threading.Thread:
    """Starts incremental download that merges new samples every 1000 rows during download."""
    def worker():
        print(f"INFO: Starting true incremental download for '{keyword}' to {file_path}", file=sys.stderr)
        
        # Create empty file immediately to prevent timeout
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("")  # Create empty file immediately
            print(f"INFO: Created initial file: {file_path}", file=sys.stderr)
        except Exception as e:
            print(f"ERROR: Failed to create initial file {file_path}: {e}", file=sys.stderr)
            return
        
        # Check if NCBI tools are available (using global verification)
        if not NCBI_TOOLS_AVAILABLE:
            print(f"ERROR: NCBI E-utilities are not available or not working properly", file=sys.stderr)
            print(f"ERROR: Data download cannot proceed without NCBI tools", file=sys.stderr)
            print(f"INFO: Please check the diagnostic information shown at startup", file=sys.stderr)
            
            # Create minimal CSV header so processing can continue
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("Run,ReleaseDate,LoadDate,spots,bases,spots_with_mates,avgLength,size_MB,AssemblyName,download_path,Experiment,LibraryName,LibraryStrategy,LibrarySelection,LibrarySource,LibraryLayout,InsertSize,InsertDev,Platform,Model,SRAStudy,BioProject,Study_Pubmed_id,ProjectID,Sample,BioSample,SampleType,TaxID,ScientificName,SampleName,g1k_pop_code,source,g1k_analysis_group,Subject_ID,Sex,Disease,Tumor,Affection_Status,Analyte_Type,Histological_Type,Body_Site,CenterName,Submission,dbgap_study_accession,Consent,RunHash,ReadHash\n")
                print(f"INFO: Created minimal CSV header for offline processing", file=sys.stderr)
            except Exception as e2:
                print(f"ERROR: Failed to create CSV header: {e2}", file=sys.stderr)
            return
        
        # Double-check tools are still working (they might have been available at startup but failed later)
        try:
            subprocess.run(["esearch", "-help"], capture_output=True, check=True, text=True, timeout=10)
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
            print(f"ERROR: NCBI esearch tool not working: {e}", file=sys.stderr)
            print(f"ERROR: Tools were available at startup but failed during execution", file=sys.stderr)
            print_ncbi_diagnostic_info()
            # Create minimal CSV header so processing can continue
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("Run,ReleaseDate,LoadDate,spots,bases,spots_with_mates,avgLength,size_MB,AssemblyName,download_path,Experiment,LibraryName,LibraryStrategy,LibrarySelection,LibrarySource,LibraryLayout,InsertSize,InsertDev,Platform,Model,SRAStudy,BioProject,Study_Pubmed_id,ProjectID,Sample,BioSample,SampleType,TaxID,ScientificName,SampleName,g1k_pop_code,source,g1k_analysis_group,Subject_ID,Sex,Disease,Tumor,Affection_Status,Analyte_Type,Histological_Type,Body_Site,CenterName,Submission,dbgap_study_accession,Consent,RunHash,ReadHash\n")
                print(f"INFO: Created minimal CSV header for offline processing", file=sys.stderr)
            except Exception as e2:
                print(f"ERROR: Failed to create CSV header: {e2}", file=sys.stderr)
            return
        
        # Enhanced search query builder to support multi-word keywords and broader coverage
        words = [w.strip() for w in keyword.split() if w.strip()]
        fields = ["All Fields", "Title", "Abstract", "Study Title", "Study Abstract", "Sample Name", "Organism", "Strain", "Cell Line", "Cell Type", "Tissue", "Source Name"]
        query_parts = []
        for field in fields:
            if len(words) > 1:
                phrase_part = f'"{keyword}"[{field}]'
                word_part = ' AND '.join([f'"{w}"[{field}]' for w in words])
                query_parts.append(f'({phrase_part} OR ({word_part}))')
            else:
                query_parts.append(f'"{keyword}"[{field}]')
        enhanced_query = ' OR '.join(query_parts)
        
        # Wrap query in parentheses for safety
        enhanced_query = f'({enhanced_query})'
        
        esearch_cmd = ["esearch", "-db", "sra", "-query", enhanced_query]
        efetch_cmd = ["efetch", "-format", "runinfo"]
        
        print(f"INFO: Using enhanced search query: {enhanced_query}", file=sys.stderr)

        try:
            temp_file = f"{file_path}.tmp"
            
            print(f"INFO: Downloading fresh data from NCBI for '{keyword}' with incremental merging...", file=sys.stderr)
            
            # Start download process without waiting for completion
            with open(temp_file, 'w', encoding='utf-8') as f_temp:
                try:
                    esearch_proc = subprocess.Popen(esearch_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    efetch_proc = subprocess.Popen(efetch_cmd, stdin=esearch_proc.stdout, stdout=f_temp, stderr=subprocess.PIPE, text=True)
                    
                    esearch_proc.stdout.close()
                    
                    # Monitor download progress and merge incrementally
                    merged_samples = 0
                    last_temp_size = 0
                    no_growth_cycles = 0
                    download_timeout = 300  # 5 minute timeout for download
                    download_start_time = time.time()
                    
                    while efetch_proc.poll() is None:  # While download is running
                        time.sleep(2)  # Check every 2 seconds
                        
                        # Check for download timeout
                        if time.time() - download_start_time > download_timeout:
                            print(f"WARNING: Download timeout after {download_timeout}s, terminating processes", file=sys.stderr)
                            efetch_proc.terminate()
                            esearch_proc.terminate()
                            break
                        
                        if os.path.exists(temp_file):
                            current_temp_size = os.path.getsize(temp_file)
                            
                            # If temp file has grown significantly, try incremental merge
                            if current_temp_size > last_temp_size + 10000:  # Reduced threshold to 10KB
                                print(f"INFO: Temp file grew to {current_temp_size} bytes, attempting incremental merge...", file=sys.stderr)
                                new_merged = incremental_merge_from_temp(temp_file, file_path, keyword, last_temp_size)
                                if new_merged > 0:
                                    merged_samples += new_merged
                                    print(f"INFO: Incrementally merged {new_merged} new samples (total: {merged_samples})", file=sys.stderr)
                                last_temp_size = current_temp_size
                                no_growth_cycles = 0
                            else:
                                no_growth_cycles += 1
                    
                    # Wait for process completion with timeout
                    try:
                        _, efetch_stderr = efetch_proc.communicate(timeout=30)
                        _, esearch_stderr = esearch_proc.communicate(timeout=30)
                    except subprocess.TimeoutExpired:
                        print(f"WARNING: Process cleanup timeout, force terminating", file=sys.stderr)
                        efetch_proc.kill()
                        esearch_proc.kill()
                        efetch_stderr = "Process killed due to timeout"
                        esearch_stderr = "Process killed due to timeout"
                    
                    # Always try final merge, even if download failed
                    if os.path.exists(temp_file) and os.path.getsize(temp_file) > 0:
                        print(f"INFO: Download completed, performing final merge...", file=sys.stderr)
                        final_merged = incremental_merge_from_temp(temp_file, file_path, keyword, 0, final_merge=True)
                        merged_samples += final_merged
                        print(f"INFO: Final merge added {final_merged} samples. Total merged: {merged_samples}", file=sys.stderr)
                        
                        # Clean up temp file
                        os.remove(temp_file)
                    else:
                        print(f"WARNING: No data downloaded or temp file empty for '{keyword}'", file=sys.stderr)

                    if efetch_proc.returncode != 0:
                        print(f"ERROR: efetch process failed for '{keyword}'. Stderr: {efetch_stderr}", file=sys.stderr)
                    if esearch_proc.returncode != 0:
                        print(f"ERROR: esearch process failed for '{keyword}'. Stderr: {esearch_stderr}", file=sys.stderr)
                        
                except Exception as e:
                    print(f"ERROR: Exception during subprocess execution: {e}", file=sys.stderr)
                    
            # Ensure main file has at least a header if no data was merged
            if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
                print(f"INFO: Creating CSV header for '{keyword}' since no data was downloaded", file=sys.stderr)
                try:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write("Run,ReleaseDate,LoadDate,spots,bases,spots_with_mates,avgLength,size_MB,AssemblyName,download_path,Experiment,LibraryName,LibraryStrategy,LibrarySelection,LibrarySource,LibraryLayout,InsertSize,InsertDev,Platform,Model,SRAStudy,BioProject,Study_Pubmed_id,ProjectID,Sample,BioSample,SampleType,TaxID,ScientificName,SampleName,g1k_pop_code,source,g1k_analysis_group,Subject_ID,Sex,Disease,Tumor,Affection_Status,Analyte_Type,Histological_Type,Body_Site,CenterName,Submission,dbgap_study_accession,Consent,RunHash,ReadHash\n")
                except Exception as e:
                    print(f"ERROR: Failed to create fallback CSV header: {e}", file=sys.stderr)

        except Exception as e:
            print(f"ERROR: Exception during incremental download for '{keyword}': {e}", file=sys.stderr)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    return thread

def incremental_merge_from_temp(temp_file: str, main_file: str, keyword: str, skip_bytes: int = 0, final_merge: bool = False) -> int:
    """
    Incrementally merge new samples from temp file to main file.
    skip_bytes: Skip this many bytes from start of temp file (already processed)
    final_merge: If True, process entire temp file and clean XML errors
    """
    if not os.path.exists(temp_file) or os.path.getsize(temp_file) <= skip_bytes:
        return 0
    
    # Load existing SRX IDs from main file to avoid duplicates
    existing_srx_ids = set()
    if os.path.exists(main_file) and os.path.getsize(main_file) > 100:
        try:
            with open(main_file, 'r', encoding='utf-8') as f:
                csv.field_size_limit(sys.maxsize)
                reader = csv.reader(f)
                header = next(reader, None)
                if header and 'Experiment' in header:
                    srx_col_idx = header.index('Experiment')
                    for row in reader:
                        if len(row) > srx_col_idx:
                            srx_id = row[srx_col_idx].strip()
                            if srx_id.startswith(('SRX', 'ERX', 'DRX')):
                                existing_srx_ids.add(srx_id)
        except Exception:
            pass  # Continue without duplicate checking if file read fails
    
    new_samples = []
    header_row = None
    
    try:
        with open(temp_file, 'r', encoding='utf-8') as f:
            # Skip bytes already processed
            f.seek(skip_bytes)
            
            if final_merge:
                # For final merge, clean XML and process all remaining data
                remaining_content = f.read()
                if remaining_content:
                    # Filter XML errors
                    clean_lines = []
                    in_xml_block = False
                    for line in remaining_content.split('\n'):
                        if line.strip().startswith('<?xml'):
                            in_xml_block = True
                            continue
                        elif in_xml_block and line.strip().startswith('</eFetchResult>'):
                            in_xml_block = False
                            continue
                        elif not in_xml_block and line.strip():
                            clean_lines.append(line)
                    
                    if clean_lines:
                        import io
                        clean_csv = io.StringIO('\n'.join(clean_lines))
                        csv.field_size_limit(sys.maxsize)
                        reader = csv.reader(clean_csv)
                        try:
                            header_row = next(reader)
                            if 'Experiment' in header_row:
                                srx_col_idx = header_row.index('Experiment')
                                lib_strategy_col_idx = header_row.index('LibraryStrategy') if 'LibraryStrategy' in header_row else -1
                                
                                for row in reader:
                                    if len(row) > srx_col_idx:
                                        srx_id = row[srx_col_idx].strip()
                                        if srx_id not in existing_srx_ids and srx_id.startswith(('SRX', 'ERX', 'DRX')):
                                            # Apply filtering
                                            if lib_strategy_col_idx >= 0 and len(row) > lib_strategy_col_idx:
                                                lib_strategy = row[lib_strategy_col_idx].strip()
                                                if lib_strategy in EXCLUDED_LIBRARY_STRATEGIES:
                                                    continue
                                            new_samples.append(row)
                                            existing_srx_ids.add(srx_id)
                        except Exception:
                            pass
            else:
                # For incremental merge, process line by line from current position
                lines_processed = 0
                for line in f:
                    lines_processed += 1
                    if lines_processed > 1000:  # Limit incremental processing
                        break
                        
                    try:
                        if line.strip() and not line.startswith('<?xml') and not line.startswith('<eFetchResult>'):
                            row = next(csv.reader([line]))
                            if len(row) > 10:  # Reasonable number of columns
                                if not header_row and 'Experiment' in row:
                                    header_row = row
                                    continue
                                elif header_row and 'Experiment' in header_row:
                                    srx_col_idx = header_row.index('Experiment')
                                    if len(row) > srx_col_idx:
                                        srx_id = row[srx_col_idx].strip()
                                        if srx_id not in existing_srx_ids and srx_id.startswith(('SRX', 'ERX', 'DRX')):
                                            new_samples.append(row)
                                            existing_srx_ids.add(srx_id)
                    except Exception:
                        continue
    
    except Exception as e:
        print(f"WARNING: Error during incremental merge: {e}", file=sys.stderr)
        return 0
    
    # Write new samples to main file
    if new_samples:
        file_exists = os.path.exists(main_file) and os.path.getsize(main_file) > 0
        write_mode = 'a' if file_exists else 'w'
        
        try:
            with open(main_file, write_mode, newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # Write header if this is a new file
                if not file_exists and header_row:
                    writer.writerow(header_row)
                
                # Write new samples
                for row in new_samples:
                    writer.writerow(row)
                    
                # Force write to disk
                f.flush()
                os.fsync(f.fileno())
                    
        except Exception as e:
            print(f"ERROR: Failed to write incremental samples: {e}", file=sys.stderr)
            return 0
    
    return len(new_samples)

def read_runinfo_batches(file_path: str, batch_size: int = BATCH_SIZE, download_thread: threading.Thread = None) -> Iterator[List[str]]:
    """Reads runinfo CSV in batches with enhanced sample tracking to fix resume logic."""
    print(f"INFO: Starting incremental processing with enhanced tracking of {file_path}", file=sys.stderr)
    
    # Wait for file to exist or be created
    wait_time = 0
    while not os.path.exists(file_path):
        time.sleep(1)
        wait_time += 1
        if wait_time > 120:  # Increased timeout for better reliability
            print(f"ERROR: Timeout waiting for {file_path} to be created after {wait_time} seconds.", file=sys.stderr)
            print(f"ERROR: This usually indicates NCBI E-utilities installation issues.", file=sys.stderr)
            print(f"ERROR: Please check that 'esearch' and 'efetch' commands are installed and working.", file=sys.stderr)
            return
        elif wait_time % 30 == 0:  # Progress update every 30 seconds
            print(f"INFO: Still waiting for {file_path} to be created... ({wait_time}s elapsed)", file=sys.stderr)
    
    print(f"INFO: File {file_path} found, starting processing", file=sys.stderr)

    # Enhanced tracking: monitor both total and eligible samples
    processed_rows = 0
    eligible_samples_found = 0      # NEW: Only count samples that pass library strategy filter
    excluded_by_strategy = 0        # NEW: Count samples filtered out by library strategy
    last_file_size = 0
    no_change_cycles = 0
    MAX_NO_CHANGE_CYCLES = 10  # Shorter wait since we process incrementally
    header_processed = False
    srx_col_idx = lib_strategy_col_idx = 0

    while True:
        try:
            current_file_size = os.path.getsize(file_path)
            
            # Process new data if file has grown or we haven't processed header
            if current_file_size > last_file_size or not header_processed:
                last_file_size = current_file_size
                no_change_cycles = 0
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    csv.field_size_limit(sys.maxsize)
                    reader = csv.reader(f)
                    
                    # Process header once
                    if not header_processed:
                        try:
                            header = next(reader)
                            srx_col_idx = header.index('Experiment')
                            lib_strategy_col_idx = header.index('LibraryStrategy')
                            header_processed = True
                            print(f"INFO: Header processed, starting incremental sample processing...", file=sys.stderr)
                        except (ValueError, StopIteration):
                            time.sleep(1)
                            continue

                    # Skip rows we've already processed
                    for _ in range(processed_rows):
                        next(reader, None)

                    batch = []
                    new_rows_this_cycle = 0
                    new_eligible_this_cycle = 0     # NEW
                    new_excluded_this_cycle = 0     # NEW
                    
                    for row in reader:
                        processed_rows += 1
                        new_rows_this_cycle += 1
                        
                        try:
                            if len(row) <= max(lib_strategy_col_idx, srx_col_idx):
                                continue
                        
                            lib_strategy = row[lib_strategy_col_idx].strip()
                            srx_id = row[srx_col_idx].strip()
                            
                            if srx_id.startswith(('SRX', 'ERX', 'DRX')):
                                # NEW: Check library strategy filter
                                if lib_strategy in EXCLUDED_LIBRARY_STRATEGIES:
                                    excluded_by_strategy += 1
                                    new_excluded_this_cycle += 1
                                    continue  # Skip this sample - it's filtered out
                                
                                # This sample is eligible for processing
                                eligible_samples_found += 1
                                new_eligible_this_cycle += 1
                                batch.append(srx_id)
                            
                            # Yield batch when it reaches batch_size
                            if len(batch) >= batch_size:
                                yield batch
                                batch = []
                                
                        except (IndexError, ValueError) as e:
                            print(f"WARNING: Skipping malformed CSV row {processed_rows}: {e}", file=sys.stderr)
                            continue
                    
                    # Yield any remaining samples in batch
                    if batch:
                        yield batch
                    
                    # Enhanced progress reporting
                    if new_rows_this_cycle > 0:
                        print(f"INFO: Processed {new_rows_this_cycle} new rows - "
                              f"Eligible: {new_eligible_this_cycle}, "
                              f"Excluded by strategy: {new_excluded_this_cycle} "
                              f"(Total eligible: {eligible_samples_found}, "
                              f"Total excluded: {excluded_by_strategy})", file=sys.stderr)

            else:
                no_change_cycles += 1
                time.sleep(2)  # Shorter sleep for more responsive processing
            
            # Fixed exit condition - check eligible samples vs download status
            if no_change_cycles > MAX_NO_CHANGE_CYCLES:
                if download_thread is None or not download_thread.is_alive():
                    print(f"INFO: Download complete. Total rows: {processed_rows}, "
                          f"Eligible samples: {eligible_samples_found}, "
                          f"Excluded by strategy: {excluded_by_strategy}", file=sys.stderr)
                    break
                else:
                    print(f"INFO: Download active - Eligible: {eligible_samples_found}, "
                          f"Excluded: {excluded_by_strategy}, waiting for more...", file=sys.stderr)
                    no_change_cycles = 0  # Reset since download is active
        
        except FileNotFoundError:
            time.sleep(1)
        except Exception as e:
            print(f"ERROR: Failed to read or parse {file_path}: {e}", file=sys.stderr)
            time.sleep(3)

def _process_complete_file(file_path: str, batch_size: int) -> Iterator[List[str]]:
    """This function is now deprecated - we always use incremental processing."""
    print(f"INFO: Using incremental processing instead of complete file processing", file=sys.stderr)
    return iter([])  # Return empty iterator

def _process_file_incrementally(file_path: str, batch_size: int, download_thread: threading.Thread) -> Iterator[List[str]]:
    """This is now handled by the main read_runinfo_batches function.""" 
    return iter([])  # Return empty iterator

def stream_process_keyword(keyword: str, output_csv: str, llm_proc: SimpleLLMProcessor, entrez: EntrezClient, append: bool = False):
    """Main streaming workflow for a single keyword."""
    print(f"\nINFO: Processing keyword '{keyword}'. Append mode: {append}", file=sys.stderr)

    # Load already processed samples for resume functionality
    already_processed = load_already_processed_samples(output_csv) if append else set()

    output_dir = os.path.dirname(os.path.abspath(output_csv))
    try:
        os.makedirs(output_dir, exist_ok=True)
        print(f"INFO: Output directory created/verified: {output_dir}", file=sys.stderr)
    except Exception as e:
        print(f"ERROR: Failed to create output directory {output_dir}: {e}", file=sys.stderr)
        raise
    
    # Sanitize keyword for filename
    sanitized_keyword = keyword.replace(' ', '_').replace('/', '_').replace('\\', '_')
    runinfo_path = os.path.join(output_dir, f"efetched_{sanitized_keyword}.csv")
    print(f"INFO: Will create intermediate file: {runinfo_path}", file=sys.stderr)

    download_thread = start_streaming_download(keyword, runinfo_path)
    
    mode = 'a' if append else 'w'
    with open(output_csv, mode, newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile, quoting=csv.QUOTE_ALL)
        if not append:
            writer.writerow(OUTPUT_COLUMNS)
        
        # Enhanced tracking of different types of skipping
        total_processed = 0
        total_skipped_resume = 0      # Already processed (resume)
        total_eligible_encountered = 0 # Total eligible samples seen
        
        with tqdm(desc=f"Processing '{keyword}'", unit=" samples") as pbar:
            for batch in read_runinfo_batches(runinfo_path, download_thread=download_thread):
                for srx_id in batch:
                    try:
                        total_eligible_encountered += 1
                        
                        # Skip if already processed (resume functionality)
                        if srx_id in already_processed:
                            total_skipped_resume += 1
                            if total_skipped_resume % 100 == 0:
                                print(f"INFO: Resume skipped {total_skipped_resume} already-processed samples", file=sys.stderr)
                            continue
                            
                        result = process_single_srx(srx_id, keyword, llm_proc, entrez)
                        if result:
                            writer.writerow(result)
                            csvfile.flush()
                            total_processed += 1
                            pbar.update(1)
                            
                            if total_processed % 10 == 0:
                                print(f"INFO: Processed {total_processed} new samples - "
                                      f"Resume skipped: {total_skipped_resume}, "
                                      f"Total eligible seen: {total_eligible_encountered}", file=sys.stderr)
                    
                    except Exception as e:
                        print(f"ERROR: Failed to process {srx_id}: {e}", file=sys.stderr)
                        continue

    download_thread.join(timeout=10)
    
    # Comprehensive final summary
    print(f"INFO: Completed processing '{keyword}':", file=sys.stderr)
    print(f"  - New samples processed: {total_processed}", file=sys.stderr)
    print(f"  - Samples skipped (resume): {total_skipped_resume}", file=sys.stderr)
    print(f"  - Total eligible samples encountered: {total_eligible_encountered}", file=sys.stderr)
    print(f"  - Samples filtered by library strategy: (handled in download phase)", file=sys.stderr)

def main():
    """Main function."""
    # Register cleanup handlers first
    register_cleanup()
    
    # Create PID file for tracking
    pid_file = create_pid_file()
    
    parser = argparse.ArgumentParser(description="SRA/GEO Metadata Extraction with LLM (1b optimized)")
    parser.add_argument("--keywords", required=True, help="CSV file with keywords")
    parser.add_argument("--output", required=True, help="Output CSV file")
    parser.add_argument("--model", default="qwen3:8b", help="LLM model name")
    parser.add_argument("--append", action="store_true", help="Append to existing output file")
    
    args = parser.parse_args()
    
    print("🧬 SRA/GEO Metadata Extraction with LLM (1b optimized)")
    print("=" * 60)
    
    try:
        # Initialize LLM processor
        llm_proc = SimpleLLMProcessor(args.model)
        entrez = EntrezClient()
        
        # Read keywords using KeywordProvider
        provider = KeywordProvider(args.keywords)
        keywords = provider.get_keywords()
        
        print(f"INFO: Found {len(keywords)} keywords to process")
        
        # Process each keyword
        for i, keyword in enumerate(keywords):
            print(f"\nProcessing keyword {i+1}/{len(keywords)}: '{keyword}'")
            try:
                stream_process_keyword(keyword, args.output, llm_proc, entrez, append=(args.append or i > 0))
            except Exception as e:
                print(f"ERROR: Failed to process keyword '{keyword}': {e}", file=sys.stderr)
                continue
        
        print("\n✅ Processing completed successfully!", file=sys.stderr)
        
        # Auto-generate visualizations
        print("🎨 Auto-generating visualizations...", file=sys.stderr)
        try:
            # Run visualization script
            viz_result = subprocess.run([
                sys.executable, "visualize_results.py"
            ], capture_output=True, text=True, timeout=300)
            
            if viz_result.returncode == 0:
                print("✅ Visualizations generated successfully!", file=sys.stderr)
                
                # Run HTML report generation
                html_result = subprocess.run([
                    sys.executable, "generate_html_report.py"
                ], capture_output=True, text=True, timeout=60)
                
                if html_result.returncode == 0:
                    print("✅ HTML report generated successfully!", file=sys.stderr)
                    print("📊 Visualization files available in 'visualizations/' directory", file=sys.stderr)
                    print("🌐 Open 'sra_geo_analysis_report.html' to view complete report", file=sys.stderr)
                else:
                    print(f"⚠️ HTML report generation failed: {html_result.stderr}", file=sys.stderr)
            else:
                print(f"⚠️ Visualization generation failed: {viz_result.stderr}", file=sys.stderr)
                
        except subprocess.TimeoutExpired:
            print("⚠️ Visualization generation timed out", file=sys.stderr)
        except Exception as e:
            print(f"⚠️ Error generating visualizations: {e}", file=sys.stderr)
        
        print("🧹 Running automatic cleanup...", file=sys.stderr)
        
    except KeyboardInterrupt:
        print("\nINFO: Processing interrupted by user", file=sys.stderr)
    except Exception as e:
        print(f"ERROR: Unexpected error in main: {e}", file=sys.stderr)
    finally:
        cleanup_ollama_processes()
        restart_ollama_service()
        remove_pid_file(pid_file)
        print("🎯 Script execution finished with cleanup and restart completed.", file=sys.stderr)

# -------------------------
# Helper utility functions
# -------------------------

def _is_uninformative_treatment(t: str) -> bool:
    """Return True if treatment string is clearly uninformative (generic or garbage)."""
    if not t or t.upper() in {"WT", "N/A"}:
        return True
    tl = t.lower().strip()
    # Only catch obviously meaningless terms
    if tl in ["treatment", "n/a", "na", ""]:
        return True
    return False

def load_already_processed_samples(csv_path: str) -> set:
    """Load SRX IDs with enhanced debugging for resume logic."""
    processed_samples = set()
    
    if not os.path.exists(csv_path):
        print(f"INFO: No existing result file found at {csv_path} - starting fresh", file=sys.stderr)
        return processed_samples
    
    try:
        total_rows = 0
        valid_samples = 0
        error_entries = 0
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                total_rows += 1
                srx_id = row.get('sra_experiment_id', '').strip()
                
                if srx_id and srx_id.startswith(('SRX', 'ERX', 'DRX')):
                    # Check for error entries
                    if any(error_text in srx_id for error_text in ['NO_SRA_IDS_FOUND', 'TIMEOUT_ERROR', 'PROCESSING_ERROR']):
                        error_entries += 1
                    else:
                        processed_samples.add(srx_id)
                        valid_samples += 1
        
        print(f"INFO: Resume analysis of {csv_path}:", file=sys.stderr)
        print(f"  - Total rows in result file: {total_rows}", file=sys.stderr)
        print(f"  - Valid processed samples: {valid_samples}", file=sys.stderr)
        print(f"  - Error entries: {error_entries}", file=sys.stderr)
        print(f"  - Will skip {len(processed_samples)} samples in resume mode", file=sys.stderr)
        
        if len(processed_samples) > 0:
            sample_preview = list(processed_samples)[:5]
            print(f"INFO: Sample of processed SRX IDs: {sample_preview}", file=sys.stderr)
            
    except Exception as e:
        print(f"WARNING: Failed to load existing results from {csv_path}: {e}", file=sys.stderr)
        print("INFO: Continuing with fresh processing", file=sys.stderr)
    
    return processed_samples

if __name__ == "__main__":
    main() 