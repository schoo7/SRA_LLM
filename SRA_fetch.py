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

# --- Configuration ---
OLLAMA_MODEL_NAME_DEFAULT = "gemma3:12b-it-qat"
OLLAMA_BASE_URL_DEFAULT = "http://localhost:11434"
RETRY_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 5
BATCH_SIZE_LLM = 3
MAX_PARALLEL_LLM_WORKERS = 4

ENTREZ_LONG_TIMEOUT_SECONDS = 3600
ENTREZ_SHORT_TIMEOUT_SECONDS = 300

# --- Column Definitions ---
# These are the columns for the final CSV output.
# The "Metadata Synthesis" LLM is prompted to provide information for these.
INITIAL_OUTPUT_COLUMNS = [
    "original_keyword", "sra_experiment_id", "gse_accession", "gsm_accession",
    "experiment_title", "species", "sequencing_technique", "sample_type",
    "cell_line_name", "tissue_type", "tissue_source_details",
    "disease_description",
    "sample_treatment_protocol", "clinical_sample_identifier",
    "library_source", "instrument_model",
    "is_chipseq_related_experiment", "chipseq_antibody_target",
    "chipseq_control_description",
    "chipseq_igg_control_present", "chipseq_input_control_present",
    "chipseq_nfcore_summary_lines",
    "scientific_sample_summary"
]
# Since Phase 2 is removed, FINAL_OUTPUT_COLUMNS is the same as INITIAL_OUTPUT_COLUMNS
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
        print("DEBUG: EntrezClient initialized.")

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
    """Handles LLM initialization and various metadata processing tasks using an LLM."""
    def __init__(self, model_name: str = OLLAMA_MODEL_NAME_DEFAULT, base_url: str = OLLAMA_BASE_URL_DEFAULT,
                 retry_attempts: int = RETRY_ATTEMPTS, retry_delay: int = RETRY_DELAY_SECONDS):
        self.model_name = model_name
        self.base_url = base_url
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self.llm = self._get_llm_instance()
        self.geo_accessions_extraction_prompt = self._get_geo_accessions_extraction_prompt()
        self.scientific_summary_prompt = self._get_scientific_summary_prompt()
        self.metadata_synthesis_prompt = self._get_metadata_synthesis_prompt()
        print(f"DEBUG: LLMProcessor initialized with model='{self.model_name}', base_url='{self.base_url}'")

    def _get_llm_instance(self) -> Optional[ChatOllama]:
        """Initializes and returns a ChatOllama instance."""
        print(f"DEBUG: LLM: Attempting to connect to Ollama model '{self.model_name}' at '{self.base_url}'")
        try:
            llm = ChatOllama(
                model=self.model_name,
                base_url=self.base_url,
                temperature=0.05, 
                request_timeout=120.0 
            )
            llm.invoke("Test: Are you operational? Respond with OK.")
            print(f"INFO: LLM: Successfully connected to Ollama model '{self.model_name}' at '{self.base_url}'", file=sys.stderr)
            return llm
        except Exception as e:
            print(f"ERROR: LLM: Failed to connect to Ollama model '{self.model_name}'. Error: {e}", file=sys.stderr)
            print(f"ERROR: LLM: Please ensure Ollama is running and the model is available/downloaded (e.g., 'ollama pull {self.model_name}').", file=sys.stderr)
            return None

    def _get_geo_accessions_extraction_prompt(self) -> ChatPromptTemplate:
        """Defines the prompt for extracting GSE and GSM accession numbers from SRA XML."""
        system_message = """
You are an AI assistant specialized in identifying GEO Series (GSE) and GEO Sample (GSM) accession numbers from SRA Experiment XML.
Your task is to find the primary GSE accession for the overall study and the specific GSM accession linked to this SRA experiment.
A GSE accession starts with "GSE" (e.g., "GSE12345"). A GSM accession starts with "GSM" (e.g., "GSM123456").
Look for GSE in <STUDY_REF accession="GSE..."/>, or <IDENTIFIERS> with db="GEO".
Look for GSM in <EXPERIMENT alias="GSM..."/>, <SAMPLE_DESCRIPTOR><EXTERNAL_ID namespace="GEO">GSM...</EXTERNAL_ID>, or in the <TITLE> of the experiment.
Respond with a JSON object containing "gse" and "gsm" keys.
Example: {{{{"gse": "GSE12345", "gsm": "GSM123456"}}}}
If a value is not found, use "N/A" for that key.
If multiple GSMs seem relevant to the SRX, pick the most direct one (e.g., from EXPERIMENT alias or SAMPLE_DESCRIPTOR).
Do not include any other text, explanations, or markdown formatting outside the JSON object. Your entire response must be only the JSON object.
"""
        human_template = """SRA Experiment XML:
```xml
{sra_experiment_xml}
```
GEO Accessions JSON:"""
        return ChatPromptTemplate.from_messages([("system", system_message), ("human", human_template)])

    def _get_scientific_summary_prompt(self) -> ChatPromptTemplate:
        """Defines the prompt for generating a scientific summary of a sample."""
        system_message = """
You are an AI assistant acting as a biomedical data scientist specializing in next-generation sequencing (NGS) metadata extraction. Your task is to generate a concise scientific summary (2-4 sentences) of a given sample based on the provided SRA Experiment XML and associated GEO data.  METADATA STRUCTURE GUIDANCE: - In SRA XML: Look for key information within these tags:   * <SAMPLE_ATTRIBUTES> and nested <SAMPLE_ATTRIBUTE> tags contain critical sample metadata   * <EXPERIMENT> tags contain sequencing platform and strategy details   * <LIBRARY_STRATEGY>, <LIBRARY_SOURCE>, <LIBRARY_SELECTION> tags indicate sequencing approach   * <PLATFORM> and nested tags provide sequencing instrument information   * <STUDY> and <STUDY_TITLE> may provide experimental context   * <SAMPLE> and <TAXON_ID> tags identify the organism  - In GEO data: Look for these elements:   * "Sample_title" often contains concise sample descriptions   * "Sample_characteristics_ch1" usually lists key attributes like tissue type, cell line, treatment   * "Sample_treatment_protocol_ch1" details treatments or conditions   * "Sample_extract_protocol_ch1" may contain preparation details   * "Sample_source_name_ch1" often indicates tissue or cell source   * "Sample_description" may provide experimental context  LOGICAL INFERENCE STRATEGY: When information is not explicitly stated, use logical inference across all available metadata fields: - Cross-reference between SRA and GEO data for the same sample - Use common abbreviations and nomenclature in the field to recognize cell lines and experimental conditions - Infer organism from cell line names (e.g., HEK293 → human, MEF → mouse) - Deduce sample type from contextual information across multiple fields - Consider information in titles, abstracts, and protocols to infer experimental context - Use standard naming conventions to recognize common treatments (e.g., "Dox" → doxycycline) - Look for patterns across multiple samples in the same study when visible  Extract and summarize the following key aspects:  1. Organism/Species:     - Look for <TAXON_ID> or <SCIENTIFIC_NAME> in SRA or organism/species fields in GEO    - If not explicitly stated, infer from cell line origin (e.g., MCF7 → Homo sapiens, 3T3 → Mus musculus)    - Check for organism-specific gene names or markers mentioned in descriptions  2. Sample Type:     - Identify if it's a cell line, primary cells, tissue, etc.    - For cell lines: Cross-reference common cell line names/abbreviations (e.g., HepG2, K562, A549)    - Look for contextual clues in sample titles, descriptions, and protocols    - Check for terms indicating primary vs. immortalized cells, patient-derived vs. established lines  3. Key Treatments or Experimental Conditions:    - Look beyond specific treatment fields to sample names, titles, and descriptions    - Connect fragmented information across multiple fields (e.g., drug name in one field, concentration in another)    - Recognize standard experimental paradigms (e.g., control vs. treatment, time course, dose response)    - Identify genetic modifications from gene names and techniques mentioned  4. Sequencing Strategy:    - Primary source: <LIBRARY_STRATEGY> tag, but also check titles and protocols    - Recognize sequencing types from context even when not explicitly labeled    - Look for target molecules or antibodies to determine specific approaches (e.g., ChIP target)    - Infer from library preparation methods when direct labeling is absent  5. Brief Experimental Context/Goal:    - Synthesize information from study title, sample descriptions, and experimental design    - Consider relationships between multiple samples if visible    - Identify common research paradigms and experimental frameworks  The summary should be written in clear, scientific prose. When information cannot be determined even after logical inference, state that it's 'not specified' or 'unclear'. If the data provided is insufficient for generating a meaningful summary, respond with "N/A".
"""
        human_template = """
SRA Experiment ID: {sra_experiment_id}
Original Search Keyword: {original_keyword}

SRA Experiment XML:
```xml
{sra_experiment_xml}
```

GEO Data Summary (if available, otherwise "N/A"):
```text
{geo_data_summary}
```
Concise Scientific Summary:"""
        return ChatPromptTemplate.from_messages([("system", system_message), ("human", human_template)])

    def _get_metadata_synthesis_prompt(self) -> ChatPromptTemplate:
        """Defines the prompt for synthesizing structured metadata."""
        system_message = """
You are an AI assistant acting as a meticulous biomedical data curator with expertise in molecular biology and next-generation sequencing. Your task is to analyze the provided 'Scientific Sample Summary', 'SRA Experiment XML', and 'GEO Data Summary' to extract comprehensive metadata about biological samples and sequencing experiments. PRIMARY OBJECTIVE Extract information from all provided sources and populate a comprehensive JSON object with specified fields. Apply domain knowledge and logical inference to ensure accuracy and completeness. CRITICAL APPROACH INSTRUCTIONS  INTEGRATE ALL DATA SOURCES: Cross-reference information between Scientific Sample Summary, SRA XML, and GEO Data. Look for consistency and complementarity across sources. APPLY DOMAIN KNOWLEDGE: Use your understanding of:  Common cell line nomenclature (e.g., HeLa → human cervical cancer, 4T1 → mouse mammary tumor) Standard sequencing workflows and their applications Typical experimental designs in molecular biology Biomedical terminology and abbreviations   EMPLOY LOGICAL INFERENCE STRATEGIES:  If cell line is mentioned (e.g., "K562"), infer species (Homo sapiens) If species-specific gene names appear (e.g., "mTOR knockout"), infer species If ChIP-seq is mentioned without explicit antibody target, look for histone marks or transcription factors in descriptions Connect fragmented information across fields (e.g., treatment mentioned in title, concentration in protocol) Recognize experimental paradigms (e.g., if "tumor vs. normal" appears, sample types can be inferred) Examine patterns in sample naming conventions (e.g., "KO" likely indicates knockout) Use indirect references (e.g., "LPS stimulation" implies treatment with lipopolysaccharide)   MAINTAIN SEMANTIC CONSISTENCY: Ensure your field values align with standard conventions in biological research. COMPLETENESS IS ESSENTIAL: Extract information for ALL fields in the TARGET JSON, using "N/A" only when information cannot be reasonably inferred after thorough analysis.  RESPONSE FORMAT Your entire response MUST be a single, valid JSON object. DO NOT include any text outside the JSON structure - no introduction, explanation, or conclusion.

Your response must be a JSON object. The JSON object should include keys such as "experiment_title", "species", "sequencing_technique", "sample_type", "cell_line_name", "tissue_type", "tissue_source_details", "disease_description", "sample_treatment_protocol", "clinical_sample_identifier", "library_source", "instrument_model", "is_chipseq_related_experiment", "chipseq_antibody_target", "chipseq_control_description", "chipseq_igg_control_present", "chipseq_input_control_present", and "chipseq_nfcore_summary_lines". Refer to the FIELD-SPECIFIC EXTRACTION GUIDELINES for details on each field.

FIELD-SPECIFIC EXTRACTION GUIDELINES experiment_title  Primary sources: GEO series title, SRA study title, experiment title Secondary sources: Sample titles, descriptions that indicate overall purpose Inference strategy: Extract the most comprehensive title that captures the experimental purpose Output format: Complete sentence or phrase describing the experiment (e.g., "Transcriptome analysis of MCF7 cells under hypoxic conditions")  species  Primary sources: SRA ORGANISM/SCIENTIFIC_NAME, GEO organism_ch1 Secondary sources: Cell line names, gene nomenclature patterns, model organism references Inference strategy:  Cellular model systems → infer species (e.g., HeLa, MCF7, A549 → Homo sapiens) Species-specific gene naming (e.g., hTERT → human, mTOR knockout → mouse) Tissue sources with species context (e.g., "mouse embryonic fibroblasts")   Output format: Full scientific name (e.g., "Homo sapiens", "Mus musculus", "Drosophila melanogaster") Common examples: Human → "Homo sapiens", Mouse → "Mus musculus", Rat → "Rattus norvegicus"  sequencing_technique  Primary sources: SRA LIBRARY_STRATEGY, GEO library_strategy_ch1 Secondary sources: Titles, descriptions, protocols with technique references Inference strategy:  "transcriptome" or "mRNA" → likely "RNA-Seq" "single cell" + "transcriptome" → likely "scRNA-Seq" Mention of chromatin immunoprecipitation → "ChIP-Seq" References to chromatin accessibility → "ATAC-Seq" References to DNA methylation → "Bisulfite-Seq" or "RRBS" Whole genome references → "WGS" Exome references → "WES"   Valid values: RNA-Seq, scRNA-Seq, ChIP-Seq, ATAC-Seq, scATAC-Seq, Bisulfite-Seq, RRBS, WGS, WES, CUT&RUN, CUT&Tag, Targeted Sequencing, AMPLICON, CLONE, OTHER  sample_type  Primary sources: GEO source_name_ch1, characteristics_ch1 Secondary sources: Sample descriptions, experimental context Inference strategy:  References to established cell lines → "Cell Line" References to isolation from tissue without immortalization → "Primary Cells" References to tumor biopsies or cancer tissue → "Tissue: Tumor" References to healthy tissue adjacent to tumor → "Tissue: Normal Adjacent" References to tissue from healthy donors → "Tissue: Healthy Donor" References to disease models not involving cancer → "Tissue: Disease Model" References to 3D cultures derived from primary cells → "Organoid" References to human tumors grown in model organisms → "Xenograft"   Valid values: Cell Line, Primary Cells, Tissue: Tumor, Tissue: Normal Adjacent, Tissue: Healthy Donor, Tissue: Disease Model, Organoid, Xenograft, Environmental, Other  cell_line_name  Primary sources: GEO characteristics_ch1 "cell line:", SRA attributes for cell line Secondary sources: Sample titles, descriptions with cell line references Inference strategy:  Look for standard cell line nomenclature (e.g., HEK293, MCF-7, A549) Distinguish between generic cell types ("lymphocytes") and established cell lines Consider modifiers indicating cell line derivatives (e.g., "HEK293T")   Output format: Standard cell line name as used in literature When to use N/A: If sample_type is not "Cell Line"  tissue_type  Primary sources: GEO source_name_ch1, characteristics_ch1 'tissue' Secondary sources: Sample descriptions with tissue references Inference strategy:  Identify specific tissue anatomy (e.g., "Brain Cortex" rather than just "Brain") For cancer samples, specify the cancer type (e.g., "Lung Adenocarcinoma") For blood-derived samples, specify the cell population (e.g., "PBMC", "CD4+ T cells")   Output format: Specific tissue name or cell population When to use N/A: If sample_type is "Cell Line"  tissue_source_details  Primary sources: GEO characteristics related to tissue origin Secondary sources: Sample descriptions with contextual information Inference strategy:  Combine information about tissue source, disease state, and experimental context Include species context for animal models Include donor context for human samples (e.g., age, gender if available)   Output format: Descriptive phrase about tissue origin (e.g., "Patient Tumor Biopsy", "Mouse Model Normal Lung") When to use N/A: If sample_type is "Cell Line"  disease_description  Primary sources: GEO characteristics_ch1 'disease', 'grade', 'stage' Secondary sources: Sample titles, descriptions with disease references Inference strategy:  Include disease name and stage/grade when available For cancer, specify cancer type and stage/grade For model systems, indicate if it's a disease model Use "Healthy Control" or "Normal" for non-disease samples   Output format: Disease name with additional context when available  sample_treatment_protocol  Primary sources: GEO treatment_protocol_ch1, characteristics_ch1 'treatment' Secondary sources: Sample descriptions, titles with treatment references Inference strategy:  Identify ALL treatments applied, including:  Chemical compounds (with concentrations and durations) Biological agents (e.g., cytokines, growth factors) Genetic modifications (e.g., CRISPR, siRNA) Environmental conditions (e.g., hypoxia, starvation)   Look for control conditions (e.g., "Vehicle control", "Untreated") Connect fragmented information about the same treatment   Output format: Detailed description of treatments (e.g., "10μM Doxorubicin for 24h; transfected with TP53 siRNA") When to use specific values: "Untreated" or "Control" when explicitly stated as control; "Vehicle Only" when vehicle control is mentioned  clinical_sample_identifier  Primary sources: GEO characteristics with patient/donor IDs Secondary sources: Sample naming patterns indicative of patient coding Inference strategy: Look for anonymized identifiers for clinical samples Output format: ID as provided (e.g., "Patient P001", "TumorID-005") When to use N/A: For non-clinical samples or when no identifier is provided  library_source  Primary sources: SRA LIBRARY_SOURCE Secondary sources: Sequencing technique, experimental context Inference strategy:  RNA-Seq, scRNA-Seq → "TRANSCRIPTOMIC" WGS, WES, Targeted Sequencing → "GENOMIC" ChIP-Seq, ATAC-Seq, CUT&RUN → "EPIGENOMIC" Microbiome studies → "METAGENOMIC"   Valid values: TRANSCRIPTOMIC, GENOMIC, EPIGENOMIC, METAGENOMIC, OTHER  instrument_model  Primary sources: SRA INSTRUMENT_MODEL, GEO platform information Secondary sources: Methods sections with sequencing details Inference strategy: Extract full instrument name when available Output format: Complete instrument model name (e.g., "Illumina NovaSeq 6000", "PacBio Sequel II")  is_chipseq_related_experiment  Primary sources: sequencing_technique field Secondary sources: References to chromatin immunoprecipitation or similar techniques Inference strategy:  Answer "yes" if sequencing_technique is ChIP-Seq, CUT&RUN, CUT&Tag Look for references to antibody-based enrichment methods   Valid values: "yes", "no"  chipseq_antibody_target  Primary sources: GEO characteristics_ch1 'chip antibody', titles with target references Secondary sources: Sample descriptions with antibody information Inference strategy:  For histone marks, use standard nomenclature (e.g., "H3K27ac", "H3K4me3") For transcription factors, use gene symbols (e.g., "CTCF", "POLR2A") For tagged proteins, include tag information (e.g., "GFP-FOXO1")   Output format: Standard target nomenclature When to use N/A: If is_chipseq_related_experiment is "no"  chipseq_control_description  Primary sources: Sample descriptions indicating control status Secondary sources: Related samples in the same experiment Inference strategy:  Look for explicit mentions of control samples Consider relationships between samples in experimental design Check for standard ChIP-seq control terminology (IgG, Input)   Output format: Description of control relationship (e.g., "IgG control performed in parallel") When to use N/A: If is_chipseq_related_experiment is "no"  chipseq_igg_control_present  Primary sources: chipseq_control_description field Secondary sources: Sample descriptions with IgG references Inference strategy: Determine if IgG control is explicitly mentioned or implied Valid values: "yes", "no", "unknown" When to use N/A: If is_chipseq_related_experiment is "no"  chipseq_input_control_present  Primary sources: chipseq_control_description field Secondary sources: Sample descriptions with Input references Inference strategy: Determine if Input control is explicitly mentioned or implied Valid values: "yes", "no", "unknown" When to use N/A: If is_chipseq_related_experiment is "no"  chipseq_nfcore_summary_lines  Primary sources: Pipeline output information if available When to use N/A: Almost always "N/A" unless specific nf-core pipeline output is available  FINAL VERIFICATION Before submitting your response:  Ensure you've populated ALL fields in the TARGET JSON Verify logical consistency between related fields Confirm you've applied domain knowledge where direct information is missing Check that your JSON is properly formatted without syntax errors  Remember: Your ENTIRE response must be a single, valid JSON object.
"""
        human_template = """
Original Search Keyword: {original_keyword}
SRA Experiment ID: {sra_experiment_id}
GSE Accession (if known): {gse_accession}
GSM Accession (if known): {gsm_accession}

Scientific Sample Summary:
```text
{scientific_sample_summary}
```

SRA Experiment XML (snippets relevant to sample description, library, instrument, study design, attributes):
```xml
{sra_experiment_xml}
```

GEO Data Summary (key metadata from GEO SOFT file, including characteristics, treatment protocols, source names):
```text
{geo_data_summary}
```
Your JSON output:"""
        return ChatPromptTemplate.from_messages([("system", system_message), ("human", human_template)])

    def _run_llm_chain(self, prompt_template: ChatPromptTemplate, input_data: Dict[str, str], sra_id_for_log: str, purpose: str) -> Optional[str]:
        """
        Runs a given LLM chain with input data, handling retries and logging.
        Returns the LLM response string or None on failure.
        For GEO Accessions, returns a default JSON string on failure.
        """
        if not self.llm:
            tqdm.write(f"ERROR: LLM not initialized. Cannot run '{purpose}' chain for SRA ID: {sra_id_for_log}.", file=sys.stderr)
            if purpose == "GEO Accessions Extraction": return json.dumps({"gse": "N/A", "gsm": "N/A"}) # Specific fallback
            return None

        chain = prompt_template | self.llm | StrOutputParser()
        tqdm.write(f"DEBUG: LLM ({purpose}): Invoked for SRA ID: {sra_id_for_log}", file=sys.stderr)
        llm_call_start_time = time.time()

        for attempt in range(self.retry_attempts):
            tqdm.write(f"DEBUG: LLM ({purpose}): Attempt {attempt + 1}/{self.retry_attempts} for {sra_id_for_log}", file=sys.stderr)
            try:
                current_input_data = input_data.copy() 
                if purpose == "GEO Accessions Extraction":
                    current_input_data = {"sra_experiment_xml": input_data.get("sra_experiment_xml","")}

                response_text = chain.invoke(current_input_data).strip()
                duration = time.time() - llm_call_start_time
                tqdm.write(f"DEBUG: LLM ({purpose}) raw response for {sra_id_for_log} (Attempt {attempt+1}, Time: {duration:.2f}s):\n>>>>\n{response_text[:500]}...\n<<<<", file=sys.stderr)

                if purpose in ["GEO Accessions Extraction", "Metadata Synthesis"]:
                    json_str_candidate = None
                    fence_match = re.search(r"```json\s*([\{\[].*?[\]\}])\s*```", response_text, re.DOTALL | re.IGNORECASE)
                    if fence_match:
                        json_str_candidate = fence_match.group(1).strip()
                        tqdm.write(f"DEBUG: LLM ({purpose}): Found fenced JSON for {sra_id_for_log}.", file=sys.stderr)
                    else:
                        stripped_response = response_text.strip()
                        if (stripped_response.startswith('{') and stripped_response.endswith('}')) or \
                           (stripped_response.startswith('[') and stripped_response.endswith(']')):
                            json_str_candidate = stripped_response
                            tqdm.write(f"DEBUG: LLM ({purpose}): Assuming stripped response is JSON for {sra_id_for_log}.", file=sys.stderr)
                        else:
                            obj_match = re.search(r'(\{.*?\})', response_text, re.DOTALL)
                            arr_match = re.search(r'(\[.*?\])', response_text, re.DOTALL) 

                            if obj_match and arr_match:
                                if obj_match.start() < arr_match.start():
                                    json_str_candidate = obj_match.group(1).strip()
                                else:
                                    json_str_candidate = arr_match.group(1).strip()
                                tqdm.write(f"DEBUG: LLM ({purpose}): Fallback found obj and arr, chose one for {sra_id_for_log}.", file=sys.stderr)
                            elif obj_match:
                                json_str_candidate = obj_match.group(1).strip()
                                tqdm.write(f"DEBUG: LLM ({purpose}): Fallback found object for {sra_id_for_log}.", file=sys.stderr)
                            elif arr_match:
                                json_str_candidate = arr_match.group(1).strip()
                                tqdm.write(f"DEBUG: LLM ({purpose}): Fallback found array for {sra_id_for_log}.", file=sys.stderr)
                    
                    if json_str_candidate:
                        try:
                            parsed_json = json.loads(json_str_candidate)
                            
                            if purpose == "GEO Accessions Extraction" and isinstance(parsed_json, list):
                                temp_gse = "N/A"
                                temp_gsm = "N/A"
                                for item in parsed_json:
                                    if isinstance(item, dict):
                                        gse_in_item = str(item.get("gse", "N/A")).upper()
                                        gsm_in_item = str(item.get("gsm", "N/A")).upper()

                                        if gse_in_item.startswith("GSE"): temp_gse = gse_in_item
                                        if gsm_in_item.startswith("GSM"): temp_gsm = gsm_in_item
                                        
                                        item_accession = str(item.get("accession", "")).upper()
                                        item_label = str(item.get("label", "")).upper()

                                        if temp_gse == "N/A" and item_accession.startswith("GSE"): temp_gse = item.get("accession")
                                        if temp_gse == "N/A" and item_label.startswith("GSE"): temp_gse = item.get("label")
                                        
                                        if temp_gsm == "N/A" and item_accession.startswith("GSM"): temp_gsm = item.get("accession")
                                        if temp_gsm == "N/A" and item_label.startswith("GSM"): temp_gsm = item.get("label")
                                json_str_candidate = json.dumps({"gse": temp_gse, "gsm": temp_gsm})
                                json.loads(json_str_candidate) 
                                tqdm.write(f"INFO: LLM ({purpose}): Valid JSON (processed from list: gse='{temp_gse}', gsm='{temp_gsm}') found for {sra_id_for_log}.", file=sys.stderr)
                            
                            elif purpose == "Metadata Synthesis" and not isinstance(parsed_json, dict):
                                tqdm.write(f"WARNING: LLM ({purpose}): Returned JSON is not a dictionary as expected for {sra_id_for_log}. Type: {type(parsed_json)}", file=sys.stderr)
                                raise json.JSONDecodeError("Metadata synthesis did not return a JSON object.", json_str_candidate, 0)
                            
                            tqdm.write(f"INFO: LLM ({purpose}): Valid JSON successfully parsed for {sra_id_for_log}.", file=sys.stderr)
                            return json_str_candidate 

                        except json.JSONDecodeError as e:
                            tqdm.write(f"WARNING: LLM ({purpose}): JSON-like string found for {sra_id_for_log} but failed validation: {e}. Candidate: '{json_str_candidate[:200]}...'", file=sys.stderr)
                    else: 
                         tqdm.write(f"WARNING: LLM ({purpose}): No JSON-like structure found in response for {sra_id_for_log}. Response: '{response_text[:200]}...'", file=sys.stderr)

                elif purpose == "Scientific Summary Generation":
                    if response_text and response_text.strip().lower() not in ["n/a", "na", "none", ""]: 
                        tqdm.write(f"INFO: LLM ({purpose}): Text summary received for {sra_id_for_log}.", file=sys.stderr)
                        return response_text.strip() 
                    else: 
                        tqdm.write(f"INFO: LLM ({purpose}): Received empty or 'N/A' like summary for {sra_id_for_log}. Normalizing to 'N/A'.", file=sys.stderr)
                        return "N/A" 
            except Exception as e:
                duration = time.time() - llm_call_start_time
                tqdm.write(f"ERROR: LLM ({purpose}): Exception during chain invocation for {sra_id_for_log} (Attempt {attempt+1}, Time: {duration:.2f}s): {e}", file=sys.stderr)
                import traceback
                tqdm.write(traceback.format_exc(), file=sys.stderr)


            if attempt < self.retry_attempts - 1:
                time.sleep(self.retry_delay)
                llm_call_start_time = time.time() 

        tqdm.write(f"ERROR: LLM ({purpose}): Failed definitively for {sra_id_for_log} after {self.retry_attempts} retries.", file=sys.stderr)
        if purpose == "GEO Accessions Extraction": return json.dumps({"gse": "N/A", "gsm": "N/A"}) 
        if purpose == "Scientific Summary Generation": return "N/A" 
        return None 

    def extract_geo_accessions_from_sra_xml(self, sra_xml_content: str, sra_experiment_id: str) -> Dict[str, str]:
        """Uses LLM to extract GSE and GSM IDs from SRA XML. Falls back to regex if LLM fails."""
        accessions = {"gse": "N/A", "gsm": "N/A"} 

        llm_json_response_str = self._run_llm_chain(
            self.geo_accessions_extraction_prompt,
            {"sra_experiment_xml": sra_xml_content},
            sra_experiment_id,
            "GEO Accessions Extraction"
        )

        if llm_json_response_str:
            try:
                data = json.loads(llm_json_response_str) 
                gse_val = str(data.get("gse", "N/A")).strip().upper()
                accessions["gse"] = gse_val if gse_val and gse_val.startswith("GSE") else "N/A"
                gsm_val = str(data.get("gsm", "N/A")).strip().upper()
                accessions["gsm"] = gsm_val if gsm_val and gsm_val.startswith("GSM") else "N/A"
            except json.JSONDecodeError:
                tqdm.write(f"DEBUG: LLM GEO Accession Extraction for {sra_experiment_id} did not return valid JSON dict despite _run_llm_chain processing. Raw: '{llm_json_response_str}'", file=sys.stderr)
            except Exception as e:
                tqdm.write(f"ERROR: Unexpected error processing LLM response for GEO Accessions ({sra_experiment_id}): {e}. Raw: '{llm_json_response_str}'", file=sys.stderr)

        if accessions["gse"] == "N/A":
            gse_patterns = [
                r'<STUDY_REF[^>]*accession\s*=\s*"(GSE\d+)"', r'<EXPERIMENT[^>]*alias\s*=\s*"(GSE\d+)"',
                r'<SUBMISSION[^>]*alias\s*=\s*".*?(GSE\d+).*?"', r'<TITLE>[^<]*(GSE\d+)[^<]*</TITLE>',
                r'<EXTERNAL_ID[^>]*namespace\s*=\s*"GEO"[^>]*>(GSE\d+)</EXTERNAL_ID>',
                r'<IDENTIFIERS><PRIMARY_ID[^>]*db\s*=\s*"GEO"[^>]*>(GSE\d+)</PRIMARY_ID>'
            ]
            for pattern in gse_patterns:
                match = re.search(pattern, sra_xml_content, re.IGNORECASE)
                if match:
                    for group_val in match.groups(): 
                        if group_val and group_val.upper().startswith("GSE"):
                            accessions["gse"] = group_val.upper()
                            tqdm.write(f"DEBUG: Regex fallback found GSE: {accessions['gse']} for {sra_experiment_id}", file=sys.stderr)
                            break 
                if accessions["gse"] != "N/A": break 

        if accessions["gsm"] == "N/A":
            gsm_patterns = [
                r'<EXPERIMENT[^>]*alias\s*=\s*"(GSM\d+)"', r'<SAMPLE_DESCRIPTOR[^>]*accession\s*=\s*"(GSM\d+)"',
                r'<SAMPLE_DESCRIPTOR[^>]*>.*?<EXTERNAL_ID[^>]*namespace="GEO"[^>]*>(GSM\d+)</EXTERNAL_ID>', 
                r'<TITLE>(GSM\d+):.*?</TITLE>',
                r'<EXPERIMENT_ATTRIBUTE><TAG>GEO Accession</TAG><VALUE>(GSM\d+)</VALUE></EXPERIMENT_ATTRIBUTE>'
            ]
            for pattern in gsm_patterns:
                match = re.search(pattern, sra_xml_content, re.IGNORECASE | re.DOTALL) 
                if match:
                    for group_val in match.groups():
                        if group_val and group_val.upper().startswith("GSM"):
                            accessions["gsm"] = group_val.upper()
                            tqdm.write(f"DEBUG: Regex fallback found GSM: {accessions['gsm']} for {sra_experiment_id}", file=sys.stderr)
                            break
                if accessions["gsm"] != "N/A": break

        tqdm.write(f"DEBUG: Final Extracted GEO Accessions for {sra_experiment_id}: GSE='{accessions['gse']}', GSM='{accessions['gsm']}' (LLM/Regex)", file=sys.stderr)
        return accessions

    def generate_scientific_summary(self, sra_xml_content: str, geo_data_summary: str, original_keyword: str, sra_experiment_id: str) -> str:
        """Uses LLM to generate a scientific summary of the sample."""
        tqdm.write(f"INFO: LLM: Generating scientific summary for SRX: {sra_experiment_id}", file=sys.stderr)
        summary_text = self._run_llm_chain(
            self.scientific_summary_prompt,
            {
                "sra_experiment_xml": sra_xml_content if sra_xml_content else "N/A", 
                "geo_data_summary": geo_data_summary if geo_data_summary else "N/A", 
                "original_keyword": original_keyword,
                "sra_experiment_id": sra_experiment_id
            },
            sra_experiment_id,
            "Scientific Summary Generation"
        )
        return summary_text if summary_text else "N/A" 

    def synthesize_metadata(self, scientific_sample_summary: str, sra_xml_content_full: str, geo_data_summary: str,
                            original_keyword: str, sra_experiment_id: str, gse_accession: str, gsm_accession: str,
                            target_csv_columns: List[str]) -> Dict[str, Any]:
        """
        Calls the LLM for metadata synthesis and then maps its JSON output to the target_csv_columns.
        This function now acts as the "relocation agent" using the LLM's output.
        """
        # Initialize result with N/A for all target CSV columns
        result_data = {col: "N/A" for col in target_csv_columns}
        
        # Pre-populate fields that are directly passed or derived before mapping LLM output
        result_data["sra_experiment_id"] = sra_experiment_id
        result_data["original_keyword"] = original_keyword
        result_data["scientific_sample_summary"] = scientific_sample_summary
        result_data["gse_accession"] = gse_accession
        result_data["gsm_accession"] = gsm_accession

        # Prepare SRA XML snippet for the LLM
        sra_xml_snippet = sra_xml_content_full[:2000]
        if len(sra_xml_content_full) > 4000:
            sra_xml_snippet += "\n...\n[SRA XML SNIPPET END]\n...\n[SRA XML SNIPPET START - END PART]\n...\n" + sra_xml_content_full[-2000:]
        elif len(sra_xml_content_full) > 2000:
             sra_xml_snippet = sra_xml_content_full[:3000]

        # Call the LLM for the primary metadata synthesis
        llm_json_str = self._run_llm_chain(
            self.metadata_synthesis_prompt, # This prompt asks the LLM to generate a comprehensive JSON
            {
                "scientific_sample_summary": scientific_sample_summary,
                "sra_experiment_xml": sra_xml_snippet if sra_xml_snippet else "N/A",
                "geo_data_summary": geo_data_summary if geo_data_summary else "N/A",
                "original_keyword": original_keyword,
                "sra_experiment_id": sra_experiment_id,
                "gse_accession": gse_accession,
                "gsm_accession": gsm_accession
            },
            sra_experiment_id,
            "Metadata Synthesis"
        )

        phase1_llm_raw_json_output = {} # For saving the direct LLM JSON output

        if llm_json_str and llm_json_str.strip().lower() != "n/a":
            try:
                llm_output_data = json.loads(llm_json_str)
                phase1_llm_raw_json_output = llm_output_data # Save the successfully parsed JSON from LLM
                tqdm.write(f"INFO: LLM Synthesizer: Successfully parsed JSON response for {sra_experiment_id}.", file=sys.stderr)

                # --- Data Relocation/Mapping Logic ---
                # Map keys from LLM's JSON output to the target_csv_columns.
                # This map helps bridge differences if LLM uses slightly different key names
                # than those in INITIAL_OUTPUT_COLUMNS.
                # Format: "target_csv_column_name": ["llm_json_key1", "llm_json_key2_if_different_name"]
                key_map_to_llm_output = {
                    "experiment_title": ["experiment_title", "study_title"], # LLM might use either
                    "species": ["species", "organism"],
                    "sequencing_technique": ["sequencing_technique", "sequencing_type"],
                    "sample_type": ["sample_type"], # Assuming LLM provides this as per its detailed prompt
                    "cell_line_name": ["cell_line_name", "cell_line"],
                    "tissue_type": ["tissue_type", "tumor_type"], # tumor_type from user example
                    "tissue_source_details": ["tissue_source_details"],
                    "disease_description": ["disease_description", "tumor_type"], # tumor_type can also inform disease
                    "sample_treatment_protocol": ["sample_treatment_protocol", "treatment"],
                    "clinical_sample_identifier": ["clinical_sample_identifier"],
                    "library_source": ["library_source"],
                    "instrument_model": ["instrument_model", "sequencing_platform"],
                    "is_chipseq_related_experiment": ["is_chipseq_related_experiment"],
                    "chipseq_antibody_target": ["chipseq_antibody_target"],
                    "chipseq_control_description": ["chipseq_control_description"],
                    "chipseq_igg_control_present": ["chipseq_igg_control_present"],
                    "chipseq_input_control_present": ["chipseq_input_control_present"],
                    "chipseq_nfcore_summary_lines": ["chipseq_nfcore_summary_lines"]
                }

                for target_col in target_csv_columns:
                    # Skip if already pre-filled by exact match earlier (srx_id, keyword, summary, gse, gsm)
                    if result_data.get(target_col) != "N/A" and target_col in [
                        "sra_experiment_id", "original_keyword", "scientific_sample_summary", 
                        "gse_accession", "gsm_accession"
                    ]:
                        continue

                    llm_keys_to_try = key_map_to_llm_output.get(target_col, [target_col]) # Default to direct match

                    found_value_for_col = False
                    for llm_key in llm_keys_to_try:
                        if llm_key in llm_output_data:
                            value = llm_output_data[llm_key]
                            if value is None or str(value).strip().lower() in ["", "null", "n/a", "na", "none", "unknown", "not specified", "unclear"]:
                                result_data[target_col] = "N/A"
                            elif isinstance(value, list) and target_col == "sample_treatment_protocol":
                                result_data[target_col] = "; ".join(map(str, value)) # Join list for treatment
                            elif isinstance(value, list): # For other list types, convert to string
                                result_data[target_col] = ", ".join(map(str, value))
                            else:
                                result_data[target_col] = str(value).strip()
                            found_value_for_col = True
                            break # Found value for this target_col using one of the llm_keys
                    
                    if not found_value_for_col:
                         result_data[target_col] = "N/A" # Ensure it's N/A if no mapping worked

            except json.JSONDecodeError as e:
                tqdm.write(f"ERROR: LLM Synthesizer (Relocation): JSON parsing failed for {sra_experiment_id}: {e}. Raw response: {llm_json_str[:200]}...", file=sys.stderr)
                phase1_llm_raw_json_output = {"error": "JSON parsing failed in relocation", "raw_response": llm_json_str}
            except Exception as e_map:
                tqdm.write(f"ERROR: LLM Synthesizer (Relocation): An unexpected error occurred while mapping LLM output for {sra_experiment_id}: {e_map}", file=sys.stderr)
                phase1_llm_raw_json_output = {"error": f"Unexpected mapping error in relocation: {str(e_map)}"}
        else:
            tqdm.write(f"WARNING: LLM Synthesizer (Relocation): No usable JSON data returned from LLM for {sra_experiment_id}. Summary was: '{scientific_sample_summary[:100]}...'", file=sys.stderr)
            phase1_llm_raw_json_output = {"error": "No usable JSON data returned from LLM for synthesis", "summary_provided": scientific_sample_summary}
        
        # Save the raw LLM JSON output for this SRX ID from the "Metadata Synthesis" call
        phase1_output_dir = "phase1_json_outputs"
        try:
            os.makedirs(phase1_output_dir, exist_ok=True)
            phase1_json_filename = os.path.join(phase1_output_dir, f"{sra_experiment_id}_phase1_synthesis_LLM_output.json")
            with open(phase1_json_filename, 'w', encoding='utf-8') as f_json_out:
                json.dump(phase1_llm_raw_json_output, f_json_out, indent=2) # Save the content of llm_output_data
            tqdm.write(f"INFO: Saved Phase 1 LLM synthesis raw JSON output for {sra_experiment_id} to {phase1_json_filename}", file=sys.stderr)
        except Exception as e_save_json:
            tqdm.write(f"ERROR: Could not save Phase 1 raw JSON output for {sra_experiment_id}: {e_save_json}", file=sys.stderr)

        tqdm.write(f"DEBUG: Relocated data for {sra_experiment_id} (sample): title='{result_data.get('experiment_title', 'N/A')[:30]}...', species='{result_data.get('species', 'N/A')}'", file=sys.stderr)
        return result_data


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
    tqdm.write(f"    Thread processing SRX ID: '{srx_id}' (Original Keyword: '{keyword}')", file=sys.stderr)
    current_record = {col: "N/A" for col in output_columns} # output_columns is INITIAL_OUTPUT_COLUMNS
    current_record["original_keyword"] = keyword
    current_record["sra_experiment_id"] = srx_id

    sra_xml_content = entrez_client.efetch_sra_experiment_xml(srx_id, save_xml_dir)
    if not sra_xml_content:
        tqdm.write(f"WARNING: Failed to fetch SRA XML for {srx_id}. Most fields will be N/A.", file=sys.stderr)
        current_record["experiment_title"] = "SRA_XML_FETCH_FAILED" 
        current_record["scientific_sample_summary"] = "SRA XML fetch failed, cannot generate summary or extract further details."
        # Save the empty/error record to the phase1_json_outputs for consistency
        phase1_output_dir = "phase1_json_outputs"
        try:
            os.makedirs(phase1_output_dir, exist_ok=True)
            phase1_json_filename = os.path.join(phase1_output_dir, f"{srx_id}_phase1_synthesis_LLM_output.json")
            with open(phase1_json_filename, 'w', encoding='utf-8') as f_json_out:
                json.dump({"error": "SRA XML Fetch Failed", "srx_id": srx_id}, f_json_out, indent=2)
        except Exception: pass # Ignore if saving error record fails
        return current_record 

    geo_accessions = llm_processor.extract_geo_accessions_from_sra_xml(sra_xml_content, srx_id)
    gse_id = geo_accessions.get("gse", "N/A")
    gsm_id = geo_accessions.get("gsm", "N/A")
    # These will be passed to synthesize_metadata and pre-filled into result_data

    geo_data_summary = "N/A" 
    geo_id_to_fetch = gsm_id if gsm_id != "N/A" else (gse_id if gse_id != "N/A" else None)
    geo_type_fetched = "GSM" if gsm_id != "N/A" else ("GSE" if gse_id != "N/A" else None)

    if geo_id_to_fetch and geo_type_fetched:
        tqdm.write(f"    Identified {geo_type_fetched} ID: {geo_id_to_fetch} for SRX: {srx_id}. Attempting to fetch GEO data.", file=sys.stderr)
        geo_object = None
        try:
            os.makedirs(temp_geo_dir, exist_ok=True) 
            geo_fetch_start = time.time()
            geo_object = GEOparse.get_GEO(geo=geo_id_to_fetch, destdir=temp_geo_dir, silent=True, annotate_gpl=False, include_data=False)
            geo_fetch_duration = time.time() - geo_fetch_start
            tqdm.write(f"    GEOparse.get_GEO for {geo_id_to_fetch} completed in {geo_fetch_duration:.2f}s.", file=sys.stderr)

            if geo_object:
                tqdm.write(f"    Successfully fetched and parsed GEO data for {geo_id_to_fetch} (SRX: {srx_id}).", file=sys.stderr)
                geo_summary_parts = [f"--- {geo_type_fetched} Metadata for {geo_id_to_fetch} ---"]
                def build_geo_summary_from_dict(metadata_dict, prefix=""):
                    # ... (implementation as before)
                    parts = []
                    for key, value in metadata_dict.items():
                        if isinstance(value, list):
                            if len(value) > 5: 
                                val_str = f"{'; '.join(map(str,value[:3]))}... (Total items: {len(value)})"
                            else:
                                val_str = "; ".join(map(str,value))
                        else:
                            val_str = str(value)
                        parts.append(f"  {prefix}{key}: {val_str[:300]}") 
                    return parts

                if geo_type_fetched == "GSM" and hasattr(geo_object, 'metadata'):
                    geo_summary_parts.extend(build_geo_summary_from_dict(geo_object.metadata, "GSM."))
                    if gse_id == "N/A": # Use local gse_id which was from LLM/Regex on SRA XML
                        parent_gse_ids = geo_object.metadata.get('series_id', [])
                        if parent_gse_ids and str(parent_gse_ids[0]).upper().startswith("GSE"):
                            gse_id = str(parent_gse_ids[0]).upper() # Update gse_id for synthesize_metadata
                            tqdm.write(f"    Updated GSE for {srx_id} to {gse_id} from GSM's series_id.", file=sys.stderr)
                elif geo_type_fetched == "GSE" and hasattr(geo_object, 'metadata'):
                    geo_summary_parts.extend(build_geo_summary_from_dict(geo_object.metadata, "GSE."))
                    target_gsm_to_summarize = gsm_id 
                    if target_gsm_to_summarize != "N/A" and hasattr(geo_object, 'gsms') and target_gsm_to_summarize in geo_object.gsms:
                        # ... (as before)
                        gsm_data_obj = geo_object.gsms[target_gsm_to_summarize]
                        if hasattr(gsm_data_obj, 'metadata'):
                             geo_summary_parts.append(f"\n  --- Specific GSM ({target_gsm_to_summarize}) Metadata from GSE ({gse_id}) ---")
                             geo_summary_parts.extend(build_geo_summary_from_dict(gsm_data_obj.metadata, f"  GSM.{target_gsm_to_summarize}."))
                    elif target_gsm_to_summarize == "N/A" and hasattr(geo_object, 'gsms') and len(geo_object.gsms) == 1:
                        # ... (as before, update local gsm_id if changed)
                        single_gsm_key = list(geo_object.gsms.keys())[0]
                        tqdm.write(f"    GSE {gse_id} has only one sample: {single_gsm_key}. Using its metadata for summary.", file=sys.stderr)
                        gsm_data_obj = geo_object.gsms[single_gsm_key]
                        if hasattr(gsm_data_obj, 'metadata'):
                            geo_summary_parts.append(f"\n  --- Single GSM ({single_gsm_key}) Metadata from GSE ({gse_id}) ---")
                            geo_summary_parts.extend(build_geo_summary_from_dict(gsm_data_obj.metadata, f"  GSM.{single_gsm_key}."))
                            gsm_id = single_gsm_key # Update gsm_id for synthesize_metadata
                geo_data_summary = "\n".join(geo_summary_parts)
                if save_geo_dir: # ... (GEO saving logic as before)
                    try:
                        os.makedirs(save_geo_dir, exist_ok=True)
                        downloaded_soft_file_gz = os.path.join(temp_geo_dir, f"{geo_id_to_fetch}.soft.gz")
                        downloaded_soft_file_plain = os.path.join(temp_geo_dir, f"{geo_id_to_fetch}.soft")
                        actual_downloaded_file = None
                        if os.path.exists(downloaded_soft_file_gz): actual_downloaded_file = downloaded_soft_file_gz
                        elif os.path.exists(downloaded_soft_file_plain): actual_downloaded_file = downloaded_soft_file_plain

                        if actual_downloaded_file:
                            target_soft_file = os.path.join(save_geo_dir, os.path.basename(actual_downloaded_file))
                            if os.path.abspath(actual_downloaded_file) != os.path.abspath(target_soft_file):
                                os.rename(actual_downloaded_file, target_soft_file)
                                tqdm.write(f"DEBUG: Moved GEO SOFT file for {geo_id_to_fetch} to {target_soft_file}", file=sys.stderr)
                    except Exception as e_save_geo:
                        tqdm.write(f"ERROR: Could not save/move GEO SOFT file for {geo_id_to_fetch}: {e_save_geo}", file=sys.stderr)
            else: 
                tqdm.write(f"WARNING: GEOparse.get_GEO returned None for {geo_id_to_fetch} (SRX: {srx_id}). No GEO data to process or summarize.", file=sys.stderr)
                geo_data_summary = f"Failed to fetch/parse GEO data for {geo_id_to_fetch} using GEOparse (returned None)."
        except Exception as e_geo: 
            tqdm.write(f"ERROR: An exception occurred during GEO data fetching/parsing for {geo_id_to_fetch} (SRX: {srx_id}): {e_geo}", file=sys.stderr)
            geo_data_summary = f"Error during GEO data fetching/parsing for {geo_id_to_fetch}: {str(e_geo)[:150]}"
    else:
        tqdm.write(f"    No valid GSE or GSM ID found or derived for SRX: {srx_id}. Proceeding with SRA XML data only for summary and synthesis.", file=sys.stderr)
        geo_data_summary = "No GEO ID linked or found from SRA XML to fetch GEO data."

    scientific_sample_summary_text = llm_processor.generate_scientific_summary(
        sra_xml_content, geo_data_summary, keyword, srx_id
    )
    # The scientific_sample_summary will be placed into current_record by synthesize_metadata

    # Call synthesize_metadata, which now handles the LLM call AND the data relocation
    # It uses output_columns (which is INITIAL_OUTPUT_COLUMNS) as the target structure.
    relocated_data_dict = llm_processor.synthesize_metadata(
        scientific_sample_summary_text, sra_xml_content, geo_data_summary,
        keyword, srx_id, gse_id, gsm_id, 
        output_columns # This is INITIAL_OUTPUT_COLUMNS
    )
    # The relocated_data_dict should already have all keys from output_columns,
    # filled from LLM or with N/A.
    current_record = relocated_data_dict

    return current_record


