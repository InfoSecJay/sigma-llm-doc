"""Validate LLM-generated investigation guides against required format."""

import re
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

REQUIRED_HEADERS = [
    "### Technical Context",
    "### Investigation Steps",
    "### Prioritization",
    "### Blind Spots and Assumptions",
]

DISCLAIMER_PREFIX = "> **Disclaimer:**"

MINIMUM_LENGTH = 200


@dataclass
class ValidationResult:
    """Result of validating an LLM response."""
    passed: bool
    errors: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        if self.passed:
            return "Validation passed"
        return "Validation failed: " + "; ".join(self.errors)


def validate_response(text: str) -> ValidationResult:
    """Validate an LLM-generated investigation guide.

    Checks:
        1. All four required ### headers are present.
        2. Disclaimer blockquote is present.
        3. Bullet items use dash prefix (no * bullets).
        4. No triple-backtick code blocks.
        5. Each section has at least 1 line of content after the header.
        6. Total response is at least 200 characters.

    Args:
        text: The raw LLM response text.

    Returns:
        A ValidationResult with pass/fail and list of specific errors.
    """
    errors: list[str] = []

    if not text or not text.strip():
        return ValidationResult(passed=False, errors=["Response is empty"])

    # Check minimum length
    if len(text.strip()) < MINIMUM_LENGTH:
        errors.append(
            f"Response too short ({len(text.strip())} chars, minimum {MINIMUM_LENGTH})"
        )

    # Check required headers
    for header in REQUIRED_HEADERS:
        if header not in text:
            errors.append(f"Missing required header: {header}")

    # Check disclaimer blockquote
    if DISCLAIMER_PREFIX not in text:
        errors.append("Missing disclaimer blockquote (> **Disclaimer:**)")

    # Check for * bullets (should use - instead)
    # Match lines starting with optional whitespace, then * and a space (bullet syntax).
    # This won't match **bold** markers since those have ** with no space between.
    star_bullet_pattern = re.compile(r"^\s*\*\s", re.MULTILINE)
    if star_bullet_pattern.search(text):
        errors.append("Found * bullet(s) — must use dash-prefixed (-) bullets only")

    # Check for triple-backtick code blocks
    if "```" in text:
        errors.append("Found triple-backtick code block(s) — code blocks are not allowed")

    # Check non-empty sections (each header must have content after it)
    _check_section_content(text, errors)

    passed = len(errors) == 0
    return ValidationResult(passed=passed, errors=errors)


def _check_section_content(text: str, errors: list[str]) -> None:
    """Verify each required section header has at least one line of content."""
    lines = text.strip().splitlines()

    for header in REQUIRED_HEADERS:
        try:
            idx = next(
                i for i, line in enumerate(lines) if line.strip() == header
            )
        except StopIteration:
            # Header missing — already reported by the header check
            continue

        # Look for at least one non-empty line before the next header or end
        has_content = False
        for subsequent in lines[idx + 1:]:
            stripped = subsequent.strip()
            if stripped.startswith("### "):
                break
            if stripped and not stripped.startswith(">"):
                has_content = True
                break
            if stripped.startswith(">"):
                # Blockquote counts as content for Blind Spots section
                has_content = True
                break

        if not has_content:
            errors.append(f"Section '{header}' has no content after the header")
