from __future__ import annotations

import re
from pathlib import Path

MOCK_SECTION_START = r"@defgroup.*Mocks"
MOCK_SECTION_END = r"^\s*/\*\*"


def find_test_file(source_basename: str, tests_root: str, prefixes: list[str]) -> str | None:
    """
    Locate a test file in tests_root matching source_basename.

    Accepts files that already start with a valid prefix, or tries prepending each prefix.
    Only returns files that are inside tests_root (safety check).
    """
    tests_path = Path(tests_root).resolve()

    if not any(source_basename.startswith(p) for p in prefixes):
        return None

    for match in tests_path.rglob(source_basename):
        if _is_under(match, tests_path):
            return str(match)

    return None


def inject_mocks(
    test_file_path: str,
    mock_code: str,
    start_pattern: str = MOCK_SECTION_START,
    end_pattern: str = MOCK_SECTION_END,
) -> bool:
    """
    Inject mock_code at the end of the mock section in test_file_path.

    The mock section is identified by start_pattern and ends at the first line
    matching end_pattern after the start. Returns True on success.
    """
    path = Path(test_file_path)
    content = path.read_text(encoding="utf-8")
    lines = content.split("\n")

    start_re = re.compile(start_pattern)
    end_re = re.compile(end_pattern)

    inject_at = _find_injection_point(lines, start_re, end_re)
    if inject_at is None:
        print(f"  [ERROR] No mock section found in: {test_file_path}")
        print(f"          (start pattern: {start_pattern!r})")
        return False

    new_lines = mock_code.splitlines() + [""]
    lines[inject_at:inject_at] = new_lines

    path.write_text("\n".join(lines), encoding="utf-8")
    return True


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _find_injection_point(
    lines: list[str], start_re: re.Pattern, end_re: re.Pattern
) -> int | None:
    """Return the line index before which mocks should be inserted."""
    mock_start = -1
    for i, line in enumerate(lines):
        if start_re.search(line):
            mock_start = i
            break

    if mock_start == -1:
        return None

    for i in range(mock_start + 1, len(lines)):
        if end_re.search(lines[i]):
            return i

    # No end marker found — append before end of file
    return len(lines)


def get_existing_mock_symbols(
    test_file_path: str,
    start_pattern: str = MOCK_SECTION_START,
    end_pattern: str = MOCK_SECTION_END,
) -> set[str]:
    """Return symbol names already present in the mock section of a test file."""
    path = Path(test_file_path)
    lines = path.read_text(encoding="utf-8").split("\n")

    start_re = re.compile(start_pattern)
    end_re = re.compile(end_pattern)

    mock_start = next((i for i, l in enumerate(lines) if start_re.search(l)), -1)
    if mock_start == -1:
        return set()

    inject_at = _find_injection_point(lines, start_re, end_re) or len(lines)
    mock_section = "\n".join(lines[mock_start:inject_at])

    return set(re.findall(r"\b(\w+)\s*(?:\(|=)", mock_section))


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root)
        return True
    except ValueError:
        return False
