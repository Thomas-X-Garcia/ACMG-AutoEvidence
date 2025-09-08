# ACMG-AutoEvidence Variant Literature Analysis Tool

A production-ready Python tool for analyzing genetic variants in scientific literature using Large Language Models (LLMs). This tool automates the process of searching PubMed/PMC for articles related to genetic variants, retrieving full text when available, and analyzing them against ACMG criteria using Ollama-based LLMs.

## Features

- **Comprehensive Literature Search**: Searches PubMed and PMC for articles related to genetic variants
- **Full Text Retrieval**: Automatically retrieves full text from PMC when available, falls back to abstracts
- **LLM-Powered Analysis**: Uses Ollama LLMs to analyze articles against customizable ACMG criteria
- **Batch Processing**: Process multiple variants from JSON files or individual variants
- **Parallel Processing**: Concurrent searches and article retrieval for improved performance
- **Flexible Configuration**: YAML-based configuration with environment variable support
- **Robust Error Handling**: Comprehensive error handling with retry logic and graceful degradation
- **Multiple Output Formats**: CSV, JSON, and Excel output formats
- **Connection Pooling**: Efficient HTTP connection reuse for better performance
- **Security Enhancements**: Uses defusedxml for safe XML parsing, path validation
- **Progress Tracking**: Detailed logging and progress tracking for long-running analyses

## Table of Contents

