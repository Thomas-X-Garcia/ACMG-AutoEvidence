#!/usr/bin/env python3
"""
ACMG-AutoEvidence - Automated ACMG Criteria Evidence Extraction

This script processes genetic variants to:
1. Search PubMed/PMC for relevant articles
2. Retrieve article content (abstracts and full text)
3. Analyze articles using LLM for ACMG criteria
4. Generate structured outputs for variant interpretation

Author: Thomas X. Garcia, PhD, HCLD
Repository: https://github.com/Thomas-X-Garcia/ACMG-AutoEvidence
License: MIT
Version: 1.1.0
"""

import sys
import os
import time
import re
import json
import yaml
import logging
import pathlib
import argparse
import fnmatch
import pandas as pd
import shutil
from typing import Dict, List, Any, Optional, Set, Tuple, Union, Iterator
from dataclasses import dataclass, field
from contextlib import contextmanager
from functools import lru_cache
import hashlib
from datetime import datetime
import tempfile
import atexit
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Third-party imports
try:
    from langchain_ollama import OllamaLLM
    from langchain.callbacks.manager import CallbackManager
    from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
    from langchain.prompts import PromptTemplate
    from langchain.output_parsers import StructuredOutputParser
    from pydantic import BaseModel, Field as PydanticField, validator
    import requests
    from urllib3.util.retry import Retry
    from requests.adapters import HTTPAdapter
    import defusedxml.ElementTree as ET  # Security fix: use defusedxml
    from bs4 import BeautifulSoup
    from jsonschema import validate, ValidationError as JsonValidationError
except ImportError as e:
    print(f"Missing required dependency: {e}")
    print("Please install requirements: pip install -r requirements.txt")
    sys.exit(1)

# --- Constants ---
__version__ = "1.1.0"

# NCBI E-utilities endpoints
NCBI_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
ESEARCH_URL = f"{NCBI_BASE_URL}/esearch.fcgi"
ESUMMARY_URL = f"{NCBI_BASE_URL}/esummary.fcgi"
EFETCH_URL = f"{NCBI_BASE_URL}/efetch.fcgi"

# Rate limiting
DEFAULT_API_DELAY = 0.15  # seconds between NCBI API calls
THROTTLE_PMC = 0.4  # seconds between PMC HTML fetches
MAX_RETRIES = 3
BACKOFF_FACTOR = 0.5

# Chunk sizes
DEFAULT_CHUNK_SIZE_PMC = 50
DEFAULT_CHUNK_SIZE_PUBMED = 100

# LLM settings
DEFAULT_MODEL = "llama3.2:latest"  # Updated to available model
DEFAULT_TEMPERATURE = 0.1
DEFAULT_STOP_TOKENS = ["<|eot_id|>", "<|start_header_id|>", "<|end_header_id|>"]

# HTML parsing blacklist
_BLACKLIST_RAW = {
    "official websites use .gov a .gov website belongs to an official government organization in the united states.",
    "secure .gov websites use https a lock ( lock locked padlock icon ) or https:// means you've safely connected to the .gov website. share sensitive information only on official, secure websites.",
    "permalink",
    "actions",
    "resources",
    "similar articles",
    "cited by other articles",
    "links to ncbi databases",
    "cite",
    "add to collections",
}

# Session pool for connection reuse
SESSION_POOL = None

# --- Custom Exceptions ---
class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing."""
    pass

class NCBIAPIError(Exception):
    """Raised when NCBI API requests fail."""
    pass

class LLMError(Exception):
    """Raised when LLM operations fail."""
    pass

class ArticleRetrievalError(Exception):
    """Raised when article retrieval fails."""
    pass

# --- Data Classes ---
@dataclass
class SearchResult:
    """Container for search results."""
    pmids: List[str] = field(default_factory=list)
    is_valid: bool = True
    search_term: str = ""
    error_message: Optional[str] = None

@dataclass
class ProcessingStats:
    """Track processing statistics."""
    variants_processed: int = 0
    articles_retrieved: int = 0
    analyses_completed: int = 0
    errors_encountered: int = 0
    start_time: float = field(default_factory=time.time)
    
    def elapsed_time(self) -> float:
        return time.time() - self.start_time
    
    def summary(self) -> str:
        elapsed = self.elapsed_time()
        return (
            f"Processing Statistics:\n"
            f"  Variants processed: {self.variants_processed}\n"
            f"  Articles retrieved: {self.articles_retrieved}\n"
            f"  Analyses completed: {self.analyses_completed}\n"
            f"  Errors encountered: {self.errors_encountered}\n"
            f"  Total time: {elapsed:.2f} seconds"
        )

# --- Pydantic Models ---
class VariantAnalysis(BaseModel):
    """Structured output for LLM variant analysis."""
    answer: str = PydanticField(description="The answer to the question: Yes or No")
    reason: str = PydanticField(description="Brief explanation for the answer")
    
    @validator('answer')
    def validate_answer(cls, v):
        if v.lower() not in ['yes', 'no', 'unclear', 'error']:
            raise ValueError('Answer must be Yes, No, Unclear, or Error')
        return v.capitalize()

# --- Configuration Schema ---
CONFIG_SCHEMA = {
    "type": "object",
    "required": ["api_key", "output_dir", "questions"],
    "properties": {
        "api_key": {"type": "string", "minLength": 1},
        "output_dir": {"type": "string", "minLength": 1},
        "questions": {
            "type": "object",
            "minProperties": 1,
            "patternProperties": {
                "^[A-Za-z0-9_]+$": {"type": "string"}
            }
        },
        "variants_json_file": {"type": "string"},
        "search_terms": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1
        },
        "langchain_settings": {
            "type": "object",
            "properties": {
                "temperature": {"type": "number", "minimum": 0, "maximum": 2},
                "stop_tokens": {"type": "array", "items": {"type": "string"}},
                "num_retries": {"type": "integer", "minimum": 1}
            }
        },
        "efetch_chunk_size_pmc": {"type": "integer", "minimum": 1},
        "efetch_chunk_size_pubmed": {"type": "integer", "minimum": 1},
        "api_request_delay": {"type": "number", "minimum": 0},
        "ollama_model": {"type": "string"},
        "run_inference": {"type": "boolean"},
        "verify_pmids": {"type": "boolean"},
        "search_only": {"type": "boolean"},
        "max_workers": {"type": "integer", "minimum": 1, "maximum": 10}
    },
    "oneOf": [
        {"required": ["variants_json_file"]},
        {"required": ["search_terms"]}
    ]
}

# --- Logging Configuration ---
class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for different log levels."""
    
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{log_color}{record.levelname}{self.RESET}"
        return super().format(record)

