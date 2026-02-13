# sigma-llm-doc — Project Template

## Project Overview

**Tool Name:** `sigma-llm-doc`
**Language:** Python 3.10+
**Type:** Standalone CLI tool (argparse)
**Purpose:** Automatically generate LLM-powered investigation guides for Sigma detection rules and append them as the `note` field in the YAML output.

### Pipeline Context

This tool is **Step 1** in a detection-as-code CI/CD pipeline:

```
Mirrored external Sigma repo (SigmaHQ, LOLRMM, custom)
        │
        ▼
   sigma-llm-doc  ──►  Enriched Sigma rules (with `note` field)
        │
        ▼
   Sigma-to-TOML converter  ──►  Elastic SIEM-compatible rules
```

Because a downstream tool parses the YAML output, **YAML fidelity is critical** — the tool must only modify the `note` field and preserve all other content, key ordering, and structure exactly.

---

## Architecture

### Project Structure

```
sigma-llm-doc/
├── sigma_llm_doc.py          # Main entry point & CLI (argparse)
├── llm_provider.py           # LLM abstraction layer (OpenAI default, swappable)
├── processor.py              # Core logic: load rules, detect changes, orchestrate
├── validator.py              # Validate generated markdown against required format
├── cache.py                  # Content + prompt hashing, cache read/write
├── config.py                 # Config file loading, defaults, CLI arg merging
├── default_prompt.txt        # Default investigation guide prompt
├── .env.example              # Example environment file
├── config.example.yaml       # Example config file
├── requirements.txt          # Python dependencies
└── README.md                 # Usage documentation
```

### Module Responsibilities

#### `sigma_llm_doc.py` (Entry Point)

- Parse CLI arguments via `argparse`
- Load and merge configuration (CLI args > config file > defaults)
- Initialize logging based on verbosity flags
- Call processor, collect results
- Print summary report
- Exit with appropriate code

#### `llm_provider.py` (LLM Abstraction)

- Define a base class/protocol `LLMProvider` with an async method `generate(prompt: str, rule_text: str) -> str`
- Implement `OpenAIProvider` as the default
  - Uses the modern `openai` Python SDK (>=1.0) with `AsyncOpenAI` client
  - Supports configurable model (default: `gpt-4o-mini`)
  - Implements exponential backoff retry (3 attempts) for API errors and rate limits
- **Design for extensibility:** Adding a new provider (Anthropic, Ollama, etc.) should only require adding a new class that implements `LLMProvider` and registering it in a provider map

#### `processor.py` (Core Orchestrator)

- Walk input directory or process single file
- For each `.yml`/`.yaml` file:
  1. Load with `ruamel.yaml` (preserving structure)
  2. Compute content hash of the rule (excluding `note` field)
  3. Check cache: skip if rule hash + prompt hash are unchanged AND output file exists with non-empty `note`
  4. Send rule to LLM provider
  5. Validate response via `validator.py`; retry up to 3 times on validation failure
  6. Write enriched rule to output directory (mirroring source structure)
  7. Update cache
- Use `asyncio.Semaphore` for concurrency control (default: 5)
- Log all outcomes (processed, skipped, failed, retried)

#### `validator.py` (Output Validation)

- Verify the LLM response contains ALL required `###` section headers:
  - `### Technical Context`
  - `### Investigation Steps`
  - `### Prioritization`
  - `### Blind Spots and Assumptions`
- Verify the disclaimer blockquote is present
- Verify dash-prefixed bullet format is used (no `*` bullets or numbered lists outside of expected sections)
- Verify no YAML code blocks or triple-backtick fences exist
- Return a validation result with pass/fail and list of specific errors
- Used by processor to decide whether to retry

#### `cache.py` (Change Detection)

- Cache file: `.sigma-llm-doc-cache.json` stored in the **output directory**
- Cache structure:
  ```json
  {
    "version": 1,
    "prompt_hash": "sha256_of_prompt_file_contents",
    "rules": {
      "path/relative/to/input/rule.yml": {
        "content_hash": "sha256_of_rule_content_minus_note_field",
        "last_processed": "2025-02-12T10:30:00Z"
      }
    }
  }
  ```
