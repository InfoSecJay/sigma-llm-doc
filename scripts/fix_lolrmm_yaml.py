"""Preprocess LOLRMM Sigma rules to fix invalid YAML.

Fixes two issues in LOLRMM detection rules (both list items and inline values):
1. Unquoted wildcard values: ``- *.domain.com`` becomes ``- '*.domain.com'``
   and ``key: *.domain.com`` becomes ``key: '*.domain.com'``
2. Environment variable references: ``- %programdata%\\path`` becomes ``- '*\\path'``
   and ``key: %envvar%\\path`` becomes ``key: '*\\path'``
   (env vars never appear in event logs -- replace with wildcard)

Usage:
    python scripts/fix_lolrmm_yaml.py <directory> [--dry-run]

This modifies files in-place. Use --dry-run to preview changes.
"""

import re
import sys
from pathlib import Path

# --- List item patterns (e.g., "  - *.anydesk.com") ---

# Match YAML list items where the value starts with * (unquoted)
STAR_PATTERN = re.compile(r"^(\s*- )(\*.+)$")

# Match YAML list items where the value starts with %envvar%
ENVVAR_PATTERN = re.compile(r"^(\s*- )(%[^%]+%)(\\+|/)(.+)$")

# Match YAML list items that are entirely an env var (no trailing path)
ENVVAR_ONLY_PATTERN = re.compile(r"^(\s*- )(%[^%]+%)$")

# --- Inline value patterns (e.g., "  key|modifier: *.domain.com") ---

# Match inline mapping value starting with * (unquoted)
# e.g., "        DestinationHostname|endswith: *.247ithelp.com"
INLINE_STAR_PATTERN = re.compile(r"^(\s+\S+:\s+)(\*.+)$")

# Match inline mapping value starting with %envvar%\path
# e.g., "        TargetFilename|endswith: %localappdata%\Alpemix\Alpemix.ini"
INLINE_ENVVAR_PATTERN = re.compile(r"^(\s+\S+:\s+)(%[^%]+%)(\\+|/)(.+)$")

# Match inline mapping value that is entirely an env var
INLINE_ENVVAR_ONLY_PATTERN = re.compile(r"^(\s+\S+:\s+)(%[^%]+%)$")


def fix_line(line: str) -> tuple[str, str | None]:
    """Fix a single line if it contains an invalid YAML pattern.

    Returns:
        Tuple of (fixed_line, description_of_change or None).
    """
    # Already quoted -- skip
    stripped_value = line.strip()
    if stripped_value.startswith("- '") or stripped_value.startswith('- "'):
        return line, None

    # --- List item fixes ---

    # Fix %envvar%\path -> '*\path' (replace env var with wildcard)
    match = ENVVAR_PATTERN.match(line)
    if match:
        indent = match.group(1)
        separator = match.group(3)
        rest = match.group(4)
        fixed = f"{indent}'*{separator}{rest}'\n"
        return fixed, f"%envvar% -> wildcard"

    # Fix bare %envvar% with no path
    match = ENVVAR_ONLY_PATTERN.match(line)
    if match:
        indent = match.group(1)
        fixed = f"{indent}'*'\n"
        return fixed, f"%envvar% -> wildcard"

    # Fix *.domain or *value -> quote it
    match = STAR_PATTERN.match(line)
    if match:
        indent = match.group(1)
        value = match.group(2)
        fixed = f"{indent}'{value}'\n"
        return fixed, "quoted wildcard"

    # --- Inline value fixes (key: value on same line) ---

    # Check if the value part is already quoted
    colon_match = re.match(r"^\s+\S+:\s+(.*)", line)
    if colon_match:
        val = colon_match.group(1).strip()
        if val.startswith("'") or val.startswith('"'):
            return line, None

    # Fix inline %envvar%\path -> '*\path'
    match = INLINE_ENVVAR_PATTERN.match(line)
    if match:
        prefix = match.group(1)
        separator = match.group(3)
        rest = match.group(4)
        fixed = f"{prefix}'*{separator}{rest}'\n"
        return fixed, f"inline %envvar% -> wildcard"

    # Fix inline bare %envvar%
    match = INLINE_ENVVAR_ONLY_PATTERN.match(line)
    if match:
        prefix = match.group(1)
        fixed = f"{prefix}'*'\n"
        return fixed, f"inline %envvar% -> wildcard"

    # Fix inline *.domain -> quote it
    match = INLINE_STAR_PATTERN.match(line)
    if match:
        prefix = match.group(1)
        value = match.group(2)
        fixed = f"{prefix}'{value}'\n"
        return fixed, "inline quoted wildcard"

    return line, None


def fix_file(path: Path, dry_run: bool = False) -> int:
    """Fix all invalid YAML patterns in a file.

    Returns:
        Number of lines changed.
    """
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    changes = 0
    fixed_lines = []

    for i, line in enumerate(lines):
        fixed, description = fix_line(line)
        if description:
            changes += 1
            if dry_run:
                print(f"  {path.name}:{i + 1}: {line.rstrip()}")
                print(f"    -> {fixed.rstrip()} ({description})")
        fixed_lines.append(fixed)

    if changes > 0 and not dry_run:
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(fixed_lines)

    return changes


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <directory> [--dry-run]")
        sys.exit(1)

    target = Path(sys.argv[1])
    dry_run = "--dry-run" in sys.argv

    if not target.exists():
        print(f"Error: {target} does not exist")
        sys.exit(1)

    if dry_run:
        print("DRY RUN -- no files will be modified\n")

    yaml_files = sorted(target.rglob("*.yml"))
    total_changes = 0
    files_changed = 0

    for path in yaml_files:
        changes = fix_file(path, dry_run)
        if changes > 0:
            files_changed += 1
            total_changes += changes

    print(f"\n{'Would fix' if dry_run else 'Fixed'} {total_changes} lines across {files_changed} files")


if __name__ == "__main__":
    main()
