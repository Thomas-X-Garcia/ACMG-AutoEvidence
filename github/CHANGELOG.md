# Changelog

All notable changes to ACMG-AutoEvidence will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Support for additional ACMG criteria templates
- Integration tests for end-to-end workflow
- Docker container support
- Web interface for easier usage

### Changed
- Improved prompt templates for better accuracy
- Enhanced error messages for troubleshooting

## [1.1.0] - 2025-01-17

### Added
- Parallel processing support for literature searches and article retrieval
- Connection pooling for improved HTTP performance  
- Security enhancements using defusedxml for safe XML parsing
- Path validation to prevent directory traversal attacks
- Streaming mode for memory-efficient BED file processing
- Support for multi-allelic variants
- Chromosome and position validation
- Enhanced prompt templates for ACMG criteria classification
- Advanced configuration file for high-accuracy analysis
- Support for llama3.3:70b and qwen2.5:32b models
- Comprehensive troubleshooting documentation

### Changed
- Renamed scripts for clarity:
  - `bed_to_json_converter.py` → `variant-alias-generator.py`
  - `variant_literature_analysis.py` → `acmg-autoevidence.py`
- Updated default LLM model to qwen2.5:32b for better balance
- Reduced default temperature to 0.05 for consistency
- Improved error handling for malformed input data
- Enhanced logging with colored output
- Better handling of amino acid parsing edge cases

### Fixed
- Session request method override bug that could cause infinite recursion
- Cache invalidation issues
- Bounds checking in BED file column extraction
- JSON parsing error handling for NCBI API responses
- Memory leaks in large file processing

### Security
- Replaced xml.etree with defusedxml to prevent XML bomb attacks
- Added input validation for file paths
- Sanitized user inputs in configuration

## [1.0.0] - 2025-01-10

### Added
- Initial release of ACMG-AutoEvidence
- Variant Alias Generator for BED to JSON conversion
- ACMG Evidence Analyzer for literature analysis
- Support for PubMed and PMC searches
- Full text retrieval from PMC
- Integration with Ollama for LLM analysis
- YAML-based configuration system
- Multiple output formats (CSV, JSON, Excel)
- Comprehensive logging system
- Example files and documentation

### Features
- Dynamic column detection in BED files
- Multiple variant nomenclature support (HGVS, SPDI, rsID)
- Robust parsing of complex variants
- Flexible ACMG criteria questions
- Progress tracking and statistics
- Error recovery and retry logic

## [0.9.0-beta] - 2024-12-15

### Added
- Beta release for testing
- Core functionality implementation
- Basic documentation

---

## Version Guidelines

- **Major version (X.0.0)**: Incompatible API changes
- **Minor version (0.X.0)**: New functionality in a backwards compatible manner
- **Patch version (0.0.X)**: Backwards compatible bug fixes

## Upgrade Instructions

### From 1.0.0 to 1.1.0
1. Update script names in any automation:
   - `bed_to_json_converter.py` → `variant-alias-generator.py`
   - `variant_literature_analysis.py` → `acmg-autoevidence.py`
2. Review new configuration options in `config.example.yaml`
3. Consider using new recommended models for better accuracy
4. Update any custom prompts to use the enhanced template format

[Unreleased]: https://github.com/Thomas-X-Garcia/ACMG-AutoEvidence/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/Thomas-X-Garcia/ACMG-AutoEvidence/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/Thomas-X-Garcia/ACMG-AutoEvidence/releases/tag/v1.0.0