![Icon](icon.png)

# SRA Fetch AI Agent 🧬🧠🔍

**Automated NGS Data Fetching and AI-Powered Metadata Processing**

## Overview

`SRA_fetch.py` is a Python command-line tool designed to automate the retrieval of Next-Generation Sequencing (NGS) data from NCBI's Sequence Read Archive (SRA) and Gene Expression Omnibus (GEO). It processes associated metadata using keyword-driven searches and leverages AI agents powered by Large Language Models (LLMs) via `langchain-ollama` to interpret, extract, synthesize, and standardize complex biological metadata, including a new standardized `treatment` field.

### AI Agent Roles

The script employs specialized AI agents for metadata processing:

1.  **GEO Accession Extractor**
    *   **Role**: Extracts GEO Series (GSE) and GEO Sample (GSM) accession numbers from SRA Experiment XML.
    *   **Output**: JSON object, e.g., `{"gse": "GSE12345", "gsm": "GSM123456"}`.
    *   **Fallback**: Uses regex if the LLM fails.

2.  **Comprehensive Metadata Synthesizer**
    *   **Role**: Analyzes SRA XML, and GEO data to extract and structure metadata fields as a meticulous biomedical data curator. This includes generating a concise scientific summary (2–4 sentences) for each sample and deriving a standardized `treatment` term from the `sample_treatment_protocol`.
    *   **Output**: Detailed JSON object with fields like species, sample type, sequencing technique, disease description, treatment protocols, standardized treatment, ChIP-Seq details, and a scientific summary, all mapped to the final CSV output.

![Workflow Diagram](workflow.png)

## Features

- **Keyword-Driven Data Discovery**: Searches SRA using keywords from a user-provided CSV (or auto-detected `keywords.csv`).
- **Automated SRA Experiment ID Retrieval**: Fetches SRA Experiment IDs (SRX) based on keywords.
- **SRA XML Fetching**: Downloads SRA Experiment XML for detailed metadata.
- **GEO Data Integration**:
    - AI-driven extraction of GSE/GSM accessions from SRA XML.
    - Fetches GEO metadata using `GEOparse` if accessions are found.
- **AI-Powered Metadata Processing**:
    - Extracts structured metadata into a detailed schema.
    - Standardizes treatment information into a dedicated `treatment` column.
    - Generates concise sample summaries.
- **Parallel Processing**: Uses multi-threading for efficient processing of multiple SRA IDs.
- **Comprehensive CSV Output**: Produces a detailed CSV (default `output/result.csv`) with extracted and processed metadata.
- **Optional Data Saving**: Saves raw SRA XML and GEO SOFT files if specified.
- **Intermediate LLM Outputs**: Stores raw JSON from metadata synthesis for debugging.
- **Retry Mechanisms**: Handles transient network issues for Entrez and LLM calls.
- **User-Friendly Setup**: Includes clear, step-by-step installation instructions.

## Installation

Follow these detailed steps to set up `SRA_fetch.py` on your local system.

### 1. Clone the Repository

First, clone the SRA_LLM repository to your local machine and navigate into the project directory:

```bash
git clone https://github.com/schoo7/SRA_LLM.git
cd SRA_LLM
```

### 2. Create and Activate a Python Virtual Environment

It is highly recommended to use a Python virtual environment to manage project dependencies and avoid conflicts with other Python projects.

- Create the virtual environment (e.g., named `sra_env`):
  ```bash
  python3 -m venv sra_env
  ```

- Activate the environment:
    - **macOS/Linux (bash/zsh)**:
      ```bash
      source sra_env/bin/activate
      ```
    - **Windows (Git Bash or WSL)**:
      ```bash
      source sra_env/Scripts/activate
      ```
    - **Windows (Command Prompt)**:
      ```bash
      .\sra_env\Scripts\activate.bat
      ```
    - **Windows (PowerShell)**:
      ```bash
      .\sra_env\Scripts\Activate.ps1
      ```
  Your terminal prompt should now be prefixed with `(sra_env)` or your chosen environment name, indicating that the virtual environment is active.

