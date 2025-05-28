#!/usr/bin/env python3

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from typing import Dict, Any, List, Optional
import tempfile
import re
import concurrent.futures
import random
import threading

import pandas as pd
try:
    import GEOparse
except ImportError:
    print("ERROR: GEOparse library not found. Please install it: pip install GEOparse", file=sys.stderr)
    sys.exit(1)

from langchain_ollama.chat_models import ChatOllama
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from tqdm import tqdm

# --- Animation and Visual Enhancement Functions ---
def print_banner():
    """Print a colorful banner for the script."""
    banner = """
🧬 ═══════════════════════════════════════════════════════════════ 🧬
║                                                                 ║
║     🔬 SRA/GEO Metadata Extraction & Analysis Pipeline 🔬      ║
║                                                                 ║
║  🤖 AI-Powered • 🧮 Parallel Processing • 📊 Rich Metadata     ║
║                                                                 ║
🧬 ═══════════════════════════════════════════════════════════════ 🧬
    """
    print(banner)

def animated_loading(message: str, duration: float = 2.0):
    """Display an animated loading message."""
    frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    end_time = time.time() + duration
    while time.time() < end_time:
        for frame in frames:
            print(f"\r{frame} {message}", end="", flush=True)
            time.sleep(0.1)
            if time.time() >= end_time:
                break
    print(f"\r✅ {message}")

def print_section_header(title: str, emoji: str = "🔍"):
    """Print a formatted section header."""
    print(f"\n{emoji} ━━━ {title} ━━━")

def print_success(message: str):
    """Print a success message with emoji."""
    print(f"✅ {message}")

def print_info(message: str):
    """Print an info message with emoji."""
    print(f"ℹ️  {message}")

def print_warning(message: str):
    """Print a warning message with emoji."""
    print(f"⚠️  {message}")

def print_error(message: str):
    """Print an error message with emoji."""
    print(f"❌ {message}")

def animate_progress_bar(total_items: int, current: int, item_name: str):
    """Create an animated progress indicator."""
    progress = current / total_items
    bar_length = 30
    filled_length = int(bar_length * progress)
    bar = '█' * filled_length + '░' * (bar_length - filled_length)
    percentage = progress * 100
    
    emojis = ["🧬", "🔬", "📊", "🤖", "🧮"]
    emoji = random.choice(emojis)
    
    print(f"\r{emoji} [{bar}] {percentage:.1f}% | {current}/{total_items} {item_name}", end="", flush=True)

# --- Configuration ---
OLLAMA_MODEL_NAME_DEFAULT = "gemma3:12b-it-qat"
OLLAMA_BASE_URL_DEFAULT = "http://localhost:11434"
RETRY_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 5

# Reduced parallel settings to prevent Ollama overload
BATCH_SIZE_LLM = 3  # Reduced from 5 to 3 (even more conservative)
MAX_PARALLEL_LLM_WORKERS = 1  # Reduced from 2 to 1 (force sequential by default)

# LLM stability settings
LLM_REQUEST_DELAY_SECONDS = 2  # Increased from 1 to 2 seconds
LLM_CONNECTION_TIMEOUT = 180   # Increased timeout
LLM_RETRY_DELAY_MULTIPLIER = 3  # Longer waits for crashes

ENTREZ_LONG_TIMEOUT_SECONDS = 3600
ENTREZ_SHORT_TIMEOUT_SECONDS = 300

# --- Column Definitions ---
# These are the columns for the final CSV output.
INITIAL_OUTPUT_COLUMNS = [
    "original_keyword", "sra_experiment_id", "gse_accession", "gsm_accession",
    "experiment_title", "species", "sequencing_technique", "sample_type",
    "cell_line_name", "tissue_type", "tissue_source_details",
    "disease_description",
    "sample_treatment_protocol", "treatment", "clinical_sample_identifier",
    "library_source", "instrument_model",
    "is_chipseq_related_experiment", "chipseq_antibody_target",
    "chipseq_control_description",
    "chipseq_igg_control_present", "chipseq_input_control_present",
    "chipseq_nfcore_summary_lines",
    "scientific_sample_summary"
]
FINAL_OUTPUT_COLUMNS = INITIAL_OUTPUT_COLUMNS


