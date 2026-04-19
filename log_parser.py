from __future__ import annotations

import re
from pathlib import Path


DEFAULT_PATTERN = r"undefined reference to `([^']+)'"


def parse_undefined_symbols(log_path: str, pattern: str = DEFAULT_PATTERN) -> list[str]:
    """
    Parse a CMake/make build log and extract all undefined reference symbol names.

    The pattern must contain exactly one capture group for the symbol name.
    Returns a sorted, deduplicated list of symbol names.
    """
    compiled = re.compile(pattern)
    symbols = set()

    with open(log_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            match = compiled.search(line)
            if match:
                symbols.add(match.group(1))

    return sorted(symbols)


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python log_parser.py <build_log>")
        sys.exit(1)

    symbols = parse_undefined_symbols(sys.argv[1])
    print(f"Found {len(symbols)} undefined symbol(s):\n")
    for s in symbols:
        print(f"  {s}")
