# sigma-llm-doc

Automatically generate LLM-powered investigation guides for Sigma detection rules and append them as the `note` field in the YAML output.

## Pipeline Context

This tool is **Step 1** in a detection-as-code CI/CD pipeline:

```
Mirrored external Sigma repo (SigmaHQ, LOLRMM, custom)
        |
        v
   sigma-llm-doc  -->  Enriched Sigma rules (with `note` field)
        |
        v
   Sigma-to-TOML converter  -->  Elastic SIEM-compatible rules
```

## Requirements

- Python 3.10+
- An API key for at least one supported provider:
  - **OpenAI** (`OPENAI_API_KEY`) -- default provider
  - **Anthropic Claude** (`ANTHROPIC_API_KEY`)

## Installation

```bash
pip install -e .
```

For development (includes pytest):

```bash
pip install -e ".[dev]"
```

Copy `.env.example` to `.env` and add your API key(s):

```bash
cp .env.example .env
# Edit .env and set your provider's API key:
#   OPENAI_API_KEY=sk-...
#   ANTHROPIC_API_KEY=sk-ant-...
```

Optionally, copy `config.example.yaml` to `sigma-llm-doc.yaml` to customize defaults:

```bash
cp config.example.yaml sigma-llm-doc.yaml
```

## Usage

After installation, the `sigma-llm-doc` command is available:

```
usage: sigma-llm-doc [-h] [--config CONFIG] [--prompt PROMPT]
                     [--output OUTPUT] [--provider {openai,claude}]
                     [--model MODEL] [--concurrency N] [--force] [--check]
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
  --provider {openai,claude}
                        LLM provider (default: openai)
  --model MODEL         LLM model to use (default depends on provider)
  --concurrency N       Max concurrent API calls (default: 5)
  --force               Regenerate all guides, ignoring cache
  --check               Validate existing guides without generating new ones
  --verbose             Increase log verbosity (debug level)
  --quiet               Suppress all output except errors and summary
```

### Examples

Process a single rule:

```bash
sigma-llm-doc rules/windows/process_creation/suspicious_cmd.yml
```

Process an entire directory:

```bash
sigma-llm-doc ./sigma-rules/ --output ./enriched-rules/
```

Force regeneration of all guides:

```bash
sigma-llm-doc ./sigma-rules/ --force
```

Validate existing guides (CI gate):

```bash
sigma-llm-doc ./enriched-rules/ --check
```

Use a custom prompt and model:

```bash
sigma-llm-doc ./sigma-rules/ --prompt my_prompt.txt --model gpt-4o
```

Use Claude as the LLM provider:

```bash
sigma-llm-doc ./sigma-rules/ --provider claude
```

Use a specific Claude model:

```bash
sigma-llm-doc ./sigma-rules/ --provider claude --model claude-opus-4-6-20250929
```

## Configuration

Configuration is resolved with this priority: **CLI arguments > config file > defaults**.

### Config File

Create `sigma-llm-doc.yaml` (or specify a path with `--config`):

```yaml
llm:
  provider: openai          # openai or claude
  model: gpt-4o-mini        # model name (default depends on provider)
  api_key_env: OPENAI_API_KEY
processing:
  concurrency: 5
  max_retries: 3
  api_max_retries: 3
output:
  directory: ./output
```

### Supported Providers

| Provider | `--provider` | Default Model | API Key Env Var |
|----------|-------------|---------------|-----------------|
| OpenAI | `openai` | `gpt-4o-mini` | `OPENAI_API_KEY` |
| Anthropic Claude | `claude` | `claude-sonnet-4-5-20250929` | `ANTHROPIC_API_KEY` |

When you switch providers with `--provider`, the default model and API key env var are automatically resolved. You can override the model with `--model` or the env var with `api_key_env` in the config file.

### Environment Variables

The API key is read from the environment variable for the selected provider (`OPENAI_API_KEY` for OpenAI, `ANTHROPIC_API_KEY` for Claude). You can set it via:

- A `.env` file in the project root (loaded automatically via `python-dotenv`)
- A system environment variable
- A CI/CD secret (e.g., GitLab CI variable)

## Exit Codes

| Code | Meaning |
|------|---------|
| 0    | Success -- all rules processed or skipped successfully |
| 1    | Error -- unrecoverable error (bad config, missing input, etc.) |
| 2    | Partial failure -- some rules failed after retries (see summary) |

## How It Works

1. **Load rules** from the input path (file or directory walk)
2. **Hash each rule's content** (excluding the `note` field) and compare against a JSON cache
3. **Skip unchanged rules** where the content hash and prompt hash match the cache
4. **Send changed rules to the LLM** with the investigation guide prompt
5. **Validate the response** against required section headers, formatting rules, and minimum length
6. **Retry on validation failure** up to `max_retries` times
7. **Write enriched rules** to the output directory, mirroring the source directory structure
8. **Update the cache** and print a summary report

### YAML Fidelity

The tool uses `ruamel.yaml` for all YAML operations to preserve key ordering, flow style, quotes, and block scalar formatting. Only the `note` field is added or modified -- all other content is preserved exactly. The `note` value is written as a YAML block scalar (`|` style) using `LiteralScalarString`.

### Change Detection

A JSON cache file (`.sigma-llm-doc-cache.json`) is stored in the output directory. A rule is skipped only when:

1. The prompt hash matches (prompt hasn't changed)
2. The rule's content hash matches (rule hasn't changed)
3. The output file exists with a non-empty `note` field

Use `--force` to bypass all caching and regenerate every guide.

## Testing

```bash
pytest
```

## Project Structure

```
sigma-llm-doc/
  pyproject.toml              # PEP 621 project metadata, deps, entry point
  .gitignore
  .env.example                # Example environment file
  config.example.yaml         # Example config file
  README.md
  src/
    sigma_llm_doc/
      __init__.py
      cli.py                  # CLI entry point (argparse, logging, summary)
      llm_provider.py         # LLM abstraction layer (OpenAI, Claude)
      processor.py            # Core logic: load rules, detect changes, orchestrate
      validator.py            # Validate generated markdown against required format
      cache.py                # Content + prompt hashing, cache read/write
      config.py               # Config file loading, defaults, CLI arg merging
      default_prompt.txt      # Default investigation guide prompt
  tests/
    test_validator.py         # Validator unit tests
    test_cache.py             # Cache and hashing unit tests
```
