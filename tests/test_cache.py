"""Tests for the cache module."""

import json
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from sigma_llm_doc.cache import compute_rule_hash, compute_prompt_hash, Cache


@pytest.fixture
def tmp_output(tmp_path):
    """Provide a temporary output directory."""
    return tmp_path


@pytest.fixture
def sample_rule():
    """Return a sample parsed YAML rule (as a dict-like object from ruamel)."""
    yaml = YAML()
    yaml.preserve_quotes = True
    from io import StringIO
    return yaml.load(StringIO(
        "title: Test Rule\n"
        "status: test\n"
        "logsource:\n"
        "  category: process_creation\n"
        "  product: windows\n"
        "detection:\n"
        "  selection:\n"
        "    CommandLine|contains: mimikatz\n"
        "  condition: selection\n"
        "level: high\n"
    ))


def test_rule_hash_deterministic(sample_rule):
    h1 = compute_rule_hash(sample_rule)
    h2 = compute_rule_hash(sample_rule)
    assert h1 == h2


def test_rule_hash_excludes_note(sample_rule):
    h_without_note = compute_rule_hash(sample_rule)
    sample_rule["note"] = "This is an investigation guide."
    h_with_note = compute_rule_hash(sample_rule)
    assert h_without_note == h_with_note


def test_rule_hash_changes_on_modification(sample_rule):
    h_original = compute_rule_hash(sample_rule)
    sample_rule["level"] = "critical"
    h_modified = compute_rule_hash(sample_rule)
    assert h_original != h_modified


def test_prompt_hash_deterministic():
    prompt = "You are a detection engineer."
    assert compute_prompt_hash(prompt) == compute_prompt_hash(prompt)


def test_prompt_hash_changes():
    h1 = compute_prompt_hash("prompt version 1")
    h2 = compute_prompt_hash("prompt version 2")
    assert h1 != h2


def test_cache_fresh_start(tmp_output):
    cache = Cache(tmp_output)
    assert cache.data["version"] == 1
    assert cache.data["rules"] == {}


def test_cache_save_and_load(tmp_output):
    cache = Cache(tmp_output)
    cache.set_prompt_hash("abc123")
    cache.update_rule("rules/test.yml", "hash_value")
    cache.save()

    # Load again
    cache2 = Cache(tmp_output)
    assert cache2.data["prompt_hash"] == "abc123"
    assert "rules/test.yml" in cache2.data["rules"]
    assert cache2.data["rules"]["rules/test.yml"]["content_hash"] == "hash_value"


def test_cache_corrupted_file(tmp_output):
    cache_path = tmp_output / ".sigma-llm-doc-cache.json"
    cache_path.write_text("NOT VALID JSON {{{", encoding="utf-8")
    cache = Cache(tmp_output)
    # Should silently recover with empty cache
    assert cache.data["rules"] == {}


def test_should_skip_all_conditions_met(tmp_output, sample_rule):
    yaml = YAML()
    yaml.preserve_quotes = True

    # Write an output file with a note
    sample_rule["note"] = "Investigation guide content here."
    out_file = tmp_output / "test.yml"
    with open(out_file, "w", encoding="utf-8") as f:
        yaml.dump(sample_rule, f)

    # Set up cache
    del sample_rule["note"]
    content_hash = compute_rule_hash(sample_rule)
    prompt_hash = "prompt_hash_123"

    cache = Cache(tmp_output)
    cache.set_prompt_hash(prompt_hash)
    cache.update_rule("test.yml", content_hash)
    cache.save()

    # Reload and check skip
    cache2 = Cache(tmp_output)
    assert cache2.should_skip("test.yml", content_hash, prompt_hash, out_file)


def test_should_not_skip_if_prompt_changed(tmp_output, sample_rule):
    yaml = YAML()
    yaml.preserve_quotes = True

    sample_rule["note"] = "Guide."
    out_file = tmp_output / "test.yml"
    with open(out_file, "w", encoding="utf-8") as f:
        yaml.dump(sample_rule, f)

    del sample_rule["note"]
    content_hash = compute_rule_hash(sample_rule)

    cache = Cache(tmp_output)
    cache.set_prompt_hash("old_prompt_hash")
    cache.update_rule("test.yml", content_hash)
    cache.save()

    cache2 = Cache(tmp_output)
    assert not cache2.should_skip("test.yml", content_hash, "new_prompt_hash", out_file)
