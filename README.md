# SRA Fetch AI Agent 🧬🧠🔍

**Automated NGS Data Fetching and AI-Powered Metadata Processing**

## Overview

`SRA_fetch.py` is a Python-based command-line tool designed to automate the retrieval of Next-Generation Sequencing (NGS) data and comprehensively process its associated metadata. By leveraging user-provided keywords, this script streamlines bioinformatics workflows for data acquisition from NCBI's Sequence Read Archive (SRA) and Gene Expression Omnibus (GEO).

The script employs a suite of specialized AI agents, powered by Large Language Models (LLMs) via `langchain-ollama`, to intelligently interpret, extract, and synthesize complex biological metadata.

### AI Agent Roles:

This script utilizes distinct AI-driven prompts to handle specific metadata tasks:

1.  **GEO Accession Extractor:**
    * **Role:** Identifies and extracts GEO Series (GSE) and GEO Sample (GSM) accession numbers from SRA Experiment XML.
    * **Output:** A JSON object like `{"gse": "GSE12345", "gsm": "GSM123456"}`. It includes a regex-based fallback if the LLM fails.

2.  **Scientific Sample Summarizer:**
    * **Role:** Acts as a biomedical data scientist to generate a concise scientific summary (2-4 sentences) for each sample.
    * **Input:** SRA Experiment XML, GEO data summary (if available), original search keyword, and SRA ID.
    * **Output:** A human-readable text summary.

3.  **Comprehensive Metadata Synthesizer:**
    * **Role:** Functions as a meticulous biomedical data curator. It analyzes the scientific summary, SRA XML, and GEO data to extract and structure a wide range of metadata fields.
    * **Output:** A detailed JSON object containing fields specified in the script (e.g., species, sample type, sequencing technique, disease description, treatment protocols, ChIP-Seq details). This JSON is then mapped to the final CSV output.

## Features

* **Keyword-driven Data Discovery:** Searches SRA using keywords from a user-provided CSV file.
* **Automated SRA Experiment ID Retrieval:** Fetches SRA Experiment IDs (SRX) based on keywords.
* **SRA XML Fetching:** Downloads SRA Experiment XML for detailed metadata.
* **GEO Data Integration:**
    * AI-driven extraction of GSE/GSM accessions from SRA XML.
    * Fetches GEO metadata using `GEOparse` if accessions are found.
* **AI-Powered Metadata Processing:**
    * **Scientific Summarization:** Generates concise summaries of samples.
    * **Structured Extraction:** Populates a detailed schema of metadata fields through LLM-based synthesis.
* **Parallel Processing:** Utilizes multi-threading for efficient processing of multiple SRA IDs.
* **Comprehensive CSV Output:** Generates a detailed CSV file with extracted and synthesized metadata.
* **Optional Data Saving:** Allows saving of raw SRA XML and GEO SOFT files.
* **Intermediate LLM Outputs:** Saves the raw JSON output from the metadata synthesis LLM for each SRA experiment, aiding in debugging and transparency.
* **Retry Mechanisms:** Implements retries for Entrez and LLM calls to handle transient network issues.

## Installation

To get `SRA_fetch.py` up and running on your local system, follow these installation steps.

### 1. Clone the Repository

First, clone this repository to your local machine using Git. Open your terminal and run:

