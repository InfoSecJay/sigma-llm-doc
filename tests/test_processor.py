"""Tests for the processor module."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from ruamel.yaml import YAML

from sigma_llm_doc.processor import (
    _clean_markdown,
    _collect_yaml_files,
    process_rules,
    check_rules,
)
from sigma_llm_doc.llm_provider import GenerateResult


class TestCleanMarkdown:
    def test_strips_dividers(self):
        text = "### Header\nContent\n---\n### Next\nMore content"
        result = _clean_markdown(text)
        assert "---" not in result
        assert "### Header" in result
        assert "### Next" in result

    def test_collapses_blank_lines(self):
        text = "Line 1\n\n\n\nLine 2"
        result = _clean_markdown(text)
        assert result == "Line 1\n\nLine 2\n"

    def test_trailing_newline(self):
        text = "Content"
        result = _clean_markdown(text)
        assert result.endswith("\n")

    def test_strips_trailing_whitespace(self):
        text = "Line with spaces   \nAnother line  "
        result = _clean_markdown(text)
        for line in result.splitlines():
            assert line == line.rstrip()

    def test_multiple_dividers_removed(self):
        text = "---\n### A\nContent\n---\n### B\nContent\n---"
        result = _clean_markdown(text)
        assert "---" not in result

    def test_converts_star_bullets_to_dash(self):
        text = "### Header\n* First item\n* Second item\n  * Nested item"
        result = _clean_markdown(text)
        assert "* " not in result
        assert "- First item" in result
        assert "- Second item" in result
        assert "  - Nested item" in result

    def test_preserves_bold_stars(self):
        text = "- **Bold text** in a bullet"
        result = _clean_markdown(text)
        assert "**Bold text**" in result
        assert result.startswith("- ")


class TestCollectYamlFiles:
    def test_single_yml_file(self, tmp_path):
        f = tmp_path / "rule.yml"
        f.write_text("title: test\n")
        files = _collect_yaml_files(f)
        assert len(files) == 1
        assert files[0] == f

    def test_single_yaml_file(self, tmp_path):
        f = tmp_path / "rule.yaml"
        f.write_text("title: test\n")
        files = _collect_yaml_files(f)
        assert len(files) == 1

    def test_non_yaml_file_ignored(self, tmp_path):
        f = tmp_path / "readme.md"
        f.write_text("# readme\n")
        files = _collect_yaml_files(f)
        assert len(files) == 0

    def test_directory_recursive(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (tmp_path / "a.yml").write_text("title: a\n")
        (sub / "b.yaml").write_text("title: b\n")
        (tmp_path / "readme.md").write_text("# readme\n")
        files = _collect_yaml_files(tmp_path)
        assert len(files) == 2

    def test_empty_directory(self, tmp_path):
        files = _collect_yaml_files(tmp_path)
        assert len(files) == 0


SAMPLE_VALID_RESPONSE = """### Technical Context
This rule detects test activity. Maps to MITRE ATT&CK T1059.

### Investigation Steps
- **Check process tree**: Review the parent process and command line arguments.
- **Correlate with network logs**: Look for outbound connections from the host.
- **Review user context**: Determine if the user account is expected to run this.
- **Check for persistence**: Look for scheduled tasks or registry modifications.

### Prioritization
High severity due to potential command execution by an attacker.

### Blind Spots and Assumptions
Assumes Sysmon logging is enabled. Will not detect fileless execution techniques.

> **Disclaimer:** This investigation guide was created using generative AI technology and has not been reviewed for its accuracy and relevance. While every effort has been made to ensure its quality, we recommend validating the content and adapting it to suit specific environments and operational needs. Please communicate any changes to the detection engineering team."""


@pytest.mark.asyncio
async def test_process_rules_generates_output(tmp_path):
    """Integration test: process a single rule with a mock provider."""
    # Create input rule
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    rule_file = input_dir / "test_rule.yml"
    rule_file.write_text(
        "title: Test Rule\n"
        "status: test\n"
        "logsource:\n"
        "  category: process_creation\n"
        "  product: windows\n"
        "detection:\n"
        "  selection:\n"
        "    CommandLine|contains: test\n"
        "  condition: selection\n"
        "level: high\n"
    )

    output_dir = tmp_path / "output"

    # Mock provider
    mock_provider = MagicMock()
    mock_provider.generate = AsyncMock(
        return_value=GenerateResult(
            text=SAMPLE_VALID_RESPONSE,
            input_tokens=100,
            output_tokens=50,
        )
    )

    result = await process_rules(
        input_path=input_dir,
        output_dir=output_dir,
        provider=mock_provider,
        concurrency=1,
        max_retries=1,
    )

    assert result.total == 1
    assert result.processed == 1
    assert result.failed == 0
    assert result.total_input_tokens == 100
    assert result.total_output_tokens == 50

    # Verify output file was written with note field
    output_file = output_dir / "test_rule.yml"
    assert output_file.exists()

    yaml = YAML()
    yaml.preserve_quotes = True
    with open(output_file, "r", encoding="utf-8") as f:
        data = yaml.load(f)
    assert "note" in data
    assert "### Technical Context" in str(data["note"])
    assert "---" not in str(data["note"])  # Dividers should be stripped


@pytest.mark.asyncio
async def test_process_rules_skips_cached(tmp_path):
    """Second run should skip unchanged rules."""
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    rule_file = input_dir / "test_rule.yml"
    rule_file.write_text(
        "title: Test Rule\n"
        "status: test\n"
        "logsource:\n"
        "  category: process_creation\n"
        "  product: windows\n"
        "detection:\n"
        "  selection:\n"
        "    CommandLine|contains: test\n"
        "  condition: selection\n"
        "level: high\n"
    )

    output_dir = tmp_path / "output"

    mock_provider = MagicMock()
    mock_provider.generate = AsyncMock(
        return_value=GenerateResult(text=SAMPLE_VALID_RESPONSE, input_tokens=100, output_tokens=50)
    )

    # First run
    result1 = await process_rules(
        input_path=input_dir, output_dir=output_dir, provider=mock_provider,
    )
    assert result1.processed == 1

    # Second run (should skip)
    result2 = await process_rules(
        input_path=input_dir, output_dir=output_dir, provider=mock_provider,
    )
    assert result2.skipped == 1
    assert result2.processed == 0


def test_check_rules_passes_valid(tmp_path):
    """Check mode should pass rules with valid notes."""
    yaml = YAML()
    yaml.preserve_quotes = True

    rule_file = tmp_path / "test.yml"
    data = {"title": "Test", "note": SAMPLE_VALID_RESPONSE}
    with open(rule_file, "w", encoding="utf-8") as f:
        yaml.dump(data, f)

    result = check_rules(tmp_path)
    assert result.processed == 1
    assert result.failed == 0


def test_check_rules_fails_invalid(tmp_path):
    """Check mode should fail rules with invalid notes."""
    yaml = YAML()
    yaml.preserve_quotes = True

    rule_file = tmp_path / "test.yml"
    data = {"title": "Test", "note": "This is not a valid investigation guide."}
    with open(rule_file, "w", encoding="utf-8") as f:
        yaml.dump(data, f)

    result = check_rules(tmp_path)
    assert result.failed == 1


def test_check_rules_skips_no_note(tmp_path):
    """Check mode should skip rules without a note field."""
    yaml = YAML()
    yaml.preserve_quotes = True

    rule_file = tmp_path / "test.yml"
    data = {"title": "Test", "level": "high"}
    with open(rule_file, "w", encoding="utf-8") as f:
        yaml.dump(data, f)

    result = check_rules(tmp_path)
    assert result.skipped == 1
