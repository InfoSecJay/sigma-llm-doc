# LLM Model Cost Analysis for sigma-llm-doc

## Baseline Metrics (from gpt-4o-mini run)

| Metric | Value |
|---|---|
| Total rules | 4,035 |
| Avg input tokens/rule | ~1,735 (prompt + rule YAML) |
| Avg output tokens/rule | ~1,090 (investigation guide) |
| Total input tokens | ~7.0M |
| Total output tokens | ~4.4M |
| Total requests | ~7,600 (includes retries) |

---

## OpenAI Models

| Model | Input $/1M | Output $/1M | Est. Cost (4K rules) | Quality | Notes |
|---|---|---|---|---|---|
| gpt-4o-mini | $0.15 | $0.60 | **~$4** | Low | Current default. Fast, cheap, generic output. |
| gpt-5-nano | $0.05 | $0.40 | **~$2** | Low | Cheapest option. Comparable to gpt-4o-mini. |
| gpt-5-mini | $0.25 | $2.00 | **~$11** | Medium | Best value upgrade. Significant quality jump. |
| gpt-5 | $1.25 | $10.00 | **~$53** | High | Strong reasoning. Good for security content. |
| gpt-5.2 | $1.75 | $14.00 | **~$74** | Highest | Same model as ChatGPT 5.2. Best OpenAI output. |

---

## Anthropic Claude Models

| Model | Input $/1M | Output $/1M | Est. Cost (4K rules) | Batch (50% off) | Batch + Cache | Notes |
|---|---|---|---|---|---|---|
| Claude Haiku 4.5 | $1.00 | $5.00 | **~$29** | **~$15** | **~$13** | Fast. Scored 5.5/10 (format issues). |
| Claude Sonnet 4.5 | $3.00 | $15.00 | **~$87** | **~$44** | **~$38** | Balanced. Strong reasoning. |
| Claude Opus 4.5 | $5.00 | $25.00 | **~$145** | **~$73** | **~$65** | Scored 8.8/10. Best companion detections. |
| Claude Opus 4.6 | $5.00 | $25.00 | **~$145** | **~$73** | **~$65** | Scored 9.3/10. Best overall quality. |

- **Prompt caching**: Up to 90% savings on input tokens (prompt is identical across all rules). Cache reads at 10% of base input price. With caching, the ~1,000 prompt tokens per request drop to ~$0.50/1M instead of $5/1M.
- **Batch API**: 50% discount for async processing.
- Requires adding a Claude provider to sigma-llm-doc.

---

## Google Gemini Models

| Model | Input $/1M | Output $/1M | Est. Cost (4K rules) | Batch Cost (50% off) | Notes |
|---|---|---|---|---|---|
| Gemini 2.5 Flash-Lite | $0.10 | $0.40 | **~$2.50** | **~$1.25** | Cheapest overall. Quality TBD. |
| Gemini 2.5 Flash | $0.15 | $0.60 | **~$3.70** | **~$1.85** | Comparable price to gpt-4o-mini. |
| Gemini 2.5 Pro | $1.25 | $10.00 | **~$53** | **~$26** | Strong reasoning. Good batch discount. |

- **Prompt caching**: Cache reads at 10% of base input price.
- **Batch API**: 50% discount for async processing.
- Requires adding a Gemini provider to sigma-llm-doc.

---

## Cost by Budget Tier

| Budget | Best Options |
|---|---|
| < $5 | gpt-4o-mini, gpt-5-nano, Gemini Flash/Flash-Lite |
| $10-15 | **gpt-5-mini**, Claude Haiku 4.5 (batch) |
| $25-55 | gpt-5, **Gemini 2.5 Pro (batch)**, Claude Haiku 4.5 |
| $50-80 | **gpt-5.2**, Claude Sonnet 4.5 (batch) |
| $80+ | Claude Sonnet 4.5, Claude Opus 4.5 |

---

## Implementation Notes

- **Currently supported**: OpenAI models only (via `--model` flag)
- **To add**: Claude and Gemini providers would need new provider classes in `llm_provider.py`
- Many providers offer OpenAI-compatible endpoints, simplifying integration
- For manual quality comparison, paste the prompt + a sample rule into each provider's chat UI

---

## Daily Incremental Run Costs

After the initial full run, daily runs only process new/changed rules (typically 0-20 rules per day).

| Model | Est. Daily Cost (20 rules) |
|---|---|
| gpt-4o-mini | < $0.01 |
| gpt-5-mini | ~$0.05 |
| gpt-5.2 | ~$0.37 |
| Claude Haiku 4.5 | ~$0.14 |
| Gemini 2.5 Pro | ~$0.26 |
