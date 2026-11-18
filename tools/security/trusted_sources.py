"""Fail-closed verification of the single owner-approved LP04 source replacement.

This preserves npm identity/version for OSV and never disposes advisory findings.
"""

from __future__ import annotations

import base64
import difflib
import hashlib
import io
import json
import re
import tarfile
from pathlib import Path, PurePosixPath

from tools.security.model import PolicyError, array, obj, read_json, string

MANIFEST = "tools/security/trusted-sources.json"
FIELDS = frozenset(
    {
        "ecosystem",
        "name",
        "version",
        "lockfile",
        "location",
        "resolved",
        "artifact",
        "artifact_sha256",
        "integrity",
        "parser_sha256",
        "manifest_sha256",
        "license_sha256",
        "upstream_artifact",
        "upstream_sha256",
        "upstream_integrity",
        "upstream_url",
        "patch",
        "patch_sha256",
        "approval",
        "evidence",
    }
)
FILES = frozenset(
    {
        "package/LICENSE",
        "package/README.md",
        "package/index.js",
        "package/posix.js",
        "package/package.json",
        "package/lib/constants.js",
        "package/lib/parse.js",
        "package/lib/picomatch.js",
        "package/lib/scan.js",
        "package/lib/utils.js",
    }
)


def _bytes(root: Path, relative: str, limit: int = 2 * 1024 * 1024) -> bytes:
    path = PurePosixPath(relative)
    if (
        path.is_absolute()
        or ".." in path.parts
        or str(path) != relative
        or "\\" in relative
    ):
        raise PolicyError("INVALID_TRUSTED_SOURCE_PATH")
    target = root.resolve() / relative
    current = root.resolve()
    for part in path.parts:
        current /= part
        if current.is_symlink():
            raise PolicyError("INVALID_TRUSTED_SOURCE_PATH")
    if not target.is_file() or target.stat().st_size > limit:
        raise PolicyError("MISSING_TRUSTED_SOURCE_FILE")
    return target.read_bytes()


def _hash(data: bytes, expected: str) -> None:
    if (
        not re.fullmatch(r"[0-9a-f]{64}", expected)
        or hashlib.sha256(data).hexdigest() != expected
    ):
        raise PolicyError("TRUSTED_SOURCE_HASH_MISMATCH")


def _integrity(data: bytes, expected: str) -> None:
    actual = "sha512-" + base64.b64encode(hashlib.sha512(data).digest()).decode()
    if expected != actual:
        raise PolicyError("TRUSTED_SOURCE_INTEGRITY_MISMATCH")


def _files(data: bytes) -> dict[str, bytes]:
    contents: dict[str, bytes] = {}
    total = 0
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        for member in archive:
            if (
                not member.isfile()
                or member.name not in FILES
                or member.name in contents
                or member.pax_headers
                or member.size < 0
            ):
                raise PolicyError("INVALID_TRUSTED_SOURCE_ARCHIVE")
            total += member.size
            if total > 2 * 1024 * 1024:
                raise PolicyError("INVALID_TRUSTED_SOURCE_ARCHIVE")
            stream = archive.extractfile(member)
            if stream is None:
                raise PolicyError("INVALID_TRUSTED_SOURCE_ARCHIVE")
            with stream:
                content = stream.read(member.size + 1)
            if len(content) != member.size:
                raise PolicyError("INVALID_TRUSTED_SOURCE_ARCHIVE")
            contents[member.name] = content
    if contents.keys() != FILES:
        raise PolicyError("INVALID_TRUSTED_SOURCE_ARCHIVE")
    return contents


def _validate(root: Path, entry: dict[str, str]) -> None:
    fixed = {
        "ecosystem": "npm",
        "name": "picomatch",
        "version": "4.0.7",
        "lockfile": "frontend/package-lock.json",
        "location": "node_modules/picomatch",
        "resolved": "file:vendor/picomatch-4.0.7-lp04.tgz",
        "artifact": "frontend/vendor/picomatch-4.0.7-lp04.tgz",
        "upstream_artifact": "frontend/vendor/picomatch-4.0.7-upstream.tgz",
        "upstream_url": "https://registry.npmjs.org/picomatch/-/picomatch-4.0.7.tgz",
        "patch": "frontend/vendor/picomatch-4.0.7-lp04.patch",
    }
    if any(entry[key] != value for key, value in fixed.items()):
        raise PolicyError("UNSUPPORTED_TRUSTED_SOURCE")
    patched = _bytes(root, entry["artifact"])
    original = _bytes(root, entry["upstream_artifact"])
    patch = _bytes(root, entry["patch"])
    _hash(patched, entry["artifact_sha256"])
    _hash(original, entry["upstream_sha256"])
    _hash(patch, entry["patch_sha256"])
    _integrity(patched, entry["integrity"])
    _integrity(original, entry["upstream_integrity"])
    before, after = _files(original), _files(patched)
    if any(
        before[name] != after[name] for name in FILES if name != "package/lib/parse.js"
    ):
        raise PolicyError("TRUSTED_SOURCE_SCOPE_MISMATCH")
    package = obj(json.loads(after["package/package.json"]))
    if (
        package.get("name") != entry["name"]
        or package.get("version") != entry["version"]
    ):
        raise PolicyError("TRUSTED_SOURCE_METADATA_MISMATCH")
    _hash(after["package/lib/parse.js"], entry["parser_sha256"])
    _hash(after["package/package.json"], entry["manifest_sha256"])
    _hash(after["package/LICENSE"], entry["license_sha256"])
    expected_patch = "".join(
        difflib.unified_diff(
            before["package/lib/parse.js"].decode().splitlines(keepends=True),
            after["package/lib/parse.js"].decode().splitlines(keepends=True),
            fromfile="a/lib/parse.js",
            tofile="b/lib/parse.js",
        )
    ).encode()
    if expected_patch != patch:
        raise PolicyError("TRUSTED_SOURCE_PATCH_MISMATCH")


def declared_sources(root: Path) -> dict[str, dict[str, str]]:
    path = root / MANIFEST
    if not path.exists() and not path.is_symlink():
        return {}
    try:
        _bytes(root, MANIFEST, 64 * 1024)  # canonical path/type/size/symlink check
        config = obj(read_json(root / MANIFEST, 64 * 1024))
        if (
            config.keys() != {"schema", "sources"}
            or type(config.get("schema")) is not int
            or config["schema"] != 1
        ):
            raise PolicyError("INVALID_TRUSTED_SOURCE_MANIFEST")
        sources = array(config["sources"])
        if len(sources) > 1:
            raise PolicyError("UNSUPPORTED_TRUSTED_SOURCE")
        result = {}
        for value in sources:
            raw = obj(value)
            if raw.keys() != FIELDS:
                raise PolicyError("INVALID_TRUSTED_SOURCE_MANIFEST")
            entry = {key: string(raw[key]) for key in FIELDS}
            _validate(root, entry)
            result[entry["location"]] = entry
        return result
    except (OSError, ValueError, UnicodeError, tarfile.TarError):
        raise PolicyError("INVALID_TRUSTED_SOURCE_MANIFEST") from None


def configuration_paths(root: Path) -> list[Path]:
    entries = declared_sources(root)
    if not (root / MANIFEST).exists():
        return []
    paths = {MANIFEST}
    for entry in entries.values():
        paths.update(entry[key] for key in ("artifact", "upstream_artifact", "patch"))
    return [root / path for path in sorted(paths)]