- **Content hash computation:** Load the YAML, remove the `note` field if present, serialize to a canonical string, and SHA-256 hash it
- **Prompt hash:** SHA-256 of the prompt file contents. Stored at the top level of the cache. If the prompt hash changes, ALL rules are considered stale.
- **Skip logic:** A rule is skipped if and only if:
  1. The prompt hash in the cache matches the current prompt hash
  2. The rule's content hash in the cache matches the current content hash
  3. The corresponding output file exists and has a non-empty `note` field
- `--force` flag bypasses all skip logic

#### `config.py` (Configuration)

- **Priority order:** CLI arguments > config file > defaults
- **Config file format:** YAML (`sigma-llm-doc.yaml` or path specified by `--config`)
- **Config file example:**
  ```yaml
  # sigma-llm-doc.yaml
  llm:
    provider: openai          # Future: anthropic, ollama, etc.
    model: gpt-4o-mini
    api_key_env: OPENAI_API_KEY  # Name of the env var holding the key
  processing:
    concurrency: 5
    max_retries: 3             # Retries on validation failure
    api_max_retries: 3         # Retries on API errors (rate limit, timeout)
  output:
    directory: ./output        # Default output directory
  ```
- **Environment variables:** API key loaded from `.env` file (via `python-dotenv`) or system environment. In CI/CD, this will be a GitLab CI secret injected as an env var.

---

## CLI Interface

```
usage: sigma-llm-doc [-h] [--config CONFIG] [--prompt PROMPT]
                     [--output OUTPUT] [--model MODEL]
                     [--concurrency N] [--force] [--check]
                     [--verbose | --quiet]
                     input

Generate LLM-powered investigation guides for Sigma detection rules.

positional arguments:
  input                 Path to a Sigma rule file (.yml/.yaml) or directory

optional arguments:
  -h, --help            show this help message and exit
  --config CONFIG       Path to config file (default: sigma-llm-doc.yaml)
  --prompt PROMPT       Path to prompt file (default: built-in prompt)
  --output OUTPUT       Output directory (default: ./output)
  --model MODEL         LLM model to use (default: gpt-4o-mini)
  --concurrency N       Max concurrent API calls (default: 5)
  --force               Regenerate all guides, ignoring cache
  --check               Validate existing guides without generating new ones
  --verbose             Increase log verbosity (debug level)
  --quiet               Suppress all output except errors and summary
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0    | Success — all rules processed or skipped successfully |
| 1    | Error — unrecoverable error (bad config, missing input, etc.) |
| 2    | Partial failure — some rules failed after retries (see summary) |

### Summary Report

After every run, print a summary to stdout (and log file):

```
========================================
sigma-llm-doc Run Summary
========================================
Input:        ./sigma-rules/
Output:       ./output/
Model:        gpt-4o-mini
Prompt:       default_prompt.txt (hash: a3f8c2...)

Total rules found:    3,247
Processed (new/updated): 142
Skipped (unchanged):     3,098
Failed (after retries):  7
  - rules/windows/process_creation/rule_xyz.yml: Validation failed 3x
  - rules/linux/auditd/rule_abc.yml: API timeout
  ...

Exit code: 2
========================================
```

---

## YAML Handling — Critical Requirements

### Library: `ruamel.yaml`

Use `ruamel.yaml` for all YAML operations. It preserves key ordering, flow style, and block scalar formatting.

### Reading Rules

```python
from ruamel.yaml import YAML

yaml = YAML()
yaml.preserve_quotes = True

with open(rule_path, 'r') as f:
    rule_data = yaml.load(f)
```

### Writing Rules (Output)

```python
from ruamel.yaml.scalarstring import LiteralScalarString

# Set the note field as a YAML block scalar (literal style: |)
rule_data['note'] = LiteralScalarString(cleaned_markdown)

