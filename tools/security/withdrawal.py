"""Fresh, bounded evidence for the exact approved LP04 advisory withdrawal."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from datetime import UTC, datetime

from tools.security.model import PolicyError, array, obj, string

ADVISORY = "GHSA-fc5q-39xc-vjpf"
ARTIFACT = "9cc97cff17fcae65f9b7e9b249670d38decc451c0210f34678de608a5e8ff39d"
API = "https://api.osv.dev/v1"
LIMIT = 2 * 1024 * 1024
ERROR = "TRUSTED_SOURCE_ADVISORY_COVERAGE_UNPROVEN"


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise PolicyError(ERROR)
        result[key] = value
    return result


def _request(path: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    url = API + path
    request = urllib.request.Request(
        url,
        data=None if payload is None else json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status != 200 or response.geturl() != url:
                raise PolicyError(ERROR)
            raw = response.read(LIMIT + 1)
        if len(raw) > LIMIT:
            raise PolicyError(ERROR)
        return obj(json.loads(raw, object_pairs_hook=_unique_pairs))
    except (OSError, ValueError, UnicodeError) as error:
        raise PolicyError(ERROR) from error


def verify_withdrawal(row: dict[str, object], entry: dict[str, str]) -> None:
    """Absence alone never proves coverage; all other advisories stay in evaluation."""
    if (entry["name"], entry["version"], entry["artifact_sha256"]) != (
        "picomatch",
        "4.0.7",
        ARTIFACT,
    ):
        raise PolicyError(ERROR)
    record = _request("/vulns/" + ADVISORY)
    stamp = string(record.get("withdrawn"))
    if record.get("id") != ADVISORY or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z", stamp
    ):
        raise PolicyError(ERROR)
    try:
        withdrawn = datetime.fromisoformat(stamp)
    except ValueError:
        raise PolicyError(ERROR) from None
    if withdrawn > datetime.now(UTC):
        raise PolicyError(ERROR)
    matches = [
        obj(affected)
        for affected in array(record.get("affected"))
        if obj(obj(affected).get("package")).get("ecosystem") == "npm"
        and obj(obj(affected).get("package")).get("name") == "picomatch"
    ]
    if len(matches) != 1 or matches[0].get("ranges") != [
        {"type": "SEMVER", "events": [{"introduced": "0"}, {"last_affected": "4.0.7"}]}
    ]:
        raise PolicyError(ERROR)
    query = _request(
        "/query",
        {"package": {"ecosystem": "npm", "name": "picomatch"}, "version": "4.0.7"},
    )
    if set(query) - {"vulns"}:
        raise PolicyError(ERROR)
    active = [obj(v) for v in array(query.get("vulns", []))]
    ids = [string(v.get("id")) for v in active]
    reported = {
        string(obj(v).get("id")): obj(v) for v in array(row.get("vulnerabilities", []))
    }
    if (
        len(ids) != len(set(ids))
        or ADVISORY in ids
        or any(v.get("withdrawn") for v in active)
        or set(ids) != reported.keys()
    ):
        raise PolicyError(ERROR)
    for advisory in active:
        previous = reported[string(advisory["id"])]
        if any(
            advisory.get(key) != previous.get(key)
            for key in (
                "modified",
                "severity",
                "affected",
                "withdrawn",
                "database_specific",
            )
        ):
            raise PolicyError(ERROR)
