# ACMG-AutoEvidence

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

> Automated extraction and classification of scientific evidence for ACMG variant interpretation

ACMG-AutoEvidence is a comprehensive toolkit that automates the process of searching scientific literature for genetic variant evidence and evaluating it against ACMG criteria using Large Language Models (LLMs). This tool helps clinical geneticists and researchers streamline variant interpretation by automatically extracting relevant evidence from PubMed/PMC publications.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Components](#components)
  - [Variant Alias Generator](#variant-alias-generator)
  - [ACMG Evidence Analyzer](#acmg-evidence-analyzer)
- [Usage](#usage)
  - [Complete Workflow](#complete-workflow)
  - [Command Line Options](#command-line-options)
- [Configuration](#configuration)
- [Input/Output Formats](#inputoutput-formats)
- [Performance Optimization](#performance-optimization)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [Citation](#citation)
- [License](#license)

## Overview

ACMG-AutoEvidence consists of two main components:

1. **Variant Alias Generator** - Converts BED files with variant information into JSON format with multiple alias representations
2. **ACMG Evidence Analyzer** - Searches scientific literature for variant information and analyzes it using LLMs against ACMG criteria

The toolkit addresses the challenge of manually reviewing thousands of publications for variant interpretation by:
- Automatically searching PubMed/PMC for relevant articles
- Retrieving full text when available
- Using state-of-the-art LLMs to evaluate evidence against specific ACMG criteria
- Generating structured outputs suitable for clinical interpretation

## Features

### Variant Alias Generator
- **Dynamic Column Detection**: Automatically detects column positions from BED file headers
- **Multiple Variant Representations**: Generates HGVS, SPDI, rsID, and other nomenclatures
- **Robust Parsing**: Handles complex variants including frameshifts, deletions, insertions, and extensions
- **Streaming Mode**: Memory-efficient processing for large files
- **Comprehensive Validation**: Validates chromosome names and genomic positions

### ACMG Evidence Analyzer
- **Comprehensive Literature Search**: Searches PubMed and PMC databases
- **Full Text Retrieval**: Automatically retrieves full text from PMC when available
- **LLM-Powered Analysis**: Uses Ollama LLMs to analyze articles against ACMG criteria
- **Parallel Processing**: Concurrent searches and article retrieval for improved performance
- **Flexible Configuration**: YAML-based configuration with environment variable support
- **Multiple Output Formats**: CSV, JSON, and Excel outputs
- **Progress Tracking**: Detailed logging and progress tracking

## Installation

### Prerequisites

- Python 3.8 or higher
- [Ollama](https://ollama.ai/) installed and running
- NCBI API key (recommended for higher rate limits)
- At least 8GB RAM (16GB+ recommended for larger models)

### Step 1: Clone the Repository

```bash
git clone https://github.com/Thomas-X-Garcia/ACMG-AutoEvidence.git
cd ACMG-AutoEvidence
```

### Step 2: Set Up Python Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Linux/macOS:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 3: Install and Configure Ollama

#### macOS
```bash
brew install ollama
ollama serve  # Start Ollama service
```

#### Linux
```bash
curl -fsSL https://ollama.ai/install.sh | sh
ollama serve  # Start Ollama service
```

#### Windows
Download and install from [Ollama website](https://ollama.ai/download/windows)

#### Pull Recommended Models
```bash
# Recommended: Best balance of speed and accuracy
ollama pull qwen2.5:32b

# For highest accuracy (requires ~40GB RAM)
ollama pull llama3.3:70b

# For limited resources (~4GB RAM)
ollama pull mistral:7b-instruct-q4_0
```

### Step 4: Get NCBI API Key

1. Go to [NCBI Account Settings](https://www.ncbi.nlm.nih.gov/account/settings/)
2. Create an account or log in
3. Generate an API key under "API Key Management"
4. Set environment variable:
   ```bash
   export NCBI_API_KEY="your-api-key-here"
   ```

## Quick Start

### 1. Convert BED File to JSON

```bash
python variant-alias-generator.py input.bed
```

This creates `input.json` with multiple variant representations.

### 2. Configure Analysis

```bash
# Copy example configuration
cp config.example.yaml config.yaml

# Edit config.yaml with your NCBI API key and preferences
nano config.yaml
```

### 3. Run ACMG Evidence Analysis

```bash
python acmg-autoevidence.py config.yaml
```

### 4. View Results

```bash
# Results are saved in the output directory specified in config
ls results/
cat results/variants_ACMG_criteria_summary.md
```

## Components

### Variant Alias Generator

Converts variant information from BED format to JSON with multiple naming conventions.

#### Usage

```bash
python variant-alias-generator.py [options] input_file [output_file]

Options:
  -h, --help     Show help message
  -d, --debug    Enable debug logging
  -s, --stream   Use streaming mode for large files
  -v, --version  Show version
```

#### Example

```bash
# Basic conversion
python variant-alias-generator.py variants.bed

# Stream large file
python variant-alias-generator.py --stream large_dataset.bed

# Debug mode
python variant-alias-generator.py --debug problematic.bed
```

### ACMG Evidence Analyzer

Analyzes genetic variants against scientific literature using LLMs.

#### Usage

```bash
python acmg-autoevidence.py [options] config_file

Options:
  -h, --help            Show help message
  --version            Show version
  --no-inference       Skip LLM inference step
  --search-only        Only perform literature search
  --collect-only       Only collect existing results
  --overwrite          Overwrite existing results
  --variant ID         Process only specific variant
  --limit N            Limit number of variants to process
  --parallel N         Number of parallel workers (default: 3)
  --format {csv,json,excel}  Output format (default: csv)
  --summary            Generate summary report
  --debug              Enable debug logging
  --log-file FILE      Save logs to file
  --dry-run            Show what would be done
```

#### Examples

```bash
# Process all variants
python acmg-autoevidence.py config.yaml

# Process specific variant with parallel processing
python acmg-autoevidence.py config.yaml --variant rs1234567 --parallel 8

# Generate summary report in Excel format
python acmg-autoevidence.py config.yaml --summary --format excel

# Debug mode with logging
python acmg-autoevidence.py config.yaml --debug --log-file analysis.log
```

## Complete Workflow

### Step-by-Step Process

1. **Prepare Input Data**
   ```bash
   # Your VEP-annotated BED file
   ls variants.bed
   ```

2. **Generate Variant Aliases**
   ```bash
   python variant-alias-generator.py variants.bed
   # Creates: variants.json
   ```

3. **Configure Analysis**
   ```bash
   cp config.example.yaml config.yaml
   # Edit config.yaml:
   # - Add NCBI API key
   # - Set variants_json_file: "./variants.json"
   # - Choose LLM model
   # - Define ACMG criteria questions
   ```

4. **Run Analysis**
   ```bash
   python acmg-autoevidence.py config.yaml --summary
   ```

5. **Review Results**
   ```bash
   # View summary
   cat results/variants_ACMG_criteria_summary.md
   
   # Open detailed results
   # CSV: results/variants_ACMG_criteria.csv
   # Individual variant folders contain article texts and analyses
   ```

## Configuration

### Basic Configuration (config.yaml)

```yaml
# NCBI API Configuration
api_key: "your-ncbi-api-key"  # Or use NCBI_API_KEY env variable

# Output directory
output_dir: "./results"

# Input variants
variants_json_file: "./variants.json"

# ACMG criteria questions
questions:
  PS3: "Does the manuscript provide functional evidence that the variant {comma-separated_variant_terms} has a damaging effect?"
  PM1: "Is the variant {comma-separated_variant_terms} located in a critical functional domain?"

# LLM Configuration
ollama_model: "qwen2.5:32b"  # Recommended model
langchain_settings:
  temperature: 0.05  # Low for consistency
  max_tokens: 300
```

### Advanced Configuration

For high-accuracy analysis with llama3.3:70b, use `config.advanced.yaml`:
- Optimized prompts with detailed ACMG definitions
- Near-zero temperature for maximum consistency
- Enhanced evidence evaluation framework

## Input/Output Formats

### Input: BED Format

Tab-delimited BED file with VEP annotations. Required columns:
- `CHROM`, `POS`, `ID`, `REF`, `ALT`
- `SYMBOL`, `Gene`, `Feature`
- `HGVSc`, `HGVSp`, `MANE_SELECT`
- `Existing_variation`, `Protein_position`, `Amino_acids`

### Intermediate: Variant JSON

```json
{
  "rsid": "rs121913343",
  "hgvs_full": "NM_007294.4(BRCA1):c.5123C>T(p.Ala1708Val)",
  "hgvsc": "BRCA1 c.5123C>T",
  "hgvsp_1": "BRCA1 p.A1708V",
  "spdi": "17:43092918:G:A"
}
```

### Output: Analysis Results

**CSV Format** includes:
- `variant_id`: Variant identifier
- `rsid`: dbSNP RS ID
- `article_id`: PMID or PMCID
- `criterion_code`: ACMG criterion
- `answer`: Yes/No/Unclear
- `reason`: Evidence explanation
- `timestamp`: Analysis time

**Directory Structure**:
```
results/
├── config_backup_*.yaml
├── rs1234567/
│   ├── variant_info.json
│   ├── search_results.json
│   ├── PMC7890123.txt
│   └── PMC7890123_PS3_result.json
├── variants_ACMG_criteria.csv
└── variants_ACMG_criteria_summary.md
```

## Performance Optimization

### Memory Management

- **Standard Mode**: Suitable for files up to ~1GB
- **Streaming Mode**: Use `--stream` flag for larger BED files
- **Reduce Workers**: Lower `max_workers` if running out of memory

### Processing Speed

```bash
# Increase parallel workers (if resources allow)
python acmg-autoevidence.py config.yaml --parallel 8

# Process subset for testing
python acmg-autoevidence.py config.yaml --limit 10

# Use faster model for initial screening
# Set ollama_model: "mistral:7b-instruct-q4_0" in config
```

### API Rate Limits

- With NCBI API key: 10 requests/second
- Without API key: 3 requests/second
- Adjust `api_request_delay` in config if needed

## Troubleshooting

### Common Issues

1. **Ollama Connection Failed**
   ```bash
   # Check if Ollama is running
   curl http://localhost:11434/api/tags
   
   # Start Ollama
   ollama serve
   
   # Verify model is installed
   ollama list
   ```

2. **No Articles Found**
   - Verify search terms in variant JSON
   - Check NCBI API key is valid
   - Try broader search terms
   - Enable `--verify-pmids` for accuracy

3. **Memory Issues**
   ```bash
   # Use streaming for BED conversion
   python variant-alias-generator.py --stream large.bed
   
   # Reduce parallel workers
   python acmg-autoevidence.py config.yaml --parallel 2
   
   # Use smaller LLM model
   ollama pull tinyllama:latest
   ```

4. **Missing Columns Error**
   - Ensure BED file has all required VEP columns
   - Column names are case-sensitive
   - File must be tab-delimited

### Debug Mode

```bash
# Enable detailed logging
python acmg-autoevidence.py config.yaml --debug --log-file debug.log

# Check specific variant processing
python variant-alias-generator.py --debug problem_variant.bed

# Monitor log in real-time
tail -f debug.log
```

### Validation

```bash
# Dry run to see what would be processed
python acmg-autoevidence.py config.yaml --dry-run

# Verify configuration
python -c "import yaml; yaml.safe_load(open('config.yaml'))"
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

### Development Setup

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests (when available)
pytest tests/

# Format code
black *.py

# Check code style
flake8 *.py
```

## Citation

If you use ACMG-AutoEvidence in your research, please cite:

```bibtex
@software{acmg_autoevidence,
  title = {ACMG-AutoEvidence: Automated extraction and classification of scientific evidence for ACMG variant interpretation},
  author = {Garcia, Thomas X.},
  year = {2025},
  url = {https://github.com/Thomas-X-Garcia/ACMG-AutoEvidence}
}
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Author

**Thomas X. Garcia, PhD, HCLD**  
GitHub: [@Thomas-X-Garcia](https://github.com/Thomas-X-Garcia)

## Acknowledgments

- NCBI for providing the E-utilities API
- Ollama team for the local LLM infrastructure
- LangChain for the LLM orchestration framework
- The clinical genetics community for ACMG guidelines and feedback

## Version History

- **v1.1.0** (2025) - Enhanced parallel processing, security improvements, optimized prompts
- **v1.0.0** (2025) - Initial release with core functionality

---

Made with ❤️ for the clinical genetics community