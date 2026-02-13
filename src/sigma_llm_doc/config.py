"""Configuration loading, defaults, and CLI argument merging."""

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from ruamel.yaml import YAML

logger = logging.getLogger(__name__)

# Defaults matching the project spec
DEFAULTS = {
    "provider": "openai",
    "model": "gpt-4o-mini",
    "api_key_env": "OPENAI_API_KEY",
    "concurrency": 5,
    "max_retries": 3,
    "api_max_retries": 3,
    "output": "./output",
}


@dataclass
class AppConfig:
    """Resolved application configuration."""

    input_path: Path
    output_dir: Path
    prompt_file: Path | None
    provider: str
    model: str
    api_key: str
    concurrency: int
    max_retries: int
    api_max_retries: int
    force: bool
    check: bool
    verbose: bool
    quiet: bool


def load_config(args) -> AppConfig:
    """Build the final AppConfig by merging CLI args > config file > defaults.

    Args:
        args: The parsed argparse.Namespace object.

    Returns:
        A fully resolved AppConfig.

    Raises:
        SystemExit: If required values (like API key) are missing.
    """
    # Load .env file if it exists
    load_dotenv()

    # Load config file if specified or if default exists
    file_cfg = _load_config_file(args.config)

    # Merge: CLI args > config file > defaults
    provider = _resolve("provider", args, file_cfg, "llm")
    model = _resolve("model", args, file_cfg, "llm")
    api_key_env = file_cfg.get("llm", {}).get("api_key_env", DEFAULTS["api_key_env"])
    concurrency = _resolve("concurrency", args, file_cfg, "processing")
    max_retries = int(
        file_cfg.get("processing", {}).get("max_retries", DEFAULTS["max_retries"])
    )
    api_max_retries = int(
        file_cfg.get("processing", {}).get("api_max_retries", DEFAULTS["api_max_retries"])
    )
    output = args.output if args.output else file_cfg.get("output", {}).get(
        "directory", DEFAULTS["output"]
    )

    # Resolve API key from environment
    api_key = os.environ.get(api_key_env, "")

    # Check mode doesn't require an API key
    if not args.check and not api_key:
        logger.error(
            "API key not found. Set the %s environment variable or add it to a .env file.",
            api_key_env,
        )
        raise SystemExit(1)

    # Resolve prompt file path
    prompt_file = None
    if args.prompt:
        prompt_file = Path(args.prompt)
        if not prompt_file.exists():
            logger.error("Prompt file not found: %s", prompt_file)
            raise SystemExit(1)

    input_path = Path(args.input)
    if not input_path.exists():
        logger.error("Input path does not exist: %s", input_path)
        raise SystemExit(1)

    return AppConfig(
        input_path=input_path,
        output_dir=Path(output),
        prompt_file=prompt_file,
        provider=provider,
        model=model,
        api_key=api_key,
        concurrency=int(concurrency),
        max_retries=max_retries,
        api_max_retries=api_max_retries,
        force=args.force,
        check=args.check,
        verbose=args.verbose,
        quiet=args.quiet,
    )


def _load_config_file(config_path: str | None) -> dict:
    """Load a YAML config file.

    Args:
        config_path: Explicit path from --config, or None to try the default.

    Returns:
        Parsed config dict, or empty dict if not found.
    """
    if config_path:
        path = Path(config_path)
        if not path.exists():
            logger.error("Config file not found: %s", path)
            raise SystemExit(1)
    else:
        path = Path("sigma-llm-doc.yaml")
        if not path.exists():
            logger.debug("No default config file found — using built-in defaults")
            return {}

    try:
        yaml = YAML()
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.load(f)
        if data is None:
            return {}
        logger.debug("Loaded config from %s", path)
        return dict(data)
    except Exception as e:
        logger.error("Failed to parse config file %s: %s", path, e)
        raise SystemExit(1)


def _resolve(key: str, args, file_cfg: dict, section: str | None = None):
    """Resolve a config value with priority: CLI > config file > default.

    Args:
        key: The config key name.
        args: Parsed CLI args namespace.
        file_cfg: Loaded config file dict.
        section: Section in the config file (e.g., 'llm', 'processing').

    Returns:
        The resolved value.
    """
    # CLI arg takes precedence (check if it was explicitly set)
    cli_val = getattr(args, key, None)
    if cli_val is not None:
        return cli_val

    # Config file
    if section and section in file_cfg:
        file_val = file_cfg[section].get(key)
        if file_val is not None:
            return file_val

    return DEFAULTS.get(key)