### 3. Install Python Dependencies

With the virtual environment activated, install the necessary Python packages listed in the (future) `requirements.txt` file, or install them manually:

```bash
pip install pandas GEOparse langchain-ollama tqdm
```
The script internally checks for `GEOparse` and will exit with an error message if it's not found.

### 4. Install NCBI Entrez Direct (EDirect)

EDirect command-line tools are required for programmatic access to NCBI databases (like SRA and GEO).

- **Automated Installation**:
  Run one of the following commands in your terminal. This script will download EDirect to a directory named `edirect` within your home directory (`~/edirect`).
    - Using `curl`:
      ```bash
      sh -c "$(curl -fsSL https://ftp.ncbi.nlm.nih.gov/entrez/entrezdirect/install-edirect.sh)"
      ```
    - Using `wget`:
      ```bash
      sh -c "$(wget -q https://ftp.ncbi.nlm.nih.gov/entrez/entrezdirect/install-edirect.sh -O -)"
      ```

- **Update PATH Environment Variable**:
  The installer should offer to update your shell configuration file (e.g., `~/.bash_profile`, `~/.bashrc`, or `~/.zshrc` for macOS/Linux). It's recommended to allow this by entering `y` when prompted.
  If you need to do this manually, add the following line to your shell configuration file:
  ```bash
  export PATH=${HOME}/edirect:${PATH}
  ```
  Then, reload your shell configuration:
  ```bash
  source ~/.bash_profile  # Or ~/.bashrc, ~/.zshrc, depending on your shell
  ```
  For Windows, you'll need to add the `edirect` directory path (e.g., `C:\Users\YourUser\edirect`) to your system's PATH environment variable manually through System Properties.

- **Verify EDirect Installation**:
  Test if EDirect is correctly installed and configured by running:
  ```bash
  esearch -db pubmed -query "genome" | efetch -format uid
  ```
  This command should output a list of PubMed UIDs, confirming EDirect is working.

### 5. Set Up Ollama and Download an LLM Model

The script uses a locally running Ollama instance to serve the Large Language Model (LLM).

