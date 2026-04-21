from __future__ import annotations

import re
import sys
from pathlib import Path


DEFAULT_PATTERN = r"undefined reference to `([^']+)'"


def _compile_pattern(pattern: str) -> re.Pattern:
    try:
        compiled = re.compile(pattern)
    except re.error as exc:
        print(f"[ERROR] Invalid symbol_pattern in config: {exc}")
        print(f"  Pattern: {pattern}")
        sys.exit(1)
    if compiled.groups != 1:
        print(f"[ERROR] symbol_pattern must contain exactly one capture group (found {compiled.groups}).")
        print(f"  Pattern: {pattern}")
        sys.exit(1)
    return compiled


def parse_undefined_symbols(log_path: str, pattern: str = DEFAULT_PATTERN) -> list[str]:
    """
    Parse a CMake/make build log and extract all undefined reference symbol names.

    The pattern must contain exactly one capture group for the symbol name.
    Returns a sorted, deduplicated list of symbol names.
    """
    compiled = _compile_pattern(pattern)
    symbols = set()

    with open(log_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            match = compiled.search(line)
            if match:
                symbols.add(match.group(1))

    return sorted(symbols)


def parse_symbols_by_file(log_path: str, pattern: str = DEFAULT_PATTERN) -> dict[str, list[str]]:
    """
    Parse a build log and return symbols grouped by source file basename.

    Returns {basename.c: [sorted, unique symbols]}.
    """
    compiled = _compile_pattern(pattern)
    file_pattern = re.compile(r"([\w./\\-]+\.c):\d+:")
    result: dict[str, set] = {}

    with open(log_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            sym_match = compiled.search(line)
            if not sym_match:
                continue
            file_match = file_pattern.search(line)
            if not file_match:
                continue
            basename = Path(file_match.group(1)).name
            result.setdefault(basename, set()).add(sym_match.group(1))

    return {f: sorted(syms) for f, syms in sorted(result.items())}


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python log_parser.py <build_log>")
        sys.exit(1)

    symbols = parse_undefined_symbols(sys.argv[1])
    print(f"Found {len(symbols)} undefined symbol(s):\n")
    for s in symbols:
        print(f"  {s}")
