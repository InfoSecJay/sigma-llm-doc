"""Tests for the validator module."""

import pytest

from sigma_llm_doc.validator import validate_response, REQUIRED_HEADERS


VALID_RESPONSE = """### Technical Context
This rule detects suspicious process creation events associated with credential
dumping tools such as Mimikatz. The attacker's objective is to extract plaintext
passwords, hashes, and Kerberos tickets from memory. This maps to MITRE ATT&CK
Credential Access (T1003). Primary data sources include process creation logs
and Windows Security Event logs.

### Investigation Steps
- **Review process lineage**: Examine the parent-child process chain to determine
  how the suspicious process was launched and whether it originated from a
  known-good application.
- **Check for credential access artifacts**: Look for lsass.exe memory access
  events, suspicious DLL loads, and related file system artifacts on the endpoint.
- **Correlate with authentication logs**: Search for anomalous logon events
  (Event ID 4624/4625) around the time of the alert to identify lateral movement.
- **Assess endpoint posture**: Verify EDR telemetry for additional indicators
  such as privilege escalation or persistence mechanisms.

### Prioritization
This alert should be treated as high severity because credential dumping directly
enables lateral movement and privilege escalation across the enterprise environment.

### Blind Spots and Assumptions
This detection assumes that process creation logging (Sysmon Event ID 1 or
Windows Security Event ID 4688) is enabled and forwarded to the SIEM. It will
not detect credential dumping techniques that operate entirely in memory without
spawning a new process, such as certain reflective DLL injection methods.
Additionally, the rule may miss renamed or obfuscated variants of known tools.

> **Disclaimer:** This investigation guide was created using generative AI technology and has not been reviewed for its accuracy and relevance. While every effort has been made to ensure its quality, we recommend validating the content and adapting it to suit specific environments and operational needs. Please communicate any changes to the detection engineering team.
"""


def test_valid_response_passes():
    result = validate_response(VALID_RESPONSE)
    assert result.passed, f"Expected pass but got: {result}"


def test_empty_response_fails():
    result = validate_response("")
    assert not result.passed
    assert "empty" in result.errors[0].lower()


def test_missing_header_fails():
    # Remove one header
    text = VALID_RESPONSE.replace("### Prioritization", "### Priority")
    result = validate_response(text)
    assert not result.passed
    assert any("### Prioritization" in e for e in result.errors)


def test_missing_disclaimer_still_passes():
    """Disclaimer is now appended programmatically, so validation should pass without it."""
    text = VALID_RESPONSE.replace("> **Disclaimer:**", "> Note:")
    result = validate_response(text)
    assert result.passed, f"Expected pass but got: {result}"


def test_star_bullets_fail():
    text = VALID_RESPONSE.replace("- **Review", "* **Review")
    result = validate_response(text)
    assert not result.passed
    assert any("dash-prefixed" in e for e in result.errors)


def test_code_blocks_fail():
    text = VALID_RESPONSE + "\n```yaml\nfoo: bar\n```\n"
    result = validate_response(text)
    assert not result.passed
    assert any("code block" in e for e in result.errors)


def test_too_short_fails():
    text = "### Technical Context\nShort.\n### Investigation Steps\nShort.\n### Prioritization\nShort.\n### Blind Spots and Assumptions\nShort.\n> **Disclaimer:** short"
    result = validate_response(text)
    assert not result.passed
    assert any("short" in e.lower() for e in result.errors)


def test_empty_section_fails():
    text = VALID_RESPONSE.replace(
        "### Prioritization\nThis alert should be treated",
        "### Prioritization\n### Blind Spots",  # empty Prioritization
    )
    # This corrupts the doc but the important thing is the empty section check
    result = validate_response(text)
    assert not result.passed
