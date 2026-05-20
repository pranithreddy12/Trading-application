from __future__ import annotations

import ast
import re
import textwrap
from dataclasses import dataclass
from typing import Iterable


FORBIDDEN_IMPORTS = {
    "os",
    "sys",
    "subprocess",
    "socket",
    "shutil",
    "ctypes",
    "pickle",
    "importlib",
}


@dataclass
class SanitizedCode:
    code: str
    warnings: list[str]


def strip_markdown_fences(code: str) -> str:
    cleaned = code.strip()
    fence = re.search(r"```(?:python)?\s*\n?(.*?)\n?```", cleaned, re.DOTALL | re.IGNORECASE)
    if fence:
        return fence.group(1).strip()
    return cleaned


def normalize_indentation(code: str) -> str:
    return textwrap.dedent(code).replace("\t", "    ").strip() + "\n"


def _forbidden_imports(tree: ast.AST) -> list[str]:
    blocked: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root in FORBIDDEN_IMPORTS:
                    blocked.append(root)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root = node.module.split(".", 1)[0]
                if root in FORBIDDEN_IMPORTS:
                    blocked.append(root)
    return sorted(set(blocked))


def sanitize_python_code(code: str) -> SanitizedCode:
    cleaned = normalize_indentation(strip_markdown_fences(code))
    tree = ast.parse(cleaned)
    blocked = _forbidden_imports(tree)
    if blocked:
        raise ValueError(f"Forbidden imports detected: {', '.join(blocked)}")
    compile(tree, "<sanitized_code>", "exec")
    return SanitizedCode(code=cleaned, warnings=[])


def safe_exec(code: str, globals_dict: dict | None = None, locals_dict: dict | None = None):
    sanitized = sanitize_python_code(code)
    safe_builtins = {
        "abs": abs,
        "all": all,
        "any": any,
        "bool": bool,
        "dict": dict,
        "enumerate": enumerate,
        "float": float,
        "int": int,
        "len": len,
        "list": list,
        "max": max,
        "min": min,
        "range": range,
        "round": round,
        "str": str,
        "sum": sum,
        "tuple": tuple,
        "zip": zip,
    }
    sandbox_globals = {"__builtins__": safe_builtins}
    if globals_dict:
        sandbox_globals.update(globals_dict)
    exec(sanitized.code, sandbox_globals, locals_dict)
    return sandbox_globals, locals_dict