```bash
git clone [https://github.com/YOUR_USERNAME/YOUR_REPOSITORY_NAME.git](https://github.com/YOUR_USERNAME/YOUR_REPOSITORY_NAME.git)
cd YOUR_REPOSITORY_NAME
Note: Replace YOUR_USERNAME and YOUR_REPOSITORY_NAME with your actual GitHub username and the name of this repository.2. Create and Activate Python Virtual EnvironmentIt is highly recommended to use a Python virtual environment to manage dependencies.Create the environment (e.g., named sra_llm):python3 -m venv sra_llm
# or "python -m venv sra_llm" if python3 is your default
Activate the environment:On macOS and Linux:source sra_llm/bin/activate
On Windows (Git Bash or WSL):source sra_llm/Scripts/activate
On Windows (Command Prompt):.\sra_llm\Scripts\activate.bat
On Windows (PowerShell):.\sra_llm\Scripts\Activate.ps1
Once activated, your terminal prompt should be prefixed with (sra_llm).3. Install Python DependenciesWith the virtual environment activated, install the necessary Python packages using pip:pip install pandas GEOparse langchain-ollama tqdm
The script includes a check for GEOparse and will exit if it's not found.4. Install NCBI Entrez Direct (EDirect)NCBI's Entrez Direct (EDirect) command-line tools are required for programmatic access to NCBI databases.Automated Installation:Execute one of the following commands in your terminal:Using curl:sh -c "$(curl -fsSL [https://ftp.ncbi.nlm.nih.gov/entrez/entrezdirect/install-edirect.sh](https://ftp.ncbi.nlm.nih.gov/entrez/entrezdirect/install-edirect.sh))"
Or, using wget:sh -c "$(wget -q [https://ftp.ncbi.nlm.nih.gov/entrez/entrezdirect/install-edirect.sh](https://ftp.ncbi.nlm.nih.gov/entrez/entrezdirect/install-edirect.sh) -O -)"
This script will download EDirect utilities into an edirect folder in your home directory.Update PATH Environment Variable:The EDirect installation script will likely offer to update your shell's configuration file (e.g., .bash_profile, .bashrc, .zshrc). It is recommended to allow the script to do this by typing y and pressing Enter.If you need to do it manually or verify:For macOS/Linux, add/ensure this line is in your shell configuration file:export PATH=${HOME}/edirect:${PATH}
Then, load the updated configuration (e.g., source ~/.bash_profile) or open a new terminal.For Windows, add the edirect directory (e.g., C:\Users\YourUser\edirect) to your System Environment Variables.Set PATH for Current Session (Temporary):export PATH=${HOME}/edirect:${PATH} # For macOS/Linux
Verify EDirect Installation:Test by running:esearch -db pubmed -query "genome" | efetch -format uid
This should return a list of UIDs from PubMed.5. Setup OllamaThis script relies on an Ollama instance to serve the LLM.Install Ollama from https://ollama.com/.Download the LLM model you intend to use (default is gemma3:12b-it-qat):ollama pull gemma3:12b-it-qat
(Or replace gemma3:12b-it-qat with your chosen model specified via the --llm_model argument).Ensure Ollama is running before executing the script. By default, it runs at http://localhost:11434.UsageExecute the script from the command line within the activated sra_llm virtual environment.Command Syntax:python SRA_fetch.py <input_csv_path> <output_csv_path> [options]
Positional Arguments:input_csv_path: (Required) Path to the input CSV file containing keywords.output_csv_path: (Required) Path to the output CSV file where results will be saved.Optional Arguments:--keyword_column TEXT: Name of the column in the input CSV that contains keywords. If not specified, the first column is used.--llm_model TEXT: Name of the Ollama model to use. (Default: gemma3:12b-it-qat)--llm_base_url TEXT: Base URL for the Ollama API. (Default: http://localhost:11434)--max_workers INTEGER: Number of parallel worker threads for processing SRA IDs. (Default: 4)--save_xml_dir DIRECTORY_PATH: Optional. Directory path to save fetched SRA XML files.--save_geo_dir DIRECTORY_PATH: Optional. Directory path to save fetched GEO SOFT files.--debug_single_srx_id TEXT: For debugging. Provide a single SRX ID to fetch and process. Requires --debug_single_keyword.--debug_single_keyword TEXT: Keyword associated with --debug_single_srx_id for context. (Default: DEBUG_KEYWORD)-h, --help: Show help message and exit.Input Keyword CSV Format:A plain CSV file.The script reads keywords from the column specified by --keyword_column or, by default, the first column.Ensure the CSV has a header row if you are specifying --keyword_column by name. If using the first column by default, the script attempts to handle CSVs with or without a header.Example Usage:Basic run with default settings:python SRA_fetch.py keywords.csv results.csv
Specify keyword column and save XML/GEO files:python SRA_fetch.py studies_to_find.csv output_metadata.csv --keyword_column "SearchTerm" --save_xml_dir ./sra_xml_files --save_geo_dir ./geo_soft_files
Use a different LLM model and more workers:python SRA_fetch.py input.csv processed_data.csv --llm_model "mistral:latest" --max_workers 8
Debug a single SRA experiment:python SRA_fetch.py debug_input.csv debug_output.csv --debug_single_srx_id "SRX123456" --debug_single_keyword "cancer study"
(Note: debug_input.csv is still a required argument for the script structure, but it won't be used if --debug_single_srx_id is provided).OutputThe script generates several outputs:Main Output CSV File (output_csv_path):This is the primary result, containing one row per processed SRA Experiment ID.If no SRA IDs are found for a keyword, a placeholder row is added.Columns include:original_keywordsra_experiment_idgse_accessiongsm_accessionexperiment_titlespeciessequencing_technique (e.g., RNA-Seq, ChIP-Seq, ATAC-Seq)sample_type (e.g., Cell Line, Primary Cells, Tissue: Tumor)cell_line_nametissue_typetissue_source_detailsdisease_descriptionsample_treatment_protocolclinical_sample_identifierlibrary_source (e.g., TRANSCRIPTOMIC, GENOMIC)instrument_modelis_chipseq_related_experiment (yes/no)chipseq_antibody_targetchipseq_control_descriptionchipseq_igg_control_present (yes/no/unknown)chipseq_input_control_present (yes/no/unknown)chipseq_nfcore_summary_lines (typically "N/A" unless specific pipeline output is parsed)scientific_sample_summary (AI-generated summary)Fields for which information could not be found or inferred will contain "N/A".Intermediate LLM Outputs (Directory: phase1_json_outputs):For each SRA Experiment ID processed by the "Metadata Synthesizer" LLM, a JSON file is saved in this directory (created in the script's working directory).Filename format: {srx_id}_phase1_synthesis_LLM_output.json.This file contains the raw JSON output from the LLM before it's mapped to the final CSV columns, useful for debugging and understanding the LLM's direct response.Optional Saved Raw Data:If --save_xml_dir is provided: SRA Experiment XML files are saved to the specified directory (e.g., {srx_id}.xml).If --save_geo_dir is provided: GEO SOFT files (usually .soft or .soft.gz) are saved to the specified directory.How it Works (High-Level Workflow)Initialization: Parses arguments, initializes LLMProcessor (connects to Ollama).Keyword Processing: Reads keywords from the input CSV.For each keyword:a.  SRA ID Fetching: Uses EntrezClient (NCBI EDirect tools esearch & efetch -format runinfo) to find SRA Experiment IDs (SRX, ERX, DRX) associated with the keyword.b.  Parallel SRX Processing: For each SRA Experiment ID:i.  Fetch SRA XML: Downloads the full SRA Experiment XML using efetch.ii. Extract GEO Accessions (GSE/GSM): The "GEO Accession Extractor" LLM (with regex fallback) parses the SRA XML to find linked GSE and GSM IDs.iii. Fetch GEO Data: If GSE or GSM IDs are found, GEOparse is used to download and parse the corresponding GEO SOFT file. A summary of GEO metadata is created.iv. Generate Scientific Summary: The "Scientific Sample Summarizer" LLM generates a concise text summary using SRA XML, GEO data, and the original keyword.v.  Synthesize Comprehensive Metadata: The "Comprehensive Metadata Synthesizer" LLM takes the scientific summary, SRA XML, GEO data, and accessions to produce a detailed JSON object containing various metadata fields. The raw JSON from this step is saved to the phase1_json_outputs directory.vi. Map to CSV: The synthesized JSON data is mapped to the predefined CSV columns.c.  Write to CSV: Processed records are batched and written to the output CSV file.Cleanup: Temporary directories are removed.ContributingContributions are welcome! If you have suggestions for improvements or find bugs, please feel free to:Fork the Project (https://github.com/YOUR_USERNAME/YOUR_REPOSITORY_NAME/fork)Create your Feature Branch (git checkout -b feature/AmazingFeature)Commit your Changes (git commit -m 'Add some AmazingFeature')Push to the Branch (git push origin feature/AmazingFeature)Open a Pull RequestYou can also open an issue with the tag "enhancement" or "bug".LicenseDistributed under the MIT License. See LICENSE.txt for more information.(TODO: Create a LICENSE.txt file in your repository with the MIT License text: https://opensource.org/licenses/MIT)ContactYOUR_NAME - (Your GitHub Profile or Email)Project Link: https://github.com/YOUR_USERNAME/YOUR_REPOSITORY_NAMEAcknowledgements (Optional)NCBI Entrez Direct & GEOOllama Team & Langchain Community
