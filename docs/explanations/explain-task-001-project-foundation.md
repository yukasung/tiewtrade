# Code Explanation: TASK-001 Project Foundation

## 1. Summary

TASK-001 created the foundation for the TiewTrade desktop application.

The work added:

- Python package metadata.
- A `src/` based project structure.
- Application entry points.
- Application bootstrap.
- Configuration loading.
- Logging setup with sensitive-value redaction.
- Shared abstraction folders.
- Foundation tests.

No trading, Binance API, license validation, SQLite persistence, UI screens, or bot runtime logic was implemented in this task.

## 2. Task Context

TASK-001 goal:

Create the base desktop application structure.

TASK-001 scope:

- Project structure.
- Dependency management.
- Application bootstrap.
- Logging framework foundation.
- Configuration framework foundation.
- Desktop application entry point.

Current project status:

- TASK-001 is complete.
- TASK-002 License Module is ready but not started.

## 3. Files Created

### Project And Configuration

- `.env.example`: Lists supported environment variables for local configuration.
- `.gitignore`: Excludes caches, build outputs, virtual environments, logs, and local runtime data.
- `README.md`: Provides basic setup and run instructions.
- `config/app.example.toml`: Example TOML configuration file.
- `pyproject.toml`: Defines package metadata, dependencies, test config, and the `tiewtrade` CLI script.

### Application Package

- `src/tiewtrade/__init__.py`: Defines the application package and version.
- `src/tiewtrade/__main__.py`: Allows running the app with `python -m tiewtrade`.
- `src/tiewtrade/main.py`: Defines the command-line entry point.

### Application Layer

- `src/tiewtrade/application/__init__.py`: Application package marker.
- `src/tiewtrade/application/bootstrap.py`: Initializes foundation services.
- `src/tiewtrade/application/context.py`: Defines the app context returned by bootstrap.

### Layer Placeholders

- `src/tiewtrade/domain/__init__.py`
- `src/tiewtrade/infrastructure/__init__.py`
- `src/tiewtrade/persistence/__init__.py`
- `src/tiewtrade/presentation/__init__.py`

These files establish the layered package structure without adding business logic.

### Shared Layer

- `src/tiewtrade/shared/__init__.py`
- `src/tiewtrade/shared/base/__init__.py`
- `src/tiewtrade/shared/functions/__init__.py`
- `src/tiewtrade/shared/helpers/__init__.py`
- `src/tiewtrade/shared/services/__init__.py`
- `src/tiewtrade/shared/services/configuration.py`
- `src/tiewtrade/shared/services/logging.py`
- `src/tiewtrade/shared/utils/__init__.py`

### Tests

- `tests/test_foundation.py`: Tests configuration loading, bootstrap behavior, and logging redaction.

## 4. Files Modified

- `docs/status.md`: Updated project progress after TASK-001 completion.

## 5. Code Walkthrough

### `pyproject.toml`

Defines the Python package.

Important parts:

- Requires Python `>=3.13`.
- Declares `PySide6` and `binance-connector` dependencies for future UI and exchange tasks.
- Defines the CLI command:

```text
tiewtrade = "tiewtrade.main:main"
```

TASK-001 only declares these dependencies. It does not use PySide6 or Binance yet.

### `src/tiewtrade/main.py`

Provides the command-line entry point.

It supports:

- `--version`: prints the package version.
- `--check`: initializes foundation services and prints a readiness message.
- `--config`: accepts an optional TOML config file path.

The main flow:

```text
Parse CLI arguments
↓
If --version, print version and exit
↓
Create ApplicationBootstrap
↓
Initialize configuration and logging
↓
Write foundation-ready log
↓
Print check message if --check was used
```

### `src/tiewtrade/application/bootstrap.py`

Defines `ApplicationBootstrap`.

This class initializes:

- Application configuration.
- Data directory.
- Log directory.
- Logger.

It returns an `AppContext` containing the initialized config and logger.

### `src/tiewtrade/application/context.py`

Defines `AppContext`.

`AppContext` is a small immutable container with:

- `config`: the loaded `AppConfig`.
- `logger`: the configured application logger.

This gives later application services a single object for foundation services.

### `src/tiewtrade/shared/services/configuration.py`

Defines configuration loading.

Configuration can come from:

- Environment variables.
- Optional TOML file.
- Defaults.

Precedence:

```text
Environment variable
↓
TOML file value
↓
Default value
```

Important behavior:

- `environ=None` means use real process environment variables.
- `environ={}` means use an intentionally empty environment mapping.

That second behavior is important for deterministic tests and prevents accidental process-environment leakage.

### `src/tiewtrade/shared/services/logging.py`

Defines centralized logging setup and redaction.

