"""Core orchestrator: load rules, detect changes, call LLM, validate, write output."""

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import LiteralScalarString

from .cache import Cache, compute_rule_hash, compute_prompt_hash
from .llm_provider import LLMProvider
from .validator import validate_response, DISCLAIMER_TEXT

logger = logging.getLogger(__name__)


@dataclass
class ProcessingResult:
    """Aggregate results from a processing run."""
    total: int = 0
    processed: int = 0
    skipped: int = 0
    failed: int = 0
    failures: list[str] = field(default_factory=list)


def _get_default_prompt() -> str:
    """Load the default prompt from default_prompt.txt."""
    prompt_path = Path(__file__).parent / "default_prompt.txt"
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


def _clean_markdown(text: str) -> str:
    """Normalize whitespace in generated markdown for clean YAML embedding.

    Collapses multiple blank lines into single blank lines, strips trailing
    whitespace from each line, and ensures a single trailing newline.
    """
    lines = text.strip().splitlines()
    output: list[str] = []
    prev_blank = True

    for line in lines:
        stripped = line.rstrip()
        if not stripped:
            if not prev_blank:
                output.append("")
            prev_blank = True
        else:
            output.append(stripped)
            prev_blank = False

    # Ensure trailing newline for YAML literal block scalar
    result = "\n".join(output)
    if not result.endswith("\n"):
        result += "\n"
    return result


def _collect_yaml_files(input_path: Path) -> list[Path]:
    """Collect all .yml/.yaml files from a file or directory path."""
    if input_path.is_file():
        if input_path.suffix.lower() in (".yml", ".yaml"):
            return [input_path]
        return []

    files = []
    for ext in ("*.yml", "*.yaml"):
        files.extend(input_path.rglob(ext))
    return sorted(files)


async def process_rules(
    input_path: Path,
    output_dir: Path,
    provider: LLMProvider,
    prompt_file: Path | None = None,
    concurrency: int = 5,
    max_retries: int = 3,
    force: bool = False,
) -> ProcessingResult:
    """Process Sigma rules: generate investigation guides and write enriched YAML.

    Args:
        input_path: Path to a single rule file or a directory of rules.
        output_dir: Directory where enriched rules are written.
        provider: The LLM provider to use for generation.
        prompt_file: Path to a custom prompt file, or None for the default.
        concurrency: Maximum number of concurrent LLM API calls.
        max_retries: Number of retries on validation failure.
        force: If True, bypass cache and regenerate all guides.

    Returns:
        A ProcessingResult with counts and failure details.
    """
    result = ProcessingResult()

    # Load prompt
    if prompt_file:
        with open(prompt_file, "r", encoding="utf-8") as f:
            prompt_text = f.read()
        logger.info("Using custom prompt: %s", prompt_file)
    else:
        prompt_text = _get_default_prompt()
        logger.info("Using default prompt")

    prompt_hash = compute_prompt_hash(prompt_text)

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize cache
    cache = Cache(output_dir)

    # Collect rule files
    yaml_files = _collect_yaml_files(input_path)
    result.total = len(yaml_files)

    if result.total == 0:
        logger.warning("No YAML files found in %s", input_path)
        raise SystemExit(1)

    logger.info("Found %d rule file(s) to process", result.total)

    # Determine the base input directory for relative path computation
    input_base = input_path if input_path.is_dir() else input_path.parent

    # Process with semaphore-controlled concurrency
    semaphore = asyncio.Semaphore(concurrency)

    async def process_one(rule_file: Path) -> None:
        async with semaphore:
            await _process_single_rule(
                rule_file=rule_file,
                input_base=input_base,
                output_dir=output_dir,
                provider=provider,
                prompt_text=prompt_text,
                prompt_hash=prompt_hash,
                cache=cache,
                max_retries=max_retries,
                force=force,
                result=result,
            )

    tasks = [asyncio.create_task(process_one(f)) for f in yaml_files]
    await asyncio.gather(*tasks)

    # Update prompt hash and save cache after all processing
    cache.set_prompt_hash(prompt_hash)
    cache.save()

    return result


