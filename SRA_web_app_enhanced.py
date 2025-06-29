import os
import sys
import subprocess
import tempfile
import csv
import time
import threading
import queue
import signal
import datetime
from pathlib import Path
import pandas as pd
import base64
from PIL import Image
import io

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

# -----------------------
# Helper functions
# -----------------------

def cleanup_ollama_processes():
    """Clean up any orphaned Ollama model processes and SRA script processes."""
    try:
        # Method 1: Clean up qwen3 and other model processes
        result = subprocess.run(['pgrep', '-f', 'ollama runner'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                if pid.strip():
                    try:
                        subprocess.run(['kill', '-TERM', pid], timeout=5)
                        time.sleep(1)
                        # Check if still running, force kill
                        check_result = subprocess.run(['ps', '-p', pid], 
                                                    capture_output=True, text=True)
                        if check_result.returncode == 0:
                            subprocess.run(['kill', '-KILL', pid], timeout=5)
                    except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                        pass  # Process already gone or can't be killed
        
        # Method 2: Clean up SRA script processes (but not current process)
        current_pid = os.getpid()
        sra_result = subprocess.run(['pgrep', '-f', 'SRA_fetch_1LLM_improved.py'], 
                                  capture_output=True, text=True)
        if sra_result.returncode == 0:
            sra_pids = sra_result.stdout.strip().split('\n')
            for pid in sra_pids:
                if pid.strip() and int(pid) != current_pid:
                    try:
                        subprocess.run(['kill', '-TERM', pid], timeout=5)
                        time.sleep(1)
                        # Force kill if still running
                        check_result = subprocess.run(['ps', '-p', pid], 
                                                    capture_output=True, text=True)
                        if check_result.returncode == 0:
                            subprocess.run(['kill', '-KILL', pid], timeout=5)
                    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, ValueError):
                        pass  # Process already gone or can't be killed
        
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
                            subprocess.run(['kill', '-TERM', pid], timeout=5)
                        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                            pass
        except FileNotFoundError:
            pass  # lsof not available
        
        # Clean up PID file
        if os.path.exists("sra_script.pid"):
            os.remove("sra_script.pid")
        
        return True
    except Exception as e:
        st.error(f"Error during cleanup: {e}")
        return False

def list_ollama_models():
    """Return a list of installed Ollama model names (or empty)."""
    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            lines = result.stdout.split("\n")[1:]  # skip header
            return [l.split()[0] for l in lines if l.strip() and ':' in l]
    except Exception:
        pass
    return []

def pull_ollama_model(model_name: str):
    """Pull model and return success/failure message."""
    try:
        result = subprocess.run(["ollama", "pull", model_name], capture_output=True, text=True, timeout=600)
        if result.returncode == 0:
            return f"✅ Model '{model_name}' installed successfully."
        else:
            return f"❌ Failed to install '{model_name}': {result.stderr}"
    except FileNotFoundError:
        return "❌ Ollama command not found – please install Ollama first."
    except subprocess.TimeoutExpired:
        return f"❌ Timeout installing '{model_name}' - try again later."

def run_analysis_with_streaming(cmd, output_queue):
    """Run analysis and stream output to queue"""
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # Store process in session state for cleanup
        if hasattr(st.session_state, 'current_process'):
            st.session_state.current_process = process
        
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                output_queue.put(('log', output.strip()))
        
        return_code = process.wait()
        output_queue.put(('done', return_code))
        
    except Exception as e:
        output_queue.put(('error', str(e)))

def run_visualization(input_file="result_prompt_fallback.csv"):
    """Run the visualization script and return success status."""
    try:
        result = subprocess.run([
            sys.executable, "visualize_results.py", input_file
        ], capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            return True, f"Visualizations generated successfully from {input_file}!"
        else:
            # Extract more readable error message
            error_msg = result.stderr if result.stderr else result.stdout
            if not error_msg:
                error_msg = f"Process exited with code {result.returncode}"
            
            # Try to extract the most relevant part of the error
            if "AttributeError" in error_msg and "str accessor" in error_msg:
                error_msg = "Data type error: Mixed data types in CSV. Please check your data format."
            elif "Traceback" in error_msg:
                # Extract just the last error line for cleaner display
                lines = error_msg.strip().split('\n')
                for line in reversed(lines):
                    if line.strip() and not line.startswith(' '):
                        error_msg = line.strip()
                        break
            
            # Truncate very long error messages for display
            if len(error_msg) > 500:
                error_msg = error_msg[:500] + "... (truncated)"
            
            return False, f"Visualization failed: {error_msg}"
    except subprocess.TimeoutExpired:
        return False, "Visualization generation timed out (>5 minutes)"
    except Exception as e:
        return False, f"Error generating visualizations: {str(e)}"

def load_visualization_images():
    """Load visualization images from the visualizations directory."""
    viz_dir = Path("visualizations")
    images = {}
    
    if viz_dir.exists():
        for image_file in viz_dir.glob("*.png"):
            try:
                img = Image.open(image_file)
                images[image_file.stem] = img
            except Exception as e:
                st.warning(f"Could not load {image_file.name}: {e}")
    
    return images

def check_for_live_updates(output_file):
    """Check for live updates to results file and return preview data."""
    if not os.path.exists(output_file):
        return None, 0
    
    try:
        # Get file modification time
        mod_time = os.path.getmtime(output_file)
        
        # Always reload if file exists and has content, check modification time for efficiency
        file_size = os.path.getsize(output_file)
        if file_size > 0:
            # Only reload if file was modified since last check OR this is first check
            last_mod_time = st.session_state.get('last_update_time', 0)
            if mod_time > last_mod_time or last_mod_time == 0:
                st.session_state.last_update_time = mod_time
                
                # Load data
                df = pd.read_csv(output_file)
                
                # Update session state
                st.session_state.results_data = df
                
                return df, len(df)
            elif st.session_state.results_data is not None:
                # Return cached data if no file changes
                return st.session_state.results_data, len(st.session_state.results_data)
    except Exception as e:
        st.error(f"Error loading live updates: {e}")
        
    return None, 0

def create_download_button(df, filename, key_suffix="", label="Download Results", help_text="Download current results"):
    """Create a non-disruptive download button that doesn't interfere with running analysis."""
    if df is not None and len(df) > 0:
        try:
            csv_data = df.to_csv(index=False)
            st.download_button(
                label=label,
                data=csv_data,
                file_name=filename,
                mime="text/csv",
                use_container_width=True,
                help=help_text,
                key=f"download_{key_suffix}_{len(df)}"  # Unique key prevents interference
            )
            return True
        except Exception as e:
            st.error(f"Error creating download: {e}")
            return False
    return False

# -----------------------
# Streamlit UI
# -----------------------

st.set_page_config(
    page_title="SRA Metadata Analyzer", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #1f77b4, #ff7f0e);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 2rem;
    }
    
    .log-container {
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 5px;
        padding: 1rem;
        max-height: 400px;
        overflow-y: auto;
        font-family: 'Courier New', monospace;
        font-size: 14px;
    }
    
    .success-message {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
        padding: 0.75rem;
        border-radius: 5px;
        margin: 1rem 0;
    }
    
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        text-align: center;
    }
    
    /* Make tabs larger and more prominent */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        height: 60px;
        padding: 20px 30px;
        background-color: #f0f2f6;
        border-radius: 8px;
        border: 2px solid #e6e9ef;
        font-weight: 600;
        font-size: 16px;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 10px;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: #1f77b4;
        color: white;
        border: 2px solid #1f77b4;
        box-shadow: 0 4px 8px rgba(31, 119, 180, 0.3);
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown("""
<div class="main-header">
    <h1>SRA-LLM</h1>
    <p>Automated NGS Data Fetching and AI-Powered Metadata Processing</p>
</div>
""", unsafe_allow_html=True)

# Initialize session state
if "analysis_running" not in st.session_state:
    st.session_state.analysis_running = False
if "analysis_logs" not in st.session_state:
    st.session_state.analysis_logs = []
if "output_queue" not in st.session_state:
    st.session_state.output_queue = None
if "current_process" not in st.session_state:
    st.session_state.current_process = None
if "previous_model" not in st.session_state:
    st.session_state.previous_model = None
if "analysis_completed" not in st.session_state:
    st.session_state.analysis_completed = False
if "visualization_generated" not in st.session_state:
    st.session_state.visualization_generated = False
if "results_data" not in st.session_state:
    st.session_state.results_data = None
if "last_update_time" not in st.session_state:
    st.session_state.last_update_time = 0
if "auto_refresh_enabled" not in st.session_state:
    st.session_state.auto_refresh_enabled = True
if "last_live_check" not in st.session_state:
    st.session_state.last_live_check = 0
if "last_log_refresh" not in st.session_state:
    st.session_state.last_log_refresh = 0
if "last_auto_refresh" not in st.session_state:
    st.session_state.last_auto_refresh = 0
if "last_data_explorer_check" not in st.session_state:
    st.session_state.last_data_explorer_check = 0
if "last_data_explorer_refresh" not in st.session_state:
    st.session_state.last_data_explorer_refresh = 0
if "last_viz_check" not in st.session_state:
    st.session_state.last_viz_check = 0
if "last_viz_file_time" not in st.session_state:
    st.session_state.last_viz_file_time = 0
if "live_preview_data" not in st.session_state:
    st.session_state.live_preview_data = None
if "live_preview_count" not in st.session_state:
    st.session_state.live_preview_count = 0
if "previous_sample_count" not in st.session_state:
    st.session_state.previous_sample_count = 0

# Function to check and auto-load user's specific output file
def check_and_load_user_output_file(output_filename):
    """Load user's specific output file if it exists and has content."""
    if os.path.exists(output_filename) and os.path.getsize(output_filename) > 1000:
        try:
            df = pd.read_csv(output_filename)
            st.session_state.results_data = df
            st.session_state.last_update_time = os.path.getmtime(output_filename)
            # Check if visualizations exist
            if os.path.exists("visualizations") and os.listdir("visualizations"):
                st.session_state.visualization_generated = True
            return True, len(df)
        except Exception as e:
            return False, 0
    return False, 0

# Create tabs
tab1, tab2, tab3 = st.tabs(["ANALYSIS", "VISUALIZATIONS", "DATA EXPLORER"])

# Initialize default output file in session state if not set
if "current_output_file" not in st.session_state:
    st.session_state.current_output_file = "sra_results_web.csv"

# -----------------------
# TAB 1: Analysis
# -----------------------
with tab1:
    # Show if user's specific output file was loaded
    if hasattr(st.session_state, 'loaded_file_info') and st.session_state.loaded_file_info:
        filename, sample_count = st.session_state.loaded_file_info
        st.success(f"📊 **Existing results loaded**: {sample_count:,} samples from `{filename}`. You can start a new analysis (will append/overwrite) or explore existing data in other tabs.")
    
    # Keyword input
    st.subheader("Research Keywords")
    keywords_input = st.text_area(
        "Enter keywords (one per line or comma-separated)", 
        height=100, 
        value="prostate cancer\nbreast cancer",
        help="Enter research terms you want to analyze. Examples: 'prostate cancer', 'BRCA1', 'RNA-seq'"
    )

    # Model selection with current popular models
    st.subheader("AI Model (Ollama)")
    col1, col2, col3, col4 = st.columns([3, 1, 1, 1])

    # Updated popular models for 2024/2025 - qwen3:8b as default (recommended in README)
    POPULAR_MODELS = [
        "qwen3:8b",
        "gemma3n:e2b",        # 5.6GB, 32K context, Text
        "gemma3n:e4b",        # Text processing optimized
        "gemma3:1b",          # 815MB, 32K context, Text (lightweight)
        "gemma3:4b",          # 3.3GB, 128K context, Text/Image
        "gemma3:12b",         # 8.1GB, 128K context, Text/Image
        "gemma3:27b",         # Large model, 128K context, Text/Image
        "llama3.2:3b",
        "qwen2.5:7b", 
        "phi3.5:3.8b",
        "mistral:7b",
        "gemma2:9b",
        "llama3.1:8b",
        "codellama:7b",
        "mixtral:8x7b"
    ]

    with col1:
        installed_models = list_ollama_models()
        if installed_models:
            model_options = installed_models + [m for m in POPULAR_MODELS if m not in installed_models]
            
            # Set default to qwen3:8b if available, otherwise first option
            default_index = 0
            if "qwen3:8b" in model_options:
                default_index = model_options.index("qwen3:8b")
            
            selected_model = st.selectbox("Choose model", model_options, index=default_index)
            
            # Check if model changed and cleanup if needed
            if st.session_state.previous_model != selected_model:
                if st.session_state.previous_model is not None and st.session_state.analysis_running:
                    st.warning("🔄 Model changed - stopping current analysis...")
                    cleanup_ollama_processes()
                    st.session_state.analysis_running = False
                st.session_state.previous_model = selected_model
            
            if selected_model in installed_models:
                st.success("Model installed ✓")
            else:
                st.warning("Model not installed")
        else:
            st.warning("No Ollama models found. Install models using the button below.")
            selected_model = POPULAR_MODELS[0]

    with col2:
        if st.button("Refresh Models"):
            st.rerun()

    with col3:
        install_model = st.selectbox("Install model:", [""] + POPULAR_MODELS)
        if st.button("Install") and install_model:
            with st.spinner(f"Installing {install_model}..."):
                result = pull_ollama_model(install_model)
                st.success(result)
            st.rerun()

    with col4:
        if st.button("Cleanup Ollama", help="Stop all running Ollama processes"):
            with st.spinner("Cleaning up Ollama processes..."):
                success = cleanup_ollama_processes()
                if success:
                    st.success("✅ Cleanup completed!")
                else:
                    st.error("❌ Cleanup failed")
            st.session_state.analysis_running = False
            st.rerun()

    # Output file
    st.subheader("Output Settings")
    output_csv = st.text_input("CSV output file", value="sra_results_web.csv")
    
    # Always check and load user's specific output file if it exists
    st.session_state.current_output_file = output_csv  # Always update current file
    
    # Force reload of data when file changes or on first load
    loaded, sample_count = check_and_load_user_output_file(output_csv)
    if loaded:
        st.session_state.loaded_file_info = (output_csv, sample_count)
        # Also update results_data immediately for all tabs
        if st.session_state.results_data is None or len(st.session_state.results_data) != sample_count:
            try:
                st.session_state.results_data = pd.read_csv(output_csv)
            except:
                pass
    else:
        # Clear previous file info if current file doesn't exist  
        if hasattr(st.session_state, 'loaded_file_info'):
            del st.session_state.loaded_file_info
        # Clear results data if file doesn't exist
        st.session_state.results_data = None

    # Analysis Control
    st.subheader("Analysis Control")

    if not st.session_state.analysis_running:
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Start Analysis", type="primary", use_container_width=True):
                # Validate inputs
                keywords = [k.strip() for part in keywords_input.split("\n") for k in part.split(',') if k.strip()]
                if not keywords:
                    st.error("Please enter at least one keyword.")
                elif selected_model not in list_ollama_models():
                    with st.spinner(f"Selected model '{selected_model}' not found. Pulling now…"):
                        pull_msg = pull_ollama_model(selected_model)
                        st.session_state.analysis_logs.append(pull_msg)
                    installed_models = list_ollama_models()
                    if selected_model not in installed_models:
                        st.error("Model installation failed – cannot start analysis.")
                        st.rerun()
                        st.stop()
                else:
                    # Create keywords CSV file
                    with tempfile.NamedTemporaryFile("w", delete=False, newline="", suffix=".csv") as tf:
                        writer = csv.writer(tf)
                        writer.writerow(["SearchTerm"])
                        for kw in keywords:
                            writer.writerow([kw])
                        keywords_file = tf.name
                    
                    # Build command
                    cmd = [
                        sys.executable, "SRA_fetch_1LLM_improved.py",
                        "--keywords", keywords_file,
                        "--output", output_csv,
                        "--model", selected_model
                    ]
                    
                    # Initialize streaming
                    st.session_state.analysis_running = True
                    st.session_state.analysis_completed = False
                    st.session_state.visualization_generated = False
                    st.session_state.analysis_logs = []
                    st.session_state.keywords_file = keywords_file
                    st.session_state.output_queue = queue.Queue()
                    
                    # Clear previous live preview data
                    st.session_state.live_preview_data = None
                    st.session_state.live_preview_count = 0
                    st.session_state.previous_sample_count = 0
                    
                    # Start analysis thread
                    thread = threading.Thread(
                        target=run_analysis_with_streaming, 
                        args=(cmd, st.session_state.output_queue)
                    )
                    thread.daemon = True
                    thread.start()
                    
                    st.rerun()
        
        with col2:
            if st.button("Generate Visualizations Only", use_container_width=True):
                # Always use the current user-defined output file
                current_output = st.session_state.get('current_output_file', output_csv)
                if os.path.exists(current_output):
                    with st.spinner("Generating visualizations..."):
                        success, message = run_visualization(current_output)
                        if success:
                            st.success(message)
                            st.session_state.visualization_generated = True
                            st.rerun()
                        else:
                            st.error(message)
                else:
                    st.warning(f"Results file '{current_output}' not found. Run analysis first.")

    else:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Refresh Status", use_container_width=True):
                st.rerun()
        with col2:
            if st.button("Force Stop", use_container_width=True):
                with st.spinner("Stopping analysis and cleaning up..."):
                    # Clean up Ollama processes
                    cleanup_ollama_processes()
                    
                    # Terminate current process if running
                    if st.session_state.current_process:
                        try:
                            st.session_state.current_process.terminate()
                            st.session_state.current_process.wait(timeout=5)
                        except:
                            try:
                                st.session_state.current_process.kill()
                            except:
                                pass
                        st.session_state.current_process = None
                    
                    # Clean up temp file
                    if hasattr(st.session_state, 'keywords_file'):
                        try:
                            os.unlink(st.session_state.keywords_file)
                        except:
                            pass
                    
                    st.session_state.analysis_running = False
                    st.session_state.analysis_logs.append("⏹️ Analysis stopped by user - all processes cleaned up")
                    
                    # Clear live preview data on stop
                    st.session_state.live_preview_data = None
                    st.session_state.live_preview_count = 0
                    st.session_state.previous_sample_count = 0
                    
                    st.success("✅ Analysis stopped and cleaned up!")
                st.rerun()

    # Enhanced real-time log display with progress
    if st.session_state.analysis_running and st.session_state.output_queue:
        st.subheader("Analysis Running - Live Progress")
        
        # Progress indicators  
        col1, col2 = st.columns(2)
        with col1:
            # Extract processed samples from logs - look for SRA script specific patterns
            processed_samples = 0
            total_samples_found = 0
            for log in st.session_state.analysis_logs:
                # Look for the exact SRA script pattern: "INFO: Processed X new samples"
                if "INFO: Processed" in log and "new samples" in log:
                    try:
                        import re
                        numbers = re.findall(r'INFO: Processed (\d+) new samples', log)
                        if numbers:
                            processed_samples = int(numbers[0])  # Use latest count, not sum
                    except:
                        pass
                # Also look for incremental merge patterns
                elif "Incrementally merged" in log and "new samples" in log:
                    try:
                        import re
                        numbers = re.findall(r'merged (\d+) new samples', log)
                        if numbers:
                            total_samples_found += int(numbers[0])
                    except:
                        pass
            
            # Show the latest processed count or total found samples
            display_count = max(processed_samples, total_samples_found)
            st.metric("Samples Processed", display_count)
        with col2:
            # Show current status
            if st.session_state.analysis_logs:
                last_log = st.session_state.analysis_logs[-1]
                if "ERROR" in last_log or "❌" in last_log:
                    st.metric("Status", "Error")
                elif "INFO" in last_log or "✅" in last_log:
                    st.metric("Status", "Running")
                else:
                    st.metric("Status", "Processing")
        
        # Progress bar (estimate based on log activity)
        if len(st.session_state.analysis_logs) > 0:
            # Simple progress estimation based on log frequency
            progress = min(len(st.session_state.analysis_logs) / 100, 0.99)  # Cap at 99%
            st.progress(progress, text=f"Analysis Progress: {progress*100:.1f}%")
        
        # Process queue messages
        logs_updated = False
        try:
            while True:
                try:
                    msg_type, content = st.session_state.output_queue.get_nowait()
                    logs_updated = True
                    
                    if msg_type == 'log':
                        st.session_state.analysis_logs.append(content)
                    elif msg_type == 'done':
                        st.session_state.analysis_running = False
                        st.session_state.analysis_completed = True
                        if content == 0:
                            st.session_state.analysis_logs.append("✅ Analysis completed successfully!")
                            # Automatically generate visualizations using user-defined file
                            st.session_state.analysis_logs.append("🎨 Auto-generating visualizations...")
                            try:
                                # Use the user-defined output file from session state
                                user_output_file = st.session_state.get('current_output_file', output_csv)
                                success, viz_message = run_visualization(user_output_file)
                                st.session_state.analysis_logs.append(f"📊 {viz_message}")
                                if success:
                                    st.session_state.visualization_generated = True
                                    st.session_state.analysis_logs.append("✅ Visualizations generated successfully!")
                                # Load results data for data explorer
                                try:
                                    if os.path.exists(user_output_file):
                                        st.session_state.results_data = pd.read_csv(user_output_file)
                                        st.session_state.analysis_logs.append("📊 Results data loaded for explorer")
                                    else:
                                        st.session_state.analysis_logs.append(f"⚠️ Output file {user_output_file} not found")
                                except Exception as e:
                                    st.session_state.analysis_logs.append(f"⚠️ Could not load results data: {e}")
                            except Exception as e:
                                st.session_state.analysis_logs.append(f"❌ Visualization generation failed: {e}")
                        else:
                            st.session_state.analysis_logs.append(f"❌ Analysis failed with exit code {content}")
                        
                        # Clean up processes and temp files
                        cleanup_ollama_processes()
                        st.session_state.current_process = None
                        try:
                            os.unlink(st.session_state.keywords_file)
                        except:
                            pass
                        st.session_state.analysis_logs.append("🧹 Cleanup completed")
                        break
                    elif msg_type == 'error':
                        st.session_state.analysis_running = False
                        st.session_state.analysis_logs.append(f"❌ Error: {content}")
                        
                        # Clean up processes and temp files on error
                        cleanup_ollama_processes()
                        st.session_state.current_process = None
                        try:
                            os.unlink(st.session_state.keywords_file)
                        except:
                            pass
                        st.session_state.analysis_logs.append("🧹 Cleanup completed after error")
                        break
                        
                except queue.Empty:
                    break
        except:
            pass
        
        # Enhanced log display with auto-scroll
        if st.session_state.analysis_logs:
            # Create a container for logs with custom styling
            log_container = st.container()
            with log_container:
                # Show last 50 lines for performance
                recent_logs = st.session_state.analysis_logs[-50:]
                log_text = "\n".join(recent_logs)
                
                # Use code block with syntax highlighting
                st.code(log_text, language=None)
                
                # Show log statistics
                st.caption(f"Showing last 50 of {len(st.session_state.analysis_logs)} log entries")
        
        # Auto-refresh every 5 seconds if still running (removed blocking sleep)
        if st.session_state.analysis_running:
            current_refresh_time = time.time()
            if current_refresh_time - st.session_state.get('last_log_refresh', 0) > 5:
                st.session_state.last_log_refresh = current_refresh_time
                st.rerun()

    # Live Results Preview (always show when running or when results exist)
    current_time = time.time()
    user_output_file = st.session_state.get('current_output_file', output_csv)
    
    # Check if we should update the data (performance optimization)
    should_update_data = False
    if st.session_state.analysis_running:
        # During analysis, update data every 5 seconds (faster updates)
        if current_time - st.session_state.get('last_live_check', 0) > 5:
            should_update_data = True
            st.session_state.last_live_check = current_time
    elif os.path.exists(user_output_file):
        # If not running but file exists, update once
        should_update_data = True
    
    # Update data if needed
    if should_update_data:
        live_data, sample_count = check_for_live_updates(user_output_file)
        if live_data is not None and sample_count > 0:
            # Store the latest data in session state for persistent display
            st.session_state.live_preview_data = live_data
            st.session_state.live_preview_count = sample_count
    
    # Always show Live Results Preview if we have data OR analysis is running
    show_live_preview = False
    display_data = None
    display_count = 0
    
    if st.session_state.analysis_running:
        # Always show during analysis, even if no data yet
        show_live_preview = True
        display_data = st.session_state.get('live_preview_data', None)
        display_count = st.session_state.get('live_preview_count', 0)
    elif st.session_state.get('live_preview_data') is not None:
        # Show if we have data and analysis is not running
        show_live_preview = True 
        display_data = st.session_state.live_preview_data
        display_count = st.session_state.live_preview_count
    
    if show_live_preview:
        st.subheader("Live Results Preview")
        
        if display_data is not None and display_count > 0:
            # Show real-time statistics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                previous_count = st.session_state.get('previous_sample_count', 0)
                delta_value = display_count - previous_count if previous_count > 0 else None
                delta_str = f"+{delta_value}" if delta_value and delta_value > 0 else None
                st.metric("Samples Found", display_count, delta=delta_str)
                st.session_state.previous_sample_count = display_count
            with col2:
                species_count = display_data['species'].nunique() if 'species' in display_data.columns else 0
                st.metric("Species", species_count)
            with col3:
                technique_count = display_data['sequencing_technique'].nunique() if 'sequencing_technique' in display_data.columns else 0
                st.metric("Techniques", technique_count)
            with col4:
                cell_line_count = len(display_data[display_data['cell_line_name'] != 'N/A']) if 'cell_line_name' in display_data.columns else 0
                st.metric("Cell Lines", cell_line_count)
            
            # Show last modified time
            if os.path.exists(user_output_file):
                mod_time = datetime.datetime.fromtimestamp(os.path.getmtime(user_output_file))
                st.caption(f"📅 Last updated: {mod_time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Live data preview - expanded by default during analysis
            expanded_state = st.session_state.analysis_running
            with st.expander("📋 Latest Samples Preview", expanded=expanded_state):
                st.dataframe(display_data.tail(10), use_container_width=True)  # Show last 10 samples
            
            # Non-disruptive download button
            col1, col2 = st.columns(2)
            with col1:
                create_download_button(
                    display_data, 
                    f"live_results_{display_count}_samples.csv",
                    "live_analysis",
                    "📥 Download Current Results",
                    f"Download {display_count} samples found so far"
                )
            with col2:
                if st.session_state.analysis_running:
                    st.info("🔄 Analysis running - results update every 5 seconds")
                else:
                    st.success("✅ Analysis completed")
        else:
            # Show placeholder when no data yet but analysis is running
            if st.session_state.analysis_running:
                st.info("Analysis starting... waiting for first results to appear.")
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Samples Found", "0", help="Samples will appear here as they are processed")
                with col2:
                    st.metric("Species", "0")
                with col3:
                    st.metric("Techniques", "0") 
                with col4:
                    st.metric("Cell Lines", "0")
                st.caption("Waiting for first samples...")
            else:
                st.info("No results data available. Run an analysis to see live preview here.")

    # Show results if analysis completed
    if st.session_state.analysis_completed and not st.session_state.analysis_running:
        if any("✅ Analysis completed successfully!" in log for log in st.session_state.analysis_logs):
            st.markdown('<div class="success-message">🎉 Analysis completed successfully!</div>', unsafe_allow_html=True)

    # Auto-refresh during analysis (every 5 seconds for live updates)
    if st.session_state.analysis_running and st.session_state.auto_refresh_enabled:
        if current_time - st.session_state.get('last_auto_refresh', 0) > 5:
            st.session_state.last_auto_refresh = current_time
            st.rerun()

    # Help section
    with st.expander("ℹ️ Help & Instructions"):
        st.markdown("""
        ### How to Use:
        
        1. **Install AI Models**: First click "🔄 Refresh Models" to see installed models, or use the dropdown to install popular models
        
        2. **Enter Keywords**: Add your research keywords in the text area (one per line or comma-separated)
        
        3. **Choose Output**: Specify where to save results (default: sra_results_web.csv)
        
        4. **Start Analysis**: Click "🚀 Start Analysis" to begin processing
        
        ### Popular Models (Updated 2024/2025):
        - **gemma3n:e2b**: Latest Gemma 3 model, 5.6GB, 32K context (recommended for scientific analysis)
        - **gemma3n:e4b**: Latest Gemma 3 model variant, optimized for text processing
        - **llama3.2:3b**: Latest Llama model, fast and efficient
        - **qwen2.5:7b**: Excellent for scientific text analysis
        - **phi3.5:3.8b**: Microsoft's latest efficient model
        - **mistral:7b**: High quality general model
        - **gemma2:9b**: Google's previous generation model
        - **llama3.1:8b**: Powerful for complex tasks
        - **codellama:7b**: Specialized for code analysis
        - **mixtral:8x7b**: High-performance mixture model
        
        ### Tips:
        - Start with just 1-2 keywords to test the system
        - Analysis can take several hours for large keyword sets
        - Results include detailed metadata extracted by AI
        - Live logs show real-time progress
        
        ### Process Management:
        - **🧹 Cleanup Ollama**: Stops all running Ollama processes (recommended before switching models)
        - **⏹️ Force Stop**: Stops current analysis and cleans up all processes
        - **Model switching**: Automatically cleans up when you change models during analysis
        - **Manual cleanup**: Run `python3 cleanup_ollama_advanced.py` from terminal if needed
        """)

    # Status info
    st.sidebar.subheader("System Status")
    if installed_models:
        st.sidebar.success(f"✅ {len(installed_models)} Ollama models available")
        with st.sidebar.expander("📋 Installed Models"):
            for model in installed_models:
                st.sidebar.text(f"• {model}")
    else:
        st.sidebar.error("❌ No Ollama models found")

    if os.path.exists("SRA_fetch_1LLM_improved.py"):
        st.sidebar.success("✅ Main analysis script found")
    else:
        st.sidebar.error("❌ Main analysis script missing")

    # Analysis status in sidebar
    if st.session_state.analysis_running:
        st.sidebar.warning("🔴 Analysis Running")
        st.sidebar.metric("Log entries", len(st.session_state.analysis_logs))
    else:
        st.sidebar.success("✅ Ready for analysis")

# -----------------------
# TAB 2: Visualizations
# -----------------------
with tab2:
    st.header("Analysis Visualizations")
    
    # Show current file being used
    current_file = st.session_state.get('current_output_file', 'sra_results_web.csv')
    if os.path.exists(current_file):
        file_size = os.path.getsize(current_file)
        if file_size > 1000:
            with open(current_file, 'r') as f:
                line_count = sum(1 for line in f) - 1  # Subtract header
            st.info(f"📁 **Using data from**: `{current_file}` ({line_count:,} samples, {file_size:,} bytes)")
        else:
            st.warning(f"📁 **Current file**: `{current_file}` (exists but appears empty)")
    else:
        st.warning(f"📁 **Current file**: `{current_file}` (does not exist yet)")
    
    # Auto-update visualizations every minute if analysis is running
    current_time = time.time()
    should_update_viz = False
    
    # Check if we should regenerate visualizations based on updated data
    if st.session_state.analysis_running and st.session_state.results_data is not None:
        if (current_time - st.session_state.get('last_viz_check', 0) > 30):  # Every 30 seconds
            st.session_state.last_viz_check = current_time
            # Use the user-defined output file for visualizations
            if os.path.exists(st.session_state.get('current_output_file', 'sra_results_web.csv')):
                result_file = st.session_state.current_output_file
                # Check if file was modified since last viz update
                file_mod_time = os.path.getmtime(result_file)
                if file_mod_time > st.session_state.get('last_viz_file_time', 0):
                    st.session_state.last_viz_file_time = file_mod_time
                    # Regenerate visualizations silently in background
                    with st.spinner("🔄 Updating visualizations with latest data..."):
                        success, message = run_visualization(result_file)
                        if success:
                            st.session_state.visualization_generated = True
                            should_update_viz = True
                            st.info("✅ Visualizations updated with latest samples")
    
    if st.session_state.visualization_generated or os.path.exists("visualizations"):
        # Load and display visualization images
        viz_images = load_visualization_images()
        
        if viz_images:
            # Show last update time
            viz_dir = Path("visualizations")
            if viz_dir.exists():
                newest_viz = max(viz_dir.glob("*.png"), key=lambda f: f.stat().st_mtime, default=None)
                if newest_viz:
                    mod_time = datetime.datetime.fromtimestamp(newest_viz.stat().st_mtime)
                    st.caption(f"📅 Visualizations last updated: {mod_time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            st.success(f"Found {len(viz_images)} visualizations")
            
            # Real-time refresh controls
            col1, col2 = st.columns([3, 1])
            with col1:
                if st.session_state.analysis_running:
                    st.info("🔄 Visualizations auto-update every minute during analysis")
            with col2:
                if st.button("🔄 Refresh Visualizations", key="refresh_viz"):
                    # Use the user-defined output file for manual refresh
                    user_output_file = st.session_state.get('current_output_file', 'sra_results_web.csv')
                    if os.path.exists(user_output_file):
                        with st.spinner("Regenerating visualizations..."):
                            success, message = run_visualization(user_output_file)
                            if success:
                                st.success("✅ Visualizations refreshed!")
                                st.rerun()
                            else:
                                st.error(f"❌ {message}")
                    else:
                        st.error(f"❌ Output file '{user_output_file}' not found. Run analysis first.")
            
            # Create columns for layout
            viz_categories = {
                "Species & Techniques": ["species_pie_chart", "sequencing_technique_pie_chart"],
                "Sample Types": ["sample_type_pie_chart", "cell_line_name_pie_chart", "tissue_type_pie_chart"],
                "Disease & Treatment": ["disease_description_pie_chart", "treatment_wordcloud"],
                "ChIP-seq Analysis": ["is_chipseq_related_experiment_pie_chart", "chipseq_antibody_target_pie_chart"]
            }
            
            for category, chart_names in viz_categories.items():
                st.subheader(f"📈 {category}")
                
                # Create columns for side-by-side display
                if len(chart_names) == 2:
                    col1, col2 = st.columns(2)
                    columns = [col1, col2]
                else:
                    # Create a single column container for consistency
                    col1 = st.container()
                    columns = [col1]
                
                for i, chart_name in enumerate(chart_names):
                    if chart_name in viz_images:
                        with columns[i % len(columns)]:
                            st.image(viz_images[chart_name], caption=chart_name.replace('_', ' ').title(), use_container_width=True)
                
                st.divider()
            
            # Summary statistics
            if os.path.exists("visualizations/summary_statistics.txt"):
                st.subheader("📋 Summary Statistics")
                with open("visualizations/summary_statistics.txt", 'r') as f:
                    stats_content = f.read()
                st.text(stats_content)
        else:
            st.info("No visualization images found. Generate visualizations first.")
            
            if st.button("🎨 Generate Visualizations Now"):
                with st.spinner("Generating visualizations..."):
                    # Use the user-defined output file
                    user_output_file = st.session_state.get('current_output_file', 'sra_results_web.csv')
                    if os.path.exists(user_output_file):
                        success, message = run_visualization(user_output_file)
                        if success:
                            st.success(message)
                            st.session_state.visualization_generated = True
                            st.rerun()
                        else:
                            st.error(message)
                    else:
                        st.error(f"❌ Output file '{user_output_file}' not found. Run analysis first.")
    else:
        st.info("📊 Visualizations will appear here after analysis completes.")
        st.markdown("""
        **Available visualizations include:**
        - 🥧 Pie charts for species, sequencing techniques, sample types
        - 📊 Cell line and tissue type distributions  
        - 🔬 Disease and treatment analysis
        - ☁️ Treatment word clouds
        - 🧬 ChIP-seq specific analysis
        """)
    
    # Auto-refresh for visualizations during analysis
    if st.session_state.analysis_running and should_update_viz:
        st.rerun()

# -----------------------
# TAB 3: Data Explorer
# -----------------------
with tab3:
    st.header("Interactive Data Explorer")
    
    # Show current file being used
    current_file = st.session_state.get('current_output_file', 'sra_results_web.csv')
    if os.path.exists(current_file):
        file_size = os.path.getsize(current_file)
        if file_size > 1000:
            with open(current_file, 'r') as f:
                line_count = sum(1 for line in f) - 1  # Subtract header
            st.info(f"📁 **Using data from**: `{current_file}` ({line_count:,} samples, {file_size:,} bytes)")
        else:
            st.warning(f"📁 **Current file**: `{current_file}` (exists but appears empty)")
    else:
        st.warning(f"📁 **Current file**: `{current_file}` (does not exist yet)")
    
    # Auto-refresh data explorer every 15 seconds during analysis
    current_time = time.time()
    
    # Check for live data updates using user-defined file
    if st.session_state.analysis_running and (current_time - st.session_state.get('last_data_explorer_check', 0) > 15):
        st.session_state.last_data_explorer_check = current_time
        # Use the user-defined output file
        user_output_file = st.session_state.get('current_output_file', 'sra_results_web.csv')
        if os.path.exists(user_output_file):
            try:
                updated_data = pd.read_csv(user_output_file)
                if st.session_state.results_data is None or len(updated_data) > len(st.session_state.results_data):
                    st.session_state.results_data = updated_data
                    st.success(f"🔄 Data explorer updated! Now showing {len(updated_data)} samples.")
            except Exception as e:
                st.warning(f"Could not update data: {e}")
    
    # Allow loading existing CSV files for testing
    if st.session_state.results_data is None:
        st.info("💡 **Load Existing Results**: You can load a previously generated CSV file to explore the data.")
        
        # File upload option
        uploaded_file = st.file_uploader("Upload a CSV file:", type=['csv'], key="data_explorer_upload")
        if uploaded_file is not None:
            try:
                st.session_state.results_data = pd.read_csv(uploaded_file)
                st.success(f"✅ Loaded {len(st.session_state.results_data)} rows from uploaded file!")
                st.rerun()
            except Exception as e:
                st.error(f"Error loading file: {e}")
        
        # Check for user-defined output file
        user_output_file = st.session_state.get('current_output_file', 'sra_results_web.csv')
        if os.path.exists(user_output_file) and os.path.getsize(user_output_file) > 1000:
            st.markdown(f"**Or load your current output file: `{user_output_file}`**")
            if st.button("📂 Load Current Output File", key="load_current_output"):
                try:
                    st.session_state.results_data = pd.read_csv(user_output_file)
                    st.success(f"✅ Loaded {len(st.session_state.results_data)} rows from {user_output_file}!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error loading {user_output_file}: {e}")
        else:
            st.info(f"💡 Your current output file `{user_output_file}` doesn't exist yet. Run an analysis first or upload a file.")

    if st.session_state.results_data is not None:
        df = st.session_state.results_data
        
        st.success(f"📊 Loaded {len(df)} samples with {len(df.columns)} columns")
        
        # Column selection and filtering interface
        st.subheader("🎛️ Data Filtering Controls")
        
        # Create filtering interface
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.markdown("**Select columns to filter:**")
            # Get all columns except IDs
            filterable_columns = [col for col in df.columns if col not in ['sra_experiment_id', 'gse_accession', 'gsm_accession']]
            
            # Ensure we have columns to work with
            if filterable_columns:
                selected_columns = st.multiselect(
                    "Choose columns for filtering:",
                    filterable_columns,
                    default=filterable_columns[:min(3, len(filterable_columns))]  # Default to first 3 columns or less
                )
            else:
                selected_columns = []
                st.warning("No filterable columns found in the data.")
        
        with col2:
            st.markdown("**Apply filters:**")
            
            # Create filters for selected columns
            filters = {}
            filtered_df = df.copy()
            
            for col in selected_columns:
                if col in df.columns:
                    # Get unique values for this column (excluding N/A and null values)
                    unique_values = df[col].dropna().unique()
                    unique_values = [val for val in unique_values if str(val) not in ['N/A', 'nan', 'None', '']]
                    unique_values = sorted([str(val) for val in unique_values])  # Sort for better UX
                    
                    if len(unique_values) > 0:
                        # Limit options if too many (for performance)
                        if len(unique_values) > 50:
                            st.info(f"Column '{col}' has {len(unique_values)} unique values. Showing top 50.")
                            unique_values = unique_values[:50]
                        
                        # Create multiselect for this column
                        selected_values = st.multiselect(
                            f"Filter by {col}:",
                            unique_values,
                            key=f"filter_{col}",
                            help=f"Select values to filter by. Column has {len(unique_values)} unique values."
                        )
                        
                        if selected_values:
                            filters[col] = selected_values
                            # Apply filter - convert back to original data types for comparison
                            try:
                                # Handle both string and non-string comparisons
                                mask = df[col].astype(str).isin(selected_values)
                                filtered_df = filtered_df[mask]
                            except Exception as e:
                                st.error(f"Error filtering column {col}: {e}")
                    else:
                        st.info(f"Column '{col}' has no valid values to filter by.")
        
        # Display filtering results
        st.subheader("📈 Filtering Results")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Original Samples", len(df))
        with col2:
            st.metric("Filtered Samples", len(filtered_df))
        with col3:
            reduction = (1 - len(filtered_df)/len(df)) * 100 if len(df) > 0 else 0
            st.metric("Reduction", f"{reduction:.1f}%")
        
        # Show active filters
        if filters:
            st.subheader("🎯 Active Filters")
            for col, values in filters.items():
                st.write(f"**{col}**: {', '.join(map(str, values))}")
        
        # Display filtered data
        st.subheader("📊 Filtered Data")
        st.dataframe(filtered_df, use_container_width=True)
        
        # Enhanced download options for filtered data
        if len(filtered_df) > 0:
            st.subheader("📁 Download & Processing Options")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**📥 Download Selected Samples**")
                
                # Create download button with enhanced filename
                csv_data = filtered_df.to_csv(index=False)
                download_filename = f"filtered_{len(filtered_df)}_samples_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.csv"
                
                create_download_button(
                    filtered_df,
                    download_filename,
                    "filtered_data",
                    "📥 Download Filtered Samples",
                    f"Download {len(filtered_df)} selected samples with all metadata"
                )
                
                # Additional download formats
                with st.expander("📄 Alternative Download Formats"):
                    # Sample IDs only
                    if 'sra_experiment_id' in filtered_df.columns:
                        sample_ids = filtered_df['sra_experiment_id'].tolist()
                        ids_text = '\n'.join(sample_ids)
                        st.download_button(
                            label="📄 Download Sample IDs Only",
                            data=ids_text,
                            file_name=f"sample_ids_{len(filtered_df)}.txt",
                            mime="text/plain",
                            help="Download just the SRA experiment IDs for external processing"
                        )
                    
                    # TSV format
                    tsv_data = filtered_df.to_csv(sep='\t', index=False)
                    st.download_button(
                        label="📊 Download as TSV",
                        data=tsv_data,
                        file_name=download_filename.replace('.csv', '.tsv'),
                        mime="text/tab-separated-values",
                        help="Tab-separated values format for R/Python analysis"
                    )
            
            with col2:
                st.markdown("**🧬 Next Steps: HPC Processing**")
                
                st.info("""
                **Ready for nf-core Pipeline Processing!**
                
                🎯 **Yale HPC McCleary Compatible**
                - Your filtered samples are ready for nf-core pipeline processing
                - Optimized for Yale's McCleary HPC cluster
                - Automatic SLURM job submission support
                
                🚀 **Available Pipelines:**
                - `nf-core/rnaseq` - RNA sequencing analysis
                - `nf-core/chipseq` - ChIP-seq peak calling
                - `nf-core/atacseq` - ATAC-seq accessibility
                - `nf-core/methylseq` - Bisulfite sequencing
                - `nf-core/sarek` - Variant calling pipeline
                
                ☁️ **Cloud Processing:** 
                Advanced cloud-based analysis pipeline integration coming soon!
                """)
                
                # Sample count recommendations
                if len(filtered_df) > 100:
                    st.warning(f"⚡ Large dataset detected ({len(filtered_df)} samples). Consider batch processing for optimal HPC performance.")
                elif len(filtered_df) > 10:
                    st.success(f"✅ Good sample size ({len(filtered_df)} samples) for comprehensive analysis.")
                else:
                    st.info(f"📊 Small dataset ({len(filtered_df)} samples) - perfect for quick analysis and testing.")
                
                # Technical specifications
                with st.expander("🔧 Technical Specifications"):
                    st.markdown("""
                    **HPC Cluster Details:**
                    - **System**: Yale McCleary HPC
                    - **Scheduler**: SLURM workload manager
                    - **Storage**: High-performance parallel filesystem
                    - **Compute**: CPU and GPU nodes available
                    
                    **Pipeline Integration:**
                    - Automatic sample metadata preservation
                    - FASTQ file path resolution
                    - Quality control metrics inclusion
                    - Results aggregation and reporting
                    """)
        
        # Live update notification for data explorer
        if st.session_state.analysis_running:
            st.info("🔄 Data explorer will auto-refresh with new samples every minute during analysis")
        
        # Interactive visualizations for filtered data
        if len(filtered_df) > 0:
            st.subheader("📈 Interactive Charts for Filtered Data")
            
            # Chart type selection
            if filterable_columns:
                chart_col = st.selectbox("Select column for chart:", filterable_columns, key="chart_column_select")
                chart_type = st.selectbox("Chart type:", ["Bar Chart", "Pie Chart", "Histogram"], key="chart_type_select")
                
                if chart_col and chart_col in filtered_df.columns:
                    try:
                        # Prepare data for visualization
                        non_null_data = filtered_df[chart_col].dropna()
                        
                        if len(non_null_data) == 0:
                            st.warning(f"No data available for column '{chart_col}' after filtering.")
                        else:
                            value_counts = non_null_data.value_counts().head(15)  # Top 15 values
                            
                            if chart_type == "Bar Chart":
                                fig = px.bar(
                                    x=value_counts.index, 
                                    y=value_counts.values,
                                    title=f"{chart_col} Distribution (Filtered Data - {len(filtered_df)} samples)",
                                    labels={'x': chart_col, 'y': 'Count'}
                                )
                                fig.update_xaxis(tickangle=45)
                                fig.update_layout(showlegend=False)
                                st.plotly_chart(fig, use_container_width=True)
                            
                            elif chart_type == "Pie Chart":
                                fig = px.pie(
                                    values=value_counts.values, 
                                    names=value_counts.index,
                                    title=f"{chart_col} Distribution (Filtered Data - {len(filtered_df)} samples)"
                                )
                                st.plotly_chart(fig, use_container_width=True)
                            
                            elif chart_type == "Histogram":
                                # Check if column is numeric
                                try:
                                    numeric_data = pd.to_numeric(non_null_data, errors='coerce').dropna()
                                    if len(numeric_data) > 0:
                                        fig = px.histogram(
                                            x=numeric_data,
                                            title=f"{chart_col} Distribution (Filtered Data - {len(filtered_df)} samples)",
                                            labels={'x': chart_col}
                                        )
                                        fig.update_layout(showlegend=False)
                                        st.plotly_chart(fig, use_container_width=True)
                                    else:
                                        st.info(f"Column '{chart_col}' contains no numeric data suitable for histogram.")
                                except Exception as e:
                                    st.info(f"Histogram not available for column '{chart_col}': {str(e)}")
                    
                    except Exception as e:
                        st.error(f"Error creating chart for column '{chart_col}': {str(e)}")
            else:
                st.info("No columns available for charting.")
        
    else:
        st.info("🔍 Data explorer will be available after running an analysis.")
        st.markdown("""
        **Features available after analysis:**
        - 🎛️ **Multi-column filtering** - Select any combination of columns
        - 🔄 **Dynamic updates** - Filters update automatically as you make selections
        - 📊 **Interactive charts** - Generate charts from filtered data
        - 📥 **Export filtered data** - Download your filtered dataset
        - 📈 **Real-time statistics** - See how filters affect your data
        """)
    
    # Auto-refresh data explorer during analysis (every 15 seconds)
    if st.session_state.analysis_running and st.session_state.auto_refresh_enabled:
        if current_time - st.session_state.get('last_data_explorer_refresh', 0) > 15:
            st.session_state.last_data_explorer_refresh = current_time
            st.rerun()

# -----------------------
# Sidebar Status
# -----------------------
st.sidebar.header("🖥️ System Status")

# System status
if list_ollama_models():
    st.sidebar.success(f"✅ {len(list_ollama_models())} Ollama models available")
    with st.sidebar.expander("📋 Installed Models"):
        for model in list_ollama_models():
            st.sidebar.text(f"• {model}")
else:
    st.sidebar.error("❌ No Ollama models found")

if os.path.exists("SRA_fetch_1LLM_improved.py"):
    st.sidebar.success("✅ Main analysis script found")
else:
    st.sidebar.error("❌ Main analysis script missing")

# Analysis status
if st.session_state.analysis_running:
    st.sidebar.warning("🔴 Analysis Running")
    st.sidebar.metric("Log entries", len(st.session_state.analysis_logs))
elif st.session_state.analysis_completed:
    st.sidebar.success("✅ Analysis completed")
    if st.session_state.visualization_generated:
        st.sidebar.success("📊 Visualizations ready")
else:
    st.sidebar.info("⭐ Ready for analysis")

# Quick actions
st.sidebar.header("⚡ Quick Actions")
if st.sidebar.button("🔄 Refresh Page"):
    st.rerun()

if st.sidebar.button("🧹 Clean System"):
    cleanup_ollama_processes()
    st.sidebar.success("System cleaned!")

# Help section
with st.sidebar.expander("ℹ️ Help & Tips"):
    st.markdown("""
    **Analysis Tab:**
    - Enter keywords and select AI model
    - Live progress tracking with metrics
    - Auto-generates visualizations
    
    **Visualizations Tab:**
    - View all generated charts
    - Organized by categories
    - Summary statistics included
    
    **Data Explorer Tab:**
    - Interactive filtering
    - Multiple column selection
    - Real-time chart generation
    - Export filtered data
    """) 