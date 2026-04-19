from __future__ import annotations

import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ModuleNotFoundError:
        print("Error: missing TOML library. Run: pip install tomli")
        sys.exit(1)

from log_parser import parse_undefined_symbols
from cmake_analyzer import get_include_dirs
from header_scanner import scan_symbols
from mock_generator import generate_mocks


CONFIG_FILE = "mockgenerator.toml"


def main() -> None:
    if len(sys.argv) != 2:
        print(f"Usage: python main.py <build_log>")
        sys.exit(1)

    log_path = sys.argv[1]
    config = _load_config()

    cmake_root = config["project"]["cmake_root"]
    test_cmake_lists = str(Path(cmake_root) / config["project"].get("test_cmake_lists", "tests/CMakeLists.txt"))
    exclude_dirs = config.get("search", {}).get("exclude_dirs", [])
    output_dir = config.get("output", {}).get("output_dir", "mocks_out")

    print(f"[1/4] Parsing build log: {log_path}")
    symbols = parse_undefined_symbols(log_path)
    if not symbols:
        print("  No undefined symbols found. Nothing to do.")
        return
    print(f"  Found {len(symbols)} symbol(s).")

    print(f"[2/4] Analyzing CMake includes: {test_cmake_lists}")
    include_dirs = get_include_dirs(test_cmake_lists, cmake_root, exclude_dirs)
    print(f"  Found {len(include_dirs)} include dir(s).")

    print(f"[3/4] Scanning headers for prototypes...")
    result = scan_symbols(symbols, include_dirs)
    print(f"  Resolved: {len(result.functions)} function(s), {len(result.variables)} variable(s).")
    if result.not_found:
        print(f"  Unresolved ({len(result.not_found)}): {', '.join(result.not_found)}")

    print(f"[4/4] Generating mocks...")
    mock_code = generate_mocks(result)

    output_path = _write_output(mock_code, log_path, output_dir)
    print(f"\nDone. Mocks written to: {output_path}")


def _load_config() -> dict:
    config_path = Path(CONFIG_FILE)
    if not config_path.exists():
        print(f"Error: config file '{CONFIG_FILE}' not found.")
        print("Create a mockgenerator.toml next to main.py. Example:")
        print("""
  [project]
  cmake_root = "C:/Projects/MyProject/Code"
  test_cmake_lists = "tests/CMakeLists.txt"  # optional, this is the default

  [search]
  exclude_dirs = ["autosar/generated"]

  [output]
  output_dir = "mocks_out"
""")
        sys.exit(1)

    with open(config_path, "rb") as f:
        return tomllib.load(f)


def _write_output(mock_code: str, log_path: str, output_dir: str) -> Path:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    stem = Path(log_path).stem
    out_path = out_dir / f"{stem}_mocks.txt"
    out_path.write_text(mock_code, encoding="utf-8")
    return out_path


if __name__ == "__main__":
    main()
