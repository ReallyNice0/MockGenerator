from __future__ import annotations

import argparse
import configparser
import sys
from pathlib import Path

from log_parser import parse_undefined_symbols, parse_symbols_by_file, DEFAULT_PATTERN
from cmake_analyzer import get_include_dirs
from header_scanner import scan_symbols
from mock_generator import generate_mocks
from injector import find_test_file, inject_mocks, get_existing_mock_symbols


CONFIG_FILE = "mockgenerator.ini"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate CMocka mocks from a build log.")
    parser.add_argument("log", metavar="<build_log>", help="Path to the CMake/make error log")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print detailed output")
    parser.add_argument("--inplace", action="store_true", help="Inject mocks directly into test files (overrides config)")
    args = parser.parse_args()

    log_path = args.log
    verbose = args.verbose
    config = _load_config()

    cmake_root = config.get("project", "cmake_root")
    test_cmake_lists = str(Path(cmake_root) / config.get("project", "test_cmake_lists", fallback="tests/CMakeLists.txt"))
    exclude_dirs = _parse_list(config.get("search", "exclude_dirs", fallback=""))
    cmake_vars = _read_cmake_vars(config)
    output_dir = config.get("output", "output_dir", fallback="mocks_out")
    symbol_pattern = config.get("log_parser", "symbol_pattern", fallback=DEFAULT_PATTERN)
    mode = "inplace" if args.inplace else config.get("output", "mode", fallback="file")

    if mode == "inplace":
        _run_inplace(log_path, symbol_pattern, cmake_root, exclude_dirs, cmake_vars,
                     test_cmake_lists, config, verbose)
    else:
        _run_file(log_path, symbol_pattern, cmake_root, exclude_dirs, cmake_vars,
                  test_cmake_lists, output_dir, verbose)


def _run_file(
    log_path: str, symbol_pattern: str, cmake_root: str,
    exclude_dirs: list, cmake_vars: dict, test_cmake_lists: str,
    output_dir: str, verbose: bool,
) -> None:
    print(f"[1/4] Parsing build log: {log_path}")
    symbols = parse_undefined_symbols(log_path, symbol_pattern)
    if not symbols:
        print("  No undefined symbols found. Nothing to do.")
        return
    print(f"  Found {len(symbols)} symbol(s).")
    if verbose:
        for s in symbols:
            print(f"    {s}")

    print(f"\n[2/4] Analyzing CMake includes: {test_cmake_lists}")
    include_dirs = get_include_dirs(test_cmake_lists, cmake_root, exclude_dirs, cmake_vars)
    print(f"  Found {len(include_dirs)} include dir(s).")
    if verbose:
        for d in include_dirs:
            print(f"    {d}")

    print(f"\n[3/4] Scanning headers for prototypes...")
    result = scan_symbols(symbols, include_dirs)
    _print_scan_result(result, verbose)

    print(f"\n[4/4] Generating mocks...")
    mock_code = generate_mocks(result)
    output_path = _write_output(mock_code, log_path, output_dir)
    print(f"\nDone. Mocks written to: {output_path}")


