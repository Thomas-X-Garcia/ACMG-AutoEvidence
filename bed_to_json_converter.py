#!/usr/bin/env python3
"""
BED to JSON Converter for Variant Aliases

This script converts BED files containing variant information into JSON format
with multiple alias representations for each variant.

Usage:
    python bed_to_json_converter.py <input_bed_file> [output_json_file]

Author: Thomas X. Garcia, PhD, HCLD
Date: June 3, 2025
Version: 2.1.0
"""

import sys
import os
import json
import csv
import re
import logging
import argparse
from typing import Dict, List, Optional, Tuple, Iterator
from datetime import datetime
from collections import OrderedDict
from pathlib import Path

__version__ = "2.1.0"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Define the mapping from 3-letter codes to 1-letter codes
AA_3_TO_1_MAP = {
    'Ala': 'A', 'Arg': 'R', 'Asn': 'N', 'Asp': 'D',
    'Cys': 'C', 'Gln': 'Q', 'Glu': 'E', 'Gly': 'G',
    'His': 'H', 'Ile': 'I', 'Leu': 'L', 'Lys': 'K',
    'Met': 'M', 'Phe': 'F', 'Pro': 'P', 'Ser': 'S',
    'Thr': 'T', 'Trp': 'W', 'Tyr': 'Y', 'Val': 'V',
    'Ter': '*', 'Stop': '*', 'Xaa': 'X'  # Added unknown amino acid
}

# Create reverse mapping
AA_1_TO_3_MAP = {v: k for k, v in AA_3_TO_1_MAP.items() if len(v) == 1}

# Valid chromosome names
VALID_CHROMOSOMES = {f"chr{i}" for i in range(1, 23)} | {"chrX", "chrY", "chrM", "chrMT"}
VALID_CHROMOSOMES.update({str(i) for i in range(1, 23)} | {"X", "Y", "M", "MT"})