with open(output_path, 'w') as f:
    yaml.dump(rule_data, f)
```

### Rules for YAML Integrity

1. **Only add/modify the `note` field.** Never alter any other field.
2. **Use `LiteralScalarString`** for the `note` value so it renders as a `|` block scalar in YAML (multi-line, preserves newlines).
3. **Preserve key ordering** — `ruamel.yaml` does this by default with its round-trip loader.
4. **Test round-tripping** — loading a rule and writing it back (without changes) should produce byte-identical output (minus trailing whitespace). This is a good integration test.

### Content Hash Computation

To compute the hash for change detection, remove the `note` field from a deep copy of the loaded YAML data, serialize to a string, and hash:

```python
import copy, hashlib
from io import StringIO

def compute_rule_hash(rule_data) -> str:
    data_copy = copy.deepcopy(rule_data)
    if 'note' in data_copy:
        del data_copy['note']
    stream = StringIO()
    yaml.dump(data_copy, stream)
    return hashlib.sha256(stream.getvalue().encode()).hexdigest()
```

---

## Default Prompt

Store in `default_prompt.txt`. This is the prompt from the project spec:

```
You are a senior detection engineer working for a large enterprise SOC with access to standard security tools (SIEM, EDR, NDR, NGFW, AV, Proxy, VPN, and cloud platforms like AWS, GCP, and Azure). You are tasked with generating concise, **detection-specific** and **actionable** documentation for a given detection rule in Sigma rule format.

Before writing, analyze the rule's title, description, detection logic, and references to determine:
- The suspected threat family, tool, or behavior (e.g., BloodHound, Mimikatz, Cobalt Strike).
- The MITRE ATT&CK tactics and techniques that apply.
- The types of telemetry/log sources that will contain the best evidence.

Your output must include the following sections in valid Markdown (`###` headers, dash-prefixed bullets):

### Technical Context
1–3 paragraphs explaining:
- What this rule detects.
- The threat scenario and likely attacker objectives.
- Relevant MITRE ATT&CK tactics/techniques (by name and ID).
- Primary data sources (e.g., LDAP query logs, process creation events, proxy logs).
Write clearly for responders who may not be subject matter experts.

### Investigation Steps
Provide **3–4 high-level bullet points**, each starting with a **bolded title** followed by a colon, with **vendor-agnostic but detection-specific steps**.
Include guidance for collecting and analyzing artifacts directly related to the suspected threat/tool.
For example, if the rule detects BloodHound activity, direct analysts to review LDAP bind/query logs, unusual Active Directory enumeration commands, suspicious SMB connections, and privilege escalation paths.

### Prioritization
1–2 sentences explaining the reasoning for the alert's severity in an enterprise environment, considering the threat impact and likelihood.

### Blind Spots and Assumptions
1 paragraph identifying:
- Any gaps in detection coverage.
- Assumptions made by the detection logic.
- Required logs or configurations for the alert to function.

> **Disclaimer:** This investigation guide was created using generative AI technology and has not been reviewed for its accuracy and relevance. While every effort has been made to ensure its quality, we recommend validating the content and adapting it to suit specific environments and operational needs. Please communicate any changes to the detection engineering team.