def setup_logging(log_level: int = logging.INFO, log_file: Optional[str] = None) -> None:
    """Configure logging with both console and file handlers."""
    handlers = []
    
    # Console handler with colors
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(ColoredFormatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    handlers.append(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        ))
        handlers.append(file_handler)
    
    logging.basicConfig(
        level=log_level,
        handlers=handlers
    )
    
    # Set specific loggers to WARNING to reduce noise
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)

# --- Utility Functions ---
@contextmanager
def timer(description: str):
    """Context manager for timing operations."""
    start_time = time.time()
    logging.info(f"Starting: {description}")
    try:
        yield
    finally:
        elapsed = time.time() - start_time
        logging.info(f"Completed: {description} (took {elapsed:.2f}s)")

def create_cache_key(*args) -> str:
    """Create a cache key from arguments."""
    key_string = "_".join(str(arg) for arg in args)
    return hashlib.md5(key_string.encode()).hexdigest()

def ensure_directory(path: Union[str, pathlib.Path]) -> pathlib.Path:
    """Ensure a directory exists, creating it if necessary."""
    path = pathlib.Path(path)
    try:
        path.mkdir(parents=True, exist_ok=True)
        return path
    except OSError as e:
        raise ConfigurationError(f"Cannot create directory {path}: {e}")

def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """Sanitize a filename for safe filesystem usage."""
    # Remove or replace invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    filename = re.sub(r'\s+', '_', filename)
    filename = filename.strip('._')
    
    # Truncate if too long
    if len(filename) > max_length:
        name, ext = os.path.splitext(filename)
        truncate_length = max_length - len(ext) - 1
        filename = f"{name[:truncate_length]}_{ext}"
    
    return filename or "unnamed"

def validate_path_safety(path: Union[str, Path]) -> Path:
    """Validate that a path is safe (no directory traversal)."""
    path = Path(path)
    
    # Check for directory traversal attempts
    try:
        path.resolve()
        if ".." in path.parts:
            raise ValueError("Directory traversal detected")
    except Exception as e:
        raise ConfigurationError(f"Invalid path: {path} - {e}")
    
    return path

def get_env_or_config(config: Dict[str, Any], key: str, env_var: str, 
                      default: Any = None, required: bool = False) -> Any:
    """Get a value from environment or config, with precedence to environment."""
    value = os.environ.get(env_var) or config.get(key, default)
    
    if required and not value:
        raise ConfigurationError(f"Missing required configuration: {key} (or env var {env_var})")
    
    return value

# --- Network Session Setup ---
def get_session_pool():
    """Get or create a session pool."""
    global SESSION_POOL
    if SESSION_POOL is None:
        SESSION_POOL = create_session()
    return SESSION_POOL

def create_session(retries: int = MAX_RETRIES, 
                   backoff_factor: float = BACKOFF_FACTOR,
                   status_forcelist: Tuple[int, ...] = (429, 500, 502, 503, 504),
                   timeout: int = 30) -> requests.Session:
    """Create a requests session with retry logic and timeout."""
    session = requests.Session()
    
    retry_strategy = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        allowed_methods=["GET", "POST"]
    )
    
    adapter = HTTPAdapter(max_retries=retry_strategy, pool_maxsize=10)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    # Set default headers
    session.headers.update({
        'User-Agent': f'VariantLiteratureAnalysis/{__version__} (https://github.com/your-repo)'
    })
    
    # Store timeout as session attribute
    session.timeout = timeout
    
    return session

# --- Configuration Management ---
def load_config(config_path: Union[str, pathlib.Path]) -> Dict[str, Any]:
    """Load and validate configuration from YAML file."""
    config_path = validate_path_safety(config_path)
    
    if not config_path.exists():
        raise ConfigurationError(f"Configuration file not found: {config_path}")
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigurationError(f"Invalid YAML in configuration file: {e}")
    except Exception as e:
        raise ConfigurationError(f"Error reading configuration file: {e}")
    
    # Validate against schema
    try:
        validate(instance=config, schema=CONFIG_SCHEMA)
    except JsonValidationError as e:
        raise ConfigurationError(f"Configuration validation failed: {e.message}")
    
    # Set defaults
    config.setdefault("langchain_settings", {
        "temperature": DEFAULT_TEMPERATURE,
        "stop_tokens": DEFAULT_STOP_TOKENS,
        "num_retries": 3
    })
    config.setdefault("efetch_chunk_size_pmc", DEFAULT_CHUNK_SIZE_PMC)
    config.setdefault("efetch_chunk_size_pubmed", DEFAULT_CHUNK_SIZE_PUBMED)
    config.setdefault("api_request_delay", DEFAULT_API_DELAY)
    config.setdefault("ollama_model", DEFAULT_MODEL)
    config.setdefault("ollama_overwrite", False)
    config.setdefault("run_inference", True)
    config.setdefault("verify_pmids", False)
    config.setdefault("search_only", False)
    config.setdefault("max_workers", 3)
    config.setdefault("retry_settings", {
        "retries": MAX_RETRIES,
        "backoff_factor": BACKOFF_FACTOR
    })
    
    # Get API key from environment if not in config
    api_key = get_env_or_config(config, "api_key", "NCBI_API_KEY", required=True)
    config["api_key"] = api_key
    
    logging.info("Configuration loaded and validated successfully")
    return config

