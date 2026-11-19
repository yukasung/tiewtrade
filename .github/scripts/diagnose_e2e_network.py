"""Collect bounded, sanitized E2E network evidence without changing runner configuration."""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

HOSTS = (
    "azure.archive.ubuntu.com",
    "archive.ubuntu.com",
    "security.ubuntu.com",
    "packages.microsoft.com",
)
HTTPS_URLS = ("https://archive.ubuntu.com/ubuntu/", "https://packages.microsoft.com/")
PROXY_NAMES = (
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "no_proxy",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
)
SCRIPT = Path(__file__).resolve()
BUDGET_SECONDS = 100.0
RETRY_DELAY_SECONDS = 0.2
PROBE_TIMEOUT_SECONDS = 8.0
CLEANUP_SECONDS = 0.5


@dataclass(frozen=True)
class CommandResult:
    status: str
    output: str = ""
    code: int | None = None


def run_command(command: list[str], timeout: float = 8.0) -> CommandResult:
    """Never forward raw command output or exceptions to a log."""
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return CommandResult("timeout")
    except FileNotFoundError:
        return CommandResult("tool_unavailable")
    except OSError:
        return CommandResult("operational_error")
    return CommandResult(
        "success" if result.returncode == 0 else "command_failed", result.stdout, result.returncode
    )


def metadata() -> dict[str, object]:
    nameservers = []
    resolver_status = "success"
    try:
        for line in Path("/etc/resolv.conf").read_text().splitlines():
            fields = line.split()
            if len(fields) >= 2 and fields[0] == "nameserver":
                nameservers.append(str(ipaddress.ip_address(fields[1].split("%", 1)[0])))
    except (OSError, ValueError):
        nameservers = []
        resolver_status = "unavailable"
    apt = run_command(["apt-config", "dump"], timeout=2.0)
    # Directive names only; their values can contain proxy credentials.
    apt_proxy = any(
        key.startswith("acquire::") and "proxy" in key
        for key in (line.partition(" ")[0].lower() for line in apt.output.splitlines())
    )
    return {
        "nameservers": nameservers,
        "resolver_status": resolver_status,
        "proxy_env": {name: bool(os.environ.get(name)) for name in PROXY_NAMES},
        "apt_proxy": apt_proxy,
        "apt_proxy_status": apt.status if apt.status != "command_failed" else "unavailable",
    }


def validate_metadata(value: object) -> bool:
    """Only the exact safe schema may cross the privileged subprocess boundary."""
    if not isinstance(value, dict) or set(value) != {
        "nameservers",
        "resolver_status",
        "proxy_env",
        "apt_proxy",
        "apt_proxy_status",
    }:
        return False
    nameservers, proxies = value["nameservers"], value["proxy_env"]
    if not isinstance(nameservers, list) or not isinstance(proxies, dict):
        return False
    if set(proxies) != set(PROXY_NAMES) or any(type(v) is not bool for v in proxies.values()):
        return False
    try:
        if any(not isinstance(v, str) or str(ipaddress.ip_address(v)) != v for v in nameservers):
            return False
    except ValueError:
        return False
    return (
        type(value["apt_proxy"]) is bool
        and value["resolver_status"] in ("success", "unavailable")
        and value["apt_proxy_status"]
        in (
            "success",
            "unavailable",
            "tool_unavailable",
            "timeout",
            "operational_error",
        )
    )


def run_group(command: list[str], seconds: float) -> CommandResult:
    """Own and kill the command's session in the same privilege context as its children."""
    deadline = time.monotonic() + seconds
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            start_new_session=True,
        )
    except FileNotFoundError:
        return CommandResult("tool_unavailable")
    except OSError:
        return CommandResult("operational_error")
    result = CommandResult("operational_error")
    cleanup_ok = True
    try:
        output, _ = process.communicate(timeout=max(0.0, deadline - time.monotonic()))
        result = CommandResult(
            "success" if process.returncode == 0 else "command_failed", output, process.returncode
        )
    except subprocess.TimeoutExpired:
        result = CommandResult("timeout")
    except OSError:
        pass
    finally:
        # Also clear descendants that closed their pipes before their parent exited.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except OSError:
            cleanup_ok = False
        try:
            process.wait(timeout=CLEANUP_SECONDS)
        except (OSError, subprocess.TimeoutExpired):
            cleanup_ok = False
        if process.stdout is not None:
            process.stdout.close()
    return result if cleanup_ok else CommandResult("operational_error")