async def _process_single_rule(
    rule_file: Path,
    input_base: Path,
    output_dir: Path,
    provider: LLMProvider,
    prompt_text: str,
    prompt_hash: str,
    cache: Cache,
    max_retries: int,
    force: bool,
    result: ProcessingResult,
) -> None:
    """Process a single Sigma rule file.

    Loads the YAML, checks the cache, calls the LLM, validates, and writes output.
    """
    # Compute relative path for cache key and output mirroring
    try:
        relative = rule_file.relative_to(input_base)
    except ValueError:
        relative = Path(rule_file.name)

    relative_str = str(relative).replace("\\", "/")

    # Compute output path (mirror source directory structure)
    output_file = output_dir / relative

    logger.debug("Processing: %s", relative_str)

    # Load the rule with ruamel.yaml
    yaml = YAML()
    yaml.preserve_quotes = True

    try:
        with open(rule_file, "r", encoding="utf-8") as f:
            rule_data = yaml.load(f)
    except Exception as e:
        logger.error("Failed to parse YAML: %s — %s", rule_file, e)
        result.failed += 1
        result.failures.append(f"{relative_str}: YAML parse error — {e}")
        return

    if rule_data is None:
        logger.error("Empty YAML file: %s", rule_file)
        result.failed += 1
        result.failures.append(f"{relative_str}: Empty YAML file")
        return

    # Compute content hash (excluding note field)
    content_hash = compute_rule_hash(rule_data)

    # Check cache (skip if unchanged)
    if not force and cache.should_skip(relative_str, content_hash, prompt_hash, output_file):
        logger.debug("Skipped (unchanged): %s", relative_str)
        result.skipped += 1
        return

    # Read the raw rule text to send to the LLM
    with open(rule_file, "r", encoding="utf-8") as f:
        rule_text = f.read()

    # Call LLM with validation retry loop
    response = None
    last_validation = None

    for attempt in range(1, max_retries + 1):
        try:
            raw_response = await provider.generate(prompt_text, rule_text)
        except Exception as e:
            logger.error(
                "LLM API error for %s (attempt %d/%d): %s",
                relative_str, attempt, max_retries, e,
            )
            if attempt == max_retries:
                result.failed += 1
                result.failures.append(f"{relative_str}: API error — {e}")
                return
            continue

        # Validate the response
        validation = validate_response(raw_response)
        last_validation = validation

        if validation.passed:
            response = raw_response
            break

        logger.warning(
            "Validation failed for %s (attempt %d/%d): %s",
            relative_str, attempt, max_retries, validation,
        )

    if response is None:
        logger.error(
            "Failed after %d retries: %s — %s",
            max_retries, relative_str, last_validation,
        )
        result.failed += 1
        result.failures.append(
            f"{relative_str}: Validation failed {max_retries}x"
        )
        return

    # Clean and set the note field, appending disclaimer if missing
    cleaned = _clean_markdown(response)
    if DISCLAIMER_TEXT not in cleaned:
        cleaned = cleaned.rstrip("\n") + "\n\n" + DISCLAIMER_TEXT + "\n"
    rule_data["note"] = LiteralScalarString(cleaned)

    # Write enriched rule to output directory
    output_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(output_file, "w", encoding="utf-8") as f:
            yaml.dump(rule_data, f)
        logger.info("Processed: %s", relative_str)
    except Exception as e:
        logger.error("Failed to write output for %s: %s", relative_str, e)
        result.failed += 1
        result.failures.append(f"{relative_str}: Write error — {e}")
        return

    # Update cache
    cache.update_rule(relative_str, content_hash)
    result.processed += 1


def check_rules(input_path: Path) -> ProcessingResult:
    """Validate existing investigation guides without making API calls.

    Walks the input path and checks every rule with a ``note`` field against
    the validation rules.

    Args:
        input_path: Path to a single rule file or directory of rules.

    Returns:
        A ProcessingResult where 'processed' = passed, 'failed' = failed validation.
    """
    result = ProcessingResult()

    yaml_files = _collect_yaml_files(input_path)
    result.total = len(yaml_files)

    if result.total == 0:
        logger.warning("No YAML files found in %s", input_path)
        return result

    yaml = YAML()
    yaml.preserve_quotes = True

    input_base = input_path if input_path.is_dir() else input_path.parent

    for rule_file in yaml_files:
        try:
            relative = rule_file.relative_to(input_base)
        except ValueError:
            relative = Path(rule_file.name)
        relative_str = str(relative).replace("\\", "/")

        try:
            with open(rule_file, "r", encoding="utf-8") as f:
                rule_data = yaml.load(f)
        except Exception as e:
            logger.error("Failed to parse YAML: %s — %s", rule_file, e)
            result.failed += 1
            result.failures.append(f"{relative_str}: YAML parse error")
            continue

        if rule_data is None:
            result.skipped += 1
            continue

        note = rule_data.get("note", "")
        if not note or not str(note).strip():
            result.skipped += 1
            logger.debug("No note field: %s", relative_str)
            continue

        validation = validate_response(str(note))
        if validation.passed:
            result.processed += 1
            logger.debug("PASS: %s", relative_str)
        else:
            result.failed += 1
            result.failures.append(f"{relative_str}: {validation}")
            logger.warning("FAIL: %s — %s", relative_str, validation)

    return result