class VariantParser:
    """Handles parsing of variant information from BED file rows."""
    
    def __init__(self, debug: bool = False):
        self.debug = debug
        self.logger = logging.getLogger(self.__class__.__name__)
        if debug:
            self.logger.setLevel(logging.DEBUG)
    
    def parse_hgvsp(self, hgvsp: str) -> Optional[Tuple[str, str, str, str]]:
        """
        Parse HGVSp notation to extract protein ID and change information.
        
        Args:
            hgvsp: HGVSp notation (e.g., "ENSP00000478421.2:p.Ala446Thr")
            
        Returns:
            Tuple of (protein_id, position, ref_aa, alt_aa) or None if parsing fails
        """
        if not hgvsp or hgvsp == '-':
            return None
        
        # Handle URL-encoded equals sign (%3D)
        hgvsp = hgvsp.replace('%3D', '=')
        
        # Skip synonymous variants (e.g., p.Gly22=)
        if '=' in hgvsp:
            self.logger.debug(f"Skipping synonymous variant: {hgvsp}")
            return None
        
        # Pattern to match standard HGVSp notation
        # Handles various formats including p.Ala446Thr, p.(Ala446Thr), etc.
        pattern = r'^([^:]+):p\.?\(?([A-Za-z]{3})(\d+)([A-Za-z]{3}|\*)\)?$'
        match = re.match(pattern, hgvsp)
        
        if match:
            protein_id, ref_aa, position, alt_aa = match.groups()
            return protein_id, position, ref_aa, alt_aa
        
        # Try to handle frameshift variants (e.g., p.Glu386GlyfsTer6)
        fs_pattern = r'^([^:]+):p\.?\(?([A-Za-z]{3})(\d+)([A-Za-z]{3})fs(?:Ter(\d+))?'
        fs_match = re.match(fs_pattern, hgvsp)
        if fs_match:
            groups = fs_match.groups()
            protein_id, ref_aa, position, alt_aa = groups[0:4]
            return protein_id, position, ref_aa, f"{alt_aa}fs"
        
        # Handle deletions (e.g., p.Asp999_Ser1001del)
        del_pattern = r'^([^:]+):p\.?\(?([A-Za-z]{3})(\d+)(?:_[A-Za-z]{3}\d+)?del'
        del_match = re.match(del_pattern, hgvsp)
        if del_match:
            protein_id, ref_aa, position = del_match.groups()
            return protein_id, position, ref_aa, "del"
        
        # Handle insertions (e.g., p.Pro270_Ala271insLysLeu)
        ins_pattern = r'^([^:]+):p\.?\(?([A-Za-z]{3})(\d+)_[A-Za-z]{3}\d+ins[A-Za-z]+'
        ins_match = re.match(ins_pattern, hgvsp)
        if ins_match:
            protein_id, ref_aa, position = ins_match.groups()
            return protein_id, position, ref_aa, "ins"
        
        # Handle duplications (e.g., p.Gln34_Gln38dup)
        dup_pattern = r'^([^:]+):p\.?\(?([A-Za-z]{3})(\d+)(?:_[A-Za-z]{3}\d+)?dup'
        dup_match = re.match(dup_pattern, hgvsp)
        if dup_match:
            protein_id, ref_aa, position = dup_match.groups()
            return protein_id, position, ref_aa, "dup"
        
        # Handle extensions (e.g., p.*110Leuext*17)
        ext_pattern = r'^([^:]+):p\.?\(?\*(\d+)([A-Za-z]{3})ext'
        ext_match = re.match(ext_pattern, hgvsp)
        if ext_match:
            protein_id, position, new_aa = ext_match.groups()
            return protein_id, position, "*", f"{new_aa}ext"
        
        self.logger.warning(f"Could not parse HGVSp notation: {hgvsp}")
        return None
    
    def parse_hgvsc(self, hgvsc: str) -> Optional[Tuple[str, str]]:
        """
        Parse HGVSc notation to extract transcript ID and change.
        
        Args:
            hgvsc: HGVSc notation (e.g., "ENST00000616016.5:c.1336G>A")
            
        Returns:
            Tuple of (transcript_id, change) or None if parsing fails
        """
        if not hgvsc or hgvsc == '-':
            return None
        
        parts = hgvsc.split(':', 1)
        if len(parts) == 2:
            return parts[0], parts[1]
        else:
            self.logger.warning(f"Could not parse HGVSc notation: {hgvsc}")
            return None
    
    def extract_rsid(self, existing_variation: str) -> Optional[str]:
        """
        Extract rsID from existing_variation field which may contain comma-separated values.
        
        Args:
            existing_variation: String that may contain multiple comma-separated IDs
            
        Returns:
            The rsID (starting with 'rs') or None if not found
        """
        if not existing_variation or existing_variation == '-':
            return None
        
        # Split by comma and look for rsID
        variants = existing_variation.split(',')
        for variant in variants:
            variant = variant.strip()
            if variant.lower().startswith('rs') and variant[2:].isdigit():
                self.logger.debug(f"Found rsID: {variant}")
                return variant
        
        # No rsID found
        self.logger.debug(f"No rsID found in: {existing_variation}")
        return None
    
    def convert_aa_3_to_1(self, aa_3letter: str) -> str:
        """
        Convert 3-letter amino acid code to 1-letter code.
        
        Args:
            aa_3letter: 3-letter amino acid code (e.g., "Ala")
            
        Returns:
            1-letter amino acid code or original if not found
        """
        # Handle special cases
        if aa_3letter in ['del', 'ins', 'dup', 'fs', 'ext']:
            return aa_3letter
        
        # Handle frameshift variants
        if 'fs' in aa_3letter:
            # Extract the amino acid part before 'fs'
            aa_part = aa_3letter.replace('fs', '')
            if aa_part:
                aa_1letter = AA_3_TO_1_MAP.get(aa_part.capitalize(), aa_part)
                return f"{aa_1letter}fs"
            return aa_3letter
        
        # Handle extension variants
        if 'ext' in aa_3letter:
            aa_part = aa_3letter.replace('ext', '')
            if aa_part:
                aa_1letter = AA_3_TO_1_MAP.get(aa_part.capitalize(), aa_part)
                return f"{aa_1letter}ext"
            return aa_3letter
        
        # Capitalize first letter for consistency
        aa_3letter = aa_3letter.capitalize()
        return AA_3_TO_1_MAP.get(aa_3letter, aa_3letter)
    
    def convert_1_to_3(self, aa_1letter: str) -> str:
        """
        Convert 1-letter amino acid code to 3-letter code.
        
        Args:
            aa_1letter: 1-letter amino acid code (e.g., "A")
            
        Returns:
            3-letter amino acid code or original if not found
        """
        # Handle special cases
        if aa_1letter == '*':
            return 'Ter'
        
        return AA_1_TO_3_MAP.get(aa_1letter.upper(), aa_1letter)
    
    def validate_chromosome(self, chrom: str) -> bool:
        """Validate chromosome name."""
        return chrom in VALID_CHROMOSOMES or chrom.startswith('chr') or chrom.isdigit()
    
    def validate_position(self, pos: str) -> bool:
        """Validate genomic position."""
        try:
            position = int(pos)
            return position > 0
        except (ValueError, TypeError):
            return False


