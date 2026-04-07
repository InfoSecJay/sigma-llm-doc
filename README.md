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
  - **Google Gemini** (`GEMINI_API_KEY`) -- or Vertex AI with Application Default Credentials

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
#   GEMINI_API_KEY=your-gemini-key-here
```

Optionally, copy `config.example.yaml` to `sigma-llm-doc.yaml` to customize defaults:

```bash
cp config.example.yaml sigma-llm-doc.yaml
```

## Usage

After installation, the `sigma-llm-doc` command is available. You can also run it as a Python module:

```bash
sigma-llm-doc ./rules/
# or
python -m sigma_llm_doc ./rules/
```

```
usage: sigma-llm-doc [-h] [--config CONFIG] [--prompt PROMPT]
                     [--output OUTPUT] [--provider {openai,claude,gemini}]
                     [--model MODEL] [--concurrency N] [--force] [--check]
                     [--base-url URL] [--proxy URL]
                     [--vertexai] [--gcp-project ID] [--gcp-location REGION]
                     [--gcp-credentials PATH]
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
  --provider {openai,claude,gemini}
                        LLM provider (default: openai)
  --model MODEL         LLM model to use (default depends on provider)
  --concurrency N       Max concurrent API calls (default: 5)
  --force               Regenerate all guides, ignoring cache
  --check               Validate existing guides without generating new ones
  --base-url URL        Custom API base URL (e.g., Azure OpenAI endpoint)
  --proxy URL           HTTP/HTTPS proxy URL
  --vertexai            Use Google Vertex AI instead of consumer Gemini API
  --gcp-project ID      Google Cloud project ID (Vertex AI)
  --gcp-location REGION Vertex AI location (e.g., us-central1)
  --gcp-credentials PATH Path to GCP service account JSON file (Vertex AI)
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

Use Google Gemini:

```bash
sigma-llm-doc ./sigma-rules/ --provider gemini
```

Use a specific Gemini model:

```bash
sigma-llm-doc ./sigma-rules/ --provider gemini --model gemini-2.5-pro
```

Use Google Vertex AI (enterprise GCP):

```bash
sigma-llm-doc ./sigma-rules/ --provider gemini --vertexai \
  --gcp-project my-gcp-project --gcp-location us-central1
```

Use through a corporate proxy:

```bash
sigma-llm-doc ./sigma-rules/ --proxy http://proxy.corp.example.com:8080
```

Use a custom API endpoint (e.g., Azure OpenAI):

```bash
sigma-llm-doc ./sigma-rules/ --provider openai \
  --base-url https://my-deployment.openai.azure.com/
```

## Configuration

Configuration is resolved with this priority: **CLI arguments > config file > defaults**.

### Config File

Create `sigma-llm-doc.yaml` (or specify a path with `--config`):

```yaml
llm:
  provider: openai          # openai, claude, or gemini
  model: gpt-4o-mini        # model name (default depends on provider)
  api_key_env: OPENAI_API_KEY
  # Enterprise / network options (optional)
  # base_url: https://custom.api.example.com/v1
  # proxy: http://proxy.corp.example.com:8080
  # Vertex AI options (Gemini only)
  # vertexai: true
  # gcp_project: my-gcp-project
  # gcp_location: us-central1
processing:
  concurrency: 5
  max_retries: 3
  api_max_retries: 3
output:
  directory: ./output
```

### Supported Providers

| Provider | `--provider` | Default Model | API Key Env Var | Auth Method |
|----------|-------------|---------------|-----------------|-------------|
| OpenAI | `openai` | `gpt-4o-mini` | `OPENAI_API_KEY` | API key |
| Anthropic Claude | `claude` | `claude-sonnet-4-5-20250929` | `ANTHROPIC_API_KEY` | API key |
| Google Gemini | `gemini` | `gemini-2.5-flash` | `GEMINI_API_KEY` | API key |
| Google Vertex AI | `gemini` + `--vertexai` | `gemini-2.5-flash` | N/A | GCP ADC |

When you switch providers with `--provider`, the default model and API key env var are automatically resolved. You can override the model with `--model` or the env var with `api_key_env` in the config file.

### Vertex AI (Enterprise GCP)

For organizations using Google Cloud Vertex AI instead of the consumer Gemini API:

```bash
sigma-llm-doc ./rules/ --provider gemini --vertexai \
  --gcp-project my-project --gcp-location us-central1
```

Vertex AI uses Application Default Credentials (ADC) instead of API keys. Authentication methods:
- **Service account JSON file** (recommended for CI/CD): `--gcp-credentials /path/to/sa.json`
- **GCE/GKE**: Automatic via instance metadata
- **CI/CD**: Service account key file via `GOOGLE_APPLICATION_CREDENTIALS` env var
- **Local dev**: `gcloud auth application-default login`

