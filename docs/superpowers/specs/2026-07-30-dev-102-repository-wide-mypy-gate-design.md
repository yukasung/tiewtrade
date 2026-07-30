# DEV-102 Repository-wide mypy Gate Design

**Date:** 2026-07-30
**Status:** Approved
**Scope:** Static type checking for `src/tiewtrade` and the complete test suite

## 1. Purpose

DEV-102 makes the repository's default mypy command check both production code
and tests under one strict configuration. The change closes typing gaps in test
doubles, fixtures, builders, dynamic logging assertions, and third-party test
boundaries without changing trading behavior or weakening the source gate.

The command below becomes the single repository type-check entry point:

```bash
.venv/bin/python -m mypy
```

It must check `src/tiewtrade` and `tests` and finish with no errors.

## 2. Observed Baseline

At the start of DEV-102:

- the default mypy command cannot locate the `tiewtrade` package from a clean
  checkout because the `src` layout is not configured as a mypy search path;
- checking `src` and `tests` directly initially produces duplicate test-module
  names because the test directories are not Python packages;
- checking `src/tiewtrade` and `tests` with the correct search path and explicit
  package bases exposes 235 errors in 25 files;
- the existing Python suite passes 739 tests, Ruff passes, and mypy passes for
  the 72 production source files.

The 235 diagnostics are the migration baseline, not permission to suppress the
files or error codes that produce them.

## 3. Configuration Decision

`pyproject.toml` remains the only mypy configuration source. The `[tool.mypy]`
section will:

- retain `python_version = "3.12"`;
- retain `strict = true`;
- replace the source-only `packages = ["tiewtrade"]` target with explicit
  repository paths for `src/tiewtrade` and `tests`;
- add `mypy_path = "src"` so imports resolve from the repository's `src`
  layout without an environment variable or editable install;
- add `explicit_package_bases = true` so identically named test files in
  different directories receive distinct module identities without adding
  package-marker files solely for mypy.

The configuration must not add a global or per-module relaxation such as
`ignore_errors`, `follow_imports = "skip"`, `allow_untyped_calls`, a disabled
error code, or an excluded test directory.

## 4. Migration Strategy

Errors will be resolved in focused groups so each commit has one reviewable
responsibility.

### 4.1 Repository Discovery

First configure the default command and add a small repository contract test
that checks the intended mypy paths and strict settings. This test protects the
gate from silently returning to source-only checking.

### 4.2 Typed Test Data and Doubles

Test builders and doubles must express the contract they already exercise:

- use exact dataclass values or focused `TypedDict` input types instead of
  heterogeneous `dict[str, object]` expansion;
- annotate callback parameters and return values;
- keep a mock reference when assertions require `Mock` methods instead of
  asking mypy to treat a production method as a `Mock`;
- model fake return values with the concrete result type expected by the
  application seam;
- remove obsolete `type: ignore` comments once their original diagnostic no
  longer exists.

Production contracts are changed only if a test exposes a real mismatch in a
public seam. A type-only convenience for tests must stay under `tests/`.

### 4.3 Structured Log Records

Python logging adds `extra` fields dynamically, while `logging.LogRecord`
cannot declare those fields statically. Repeated assertions will use a focused
test helper that gives the existing market-data log field set one typed view.

The cast is allowed only at that dynamic logging boundary. Tests must continue
to assert event names, values, omitted secrets, and field types; the helper must
not fabricate missing values or make a failed assertion pass.

### 4.4 Qt and pytest-qt Boundaries

PySide objects that can legally return `None`, such as table items, will be
checked by an assertion before use. Repeated checks may use a focused helper
that returns the concrete Qt item after proving it exists.

Calls exposed as untyped by pytest-qt will pass through a focused typed test
helper or a localized callable cast. The cast must remain at the third-party
boundary and must not turn the surrounding test data into `Any`.

### 4.5 aiohttp and Other Third-party Test Boundaries

Fake transports will use the exact callable and result types consumed by the
production boundary. Tests constructing aiohttp exceptions will supply valid
typed request and header values when practical.

When a third-party class is intentionally replaced by a structurally compatible
fake but its concrete constructor annotation prevents substitution, a localized
cast is allowed at that constructor call. The fake itself remains fully typed,
and the cast must not enter production code.

## 5. Strictness and Cast Policy

Localized casts are acceptable only when all of the following hold:

1. the value crosses a dynamic or insufficiently typed third-party boundary;
2. the target type is narrower and names the actual runtime contract;
3. the cast is next to the boundary or inside one focused test helper;
4. tests still verify the value's runtime behavior;
5. an ordinary annotation, assertion, `Protocol`, or concrete value cannot
   express the same contract more accurately.

New `Any`, broad `object` plumbing, unscoped `# type: ignore`, or changes to
mypy strictness are not acceptable ways to make the gate pass. A targeted ignore
is permitted only when a third-party stub defect cannot be represented with a
typed wrapper or cast, and it must name the exact error code and explain the
stub boundary. The implementation plan should avoid this fallback unless a
failing mypy case proves it necessary.

## 6. Behavior and Safety Boundaries

DEV-102 must not change:

- Strategy, capital, Basket, Entry Pair, PnL, liquidation, or risk decisions;
- Paper execution or future Live execution boundaries;
- Public Binance market-data retry, deadline, stale-data, backfill, logging, or
  fail-closed behavior;
- SQLite schema, persisted records, UI copy, or Session lifecycle;
- credentials, Private API access, network calls in tests, or Live Orders.

All verification continues to use Paper sessions, fakes, and local test data.

## 7. Verification Strategy

Each migration group follows a type-gate cycle:

1. run mypy against the focused files and preserve the expected failing
   diagnostics before the fix;
2. apply the smallest annotation, helper, or test-double correction;
3. rerun focused mypy until that group is clean;
4. run the affected pytest files and Ruff checks;
5. commit the independently reviewable group.

Final verification must run:

```bash
.venv/bin/python -m mypy
PYTHONPATH=src QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
npm --prefix docs-site test
npm --prefix docs-site run check:content
git diff --check
git diff --check "$(git merge-base main HEAD)" HEAD
```

Success requires zero mypy errors in both production and test code, unchanged
runtime test outcomes, and no new warning or formatting failure.

## 8. Expected File Scope

- Modify: `pyproject.toml`
- Modify: focused test files currently reported by mypy under
  `tests/unit/` and `tests/acceptance/`
- Create only when repeated use justifies them: focused helpers under
  `tests/support/` for market-data log fields or Qt test interactions
- Add or modify a repository contract test that proves the default mypy scope
- Modify production files only if a real consumer contract mismatch is proven
  and the change remains behavior-preserving

No generic `utils.py`, catch-all test model module, base test framework, registry,
or production abstraction will be added.

## 9. Success Criteria

- `.venv/bin/python -m mypy` resolves the `src` layout without `PYTHONPATH`.
- The default command checks both `src/tiewtrade` and all tests.
- `strict = true` remains enabled with no excluded failing directory or disabled
  error category.
- Test doubles, callbacks, builders, Qt assertions, logging assertions, and
  third-party boundaries are typed accurately.
- Python tests, Ruff, documentation checks, and both diff checks pass.
- Production behavior and Trading Safety remain unchanged.

## 10. Out of Scope

- New product, Strategy, execution, persistence, UI, or market-data behavior
- A separate type checker or mypy plugin
- Increasing or decreasing dependency version ranges
- Runtime validation framework for production data
- Refactoring unrelated production modules
- Live Binance credentials, Private API calls, or real Orders
