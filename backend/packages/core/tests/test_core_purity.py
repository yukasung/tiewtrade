"""Mechanical checks on the Trading Core's two standing rules (ADR-0001, IMP-02).

import-linter already proves the core imports no framework and no sibling package. These
tests cover what it cannot see: that every Decimal calculation runs in the core's own
context, and that the core reads no clock, no filesystem and no randomness.

Both rules have been broken by hand before. ``remaining_quantity`` once subtracted without
``@calc`` and truncated silently under a caller's low precision; the trigger predicates
once used signed arithmetic and raised under a caller trapping Inexact. Remembering the
rule is evidently not enough, so it is checked here instead.
"""

import ast
import pathlib

import pytest

CORE = pathlib.Path(__file__).resolve().parents[1] / "src" / "tiewtrade_core"

ARITHMETIC = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow)

# Reading any of these would make a result depend on when or where it ran, which breaks
# replay and reproducible tests (ADR-0001). Time and ids come from the caller instead.
FORBIDDEN_MODULES = frozenset(
    {"os", "sys", "time", "random", "secrets", "datetime", "uuid", "pathlib", "socket"}
)
FORBIDDEN_CALLS = frozenset({"open", "input", "print", "eval", "exec", "compile", "breakpoint"})


def core_modules() -> list[pathlib.Path]:
    return sorted(p for p in CORE.rglob("*.py") if "__pycache__" not in p.parts)


def module_id(path: pathlib.Path) -> str:
    return str(path.relative_to(CORE))


MODULES = core_modules()
IDS = [module_id(p) for p in MODULES]


def test_the_core_has_modules_to_check() -> None:
    """Guards the checks below from passing because they found nothing to look at."""
    assert len(MODULES) > 10


def _has_calc(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return any(
        (isinstance(d, ast.Name) and d.id == "calc")
        or (isinstance(d, ast.Attribute) and d.attr == "calc")
        for d in node.decorator_list
    )


def _unprotected_arithmetic(tree: ast.Module) -> list[str]:
    """Functions that do arithmetic while neither they nor an enclosing function run in CALC."""
    found: list[str] = []

    def walk(node: ast.AST, protected: bool) -> None:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            protected = protected or _has_calc(node)
            if not protected and any(
                isinstance(inner, ast.BinOp) and isinstance(inner.op, ARITHMETIC)
                for inner in ast.walk(node)
            ):
                found.append(f"{node.name} (line {node.lineno})")
        for child in ast.iter_child_nodes(node):
            walk(child, protected)

    walk(tree, False)
    return found


@pytest.mark.parametrize("path", MODULES, ids=IDS)
def test_arithmetic_runs_in_the_core_decimal_context(path: pathlib.Path) -> None:
    """Every function doing arithmetic must be wrapped in ``@calc``, directly or by a caller.

    Without it the operation runs in whatever context the caller happens to be in: a low
    precision truncates the result silently, and a trapped Inexact raises on what looks
    like a plain attribute read. A function that only compares needs no decorator, which is
    why the check looks for arithmetic operators rather than for Decimal values.
    """
    offenders = _unprotected_arithmetic(ast.parse(path.read_text()))

    assert not offenders, (
        f"{module_id(path)} does arithmetic outside the core Decimal context: "
        f"{', '.join(offenders)}. Add @calc, or rewrite it as a comparison."
    )


@pytest.mark.parametrize("path", MODULES, ids=IDS)
def test_the_core_reads_no_clock_filesystem_or_randomness(path: pathlib.Path) -> None:
    """Closes IMP-02: import-linter blocks frameworks, not the stdlib's nondeterminism."""
    tree = ast.parse(path.read_text())
    offenders: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            offenders += [
                f"import {alias.name} (line {node.lineno})"
                for alias in node.names
                if alias.name.split(".")[0] in FORBIDDEN_MODULES
            ]
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root in FORBIDDEN_MODULES:
                offenders.append(f"from {node.module} import ... (line {node.lineno})")
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in FORBIDDEN_CALLS
        ):
            offenders.append(f"{node.func.id}() (line {node.lineno})")

    assert not offenders, (
        f"{module_id(path)} reaches outside pure computation: {', '.join(offenders)}. "
        "Time, ids and randomness come from the caller (ADR-0001)."
    )


def test_decimal_is_imported_from_the_standard_library_only() -> None:
    """``decimal`` is the one numeric import the core needs; ``float`` must not appear."""
    offenders: list[str] = []

    for path in MODULES:
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Name) and node.id == "float":
                offenders.append(f"{module_id(path)} line {node.lineno}")

    assert not offenders, f"money must be Decimal, never float: {', '.join(offenders)}"