Formatting rules:
- Output only valid Markdown.
- Use `###` for section headers.
- Use dash-prefixed bullets for lists.
- Never include YAML or code blocks in the output.
```

---

## Validation Rules

The `validator.py` module checks the LLM response and returns a structured result:

### Required Checks

| Check | Rule | Fail Action |
|-------|------|-------------|
| Required headers | All four `###` headers must be present (exact text match) | Retry |
| Disclaimer | Blockquote starting with `> **Disclaimer:**` must be present | Retry |
| Bullet format | List items must use `-` prefix (no `*`, no `1.` outside expected areas) | Retry |
| No code blocks | No triple backticks (`` ``` ``) in output | Retry |
| Non-empty sections | Each section must have at least 1 line of content after the header | Retry |
| Minimum length | Total response must be at least 200 characters | Retry |

### Validation Flow

```
LLM generates response
        │
        ▼
  Run all validation checks
        │
   ┌────┴────┐
   │ PASS    │ FAIL (attempt < max_retries)
   │         │         │
   ▼         │         ▼
 Accept      │   Log validation errors
 & write     │   Re-send to LLM with
             │   original prompt
             │         │
             │         ▼
             │   FAIL (attempt = max_retries)
             │         │
             │         ▼
             │   Log as failed, skip rule,
             │   continue processing
             └─────────┘
```

---

## Logging

- Use Python's built-in `logging` module
- Log to both **console** (stderr) and **file** (`sigma-llm-doc.log` in output directory)
- Log levels:
  - `--quiet`: ERROR only on console
  - default: INFO on console
  - `--verbose`: DEBUG on console
- File log always captures DEBUG level
- Log entries include: timestamp, level, rule file path, action taken

---

## --check Mode

When `--check` is passed:
- Walk all rules in the input (or output if that makes more sense)
- For each rule with a `note` field, run the validation checks from `validator.py`
- Report which rules pass/fail validation
- Do NOT make any API calls
- Do NOT modify any files
- Useful as a CI gate to verify all rules have valid investigation guides

---

## Dependencies

### `requirements.txt`

```
ruamel.yaml>=0.18.0
openai>=1.0.0
python-dotenv>=1.0.0
```

No other external dependencies. The tool uses only `argparse`, `asyncio`, `logging`, `hashlib`, `json`, `copy`, `pathlib`, `os`, `sys`, `re`, `io`, and `datetime` from the standard library.

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Input path doesn't exist | Exit code 1, log error |
| No YAML files found in directory | Exit code 1, log warning |
| Invalid YAML file (parse error) | Log error, skip file, count as failed |
| API key not set | Exit code 1, log error with instructions |
| API rate limit hit | Exponential backoff retry (API-level, separate from validation retry) |
| API timeout / network error | Retry with backoff up to `api_max_retries` times, then fail the rule |
| LLM returns empty response | Count as validation failure, retry |
| Validation failure after max retries | Log as failed, skip rule, continue |
| Output directory doesn't exist | Create it automatically |
| Prompt file not found | Exit code 1, log error |
| Cache file corrupted/invalid JSON | Log warning, treat as empty cache (reprocess all) |

---

## Future Enhancements (Not in v1)

These are explicitly out of scope for v1 but the architecture should not prevent them:

- **Additional LLM providers:** Anthropic Claude, Ollama (local models), Azure OpenAI
- **Template variables in prompts:** Allow `{{title}}`, `{{description}}`, etc. to reference rule fields
- **Selective field forwarding:** Send only specific rule fields to the LLM instead of full YAML (token optimization)
- **Cost estimation mode:** `--estimate` flag that counts rules to process and estimates API cost without making calls
- **Parallel batch API:** Use OpenAI Batch API for large rulesets (50% cost reduction, higher latency)
- **Git-aware change detection:** Use `git diff` instead of/alongside content hashing
- **Custom validation schemas:** Allow users to define their own required sections
- **HTML/PDF report generation:** Generate a formatted report of all investigation guides

---

## Implementation Notes for the Developer

1. **Start with the LLM abstraction (`llm_provider.py`)** — get a working async OpenAI call with retry logic. Test it standalone.

2. **Then build `validator.py`** — this is simple regex/string matching but critical. Write unit tests for it with known-good and known-bad markdown samples.

3. **Then build `cache.py`** — the hashing and JSON read/write. Test that changing a single character in a rule produces a different hash.

4. **Then build `processor.py`** — this ties everything together. Start with single-file processing, then add directory walking and async concurrency.

5. **Finally, build `sigma_llm_doc.py`** — the CLI wrapper. This should be thin; all logic lives in the other modules.

6. **Test the full pipeline** with a small set of real Sigma rules from SigmaHQ before running on the full repo.

7. **YAML round-trip test:** Load a rule, dump it, load the dumped version, compare. They should be identical. Do this before adding any `note` field logic.