def _run_inplace(
    log_path: str,
    symbol_pattern: str,
    cmake_root: str,
    exclude_dirs: list,
    cmake_vars: dict,
    test_cmake_lists: str,
    config: configparser.ConfigParser,
    verbose: bool,
) -> None:
    tests_root = str(Path(cmake_root) / config.get("project", "tests_root", fallback="tests"))
    prefixes = _parse_list(config.get("output", "test_file_prefixes", fallback="TestUnit_\nTestIntegration_"))

    print(f"[1/4] Parsing build log (grouped by file): {log_path}")
    symbols_by_file = parse_symbols_by_file(log_path, symbol_pattern)
    if not symbols_by_file:
        print("  No undefined symbols found. Nothing to do.")
        return
    for src_file, syms in symbols_by_file.items():
        print(f"  {src_file}: {len(syms)} symbol(s)")
        if verbose:
            for s in syms:
                print(f"    {s}")

    print(f"\n[2/4] Analyzing CMake includes: {test_cmake_lists}")
    include_dirs = get_include_dirs(test_cmake_lists, cmake_root, exclude_dirs, cmake_vars)
    print(f"  Found {len(include_dirs)} include dir(s).")
    if verbose:
        for d in include_dirs:
            print(f"    {d}")

    print(f"\n[3/4] Scanning headers for prototypes...")
    all_symbols = sorted({s for syms in symbols_by_file.values() for s in syms})
    all_results = scan_symbols(all_symbols, include_dirs)
    _print_scan_result(all_results, verbose)

    print(f"\n[4/4] Injecting mocks into test files...")
    injected, nothing_new, no_test_file, failed = 0, 0, 0, 0
    for src_file, syms in symbols_by_file.items():
        test_file = find_test_file(src_file, tests_root, prefixes)
        if not test_file:
            print(f"  [WARNING] No test file found for: {src_file} (skipping)")
            no_test_file += 1
            continue

        # Build a ScanResult containing only this file's symbols
        from header_scanner import ScanResult
        file_result = ScanResult(
            functions={s: all_results.functions[s] for s in syms if s in all_results.functions},
            variables={s: all_results.variables[s] for s in syms if s in all_results.variables},
            not_found=[s for s in syms if s in all_results.not_found],
        )

        existing = get_existing_mock_symbols(test_file)
        file_result.functions = {k: v for k, v in file_result.functions.items() if k not in existing}
        file_result.variables = {k: v for k, v in file_result.variables.items() if k not in existing}
        file_result.not_found = [s for s in file_result.not_found if s not in existing]

        new_syms = set(file_result.functions) | set(file_result.variables) | set(file_result.not_found)
        skipped_syms = [s for s in syms if s in existing]
        if skipped_syms:
            print(f"  [INFO] {len(skipped_syms)} symbol(s) already mocked in {src_file}, skipping.")
            if verbose:
                for s in skipped_syms:
                    print(f"    (skip) {s}")
        if not new_syms:
            print(f"  Nothing new to inject for {src_file}.")
            nothing_new += 1
            continue

        mock_code = generate_mocks(file_result)
        print(f"  {src_file}  ->  {test_file}")
        if verbose:
            for s in new_syms:
                print(f"    (inject) {s}")
        if inject_mocks(test_file, mock_code):
            injected += 1
        else:
            failed += 1

    parts = [f"Injected into {injected} file(s)"]
    if nothing_new:
        parts.append(f"already up-to-date: {nothing_new}")
    if no_test_file:
        parts.append(f"no test file found: {no_test_file}")
    if failed:
        parts.append(f"injection failed: {failed}")
    print(f"\nDone. {', '.join(parts)}.")


def _print_scan_result(result, verbose: bool) -> None:
    print(f"  Resolved: {len(result.functions)} function(s), {len(result.variables)} variable(s).")
    if verbose:
        for decl in result.functions.values():
            print(f"    {decl.name}  ->  {decl.source_file}")
        for decl in result.variables.values():
            print(f"    {decl.name}  ->  {decl.source_file}")
    if result.not_found:
        print(f"  Unresolved ({len(result.not_found)}): {', '.join(result.not_found)}")


def _load_config() -> configparser.ConfigParser:
    config_path = Path(CONFIG_FILE)
    if not config_path.exists():
        print(f"Error: config file '{CONFIG_FILE}' not found.")
        print("Create a mockgenerator.ini next to main.py. Example:\n")
        print("""\
[project]
cmake_root = C:/Projects/MyProject/Code
test_cmake_lists = tests/CMakeLists.txt
tests_root = tests

[search]
exclude_dirs =
    autosar/generated
    vendor/lowlevel

[output]
mode = file
output_dir = mocks_out
test_file_prefixes =
    TestUnit_
    TestIntegration_
""")
        sys.exit(1)

    config = configparser.ConfigParser()
    config.read(config_path, encoding="utf-8")
    return config


def _read_cmake_vars(config: configparser.ConfigParser) -> dict:
    if not config.has_section("cmake_vars"):
        return {}
    case_config = configparser.RawConfigParser()
    case_config.optionxform = str
    case_config.read(CONFIG_FILE, encoding="utf-8")
    return dict(case_config.items("cmake_vars")) if case_config.has_section("cmake_vars") else {}


def _parse_list(value: str) -> list:
    return [line.strip() for line in value.splitlines() if line.strip()]


def _write_output(mock_code: str, log_path: str, output_dir: str) -> Path:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(log_path).stem
    out_path = out_dir / f"{stem}_mocks.txt"
    out_path.write_text(mock_code, encoding="utf-8")
    return out_path


if __name__ == "__main__":
    main()
