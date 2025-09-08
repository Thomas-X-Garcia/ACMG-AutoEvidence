# Contributing to ACMG-AutoEvidence

Thank you for your interest in contributing to ACMG-AutoEvidence! This document provides guidelines for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [How to Contribute](#how-to-contribute)
- [Development Setup](#development-setup)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Reporting Issues](#reporting-issues)

## Code of Conduct

This project adheres to a code of conduct that all contributors are expected to follow:

- Be respectful and inclusive
- Welcome newcomers and help them get started
- Focus on what is best for the community
- Show empathy towards other community members

## Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/your-username/ACMG-AutoEvidence.git
   cd ACMG-AutoEvidence
   ```
3. Add the upstream repository:
   ```bash
   git remote add upstream https://github.com/Thomas-X-Garcia/ACMG-AutoEvidence.git
   ```

## How to Contribute

### Types of Contributions

- **Bug Fixes**: Fix issues reported in GitHub Issues
- **Features**: Implement new functionality
- **Documentation**: Improve or add documentation
- **Tests**: Add or improve test coverage
- **Performance**: Optimize code for better performance
- **ACMG Criteria**: Add or improve ACMG criteria definitions

### Areas Needing Contribution

1. **Additional ACMG Criteria**: Expand the question templates for more criteria
2. **Test Suite**: Develop comprehensive unit and integration tests
3. **Performance Optimization**: Improve processing speed for large datasets
4. **LLM Prompt Engineering**: Optimize prompts for better accuracy
5. **Documentation**: Add more examples and use cases

## Development Setup

1. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install development dependencies**:
   ```bash
   pip install -r requirements-dev.txt
   ```

3. **Install pre-commit hooks**:
   ```bash
   pre-commit install
   ```

## Coding Standards

### Python Style Guide

- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/)
- Use type hints where appropriate
- Maximum line length: 100 characters
- Use meaningful variable and function names

### Code Formatting

```bash
# Format code with black
black *.py

# Sort imports
isort *.py

# Check style with flake8
flake8 *.py

# Type checking
mypy *.py
```

### Docstrings

All functions and classes should have docstrings following the Google style:

```python
def function_name(param1: str, param2: int) -> bool:
    """Brief description of function.
    
    Args:
        param1: Description of param1
        param2: Description of param2
        
    Returns:
        Description of return value
        
    Raises:
        ValueError: When invalid input provided
    """
    pass
```

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=.

# Run specific test file
pytest tests/test_variant_alias_generator.py
```

### Writing Tests

- Place tests in the `tests/` directory
- Name test files with `test_` prefix
- Use descriptive test function names
- Include both positive and negative test cases

Example:
```python
def test_parse_hgvsp_standard_missense():
    """Test parsing standard missense variant."""
    parser = VariantParser()
    result = parser.parse_hgvsp("ENSP00000123456.1:p.Ala123Val")
    assert result == ("ENSP00000123456.1", "123", "Ala", "Val")
```

## Submitting Changes

### Pull Request Process

1. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**:
   - Write clean, documented code
   - Add tests for new functionality
   - Update documentation as needed

3. **Commit your changes**:
   ```bash
   git add .
   git commit -m "feat: add new feature description"
   ```
   
   Use conventional commits:
   - `feat:` for new features
   - `fix:` for bug fixes
   - `docs:` for documentation
   - `test:` for tests
   - `perf:` for performance improvements

4. **Push to your fork**:
   ```bash
   git push origin feature/your-feature-name
   ```

5. **Create a Pull Request**:
   - Go to the original repository on GitHub
   - Click "New Pull Request"
   - Select your fork and branch
   - Fill out the PR template
   - Link any related issues

### PR Requirements

- All tests must pass
- Code must be formatted with black
- No flake8 warnings
- Documentation updated if needed
- Descriptive commit messages
- PR description explains the changes

## Reporting Issues

### Bug Reports

When reporting bugs, please include:

1. **Description**: Clear description of the bug
2. **Steps to Reproduce**: Minimal steps to reproduce the issue
3. **Expected Behavior**: What should happen
4. **Actual Behavior**: What actually happens
5. **Environment**:
   - Python version
   - Operating system
   - Ollama version and model
   - Relevant configuration

### Feature Requests

For feature requests, please include:

1. **Use Case**: Describe the problem you're trying to solve
2. **Proposed Solution**: How you think it should work
3. **Alternatives**: Other solutions you've considered
4. **Impact**: Who would benefit from this feature

## Questions?

If you have questions about contributing:

1. Check existing issues and discussions
2. Open a new discussion on GitHub
3. Contact the maintainer: Thomas X. Garcia, PhD, HCLD

Thank you for contributing to ACMG-AutoEvidence!