Logging writes to:

- Console stream.
- Local log file.

The logger uses `RedactingFilter` to remove sensitive values before handlers write records.

Sensitive markers include:

- API keys.
- API secrets.
- Generic secrets.
- License values.
- Tokens.
- Signatures.

The redaction supports:

- Plain strings.
- JSON-like strings.
- Dictionaries.
- Nested dictionaries.
- Lists.
- Tuples.
- Mapping-format logging arguments.

This is important because future tasks will handle license files, API keys, and Binance responses.

## 6. Important Classes

### `AppConfig`

Location: `src/tiewtrade/shared/services/configuration.py`

Purpose:

Stores validated foundation configuration.

Fields:

- `app_name`
- `environment`
- `data_dir`
- `log_dir`
- `log_file`
- `log_level`

### `ApplicationBootstrap`

Location: `src/tiewtrade/application/bootstrap.py`

Purpose:

Initializes the foundation services needed when the app starts.

Used by:

- `src/tiewtrade/main.py`
- Tests in `tests/test_foundation.py`

### `AppContext`

Location: `src/tiewtrade/application/context.py`

Purpose:

Carries initialized foundation services after bootstrap.

### `RedactingFilter`

Location: `src/tiewtrade/shared/services/logging.py`

Purpose:

Redacts sensitive values before log records are written.

## 7. Important Functions

### `main()`

Location: `src/tiewtrade/main.py`

Runs the command-line application.

Inputs:

- Optional CLI argument sequence.

Output:

- Exit code integer.

### `build_parser()`

Location: `src/tiewtrade/main.py`

Creates the CLI parser for `--version`, `--check`, and `--config`.

### `load_app_config()`

Location: `src/tiewtrade/shared/services/configuration.py`

Loads config from environment, optional TOML file, and defaults.

Inputs:

- Optional config path.
- Optional environment mapping.

Output:

- `AppConfig`.

### `configure_logging()`

Location: `src/tiewtrade/shared/services/logging.py`

Creates and configures the application logger.

Inputs:

- `AppConfig`.

Output:

- Configured `logging.Logger`.

## 8. Architecture Alignment

TASK-001 follows the documented layered architecture:

- Application bootstrap lives in the Application Layer.
- Configuration and logging are reusable Shared Services.
- Domain, Infrastructure, Persistence, and Presentation packages exist but contain no premature logic.
- No UI code calls Binance or persistence.
- Domain does not depend on PySide6, Binance, SQLite, or OS services.
- Logging redaction is centralized instead of duplicated.

The implementation stays inside TASK-001 scope and does not implement future tasks.

## 9. Data Flow

### Startup / Check Flow

```text
User runs command
↓
main()
↓
ApplicationBootstrap.initialize()
↓
load_app_config()
↓
Create data and log directories
↓
configure_logging()
↓
Return AppContext
↓
Log readiness message
↓
Print optional --check message
```

### Configuration Flow

```text
Environment variables
↓
Optional TOML config
↓
Defaults
↓
AppConfig
```

### Logging Flow

```text
Application logs message
↓
RedactingFilter redacts sensitive message and args
↓
Console handler writes safe message
↓
File handler writes safe message
```

## 10. How To Run

Show version:

```text
PYTHONPATH=src python3 -m tiewtrade --version
```

Run foundation check:

```text
PYTHONPATH=src TIEWTRADE_DATA_DIR=var/data TIEWTRADE_LOG_DIR=var/logs python3 -m tiewtrade --check
```

Use an explicit config file:

```text
PYTHONPATH=src python3 -m tiewtrade --config config/app.example.toml --check
```

## 11. How To Verify

Run unit tests:

```text
PYTHONPATH=src python3 -m unittest discover -s tests
```

Run compile check:

```text
PYTHONPATH=src python3 -m compileall -q src tests
```

Expected result:

- Tests pass.
- Compile check returns no output.
- Logs should show `[REDACTED]` instead of raw sensitive values.

## 12. Limitations

TASK-001 intentionally does not implement:

- Offline License File validation.
- Secure credential storage.
- SQLite database setup.
- Binance account validation.
- Spot or Futures adapters.
- Bot lifecycle.
- Strategy logic.
- Risk engine.
- Order management.
- Position management.
- Recovery engine.
- PySide6 UI screens.

Known limitation:

- Full editable dependency installation was not verified in this workflow.
- Default data directory uses the user home directory. In sandboxed test runs, use local `TIEWTRADE_DATA_DIR` and `TIEWTRADE_LOG_DIR` overrides.

## 13. Next Recommended Step

Proceed to TASK-002 License Module through the implementation workflow.

TASK-002 should build on this foundation by adding local Offline License File validation without adding online activation or network license checks.
