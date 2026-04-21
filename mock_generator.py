from __future__ import annotations

from header_scanner import FunctionDecl, ScanResult, VariableDecl, extract_param_name

VARIABLE_MOCK_HINT = "/* MOCK: verify initial value */"
MAX_HINT_LENGTH = 80


def generate_mocks(scan_result: ScanResult, variable_hint: str = VARIABLE_MOCK_HINT) -> str:
    blocks: list[str] = []

    for decl in scan_result.variables.values():
        blocks.append(_generate_variable_mock(decl, variable_hint))

    for decl in scan_result.functions.values():
        blocks.append(_generate_function_mock(decl))

    if scan_result.not_found:
        blocks.append(_generate_not_found_comment(scan_result.not_found))

    return "\n\n".join(blocks)


# ---------------------------------------------------------------------------
# Internal generators
# ---------------------------------------------------------------------------

def _generate_function_mock(decl: FunctionDecl) -> str:
    void_return = decl.is_void_return()
    has_params = len(decl.params) > 0

    params_str = ", ".join(decl.params) if has_params else "void"
    signature = f"{decl.return_type} {decl.name}({params_str})"

    body = _build_function_body(decl, void_return, has_params)
    return f"{signature}\n{{\n{body}\n}}"


def _build_function_body(decl: FunctionDecl, void_return: bool, has_params: bool) -> str:
    lines: list[str] = []

    if void_return and not has_params:
        lines.append("    function_called();")
    else:
        for i, param in enumerate(decl.params):
            name = extract_param_name(param)
            if decl.is_pointer_param[i]:
                lines.append(f"    check_expected_ptr({name});")
            else:
                lines.append(f"    check_expected({name});")
        if not void_return:
            lines.append("    return mock();")

    return "\n".join(lines)


def _generate_variable_mock(decl: VariableDecl, hint: str) -> str:
    init = "NULL_PTR" if "*" in decl.decl_text else "{0}"
    return f"{decl.decl_text} = {init}; {hint}"


def _generate_not_found_comment(symbols: list[str]) -> str:
    lines = ["/* MOCK: the following symbols could not be resolved - handle manually: */"]
    for s in symbols:
        lines.append(f"/* {s} */")
    return "\n".join(lines)