def save_config_backup(config: Dict[str, Any], output_dir: pathlib.Path) -> None:
    """Save a backup of the configuration (without sensitive data)."""
    safe_config = config.copy()
    safe_config["api_key"] = "***REDACTED***"
    
    backup_path = output_dir / f"config_backup_{datetime.now():%Y%m%d_%H%M%S}.yaml"
    
    try:
        with open(backup_path, "w", encoding="utf-8") as f:
            yaml.dump(safe_config, f, default_flow_style=False, sort_keys=False)
        logging.debug(f"Configuration backup saved to {backup_path}")
    except Exception as e:
        logging.warning(f"Failed to save configuration backup: {e}")

# --- NCBI API Functions ---
def normalize_text(text: str) -> str:
    """Normalize text for comparison."""
    return " ".join(text.lower().split())

_BLACKLIST = {normalize_text(t) for t in _BLACKLIST_RAW}

def search_pubmed_for_pmids(search_term: str, api_key: str, 
                            session: Optional[requests.Session] = None,
                            api_delay: float = DEFAULT_API_DELAY) -> SearchResult:
    """
    Search PubMed using ESearch API.
    
    Args:
        search_term: Term to search for
        api_key: NCBI API key
        session: Requests session (if None, will use pool)
        api_delay: Delay between API calls
    
    Returns:
        SearchResult containing PMIDs and validity status
    """
    if session is None:
        session = get_session_pool()
        
    result = SearchResult(search_term=search_term)
    
    params = {
        "db": "pubmed",
        "term": search_term,
        "retmode": "json",
        "retmax": 100000,
        "usehistory": "y",
        "sort": "relevance"
    }
    
    if api_key:
        params["api_key"] = api_key
    
    try:
        with timer(f"ESearch for '{search_term}'"):
            response = session.get(ESEARCH_URL, params=params, timeout=session.timeout)
            response.raise_for_status()
            
            # Validate JSON response
            try:
                data = response.json()
            except json.JSONDecodeError as e:
                result.is_valid = False
                result.error_message = f"Invalid JSON response: {e}"
                return result
        
        if "esearchresult" not in data:
            result.is_valid = False
            result.error_message = "Invalid response structure"
            return result
        
        esearch_result = data["esearchresult"]
        
        # Check for errors and warnings
        error_list = esearch_result.get("errorlist", {})
        warnings = esearch_result.get("warninglist", {}).get("outputmessages", [])
        phrases_not_found = error_list.get("phrasesnotfound", [])
        
        # Validate results
        count = int(esearch_result.get("count", "0"))
        ids_found = esearch_result.get("idlist", [])
        
        # Check for invalid results
        for warning in warnings:
            if any(indicator in warning.lower() for indicator in 
                   ["processed without automatic term mapping", "was not found in pubmed"]):
                logging.warning(f"Search warning for '{search_term}': {warning}")
                result.is_valid = False
                result.error_message = warning
        
        if phrases_not_found:
            logging.warning(f"Phrases not found for '{search_term}': {', '.join(phrases_not_found)}")
            result.is_valid = False
            result.error_message = f"Phrases not found: {', '.join(phrases_not_found)}"
        
        # Only return PMIDs if the search was valid
        if result.is_valid:
            result.pmids = ids_found
            logging.info(f"Found {count} PMIDs for '{search_term}'")
        else:
            result.pmids = []
            logging.warning(f"Invalid search results for '{search_term}': {result.error_message}")
        
        return result
        
    except requests.exceptions.RequestException as e:
        logging.error(f"Network error during ESearch for '{search_term}': {e}")
        result.is_valid = False
        result.error_message = f"Network error: {str(e)}"
        return result
    except Exception as e:
        logging.error(f"Unexpected error during ESearch for '{search_term}': {e}")
        result.is_valid = False
        result.error_message = f"Unexpected error: {str(e)}"
        return result
    finally:
        time.sleep(api_delay)

def fetch_pmid_metadata(pmids: List[str], api_key: str, 
                       session: Optional[requests.Session] = None,
                       api_delay: float = DEFAULT_API_DELAY) -> Dict[str, Dict[str, Any]]:
    """Fetch metadata for PMIDs including PMC links."""
    if not pmids:
        return {}
    
    if session is None:
        session = get_session_pool()
    
    metadata = {}
    batch_size = 200  # NCBI recommended batch size
    
    for i in range(0, len(pmids), batch_size):
        batch = pmids[i:i + batch_size]
        
        params = {
            "db": "pubmed",
            "retmode": "json",
            "api_key": api_key,
            "version": "2.0"
        }
        
        try:
            response = session.post(
                ESUMMARY_URL,
                params=params,
                data={"id": ",".join(batch)},
                timeout=session.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            if "result" in data:
                for pmid in data["result"].get("uids", []):
                    if pmid in data["result"]:
                        record = data["result"][pmid]
                        
                        # Extract PMC ID if available
                        pmcid = None
                        for aid in record.get("articleids", []):
                            if aid.get("idtype") == "pmc":
                                pmcid_value = aid.get("value", "")
                                if pmcid_value:
                                    pmcid = f"PMC{pmcid_value}" if not pmcid_value.startswith("PMC") else pmcid_value
                                    break
                        
                        metadata[pmid] = {
                            "title": record.get("title", ""),
                            "authors": record.get("authors", []),
                            "pubdate": record.get("pubdate", ""),
                            "pmcid": pmcid,
                            "doi": next((aid["value"] for aid in record.get("articleids", []) 
                                       if aid.get("idtype") == "doi"), None)
                        }
            
        except Exception as e:
            logging.error(f"Error fetching metadata for batch starting with {batch[0]}: {e}")
        
        time.sleep(api_delay)
    
    return metadata

def fetch_pmc_html(pmcid: str, session: Optional[requests.Session] = None, 
                   retries: int = MAX_RETRIES) -> Optional[str]:
    """Fetch and clean PMC article HTML."""
    if session is None:
        session = get_session_pool()
        
    if not pmcid.upper().startswith("PMC"):
        pmcid = f"PMC{pmcid}"
    
    url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}"
    
    for attempt in range(retries):
        try:
            response = session.get(url, timeout=session.timeout)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "lxml")
            
            # Remove navigation and metadata elements
            for selector in ("nav", "header", "footer", ".floating-menu",
                           ".nav-wrapper", "aside", ".contrib-group", 
                           ".contributors", ".authors", "#authors",
                           ".fm-authors", "[class*=author]", "[id*=author]",
                           "[class*=contrib]", "[id*=contrib]",
                           ".aff", ".affiliations"):
                for tag in soup.select(selector):
                    tag.decompose()
            
            # Extract text content
            pieces = []
            for tag in soup.select("h1, h2, h3, p"):
                text = tag.get_text(" ", strip=True)
                if text and normalize_text(text) not in _BLACKLIST:
                    pieces.append(text)
            
            if not pieces:
                return None
            
            # Process content
            content = []
            title_found = False
            
            for i, piece in enumerate(pieces):
                # First significant piece is likely the title
                if not title_found and piece.strip():
                    content.append(f"Title: {piece}")
                    title_found = True
                    continue
                
                # Look for abstract/summary sections
                lower_piece = piece.lower()
                if any(marker in lower_piece for marker in ["abstract", "summary"]):
                    content.extend(pieces[i:])
                    break
                elif title_found:
                    content.append(piece)
            
            return "\n\n".join(content)
            
        except Exception as e:
            logging.warning(f"Attempt {attempt + 1}/{retries} failed for {pmcid}: {e}")
            if attempt < retries - 1:
                time.sleep(BACKOFF_FACTOR * (attempt + 1))
    
    return None