- [Installation](#installation)
  - [Prerequisites](#prerequisites)
  - [Setup](#setup)
  - [Installing Ollama](#installing-ollama)
- [Configuration](#configuration)
  - [Basic Configuration](#basic-configuration)
  - [Advanced Settings](#advanced-settings)
- [Usage](#usage)
  - [Basic Usage](#basic-usage)
  - [Command Line Options](#command-line-options)
  - [Processing Modes](#processing-modes)
- [Input/Output](#inputoutput)
  - [Variants JSON Format](#variants-json-format)
  - [Output Structure](#output-structure)
  - [Output Formats](#output-formats)
- [Performance Tuning](#performance-tuning)
- [Troubleshooting](#troubleshooting)
- [API Reference](#api-reference)
- [Contributing](#contributing)

## Installation

### Prerequisites

- Python 3.8 or higher
- Ollama installed and running (for LLM analysis)
- NCBI API key (recommended for higher rate limits)
- At least 8GB RAM (16GB recommended for larger models)

### Setup

1. Clone the repository:
```bash
git clone https://github.com/Thomas-X-Garcia/ACMG-AutoEvidence.git
cd ACMG-AutoEvidence
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up your NCBI API key:
```bash
export NCBI_API_KEY="your-api-key-here"
```

To get an NCBI API key:
1. Go to [NCBI Account Settings](https://www.ncbi.nlm.nih.gov/account/settings/)
2. Create an account or log in
3. Generate an API key under "API Key Management"

### Installing Ollama

Ollama is required for LLM analysis. Install it based on your operating system:

#### macOS
```bash
brew install ollama
# Start Ollama service
ollama serve
```

#### Linux
```bash
curl -fsSL https://ollama.ai/install.sh | sh
# Start Ollama service
ollama serve
```

#### Windows
Download and install from [Ollama website](https://ollama.ai/download/windows)

#### Pull a Model
After installation, pull a model:
```bash
# Recommended models
ollama pull llama3.2:latest      # Fast, good accuracy
ollama pull mistral:latest       # Alternative option
ollama pull gemma2:27b           # Larger, more accurate

# List available models
ollama list
```

## Configuration

### Basic Configuration

Create a YAML configuration file (e.g., `config.yaml`):

```yaml
# API Configuration
api_key: "your-ncbi-api-key"  # Can also use NCBI_API_KEY environment variable

# Output directory for results
output_dir: "./results"

# Variant source (choose one)
variants_json_file: "./variants.json"  # For batch processing
# OR
search_terms: ["rs1234567", "BRCA1 p.Val1736Ala"]  # For single variant

# ACMG criteria questions
questions:
  PS3: "Does the manuscript provide functional evidence that the variant {comma-separated_variant_terms} has a damaging effect on protein function?"
  PM1: "Is the variant {comma-separated_variant_terms} located in a critical functional domain?"
  PP3: "Do computational predictions suggest the variant {comma-separated_variant_terms} is damaging?"

# Optional settings
ollama_model: "llama3.2:latest"  # Ollama model to use
max_workers: 3  # Number of parallel workers for searches/retrieval
```

### Advanced Settings

```yaml
# LangChain settings for LLM
langchain_settings:
  temperature: 0.1          # Lower = more deterministic
  stop_tokens: ["<|eot_id|>"]
  num_retries: 3

# Performance settings
efetch_chunk_size_pubmed: 100    # Articles per PubMed request
efetch_chunk_size_pmc: 50        # Articles per PMC request
api_request_delay: 0.15          # Seconds between API calls

# Retry settings for failed requests
retry_settings:
  retries: 3
  backoff_factor: 0.5

# Processing options
verify_pmids: false          # Additional verification of search results
search_only: false           # Only perform searches without retrieval
run_inference: true          # Run LLM analysis
ollama_overwrite: false      # Overwrite existing results
```

## Usage

### Basic Usage

Process all variants in a configuration:
```bash
python variant_literature_analysis.py config.yaml
```

### Command Line Options

```bash
# Process a specific variant
python variant_literature_analysis.py config.yaml --variant rs1234567

# Use parallel processing
python variant_literature_analysis.py config.yaml --parallel 5

# Search only (no article retrieval or analysis)
python variant_literature_analysis.py config.yaml --search-only

# Skip LLM analysis
python variant_literature_analysis.py config.yaml --no-inference

# Collect existing results
python variant_literature_analysis.py config.yaml --collect-only

# Overwrite existing results
python variant_literature_analysis.py config.yaml --overwrite

# Enable debug logging
python variant_literature_analysis.py config.yaml --debug --log-file debug.log

# Generate summary report
python variant_literature_analysis.py config.yaml --summary

# Different output formats
python variant_literature_analysis.py config.yaml --format excel

# Dry run (show what would be done)
python variant_literature_analysis.py config.yaml --dry-run
```

### Processing Modes

1. **Full Processing** (default): Search → Retrieve → Analyze
2. **Search Only**: Only search for PMIDs (`--search-only`)
3. **No Inference**: Search and retrieve but skip LLM analysis (`--no-inference`)
4. **Collect Only**: Gather existing results without processing (`--collect-only`)

## Input/Output

### Variants JSON Format

Create a JSON file with variant information:

```json
[
  {
    "rsid": "rs1234567",
    "hgvs_full": "NM_000059.3:c.5074G>A(p.Val1736Ala)",
    "hgvsp_1": "BRCA2 p.V1736A",
    "hgvsp_3": "BRCA2 p.Val1736Ala",
    "hgvsc": "BRCA2 c.5074G>A",
    "gene": "BRCA2"
  },
  {
    "rsid": "rs7654321",
    "hgvsc": "MLH1 c.215C>G",
    "hgvsp_1": "MLH1 p.P72R",
    "hgvsp_3": "MLH1 p.Pro72Arg"
  }
]
```

The tool will search using all provided variant identifiers.

### Output Structure

```
results/
├── config_backup_20240115_123456.yaml  # Configuration backup
├── rs1234567/                          # Variant-specific directory
│   ├── variant_info.json               # Variant metadata
│   ├── search_log.txt                  # Search process log
│   ├── search_results.json             # Structured search results
│   ├── PMC7890123.txt                  # Retrieved article text
│   ├── 12345678.txt                    # Retrieved abstract
│   ├── PMC7890123_PS3_result.json     # Analysis result (JSON)
│   └── PMC7890123_PS3_result.txt      # Analysis result (text)
├── variants_ACMG_criteria.csv          # Combined results (all variants)
└── variants_ACMG_criteria_summary.md   # Summary report
```

### Output Formats

#### CSV Output
Contains columns:
- `variant_id`: Variant identifier
- `rsid`: RS identifier (if available)
- `article_id`: PMID or PMCID
- `article_type`: PMID or PMCID
- `criterion_code`: ACMG criterion evaluated
- `answer`: Yes/No/Unclear/Error
- `reason`: Explanation for the answer
- `timestamp`: Analysis timestamp

#### JSON Output
```json
[
  {
    "variant_id": "rs1234567",
    "rsid": "rs1234567",
    "article_id": "PMC7890123",
    "article_type": "PMCID",
    "criterion_code": "PS3",
    "answer": "Yes",
    "reason": "The study demonstrates reduced protein function...",
    "timestamp": "2024-01-15T10:30:45"
  }
]
```

#### Summary Report
Markdown format with:
- Total variants analyzed
- Articles processed per variant
- Results breakdown by criterion
- Success/error statistics

## Performance Tuning

### Parallel Processing

Adjust the number of workers based on your system:
```bash
# Default: 3 workers
python variant_literature_analysis.py config.yaml

# Increase for better performance (if you have the resources)
python variant_literature_analysis.py config.yaml --parallel 8
```

### Memory Management

For systems with limited memory:
1. Reduce chunk sizes in configuration
2. Process fewer variants at once using `--limit`
3. Use a smaller LLM model

### API Rate Limits

- With API key: 10 requests/second
- Without API key: 3 requests/second
- Adjust `api_request_delay` accordingly

### LLM Model Selection

Choose models based on your needs:
- **Fast processing**: `llama3.2:latest` (3B parameters)
- **Better accuracy**: `mistral:latest` (7B parameters)
- **Best accuracy**: `gemma2:27b` (27B parameters)

## Troubleshooting

### Common Issues

1. **LLM Connection Failed**
   ```bash
   # Check if Ollama is running
   curl http://localhost:11434/api/tags
   
   # Start Ollama if needed
   ollama serve
   
   # Pull required model
   ollama pull llama3.2:latest
   ```

2. **No Articles Found**
   - Verify search terms are appropriate
   - Check NCBI API key is valid
   - Try broader search terms
   - Use `--verify-pmids` for more accurate results

3. **Rate Limit Errors**
   - Increase `api_request_delay` in configuration
   - Ensure you're using an NCBI API key
   - Reduce parallel workers

4. **Memory Issues**
   ```bash
   # Process variants in smaller batches
   python variant_literature_analysis.py config.yaml --limit 10
   
   # Use a smaller model
   ollama pull tinyllama:latest
   ```

5. **XML Parsing Errors**
   - Usually indicates malformed NCBI response
   - Check network connectivity
   - Retry after a few minutes

### Debug Mode

Enable detailed logging:
```bash
python variant_literature_analysis.py config.yaml --debug --log-file debug.log

# View the log
tail -f debug.log
```

### Checking Results

```bash
# Count results
find results -name "*_result.json" | wc -l

# Check for errors
grep -r "Error" results/*/search_log.txt

# View a specific result
cat results/rs1234567/PMC123456_PS3_result.json | jq .
```

## API Reference

### Main Classes

#### VariantProcessor
Handles processing of individual variants with parallel support.

```python
processor = VariantProcessor(config, session, llm, prompt_template, output_parser)
articles_count, results = processor.process_variant(variant)
```

#### SearchResult
Container for search results from PubMed.

```python
@dataclass
class SearchResult:
    pmids: List[str]
    is_valid: bool
    search_term: str
    error_message: Optional[str]
```

### Key Functions

#### search_pubmed_for_pmids
Search PubMed for articles related to a term.

```python
result = search_pubmed_for_pmids(
    search_term="BRCA1 p.Val1736Ala",
    api_key="your-key",
    session=None,  # Uses connection pool if None
    api_delay=0.15
)
```

#### analyze_with_llm
Analyze article text with LLM for ACMG criteria.

```python
analysis = analyze_with_llm(
    llm=ollama_llm,
    prompt_template=template,
    output_parser=parser,
    manuscript_text=article_text,
    question="Does this article provide functional evidence..."
)
```

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

### Development Setup

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
pytest tests/

# Run linting
flake8 variant_literature_analysis.py
mypy variant_literature_analysis.py

# Format code
black variant_literature_analysis.py
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Citation

If you use this tool in your research, please cite:

```bibtex
@software{variant_literature_analysis,
  title = {ACMG-AutoEvidence: Variant Literature Analysis Tool},
  author = {Garcia, Thomas X.},
  year = {2024},
  version = {1.1.0},
  url = {https://github.com/Thomas-X-Garcia/ACMG-AutoEvidence}
}
```

## Author

**Thomas X. Garcia, PhD, HCLD**

## Acknowledgments

- NCBI for providing the E-utilities API
- Ollama team for the local LLM infrastructure
- LangChain for the LLM orchestration framework
- Contributors and users who have provided feedback

## Changelog

### Version 1.1.0 (Current)
- Added parallel processing support for searches and retrieval
- Implemented connection pooling for better performance
- Added security improvements (defusedxml, path validation)
- Fixed session request method override bug
- Added streaming mode support
- Improved error handling and retry logic
- Added support for more LLM models
- Enhanced configuration validation

### Version 1.0.0
- Initial release with core functionality
- PubMed/PMC search and retrieval
- Ollama LLM integration
- ACMG criteria analysis
- Multiple output formats