Use a service account with explicit credentials:

```bash
sigma-llm-doc ./rules/ --provider gemini --vertexai \
  --gcp-project my-project --gcp-location us-central1 \
  --gcp-credentials /path/to/service-account.json
```

GCP project, location, and credentials can also be set via environment variables:
- `GOOGLE_CLOUD_PROJECT` -- GCP project ID
- `GOOGLE_CLOUD_LOCATION` -- Vertex AI region (e.g., `us-central1`)
- `GOOGLE_APPLICATION_CREDENTIALS` -- path to service account JSON file

### Proxy and Custom Endpoints

For enterprise environments behind a proxy or using custom API endpoints:

```yaml
# sigma-llm-doc.yaml
llm:
  provider: openai
  proxy: http://proxy.corp.example.com:8080
  # or custom base URL (e.g., Azure OpenAI, API gateway)
  # base_url: https://my-deployment.openai.azure.com/
```

Or via CLI: `--proxy URL` and `--base-url URL`.

All three providers also respect the standard `HTTP_PROXY`, `HTTPS_PROXY`, and `NO_PROXY` environment variables automatically.

### Environment Variables

The API key is read from the environment variable for the selected provider (`OPENAI_API_KEY` for OpenAI, `ANTHROPIC_API_KEY` for Claude, `GEMINI_API_KEY` for Gemini). You can set it via:

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
4. **Send changed rules to the LLM** in batches with semaphore-controlled concurrency
5. **Validate the response** against required section headers, formatting rules, and minimum length
6. **Post-process** the response (strip dividers, normalize whitespace, append disclaimer)
7. **Retry on validation failure** up to `max_retries` times
8. **Write enriched rules** to the output directory, mirroring the source directory structure
9. **Update the cache** and print a summary report with token usage

### Output Validation

Every LLM response is validated before being written. The validator checks:

- All four required `###` headers present (Technical Context, Investigation Steps, Prioritization, Blind Spots and Assumptions)
- No horizontal rule dividers (`---`)
- No numbered lists (must use dash `-` bullets)
- No `*` bullets, no triple-backtick code blocks
- Only `###` level headers (no `#` or `##`)
- At least 3 bullet points in Investigation Steps
- Minimum 200 character response length
- Non-empty content in each section

### YAML Fidelity

The tool uses `ruamel.yaml` for all YAML operations to preserve key ordering, flow style, quotes, and block scalar formatting. Only the `note` field is added or modified -- all other content is preserved exactly. The `note` value is written as a YAML block scalar (`|` style) using `LiteralScalarString`.

### Change Detection

A JSON cache file (`.sigma-llm-doc-cache.json`) is stored in the output directory. A rule is skipped only when:

1. The prompt hash matches (prompt hasn't changed)
2. The rule's content hash matches (rule hasn't changed)
3. The output file exists with a non-empty `note` field

Use `--force` to bypass all caching and regenerate every guide.

### Security

- **Path traversal prevention**: Output files are verified to stay within the output directory
- **Symlink protection**: Files that resolve outside the input directory are excluded during collection
- **Response length guard**: LLM responses exceeding 50,000 characters are rejected
- **Config validation**: Provider, model, concurrency, and retry values are validated at startup

## CI/CD Integration

See [docs/gitlab-cicd-guide.md](docs/gitlab-cicd-guide.md) for a complete GitLab CI/CD integration guide covering:

- Pipeline configuration (`.gitlab-ci.yml` templates)
- API key management with CI/CD variables
- Merge request and nightly enrichment workflows
- Provider selection and cost management
- Troubleshooting and best practices

## Testing

```bash
pytest
```

The test suite covers all modules: validator, cache, providers, config, processor, and CLI (82 tests).

## Troubleshooting

### `Expecting value: line 1 column 1 (char 0)` — Empty API responses

**Symptom**: Every rule fails with this JSON decode error, but the HTTP response shows `200 OK`.

**Cause**: A corporate proxy is intercepting HTTPS traffic and returning its own response (HTML block page) instead of the actual API response. Check the response headers — if you see `Content-Type: text/html` instead of `application/json`, the proxy is the problem.

**Solutions**:

1. **Switch to Vertex AI with a service account** (recommended for corporate environments):
   ```bash
   sigma-llm-doc ./rules/ --provider gemini --vertexai \
     --gcp-project my-project --gcp-location us-central1 \
     --gcp-credentials /path/to/sa.json
   ```
   Vertex AI uses `*.googleapis.com` endpoints which corporate networks typically allow.

2. **Bypass the proxy for the Gemini API** (if using consumer API):
   ```bash
   export NO_PROXY="${NO_PROXY},generativelanguage.googleapis.com"
   export no_proxy="${no_proxy},generativelanguage.googleapis.com"
   ```