def fetch_pubmed_abstracts(pmids: List[str], api_key: str, 
                          session: Optional[requests.Session] = None,
                          chunk_size: int = DEFAULT_CHUNK_SIZE_PUBMED,
                          api_delay: float = DEFAULT_API_DELAY) -> Dict[str, str]:
    """Fetch PubMed abstracts in batches."""
    if session is None:
        session = get_session_pool()
        
    abstracts = {}
    
    for i in range(0, len(pmids), chunk_size):
        chunk = pmids[i:i + chunk_size]
        
        params = {
            "db": "pubmed",
            "id": ",".join(chunk),
            "retmode": "xml",
            "api_key": api_key
        }
        
        try:
            response = session.get(EFETCH_URL, params=params, timeout=session.timeout)
            response.raise_for_status()
            
            # Use defusedxml for security
            root = ET.fromstring(response.text)
            
            for article in root.findall(".//PubmedArticle"):
                pmid_elem = article.find(".//PMID")
                if pmid_elem is not None and pmid_elem.text:
                    pmid = pmid_elem.text.strip()
                    
                    # Extract title
                    title_elem = article.find(".//ArticleTitle")
                    title = "".join(title_elem.itertext()).strip() if title_elem is not None else ""
                    
                    # Extract abstract
                    abstract_parts = []
                    for abs_elem in article.findall(".//Abstract/AbstractText"):
                        text = "".join(abs_elem.itertext()).strip()
                        label = abs_elem.get("Label")
                        if label:
                            text = f"{label}: {text}"
                        if text:
                            abstract_parts.append(text)
                    
                    if title or abstract_parts:
                        content = []
                        if title:
                            content.append(f"Title: {title}")
                        if abstract_parts:
                            content.append(f"Abstract:\n" + "\n\n".join(abstract_parts))
                        
                        abstracts[pmid] = "\n\n".join(content)
            
        except Exception as e:
            logging.error(f"Error fetching abstracts for chunk {i//chunk_size + 1}: {e}")
        
        time.sleep(api_delay)
    
    return abstracts

# --- LLM Functions ---
def setup_ollama_llm(model_name: str, settings: Dict[str, Any]) -> OllamaLLM:
    """Set up Ollama LLM with error handling."""
    try:
        callbacks = [StreamingStdOutCallbackHandler()] if logging.getLogger().level <= logging.INFO else []
        
        llm = OllamaLLM(
            model=model_name,
            callbacks=callbacks,
            temperature=settings.get("temperature", DEFAULT_TEMPERATURE),
            stop=settings.get("stop_tokens", DEFAULT_STOP_TOKENS)
        )
        
        # Test the connection
        test_response = llm.invoke("Test")
        logging.info(f"LLM initialized successfully with model: {model_name}")
        
        return llm
        
    except Exception as e:
        raise LLMError(f"Failed to initialize Ollama LLM: {e}")

def create_analysis_prompt() -> Tuple[PromptTemplate, StructuredOutputParser]:
    """Create structured prompt template for analysis."""
    response_schemas = [
        {
            "name": "answer",
            "type": "string",
            "description": "The answer to the question: Yes, No, or Unclear"
        },
        {
            "name": "reason",
            "type": "string", 
            "description": "Brief explanation for the answer (max 200 words)"
        }
    ]
    
    output_parser = StructuredOutputParser.from_response_schemas(response_schemas)
    format_instructions = output_parser.get_format_instructions()
    
    prompt_template = PromptTemplate(
        input_variables=["manuscript_text", "specific_question"],
        partial_variables={"format_instructions": format_instructions},
        template="""You are a scientific reasoning assistant analyzing manuscripts for evidence about genetic variants.

Manuscript:
```
{manuscript_text}
```

Question: {specific_question}

Analyze the manuscript thoroughly and determine if it contains evidence related to the question.
Focus on experimental data, clinical observations, and functional studies.

{format_instructions}

Provide a clear Yes/No/Unclear answer followed by a concise explanation."""
    )
    
    return prompt_template, output_parser