class BedToJsonConverter:
    """Main converter class for BED to JSON conversion."""
    
    def __init__(self, debug: bool = False, stream_output: bool = False):
        self.debug = debug
        self.stream_output = stream_output
        self.logger = logging.getLogger(self.__class__.__name__)
        if debug:
            self.logger.setLevel(logging.DEBUG)
        self.parser = VariantParser(debug)
        self.column_map = {}  # Will store column name to index mapping
        self.stats = {
            'total_rows': 0,
            'processed': 0,
            'skipped': 0,
            'errors': 0,
            'missing_rsid': 0,
            'missing_hgvsp': 0,
            'invalid_chromosome': 0,
            'invalid_position': 0
        }
    
    def parse_header(self, header: List[str]) -> bool:
        """
        Parse the header line to create column name to index mapping.
        
        Args:
            header: List of column names from header line
            
        Returns:
            True if successful, False otherwise
        """
        # Clean the first column name (remove # if present)
        if header[0].startswith('#'):
            header[0] = header[0][1:]
        
        # Create column mapping
        self.column_map = {col: idx for idx, col in enumerate(header)}
        
        # Verify required columns exist
        required_columns = [
            'CHROM', 'POS', 'ID', 'REF', 'ALT', 'SYMBOL',
            'Existing_variation', 'Gene', 'Feature', 'Protein_position',
            'Amino_acids', 'MANE_SELECT', 'HGVSc', 'HGVSp'
        ]
        
        missing_columns = []
        for col in required_columns:
            if col not in self.column_map:
                missing_columns.append(col)
        
        if missing_columns:
            self.logger.error(f"Missing required columns: {', '.join(missing_columns)}")
            return False
        
        self.logger.info(f"Found {len(self.column_map)} columns in header")
        return True
    
    def get_column_value(self, row: List[str], column_name: str) -> str:
        """
        Get value from row by column name with bounds checking.
        
        Args:
            row: Data row
            column_name: Name of the column
            
        Returns:
            Column value or empty string if not found
        """
        if column_name not in self.column_map:
            return ''
        
        idx = self.column_map[column_name]
        if 0 <= idx < len(row):
            return row[idx].strip()
        return ''
    
    def extract_clean_change(self, hgvsc: str) -> str:
        """
        Extract just the change notation from HGVSc (e.g., "c.638C>T" from "ENST00000373960.4:c.638C>T")
        
        Args:
            hgvsc: Full HGVSc notation
            
        Returns:
            Clean change notation or original if parsing fails
        """
        if ':' in hgvsc:
            parts = hgvsc.split(':', 1)
            if len(parts) >= 2:
                return parts[1]
        return hgvsc
    
    def extract_clean_protein_change(self, hgvsp: str) -> str:
        """
        Extract just the protein change from HGVSp (e.g., "p.Ala213Val" from "ENSP00000363071.3:p.Ala213Val")
        
        Args:
            hgvsp: Full HGVSp notation
            
        Returns:
            Clean protein change notation or original if parsing fails
        """
        if ':' in hgvsp:
            parts = hgvsp.split(':', 1)
            if len(parts) >= 2:
                return parts[1]
        return hgvsp
    
    def parse_amino_acids(self, amino_acids: str) -> Optional[Tuple[str, str]]:
        """
        Parse amino acids field safely.
        
        Args:
            amino_acids: Amino acids string (e.g., "A/T")
            
        Returns:
            Tuple of (ref_aa, alt_aa) or None
        """
        if not amino_acids or amino_acids == '-':
            return None
        
        # Handle various formats
        parts = None
        if '/' in amino_acids:
            parts = amino_acids.split('/', 1)
        elif '>' in amino_acids:
            parts = amino_acids.split('>', 1)
        
        if parts and len(parts) == 2:
            ref_aa = parts[0].strip()
            alt_aa = parts[1].strip()
            if ref_aa and alt_aa:
                return ref_aa, alt_aa
        
        return None
    
    def handle_multiallelic(self, alt: str) -> List[str]:
        """
        Handle multi-allelic variants.
        
        Args:
            alt: ALT field which may contain comma-separated alleles
            
        Returns:
            List of alternate alleles
        """
        if ',' in alt:
            return [a.strip() for a in alt.split(',') if a.strip()]
        return [alt]
    
    def process_row(self, row: List[str], row_num: int) -> Optional[Dict]:
        """
        Process a single BED file row and generate variant aliases.
        
        Args:
            row: List of column values
            row_num: Row number for error reporting
            
        Returns:
            Dictionary with variant aliases or None if row should be skipped
        """
        try:
            # Extract basic fields
            chrom = self.get_column_value(row, 'CHROM')
            pos = self.get_column_value(row, 'POS')
            var_id = self.get_column_value(row, 'ID')
            ref = self.get_column_value(row, 'REF')
            alt = self.get_column_value(row, 'ALT')
            gene_symbol = self.get_column_value(row, 'SYMBOL')
            
            # Validate chromosome
            if not self.parser.validate_chromosome(chrom):
                self.logger.warning(f"Row {row_num}: Invalid chromosome: {chrom}")
                self.stats['invalid_chromosome'] += 1
                return None
            
            # Validate position
            if not self.parser.validate_position(pos):
                self.logger.warning(f"Row {row_num}: Invalid position: {pos}")
                self.stats['invalid_position'] += 1
                return None
            
            # Skip Sniffles2 variants
            if var_id.startswith('Sniffles2'):
                self.logger.debug(f"Row {row_num}: Skipping Sniffles2 variant")
                return None
            
            # Extract key fields
            existing_variation = self.get_column_value(row, 'Existing_variation')
            hgvsc = self.get_column_value(row, 'HGVSc')
            hgvsp = self.get_column_value(row, 'HGVSp')
            mane_select = self.get_column_value(row, 'MANE_SELECT')
            protein_position = self.get_column_value(row, 'Protein_position')
            amino_acids = self.get_column_value(row, 'Amino_acids')
            
            # Extract rsID
            rsid = self.parser.extract_rsid(existing_variation)
            if not rsid:
                self.stats['missing_rsid'] += 1
            
            # Handle multi-allelic variants
            alt_alleles = self.handle_multiallelic(alt)
            if len(alt_alleles) > 1:
                self.logger.info(f"Row {row_num}: Multi-allelic variant with {len(alt_alleles)} alternate alleles")
            
            # Use first alternate allele for now (could be extended to handle all)
            alt = alt_alleles[0]
            
            # Create SPDI notation
            # SPDI format: sequence:position:deleted_sequence:inserted_sequence
            # Convert 1-based position to 0-based for SPDI
            spdi_pos = int(pos) - 1
            # Remove 'chr' prefix from chromosome for SPDI
            spdi_chrom = chrom.replace('chr', '')
            spdi = f"{spdi_chrom}:{spdi_pos}:{ref}:{alt}"
            
            # Check if we have HGVSp
            if not hgvsp or hgvsp == '-':
                self.logger.debug(f"Row {row_num}: No HGVSp found")
                self.stats['missing_hgvsp'] += 1
                
                # Try to create entry from Protein_position and Amino_acids columns
                if protein_position and protein_position != '-':
                    aa_parsed = self.parse_amino_acids(amino_acids)
                    if aa_parsed:
                        ref_aa_1, alt_aa_1 = aa_parsed
                        
                        # Convert 1-letter to 3-letter if needed
                        ref_aa_3 = self.parser.convert_1_to_3(ref_aa_1) if len(ref_aa_1) == 1 else ref_aa_1
                        alt_aa_3 = self.parser.convert_1_to_3(alt_aa_1) if len(alt_aa_1) == 1 else alt_aa_1
                        
                        # Create variant entry
                        variant = OrderedDict()
                        variant['internal_id'] = var_id
                        if rsid:
                            variant['rsid'] = rsid
                        variant['spdi'] = spdi
                        
                        # Use whatever transcript we have for HGVS_full
                        if hgvsc and hgvsc != '-':
                            # Extract clean notation
                            clean_hgvsc = self.extract_clean_change(hgvsc)
                            
                            # Use MANE transcript if available
                            if mane_select and mane_select != '-':
                                mane_transcript = mane_select.split(',')[0].strip()
                                if mane_transcript.startswith('NM_'):
                                    variant['hgvs_full'] = f"{mane_transcript}({gene_symbol}):{clean_hgvsc}(p.{ref_aa_3}{protein_position}{alt_aa_3})"
                                else:
                                    variant['hgvs_full'] = f"{gene_symbol}:{clean_hgvsc}(p.{ref_aa_3}{protein_position}{alt_aa_3})"
                            else:
                                variant['hgvs_full'] = f"{gene_symbol}:{clean_hgvsc}(p.{ref_aa_3}{protein_position}{alt_aa_3})"
                            
                            variant['hgvsc'] = f"{gene_symbol} {clean_hgvsc}"
                        
                        # Create protein aliases
                        variant['hgvsp_3p'] = f"{gene_symbol} p.{ref_aa_3}{protein_position}{alt_aa_3}"
                        variant['hgvsp_3'] = f"{gene_symbol} {ref_aa_3}{protein_position}{alt_aa_3}"
                        variant['hgvsp_1p'] = f"{gene_symbol} p.{ref_aa_1}{protein_position}{alt_aa_1}"
                        variant['hgvsp_1'] = f"{gene_symbol} {ref_aa_1}{protein_position}{alt_aa_1}"
                        
                        self.logger.info(f"Row {row_num}: Created entry from Protein_position and Amino_acids")
                        return variant
                
                return None
            
            # Parse HGVSp notation
            hgvsp_parsed = self.parser.parse_hgvsp(hgvsp)
            if not hgvsp_parsed:
                self.logger.warning(f"Row {row_num}: Failed to parse HGVSp: {hgvsp}")
                return None
            
            protein_id, position, ref_aa_3, alt_aa_3 = hgvsp_parsed
            
            # Convert 3-letter to 1-letter amino acids
            ref_aa_1 = self.parser.convert_aa_3_to_1(ref_aa_3)
            alt_aa_1 = self.parser.convert_aa_3_to_1(alt_aa_3)
            
            # Create the variant dictionary
            variant = OrderedDict()
            variant['internal_id'] = var_id
            if rsid:
                variant['rsid'] = rsid
            variant['spdi'] = spdi
            
            # Build HGVS_full notation
            # Extract clean notations
            clean_hgvsc = self.extract_clean_change(hgvsc) if hgvsc and hgvsc != '-' else ''
            clean_hgvsp = self.extract_clean_protein_change(hgvsp)
            
            # Use MANE transcript if available
            if mane_select and mane_select != '-':
                mane_transcript = mane_select.split(',')[0].strip()
                if mane_transcript.startswith('NM_'):
                    if clean_hgvsc:
                        variant['hgvs_full'] = f"{mane_transcript}({gene_symbol}):{clean_hgvsc}({clean_hgvsp})"
                    else:
                        variant['hgvs_full'] = f"{mane_transcript}({gene_symbol}):{clean_hgvsp}"
                else:
                    if clean_hgvsc:
                        variant['hgvs_full'] = f"{gene_symbol}:{clean_hgvsc}({clean_hgvsp})"
                    else:
                        variant['hgvs_full'] = f"{gene_symbol}:{clean_hgvsp}"
            else:
                if clean_hgvsc:
                    variant['hgvs_full'] = f"{gene_symbol}:{clean_hgvsc}({clean_hgvsp})"
                else:
                    variant['hgvs_full'] = f"{gene_symbol}:{clean_hgvsp}"
            
            # Add HGVSc if available
            if clean_hgvsc:
                variant['hgvsc'] = f"{gene_symbol} {clean_hgvsc}"
            
            # Add protein aliases
            variant['hgvsp_3p'] = f"{gene_symbol} p.{ref_aa_3}{position}{alt_aa_3}"
            variant['hgvsp_3'] = f"{gene_symbol} {ref_aa_3}{position}{alt_aa_3}"
            variant['hgvsp_1p'] = f"{gene_symbol} p.{ref_aa_1}{position}{alt_aa_1}"
            variant['hgvsp_1'] = f"{gene_symbol} {ref_aa_1}{position}{alt_aa_1}"
            
            return variant
            
        except Exception as e:
            self.logger.error(f"Row {row_num}: Unexpected error: {str(e)}")
            if self.debug:
                import traceback
                self.logger.debug(traceback.format_exc())
            self.stats['errors'] += 1
            return None
    
    def process_file_streaming(self, input_file: str, output_file: str) -> bool:
        """
        Process BED file with streaming output for memory efficiency.
        
        Args:
            input_file: Path to input BED file
            output_file: Path to output JSON file
            
        Returns:
            True if successful, False otherwise
        """
        self.logger.info(f"Starting streaming conversion of {input_file}")
        
        try:
            with open(input_file, 'r', encoding='utf-8') as infile, \
                 open(output_file, 'w', encoding='utf-8') as outfile:
                
                # Use csv reader for proper tab-delimited parsing
                reader = csv.reader(infile, delimiter='\t')
                
                # Read and parse header line
                header = next(reader, None)
                if not header:
                    self.logger.error("No header line found in BED file")
                    return False
                
                if not self.parse_header(header):
                    return False
                
                # Start JSON array
                outfile.write('[\n')
                first_variant = True
                
                # Process each data row
                for row_num, row in enumerate(reader, start=2):
                    self.stats['total_rows'] += 1
                    
                    if row_num % 1000 == 0:
                        self.logger.info(f"Processed {row_num} rows...")
                    
                    variant = self.process_row(row, row_num)
                    
                    if variant:
                        if not first_variant:
                            outfile.write(',\n')
                        json.dump(variant, outfile, indent=4, ensure_ascii=False)
                        first_variant = False
                        self.stats['processed'] += 1
                    else:
                        self.stats['skipped'] += 1
                
                # Close JSON array
                outfile.write('\n]\n')
            
            # Print statistics
            self.print_stats()
            return True
            
        except FileNotFoundError:
            self.logger.error(f"Input file not found: {input_file}")
            return False
        except PermissionError:
            self.logger.error(f"Permission denied accessing files")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during conversion: {str(e)}")
            if self.debug:
                import traceback
                self.logger.debug(traceback.format_exc())
            return False
    
    def convert_file(self, input_file: str, output_file: str) -> bool:
        """
        Convert BED file to JSON format.
        
        Args:
            input_file: Path to input BED file
            output_file: Path to output JSON file
            
        Returns:
            True if conversion successful, False otherwise
        """
        if self.stream_output:
            return self.process_file_streaming(input_file, output_file)
        
        self.logger.info(f"Starting conversion of {input_file}")
        variants = []
        
        try:
            with open(input_file, 'r', encoding='utf-8') as infile:
                # Use csv reader for proper tab-delimited parsing
                reader = csv.reader(infile, delimiter='\t')
                
                # Read and parse header line
                header = next(reader, None)
                if not header:
                    self.logger.error("No header line found in BED file")
                    return False
                
                if not self.parse_header(header):
                    return False
                
                # Process each data row
                for row_num, row in enumerate(reader, start=2):
                    self.stats['total_rows'] += 1
                    
                    if row_num % 1000 == 0:
                        self.logger.info(f"Processed {row_num} rows...")
                    
                    variant = self.process_row(row, row_num)
                    
                    if variant:
                        variants.append(variant)
                        self.stats['processed'] += 1
                    else:
                        self.stats['skipped'] += 1
            
            # Write output JSON
            self.logger.info(f"Writing {len(variants)} variants to {output_file}")
            with open(output_file, 'w', encoding='utf-8') as outfile:
                json.dump(variants, outfile, indent=4, ensure_ascii=False)
            
            # Print statistics
            self.print_stats()
            
            return True
            
        except FileNotFoundError:
            self.logger.error(f"Input file not found: {input_file}")
            return False
        except PermissionError:
            self.logger.error(f"Permission denied accessing files")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during conversion: {str(e)}")
            if self.debug:
                import traceback
                self.logger.debug(traceback.format_exc())
            return False
    
    def print_stats(self):
        """Print conversion statistics."""
        self.logger.info("=== Conversion Statistics ===")
        self.logger.info(f"Total rows read: {self.stats['total_rows']}")
        self.logger.info(f"Variants processed: {self.stats['processed']}")
        self.logger.info(f"Rows skipped: {self.stats['skipped']}")
        self.logger.info(f"Errors encountered: {self.stats['errors']}")
        self.logger.info(f"Rows missing rsID: {self.stats['missing_rsid']}")
        self.logger.info(f"Rows missing HGVSp: {self.stats['missing_hgvsp']}")
        self.logger.info(f"Invalid chromosomes: {self.stats['invalid_chromosome']}")
        self.logger.info(f"Invalid positions: {self.stats['invalid_position']}")
        
        success_rate = (self.stats['processed'] / self.stats['total_rows'] * 100) if self.stats['total_rows'] > 0 else 0
        self.logger.info(f"Success rate: {success_rate:.1f}%")