def fixed_command(kind: str, target: str) -> tuple[list[str], int]:
    if (kind == "dns" and target not in HOSTS) or (kind == "https" and target not in HTTPS_URLS):
        raise ValueError("Unsupported diagnostic target")
    if kind == "dns":
        command = ["getent", "ahosts", target]
        seconds = 5
    elif kind == "https":
        command = [
            "curl",
            "--disable",
            "--silent",
            "--show-error",
            "--head",
            "--fail",
            "--location",
            "--max-redirs",
            "3",
            "--proto",
            "=https",
            "--proto-redir",
            "=https",
            "--retry",
            "0",
            "--connect-timeout",
            "3",
            "--max-time",
            "6",
            "--output",
            "/dev/null",
            "--write-out",
            "%{http_code}",
            target,
        ]
        seconds = 7
    elif kind == "metadata" and target == "-":
        command = [sys.executable, str(SCRIPT), "--metadata-only"]
        seconds = 7
    else:
        raise ValueError("Unsupported diagnostic operation")
    return command, seconds


def bounded_command(kind: str, target: str, context: str) -> list[str]:
    fixed_command(kind, target)  # Validate before crossing the privilege boundary.
    if context not in ("user", "sudo"):
        raise ValueError("Unsupported diagnostic context")
    bounded = [sys.executable, str(SCRIPT), "--supervise", kind, target]
    return ["sudo", "-n", "--", *bounded] if context == "sudo" else bounded


def supervised_command(kind: str, target: str, context: str) -> CommandResult:
    outer = run_command(bounded_command(kind, target, context), PROBE_TIMEOUT_SECONDS)
    # Failure of sudo/the supervisor is not a genuine retryable network timeout.
    if outer.status != "success":
        return CommandResult("operational_error")
    try:
        value = json.loads(outer.output)
    except ValueError:
        return CommandResult("operational_error")
    if not isinstance(value, dict) or set(value) != {"status", "output", "code"}:
        return CommandResult("operational_error")
    status, output, code = value["status"], value["output"], value["code"]
    if not isinstance(output, str):
        return CommandResult("operational_error")
    if status in ("timeout", "tool_unavailable", "operational_error"):
        return (
            CommandResult(status)
            if output == "" and code is None
            else CommandResult("operational_error")
        )
    if type(code) is not int or (status, code == 0) not in (
        ("success", True),
        ("command_failed", False),
    ):
        return CommandResult("operational_error")
    return CommandResult(status, output, code)


def probe(kind: str, target: str, context: str, deadline: float) -> dict[str, object]:
    # Reserve the complete supervisor/cleanup boundary, including in sudo.
    if deadline - time.monotonic() < PROBE_TIMEOUT_SECONDS:
        return {"status": "budget_exhausted"}
    result = supervised_command(kind, target, context)
    if result.status not in ("success", "command_failed"):
        return {"status": result.status}
    if result.code in (124, 137, -9):
        return {"status": "timeout"}
    if result.code in (126, 127):
        return {"status": "tool_unavailable"}
    if kind == "dns":
        if result.code == 2:
            return {"status": "dns_failure"}
        if result.code != 0:
            return {"status": "operational_error"}
        try:
            addresses = [
                ipaddress.ip_address(line.split()[0])
                for line in result.output.splitlines()
                if line.strip()
            ]
        except ValueError:
            return {"status": "invalid_response"}
        return {"status": "success" if addresses else "invalid_response"}
    statuses = {
        5: "proxy_dns_failure",
        6: "dns_failure",
        7: "connection_failure",
        22: "http_failure",
        28: "timeout",
        35: "tls_failure",
        47: "redirect_failure",
        60: "certificate_failure",
    }
    if result.code != 0:
        return {"status": statuses.get(result.code or -1, "operational_error")}
    code = result.output.strip()
    if not re.fullmatch(r"[23][0-9]{2}", code):
        return {"status": "invalid_response"}
    return {"status": "success", "http_status": int(code)}