def analyze_with_llm(llm: OllamaLLM, prompt_template: PromptTemplate,
                     output_parser: StructuredOutputParser,
                     manuscript_text: str, question: str,
                     max_retries: int = 3, max_manuscript_length: int = 250000) -> Dict[str, str]:
    """Analyze manuscript with LLM and structured output parsing."""
    
    # Truncate manuscript if too long
    if len(manuscript_text) > max_manuscript_length:
        manuscript_text = manuscript_text[:max_manuscript_length] + "\n\n[Content truncated...]"
    
    for attempt in range(max_retries):
        try:
            # Generate prompt
            prompt = prompt_template.format(
                manuscript_text=manuscript_text,
                specific_question=question
            )
            
            # Get LLM response
            response = llm.invoke(prompt)
            
            # Try structured parsing first
            try:
                parsed = output_parser.parse(response)
                return {
                    "answer": parsed.get("answer", "Unclear"),
                    "reason": parsed.get("reason", "No explicit reason provided")
                }
            except Exception as parse_error:
                logging.debug(f"Structured parsing failed: {parse_error}")
                
                # Fallback to pattern matching
                answer = extract_answer_pattern(response)
                reason = extract_reason_pattern(response, answer)
                
                return {"answer": answer, "reason": reason}
                
        except Exception as e:
            logging.warning(f"LLM analysis attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(BACKOFF_FACTOR * (attempt + 1))
            else:
                return {
                    "answer": "Error",
                    "reason": f"Analysis failed after {max_retries} attempts: {str(e)}"
                }

def extract_answer_pattern(text: str) -> str:
    """Extract Yes/No/Unclear answer from text."""
    patterns = {
        "Yes": [r'\byes\b', r'\[yes\]', r'"answer":\s*"yes"'],
        "No": [r'\bno\b', r'\[no\]', r'"answer":\s*"no"'],
        "Unclear": [r'\bunclear\b', r'\[unclear\]', r'"answer":\s*"unclear"']
    }
    
    for answer, pattern_list in patterns.items():
        for pattern in pattern_list:
            if re.search(pattern, text, re.IGNORECASE):
                return answer
    
    return "Unclear"

def extract_reason_pattern(text: str, answer: str) -> str:
    """Extract reasoning from LLM response."""
    # Try to find structured reason
    reason_match = re.search(r'"reason":\s*"([^"]*)"', text)
    if reason_match:
        return reason_match.group(1)
    
    # Look for reason after answer
    pattern = rf'\b{answer}\b[:\s]*(.*?)(?:\n|$)'
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if match:
        reason = match.group(1).strip()
        # Limit length
        if len(reason) > 500:
            reason = reason[:497] + "..."
        return reason
    
    return "No explicit reason provided"

# --- Variant Processing ---
class VariantProcessor:
    """Handles processing of individual variants with parallel support."""
    
    def __init__(self, config: Dict[str, Any], session: Optional[requests.Session] = None,
                 llm: Optional[OllamaLLM] = None,
                 prompt_template: Optional[PromptTemplate] = None,
                 output_parser: Optional[StructuredOutputParser] = None):
        self.config = config
        self.session = session or get_session_pool()
        self.llm = llm
        self.prompt_template = prompt_template
        self.output_parser = output_parser
        self.stats = ProcessingStats()
        self.executor = ThreadPoolExecutor(max_workers=config.get("max_workers", 3))
    
    def __del__(self):
        """Cleanup executor on deletion."""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=False)
    
    def process_variant(self, variant: Dict[str, Any]) -> Tuple[int, List[Dict[str, Any]]]:
        """Process a single variant through the full pipeline."""
        
        # Get variant identifiers
        variant_id = self._get_variant_id(variant)
        output_dir = ensure_directory(pathlib.Path(self.config["output_dir"]) / sanitize_filename(variant_id))
        
        logging.info(f"Processing variant: {variant_id}")
        
        # Save variant info
        self._save_variant_info(variant, output_dir)
        
        # Get search terms
        search_terms = self._get_search_terms(variant)
        if not search_terms:
            logging.warning(f"No search terms for variant {variant_id}")
            return 0, []
        
        # Search phase
        search_results = self._search_literature(search_terms, output_dir)
        
        if self.config.get("search_only"):
            logging.info("Search-only mode: skipping retrieval and analysis")
            return len(search_results), []
        
        # Retrieval phase
        articles = self._retrieve_articles(search_results, output_dir)
        
        if not articles:
            logging.info(f"No articles retrieved for variant {variant_id}")
            return 0, []
        
        # Analysis phase
        results = []
        if self.config.get("run_inference") and self.llm:
            results = self._analyze_articles(articles, search_terms, output_dir)
        
        self.stats.variants_processed += 1
        self.stats.articles_retrieved += len(articles)
        self.stats.analyses_completed += len(results)
        
        return len(articles), results
    
    def _get_variant_id(self, variant: Dict[str, Any]) -> str:
        """Extract the best identifier for a variant."""
        # Priority order for identifiers
        id_fields = ["rsid", "hgvs_full", "hgvsp_1", "hgvsc", "hgvsp_3", "internal_id"]
        
        for field in id_fields:
            if field in variant and variant[field]:
                return str(variant[field])
        
        # Fallback
        return f"variant_{int(time.time() * 1000)}"
    
    def _get_search_terms(self, variant: Dict[str, Any]) -> List[str]:
        """Extract search terms from variant."""
        terms = []
        excluded_fields = {'internal_id', 'internal_code', 'comment', 'notes'}
        
        for key, value in variant.items():
            if (value and isinstance(value, str) and 
                key.lower() not in excluded_fields and
                not key.lower().startswith('internal')):
                terms.append(value)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_terms = []
        for term in terms:
            if term not in seen:
                seen.add(term)
                unique_terms.append(term)
        
        return unique_terms
    
    def _save_variant_info(self, variant: Dict[str, Any], output_dir: pathlib.Path) -> None:
        """Save variant information to file."""
        info_path = output_dir / "variant_info.json"
        try:
            with open(info_path, "w", encoding="utf-8") as f:
                json.dump(variant, f, indent=2, default=str)
        except Exception as e:
            logging.warning(f"Failed to save variant info: {e}")
    
    def _search_literature(self, search_terms: List[str], 
                          output_dir: pathlib.Path) -> Dict[str, SearchResult]:
        """Search literature for all terms in parallel."""
        results = {}
        all_pmids = set()
        
        # Create search log
        log_path = output_dir / "search_log.txt"
        with open(log_path, "w", encoding="utf-8") as log_file:
            log_file.write(f"Search performed: {datetime.now()}\n")
            log_file.write(f"Terms: {', '.join(search_terms)}\n\n")
            
            # Parallel search
            futures = {
                self.executor.submit(
                    search_pubmed_for_pmids,
                    term,
                    self.config["api_key"],
                    self.session,
                    self.config.get("api_request_delay", DEFAULT_API_DELAY)
                ): term for term in search_terms
            }
            
            for future in as_completed(futures):
                term = futures[future]
                try:
                    result = future.result()
                    results[term] = result
                    
                    log_file.write(f"Term: {term}\n")
                    log_file.write(f"  Valid: {result.is_valid}\n")
                    log_file.write(f"  PMIDs: {len(result.pmids)}\n")
                    
                    if result.is_valid:
                        all_pmids.update(result.pmids)
                    else:
                        log_file.write(f"  Error: {result.error_message}\n")
                    
                    log_file.write("\n")
                except Exception as e:
                    logging.error(f"Search failed for term '{term}': {e}")
                    results[term] = SearchResult(search_term=term, is_valid=False, error_message=str(e))
            
            log_file.write(f"Total unique PMIDs: {len(all_pmids)}\n")
        
        # Save search results
        results_path = output_dir / "search_results.json"
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "terms": search_terms,
                "total_pmids": len(all_pmids),
                "results": {
                    term: {
                        "valid": r.is_valid,
                        "pmid_count": len(r.pmids),
                        "error": r.error_message
                    } for term, r in results.items()
                }
            }, f, indent=2)
        
        return results
    
    def _retrieve_articles(self, search_results: Dict[str, SearchResult],
                          output_dir: pathlib.Path) -> Dict[str, str]:
        """Retrieve article content."""
        # Collect all valid PMIDs
        all_pmids = set()
        for result in search_results.values():
            if result.is_valid:
                all_pmids.update(result.pmids)
        
        if not all_pmids:
            return {}
        
        pmids_list = list(all_pmids)
        articles = {}
        
        # Get metadata
        with timer("Fetching article metadata"):
            metadata = fetch_pmid_metadata(
                pmids_list,
                self.config["api_key"],
                self.session,
                self.config.get("api_request_delay", DEFAULT_API_DELAY)
            )
        
        # Separate PMC and PubMed-only articles
        pmc_articles = {pmid: meta for pmid, meta in metadata.items() if meta.get("pmcid")}
        pubmed_only = [pmid for pmid in pmids_list if pmid not in pmc_articles]
        
        # Fetch PMC full text in parallel
        pmc_futures = {}
        for pmid, meta in pmc_articles.items():
            pmcid = meta["pmcid"]
            future = self.executor.submit(fetch_pmc_html, pmcid, self.session)
            pmc_futures[future] = (pmid, pmcid)
        
        for future in as_completed(pmc_futures):
            pmid, pmcid = pmc_futures[future]
            try:
                content = future.result()
                if content:
                    articles[pmcid] = content
                    
                    # Save to file
                    article_path = output_dir / f"{pmcid}.txt"
                    with open(article_path, "w", encoding="utf-8") as f:
                        f.write(content)
                
                time.sleep(THROTTLE_PMC)
                
            except Exception as e:
                logging.error(f"Failed to retrieve {pmcid}: {e}")
                self.stats.errors_encountered += 1
        
        # Fetch PubMed abstracts
        if pubmed_only:
            with timer(f"Fetching {len(pubmed_only)} PubMed abstracts"):
                abstracts = fetch_pubmed_abstracts(
                    pubmed_only,
                    self.config["api_key"],
                    self.session,
                    self.config.get("efetch_chunk_size_pubmed", DEFAULT_CHUNK_SIZE_PUBMED),
                    self.config.get("api_request_delay", DEFAULT_API_DELAY)
                )
                
                for pmid, content in abstracts.items():
                    articles[pmid] = content
                    
                    # Save to file
                    article_path = output_dir / f"{pmid}.txt"
                    with open(article_path, "w", encoding="utf-8") as f:
                        f.write(content)
        
        return articles
    
    def _analyze_articles(self, articles: Dict[str, str], search_terms: List[str],
                         output_dir: pathlib.Path) -> List[Dict[str, Any]]:
        """Analyze articles with LLM."""
        results = []
        questions = self.config.get("questions", {})
        
        # Format search terms for questions
        quoted_terms = ", ".join(f'"{term}"' for term in search_terms)
        
        for article_id, content in articles.items():
            for criterion_code, question_template in questions.items():
                # Check if result already exists
                result_file = output_dir / f"{article_id}_{criterion_code}_result.json"
                
                if result_file.exists() and not self.config.get("ollama_overwrite"):
                    # Load existing result
                    try:
                        with open(result_file, "r", encoding="utf-8") as f:
                            result = json.load(f)
                            results.append(result)
                            continue
                    except Exception as e:
                        logging.warning(f"Failed to load existing result: {e}")
                
                # Prepare question
                question = question_template.replace("{comma-separated_variant_terms}", quoted_terms)
                
                # Analyze with LLM
                try:
                    with timer(f"Analyzing {article_id} for {criterion_code}"):
                        max_length = self.config.get("langchain_settings", {}).get("max_manuscript_length", 250000)
                        analysis = analyze_with_llm(
                            self.llm,
                            self.prompt_template,
                            self.output_parser,
                            content,
                            question,
                            max_manuscript_length=max_length
                        )
                    
                    result = {
                        "variant_id": output_dir.name,
                        "article_id": article_id,
                        "criterion_code": criterion_code,
                        "answer": analysis["answer"],
                        "reason": analysis["reason"],
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    # Save result
                    with open(result_file, "w", encoding="utf-8") as f:
                        json.dump(result, f, indent=2)
                    
                    # Also save in simple text format for compatibility
                    text_file = output_dir / f"{article_id}_{criterion_code}_result.txt"
                    with open(text_file, "w", encoding="utf-8") as f:
                        f.write(f"[{analysis['answer']}] {analysis['reason']}")
                    
                    results.append(result)
                    
                except Exception as e:
                    logging.error(f"Analysis failed for {article_id}, {criterion_code}: {e}")
                    self.stats.errors_encountered += 1
        
        return results

# --- Results Processing ---
def collect_results(base_dir: pathlib.Path, pattern: str = "*_result.json") -> List[Dict[str, Any]]:
    """Collect all result files from directory tree."""
    results = []
    
    for result_file in base_dir.rglob(pattern):
        try:
            with open(result_file, "r", encoding="utf-8") as f:
                result = json.load(f)
                results.append(result)
        except Exception as e:
            logging.warning(f"Failed to load result file {result_file}: {e}")
            
            # Try loading text format
            text_file = result_file.with_suffix(".txt")
            if text_file.exists():
                try:
                    with open(text_file, "r", encoding="utf-8") as f:
                        content = f.read().strip()
                        
                    # Parse text format
                    answer = extract_answer_pattern(content)
                    reason = extract_reason_pattern(content, answer)
                    
                    # Extract metadata from filename
                    parts = result_file.stem.split("_")
                    if len(parts) >= 2:
                        article_id = parts[0]
                        criterion_code = parts[1].replace("_result", "")
                        
                        results.append({
                            "variant_id": result_file.parent.name,
                            "article_id": article_id,
                            "criterion_code": criterion_code,
                            "answer": answer,
                            "reason": reason,
                            "timestamp": None
                        })
                except Exception as e2:
                    logging.error(f"Failed to parse text file {text_file}: {e2}")
    
    return results

def results_to_dataframe(results: List[Dict[str, Any]], 
                        variant_lookup: Optional[Dict[str, Dict[str, Any]]] = None) -> pd.DataFrame:
    """Convert results to pandas DataFrame with enhanced metadata."""
    if not results:
        return pd.DataFrame()
    
    df = pd.DataFrame(results)
    
    # Add rsid column if variant lookup provided
    if variant_lookup:
        df["rsid"] = df["variant_id"].map(
            lambda vid: variant_lookup.get(vid, {}).get("rsid", vid)
        )
    
    # Add article type
    df["article_type"] = df["article_id"].apply(
        lambda aid: "PMCID" if str(aid).upper().startswith("PMC") else "PMID"
    )
    
    # Ensure consistent column order
    columns = ["variant_id", "rsid", "article_id", "article_type", 
               "criterion_code", "answer", "reason", "timestamp"]
    
    for col in columns:
        if col not in df.columns:
            df[col] = None
    
    return df[columns]

def generate_summary_report(df: pd.DataFrame, output_path: pathlib.Path) -> None:
    """Generate a summary report from results."""
    report_lines = [
        "# Variant Analysis Summary Report",
        f"Generated: {datetime.now():%Y-%m-%d %H:%M:%S}",
        "",
        "## Overview",
        f"- Total variants analyzed: {df['variant_id'].nunique()}",
        f"- Total articles processed: {df['article_id'].nunique()}",
        f"- Total analyses performed: {len(df)}",
        "",
        "## Results by Criterion",
    ]
    
    # Summary by criterion
    for criterion in sorted(df['criterion_code'].unique()):
        criterion_df = df[df['criterion_code'] == criterion]
        answer_counts = criterion_df['answer'].value_counts()
        
        report_lines.extend([
            f"\n### {criterion}",
            f"- Total analyses: {len(criterion_df)}",
            f"- Yes: {answer_counts.get('Yes', 0)}",
            f"- No: {answer_counts.get('No', 0)}",
            f"- Unclear: {answer_counts.get('Unclear', 0)}",
            f"- Error: {answer_counts.get('Error', 0)}",
        ])
    
    # Write report
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

# --- Main Application ---
def main():
    """Main application entry point."""
    # Parse arguments
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("config", help="Path to YAML configuration file")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    
    # Processing options
    parser.add_argument("--no-inference", action="store_true",
                       help="Skip LLM inference step")
    parser.add_argument("--search-only", action="store_true",
                       help="Only perform literature search")
    parser.add_argument("--collect-only", action="store_true",
                       help="Only collect existing results")
    parser.add_argument("--overwrite", action="store_true",
                       help="Overwrite existing results")
    
    # Filtering options
    parser.add_argument("--variant", help="Process only this variant ID")
    parser.add_argument("--limit", type=int, help="Limit number of variants to process")
    
    # Performance options
    parser.add_argument("--verify-pmids", action="store_true",
                       help="Verify PMIDs with additional API calls")
    parser.add_argument("--cache", action="store_true",
                       help="Enable search result caching")
    parser.add_argument("--parallel", type=int, metavar="N",
                       help="Number of parallel workers (default: 3)")
    
    # Output options
    parser.add_argument("--format", choices=["csv", "json", "excel"],
                       default="csv", help="Output format (default: csv)")
    parser.add_argument("--summary", action="store_true",
                       help="Generate summary report")
    
    # Debugging options
    parser.add_argument("--debug", action="store_true",
                       help="Enable debug logging")
    parser.add_argument("--log-file", help="Save logs to file")
    parser.add_argument("--dry-run", action="store_true",
                       help="Show what would be done without doing it")
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    setup_logging(log_level, args.log_file)
    
    logging.info(f"Starting Variant Analysis Tool v{__version__}")
    
    # Validate arguments
    if args.collect_only and args.search_only:
        parser.error("--collect-only and --search-only are mutually exclusive")
    
    try:
        # Load configuration
        config = load_config(args.config)
        
        # Override config with command line options
        if args.no_inference:
            config["run_inference"] = False
        if args.search_only:
            config["search_only"] = True
        if args.overwrite:
            config["ollama_overwrite"] = True
        if args.verify_pmids:
            config["verify_pmids"] = True
        if args.parallel:
            config["max_workers"] = args.parallel
        
        # Create output directory
        output_dir = ensure_directory(config["output_dir"])
        
        # Save config backup
        save_config_backup(config, output_dir)
        
        # Collect-only mode
        if args.collect_only:
            logging.info("Running in collect-only mode")
            results = collect_results(output_dir)
            
            if results:
                df = results_to_dataframe(results)
                
                # Save results
                if args.format == "csv":
                    output_file = output_dir / "collected_results.csv"
                    df.to_csv(output_file, index=False)
                elif args.format == "json":
                    output_file = output_dir / "collected_results.json"
                    df.to_json(output_file, orient="records", indent=2)
                elif args.format == "excel":
                    output_file = output_dir / "collected_results.xlsx"
                    df.to_excel(output_file, index=False)
                
                logging.info(f"Saved {len(results)} results to {output_file}")
                
                if args.summary:
                    summary_file = output_dir / "summary_report.md"
                    generate_summary_report(df, summary_file)
                    logging.info(f"Generated summary report: {summary_file}")
            else:
                logging.warning("No results found to collect")
            
            return
        
        # Regular processing mode
        # Set up LLM if needed
        llm = None
        prompt_template = None
        output_parser = None
        
        if config.get("run_inference") and not args.search_only:
            try:
                model_name = config.get("ollama_model", DEFAULT_MODEL)
                llm = setup_ollama_llm(model_name, config.get("langchain_settings", {}))
                prompt_template, output_parser = create_analysis_prompt()
            except LLMError as e:
                logging.error(f"Failed to initialize LLM: {e}")
                if not args.dry_run:
                    response = input("Continue without LLM analysis? [y/N]: ")
                    if response.lower() != 'y':
                        sys.exit(1)
                config["run_inference"] = False
        
        # Load variants
        variants = []
        if "variants_json_file" in config:
            variants_file = validate_path_safety(config["variants_json_file"])
            if not variants_file.exists():
                raise ConfigurationError(f"Variants file not found: {variants_file}")
            
            with open(variants_file, "r", encoding="utf-8") as f:
                variants = json.load(f)
            
            if not isinstance(variants, list):
                raise ConfigurationError("Variants file must contain a JSON array")
            
            logging.info(f"Loaded {len(variants)} variants from {variants_file}")
        
        elif "search_terms" in config:
            # Create synthetic variant
            variant = {"search_terms": config["search_terms"]}
            if any(term.lower().startswith("rs") for term in config["search_terms"]):
                variant["rsid"] = next(t for t in config["search_terms"] 
                                     if t.lower().startswith("rs"))
            variants = [variant]
        
        # Filter variants if requested
        if args.variant:
            filtered = []
            for v in variants:
                for key, value in v.items():
                    if str(value) == args.variant:
                        filtered.append(v)
                        break
            
            if not filtered:
                raise ValueError(f"Variant '{args.variant}' not found")
            
            variants = filtered
        
        # Limit variants if requested
        if args.limit:
            variants = variants[:args.limit]
        
        if args.dry_run:
            logging.info(f"DRY RUN: Would process {len(variants)} variants")
            for i, v in enumerate(variants[:5]):
                logging.info(f"  Variant {i+1}: {v}")
            if len(variants) > 5:
                logging.info(f"  ... and {len(variants) - 5} more")
            return
        
        # Process variants
        processor = VariantProcessor(config, None, llm, prompt_template, output_parser)
        all_results = []
        variant_lookup = {}
        
        try:
            for i, variant in enumerate(variants, 1):
                logging.info(f"Processing variant {i}/{len(variants)}")
                
                try:
                    variant_id = processor._get_variant_id(variant)
                    variant_lookup[variant_id] = variant
                    
                    articles_count, results = processor.process_variant(variant)
                    all_results.extend(results)
                    
                except Exception as e:
                    logging.error(f"Error processing variant {i}: {e}")
                    processor.stats.errors_encountered += 1
                    if args.debug:
                        raise
            
            # Save results
            if all_results:
                df = results_to_dataframe(all_results, variant_lookup)
                
                # Generate output filename
                if "variants_json_file" in config:
                    base_name = pathlib.Path(config["variants_json_file"]).stem
                    output_name = f"{base_name}_ACMG_criteria"
                else:
                    output_name = "variant_ACMG_criteria"
                
                # Save in requested format
                if args.format == "csv":
                    output_file = output_dir / f"{output_name}.csv"
                    df.to_csv(output_file, index=False)
                elif args.format == "json":
                    output_file = output_dir / f"{output_name}.json"
                    df.to_json(output_file, orient="records", indent=2)
                elif args.format == "excel":
                    output_file = output_dir / f"{output_name}.xlsx"
                    df.to_excel(output_file, index=False)
                
                logging.info(f"Saved {len(all_results)} results to {output_file}")
                
                # Generate summary if requested
                if args.summary:
                    summary_file = output_dir / f"{output_name}_summary.md"
                    generate_summary_report(df, summary_file)
                    logging.info(f"Generated summary report: {summary_file}")
            
            # Print statistics
            logging.info(processor.stats.summary())
            
        except KeyboardInterrupt:
            logging.warning("Processing interrupted by user")
            logging.info(processor.stats.summary())
        
    except ConfigurationError as e:
        logging.error(f"Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        if args.debug:
            raise
        sys.exit(1)

if __name__ == "__main__":
    main()