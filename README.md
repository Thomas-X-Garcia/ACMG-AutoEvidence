# ACMG-AutoEvidence

A comprehensive suite of Python tools for analyzing genetic variants, including format conversion and literature analysis using Large Language Models (LLMs).

## Overview

This repository contains two main tools that work together to analyze genetic variants:

1. **BED to JSON Converter** - Converts BED files with variant information into JSON format with multiple alias representations
2. **Variant Literature Analysis Tool** - Searches scientific literature for variant information and analyzes it using LLMs against ACMG criteria

## Quick Start

### Prerequisites

- Python 3.8 or higher
- Ollama (for LLM analysis)
- NCBI API key (recommended)

### Installation

```bash
# Clone the repository
git clone https://github.com/Thomas-X-Garcia/ACMG-AutoEvidence.git
cd ACMG-AutoEvidence

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Ollama (macOS/Linux)
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull llama3.2:latest
```

### Basic Usage

1. **Convert BED file to JSON:**
```bash
python bed_to_json_converter.py input.bed
```

2. **Analyze variants in literature:**
```bash
# Copy and edit the example config
cp config.example.yaml config.yaml
# Edit config.yaml with your NCBI API key

# Run analysis
python variant_literature_analysis.py config.yaml
```

## Tools Documentation

### BED to JSON Converter

Converts variant information from BED format to JSON with multiple naming conventions.

**Features:**
- Dynamic column detection
- Multiple variant representations (HGVS, SPDI, rsID)
- Handles complex variant types (frameshifts, deletions, insertions)
- Streaming mode for large files
- Comprehensive validation

[Full Documentation →](bed_to_json_converter_README.md)

### Variant Literature Analysis Tool

Analyzes genetic variants against scientific literature using LLMs.

**Features:**
- PubMed/PMC literature search
- Full text retrieval when available
- LLM-powered analysis against ACMG criteria
- Parallel processing for performance
- Multiple output formats (CSV, JSON, Excel)

[Full Documentation →](variant_literature_analysis_README.md)

## Workflow Example

Complete workflow from BED file to ACMG analysis:

```bash
# Step 1: Convert BED to JSON
python bed_to_json_converter.py variants.bed

# Step 2: Configure analysis
cp config.example.yaml config.yaml
# Edit config.yaml:
# - Add your NCBI API key
# - Set variants_json_file: "./variants.json"

# Step 3: Run literature analysis
python variant_literature_analysis.py config.yaml --summary

# Step 4: View results
ls results/
cat results/variants_ACMG_criteria_summary.md
```

## Configuration

### Example Configuration Files

- `config.example.yaml` - Example configuration for literature analysis
- `variants.example.json` - Example variant JSON format

### Environment Variables

```bash
# NCBI API key (recommended)
export NCBI_API_KEY="your-api-key-here"

# Ollama host (if not localhost)
export OLLAMA_HOST="http://your-ollama-server:11434"
```

## File Formats

### Input BED Format

Tab-delimited BED file with VEP annotations. Required columns:
- CHROM, POS, ID, REF, ALT
- SYMBOL, Gene, Feature
- HGVSc, HGVSp
- Existing_variation

### Variant JSON Format

```json
{
  "rsid": "rs1234567",
  "hgvs_full": "NM_000059.3:c.5074G>A(p.Val1736Ala)",
  "hgvsc": "BRCA2 c.5074G>A",
  "hgvsp_1": "BRCA2 p.V1736A",
  "spdi": "13:32332591:G:A"
}
```

## Performance Tips

1. **Use parallel processing:**
   ```bash
   python variant_literature_analysis.py config.yaml --parallel 8
   ```

2. **Process large BED files with streaming:**
   ```bash
   python bed_to_json_converter.py --stream large_file.bed
   ```

3. **Limit variants for testing:**
   ```bash
   python variant_literature_analysis.py config.yaml --limit 10
   ```

## Troubleshooting

### Common Issues

1. **Ollama not found:**
   ```bash
   # Check if Ollama is running
   curl http://localhost:11434/api/tags
   
   # Start Ollama
   ollama serve
   ```

2. **NCBI rate limits:**
   - Get an API key from [NCBI](https://www.ncbi.nlm.nih.gov/account/settings/)
   - Increase `api_request_delay` in config

3. **Memory issues:**
   - Use `--stream` flag for large BED files
   - Reduce `max_workers` in config
   - Use smaller LLM models

### Debug Mode

```bash
# Enable debug logging
python variant_literature_analysis.py config.yaml --debug --log-file debug.log

# Check specific variant processing
python bed_to_json_converter.py --debug problematic.bed
```

## Development

### Project Structure

```
.
├── bed_to_json_converter.py         # BED to JSON conversion tool
├── variant_literature_analysis.py    # Literature analysis tool
├── requirements.txt                  # Production dependencies
├── requirements-dev.txt             # Development dependencies
├── config.example.yaml              # Example configuration
├── variants.example.json            # Example variant format
└── README.md                        # This file
```

### Running Tests

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
pytest tests/

# Run with coverage
pytest --cov=. tests/
```

### Code Quality

```bash
# Format code
black *.py

# Check style
flake8 *.py

# Type checking
mypy *.py
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Citations

If you use these tools in your research, please cite:

Garcia, T.X. (2025) ACMG-AutoEvidence: A comprehensive toolkit for automated genetic variant literature analysis using local LLMs to evaluate ACMG criteria. https://github.com/Thomas-X-Garcia/ACMG-AutoEvidence

## Acknowledgments

- NCBI for E-utilities API access
- Ollama team for local LLM infrastructure
- LangChain for LLM orchestration
- All contributors and users

## Author

**Thomas X. Garcia, PhD, HCLD**

## Support

- **Issues**: [GitHub Issues](https://github.com/Thomas-X-Garcia/ACMG-AutoEvidence/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Thomas-X-Garcia/ACMG-AutoEvidence/discussions)

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.

---

Made with ❤️ for the bioinformatics community
