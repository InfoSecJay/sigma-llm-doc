"""CLI entry point for sigma-llm-doc.

All logic lives in the other modules; this file is a thin wrapper
that parses arguments, sets up logging, calls the processor, and prints a summary.
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path

from .cache import compute_prompt_hash
from .config import load_config
from .llm_provider import get_provider
from .processor import process_rules, check_rules


def main() -> None:
    args = parse_args()

    # Load and validate configuration
    try:
        cfg = load_config(args)
    except SystemExit as e:
        sys.exit(e.code)

    # Set up logging
    setup_logging(cfg.output_dir, verbose=cfg.verbose, quiet=cfg.quiet)
    logger = logging.getLogger(__name__)

    # --check mode: validate existing guides, no API calls
    if cfg.check:
        logger.info("Running in check mode — validating existing guides")
        result = check_rules(cfg.input_path)
        print_check_summary(cfg, result)
        if result.failed > 0:
            sys.exit(2)
        sys.exit(0)

    # Initialize LLM provider
    provider = get_provider(
        cfg.provider,
        api_key=cfg.api_key,
        model=cfg.model,
        api_max_retries=cfg.api_max_retries,
    )

    # Run the async processing pipeline
    result = asyncio.run(
        process_rules(
            input_path=cfg.input_path,
            output_dir=cfg.output_dir,
            provider=provider,
            prompt_file=cfg.prompt_file,
            concurrency=cfg.concurrency,
            max_retries=cfg.max_retries,
            force=cfg.force,
        )
    )

    # Print summary
    print_summary(cfg, result)

    # Exit code
    if result.failed > 0:
        sys.exit(2)
    sys.exit(0)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="sigma-llm-doc",
        description="Generate LLM-powered investigation guides for Sigma detection rules.",
    )

    parser.add_argument(
        "input",
        help="Path to a Sigma rule file (.yml/.yaml) or directory",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to config file (default: sigma-llm-doc.yaml)",
    )
    parser.add_argument(
        "--prompt",
        default=None,
        help="Path to prompt file (default: built-in prompt)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output directory (default: ./output)",
    )
    parser.add_argument(
        "--provider",
        default=None,
        choices=["openai", "claude"],
        help="LLM provider (default: openai)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="LLM model to use (default depends on provider)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=None,
        metavar="N",
        help="Max concurrent API calls (default: 5)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Regenerate all guides, ignoring cache",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        default=False,
        help="Validate existing guides without generating new ones",
    )

    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Increase log verbosity (debug level)",
    )
    verbosity.add_argument(
        "--quiet",
        action="store_true",
        default=False,
        help="Suppress all output except errors and summary",
    )

    return parser.parse_args()


def setup_logging(output_dir: Path, verbose: bool = False, quiet: bool = False) -> None:
    """Configure logging to console (stderr) and file.

    Console level varies by verbosity flags; file always captures DEBUG.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Clear any existing handlers
    root_logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)-7s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler (stderr)
    console = logging.StreamHandler(sys.stderr)
    if quiet:
        console.setLevel(logging.ERROR)
    elif verbose:
        console.setLevel(logging.DEBUG)
    else:
        console.setLevel(logging.INFO)
    console.setFormatter(formatter)
    root_logger.addHandler(console)

    # File handler (always DEBUG)
    output_dir.mkdir(parents=True, exist_ok=True)
    log_file = output_dir / "sigma-llm-doc.log"
    file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)


def _get_prompt_hash_str(cfg) -> str:
    """Compute a short prompt hash string for the summary."""
    if cfg.prompt_file:
        with open(cfg.prompt_file, "r", encoding="utf-8") as f:
            prompt_text = f.read()
        prompt_name = str(cfg.prompt_file)
    else:
        prompt_path = Path(__file__).parent / "default_prompt.txt"
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_text = f.read()
        prompt_name = "default_prompt.txt"

    h = compute_prompt_hash(prompt_text)
    return f"{prompt_name} (hash: {h[:8]}...)"


def print_summary(cfg, result) -> None:
    """Print the run summary report."""
    prompt_str = _get_prompt_hash_str(cfg)

    lines = [
        "",
        "========================================",
        "sigma-llm-doc Run Summary",
        "========================================",
        f"Input:        {cfg.input_path}",
        f"Output:       {cfg.output_dir}",
        f"Provider:     {cfg.provider}",
        f"Model:        {cfg.model}",
        f"Prompt:       {prompt_str}",
        "",
        f"Total rules found:       {result.total:,}",
        f"Processed (new/updated): {result.processed:,}",
        f"Skipped (unchanged):     {result.skipped:,}",
        f"Failed (after retries):  {result.failed:,}",
    ]

    if result.failures:
        for failure in result.failures:
            lines.append(f"  - {failure}")

    exit_code = 2 if result.failed > 0 else 0
    lines.extend([
        "",
        f"Exit code: {exit_code}",
        "========================================",
    ])

    print("\n".join(lines))


def print_check_summary(cfg, result) -> None:
    """Print the --check mode summary report."""
    lines = [
        "",
        "========================================",
        "sigma-llm-doc Check Summary",
        "========================================",
        f"Input:          {cfg.input_path}",
        "",
        f"Total rules:    {result.total:,}",
        f"Passed:         {result.processed:,}",
        f"Failed:         {result.failed:,}",
        f"No note field:  {result.skipped:,}",
    ]

    if result.failures:
        lines.append("")
        for failure in result.failures:
            lines.append(f"  - {failure}")

    exit_code = 2 if result.failed > 0 else 0
    lines.extend([
        "",
        f"Exit code: {exit_code}",
        "========================================",
    ])

    print("\n".join(lines))