def main():
    overall_script_start_time = time.time()
    print(f"--- Script Execution Started at {time.ctime(overall_script_start_time)} ---")

    parser = argparse.ArgumentParser(description="Fetch SRA/GEO metadata, generate summaries, and extract structured data using LLMs.")
    parser.add_argument("input_csv_path", help="Path to the input CSV file containing keywords.")
    parser.add_argument("output_csv_path", help="Path to the output CSV file where results will be saved.")
    parser.add_argument("--keyword_column", default=None, type=str, help="Name of the column in the input CSV that contains keywords. If not specified, the first column is used.")
    # --skip_initial_fetch might not make sense if Phase 2 is removed, or needs redefinition.
    # For now, let's assume it means skip the entire processing if the output file exists and is non-empty,
    # or just remove it if it's no longer logical.
    # Given the user wants to replace Phase 2, let's simplify and remove --skip_initial_fetch for now,
    # as the script will always run Phase 1.
    # parser.add_argument("--skip_initial_fetch", action="store_true", help="If set, skips Entrez fetching and initial LLM extraction/synthesis (Phase 1). Only runs post-processing (Phase 2) on an existing output_csv_path.")
    parser.add_argument("--llm_model", default=OLLAMA_MODEL_NAME_DEFAULT, type=str, help=f"Name of the Ollama model to use (Default: {OLLAMA_MODEL_NAME_DEFAULT})")
    parser.add_argument("--llm_base_url", default=OLLAMA_BASE_URL_DEFAULT, type=str, help=f"Base URL for the Ollama API (Default: {OLLAMA_BASE_URL_DEFAULT})")
    parser.add_argument("--max_workers", type=int, default=MAX_PARALLEL_LLM_WORKERS, help=f"Number of parallel worker threads for processing SRA IDs (Default: {MAX_PARALLEL_LLM_WORKERS})")
    parser.add_argument("--save_xml_dir", type=str, default=None, help="Optional: Directory path to save fetched SRA XML files.")
    parser.add_argument("--save_geo_dir", type=str, default=None, help="Optional: Directory path to save fetched GEO SOFT files.")
    parser.add_argument("--debug_single_srx_id", type=str, default=None, help="For debugging: provide a single SRX ID to fetch and process. Requires --debug_single_keyword.")
    parser.add_argument("--debug_single_keyword", type=str, default="DEBUG_KEYWORD", help="Keyword associated with --debug_single_srx_id for context (Default: DEBUG_KEYWORD).")
    args = parser.parse_args()
    print(f"DEBUG: Parsed command-line arguments: {args}")

    if args.save_xml_dir:
        try: os.makedirs(args.save_xml_dir, exist_ok=True)
        except OSError as e: print(f"ERROR: Could not create XML save directory '{args.save_xml_dir}': {e}. XML files will not be saved.", file=sys.stderr); args.save_xml_dir = None
    if args.save_geo_dir:
        try: os.makedirs(args.save_geo_dir, exist_ok=True)
        except OSError as e: print(f"ERROR: Could not create GEO save directory '{args.save_geo_dir}': {e}. GEO files will not be saved.", file=sys.stderr); args.save_geo_dir = None

    temp_geo_download_dir_obj = tempfile.TemporaryDirectory(prefix="geoparse_dl_")
    temp_geo_download_dir = temp_geo_download_dir_obj.name
    print(f"DEBUG: Using temporary directory for GEOparse downloads: {temp_geo_download_dir}")

    print(f"INFO: Initializing LLMProcessor with model: {args.llm_model}, base URL: {args.llm_base_url}", file=sys.stderr)
    llm_processor = LLMProcessor(model_name=args.llm_model, base_url=args.llm_base_url)
    if not llm_processor.llm: 
        print("ERROR: LLM Processor could not be initialized. This is critical for the script's function. Exiting.", file=sys.stderr)
        temp_geo_download_dir_obj.cleanup() 
        sys.exit(1)

    if args.debug_single_srx_id:
        if not args.debug_single_keyword: 
            print("ERROR: --debug_single_keyword must be provided alongside --debug_single_srx_id for context.", file=sys.stderr)
            temp_geo_download_dir_obj.cleanup(); sys.exit(1)
        print(f"\n--- DEBUG MODE: Processing single SRX ID: {args.debug_single_srx_id} with keyword: '{args.debug_single_keyword}' ---")
        entrez_client_debug = EntrezClient() 

        # In debug mode, _process_single_srx will use INITIAL_OUTPUT_COLUMNS
        processed_record = _process_single_srx(
            args.debug_single_srx_id, args.debug_single_keyword, INITIAL_OUTPUT_COLUMNS,
            llm_processor, entrez_client_debug, args.save_xml_dir, args.save_geo_dir, temp_geo_download_dir
        )

        if processed_record:
            print(f"INFO: Extracted and synthesized metadata for {args.debug_single_srx_id} in debug mode:\n{json.dumps(processed_record, indent=2)}")
            # The CSV output in debug mode will use FINAL_OUTPUT_COLUMNS (which is INITIAL_OUTPUT_COLUMNS)
            pd.DataFrame([processed_record]).to_csv(args.output_csv_path, index=False, columns=FINAL_OUTPUT_COLUMNS, quoting=csv.QUOTE_ALL)
            print(f"INFO: Debug output saved to '{args.output_csv_path}'")
            # The individual phase1 JSON for this SRX ID would have been saved by _process_single_srx via synthesize_metadata
        else:
            print(f"ERROR: Failed to process SRX ID {args.debug_single_srx_id} in debug mode. No record generated.", file=sys.stderr)

        print("--- DEBUG MODE: Execution Finished ---")
        temp_geo_download_dir_obj.cleanup(); sys.exit(0) 

    # --- Main Processing (Formerly Phase 1) ---
    phase1_start_time = time.time()
    print(f"\n--- Main Processing: Fetching SRA Data, LLM Summary Generation & Metadata Synthesis/Relocation ---")
    print(f"Input Keyword CSV: '{args.input_csv_path}'")
    print(f"Output CSV: '{args.output_csv_path}'")

    keyword_provider = KeywordProvider(args.input_csv_path, args.keyword_column)
    entrez_client = EntrezClient() 

    keywords_to_process = keyword_provider.get_keywords()
    if not keywords_to_process:
        print("ERROR: No keywords found to process from the input CSV. Exiting.", file=sys.stderr)
    else:
        # CSV writer uses FINAL_OUTPUT_COLUMNS (which is INITIAL_OUTPUT_COLUMNS)
        csv_writer = CSVResultWriter(args.output_csv_path, FINAL_OUTPUT_COLUMNS)
        total_srx_processed_overall = 0
        total_srx_with_meaningful_data = 0 

        try:
            with tqdm(keywords_to_process, desc="Total Keywords Progress", unit="keyword", file=sys.stdout) as keyword_pbar:
                for keyword_idx, keyword in enumerate(keyword_pbar):
                    keyword_pbar.set_postfix_str(f"Current Keyword: {keyword[:30]}...") 
                    keyword_start_time = time.time()
                    tqdm.write(f"\nProcessing Keyword {keyword_idx+1}/{len(keywords_to_process)}: '{keyword}'")

                    sra_experiment_ids_all = entrez_client.get_sra_experiment_ids_from_runinfo_file(keyword)

                    if not sra_experiment_ids_all:
                        tqdm.write(f"INFO: No SRA Experiment IDs found for keyword '{keyword}'. Recording this and skipping.", file=sys.stderr)
                        placeholder_record = {col: "N/A" for col in FINAL_OUTPUT_COLUMNS}
                        placeholder_record["original_keyword"] = keyword
                        placeholder_record["sra_experiment_id"] = "NO_SRA_IDS_FOUND_FOR_KEYWORD"
                        placeholder_record["scientific_sample_summary"] = "No SRA Experiment IDs were found for this keyword."
                        csv_writer.write_batch([placeholder_record])
                        tqdm.write(f"Finished Keyword '{keyword}' in {time.time() - keyword_start_time:.2f}s (0 SRXs processed).", file=sys.stderr)
                        continue

                    tqdm.write(f"INFO: Found {len(sra_experiment_ids_all)} SRA Experiment IDs for '{keyword}'. Starting parallel processing with {args.max_workers} workers.", file=sys.stderr)
                    batch_of_records_for_csv = [] 

                    with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_workers) as executor:
                        future_to_srx = {
                            # _process_single_srx now uses INITIAL_OUTPUT_COLUMNS for its internal structure
                            executor.submit(_process_single_srx, srx_id, keyword, INITIAL_OUTPUT_COLUMNS, llm_processor, entrez_client, args.save_xml_dir, args.save_geo_dir, temp_geo_download_dir): srx_id
                            for srx_id in sra_experiment_ids_all
                        }
                        for future in tqdm(concurrent.futures.as_completed(future_to_srx), total=len(sra_experiment_ids_all), desc=f"  Keyword '{keyword[:20]}' SRX Progress", unit="SRX", leave=False, file=sys.stdout):
                            srx_id_completed = future_to_srx[future]
                            try:
                                current_record = future.result() # This record is structured by INITIAL_OUTPUT_COLUMNS
                                total_srx_processed_overall += 1
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
                                if is_meaningful: total_srx_with_meaningful_data +=1

                                batch_of_records_for_csv.append(current_record)
                                if len(batch_of_records_for_csv) >= BATCH_SIZE_LLM:
                                    csv_writer.write_batch(batch_of_records_for_csv); batch_of_records_for_csv = []
                            except Exception as exc: 
                                tqdm.write(f"    ERROR: SRX ID '{srx_id_completed}' (Keyword: '{keyword}') generated an unhandled exception during parallel processing: {exc}", file=sys.stderr)
                                import traceback; traceback.print_exc(file=sys.stderr)
                                failure_record = {col: "N/A" for col in FINAL_OUTPUT_COLUMNS}
                                failure_record["original_keyword"] = keyword
                                failure_record["sra_experiment_id"] = srx_id_completed
                                failure_record["experiment_title"] = f"TOP_LEVEL_PROCESSING_ERROR: {str(exc)[:100]}"
                                failure_record["scientific_sample_summary"] = f"A critical error occurred during processing: {str(exc)[:100]}"
                                batch_of_records_for_csv.append(failure_record)
                                if len(batch_of_records_for_csv) >= BATCH_SIZE_LLM: 
                                     csv_writer.write_batch(batch_of_records_for_csv); batch_of_records_for_csv = []
                            finally:
                                time.sleep(0.01) 

                    if batch_of_records_for_csv:
                        tqdm.write(f"  INFO: Writing final batch of {len(batch_of_records_for_csv)} records for keyword '{keyword}' to CSV.", file=sys.stderr)
                        csv_writer.write_batch(batch_of_records_for_csv)

                    tqdm.write(f"Finished Keyword '{keyword}' in {time.time() - keyword_start_time:.2f}s ({len(sra_experiment_ids_all)} SRXs attempted).", file=sys.stderr)
        except KeyboardInterrupt:
            print("\nINFO: KeyboardInterrupt received during processing. Attempting to shut down gracefully...", file=sys.stderr)
        finally:
            if 'csv_writer' in locals() and csv_writer: csv_writer.close_writer()
            processing_duration = time.time() - phase1_start_time
            print(f"\n--- Main Processing Finished (Total Time: {processing_duration:.2f}s) ---")
            print(f"Total SRA Experiment IDs processed: {total_srx_processed_overall}")
            print(f"Total SRA Experiment IDs with some meaningful metadata extracted: {total_srx_with_meaningful_data}")
            print(f"Results saved to: {args.output_csv_path}")

    # Phase 2 is removed.

    try:
        temp_geo_download_dir_obj.cleanup()
        print(f"DEBUG: Successfully cleaned up temporary GEO download directory: {temp_geo_download_dir}")
    except Exception as e_cleanup:
        print(f"WARNING: Could not cleanup temporary GEO download directory '{temp_geo_download_dir}': {e_cleanup}", file=sys.stderr)

    overall_script_duration = time.time() - overall_script_start_time
    print(f"\n--- All Script Processing Finished ---")
    print(f"Total script execution time: {overall_script_duration:.2f} seconds (approx. {overall_script_duration/60:.2f} minutes).")
    print(f"Final results are in: {args.output_csv_path}")
    print(f"Individual LLM synthesis JSON outputs (if any) are saved in the 'phase1_json_outputs' directory.")


if __name__ == "__main__":
    main()
