from __future__ import annotations

import re
from pathlib import Path


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


def inject_mocks(test_file_path: str, mock_code: str) -> bool:
    """
    Inject mock_code at the end of the mock section in test_file_path.

    The mock section is identified by @defgroup ... Mocks and ends before
    the /** block that opens the next @defgroup.
    Returns True on success.
    """
    path = Path(test_file_path)
    content = path.read_text(encoding="utf-8")
    lines = content.split("\n")

    inject_at = _find_injection_point(lines)
    if inject_at is None:
        print(f"  [ERROR] No mock section (@defgroup ... Mocks) found in: {test_file_path}")
        return False

    new_lines = mock_code.splitlines() + [""]
    lines[inject_at:inject_at] = new_lines

    path.write_text("\n".join(lines), encoding="utf-8")
    return True


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _find_injection_point(lines: list[str]) -> int | None:
    """Return the line index before which mocks should be inserted."""
    mock_section_line = -1
    for i, line in enumerate(lines):
        if "@defgroup" in line and "Mocks" in line:
            mock_section_line = i
            break

    if mock_section_line == -1:
        return None

    # Find the next @defgroup after the mock section
    next_defgroup_line = -1
    for i in range(mock_section_line + 1, len(lines)):
        if "@defgroup" in lines[i]:
            next_defgroup_line = i
            break

    if next_defgroup_line == -1:
        # No closing section found — append before end of file
        return len(lines)

    # Walk backwards from next_defgroup_line to find the opening /**
    for i in range(next_defgroup_line - 1, mock_section_line, -1):
        if lines[i].strip().startswith("/**"):
            return i

    return next_defgroup_line


def get_existing_mock_symbols(test_file_path: str) -> set[str]:
    """Return symbol names already present in the mock section of a test file."""
    path = Path(test_file_path)
    lines = path.read_text(encoding="utf-8").split("\n")

    mock_start = next(
        (i for i, l in enumerate(lines) if "@defgroup" in l and "Mocks" in l), -1
    )
    if mock_start == -1:
        return set()

    inject_at = _find_injection_point(lines) or len(lines)
    mock_section = "\n".join(lines[mock_start:inject_at])

    return set(re.findall(r"\b(\w+)\s*(?:\(|=)", mock_section))


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root)
        return True
    except ValueError:
        return False
