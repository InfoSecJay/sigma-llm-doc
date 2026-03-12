"""Tests for the config module."""

import os
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

import pytest

from sigma_llm_doc.config import (
    load_config,
    _validate_config,
    PROVIDER_API_KEY_ENV,
    PROVIDER_DEFAULT_MODEL,
    AppConfig,
)


def _make_args(**overrides):
    """Create a minimal argparse Namespace with defaults."""
    defaults = dict(
        input=".",
        config=None,
        prompt=None,
        output=None,
        provider=None,
        model=None,
        concurrency=None,
        force=False,
        check=True,  # check mode doesn't require API key
        verbose=False,
        quiet=False,
        base_url=None,
        proxy=None,
        vertexai=False,
        gcp_project=None,
        gcp_location=None,
    )
    defaults.update(overrides)
    return Namespace(**defaults)


def test_provider_defaults_include_gemini():
    assert "gemini" in PROVIDER_API_KEY_ENV
    assert PROVIDER_API_KEY_ENV["gemini"] == "GEMINI_API_KEY"
    assert "gemini" in PROVIDER_DEFAULT_MODEL
    assert PROVIDER_DEFAULT_MODEL["gemini"] == "gemini-2.5-flash"


def test_default_provider_is_openai(tmp_path):
    """Without specifying a provider, the default should be openai."""
    input_file = tmp_path / "test.yml"
    input_file.write_text("title: test\n")

    args = _make_args(input=str(input_file))
    cfg = load_config(args)
    assert cfg.provider == "openai"
    assert cfg.model == "gpt-4o-mini"


def test_provider_claude_resolves_defaults(tmp_path):
    input_file = tmp_path / "test.yml"
    input_file.write_text("title: test\n")

    args = _make_args(input=str(input_file), provider="claude")
    cfg = load_config(args)
    assert cfg.provider == "claude"
    assert cfg.model == "claude-sonnet-4-5-20250929"


def test_provider_gemini_resolves_defaults(tmp_path):
    input_file = tmp_path / "test.yml"
    input_file.write_text("title: test\n")

    args = _make_args(input=str(input_file), provider="gemini")
    cfg = load_config(args)
    assert cfg.provider == "gemini"
    assert cfg.model == "gemini-2.5-flash"


def test_cli_model_overrides_provider_default(tmp_path):
    input_file = tmp_path / "test.yml"
    input_file.write_text("title: test\n")

    args = _make_args(input=str(input_file), provider="claude", model="claude-opus-4-6-20250929")
    cfg = load_config(args)
    assert cfg.model == "claude-opus-4-6-20250929"


def test_validate_config_rejects_zero_concurrency():
    cfg = AppConfig(
        input_path=Path("."),
        output_dir=Path("./output"),
        prompt_file=None,
        provider="openai",
        model="gpt-4o-mini",
        api_key="test",
        concurrency=0,
        max_retries=3,
        api_max_retries=3,
        force=False,
        check=False,
        verbose=False,
        quiet=False,
    )
    with pytest.raises(SystemExit):
        _validate_config(cfg)


def test_validate_config_rejects_negative_retries():
    cfg = AppConfig(
        input_path=Path("."),
        output_dir=Path("./output"),
        prompt_file=None,
        provider="openai",
        model="gpt-4o-mini",
        api_key="test",
        concurrency=5,
        max_retries=0,
        api_max_retries=3,
        force=False,
        check=False,
        verbose=False,
        quiet=False,
    )
    with pytest.raises(SystemExit):
        _validate_config(cfg)


def test_validate_config_rejects_empty_model():
    cfg = AppConfig(
        input_path=Path("."),
        output_dir=Path("./output"),
        prompt_file=None,
        provider="openai",
        model="",
        api_key="test",
        concurrency=5,
        max_retries=3,
        api_max_retries=3,
        force=False,
        check=False,
        verbose=False,
        quiet=False,
    )
    with pytest.raises(SystemExit):
        _validate_config(cfg)


def test_validate_config_rejects_unknown_provider():
    cfg = AppConfig(
        input_path=Path("."),
        output_dir=Path("./output"),
        prompt_file=None,
        provider="ollama",
        model="llama3",
        api_key="test",
        concurrency=5,
        max_retries=3,
        api_max_retries=3,
        force=False,
        check=False,
        verbose=False,
        quiet=False,
    )
    with pytest.raises(SystemExit):
        _validate_config(cfg)


def test_missing_api_key_raises(tmp_path):
    """Non-check mode with no API key should fail."""
    input_file = tmp_path / "test.yml"
    input_file.write_text("title: test\n")

    # Ensure env var is empty
    with patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=False):
        args = _make_args(input=str(input_file), check=False)
        with pytest.raises(SystemExit):
            load_config(args)


def test_check_mode_no_api_key_ok(tmp_path):
    """Check mode should not require an API key."""
    input_file = tmp_path / "test.yml"
    input_file.write_text("title: test\n")

    with patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=False):
        args = _make_args(input=str(input_file), check=True)
        cfg = load_config(args)
        assert cfg.check is True


def test_vertexai_no_api_key_ok(tmp_path):
    """Vertex AI mode should not require an API key."""
    input_file = tmp_path / "test.yml"
    input_file.write_text("title: test\n")

    with patch.dict(os.environ, {"GEMINI_API_KEY": ""}, clear=False):
        args = _make_args(
            input=str(input_file),
            check=False,
            provider="gemini",
            vertexai=True,
            gcp_project="my-project",
            gcp_location="us-central1",
        )
        cfg = load_config(args)
        assert cfg.vertexai is True
        assert cfg.gcp_project == "my-project"
        assert cfg.gcp_location == "us-central1"
        assert cfg.api_key == ""  # empty is OK for vertex


def test_proxy_from_cli(tmp_path):
    """Proxy should be resolved from CLI args."""
    input_file = tmp_path / "test.yml"
    input_file.write_text("title: test\n")

    args = _make_args(
        input=str(input_file),
        proxy="http://proxy.corp.example.com:8080",
    )
    cfg = load_config(args)
    assert cfg.proxy == "http://proxy.corp.example.com:8080"


def test_base_url_from_cli(tmp_path):
    """Base URL should be resolved from CLI args."""
    input_file = tmp_path / "test.yml"
    input_file.write_text("title: test\n")

    args = _make_args(
        input=str(input_file),
        base_url="https://custom.openai.example.com/v1",
    )
    cfg = load_config(args)
    assert cfg.base_url == "https://custom.openai.example.com/v1"


def test_gcp_project_from_env(tmp_path):
    """GCP project should fall back to GOOGLE_CLOUD_PROJECT env var."""
    input_file = tmp_path / "test.yml"
    input_file.write_text("title: test\n")

    with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "env-project", "GOOGLE_CLOUD_LOCATION": "europe-west1"}, clear=False):
        args = _make_args(input=str(input_file), provider="gemini", vertexai=True)
        cfg = load_config(args)
        assert cfg.gcp_project == "env-project"
        assert cfg.gcp_location == "europe-west1"
