"""LP04 source verification: actual pinned public artifacts, no scanner/network mocks."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import shutil
import tarfile
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from tools.security.dependencies import evaluate, inventory, package_findings
from tools.security.model import PolicyError, array, obj, policy_counts
from tools.security.scan import scan_dependencies
from tools.security.system import configuration
from tools.security.tests.test_adapters import lockfiles, osv_report
from tools.security.trusted_sources import (
    MANIFEST,
    _files,
    configuration_paths,
)

ROOT = Path(__file__).resolve().parents[3]


def tar_bytes(
    files: dict[str, bytes], *, extra: tarfile.TarInfo | None = None
) -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        for name, content in files.items():
            member = tarfile.TarInfo(name)
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))
        if extra is not None:
            archive.addfile(extra, io.BytesIO(b""))
    return output.getvalue()


class TrustedSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.owned = tempfile.TemporaryDirectory(prefix="security-trusted-source-")
        self.addCleanup(self.owned.cleanup)
        self.root = Path(self.owned.name)
        lockfiles(self.root)
        (self.root / "tools/security").mkdir(parents=True)
        shutil.copytree(ROOT / "frontend/vendor", self.root / "frontend/vendor")
        self.config: dict[str, Any] = json.loads((ROOT / MANIFEST).read_text())
        self.entry = self.config["sources"][0]
        self.lock = json.loads((self.root / "frontend/package-lock.json").read_text())
        self.lock["packages"] = {
            "": {"name": "fixture"},
            "node_modules/picomatch": {
                "version": "4.0.7",
                "dev": True,
                "optional": True,
                "resolved": self.entry["resolved"],
                "integrity": self.entry["integrity"],
            },
        }
        self.save()

    def save(self) -> None:
        (self.root / MANIFEST).write_text(json.dumps(self.config))
        (self.root / "frontend/package-lock.json").write_text(json.dumps(self.lock))

    def replace_artifact(self, content: bytes) -> None:
        (self.root / self.entry["artifact"]).write_bytes(content)
        self.entry["artifact_sha256"] = hashlib.sha256(content).hexdigest()
        self.entry["integrity"] = (
            "sha512-" + base64.b64encode(hashlib.sha512(content).digest()).decode()
        )
        self.lock["packages"]["node_modules/picomatch"]["integrity"] = self.entry[
            "integrity"
        ]
        self.save()

    def test_sbom_gate_and_artifact_specific_exception(self) -> None:
        for fault in ("none", "missing", "version", "advisory", "hash", "lock"):
            with self.subTest(fault=fault):

                def scanner(
                    args: list[str],
                    temp: Path,
                    report: Path,
                    statuses: tuple[int, ...],
                    fault: str = fault,
                ) -> int:
                    path = Path(args[-1].removeprefix("--lockfile="))
                    component = json.loads(path.read_bytes())["components"][0]
                    self.assertEqual(
                        component["hashes"][0]["content"], self.entry["artifact_sha256"]
                    )
                    raw: Any = osv_report(self.root)
                    identity = {
                        "name": "picomatch",
                        "ecosystem": "npm",
                        "version": "4.0.7",
                    }
                    raw["results"][1]["packages"][0]["package"] = identity
                    ids = (
                        ["OTHER", "GHSA-fc5q-39xc-vjpf"]
                        if fault != "advisory"
                        else ["OTHER"]
                    )
                    row = {
                        "package": {
                            **identity,
                            "purl": component["purl"],
                            "version": "0" if fault == "version" else "4.0.7",
                        },
                        "vulnerabilities": [
                            {
                                "id": v,
                                "severity": [
                                    {
                                        "type": "CVSS_V3",
                                        "score": (
                                            "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
                                        ),
                                    }
                                ],
                            }
                            for v in ids
                        ],
                        "groups": [{"ids": ids, "max_severity": "8.7"}],
                    }
                    if fault != "missing":
                        raw["results"].append(
                            {
                                "source": {"path": str(path), "type": "sbom"},
                                "packages": [row],
                            }
                        )
                    if fault == "hash":
                        path.write_text("{}")
                    if fault == "lock":
                        raw["results"].pop(0)
                    report.write_text(json.dumps(raw))
                    return 1

                with (
                    patch("tools.security.scan.execute", side_effect=scanner),
                    patch(
                        "tools.security.scan.verify_withdrawal",
                        side_effect=PolicyError(
                            "TRUSTED_SOURCE_ADVISORY_COVERAGE_UNPROVEN"
                        ),
                    ),
                ):
                    if fault != "none":
                        with self.assertRaises(PolicyError):
                            scan_dependencies(self.root, self.root, Path("scanner"))
                        continue
                    findings, coverage = scan_dependencies(
                        self.root, self.root, Path("scanner")
                    )
                    self.assertEqual(coverage, 2)
                    known = next(
                        f for f in findings if f.locator[3] == "GHSA-fc5q-39xc-vjpf"
                    )
                    self.assertEqual(known.locator[-1], self.entry["artifact_sha256"])
                    exceptions = frozenset({("dependency", known.identity)})
                    self.assertEqual(policy_counts(findings, exceptions)["blocked"], 1)
                    for suffix in ((), ("different-archive",)):
                        original = package_findings(
                            {
                                "vulnerabilities": [
                                    {
                                        "id": known.locator[3],
                                        "severity": [
                                            {
                                                "type": "CVSS_V3",
                                                "score": (
                                                    "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
                                                ),
                                            }
                                        ],
                                    }
                                ],
                                "groups": [
                                    {"ids": [known.locator[3]], "max_severity": "8.7"}
                                ],
                            },
                            ("npm", "picomatch", "4.0.7"),
                            suffix,
                        )
                        self.assertEqual(
                            policy_counts(original, exceptions)["blocked"], 1
                        )

    def test_actual_source_keeps_both_inventory_identities(self) -> None:
        result = inventory(self.root)
        self.assertEqual(
            result["frontend/package-lock.json"], {("npm", "picomatch", "4.0.7")}
        )
        self.assertEqual(result["backend/uv.lock"], {("PyPI", "requests", "2.31.0")})

    def test_default_registry_inventory_unchanged_without_manifest(self) -> None:
        (self.root / MANIFEST).unlink()
        lockfiles(self.root)
        self.assertEqual(
            inventory(self.root)["frontend/package-lock.json"],
            {("npm", "lodash", "4.17.20")},
        )

    def test_missing_manifest_does_not_allow_local_source(self) -> None:
        (self.root / MANIFEST).unlink()
        with self.assertRaisesRegex(PolicyError, "UNSUPPORTED_PACKAGE_SOURCE"):
            inventory(self.root)

    def test_missing_or_tampered_assets_rejected(self) -> None:
        for key in ("artifact", "upstream_artifact", "patch"):
            with self.subTest(key=key):
                path = self.root / self.entry[key]
                original = path.read_bytes()
                path.unlink()
                with self.assertRaises(PolicyError):
                    inventory(self.root)
                path.write_bytes(original + b"altered")
                with self.assertRaises(PolicyError):
                    inventory(self.root)
                path.write_bytes(original)

    def test_symlink_asset_and_manifest_rejected(self) -> None:
        for relative in (self.entry["artifact"], MANIFEST):
            with self.subTest(path=relative):
                path = self.root / relative
                data = path.read_bytes()
                target = self.root / "real-file"
                target.write_bytes(data)
                path.unlink()
                path.symlink_to(target)
                with self.assertRaises(PolicyError):
                    inventory(self.root)
                path.unlink()
                path.write_bytes(data)

    def test_unknown_source_schema_or_identity_rejected(self) -> None:
        original = json.loads(json.dumps(self.config))
        for key, value in (
            ("artifact", "../outside.tgz"),
            ("artifact", "/absolute.tgz"),
            ("resolved", "file:other.tgz"),
            ("name", "other"),
            ("version", "4.0.8"),
            ("lockfile", "other/package-lock.json"),
        ):
            with self.subTest(key=key, value=value):
                self.config = json.loads(json.dumps(original))
                self.config["sources"][0][key] = value
                self.save()
                with self.assertRaises(PolicyError):
                    inventory(self.root)
        self.config = original
        self.config["sources"][0]["unknown"] = "extra"
        self.save()
        with self.assertRaises(PolicyError):
            inventory(self.root)

    def test_duplicate_manifest_keys_rejected(self) -> None:
        text = json.dumps(self.config)
        (self.root / MANIFEST).write_text(
            text.replace('"schema": 1', '"schema": 1, "schema": 1')
        )
        with self.assertRaisesRegex(PolicyError, "DUPLICATE_JSON_KEY"):
            inventory(self.root)

    def test_malformed_manifest_rejected(self) -> None:
        (self.root / MANIFEST).write_text('{"schema":')
        with self.assertRaises(PolicyError):
            inventory(self.root)

    def test_extra_unpatched_identity_occurrence_rejected(self) -> None:
        self.lock["packages"]["node_modules/other/node_modules/picomatch"] = {
            "version": "4.0.7",
            "resolved": self.entry["upstream_url"],
        }
        self.save()
        with self.assertRaisesRegex(
            PolicyError, "UNPATCHED_TRUSTED_IDENTITY_OCCURRENCE"
        ):
            inventory(self.root)

    def test_unknown_local_and_lock_metadata_mismatch_rejected(self) -> None:
        row = self.lock["packages"]["node_modules/picomatch"]
        for key, value in (
            ("resolved", "file:unknown.tgz"),
            ("integrity", "sha512-invalid"),
            ("version", "4.0.8"),
        ):
            original = row[key]
            row[key] = value
            self.save()
            with self.assertRaises(PolicyError):
                inventory(self.root)
            row[key] = original

    def test_unused_manifest_entry_rejected(self) -> None:
        self.lock["packages"].pop("node_modules/picomatch")
        self.save()
        with self.assertRaisesRegex(PolicyError, "UNUSED_TRUSTED_SOURCE"):
            inventory(self.root)

    def test_archive_unsafe_types_paths_duplicates_and_missing_files_rejected(
        self,
    ) -> None:
        files = _files((self.root / self.entry["artifact"]).read_bytes())
        for name, kind in (
            ("../../escape", tarfile.REGTYPE),
            ("/absolute", tarfile.REGTYPE),
            ("package/extra", tarfile.REGTYPE),
            ("package/LICENSE", tarfile.REGTYPE),
            ("package/linked", tarfile.SYMTYPE),
            ("package/hard", tarfile.LNKTYPE),
        ):
            with self.subTest(name=name, kind=kind):
                member = tarfile.TarInfo(name)
                member.type = kind
                member.linkname = (
                    "package/LICENSE"
                    if kind in {tarfile.SYMTYPE, tarfile.LNKTYPE}
                    else ""
                )
                with self.assertRaises(PolicyError):
                    _files(tar_bytes(files, extra=member))
        files.pop("package/README.md")
        with self.assertRaises(PolicyError):
            _files(tar_bytes(files))

    def test_nonparser_content_change_rejected_even_with_updated_tar_hash(self) -> None:
        files = _files((self.root / self.entry["artifact"]).read_bytes())
        files["package/README.md"] += b"changed"
        self.replace_artifact(tar_bytes(files))
        with self.assertRaisesRegex(PolicyError, "TRUSTED_SOURCE_SCOPE_MISMATCH"):
            inventory(self.root)

    def test_parser_patch_mismatch_rejected_even_with_updated_hashes(self) -> None:
        files = _files((self.root / self.entry["artifact"]).read_bytes())
        files["package/lib/parse.js"] += b"\n//changed\n"
        self.entry["parser_sha256"] = hashlib.sha256(
            files["package/lib/parse.js"]
        ).hexdigest()
        self.replace_artifact(tar_bytes(files))
        with self.assertRaisesRegex(PolicyError, "TRUSTED_SOURCE_PATCH_MISMATCH"):
            inventory(self.root)

    def test_policy_digest_binds_manifest_and_all_source_assets(self) -> None:
        (self.root / ".github/security").mkdir(parents=True)
        (self.root / ".github/security/fixture.json").write_text("{}")
        (self.root / ".github/workflows").mkdir()
        (self.root / ".github/workflows/security.yml").write_text("#fixture")
        paths = configuration_paths(self.root)
        self.assertEqual(
            {p.relative_to(self.root).as_posix() for p in paths},
            {
                MANIFEST,
                self.entry["artifact"],
                self.entry["upstream_artifact"],
                self.entry["patch"],
            },
        )
        before = configuration(self.root)
        self.entry["approval"] += " updated"
        self.save()
        self.assertNotEqual(configuration(self.root), before)
        artifact = self.root / self.entry["artifact"]
        artifact.write_bytes(artifact.read_bytes() + b"changed")
        with self.assertRaises(PolicyError):
            configuration(self.root)

    def test_local_source_does_not_suppress_high_and_requires_complete_scan(
        self,
    ) -> None:
        expected = inventory(self.root)
        report = osv_report(self.root)
        package = obj(array(obj(array(report["results"])[1])["packages"])[0])
        package["package"] = {
            "ecosystem": "npm",
            "name": "picomatch",
            "version": "4.0.7",
        }
        package["vulnerabilities"] = [
            {
                "id": "GHSA-fc5q-39xc-vjpf",
                "severity": [
                    {
                        "type": "CVSS_V3",
                        "score": ("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"),
                    }
                ],
            }
        ]
        package["groups"] = [{"ids": ["GHSA-fc5q-39xc-vjpf"], "max_severity": "8.7"}]
        findings, count = evaluate(report, self.root, expected)
        self.assertEqual(count, 2)
        self.assertEqual(findings[0].severity, "high")
        self.assertEqual(policy_counts(findings, frozenset())["high"], 1)
        array(obj(array(report["results"])[1])["packages"]).clear()
        with self.assertRaisesRegex(PolicyError, "INCOMPLETE_DEPENDENCY_INVENTORY"):
            evaluate(report, self.root, expected)


if __name__ == "__main__":
    unittest.main()
