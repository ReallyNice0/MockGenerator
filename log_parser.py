import re
from pathlib import Path


def parse_undefined_symbols(log_path: str) -> list[str]:
    """
    Parse a CMake/make build log and extract all undefined reference symbol names.

    Returns a sorted, deduplicated list of symbol names.
    """
    pattern = re.compile(r"undefined reference to `([^']+)'")
    symbols = set()

    with open(log_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            match = pattern.search(line)
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