def https_probe(target: str, context: str, deadline: float) -> dict[str, object]:
    """Retry only the approved sudo Ubuntu timeout, retaining each safe outcome."""
    outcome = probe("https", target, context, deadline)
    if target != HTTPS_URLS[0] or context != "sudo":
        return outcome
    attempts = [outcome]
    while outcome["status"] == "timeout" and len(attempts) < 3:
        # Do not sleep or spawn unless the delay and complete privileged probe fit.
        if deadline - time.monotonic() < RETRY_DELAY_SECONDS + PROBE_TIMEOUT_SECONDS:
            outcome = {"status": "budget_exhausted"}
            break
        time.sleep(RETRY_DELAY_SECONDS)
        outcome = probe("https", target, context, deadline)
        attempts.append(outcome)
    return {**outcome, "attempts": attempts, "attempt_count": len(attempts)}


def _context_metadata(context: str, deadline: float) -> tuple[dict[str, object], bool]:
    """Collect and validate one context without mixing it with probe/gate orchestration."""
    if context == "user":
        context_metadata: object = metadata()
    else:
        remaining = deadline - time.monotonic()
        result = (
            supervised_command("metadata", "-", context)
            if remaining >= PROBE_TIMEOUT_SECONDS
            else CommandResult("budget_exhausted")
        )
        try:
            context_metadata = json.loads(result.output) if result.status == "success" else None
        except ValueError:
            context_metadata = None
    if validate_metadata(context_metadata) and isinstance(context_metadata, dict):
        safe_metadata = context_metadata
        complete = all(
            safe_metadata[key] == "success" for key in ("resolver_status", "apt_proxy_status")
        )
    else:
        safe_metadata = {"status": "unavailable_or_invalid"}
        complete = False
    return safe_metadata, complete


def diagnose() -> tuple[dict[str, object], bool]:
    deadline = time.monotonic() + BUDGET_SECONDS
    contexts: dict[str, object] = {}
    complete = True
    archive_ok = False
    for context in ("user", "sudo"):
        safe_metadata, metadata_complete = _context_metadata(context, deadline)
        complete = complete and metadata_complete
        dns = {host: probe("dns", host, context, deadline) for host in HOSTS}
        https = {url: https_probe(url, context, deadline) for url in HTTPS_URLS}
        contexts[context] = {"metadata": safe_metadata, "dns": dns, "https": https}
        for outcome in (*dns.values(), *https.values()):
            if outcome["status"] in (
                "operational_error",
                "tool_unavailable",
                "invalid_response",
                "budget_exhausted",
            ):
                complete = False
        if context == "sudo":
            archive_ok = https[HTTPS_URLS[0]]["status"] == "success"
    complete = complete and time.monotonic() <= deadline
    allowed = complete and archive_ok
    image = {
        key: value if re.fullmatch(r"[a-zA-Z0-9_.-]{1,80}", value) else "unavailable"
        for key in ("ImageOS", "ImageVersion")
        for value in (os.environ.get(key, ""),)
    }
    return {
        "runner_image": image,
        "contexts": contexts,
        "diagnostic_complete": complete,
        "continue_installation": allowed,
    }, allowed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--metadata-only", action="store_true")
    modes.add_argument("--supervise", nargs=2, metavar=("OPERATION", "TARGET"))
    args = parser.parse_args(argv)
    try:
        if args.supervise:
            command, seconds = fixed_command(*args.supervise)
            result = run_group(command, seconds)
            sys.stdout.write(
                json.dumps({"status": result.status, "output": result.output, "code": result.code})
                + "\n"
            )
            return 0
        if args.metadata_only:
            sys.stdout.write(json.dumps(metadata(), sort_keys=True) + "\n")
            return 0
        report, allowed = diagnose()
        sys.stdout.write(json.dumps(report, sort_keys=True) + "\n")
        if not allowed:
            sys.stderr.write(
                "E2E network preflight failed; inspect sanitized DNS/HTTPS evidence.\n"
            )
        return 0 if allowed else 1
    except (OSError, ValueError, TypeError):
        sys.stderr.write("E2E network diagnostics failed to collect valid evidence.\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