class KeywordProvider:
    """Reads keywords from a CSV file."""
    def __init__(self, csv_path: str, column_name: Optional[str] = None):
        self.csv_path = csv_path
        self.column_name = column_name
        print(f"DEBUG: KeywordProvider initialized with csv_path='{csv_path}', column_name='{column_name}'")

    def get_keywords(self) -> List[str]:
        """
        Loads keywords from the specified CSV file.
        If column_name is provided, it uses that column. Otherwise, it uses the first column.
        Returns a list of unique, stripped keywords.
        """
        print(f"DEBUG: KeywordProvider.get_keywords called for '{self.csv_path}'")
        try:
            if self.column_name:
                df = pd.read_csv(self.csv_path, usecols=[self.column_name], dtype=str)
                keywords = df[self.column_name].dropna().unique().tolist()
            else:
                try:
                    df = pd.read_csv(self.csv_path, usecols=[0], header=0, dtype=str) # Assumes header
                except (ValueError, pd.errors.ParserError): # If header is not first row or parsing error
                    df = pd.read_csv(self.csv_path, usecols=[0], header=None, dtype=str) # Assumes no header
                keywords = df.iloc[:, 0].dropna().unique().tolist()
            keywords = [str(k).strip() for k in keywords if str(k).strip()]
            print(f"INFO: Loaded {len(keywords)} unique keywords from '{self.csv_path}'. First 5: {keywords[:5]}", file=sys.stderr)
            if not keywords:
                print("WARNING: No keywords loaded. The CSV might be empty or the specified column might be empty/missing.", file=sys.stderr)
            return keywords
        except FileNotFoundError:
            print(f"ERROR: Input keyword CSV file not found: '{self.csv_path}'", file=sys.stderr)
            sys.exit(1)
        except ValueError as ve: # Handles issues like column not found in usecols
            print(f"ERROR: Value error processing keywords from '{self.csv_path}'. Is column '{self.column_name}' correct? Details: {ve}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"ERROR: An unexpected error occurred while processing keywords from '{self.csv_path}': {e}", file=sys.stderr)
            sys.exit(1)


class EntrezClient:
    """Client for interacting with NCBI Entrez E-utils via command-line tools."""
    def __init__(self, retry_attempts: int = RETRY_ATTEMPTS, retry_delay: int = RETRY_DELAY_SECONDS):
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        print("🌐 NCBI Entrez client initialized")

    def _run_command_direct(self, command_parts: List[str], timeout_seconds: int = ENTREZ_SHORT_TIMEOUT_SECONDS) -> Optional[str]:
        """
        Runs a command directly using subprocess.Popen and returns its stdout.
        Handles retries and timeouts.
        """
        command_str = ' '.join(command_parts)
        tqdm.write(f"DEBUG: Entrez: Attempting command: {command_str} (Timeout: {timeout_seconds}s)", file=sys.stderr)
        for attempt in range(self.retry_attempts):
            process = None
            try:
                process = subprocess.Popen(command_parts, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, stderr = process.communicate(timeout=timeout_seconds)
                if process.returncode == 0:
                    tqdm.write(f"DEBUG: Entrez: Command successful (Attempt {attempt+1}). Output size: {len(stdout)}B.", file=sys.stderr)
                    return stdout.decode('utf-8', errors='ignore')
                else:
                    tqdm.write(f"ERROR: Entrez: Command failed (Attempt {attempt+1}): {command_str}. Return Code: {process.returncode}. Stderr: {stderr.decode('utf-8', errors='ignore').strip()}", file=sys.stderr)
            except subprocess.TimeoutExpired:
                tqdm.write(f"ERROR: Entrez: Command timed out ({timeout_seconds}s, Attempt {attempt+1}): {command_str}", file=sys.stderr)
                if process: process.kill(); process.communicate() 
            except Exception as e:
                tqdm.write(f"ERROR: Entrez: An exception occurred (Attempt {attempt+1}) while running command: {command_str}. Exception: {e}", file=sys.stderr)

            if attempt < self.retry_attempts - 1:
                tqdm.write(f"DEBUG: Entrez: Retrying in {self.retry_delay} seconds...", file=sys.stderr)
                time.sleep(self.retry_delay)
            else:
                tqdm.write(f"ERROR: Entrez: Command failed definitively after {self.retry_attempts} attempts: {command_str}", file=sys.stderr)
        return None

    def _fetch_runinfo_to_temp_file(self, keyword: str) -> Optional[str]:
        """
        Fetches SRA runinfo for a keyword and saves it to a temporary CSV file.
        Returns the path to the temporary file, or None on failure.
        """
        print(f"DEBUG: Entrez: Fetching SRA runinfo for keyword '{keyword}'", file=sys.stderr)
        fetch_start_time = time.time()
        esearch_cmd = ["esearch", "-db", "sra", "-query", f"{keyword}[All Fields]"]
        efetch_cmd = ["efetch", "-db", "sra", "-format", "runinfo"]
        temp_file_path = None
        try:
            with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix=".csv", encoding='utf-8') as tf:
                temp_file_path = tf.name
            tqdm.write(f"DEBUG: Entrez: Temporary runinfo file for '{keyword}': {temp_file_path}", file=sys.stderr)

            for attempt in range(self.retry_attempts):
                esearch_process, efetch_process = None, None
                try:
                    with open(temp_file_path, 'w', encoding='utf-8') as outfile:
                        esearch_process = subprocess.Popen(esearch_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        efetch_process = subprocess.Popen(efetch_cmd, stdin=esearch_process.stdout, stdout=outfile, stderr=subprocess.PIPE)
                        if esearch_process.stdout: esearch_process.stdout.close() 

                        efetch_stdout, efetch_stderr = efetch_process.communicate(timeout=ENTREZ_LONG_TIMEOUT_SECONDS)
                        esearch_stdout, esearch_stderr = esearch_process.communicate(timeout=ENTREZ_SHORT_TIMEOUT_SECONDS)

                    if efetch_process.returncode == 0: 
                        duration = time.time() - fetch_start_time
                        file_size = os.path.getsize(temp_file_path)
                        if file_size > 0:
                            print(f"INFO: Entrez: Successfully fetched runinfo for '{keyword}' to {temp_file_path}. Size: {file_size}B. (Time: {duration:.2f}s)", file=sys.stderr)
                            return temp_file_path
                        else:
                            print(f"WARNING: Entrez: Runinfo file for '{keyword}' is empty, but command succeeded. (Time: {duration:.2f}s)", file=sys.stderr)
                            return temp_file_path 
                    else:
                        print(f"ERROR: Entrez: Failed to fetch runinfo for '{keyword}' (Attempt {attempt+1}). Efetch RC: {efetch_process.returncode}. Efetch Stderr: {efetch_stderr.decode(errors='ignore').strip()}", file=sys.stderr)
                        if esearch_process.returncode != 0: 
                               print(f"ERROR: Entrez: Esearch also failed for '{keyword}'. Esearch RC: {esearch_process.returncode}. Esearch Stderr: {esearch_stderr.decode(errors='ignore').strip()}", file=sys.stderr)

                except subprocess.TimeoutExpired:
                    print(f"ERROR: Entrez: Timeout occurred while fetching runinfo for '{keyword}' (Attempt {attempt+1}).", file=sys.stderr)
                except Exception as e:
                    print(f"ERROR: Entrez: An exception occurred during runinfo pipe for '{keyword}' (Attempt {attempt+1}): {e}", file=sys.stderr)
                finally:
                    if efetch_process and efetch_process.poll() is None: efetch_process.kill(); efetch_process.communicate()
                    if esearch_process and esearch_process.poll() is None: esearch_process.kill(); esearch_process.communicate()

                if attempt < self.retry_attempts - 1: time.sleep(self.retry_delay)
                else: print(f"ERROR: Entrez: Failed to fetch runinfo for '{keyword}' after {self.retry_attempts} retries.", file=sys.stderr)

            if temp_file_path and os.path.exists(temp_file_path) and os.path.getsize(temp_file_path) == 0:
                os.remove(temp_file_path); return None
            return None 

        except Exception as e: 
            print(f"ERROR: Entrez: General exception in _fetch_runinfo_to_temp_file for '{keyword}': {e}", file=sys.stderr)

        if temp_file_path and os.path.exists(temp_file_path):
            try: os.remove(temp_file_path)
            except OSError: pass 
        return None

    def get_sra_experiment_ids_from_runinfo_file(self, keyword: str) -> List[str]:
        """
        Gets SRA Experiment (SRX/ERX/DRX) IDs from the fetched runinfo file for a keyword.
        """
        print(f"INFO: Entrez: Getting SRA Experiment IDs for keyword '{keyword}'...", file=sys.stderr)
        temp_file_path = self._fetch_runinfo_to_temp_file(keyword)
        if not temp_file_path: 
            return []

        srx_ids = []
        try:
            if os.path.getsize(temp_file_path) == 0: 
                print(f"INFO: Entrez: Runinfo file for '{keyword}' was empty. No SRX IDs found.", file=sys.stderr)
                return []

            df = pd.read_csv(temp_file_path, dtype=str)
            if "Experiment" in df.columns:
                for exp_id in df["Experiment"].dropna().unique():
                    if isinstance(exp_id, str) and exp_id.strip().startswith(("SRX", "ERX", "DRX")):
                        srx_ids.append(exp_id.strip())
            else:
                print(f"WARNING: Entrez: 'Experiment' column not found in runinfo for '{keyword}'. Cannot extract SRX IDs.", file=sys.stderr)
            print(f"INFO: Entrez: Found {len(srx_ids)} unique SRA Experiment IDs for '{keyword}'.", file=sys.stderr)
        except pd.errors.EmptyDataError: 
             print(f"WARNING: Entrez: Runinfo file for '{keyword}' was empty or malformed (pandas EmptyDataError).", file=sys.stderr)
        except Exception as e:
            print(f"ERROR: Entrez: Failed to parse SRA Experiment IDs from runinfo for '{keyword}': {e}", file=sys.stderr)
        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                try: os.remove(temp_file_path)
                except OSError: pass 
        return srx_ids

    def efetch_sra_experiment_xml(self, sra_experiment_id: str, save_xml_dir: Optional[str] = None) -> Optional[str]:
        """
        Fetches SRA Experiment XML for a given SRA Experiment ID.
        Optionally saves the XML to a file.
        """
        start_time = time.time()
        tqdm.write(f"DEBUG: Entrez: Fetching SRA Experiment XML for SRX ID '{sra_experiment_id}'", file=sys.stderr)
        if not sra_experiment_id:
            tqdm.write("ERROR: Entrez: sra_experiment_id cannot be empty for XML fetch.", file=sys.stderr)
            return None

        command_parts = ["efetch", "-db", "sra", "-id", sra_experiment_id, "-format", "xml"]
        xml_content = self._run_command_direct(command_parts, ENTREZ_SHORT_TIMEOUT_SECONDS)
        duration = time.time() - start_time

        if xml_content:
            tqdm.write(f"DEBUG: Entrez: Successfully fetched XML for {sra_experiment_id} (Size: {len(xml_content)}B, Time: {duration:.2f}s).", file=sys.stderr)
            if save_xml_dir:
                try:
                    os.makedirs(save_xml_dir, exist_ok=True) 
                    xml_file_path = os.path.join(save_xml_dir, f"{sra_experiment_id}.xml")
                    with open(xml_file_path, 'w', encoding='utf-8') as f: f.write(xml_content)
                    tqdm.write(f"DEBUG: Entrez: Saved XML for {sra_experiment_id} to {xml_file_path}.", file=sys.stderr)
                except Exception as e:
                    tqdm.write(f"ERROR: Entrez: Failed to save XML for {sra_experiment_id}: {e}", file=sys.stderr)
        else:
            tqdm.write(f"DEBUG: Entrez: Failed to fetch XML for {sra_experiment_id} (Time: {duration:.2f}s).", file=sys.stderr)
        return xml_content

class LLMProcessor:
    """Handles LLM processing tasks with optimized agents."""
    
    # Class variable to track last request time for throttling
    _last_request_time = 0
    _request_lock = None
    
    def __init__(self, model_name: str = OLLAMA_MODEL_NAME_DEFAULT, base_url: str = OLLAMA_BASE_URL_DEFAULT,
                 retry_attempts: int = RETRY_ATTEMPTS, retry_delay: int = RETRY_DELAY_SECONDS):
        self.model_name = model_name
        self.base_url = base_url
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self.llm = self._get_llm_instance()
        
        # Initialize thread lock for request throttling
        if LLMProcessor._request_lock is None:
            LLMProcessor._request_lock = threading.Lock()
        
        # Initialize optimized prompts (reduced from 3 to 2 agents)
        self.geo_accessions_extraction_prompt = self._get_geo_accessions_extraction_prompt()
        self.comprehensive_metadata_prompt = self._get_comprehensive_metadata_prompt()
        print(f"🤖 LLM processor initialized with {model_name}")

    def _throttle_requests(self):
        """Ensure minimum time between LLM requests to prevent overload."""
        with LLMProcessor._request_lock:
            current_time = time.time()
            time_since_last_request = current_time - LLMProcessor._last_request_time
            
            if time_since_last_request < LLM_REQUEST_DELAY_SECONDS:
                wait_time = LLM_REQUEST_DELAY_SECONDS - time_since_last_request
                tqdm.write(f"🔄 Throttling request (waiting {wait_time:.1f}s)...", file=sys.stderr)
                time.sleep(wait_time)
            
            LLMProcessor._last_request_time = time.time()

    def _get_llm_instance(self) -> Optional[ChatOllama]:
        """Initialize and return an Ollama LLM instance."""
        max_connection_attempts = 3
        for attempt in range(max_connection_attempts):
            try:
                if attempt > 0:
                    print(f"🔄 Reconnection attempt {attempt + 1}/{max_connection_attempts}...")
                    time.sleep(5)  # Wait before retry
                
                print("🤖 Connecting to AI model...")
                llm = ChatOllama(model=self.model_name, base_url=self.base_url, temperature=0.1)
                
                # Test the LLM connection with a simple request
                print("🧠 Testing AI model connection...")
                test_response = llm.invoke("Test connection. Respond with 'OK'.")
                if test_response and 'OK' in str(test_response).upper():
                    print("✅ AI model connection successful!")
                    return llm
                else:
                    print("⚠️ AI model test response unexpected, but proceeding...")
                    return llm  # Still return it as it might work
                    
            except Exception as e:
                error_msg = str(e)
                print(f"❌ Connection attempt {attempt + 1} failed: {error_msg}")
                
                if attempt < max_connection_attempts - 1:
                    if "connection" in error_msg.lower() or "eof" in error_msg.lower():
                        print("🔄 Ollama might be starting up, waiting before retry...")
                        time.sleep(10)
                    else:
                        time.sleep(5)
                else:
                    print(f"❌ Failed to connect to AI model after {max_connection_attempts} attempts")
                    
        return None
    
    def _check_ollama_health(self) -> bool:
        """Check if Ollama is responding properly."""
        try:
            test_response = self.llm.invoke("ping")
            return True
        except Exception:
            return False
    
    def _wait_for_ollama_recovery(self, wait_time: int = 15):
        """Wait for Ollama to recover from a crash."""
        print(f"⏳ Waiting {wait_time}s for Ollama to recover...")
        time.sleep(wait_time)
        
        # Try to reconnect
        print("🔄 Attempting to reconnect to Ollama...")
        new_llm = self._get_llm_instance()
        if new_llm:
            self.llm = new_llm
            print("✅ Successfully reconnected to Ollama!")
            return True
        else:
            print("❌ Failed to reconnect to Ollama")
            return False

    def _get_geo_accessions_extraction_prompt(self) -> ChatPromptTemplate:
        """Optimized prompt for extracting GSE and GSM accession numbers from SRA XML."""
        system_message = """You are an AI assistant specialized in extracting GEO accession numbers from SRA XML data.

IMPORTANT: You must find GSE and GSM accession numbers, NOT SRR/ERR/DRR run numbers.

GSE = GEO Series (starts with "GSE" + numbers, like GSE12345)
GSM = GEO Sample (starts with "GSM" + numbers, like GSM123456)

DO NOT EXTRACT:
- SRR/ERR/DRR numbers (these are SRA run IDs, not GEO accessions)
- Any other identifiers

Look for these XML patterns:
- <STUDY_REF accession="GSE12345"/>
- <EXTERNAL_ID namespace="GEO">GSE12345</EXTERNAL_ID>
- <EXPERIMENT alias="GSM123456"/>
- <EXTERNAL_ID namespace="GEO">GSM123456</EXTERNAL_ID>

RESPONSE FORMAT: You must respond with exactly this JSON structure:
{{"gse": "GSE12345", "gsm": "GSM123456"}}

Examples:
- If you find GSE12345 and GSM678910: {{"gse": "GSE12345", "gsm": "GSM678910"}}
- If you find only GSE12345: {{"gse": "GSE12345", "gsm": "N/A"}}
- If you find only GSM678910: {{"gse": "N/A", "gsm": "GSM678910"}}
- If you find neither: {{"gse": "N/A", "gsm": "N/A"}}

Do not include arrays, explanations, or any other format."""

        human_template = """SRA Experiment XML:
{sra_experiment_xml}

Find GSE and GSM accessions (JSON object only):"""
        return ChatPromptTemplate.from_messages([("system", system_message), ("human", human_template)])

    def _get_comprehensive_metadata_prompt(self) -> ChatPromptTemplate:
        """Streamlined prompt that combines summary generation and metadata extraction."""
        system_message = """You are an expert biomedical data curator. Extract comprehensive metadata from SRA and GEO data and provide a structured JSON response.

IMPORTANT: Your response must be a valid JSON object with exactly these fields. Use "N/A" for missing data.

Required JSON structure:
{{
  "experiment_title": "Brief descriptive title of the experiment",
  "species": "Full scientific name (e.g., Homo sapiens, Mus musculus)",
  "sequencing_technique": "RNA-Seq|ChIP-Seq|ATAC-Seq|scRNA-Seq|WGS|WES|Bisulfite-Seq|OTHER",
  "sample_type": "Cell Line|Primary Cells|Tissue: Tumor|Tissue: Normal Adjacent|Tissue: Healthy Donor|Organoid|Other",
  "cell_line_name": "Standard cell line name if applicable",
  "tissue_type": "Specific tissue/organ type",
  "tissue_source_details": "Additional tissue source information",
  "disease_description": "Disease name and details or 'Healthy Control'",
  "sample_treatment_protocol": "Treatment details with concentrations/duration",
  "treatment": "Standardized treatment term (see guidelines below)",
  "clinical_sample_identifier": "Patient/sample ID if clinical",
  "library_source": "TRANSCRIPTOMIC|GENOMIC|EPIGENOMIC|METAGENOMIC|OTHER",
  "instrument_model": "Sequencing instrument name",
  "is_chipseq_related_experiment": "yes|no",
  "chipseq_antibody_target": "Target protein/histone mark for ChIP-seq",
  "chipseq_control_description": "Control description for ChIP-seq",
  "chipseq_igg_control_present": "yes|no|unknown",
  "chipseq_input_control_present": "yes|no|unknown", 
  "chipseq_nfcore_summary_lines": "N/A",
  "scientific_sample_summary": "2-4 sentence scientific summary of the sample and experiment"
}}

TREATMENT FIELD GUIDELINES:
- Use standardized terms based on the sample_treatment_protocol
- "WT" = wild-type, untreated, or unknown treatment
- "control" = vehicle control, PBS, DMSO, negative control
- "GENE_overexpressed" = gene overexpression (e.g., "YAP1_overexpressed")
- "GENE_knockdown" = siRNA/shRNA knockdown (e.g., "PLXND1_knockdown", "siJUN_knockdown")
- "GENE_knockout" = CRISPR knockout or genetic deletion
- "COMPOUND_treated" = drug/compound treatment (e.g., "Romidepsin_treated", "DOX_treated")
- Combine multiple treatments with "+" (e.g., "Romidepsin_treated+Ipata_treated")
- Use actual gene/compound names, keep concise but specific

EXTRACTION GUIDELINES:
1. Use domain knowledge to infer missing information (e.g., HeLa→human, ChIP-seq→EPIGENOMIC)
2. Cross-reference SRA and GEO data for consistency
3. For ChIP-seq fields, only fill if sequencing_technique is ChIP-seq related
4. Be precise with species names (full scientific names)
5. Extract complete treatment protocols with dosages/times when available
6. For treatment field, analyze the protocol and create standardized terms

Your response must be ONLY the JSON object, nothing else."""

        human_template = """Original Search Keyword: {original_keyword}
SRA Experiment ID: {sra_experiment_id}
GSE Accession: {gse_accession}
GSM Accession: {gsm_accession}

SRA Experiment XML:
{sra_experiment_xml}

GEO Data Summary:
{geo_data_summary}

Extract metadata:"""
        return ChatPromptTemplate.from_messages([("system", system_message), ("human", human_template)])

    def _run_llm_chain(self, prompt_template: ChatPromptTemplate, input_data: Dict[str, str], sra_id_for_log: str, purpose: str) -> Optional[str]:
        """Runs LLM chain with improved error handling and JSON extraction."""
        if not self.llm:
            tqdm.write(f"ERROR: LLM not initialized. Cannot run '{purpose}' for {sra_id_for_log}.", file=sys.stderr)
            if purpose == "GEO Accessions Extraction": 
                return json.dumps({"gse": "N/A", "gsm": "N/A"})
            return None

        chain = prompt_template | self.llm | StrOutputParser()
        tqdm.write(f"DEBUG: LLM ({purpose}): Processing {sra_id_for_log}", file=sys.stderr)

        for attempt in range(self.retry_attempts):
            try:
                # Throttle requests to prevent overwhelming Ollama
                self._throttle_requests()
                
                # Add small delay to prevent overwhelming Ollama on retries
                if attempt > 0:
                    time.sleep(LLM_REQUEST_DELAY_SECONDS)
                
                start_time = time.time()
                response_text = chain.invoke(input_data).strip()
                duration = time.time() - start_time
                
                tqdm.write(f"DEBUG: LLM ({purpose}) completed for {sra_id_for_log} in {duration:.2f}s (attempt {attempt+1})", file=sys.stderr)

                # Extract JSON from response
                json_str = self._extract_json_from_response(response_text, purpose, sra_id_for_log)
                if json_str:
                    # Validate JSON
                    try:
                        parsed = json.loads(json_str)
                        tqdm.write(f"DEBUG: Parsed JSON for {sra_id_for_log} ({purpose}): {parsed}", file=sys.stderr)
                        
                        if purpose == "GEO Accessions Extraction":
                            # Ensure we have the right structure (accept N/A values as valid)
                            # Handle both lowercase and uppercase field names
                            has_gse = "gse" in parsed or "GSE" in parsed
                            has_gsm = "gsm" in parsed or "GSM" in parsed
                            
                            if isinstance(parsed, dict) and has_gse and has_gsm:
                                # Extract values with case-insensitive lookup
                                gse_val = parsed.get("gse", parsed.get("GSE", "N/A"))
                                gsm_val = parsed.get("gsm", parsed.get("GSM", "N/A"))
                                
                                if gse_val != "N/A" or gsm_val != "N/A":
                                    tqdm.write(f"INFO: Found GEO accessions for {sra_id_for_log}: GSE={gse_val}, GSM={gsm_val}", file=sys.stderr)
                                    # Normalize the response to lowercase for consistency
                                    normalized_response = json.dumps({"gse": gse_val, "gsm": gsm_val})
                                    return normalized_response
                                else:
                                    tqdm.write(f"DEBUG: No GEO accessions found for {sra_id_for_log} (using SRA data only)", file=sys.stderr)
                            else:
                                tqdm.write(f"DEBUG: JSON validation failed for {sra_id_for_log} ({purpose}). Type: {type(parsed)}, Keys: {list(parsed.keys()) if isinstance(parsed, dict) else 'Not a dict'}", file=sys.stderr)
                        elif purpose == "Comprehensive Metadata Extraction":
                            # Ensure we have a dictionary with expected fields
                            if isinstance(parsed, dict) and "experiment_title" in parsed:
                                return json_str
                        
                        tqdm.write(f"WARNING: LLM ({purpose}): JSON structure validation failed for {sra_id_for_log}", file=sys.stderr)
                    except json.JSONDecodeError as e:
                        tqdm.write(f"WARNING: LLM ({purpose}): JSON validation failed for {sra_id_for_log}: {e}", file=sys.stderr)

            except Exception as e:
                error_msg = str(e)
                tqdm.write(f"ERROR: LLM ({purpose}) exception for {sra_id_for_log} (attempt {attempt+1}): {error_msg}", file=sys.stderr)
                
                # Handle specific Ollama errors with recovery
                if "llama runner process no longer running" in error_msg:
                    tqdm.write(f"WARNING: Ollama model crashed. Initiating recovery...", file=sys.stderr)
                    if self._wait_for_ollama_recovery(15):
                        tqdm.write(f"INFO: Ollama recovered, continuing processing...", file=sys.stderr)
                        continue  # Retry with recovered connection
                    else:
                        tqdm.write(f"ERROR: Could not recover Ollama connection", file=sys.stderr)
                        break  # Exit retry loop
                        
                elif "EOF" in error_msg or "connection" in error_msg.lower():
                    tqdm.write(f"WARNING: Connection issue with Ollama. Attempting recovery...", file=sys.stderr)
                    if self._wait_for_ollama_recovery(10):
                        continue  # Retry with recovered connection
                    else:
                        time.sleep(self.retry_delay)
                        
                elif "timeout" in error_msg.lower():
                    tqdm.write(f"WARNING: Request timeout. Waiting before retry...", file=sys.stderr)
                    time.sleep(self.retry_delay * 2)
                else:
                    # Unknown error, wait standard time
                    time.sleep(self.retry_delay)

            if attempt < self.retry_attempts - 1:
                time.sleep(self.retry_delay)

        # Fallback responses
        tqdm.write(f"ERROR: LLM ({purpose}) failed for {sra_id_for_log} after {self.retry_attempts} attempts", file=sys.stderr)
        if purpose == "GEO Accessions Extraction":
            return json.dumps({"gse": "N/A", "gsm": "N/A"})
        return None

    def _extract_json_from_response(self, response_text: str, purpose: str, sra_id: str) -> Optional[str]:
        """Extract JSON from LLM response with improved parsing."""
        if not response_text or response_text.strip() == "":
            tqdm.write(f"WARNING: Empty LLM response for {sra_id} ({purpose})", file=sys.stderr)
            return None
        
        # First, check if the response is already clean JSON
        response_stripped = response_text.strip()
        if response_stripped.startswith('{') and response_stripped.endswith('}'):
            try:
                # Test if it's valid JSON
                json.loads(response_stripped)
                tqdm.write(f"DEBUG: Response is clean JSON for {sra_id} ({purpose})", file=sys.stderr)
                return response_stripped
            except json.JSONDecodeError:
                pass  # Continue to other extraction methods
            
        # Try to find JSON in code blocks
        json_pattern = r"```(?:json)?\s*(\{.*?\})\s*```"
        match = re.search(json_pattern, response_text, re.DOTALL | re.IGNORECASE)
        if match:
            tqdm.write(f"DEBUG: Found JSON in code block for {sra_id} ({purpose})", file=sys.stderr)
            return match.group(1).strip()
        
        # Also check for arrays in code blocks (common mistake)
        array_pattern = r"```(?:json)?\s*(\[.*?\])\s*```"
        match = re.search(array_pattern, response_text, re.DOTALL | re.IGNORECASE)
        if match:
            tqdm.write(f"WARNING: Found array instead of object in code block for {sra_id} ({purpose}). LLM returned wrong format.", file=sys.stderr)
            # Don't return arrays for our use case
            
        # Try to find JSON object in response (improved pattern)
        json_pattern = r"(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})"
        matches = re.findall(json_pattern, response_text, re.DOTALL)
        if matches:
            # Take the largest JSON object (most likely to be complete)
            best_match = max(matches, key=len)
            try:
                # Validate it's proper JSON
                json.loads(best_match)
                tqdm.write(f"DEBUG: Found valid JSON object for {sra_id} ({purpose}), length: {len(best_match)}", file=sys.stderr)
                return best_match.strip()
            except json.JSONDecodeError:
                pass
        
        # More aggressive JSON search - look for any content between curly braces
        simple_json_pattern = r"\{[^{}]*\}"
        match = re.search(simple_json_pattern, response_text, re.DOTALL)
        if match:
            try:
                json.loads(match.group(0))
                tqdm.write(f"DEBUG: Found simple JSON pattern for {sra_id} ({purpose})", file=sys.stderr)
                return match.group(0).strip()
            except json.JSONDecodeError:
                pass
        
        # Log the actual response for debugging
        tqdm.write(f"WARNING: No valid JSON found in LLM response for {sra_id} ({purpose}). Response preview: {repr(response_text[:200])}", file=sys.stderr)
        return None

    def extract_geo_accessions_from_sra_xml(self, sra_xml_content: str, sra_experiment_id: str) -> Dict[str, str]:
        """Extract GSE and GSM IDs using LLM with regex fallback."""
        # Try LLM first
        llm_response = self._run_llm_chain(
            self.geo_accessions_extraction_prompt,
            {"sra_experiment_xml": sra_xml_content},
            sra_experiment_id,
            "GEO Accessions Extraction"
        )

        # Save debug output for GEO accessions extraction
        try:
            debug_dir = "phase1_json_outputs"
            os.makedirs(debug_dir, exist_ok=True)
            debug_file = os.path.join(debug_dir, f"{sra_experiment_id}_geo_accessions_debug.json")
            debug_output = {
                "sra_experiment_id": sra_experiment_id,
                "raw_llm_response": llm_response,
                "extraction_method": "LLM" if llm_response else "regex_fallback",
                "timestamp": time.time()
            }
            with open(debug_file, 'w', encoding='utf-8') as f:
                json.dump(debug_output, f, indent=2)
        except Exception as e:
            tqdm.write(f"WARNING: Could not save GEO accessions debug output for {sra_experiment_id}: {e}", file=sys.stderr)

        if llm_response:
            try:
                accessions = json.loads(llm_response)
                if isinstance(accessions, dict):
                    gse = accessions.get("gse", "N/A")
                    gsm = accessions.get("gsm", "N/A")
                    # Validate accession format
                    if gse != "N/A" and not gse.upper().startswith("GSE"):
                        gse = "N/A"
                    if gsm != "N/A" and not gsm.upper().startswith("GSM"):
                        gsm = "N/A"
                    
                    if gse != "N/A" or gsm != "N/A":
                        tqdm.write(f"INFO: LLM extracted GEO accessions for {sra_experiment_id}: GSE={gse}, GSM={gsm}", file=sys.stderr)
                        return {"gse": gse, "gsm": gsm}
            except (json.JSONDecodeError, AttributeError):
                pass
        
        # Fallback to regex
        tqdm.write(f"INFO: Using regex fallback for GEO accession extraction for {sra_experiment_id}", file=sys.stderr)
        gse_match = re.search(r'GSE\d+', sra_xml_content, re.IGNORECASE)
        gsm_match = re.search(r'GSM\d+', sra_xml_content, re.IGNORECASE)
        
        return {
            "gse": gse_match.group().upper() if gse_match else "N/A",
            "gsm": gsm_match.group().upper() if gsm_match else "N/A"
        }

    def extract_comprehensive_metadata(self, sra_xml_content: str, geo_data_summary: str, original_keyword: str, 
                                     sra_experiment_id: str, gse_accession: str, gsm_accession: str, 
                                     target_csv_columns: List[str]) -> Dict[str, Any]:
        """Extract all metadata in one streamlined LLM call."""
        # Initialize result with N/A
        result_data = {col: "N/A" for col in target_csv_columns}
        
        # Pre-populate known fields
        result_data["sra_experiment_id"] = sra_experiment_id
        result_data["original_keyword"] = original_keyword
        result_data["gse_accession"] = gse_accession
        result_data["gsm_accession"] = gsm_accession
        
        # Prepare XML snippet (limit size for LLM)
        xml_snippet = sra_xml_content[:3000] if len(sra_xml_content) > 3000 else sra_xml_content
        if len(sra_xml_content) > 6000:
            xml_snippet += "\n...[TRUNCATED]...\n" + sra_xml_content[-2000:]
        
        # Call LLM
        llm_response = self._run_llm_chain(
            self.comprehensive_metadata_prompt,
            {
                "original_keyword": original_keyword,
                "sra_experiment_id": sra_experiment_id,
                "gse_accession": gse_accession,
                "gsm_accession": gsm_accession,
                "sra_experiment_xml": xml_snippet,
                "geo_data_summary": geo_data_summary if geo_data_summary else "N/A"
            },
            sra_experiment_id,
            "Comprehensive Metadata Extraction"
        )
        
        # Parse LLM response and map to result
        if llm_response:
            try:
                llm_data = json.loads(llm_response)
                
                # Direct mapping - field names should match exactly
                for field in target_csv_columns:
                    if field in llm_data and llm_data[field] is not None:
                        value = str(llm_data[field]).strip()
                        # Skip empty or null-like values
                        if value.lower() not in ["", "n/a", "na", "none", "null", "unknown", "not specified"]:
                            result_data[field] = value
                
                tqdm.write(f"INFO: Successfully extracted metadata for {sra_experiment_id}", file=sys.stderr)
                
            except json.JSONDecodeError as e:
                tqdm.write(f"ERROR: Failed to parse LLM JSON for {sra_experiment_id}: {e}", file=sys.stderr)
                result_data["scientific_sample_summary"] = "Failed to parse LLM response for metadata extraction"
        else:
            tqdm.write(f"WARNING: No LLM response for metadata extraction for {sra_experiment_id}", file=sys.stderr)
            result_data["scientific_sample_summary"] = "LLM failed to generate metadata"
        
        # Save raw LLM output for debugging
        self._save_llm_debug_output(sra_experiment_id, llm_response, llm_data if 'llm_data' in locals() else {})
        
        return result_data

    def _save_llm_debug_output(self, sra_experiment_id: str, raw_response: str, parsed_data: Dict):
        """Save LLM output for debugging purposes."""
        debug_dir = "phase1_json_outputs"
        try:
            os.makedirs(debug_dir, exist_ok=True)
            debug_file = os.path.join(debug_dir, f"{sra_experiment_id}_phase1_synthesis_LLM_output.json")
            
            debug_output = {
                "sra_experiment_id": sra_experiment_id,
                "raw_llm_response": raw_response,
                "parsed_data": parsed_data,
                "timestamp": time.time()
            }
            
            with open(debug_file, 'w', encoding='utf-8') as f:
                json.dump(debug_output, f, indent=2)
                
        except Exception as e:
            tqdm.write(f"ERROR: Could not save debug output for {sra_experiment_id}: {e}", file=sys.stderr)


# PostProcessor class is removed as Phase 2 is removed.

class CSVResultWriter:
    """Writes metadata records to a CSV file, handling headers and appending correctly."""
    def __init__(self, output_path: str, fieldnames: List[str]):
        self.output_path = output_path
        self.fieldnames = fieldnames # Should be FINAL_OUTPUT_COLUMNS (which is now INITIAL_OUTPUT_COLUMNS)
        self.outfile: Optional[Any] = None
        self.writer: Optional[csv.DictWriter] = None
        self._open_writer() 
        print(f"DEBUG: CSVResultWriter initialized for '{output_path}'. Fieldnames (first 5): {self.fieldnames[:5]}...")

    def _open_writer(self):
        file_exists = os.path.exists(self.output_path)
        is_empty = (not file_exists) or (os.path.getsize(self.output_path) == 0)
        self.outfile = open(self.output_path, 'a', newline='', encoding='utf-8')
        self.writer = csv.DictWriter(
            self.outfile, fieldnames=self.fieldnames,
            quoting=csv.QUOTE_ALL, restval="N/A", extrasaction='ignore'
        )
        if is_empty: 
            self.writer.writeheader()
            self.outfile.flush() 

    def write_batch(self, data_list: List[Dict[str, Any]]):
        if not self.writer or not self.outfile or self.outfile.closed:
            tqdm.write("DEBUG: CSV writer was closed or not initialized. Re-opening.", file=sys.stderr)
            self._open_writer() 
        if not self.writer: 
            print("ERROR: CSV writer failed to re-open or initialize. Cannot write batch.", file=sys.stderr)
            return
        try:
            for record in data_list:
                self.writer.writerow(record)
            self.outfile.flush() 
        except Exception as e:
            tqdm.write(f"ERROR: An exception occurred while writing batch to CSV '{self.output_path}': {e}", file=sys.stderr)

    def close_writer(self):
        if self.outfile and not self.outfile.closed:
            try:
                self.outfile.close()
                print(f"INFO: CSV file '{self.output_path}' has been closed.", file=sys.stderr)
            except Exception as e:
                print(f"ERROR: An exception occurred while closing CSV file '{self.output_path}': {e}", file=sys.stderr)
        self.outfile, self.writer = None, None

def _process_single_srx(srx_id: str, keyword: str, output_columns: List[str], llm_processor: LLMProcessor, entrez_client: EntrezClient, save_xml_dir: Optional[str], save_geo_dir: Optional[str], temp_geo_dir: str) -> Dict[str, Any]:
    """Optimized processing function with streamlined LLM calls."""
    tqdm.write(f"    Processing SRX ID: '{srx_id}' (Keyword: '{keyword}')", file=sys.stderr)
    
    # Initialize record
    current_record = {col: "N/A" for col in output_columns}
    current_record["original_keyword"] = keyword
    current_record["sra_experiment_id"] = srx_id

    # Fetch SRA XML
    sra_xml_content = entrez_client.efetch_sra_experiment_xml(srx_id, save_xml_dir)
    if not sra_xml_content:
        tqdm.write(f"WARNING: Failed to fetch SRA XML for {srx_id}", file=sys.stderr)
        current_record["experiment_title"] = "SRA_XML_FETCH_FAILED"
        current_record["scientific_sample_summary"] = "SRA XML fetch failed, cannot generate summary or extract further details."
        return current_record

    # Extract GEO accessions (Agent 1)
    geo_accessions = llm_processor.extract_geo_accessions_from_sra_xml(sra_xml_content, srx_id)
    gse_id = geo_accessions.get("gse", "N/A")
    gsm_id = geo_accessions.get("gsm", "N/A")

    # Fetch GEO data if available
    geo_data_summary = "N/A"
    if gse_id != "N/A" or gsm_id != "N/A":
        geo_data_summary = fetch_geo_data_summary(gse_id, gsm_id, srx_id, temp_geo_dir, save_geo_dir)

    # Extract comprehensive metadata (Agent 2 - combines summary + metadata)
    result_data = llm_processor.extract_comprehensive_metadata(
        sra_xml_content, geo_data_summary, keyword, srx_id, gse_id, gsm_id, output_columns
    )
    
    return result_data

def fetch_geo_data_summary(gse_id: str, gsm_id: str, srx_id: str, temp_geo_dir: str, save_geo_dir: Optional[str]) -> str:
    """Fetch and summarize GEO data."""
    geo_id_to_fetch = gsm_id if gsm_id != "N/A" else gse_id
    geo_type = "GSM" if gsm_id != "N/A" else "GSE"
    
    if geo_id_to_fetch == "N/A":
        return "No GEO ID available"
    
    try:
        tqdm.write(f"    Fetching {geo_type} data: {geo_id_to_fetch} for SRX: {srx_id}", file=sys.stderr)
        os.makedirs(temp_geo_dir, exist_ok=True)
        
        geo_object = GEOparse.get_GEO(geo=geo_id_to_fetch, destdir=temp_geo_dir, silent=True, 
                                     annotate_gpl=False, include_data=False)
        
        if not geo_object:
            return f"Failed to fetch GEO data for {geo_id_to_fetch}"
        
        # Build summary
        summary_parts = [f"--- {geo_type} Metadata for {geo_id_to_fetch} ---"]
        
        if hasattr(geo_object, 'metadata'):
            for key, value in geo_object.metadata.items():
                if isinstance(value, list):
                    val_str = "; ".join(map(str, value[:3]))
                    if len(value) > 3:
                        val_str += f"... (Total: {len(value)} items)"
                else:
                    val_str = str(value)[:300]
                summary_parts.append(f"  {key}: {val_str}")
        
        # Handle GSM-specific data
        if geo_type == "GSE" and gsm_id != "N/A" and hasattr(geo_object, 'gsms') and gsm_id in geo_object.gsms:
            gsm_obj = geo_object.gsms[gsm_id]
            if hasattr(gsm_obj, 'metadata'):
                summary_parts.append(f"\n--- GSM {gsm_id} Metadata ---")
                for key, value in gsm_obj.metadata.items():
                    val_str = str(value)[:300] if not isinstance(value, list) else "; ".join(map(str, value[:3]))
                    summary_parts.append(f"  {key}: {val_str}")
        
        # Save GEO file if requested
        if save_geo_dir:
            save_geo_file(geo_id_to_fetch, temp_geo_dir, save_geo_dir)
        
        return "\n".join(summary_parts)
        
    except Exception as e:
        tqdm.write(f"ERROR: GEO data fetch failed for {geo_id_to_fetch} (SRX: {srx_id}): {e}", file=sys.stderr)
        return f"Error fetching GEO data for {geo_id_to_fetch}: {str(e)[:150]}"

def save_geo_file(geo_id: str, temp_dir: str, save_dir: str):
    """Save GEO SOFT file to permanent location."""
    try:
        os.makedirs(save_dir, exist_ok=True)
        
        # Look for downloaded file
        for ext in [".soft.gz", ".soft"]:
            temp_file = os.path.join(temp_dir, f"{geo_id}{ext}")
            if os.path.exists(temp_file):
                target_file = os.path.join(save_dir, f"{geo_id}{ext}")
                if os.path.abspath(temp_file) != os.path.abspath(target_file):
                    os.rename(temp_file, target_file)
                    tqdm.write(f"DEBUG: Saved GEO file: {target_file}", file=sys.stderr)
                break
    except Exception as e:
        tqdm.write(f"ERROR: Could not save GEO file for {geo_id}: {e}", file=sys.stderr)

def main():
    overall_script_start_time = time.time()
    
    # Print animated banner
    print_banner()
    animated_loading("Initializing SRA/GEO Analysis Pipeline", 1.5)
    
    print_section_header("Configuration & Setup", "⚙️")
    print(f"🕐 Script started at {time.ctime(overall_script_start_time)}")

    parser = argparse.ArgumentParser(description="Fetch SRA/GEO metadata, generate summaries, and extract structured data using LLMs.")
    parser.add_argument("input_csv_path", nargs='?', help="Path to the input CSV file containing keywords. If not specified, will look for 'keywords.csv' in the current directory.")
    parser.add_argument("output_csv_path", nargs='?', help="Path to the output CSV file where results will be saved. If not specified, will create 'output/results_TIMESTAMP.csv'.")
    parser.add_argument("--keyword_column", default=None, type=str, help="Name of the column in the input CSV that contains keywords. If not specified, the first column is used.")
    parser.add_argument("--llm_model", default=OLLAMA_MODEL_NAME_DEFAULT, type=str, help=f"Name of the Ollama model to use (Default: {OLLAMA_MODEL_NAME_DEFAULT})")
    parser.add_argument("--llm_base_url", default=OLLAMA_BASE_URL_DEFAULT, type=str, help=f"Base URL for the Ollama API (Default: {OLLAMA_BASE_URL_DEFAULT})")
    parser.add_argument("--max_workers", type=int, default=MAX_PARALLEL_LLM_WORKERS, help=f"Number of parallel worker threads for processing SRA IDs (Default: {MAX_PARALLEL_LLM_WORKERS}). Use 1 for sequential processing if Ollama is unstable.")
    parser.add_argument("--sequential", action="store_true", help="Force sequential processing (same as --max_workers 1) for maximum Ollama stability.")
    parser.add_argument("--save_xml_dir", type=str, default=None, help="Optional: Directory path to save fetched SRA XML files.")
    parser.add_argument("--save_geo_dir", type=str, default=None, help="Optional: Directory path to save fetched GEO SOFT files.")
    parser.add_argument("--debug_single_srx_id", type=str, default=None, help="For debugging: provide a single SRX ID to fetch and process. Requires --debug_single_keyword.")
    parser.add_argument("--debug_single_keyword", type=str, default="DEBUG_KEYWORD", help="Keyword associated with --debug_single_srx_id for context (Default: DEBUG_KEYWORD).")
    args = parser.parse_args()
    
    print_section_header("File Detection & Auto-Configuration", "🔍")
    
    # Auto-detect keywords.csv if no input file specified
    if not args.input_csv_path:
        animated_loading("Searching for keyword files", 1.0)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Check for multiple possible keyword file names
        possible_keyword_files = ["keywords.csv", "keyword.csv", "Keywords.csv", "Keyword.csv"]
        default_keywords_file = None
        
        for filename in possible_keyword_files:
            candidate_file = os.path.join(script_dir, filename)
            if os.path.exists(candidate_file):
                default_keywords_file = candidate_file
                break
        
        if default_keywords_file:
            args.input_csv_path = default_keywords_file
            print_success(f"Found keyword file: '{os.path.basename(default_keywords_file)}'")
        else:
            print_error("No keyword file found in script directory")
            print("Please either:")
            print("1. Create a keyword file (keywords.csv, keyword.csv, etc.) in the same directory as the script, or")
            print("2. Specify the path to your keywords file as the first argument")
            print("\nExample usage:")
            print(f"  python {os.path.basename(__file__)}  # Uses keyword file and creates output/results_TIMESTAMP.csv")
            print(f"  python {os.path.basename(__file__)} output.csv  # Uses keyword file with specified output")
            print(f"  python {os.path.basename(__file__)} my_keywords.csv output.csv  # Uses specified files")
            sys.exit(1)
    else:
        print_success(f"Using specified keyword file: {args.input_csv_path}")
    
    # Auto-create output directory and filename if no output file specified
    if not args.output_csv_path:
        animated_loading("Setting up output directory", 1.0)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.join(script_dir, "output")
        
        # Create output directory if it doesn't exist
        try:
            os.makedirs(output_dir, exist_ok=True)
            print_success(f"Output directory ready: {output_dir}")
        except OSError as e:
            print_error(f"Could not create output directory '{output_dir}': {e}")
            sys.exit(1)
        
        # Use "result.csv" as the default filename
        default_output_file = os.path.join(output_dir, "result.csv")
        args.output_csv_path = default_output_file
        print_success(f"Output file: {default_output_file}")
    else:
        print_success(f"Using specified output file: {args.output_csv_path}")
    
    print(f"🔧 Configuration: {args}")

    # Handle sequential processing flag
    if args.sequential:
        args.max_workers = 1
        print_info("🔄 Sequential processing enabled for maximum Ollama stability")
    elif args.max_workers == 1:
        print_info("🔄 Sequential processing mode (default for stability)")
    else:
        print_info(f"⚡ Parallel processing with {args.max_workers} workers (experimental)")

    if args.save_xml_dir:
        try: 
            os.makedirs(args.save_xml_dir, exist_ok=True)
            print_success(f"XML save directory: {args.save_xml_dir}")
        except OSError as e: 
            print_warning(f"Could not create XML directory: {e}")
            args.save_xml_dir = None
    if args.save_geo_dir:
        try: 
            os.makedirs(args.save_geo_dir, exist_ok=True)
            print_success(f"GEO save directory: {args.save_geo_dir}")
        except OSError as e: 
            print_warning(f"Could not create GEO directory: {e}")
            args.save_geo_dir = None

    temp_geo_download_dir_obj = tempfile.TemporaryDirectory(prefix="geoparse_dl_")
    temp_geo_download_dir = temp_geo_download_dir_obj.name
    print_info(f"📂 Temporary GEO directory: {temp_geo_download_dir}")

    print_section_header("AI Model Initialization", "🤖")
    animated_loading(f"Connecting to {args.llm_model}", 2.0)
    
    llm_processor = LLMProcessor(model_name=args.llm_model, base_url=args.llm_base_url)
    if not llm_processor.llm: 
        print_error("LLM initialization failed!")
        temp_geo_download_dir_obj.cleanup() 
        sys.exit(1)
    else:
        print_success("🧠 AI model ready for metadata extraction!")

    if args.debug_single_srx_id:
        print_section_header("Debug Mode", "🐛")
        if not args.debug_single_keyword: 
            print_error("--debug_single_keyword required with --debug_single_srx_id")
            temp_geo_download_dir_obj.cleanup(); sys.exit(1)
        
        print_info(f"🎯 Processing single SRX: {args.debug_single_srx_id}")
        animated_loading("Setting up debug environment", 1.0)
        
        entrez_client_debug = EntrezClient() 

        # In debug mode, _process_single_srx will use INITIAL_OUTPUT_COLUMNS
        processed_record = _process_single_srx(
            args.debug_single_srx_id, args.debug_single_keyword, INITIAL_OUTPUT_COLUMNS,
            llm_processor, entrez_client_debug, args.save_xml_dir, args.save_geo_dir, temp_geo_download_dir
        )

        if processed_record:
            print_success("🎉 Debug processing completed!")
            print(f"📋 Metadata extracted:\n{json.dumps(processed_record, indent=2)}")
            # The CSV output in debug mode will use FINAL_OUTPUT_COLUMNS (which is INITIAL_OUTPUT_COLUMNS)
            pd.DataFrame([processed_record]).to_csv(args.output_csv_path, index=False, columns=FINAL_OUTPUT_COLUMNS, quoting=csv.QUOTE_ALL)
            print_success(f"💾 Debug results saved to: {args.output_csv_path}")
        else:
            print_error(f"Debug processing failed for {args.debug_single_srx_id}")

        print("\n🎯 ━━━ Debug Mode Complete ━━━")
        temp_geo_download_dir_obj.cleanup(); sys.exit(0)

    # --- Main Processing (Formerly Phase 1) ---
    print_section_header("Main Processing Pipeline", "🚀")
    phase1_start_time = time.time()
    print_info("🔬 Fetching SRA Data & AI-Powered Metadata Extraction")
    print_info(f"📁 Input: {args.input_csv_path}")
    print_info(f"📄 Output: {args.output_csv_path}")

    animated_loading("Initializing data providers", 1.0)
    keyword_provider = KeywordProvider(args.input_csv_path, args.keyword_column)
    entrez_client = EntrezClient() 

    keywords_to_process = keyword_provider.get_keywords()
    if not keywords_to_process:
        print_error("No keywords found in input CSV!")
    else:
        print_success(f"🔤 Found {len(keywords_to_process)} keywords to process")
        
        # CSV writer uses FINAL_OUTPUT_COLUMNS (which is INITIAL_OUTPUT_COLUMNS)
        csv_writer = CSVResultWriter(args.output_csv_path, FINAL_OUTPUT_COLUMNS)
        total_srx_processed_overall = 0
        total_srx_with_meaningful_data = 0 
        
        print_section_header("Processing Keywords", "🔄")

        try:
            with tqdm(keywords_to_process, desc="🧬 Processing Keywords", unit="keyword", 
                     bar_format="{l_bar}{bar:30}{r_bar}{bar:-30b}", colour="green") as keyword_pbar:
                for keyword_idx, keyword in enumerate(keyword_pbar):
                    keyword_pbar.set_postfix_str(f"Current: {keyword[:20]}...")
                    keyword_start_time = time.time()
                    
                    print(f"\n🔍 Keyword {keyword_idx+1}/{len(keywords_to_process)}: '{keyword}'")
                    animated_loading(f"Searching NCBI SRA for '{keyword}'", 1.0)

                    sra_experiment_ids_all = entrez_client.get_sra_experiment_ids_from_runinfo_file(keyword)

                    if not sra_experiment_ids_all:
                        print_warning(f"No SRA experiments found for '{keyword}'")
                        placeholder_record = {col: "N/A" for col in FINAL_OUTPUT_COLUMNS}
                        placeholder_record["original_keyword"] = keyword
                        placeholder_record["sra_experiment_id"] = "NO_SRA_IDS_FOUND_FOR_KEYWORD"
                        placeholder_record["scientific_sample_summary"] = "No SRA Experiment IDs were found for this keyword."
                        csv_writer.write_batch([placeholder_record])
                        duration = time.time() - keyword_start_time
                        print_info(f"⏱️ Completed '{keyword}' in {duration:.2f}s (0 SRXs)")
                        continue

                    print_success(f"🎯 Found {len(sra_experiment_ids_all)} SRA experiments!")
                    print_info(f"🔧 Processing with {args.max_workers} {'worker' if args.max_workers == 1 else 'workers'}")
                    
                    batch_of_records_for_csv = [] 

                    with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_workers) as executor:
                        future_to_srx = {
                            # _process_single_srx now uses INITIAL_OUTPUT_COLUMNS for its internal structure
                            executor.submit(_process_single_srx, srx_id, keyword, INITIAL_OUTPUT_COLUMNS, llm_processor, entrez_client, args.save_xml_dir, args.save_geo_dir, temp_geo_download_dir): srx_id
                            for srx_id in sra_experiment_ids_all
                        }
                        
                        # Enhanced progress tracking
                        with tqdm(concurrent.futures.as_completed(future_to_srx), 
                                total=len(sra_experiment_ids_all), 
                                desc=f"🧮 Processing {keyword[:15]}", 
                                unit="SRX", 
                                leave=False,
                                bar_format="{l_bar}{bar:25}{r_bar}",
                                colour="blue") as srx_pbar:
                            
                            for future in srx_pbar:
                                srx_id_completed = future_to_srx[future]
                                try:
                                    current_record = future.result()
                                    total_srx_processed_overall += 1
                                    
                                    # Check if record has meaningful data
                                    meaningful_fields_check = [ 
                                        "gse_accession", "gsm_accession", "experiment_title", "species",
                                        "sequencing_technique", "sample_type", "cell_line_name",
                                        "tissue_type", "tissue_source_details", "disease_description",
                                        "sample_treatment_protocol", "scientific_sample_summary"
                                    ]
                                    is_meaningful = any(
                                        str(current_record.get(k, "N/A")).strip().lower() not in ["n/a", "na", "none", "", "unknown"] and 
                                        not any(err_token in str(current_record.get(k, "")).lower() for err_token in ["failed", "error", "no sra ids found", "cannot generate summary"]) 
                                        for k in meaningful_fields_check
                                    )
                                    if is_meaningful: 
                                        total_srx_with_meaningful_data += 1
                                        srx_pbar.set_postfix_str(f"✅ {total_srx_with_meaningful_data} meaningful")
                                    else:
                                        srx_pbar.set_postfix_str(f"📊 {total_srx_processed_overall} processed")

                                    batch_of_records_for_csv.append(current_record)
                                    if len(batch_of_records_for_csv) >= BATCH_SIZE_LLM:
                                        csv_writer.write_batch(batch_of_records_for_csv)
                                        batch_of_records_for_csv = []
                                        
                                except Exception as exc: 
                                    tqdm.write(f"💥 Error processing {srx_id_completed}: {str(exc)[:100]}", file=sys.stderr)
                                    failure_record = {col: "N/A" for col in FINAL_OUTPUT_COLUMNS}
                                    failure_record["original_keyword"] = keyword
                                    failure_record["sra_experiment_id"] = srx_id_completed
                                    failure_record["experiment_title"] = f"PROCESSING_ERROR: {str(exc)[:100]}"
                                    failure_record["scientific_sample_summary"] = f"Processing error: {str(exc)[:100]}"
                                    batch_of_records_for_csv.append(failure_record)
                                    if len(batch_of_records_for_csv) >= BATCH_SIZE_LLM: 
                                         csv_writer.write_batch(batch_of_records_for_csv)
                                         batch_of_records_for_csv = []
                                finally:
                                    time.sleep(0.01)

                    if batch_of_records_for_csv:
                        print_info(f"💾 Writing final batch of {len(batch_of_records_for_csv)} records")
                        csv_writer.write_batch(batch_of_records_for_csv)

                    duration = time.time() - keyword_start_time
                    print_success(f"✅ Completed '{keyword}' in {duration:.2f}s ({len(sra_experiment_ids_all)} SRXs)")
                    
        except KeyboardInterrupt:
            print_warning("\n⏹️ User interrupted processing - shutting down gracefully...")
        finally:
            if 'csv_writer' in locals() and csv_writer: 
                csv_writer.close_writer()
            processing_duration = time.time() - phase1_start_time
            
            print_section_header("Processing Summary", "📊")
            print_success(f"⏱️ Total processing time: {processing_duration:.2f}s ({processing_duration/60:.2f}m)")
            print_success(f"🧮 Total SRA experiments processed: {total_srx_processed_overall}")
            print_success(f"✨ Experiments with meaningful metadata: {total_srx_with_meaningful_data}")
            print_success(f"💾 Results saved to: {args.output_csv_path}")

    # Cleanup and final summary
    try:
        temp_geo_download_dir_obj.cleanup()
        print_info("🧹 Cleaned up temporary files")
    except Exception as e_cleanup:
        print_warning(f"Could not cleanup temp directory: {e_cleanup}")

    overall_script_duration = time.time() - overall_script_start_time
    
    print_section_header("Mission Complete!", "🎉")
    print_success(f"🕐 Total execution time: {overall_script_duration:.2f}s ({overall_script_duration/60:.2f}m)")
    print_success(f"📁 Final results: {args.output_csv_path}")
    print_success(f"🔬 Debug outputs: phase1_json_outputs/ directory")
    
    # Fun completion message
    completion_messages = [
        "🧬 Genomic data mining mission accomplished!",
        "🔬 Scientific metadata extraction complete!",
        "🤖 AI-powered analysis pipeline finished!",
        "📊 Data processing mission successful!",
        "🧮 Computational biology task completed!"
    ]
    print(f"\n{random.choice(completion_messages)}")
    print("🚀 Ready for the next scientific adventure!")


if __name__ == "__main__":
    main()
