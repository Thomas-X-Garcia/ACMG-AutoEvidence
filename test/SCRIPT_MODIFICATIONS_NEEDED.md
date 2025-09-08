# Script Modifications Needed for Improved Prompts

## Critical Issues to Fix

### 1. **Prompt Template Not Used from Config**
The script creates its own hardcoded prompt in `create_analysis_prompt()` instead of using `prompt_base_template` from the config file.

**Current Code (lines 753-771):**
```python
prompt_template = PromptTemplate(
    input_variables=["manuscript_text", "specific_question"],
    partial_variables={"format_instructions": format_instructions},
    template="""You are a scientific reasoning assistant..."""  # Hardcoded!
)
```

**Fix Required:**
```python
# Read prompt template from config
prompt_template_str = config.get("prompt_base_template", DEFAULT_PROMPT_TEMPLATE)

# Replace placeholders to match script's variable names
prompt_template_str = prompt_template_str.replace("{FILENAME}", "{manuscript_text}")
prompt_template_str = prompt_template_str.replace("{question_from_question_list}", "{specific_question}")

prompt_template = PromptTemplate(
    input_variables=["manuscript_text", "specific_question"],
    partial_variables={"format_instructions": format_instructions},
    template=prompt_template_str
)
```

### 2. **Limited Response Schema**
Current schema only supports "answer" and "reason", not "evidence_quotes".

**Current Code (lines 737-748):**
```python
response_schemas = [
    {
        "name": "answer",
        "type": "string",
        "description": "The answer to the question: Yes, No, or Unclear"
    },
    {
        "name": "reason", 
        "type": "string",
        "description": "Brief explanation of the answer based on the manuscript"
    }
]
```

**Fix Required:**
```python
response_schemas = [
    {
        "name": "answer",
        "type": "string", 
        "description": "The answer to the question: Yes, No, or Unclear"
    },
    {
        "name": "reason",
        "type": "string",
        "description": "Brief explanation of the answer based on the manuscript"
    },
    {
        "name": "evidence_quotes",
        "type": "array",
        "description": "Direct quotes from the manuscript supporting the answer",
        "items": {"type": "string"}
    }
]
```

### 3. **Output Parser Compatibility**
The fallback parsing methods need to handle the new "evidence_quotes" field.

**Current Code (lines 820-836):**
```python
# Fallback parsing
answer_match = re.search(r'"answer":\s*"([^"]+)"', response, re.IGNORECASE)
reason_match = re.search(r'"reason":\s*"([^"]+)"', response, re.IGNORECASE | re.DOTALL)
```

**Fix Required:**
Add evidence quotes extraction:
```python
# Extract evidence quotes
evidence_quotes = []
evidence_match = re.search(r'"evidence_quotes":\s*\[(.*?)\]', response, re.DOTALL)
if evidence_match:
    quotes_str = evidence_match.group(1)
    evidence_quotes = re.findall(r'"([^"]+)"', quotes_str)

return {
    "answer": answer or "Unclear",
    "reason": reason or "Unable to extract reasoning",
    "evidence_quotes": evidence_quotes
}
```

### 4. **Result Storage Update**
Update result dictionary to include evidence quotes.

**Current Code (lines 1138-1145):**
```python
result = {
    "variant_id": output_dir.name,
    "article_id": article_id,
    "criterion_code": criterion_code,
    "answer": analysis["answer"],
    "reason": analysis["reason"],
    "timestamp": datetime.now().isoformat()
}
```

**Fix Required:**
```python
result = {
    "variant_id": output_dir.name,
    "article_id": article_id,
    "criterion_code": criterion_code,
    "answer": analysis["answer"],
    "reason": analysis["reason"],
    "evidence_quotes": analysis.get("evidence_quotes", []),
    "timestamp": datetime.now().isoformat()
}
```

## Quick Workaround (Without Script Changes)

Until the script is modified, you can work around these issues by:

1. **Modifying the prompt to fit current constraints:**
   - Remove the `{format_instructions}` placeholder
   - Use `{FILENAME}` and `{question_from_question_list}` as-is
   - Ask for evidence within the "reason" field

2. **Example Workaround Prompt:**
```yaml
prompt_base_template: |
  You are an expert clinical geneticist analyzing scientific literature.
  
  Analyze the manuscript and answer with a JSON object containing:
  - "answer": "Yes", "No", or "Unclear"
  - "reason": Your explanation INCLUDING 1-3 direct quotes from the text
  
  Manuscript:
  """
  {FILENAME}
  """
  
  Question: {question_from_question_list}
  
  Output JSON only:
```

## Recommended Implementation Priority

1. **High Priority**: Make script use `prompt_base_template` from config
2. **Medium Priority**: Add support for `evidence_quotes` field
3. **Low Priority**: Enhanced validation and fallback parsing

These changes would make the script significantly more flexible and allow users to optimize prompts for their specific use cases and models.