from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


POINTER_MACROS = frozenset({"P2VAR", "P2CONST", "CONSTP2VAR", "CONSTP2CONST"})


@dataclass
class FunctionDecl:
    name: str
    return_type: str        # raw return type string (e.g. "FUNC(void, CODE)" or "uint8")
    params: list[str]       # raw param strings, empty list means (void)
    is_pointer_param: list[bool]
    source_file: str

    def is_void_return(self) -> bool:
        rt = self.return_type.strip()
        if rt == "void":
            return True
        # FUNC(void, MemClass) → first argument is void
        m = re.match(r"FUNC\s*\(\s*(\w+)", rt)
        if m:
            return m.group(1) == "void"
        return False


@dataclass
class VariableDecl:
    name: str
    decl_text: str          # normalized declaration without trailing semicolon
    is_array: bool
    source_file: str


@dataclass
class ScanResult:
    functions: dict[str, FunctionDecl] = field(default_factory=dict)
    variables: dict[str, VariableDecl] = field(default_factory=dict)
    not_found: list[str] = field(default_factory=list)


def scan_symbols(symbols: list[str], include_dirs: list[str]) -> ScanResult:
    result = ScanResult()
    headers = _collect_headers(include_dirs)

    for symbol in symbols:
        decl = _find_declaration(symbol, headers)
        if decl is None:
            result.not_found.append(symbol)
        elif isinstance(decl, FunctionDecl):
            result.functions[symbol] = decl
        else:
            result.variables[symbol] = decl

    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _collect_headers(include_dirs: list[str]) -> list[Path]:
    headers = []
    for d in include_dirs:
        headers.extend(Path(d).glob("*.h"))
    return headers


def _find_declaration(symbol: str, headers: list[Path]):
    pattern = re.compile(r"\b" + re.escape(symbol) + r"\b")
    for header in headers:
        try:
            text = header.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        text = _strip_comments(text)
        text = _strip_preprocessor(text)
        decl = _extract_declaration(text, symbol, pattern)
        if decl:
            return _parse_declaration(decl, symbol, str(header))
    return None


def _strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
    text = re.sub(r"//[^\n]*", "", text)
    return text


def _strip_preprocessor(text: str) -> str:
    """Replace preprocessor directives with semicolons to act as declaration boundaries."""
    return re.sub(r"^\s*#[^\n]*", ";", text, flags=re.MULTILINE)


def _extract_declaration(text: str, symbol: str, pattern: re.Pattern) -> str | None:
    for match in pattern.finditer(text):
        pos = match.start()
        if _brace_depth_at(text, pos) > 0:
            continue  # inside a function/block body — not a declaration

        start = _find_decl_start(text, pos)
        end = _find_decl_end(text, pos)
        if end == -1:
            continue

        raw = text[start : end + 1]
        return " ".join(raw.split())

    return None


def _brace_depth_at(text: str, pos: int) -> int:
    """Return the net brace nesting depth at position pos."""
    depth = 0
    for ch in text[:pos]:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
    return max(0, depth)


def _find_decl_start(text: str, pos: int) -> int:
    i = pos - 1
    while i >= 0:
        if text[i] in (";", "{", "}"):
            return i + 1
        i -= 1
    return 0


def _find_decl_end(text: str, pos: int) -> int:
    depth = 0
    for i in range(pos, len(text)):
        c = text[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        elif c == ";" and depth == 0:
            return i
    return -1


def _parse_declaration(decl: str, symbol: str, source_file: str):
    # Function if symbol is immediately followed by '(' (after optional whitespace)
    sym_call = re.compile(r"\b" + re.escape(symbol) + r"\s*\(")
    match = sym_call.search(decl)
    if match:
        return _parse_function(decl, symbol, match, source_file)
    return _parse_variable(decl, symbol, source_file)


def _parse_function(decl: str, symbol: str, sym_match: re.Match, source_file: str) -> FunctionDecl:
    return_type = decl[: sym_match.start()].strip()
    return_type = re.sub(r"^extern\s+", "", return_type).strip()

    paren_start = decl.index("(", sym_match.start())
    params_text = _extract_balanced(decl, paren_start)
    params_raw = _split_params(params_text)
    is_ptr = [_is_pointer_param(p) for p in params_raw]

    return FunctionDecl(
        name=symbol,
        return_type=return_type,
        params=params_raw,
        is_pointer_param=is_ptr,
        source_file=source_file,
    )


def _parse_variable(decl: str, symbol: str, source_file: str) -> VariableDecl:
    clean = decl.rstrip(";").strip()
    clean = re.sub(r"^extern\s+", "", clean).strip()
    return VariableDecl(
        name=symbol,
        decl_text=clean,
        is_array="[" in clean,
        source_file=source_file,
    )


def _extract_balanced(text: str, start: int) -> str:
    """Return content between the balanced parentheses starting at `start`."""
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return text[start + 1 : i]
    return text[start + 1 :]


def _split_params(params_text: str) -> list[str]:
    """Split parameter list by commas at paren depth 0."""
    params: list[str] = []
    current: list[str] = []
    depth = 0
    for c in params_text:
        if c == "(":
            depth += 1
            current.append(c)
        elif c == ")":
            depth -= 1
            current.append(c)
        elif c == "," and depth == 0:
            p = "".join(current).strip()
            if p:
                params.append(p)
            current = []
        else:
            current.append(c)

    last = "".join(current).strip()
    if last:
        params.append(last)

    if len(params) == 1 and params[0] == "void":
        return []
    return params


def _is_pointer_param(param: str) -> bool:
    param = param.strip()
    for macro in POINTER_MACROS:
        if re.match(rf"{macro}\s*\(", param):
            return True
    return "*" in param


def extract_param_name(param: str) -> str:
    """Return the parameter name from a raw param string."""
    tokens = [t for t in re.split(r"[\s*]+", param.strip()) if t]
    return tokens[-1] if tokens else ""


# ---------------------------------------------------------------------------
# CLI smoke-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python header_scanner.py <include_dir> <symbol> [symbol ...]")
        sys.exit(1)

    include_dir = sys.argv[1]
    syms = sys.argv[2:]
    res = scan_symbols(syms, [include_dir])

    print(f"\nFunctions ({len(res.functions)}):")
    for name, f in res.functions.items():
        print(f"  {name}")
        print(f"    return_type : {f.return_type}")
        print(f"    void_return : {f.is_void_return()}")
        print(f"    params      : {f.params}")
        print(f"    is_ptr      : {f.is_pointer_param}")
        print(f"    source      : {f.source_file}")

    print(f"\nVariables ({len(res.variables)}):")
    for name, v in res.variables.items():
        print(f"  {name}")
        print(f"    decl_text : {v.decl_text}")
        print(f"    is_array  : {v.is_array}")
        print(f"    source    : {v.source_file}")

    print(f"\nNot found ({len(res.not_found)}): {res.not_found}")