3. **Patch the certifi CA bundle** so `httpx` trusts your corporate CA:
   ```bash
   python -c "
   import certifi
   with open('/etc/ssl/certs/ca-certificates.crt', 'rb') as corp, open(certifi.where(), 'ab') as bundle:
       bundle.write(b'\n')
       bundle.write(corp.read())
   "
   ```

> **Note**: The `google-genai` SDK uses `httpx` internally, which does NOT respect `REQUESTS_CA_BUNDLE` or `SSL_CERT_FILE` environment variables. Setting those only helps `requests`-based libraries, not `httpx`.

### GitLab CI job log exceeds 4MB limit

**Symptom**: `Job's log exceeded limit of 4194304 bytes. Job execution will continue but no more output will be collected.`

**Cause**: Running with `--verbose` logs the full raw and cleaned LLM response for every rule at DEBUG level. With 400+ rules, this easily exceeds GitLab's default 4MB log limit.

**Solutions**:

1. **Don't use `--verbose` in CI** (recommended). Normal INFO level still shows batch progress, errors, and the final summary. The full DEBUG log is always written to `<output_dir>/sigma-llm-doc.log` regardless of console verbosity.

2. **Redirect verbose output to a file artifact**:
   ```yaml
   script:
     - sigma-llm-doc ./rules/ --provider gemini --vertexai
         --gcp-project $GCP_PROJECT --gcp-location $GCP_LOCATION
         --gcp-credentials $GCP_SA_KEY
         --concurrency 10 --verbose 2> verbose.log || true

   artifacts:
     paths:
       - verbose.log
       - ./output/sigma-llm-doc.log
     when: always
     expire_in: 7 days
   ```

3. **Increase the runner log limit** (requires admin access to GitLab Runner):
   ```toml
   # /etc/gitlab-runner/config.toml
   [[runners]]
     output_limit = 16384  # 16MB, default is 4MB (value in KB)
   ```

### Logging levels

| Flag | Console Level | Use Case |
|------|--------------|----------|
| *(default)* | INFO | CI/CD — batch progress, errors, summary |
| `--verbose` | DEBUG | Local debugging — full LLM responses, HTTP details |
| `--quiet` | ERROR | Scripting — only errors and the final summary |

The file log (`<output_dir>/sigma-llm-doc.log`) always captures DEBUG level regardless of the console flag. Download it as a CI artifact when you need to troubleshoot a specific rule failure.

### GitLab CI push fails with 403

**Symptom**: `remote: You are not allowed to push code to this project. fatal: unable to access ... 403`

**Cause**: `CI_JOB_TOKEN` is read-only by default and cannot push code.

**Solution**: Use a Project Access Token with `write_repository` scope:

1. In GitLab, go to **Settings → Access Tokens**
2. Create a token with `write_repository` scope (role: Maintainer)
3. Add it as a CI/CD variable named `GITLAB_PUSH_TOKEN` (masked, protected)
4. In your `.gitlab-ci.yml`:
   ```yaml
   before_script:
     - git remote set-url origin "https://ci-push-token:${GITLAB_PUSH_TOKEN}@${CI_SERVER_HOST}/${CI_PROJECT_PATH}.git"
   ```

## Project Structure

```
sigma-llm-doc/
  pyproject.toml              # PEP 621 project metadata, deps, entry point
  LICENSE                     # MIT License
  .gitignore
  .env.example                # Example environment file
  config.example.yaml         # Example config file
  README.md
  docs/
    gitlab-cicd-guide.md      # GitLab CI/CD integration guide
  src/
    sigma_llm_doc/
      __init__.py
      __main__.py             # python -m sigma_llm_doc support
      cli.py                  # CLI entry point (argparse, logging, summary)
      llm_provider.py         # LLM providers (OpenAI, Claude, Gemini)
      processor.py            # Core logic: load rules, detect changes, orchestrate
      validator.py            # Validate generated markdown against required format
      cache.py                # Content + prompt hashing, cache read/write
      config.py               # Config file loading, defaults, CLI arg merging
      default_prompt.txt      # Default investigation guide prompt
  tests/
    test_validator.py         # Validator unit tests
    test_cache.py             # Cache and hashing unit tests
    test_providers.py         # Provider registration, mocked API calls, retry logic
    test_config.py            # Config resolution, validation, provider defaults
    test_processor.py         # Processing pipeline, clean_markdown, check mode
    test_cli.py               # Argument parsing tests
  prompt_tests/               # Model comparison outputs and cost analysis
    cost_analysis.md
    model_ranking.md
    sample_outputs/           # Per-model investigation guide samples
```
