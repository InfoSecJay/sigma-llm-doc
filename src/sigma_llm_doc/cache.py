"""Content + prompt hashing and JSON cache for change detection."""

import copy
import hashlib
import json
import logging
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

from ruamel.yaml import YAML

logger = logging.getLogger(__name__)

CACHE_FILENAME = ".sigma-llm-doc-cache.json"
CACHE_VERSION = 1

# Shared YAML instance for canonical serialization
_yaml = YAML()
_yaml.preserve_quotes = True


def compute_rule_hash(rule_data) -> str:
    """Compute a SHA-256 hash of rule content, excluding the note field.

    Args:
        rule_data: Parsed YAML rule data (ruamel.yaml CommentedMap).

    Returns:
        Hex digest of the SHA-256 hash.
    """
    data_copy = copy.deepcopy(rule_data)
    if "note" in data_copy:
        del data_copy["note"]
    stream = StringIO()
    _yaml.dump(data_copy, stream)
    return hashlib.sha256(stream.getvalue().encode()).hexdigest()


def compute_prompt_hash(prompt_text: str) -> str:
    """Compute a SHA-256 hash of the prompt file contents.

    Args:
        prompt_text: The full text of the prompt file.

    Returns:
        Hex digest of the SHA-256 hash.
    """
    return hashlib.sha256(prompt_text.encode()).hexdigest()


class Cache:
    """Manages the rule processing cache stored as JSON in the output directory."""

    def __init__(self, output_dir: Path):
        self.cache_path = output_dir / CACHE_FILENAME
        self.data: dict = {
            "version": CACHE_VERSION,
            "prompt_hash": "",
            "rules": {},
        }
        self._load()

    def _load(self) -> None:
        """Load the cache from disk, or start fresh if missing/corrupt."""
        if not self.cache_path.exists():
            logger.debug("No cache file found at %s — starting fresh", self.cache_path)
            return

        try:
            with open(self.cache_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)

            if not isinstance(loaded, dict) or loaded.get("version") != CACHE_VERSION:
                logger.warning(
                    "Cache file version mismatch or invalid format — treating as empty"
                )
                return

            self.data = loaded
            logger.debug(
                "Loaded cache with %d rule entries", len(self.data.get("rules", {}))
            )

        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Cache file corrupted or unreadable (%s) — treating as empty", e)

    def save(self) -> None:
        """Write the cache to disk."""
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
            logger.debug("Cache saved to %s", self.cache_path)
        except OSError as e:
            logger.error("Failed to save cache: %s", e)

    def should_skip(
        self,
        relative_path: str,
        content_hash: str,
        prompt_hash: str,
        output_file: Path,
    ) -> bool:
        """Determine if a rule can be skipped (unchanged since last processing).

        A rule is skipped if and only if:
            1. The prompt hash in the cache matches the current prompt hash.
            2. The rule's content hash in the cache matches the current content hash.
            3. The corresponding output file exists and has a non-empty note field.

        Args:
            relative_path: Path of the rule relative to the input directory.
            content_hash: Current SHA-256 hash of the rule content (minus note).
            prompt_hash: Current SHA-256 hash of the prompt file.
            output_file: Path to the expected output file.

        Returns:
            True if the rule should be skipped.
        """
        # Check prompt hash
        if self.data.get("prompt_hash") != prompt_hash:
            return False

        # Check rule entry exists and content hash matches
        rules = self.data.get("rules", {})
        entry = rules.get(relative_path)
        if not entry or entry.get("content_hash") != content_hash:
            return False

        # Check output file exists with non-empty note
        if not output_file.exists():
            return False

        try:
            yaml = YAML()
            yaml.preserve_quotes = True
            with open(output_file, "r", encoding="utf-8") as f:
                out_data = yaml.load(f)
            note = out_data.get("note", "") if out_data else ""
            if not note or not str(note).strip():
                return False
        except Exception:
            return False

        return True

    def update_rule(self, relative_path: str, content_hash: str) -> None:
        """Record that a rule was successfully processed.

        Args:
            relative_path: Path of the rule relative to the input directory.
            content_hash: SHA-256 hash of the rule content (minus note).
        """
        if "rules" not in self.data:
            self.data["rules"] = {}

        self.data["rules"][relative_path] = {
            "content_hash": content_hash,
            "last_processed": datetime.now(timezone.utc).isoformat(),
        }

    def set_prompt_hash(self, prompt_hash: str) -> None:
        """Update the stored prompt hash."""
        self.data["prompt_hash"] = prompt_hash
