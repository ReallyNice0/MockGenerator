from __future__ import annotations

import re
from pathlib import Path


def get_include_dirs(
    cmake_lists_path: str,
    cmake_root: str,
    exclude_dirs: list[str] = None,
    cmake_vars: dict[str, str] = None,
) -> list[str]:
    """
    Parse a CMakeLists.txt and return resolved, filtered include directory paths.

    Resolves ${CMAKE_SOURCE_DIR} to cmake_root and any extra ${VAR} from cmake_vars.
    Skips directories matching any prefix in exclude_dirs.
    Warns about configured paths that don't exist on disk.
    """
    cmake_root_path = Path(cmake_root).resolve()
    exclude_dirs = exclude_dirs or []
    cmake_vars = cmake_vars or {}

    substitutions = {"CMAKE_SOURCE_DIR": str(cmake_root_path)}
    substitutions.update(cmake_vars)

    raw_paths = _extract_include_dirs(cmake_lists_path)
    resolved = []

    for raw in raw_paths:
        substituted = _apply_cmake_vars(raw, substitutions)
        if "${" in substituted:
            print(f"  [WARNING] Unresolved CMake variable in path, skipping: {substituted}")
            continue
        resolved_path = Path(substituted).resolve()

        if _is_excluded(resolved_path, cmake_root_path, exclude_dirs):
            continue

        if not resolved_path.exists():
            print(f"  [WARNING] Include path does not exist: {resolved_path}")
            continue

        resolved.append(str(resolved_path))

    return resolved


def _extract_include_dirs(cmake_lists_path: str) -> list[str]:
    """Extract raw path strings from all include_directories(...) calls."""
    text = Path(cmake_lists_path).read_text(encoding="utf-8")

    # Match include_directories( ... ) — handles multiline, ignores comments
    block_pattern = re.compile(r"include_directories\s*\((.*?)\)", re.DOTALL)
    path_pattern = re.compile(r"[^\s)]+")

    raw_paths = []
    for block in block_pattern.finditer(text):
        content = _strip_cmake_comments(block.group(1))
        for match in path_pattern.finditer(content):
            raw_paths.append(match.group(0))

    return raw_paths


def _apply_cmake_vars(path: str, variables: dict[str, str]) -> str:
    """Replace all ${VAR} occurrences using the provided variables dict."""
    for name, value in variables.items():
        path = path.replace(f"${{{name}}}", value)
    return path


def _strip_cmake_comments(text: str) -> str:
    """Remove CMake line comments (# ...)."""
    return re.sub(r"#[^\n]*", "", text)


def _is_excluded(path: Path, cmake_root: Path, exclude_dirs: list[str]) -> bool:
    """Return True if path falls under any of the exclude_dirs (relative to cmake_root)."""
    for exclude in exclude_dirs:
        excluded_abs = (cmake_root / exclude).resolve()
        try:
            path.relative_to(excluded_abs)
            return True
        except ValueError:
            pass
    return False


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python cmake_analyzer.py <cmake_lists_path> <cmake_root> [exclude_dir ...]")
        sys.exit(1)

    cmake_lists = sys.argv[1]
    root = sys.argv[2]
    excludes = sys.argv[3:]

    dirs = get_include_dirs(cmake_lists, root, excludes)
    print(f"Found {len(dirs)} include dir(s):\n")
    for d in dirs:
        print(f"  {d}")
