"""Tests for the CLI module."""

import sys
from unittest.mock import patch

import pytest

from sigma_llm_doc.cli import parse_args


def test_parse_args_minimal():
    with patch("sys.argv", ["sigma-llm-doc", "rules/"]):
        args = parse_args()
        assert args.input == "rules/"
        assert args.provider is None
        assert args.model is None
        assert args.force is False
        assert args.check is False


def test_parse_args_all_options():
    with patch("sys.argv", [
        "sigma-llm-doc", "rules/",
        "--provider", "claude",
        "--model", "claude-opus-4-6-20250929",
        "--output", "./enriched",
        "--concurrency", "10",
        "--force",
        "--verbose",
    ]):
        args = parse_args()
        assert args.input == "rules/"
        assert args.provider == "claude"
        assert args.model == "claude-opus-4-6-20250929"
        assert args.output == "./enriched"
        assert args.concurrency == 10
        assert args.force is True
        assert args.verbose is True


def test_parse_args_gemini_provider():
    with patch("sys.argv", ["sigma-llm-doc", "rules/", "--provider", "gemini"]):
        args = parse_args()
        assert args.provider == "gemini"


def test_parse_args_check_mode():
    with patch("sys.argv", ["sigma-llm-doc", "rules/", "--check"]):
        args = parse_args()
        assert args.check is True


def test_parse_args_verbose_quiet_exclusive():
    """--verbose and --quiet should be mutually exclusive."""
    with patch("sys.argv", ["sigma-llm-doc", "rules/", "--verbose", "--quiet"]):
        with pytest.raises(SystemExit):
            parse_args()


def test_parse_args_invalid_provider():
    """Invalid provider should fail argparse validation."""
    with patch("sys.argv", ["sigma-llm-doc", "rules/", "--provider", "invalid"]):
        with pytest.raises(SystemExit):
            parse_args()


def test_parse_args_vertexai():
    with patch("sys.argv", [
        "sigma-llm-doc", "rules/",
        "--provider", "gemini",
        "--vertexai",
        "--gcp-project", "my-project",
        "--gcp-location", "us-central1",
    ]):
        args = parse_args()
        assert args.vertexai is True
        assert args.gcp_project == "my-project"
        assert args.gcp_location == "us-central1"


def test_parse_args_proxy():
    with patch("sys.argv", [
        "sigma-llm-doc", "rules/",
        "--proxy", "http://proxy.corp.example.com:8080",
    ]):
        args = parse_args()
        assert args.proxy == "http://proxy.corp.example.com:8080"


def test_parse_args_base_url():
    with patch("sys.argv", [
        "sigma-llm-doc", "rules/",
        "--base-url", "https://custom.openai.example.com/v1",
    ]):
        args = parse_args()
        assert args.base_url == "https://custom.openai.example.com/v1"