1.  **Install Ollama**:
    Download and install Ollama for your operating system from the official website: [https://ollama.com/](https://ollama.com/). Follow the installation instructions provided.

2.  **Pull an LLM Model**:
    Once Ollama is installed, you need to download an LLM model. The script defaults to `gemma3:12b-it-qat`, but you can specify a different model via the `--llm_model` argument. To pull the default model, run:
    ```bash
    ollama pull gemma3:12b-it-qat
    ```
    For other models, like `mistral`:
    ```bash
    ollama pull mistral
    ```
    Ensure you have sufficient disk space and RAM for the chosen model.

3.  **Ensure Ollama is Running**:
    Before executing `SRA_fetch.py`, make sure the Ollama application is running. By default, it serves the API at `http://localhost:11434`. You can usually start it from your applications menu or by running `ollama serve` in a terminal (though often it runs as a background service after installation).

## Usage

Ensure your Python virtual environment (`sra_env`) is activated before running the script.

### Command Syntax

```bash
python SRA_fetch.py [input_csv_path] [output_csv_path] [options]
```

### Positional Arguments

- `input_csv_path` (Optional): Path to the input CSV file containing keywords.
    - If not provided, the script will automatically look for `keywords.csv`, `keyword.csv`, `Keywords.csv`, or `Keyword.csv` in the script's directory.
- `output_csv_path` (Optional): Path to the output CSV file where results will be saved.
    - If not provided, results will be saved to `output/result.csv` in the script's directory. The `output` directory will be created if it doesn't exist.

### Optional Arguments

- `--keyword_column TEXT`: Name of the column in the input CSV that contains keywords. If not specified, the first column is used.
- `--llm_model TEXT`: Name of the Ollama model to use (Default: `gemma3:12b-it-qat`).
- `--llm_base_url TEXT`: Base URL for the Ollama API (Default: `http://localhost:11434`).
- `--max_workers INTEGER`: Number of parallel worker threads for processing SRA IDs (Default: 1 for sequential processing, which is recommended for Ollama stability).
- `--sequential`: Force sequential processing (same as `--max_workers 1`). Recommended for Ollama stability.
- `--save_xml_dir DIRECTORY_PATH`: Optional: Directory path to save fetched SRA XML files.
- `--save_geo_dir DIRECTORY_PATH`: Optional: Directory path to save fetched GEO SOFT files.
- `--debug_single_srx_id TEXT`: For debugging: provide a single SRX ID to fetch and process. Requires `--debug_single_keyword`.
- `--debug_single_keyword TEXT`: Keyword associated with `--debug_single_srx_id` for context (Default: `DEBUG_KEYWORD`).
- `-h, --help`: Show this help message and exit.

### Input Keyword CSV Format

- A plain CSV file.
- Keywords should be in the column specified by `--keyword_column` or in the first column by default.
- If using `--keyword_column`, ensure your CSV has a header row.
- The script can auto-detect and use files like `keywords.csv` in its directory if `input_csv_path` is not specified. A simple `keyword.csv` could look like:
  ```csv
  SearchTerm
  H660
  Prostate Cancer ChIP-seq
  GSE12345
  ```

### Example Usage

1.  **Run with auto-detected `keywords.csv` and default output `output/result.csv`**:
    ```bash
    python SRA_fetch.py
    ```
    (Ensure `keywords.csv` exists in the same directory as `SRA_fetch.py`)

2.  **Specify input and output files**:
    ```bash
    python SRA_fetch.py my_keywords.csv my_results.csv
    ```

3.  **Specify keyword column and save XML/GEO files**:
    ```bash
    python SRA_fetch.py studies_to_find.csv output_metadata.csv --keyword_column "CellLine" --save_xml_dir ./sra_xml_files --save_geo_dir ./geo_soft_files
    ```

4.  **Use a different LLM model and run sequentially**:
    ```bash
    python SRA_fetch.py input.csv processed_data.csv --llm_model "mistral:latest" --sequential
    ```

5.  **Debug a single SRA experiment**:
    ```bash
    python SRA_fetch.py --debug_single_srx_id "SRX123456" --debug_single_keyword "cancer study"
    ```
    (Note: When debugging a single SRX ID, `input_csv_path` and `output_csv_path` arguments can be omitted if you want to use the default debug output name, or provided to specify them. The script will create a debug output CSV.)


## Output

The script generates the following outputs:

### Main Output CSV File

- Default location: `output/result.csv` (created in the script's working directory, inside an `output` subfolder).
- Each row corresponds to one processed SRA Experiment ID.
- If no SRA IDs are found for a given keyword, a placeholder row for that keyword is added.
- **Columns include**:
    - `original_keyword`
    - `sra_experiment_id`
    - `gse_accession`
    - `gsm_accession`
    - `experiment_title`
    - `species`
    - `sequencing_technique` (e.g., RNA-Seq, ChIP-Seq, ATAC-Seq, WGS)
    - `sample_type` (e.g., Cell Line, Primary Cells, Tissue: Tumor, Tissue: Healthy Donor)
    - `cell_line_name`
    - `tissue_type`
    - `tissue_source_details`
    - `disease_description` (e.g., Prostate cancer, Healthy Control)
    - `sample_treatment_protocol` (Detailed protocol from the source)
    - `treatment` (Standardized treatment term, see below)
    - `clinical_sample_identifier`
    - `library_source` (e.g., TRANSCRIPTOMIC, GENOMIC, EPIGENOMIC)
    - `instrument_model`
    - `is_chipseq_related_experiment` (yes/no)
    - `chipseq_antibody_target`
    - `chipseq_control_description`
    - `chipseq_igg_control_present` (yes/no/unknown)
    - `chipseq_input_control_present` (yes/no/unknown)
    - `chipseq_nfcore_summary_lines` (typically "N/A")
    - `scientific_sample_summary` (AI-generated 2-4 sentence summary)
- Fields for which no data could be extracted or inferred are marked as "N/A".

### `treatment` Column Standardization

The `treatment` column provides a concise, standardized version of the `sample_treatment_protocol`. The LLM is guided to use the following patterns:

- **`WT`**: For wild-type, untreated samples, or when treatment is unknown/not specified.
- **`control`**: For vehicle controls (e.g., DMSO, PBS), negative controls (e.g., siNC, control siRNA), or mock treatments.
- **`GENE_overexpressed`**: For samples where a specific gene is overexpressed (e.g., `YAP1_overexpressed`).
- **`GENE_knockdown`**: For samples where a specific gene is knocked down using siRNA, shRNA, etc. (e.g., `PLXND1_knockdown`, `siJUN_knockdown`).
- **`GENE_knockout`**: For samples where a specific gene is knocked out (e.g., via CRISPR).
- **`COMPOUND_treated`**: For samples treated with a specific drug or chemical compound (e.g., `Romidepsin_treated`, `DOX_treated`, `JG231_treated`).
- **Combined Treatments**: Multiple treatments can be combined using "+" (e.g., `Romidepsin_treated+Ipata_treated`).
- The LLM uses the actual gene or compound names identified in the protocol.

### Example Output Table (`output/result.csv`)

Here's a snippet of what the `result.csv` might look like:

| original_keyword | sra_experiment_id | gse_accession | gsm_accession | ... | sample_treatment_protocol                                                                                                                                                                                                                            | treatment             | ... | scientific_sample_summary                                                                                                                                                                                                                                                           |
| :--------------- | :---------------- | :------------ | :------------ | :-- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :-------------------- | :-- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| H660             | SRX27646686       | GSE289308     | GSM8788756    | ... | H660 cells were maintained in Gibco RPMI 1640 Media containing 10% heat inactivated FBS.                                                                                                                                                           | WT                    | ... | This study investigated H660 prostate cancer cells treated with DOX. Total RNA was isolated...                                                                                                                                                                                    |
| H660             | SRX24614915       | GSE267961     | GSM8282538    | ... | PLXND1 knockdown                                                                                                                                                                                                                                   | PLXND1_knockdown      | ... | This study investigates the effect of PLXND1 knockdown in the H660 prostate cancer cell line using RNA-Seq...                                                                                                                                                                    |
| H660             | SRX22861194       | GSE249916     | GSM7966926    | ... | Total cellular RNA was isolated from vehicle (DMSO)-treated H660 prostate cancer cell lines...                                                                                                                                                         | control               | ... | This study investigates the transcriptome of H660 prostate cancer cells treated with DMSO...                                                                                                                                                                                    |
| H660             | SRX20355949       | GSE232552     | GSM7350173    | ... | PC3,NCI-H660 cells were treated with vehicle versus ORY-1001, or C12 for 4hrs                                                                                                                                                                         | vehicle_treated       | ... | This experiment investigates FOXA2 binding in NCI-H660 prostate cancer cells treated with vehicle...                                                                                                                                                                         |
| H660             | SRX11823681       | GSE182407     | GSM5528455    | ... | Total RNA from cell lines/cell pellets... NCI-H660 with YAP1 overexpression human prostate tumor cell line                                                                                                                                              | YAP1_overexpressed    | ... | This experiment investigates the effects of YAP1 overexpression in the NCI-H660 human prostate cancer cell line...                                                                                                                                                            |

*(Note: "..." indicates other columns present in the table.)*

### Intermediate LLM Outputs

- Directory: `phase1_json_outputs` (created in the working directory where the script is run).
- Each SRA Experiment ID processed will have a corresponding JSON file: `{srx_id}_phase1_synthesis_LLM_output.json`.
- These files contain the raw JSON output from the Comprehensive Metadata Synthesizer LLM before it's mapped to the CSV. This is useful for debugging the LLM's interpretation and data extraction.
- Additionally, `{srx_id}_geo_accessions_debug.json` files are saved in the same directory, containing raw LLM output for GEO accession extraction.


### Optional Saved Raw Data

- If `--save_xml_dir PATH` is provided: SRA XML files are saved to the specified `PATH` as `{srx_id}.xml`.
- If `--save_geo_dir PATH` is provided: GEO SOFT files (e.g., `GSE12345.soft.gz`, `GSM123456.soft`) are downloaded by `GEOparse` into a temporary directory and then moved to the specified `PATH`.

## How It Works

### High-Level Workflow

1.  **Initialization**:
    *   Parses command-line arguments.
    *   Sets up output directories and logging.
    *   Initializes the `LLMProcessor` with the specified Ollama model and settings.
    *   Initializes the `EntrezClient` for NCBI communication.

2.  **Keyword Processing**:
    *   Reads keywords from the input CSV (or auto-detected file).
    *   For each keyword:
        a.  **SRA ID Fetching**: Uses `EntrezClient` (which internally uses EDirect's `esearch` and `efetch -format runinfo` commands) to find all associated SRA Experiment IDs (SRX, ERX, DRX).
        b.  **Parallel SRX Processing** (using `ThreadPoolExecutor` if `max_workers` > 1):
            For each SRA Experiment ID:
            i.  Fetch SRA Experiment XML using `EntrezClient` (`efetch -db sra -id SRX... -format xml`).
            ii. Extract GEO Accessions (GSE/GSM): The `LLMProcessor` calls the GEO Accession Extractor agent with the SRA XML. Regex fallback is used if the LLM fails or returns invalid data.
            iii. Fetch GEO Data: If GSE or GSM IDs are found, `GEOparse` is used to download the GEO SOFT file (to a temporary directory). Key metadata from the GEO record is summarized.
            iv. Synthesize Comprehensive Metadata: The `LLMProcessor` calls the Comprehensive Metadata Synthesizer agent. This agent receives the original keyword, SRA ID, GSE/GSM IDs, the SRA XML snippet, and the GEO data summary. It then generates a structured JSON containing all required fields, including the standardized `treatment` term and the `scientific_sample_summary`.
            v.  Save Intermediate Output: The raw JSON response from the metadata synthesizer is saved to the `phase1_json_outputs` directory.
            vi. Map to CSV: The structured JSON data is mapped to the defined CSV columns.
        c.  **Write to CSV**: Processed records are batched and written to the main output CSV file by `CSVResultWriter`, which handles headers and appends data correctly.

3.  **Cleanup**: Temporary directories (e.g., for GEO downloads) are removed.
4.  **Summary**: Prints a summary of the processing, including total time taken and number of records processed.

## Contributing

Contributions are welcome! If you'd like to contribute to this project, please follow these steps:

1.  Fork the project: [https://github.com/schoo7/SRA_LLM/fork](https://github.com/schoo7/SRA_LLM/fork)
2.  Create a feature branch for your changes:
    ```bash
    git checkout -b feature/YourAmazingFeature
    ```
3.  Make your changes and commit them with clear, descriptive messages:
    ```bash
    git commit -m 'Add: Your amazing feature'
    ```
4.  Push your feature branch to your fork:
    ```bash
    git push origin feature/YourAmazingFeature
    ```
5.  Open a Pull Request against the `main` branch of the `schoo7/SRA_LLM` repository.

If you find any bugs or have suggestions for enhancements, please open an issue on GitHub and use the "bug" or "enhancement" tag.

## License

Distributed under the MIT License. Please see the `LICENSE.txt` file for more details (if it exists in the repository, or refer to the standard MIT License text).

*TODO*: Add a `LICENSE.txt` file to the repository. You can use the MIT License text from: [https://opensource.org/licenses/MIT](https://opensource.org/licenses/MIT).

## Contact

- **Author**: Siyuan Cheng
- **Lab**: Mu Lab, Yale
- **GitHub**: [https://github.com/schoo7](https://github.com/schoo7)
- **Email**: siyuan.cheng@yale.edu (Please use GitHub Issues for project-related questions)
- **Project Link**: [https://github.com/schoo7/SRA_LLM/](https://github.com/schoo7/SRA_LLM/)
