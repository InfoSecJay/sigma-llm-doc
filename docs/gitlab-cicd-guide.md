# GitLab CI/CD Integration Guide

Complete guide for deploying sigma-llm-doc in an enterprise GitLab CI/CD pipeline for automated Sigma rule enrichment.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Repository Setup](#repository-setup)
- [GitLab CI/CD Configuration](#gitlab-cicd-configuration)
- [API Key Management](#api-key-management)
- [Pipeline Workflows](#pipeline-workflows)
- [Provider Selection](#provider-selection)
- [Cost Management](#cost-management)
- [Troubleshooting](#troubleshooting)
- [Security Considerations](#security-considerations)
- [Best Practices](#best-practices)

---

## Architecture Overview

```
┌─────────────────────┐     ┌──────────────────────┐     ┌─────────────────────┐
│  Upstream Sigma      │     │  sigma-llm-doc        │     │  Enriched Rules      │
│  Rules (SigmaHQ,     │────>│  GitLab Pipeline      │────>│  Repository          │
│  LOLRMM, custom)     │     │                        │     │  (with note field)   │
└─────────────────────┘     └──────────────────────┘     └─────────────────────┘
                                      │                            │
                                      v                            v
                              LLM Provider API              Sigma-to-TOML
                              (OpenAI/Claude/Gemini)        Elastic SIEM Rules
```

The pipeline has three stages:
1. **generate** — Enrich Sigma rules with LLM-generated investigation guides
2. **validate** — Check that all enriched rules pass format validation
3. **deploy** — Commit enriched rules back or push to a downstream repository

---

## Repository Setup

### Option A: Monorepo (Rules + Tool)

```
detection-rules/
├── .gitlab-ci.yml
├── sigma-llm-doc.yaml          # Tool configuration
├── rules/                      # Raw Sigma rules (mirrored from upstream)
│   ├── sigmahq/
│   ├── lolrmm/
│   └── custom/                 # Your organization's custom rules
├── enriched/                   # Output: enriched rules with investigation guides
└── tools/
    └── sigma-llm-doc/          # Forked/submoduled tool
```

### Option B: Separate Repos (Recommended)

- **sigma-rules-raw** — Mirror of upstream Sigma repos (SigmaHQ, LOLRMM)
- **sigma-llm-doc** — Forked tool (your customizations, prompt tuning)
- **sigma-rules-enriched** — Enriched output (committed by CI pipeline)

This separation keeps concerns clean and allows independent versioning.

### Fork Setup

1. Fork `sigma-llm-doc` to your GitLab group
2. Clone and customize:
   - Edit `src/sigma_llm_doc/default_prompt.txt` for your environment
   - Update `sigma-llm-doc.yaml` with your preferred provider/model
3. Install in the pipeline: `pip install -e ./tools/sigma-llm-doc`

---

## GitLab CI/CD Configuration

### Basic `.gitlab-ci.yml`

```yaml
stages:
  - generate
  - validate
  - deploy

variables:
  RULES_INPUT: "./rules"
  RULES_OUTPUT: "./enriched"
  LLM_PROVIDER: "openai"
  LLM_MODEL: "gpt-4o-mini"
  CONCURRENCY: "5"

# Install sigma-llm-doc
.setup: &setup
  before_script:
    - pip install -e ./tools/sigma-llm-doc

generate:
  stage: generate
  <<: *setup
  script:
    - sigma-llm-doc "$RULES_INPUT" --output "$RULES_OUTPUT" --provider "$LLM_PROVIDER" --model "$LLM_MODEL" --concurrency "$CONCURRENCY"
  artifacts:
    paths:
      - enriched/
    expire_in: 1 week
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH

validate:
  stage: validate
  <<: *setup
  script:
    - sigma-llm-doc "$RULES_OUTPUT" --check
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH

deploy:
  stage: deploy
  <<: *setup
  script:
    - |
      cd "$RULES_OUTPUT"
      git add -A
      git diff --cached --quiet && echo "No changes to deploy" && exit 0
      git commit -m "Update enriched rules [CI skip]"
      git push
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
```

### Docker-Based Pipeline

If your GitLab runners use Docker:

```yaml
image: python:3.12-slim

generate:
  stage: generate
  before_script:
    - pip install --no-cache-dir -e ./tools/sigma-llm-doc
  script:
    - python -m sigma_llm_doc "$RULES_INPUT" --output "$RULES_OUTPUT" --provider "$LLM_PROVIDER"
```

### Scheduled Pipeline (Nightly Enrichment)

For nightly re-enrichment of upstream rule updates:

```yaml
generate-nightly:
  stage: generate
  <<: *setup
  script:
    - sigma-llm-doc "$RULES_INPUT" --output "$RULES_OUTPUT" --provider "$LLM_PROVIDER"
  rules:
    - if: $CI_PIPELINE_SOURCE == "schedule"
```

Create the schedule in **GitLab > CI/CD > Schedules** with a daily cron (e.g., `0 2 * * *`).

---

## API Key Management

### Setting CI/CD Variables

1. Go to **Settings > CI/CD > Variables** in your GitLab project
2. Add the variable for your chosen provider:

| Variable Name | Provider | Flags |
|--------------|----------|-------|
| `OPENAI_API_KEY` | OpenAI | Masked, Protected |
| `ANTHROPIC_API_KEY` | Anthropic Claude | Masked, Protected |
| `GEMINI_API_KEY` | Google Gemini | Masked, Protected |

**Important flags:**
- **Masked** — Prevents the key from appearing in job logs
- **Protected** — Only available on protected branches (recommended for deploy jobs)

### Group-Level Variables

For shared API keys across multiple projects, set variables at the GitLab **Group** level:
- **Group > Settings > CI/CD > Variables**

### Rotating Keys

1. Generate a new API key from your provider's dashboard
2. Update the GitLab CI/CD variable
3. No code changes required — the tool reads from environment variables

---

## Pipeline Workflows

### Merge Request Workflow

```
Feature Branch: Add/modify Sigma rules
       │
       ▼
MR Created ──> generate stage ──> validate stage
       │              │                   │
       │         Enrich new/changed    Check all rules
       │         rules via LLM API     pass validation
       │              │                   │
       ▼              ▼                   ▼
MR Approved ──> Merge to main ──> deploy stage
                                       │
                                  Commit enriched rules
                                  to downstream repo
```

**Key benefits:**
- New rules get investigation guides automatically on MR
- Validation gate prevents broken formatting from merging
- Cache ensures only new/changed rules call the LLM API

### Force Regeneration

To regenerate all rules (e.g., after changing the prompt):

```yaml
generate-force:
  stage: generate
  <<: *setup
  script:
    - sigma-llm-doc "$RULES_INPUT" --output "$RULES_OUTPUT" --provider "$LLM_PROVIDER" --force
  rules:
    - if: $CI_PIPELINE_SOURCE == "web"
      when: manual
```

Trigger manually from **CI/CD > Pipelines > Run Pipeline**.

---

## Provider Selection

### Comparison Table

| Provider | Default Model | Quality | Cost (4000 rules) | Speed |
|----------|--------------|---------|-------------------|-------|
| OpenAI | gpt-4o-mini | Low | ~$4 | Fast |
| OpenAI | gpt-4o | Medium | ~$40 | Medium |
| Anthropic | claude-sonnet-4-5 | High | ~$87 | Medium |
| Anthropic | claude-opus-4-6 | Highest | ~$145 | Slow |
| Google | gemini-2.5-flash | Medium | ~$3 | Fast |
| Google | gemini-2.5-pro | High | ~$30 | Medium |

### Recommended Strategy

- **Development/testing**: Use `gemini-2.5-flash` or `gpt-4o-mini` (cheapest, fastest)
- **Production**: Use `claude-sonnet-4-5` or `gpt-4o` (best quality/cost balance)
- **Premium quality**: Use `claude-opus-4-6` (highest quality investigation guides)

### Switching Providers

Via CI/CD variables (no code changes):

```yaml
variables:
  LLM_PROVIDER: "claude"
  LLM_MODEL: "claude-sonnet-4-5-20250929"
```

Or via command line:

```bash
sigma-llm-doc ./rules --provider claude --model claude-opus-4-6-20250929
```

---

## Cost Management

### Cache-Based Cost Control

The tool uses a JSON cache (`.sigma-llm-doc-cache.json`) to skip unchanged rules. This is the primary cost control mechanism:

- **Rule unchanged + prompt unchanged** = Skipped (no API call)
- **Rule changed OR prompt changed** = Processed (API call)
- **`--force` flag** = All rules processed (full API cost)

### Token Usage Tracking

The run summary now includes token counts:

```
Total rules found:       4,035
Processed (new/updated): 150
Skipped (unchanged):     3,885
Failed (after retries):  0

Input tokens:    260,250
Output tokens:   163,500
Total tokens:    423,750
```

Use this data to estimate costs: `(input_tokens * input_price + output_tokens * output_price) / 1_000_000`

### Concurrency Tuning

Higher concurrency = faster completion but may hit rate limits:

| Provider | Recommended Concurrency | Notes |
|----------|------------------------|-------|
| OpenAI (gpt-4o-mini) | 10-20 | High rate limits |
| OpenAI (gpt-4o) | 5-10 | Lower rate limits |
| Anthropic | 3-5 | Strict rate limits on new accounts |
| Gemini | 5-10 | Generous free tier |

```bash
sigma-llm-doc ./rules --concurrency 10
```

### Budget Alerts

Monitor your LLM provider dashboards:
- **OpenAI**: Settings > Usage > Set budget alerts
- **Anthropic**: Console > Usage
- **Google**: AI Studio > API keys > Usage

---

## Troubleshooting

### Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `API key not found` | Missing env var | Set the correct CI/CD variable |
| `insufficient_quota (429)` | API credits exhausted | Add credits in provider dashboard |
| `Rate limited` | Too many concurrent calls | Reduce `--concurrency` |
| `Validation failed Nx` | LLM output doesn't match format | Check prompt, try different model |
| `YAML parse error` | Malformed input rule | Fix the source YAML file |
| `Path traversal blocked` | Symlink or `..` in rule path | Remove symlinks from input |

### Debugging

1. **Enable verbose logging**: `--verbose` flag shows all API calls and validation details
2. **Check the log file**: `<output_dir>/sigma-llm-doc.log` has full DEBUG output
3. **Run on a single rule**: Test with one file before batch processing
4. **Validate without API**: `--check` mode validates existing output offline

### Cache Issues

If rules are unexpectedly skipped or re-processed:

1. Check the cache file: `<output_dir>/.sigma-llm-doc-cache.json`
2. Delete the cache to force full re-processing: `rm .sigma-llm-doc-cache.json`
3. Use `--force` to bypass cache entirely

---

## Security Considerations

### API Key Protection

- **Never** commit API keys to the repository
- Use GitLab CI/CD masked variables
- Rotate keys periodically
- Use protected variables for production branches

### Input Validation

The tool includes built-in protections:
- **Path traversal prevention**: Output files are verified to stay within the output directory
- **Symlink protection**: Files that resolve outside the input directory are excluded
- **Response length guard**: Excessively long LLM responses are rejected (50,000 char limit)

### Output Review

LLM-generated investigation guides should be reviewed:
- **Automated**: The `--check` validation gate catches formatting issues
- **Manual**: Security team should periodically review guides for accuracy
- **Disclaimer**: Every guide includes a disclaimer about AI-generated content

### Network Security

For restricted environments:
- Allowlist the API endpoints for your chosen provider
- OpenAI: `api.openai.com`
- Anthropic: `api.anthropic.com`
- Google: `generativelanguage.googleapis.com`

---

## Best Practices

### Prompt Engineering

1. **Start with the default prompt** and iterate based on your environment
2. **Test prompt changes** on 5-10 representative rules before running on all rules
3. **Include environment-specific context** (your SIEM, EDR tool names, log sources)
4. **Version your prompt** — commit changes to `default_prompt.txt` with descriptive messages

### Pipeline Design

1. **Cache the enriched output** as a GitLab artifact between stages
2. **Run validation as a separate stage** (fail fast on format issues)
3. **Use `[CI skip]` in deploy commits** to prevent pipeline loops
4. **Schedule nightly runs** for upstream rule updates
5. **Use protected branches** for the deploy stage

### Rule Management

1. **Mirror upstream repos** — Don't modify SigmaHQ rules directly
2. **Maintain a `custom/` directory** for your organization's rules
3. **Use `--check` in MR pipelines** as a quality gate
4. **Track costs** using the token usage in run summaries

### Model Selection

1. **Test multiple models** using `prompt_tests/` directory pattern
2. **Compare quality vs cost** before selecting a production model
3. **Use cheaper models for development** and premium models for production
4. **Document your model choice** in the project README or wiki

### Team Workflow

1. Detection engineers write Sigma rules (no need to write investigation guides)
2. CI pipeline automatically generates investigation guides on commit
3. SOC analysts see the investigation guide in the `note` field of deployed rules
4. Detection engineers review and tune the prompt periodically
5. Security team reviews a sample of generated guides quarterly