def main():
    """Main function to handle command line arguments and run conversion."""
    parser = argparse.ArgumentParser(
        description='Convert BED file with variant information to JSON format with aliases',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s input.bed
  %(prog)s input.bed output.json
  %(prog)s --debug input.bed
  %(prog)s --stream input.bed  # For large files
        """
    )
    
    parser.add_argument('input_file', 
                        help='Input BED file containing variant information')
    parser.add_argument('output_file', 
                        nargs='?',
                        help='Output JSON file (default: input_file with .json extension)')
    parser.add_argument('--debug', '-d',
                        action='store_true',
                        help='Enable debug logging')
    parser.add_argument('--stream', '-s',
                        action='store_true',
                        help='Use streaming mode for large files')
    parser.add_argument('--version', '-v',
                        action='version',
                        version=f'%(prog)s {__version__}')
    
    args = parser.parse_args()
    
    # Set debug logging if requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Validate input file
    input_path = Path(args.input_file)
    if not input_path.is_file():
        logging.error(f"Input file does not exist: {args.input_file}")
        sys.exit(1)
    
    # Determine output file name
    if args.output_file:
        output_file = args.output_file
    else:
        output_file = input_path.with_suffix('.json')
    
    # Check if output file already exists
    if Path(output_file).exists():
        response = input(f"Output file {output_file} already exists. Overwrite? (y/N): ")
        if response.lower() != 'y':
            logging.info("Conversion cancelled.")
            sys.exit(0)
    
    # Create converter and run conversion
    converter = BedToJsonConverter(debug=args.debug, stream_output=args.stream)
    
    start_time = datetime.now()
    success = converter.convert_file(str(input_path), str(output_file))
    end_time = datetime.now()
    
    if success:
        duration = (end_time - start_time).total_seconds()
        logging.info(f"Conversion completed successfully in {duration:.1f} seconds")
        logging.info(f"Output saved to: {output_file}")
        sys.exit(0)
    else:
        logging.error("Conversion failed")
        sys.exit(1)


if __name__ == "__main__":
    main()