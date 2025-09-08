# BED to JSON Converter for Variant Aliases

A Python script that converts BED files containing variant information into JSON format with multiple alias representations for each variant. This tool is particularly useful for bioinformatics workflows that need to work with different variant nomenclatures.

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
- [Input Format](#input-format)
- [Output Format](#output-format)
- [Command Line Options](#command-line-options)
- [Examples](#examples)
- [Performance Considerations](#performance-considerations)
- [Variant Nomenclature](#variant-nomenclature)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

## Features

- **Dynamic Column Detection**: Automatically detects column positions from the header line
- **Multiple Variant Representations**: Generates various alias formats including:
  - HGVS full notation (transcript + gene + cDNA + protein)
  - HGVSc (gene + cDNA change)
  - HGVSp with 3-letter amino acids (with and without "p." prefix)
  - HGVSp with 1-letter amino acids (with and without "p." prefix)
  - SPDI notation
  - rsID extraction from comma-separated lists
- **MANE Transcript Support**: Prioritizes MANE SELECT transcripts when available
- **Robust Parsing**: Handles various HGVSp formats including:
  - Standard missense variants (p.Ala213Val)
  - Frameshift variants (p.Glu386GlyfsTer6)
  - Deletions (p.Asp999_Ser1001del)
  - Insertions (p.Pro270_Ala271insLysLeu)
  - Duplications (p.Gln34_Gln38dup)
  - Extensions (p.*110Leuext*17)
- **Fallback Mechanisms**: Creates entries from Protein_position and Amino_acids columns when HGVSp is missing
- **Validation**: Validates chromosome names and genomic positions
- **Multi-allelic Support**: Detects and processes variants with multiple alternate alleles
- **Streaming Mode**: Memory-efficient processing for large files
- **Comprehensive Logging**: Detailed logging with statistics and error reporting
- **Debug Mode**: Optional verbose output for troubleshooting

## Requirements

- Python 3.8 or higher
- No external dependencies (uses only Python standard library)

## Installation

### Direct Download

```bash
# Download the script
wget https://github.com/your-repo/bed_to_json_converter.py
# or
curl -O https://github.com/your-repo/bed_to_json_converter.py

# Make it executable (optional)
chmod +x bed_to_json_converter.py
```

### Clone Repository

```bash
git clone https://github.com/Thomas-X-Garcia/ACMG-AutoEvidence.git
cd ACMG-AutoEvidence
```

## Usage

### Basic Usage

```bash
python bed_to_json_converter.py input.bed
```

This will create an output file named `input.json` in the same directory.

### Specify Output File

```bash
python bed_to_json_converter.py input.bed output.json
```

### Streaming Mode (for large files)

```bash
python bed_to_json_converter.py --stream large_input.bed
```

### Debug Mode

```bash
python bed_to_json_converter.py --debug input.bed
```

### Show Version

```bash
python bed_to_json_converter.py --version
```

## Input Format

The script expects a tab-delimited BED file conforming to the [VEP output format](https://www.ensembl.org/info/docs/tools/vep/vep_formats.html#output) with the following required columns in the header:

| Column Name | Description | Example |
|------------|-------------|---------|
| CHROM | Chromosome | chr2 |
| POS | Position (1-based) | 219420154 |
| ID | Variant identifier | chr2_219420154_C/T |
| REF | Reference allele | C |
| ALT | Alternate allele(s) | T |
| SYMBOL | Gene symbol | DES |
| Existing_variation | Known variant IDs (comma-separated) | rs41272699,CM117560 |
| Gene | Ensembl gene ID | ENSG00000175084 |
| Feature | Ensembl transcript ID | ENST00000373960 |
| Protein_position | Amino acid position | 213 |
| Amino_acids | Amino acid change | A/V |
| MANE_SELECT | MANE transcript | NM_001927.4 |
| HGVSc | cDNA change notation | ENST00000373960.4:c.638C>T |
| HGVSp | Protein change notation | ENSP00000363071.3:p.Ala213Val |

**Notes**: 
- The script will automatically detect column positions based on the header line, so the order doesn't matter as long as all required columns are present
- The script handles BED files with additional columns beyond those listed above
- Multi-allelic variants (comma-separated ALT values) are detected and logged

## Output Format

The script generates a JSON array where each element represents a variant with multiple alias representations:

```json
[
    {
        "internal_id": "chr2_219420154_C/T",
        "rsid": "rs41272699",
        "spdi": "2:219420153:C:T",
        "hgvs_full": "NM_001927.4(DES):c.638C>T(p.Ala213Val)",
        "hgvsc": "DES c.638C>T",
        "hgvsp_3p": "DES p.Ala213Val",
        "hgvsp_3": "DES Ala213Val",
        "hgvsp_1p": "DES p.A213V",
        "hgvsp_1": "DES A213V"
    }
]
```

### Field Descriptions

| Field | Description |
|-------|-------------|
| internal_id | Original variant ID from the BED file |
| rsid | dbSNP reference SNP ID (if available) |
| spdi | SPDI notation (sequence:position:deleted:inserted) with 0-based position |
| hgvs_full | Complete HGVS notation with transcript, gene, and changes |
| hgvsc | Gene symbol with cDNA change |
| hgvsp_3p | Gene symbol with 3-letter amino acid change (with p.) |
| hgvsp_3 | Gene symbol with 3-letter amino acid change (without p.) |
| hgvsp_1p | Gene symbol with 1-letter amino acid change (with p.) |
| hgvsp_1 | Gene symbol with 1-letter amino acid change (without p.) |

## Command Line Options

```
usage: bed_to_json_converter.py [-h] [--debug] [--stream] [--version] input_file [output_file]

Convert BED file with variant information to JSON format with aliases

positional arguments:
  input_file         Input BED file containing variant information
  output_file        Output JSON file (default: input_file with .json extension)

optional arguments:
  -h, --help         show this help message and exit
  --debug, -d        Enable debug logging
  --stream, -s       Use streaming mode for large files
  --version, -v      show program's version number and exit
```

## Examples

### Example 1: Basic Conversion

```bash
python bed_to_json_converter.py variants.bed
```

Output: `variants.json`

### Example 2: Custom Output Name

```bash
python bed_to_json_converter.py patient_001.bed patient_001_aliases.json
```

### Example 3: Debug Mode for Troubleshooting

```bash
python bed_to_json_converter.py --debug problematic_file.bed
```

This will show detailed processing information for each row.

### Example 4: Processing Large Files

```bash
# Use streaming mode to process files too large to fit in memory
python bed_to_json_converter.py --stream large_dataset.bed
```

### Example 5: Processing Multiple Files

```bash
for bed_file in *.bed; do
    python bed_to_json_converter.py "$bed_file"
done
```

### Example 6: Pipeline Integration

```bash
# Run VEP and convert output to JSON
vep -i variants.vcf -o variants.bed --tab --fields "Uploaded_variation,Location,Allele,Gene,Feature,Feature_type,Consequence,cDNA_position,CDS_position,Protein_position,Amino_acids,Codons,Existing_variation,IMPACT,DISTANCE,STRAND,FLAGS,SYMBOL,SYMBOL_SOURCE,HGNC_ID,BIOTYPE,CANONICAL,TSL,APPRIS,CCDS,ENSP,SWISSPROT,TREMBL,UNIPARC,REFSEQ_MATCH,GIVEN_REF,USED_REF,BAM_EDIT,GENE_PHENO,SIFT,PolyPhen,DOMAINS,HGVS_OFFSET,GMAF,AFR_MAF,AMR_MAF,EAS_MAF,EUR_MAF,SAS_MAF,AA_MAF,EA_MAF,ExAC_MAF,ExAC_Adj_MAF,ExAC_AFR_MAF,ExAC_AMR_MAF,ExAC_EAS_MAF,ExAC_FIN_MAF,ExAC_NFE_MAF,ExAC_OTH_MAF,ExAC_SAS_MAF,CLIN_SIG,SOMATIC,PHENO,PUBMED,VAR_SYNONYMS,MOTIF_NAME,MOTIF_POS,HIGH_INF_POS,MOTIF_SCORE_CHANGE,TRANSCRIPTION_FACTORS,MANE_SELECT,MANE_PLUS_CLINICAL,HGVSc,HGVSp,HGVSg"

python bed_to_json_converter.py variants.bed
```

## Performance Considerations

### Memory Usage

- **Standard Mode**: Loads all variants into memory before writing. Suitable for files up to ~1GB
- **Streaming Mode**: Processes and writes variants one at a time. Use for larger files with `--stream` flag

### Processing Speed

- Typical processing speed: ~10,000-50,000 variants per second (depending on system)
- Debug mode significantly slows processing due to verbose logging

### File Size Limits

- Standard mode: Limited by available system memory
- Streaming mode: No practical limit on file size
- Maximum recommended variants per file: 10 million (standard mode)

## Variant Nomenclature

The script follows standard variant nomenclature conventions as defined by the [Human Genome Variation Society (HGVS)](http://varnomen.hgvs.org/).

### Supported Variant Types

1. **Substitutions**: p.Arg156Cys
2. **Deletions**: p.Ala3_Ser5del
3. **Insertions**: p.His4_Gln5insAla
4. **Duplications**: p.Ala3_Ser5dup
5. **Frameshift**: p.Arg97ProfsTer23
6. **Extensions**: p.*110Glnext*17

### Amino Acid Codes

The script converts between 3-letter and 1-letter amino acid codes:

| 3-letter | 1-letter | Amino Acid |
|----------|----------|------------|
| Ala | A | Alanine |
| Arg | R | Arginine |
| Asn | N | Asparagine |
| Asp | D | Aspartic acid |
| Cys | C | Cysteine |
| Gln | Q | Glutamine |
| Glu | E | Glutamic acid |
| Gly | G | Glycine |
| His | H | Histidine |
| Ile | I | Isoleucine |
| Leu | L | Leucine |
| Lys | K | Lysine |
| Met | M | Methionine |
| Phe | F | Phenylalanine |
| Pro | P | Proline |
| Ser | S | Serine |
| Thr | T | Threonine |
| Trp | W | Tryptophan |
| Tyr | Y | Tyrosine |
| Val | V | Valine |
| Ter/* | * | Stop codon |
| Xaa | X | Unknown |

## Troubleshooting

### Common Issues

1. **Missing columns error**
   - Ensure your BED file has all required columns in the header
   - Column names are case-sensitive
   - Check that your file is tab-delimited, not space-delimited

2. **No variants processed**
   - Check if variants are being skipped (e.g., Sniffles2 variants)
   - Enable debug mode to see detailed processing information
   - Verify file encoding is UTF-8

3. **Invalid chromosome warnings**
   - The script validates chromosome names (chr1-22, chrX, chrY, chrM/MT)
   - Non-standard chromosome names will be logged but processed

4. **Parsing errors**
   - Verify HGVSp notation follows standard format
   - Check for special characters or encoding issues
   - Some complex variants may not be parseable

5. **Memory issues with large files**
   - Use `--stream` flag for files larger than available RAM
   - Consider splitting very large files into chunks

### Log Messages

The script provides detailed statistics after processing:

```
=== Conversion Statistics ===
Total rows read: 1000
Variants processed: 950
Rows skipped: 40
Errors encountered: 10
Rows missing rsID: 100
Rows missing HGVSp: 30
Invalid chromosomes: 5
Invalid positions: 2
Success rate: 95.0%
```

### Debug Mode Output

Debug mode provides detailed information for each row:

```
2024-01-15 10:23:45 - DEBUG - Row 2: Processing variant
2024-01-15 10:23:45 - DEBUG - Found rsID: rs1234567
2024-01-15 10:23:45 - INFO - Row 2: Multi-allelic variant with 2 alternate alleles
2024-01-15 10:23:45 - DEBUG - Parsed HGVSp: ('ENSP00000123456.1', '123', 'Ala', 'Val')
```

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

### Development Setup

1. Clone the repository
2. Create a virtual environment (optional but recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install development dependencies (if any)
4. Run tests (when available)

### Code Style

- Follow PEP 8 guidelines
- Add docstrings to all functions
- Include type hints where appropriate
- Update this README for any new features
- Add unit tests for new functionality

### Submitting Changes

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This script is provided under the MIT License. See LICENSE file for details.

## Author

- Thomas X. Garcia, PhD, HCLD
- Date: June 3, 2025
- Version: 2.1.0

## Changelog

### Version 2.1.0 (Current)
- Added security improvements and input validation
- Added streaming mode for large file support
- Added multi-allelic variant detection
- Added chromosome and position validation
- Improved error handling for malformed amino acid fields
- Added support for extension variants
- Fixed bounds checking in column value extraction
- Added unknown amino acid (Xaa/X) support

### Version 2.0.0
- Complete rewrite with dynamic column detection
- Added SPDI notation support
- Improved MANE transcript handling
- Better error handling and logging

### Version 1.0.0
- Initial release with basic BED to JSON conversion

## Acknowledgments

- HGVS nomenclature guidelines from the Human Genome Variation Society
- BED format specification from UCSC Genome Browser
- VEP output format documentation from Ensembl