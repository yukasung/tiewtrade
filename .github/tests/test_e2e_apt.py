"""Exercise runner APT configuration changes without sudo or a live package manager."""

from __future__ import annotations

import io
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import prepare_e2e_apt as apt  # noqa: E402


class AptPreparationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "apt"
        self.root.mkdir()

    def write(self, relative: str, content: bytes) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def test_mirror_list_preserves_security_priorities_comments_and_line_endings(self) -> None:
        path = self.write(
            "apt-mirrors.txt",
            b"# http://azure.archive.ubuntu.com/ubuntu\r\n"
            b"http://azure.archive.ubuntu.com/ubuntu/\tpriority:10\r\n"
            b"https://security.ubuntu.com/ubuntu\tpriority:20\r\n",
        )
        self.assertEqual(apt.prepare_apt(self.root), 1)
        self.assertEqual(
            path.read_bytes(),
            b"# http://azure.archive.ubuntu.com/ubuntu\r\n"
            b"https://archive.ubuntu.com/ubuntu/\tpriority:10\r\n"
            b"https://security.ubuntu.com/ubuntu\tpriority:20\r\n",
        )

    def test_legacy_sources_preserve_suites_components_keys_and_other_repositories(self) -> None:
        path = self.write(
            "sources.list",
            b"deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] "
            b"https://azure.archive.ubuntu.com/ubuntu noble main restricted universe multiverse\n"
            b"deb https://security.ubuntu.com/ubuntu noble-security main universe\n"
            b"deb [signed-by=/usr/share/keyrings/vendor.gpg] "
            b"https://packages.example.invalid/repos/code stable main\n"
            b"deb https://azure.archive.ubuntu.com.evil.invalid/ubuntu stable main\n",
        )
        self.assertEqual(apt.prepare_apt(self.root), 1)
        self.assertEqual(
            path.read_bytes(),
            b"deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] "
            b"https://archive.ubuntu.com/ubuntu noble main restricted universe multiverse\n"
            b"deb https://security.ubuntu.com/ubuntu noble-security main universe\n"
            b"deb [signed-by=/usr/share/keyrings/vendor.gpg] "
            b"https://packages.example.invalid/repos/code stable main\n"
            b"deb https://azure.archive.ubuntu.com.evil.invalid/ubuntu stable main\n",
        )

    def test_deb822_preserves_all_fields_and_supports_http_and_https(self) -> None:
        path = self.write(
            "sources.list.d/ubuntu.sources",
            b"Types: deb deb-src\n"
            b"URIs: http://azure.archive.ubuntu.com/ubuntu https://azure.archive.ubuntu.com/ubuntu/\n"
            b"Suites: noble noble-updates noble-backports\n"
            b"Components: main restricted universe multiverse\n"
            b"Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg\n\n"
            b"Types: deb\nURIs: https://security.ubuntu.com/ubuntu\nSuites: noble-security\n"
            b"Components: main universe\n"
            b"Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg\n",
        )
        expected = (
            b"Types: deb deb-src\n"
            b"URIs: https://archive.ubuntu.com/ubuntu https://archive.ubuntu.com/ubuntu/\n"
            b"Suites: noble noble-updates noble-backports\n"
            b"Components: main restricted universe multiverse\n"
            b"Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg\n\n"
            b"Types: deb\nURIs: https://security.ubuntu.com/ubuntu\nSuites: noble-security\n"
            b"Components: main universe\n"
            b"Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg\n"
        )
        self.assertEqual(apt.prepare_apt(self.root), 1)
        self.assertEqual(path.read_bytes(), expected)

    def test_repeated_preparation_is_idempotent_and_preserves_permissions(self) -> None:
        path = self.write("apt-mirrors.txt", b"http://azure.archive.ubuntu.com/ubuntu\n")
        path.chmod(0o640)
        owner = path.stat().st_uid
        self.assertEqual(apt.prepare_apt(self.root), 1)
        self.assertEqual(apt.prepare_apt(self.root), 0)
        self.assertEqual(path.read_bytes(), b"https://archive.ubuntu.com/ubuntu\n")
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o640)
        self.assertEqual(path.stat().st_uid, owner)

    def test_already_official_mirror_layout_is_a_successful_noop(self) -> None:
        path = self.write("apt-mirrors.txt", b"https://archive.ubuntu.com/ubuntu\n")
        self.assertEqual(apt.prepare_apt(self.root), 0)
        self.assertEqual(path.read_bytes(), b"https://archive.ubuntu.com/ubuntu\n")

    def test_unknown_layout_and_missing_known_configs_are_failures(self) -> None:
        with self.assertRaises(ValueError):
            apt.prepare_apt(self.root)
        self.write(
            "sources.list.d/other.sources", b"URIs: http://azure.archive.ubuntu.com/ubuntu\n"
        )
        with self.assertRaises(ValueError):
            apt.prepare_apt(self.root)
        self.write("apt-mirrors.txt", b"unrecognized mirror configuration\n")
        with self.assertRaises(ValueError):
            apt.prepare_apt(self.root)

    def test_unsupported_azure_uri_prevents_any_writes(self) -> None:
        first = self.write("apt-mirrors.txt", b"http://azure.archive.ubuntu.com/ubuntu\n")
        self.write("sources.list", b"deb https://azure.archive.ubuntu.com/other noble main\n")
        with self.assertRaises(ValueError):
            apt.prepare_apt(self.root)
        self.assertEqual(first.read_bytes(), b"http://azure.archive.ubuntu.com/ubuntu\n")

    def test_symlinked_config_or_parent_cannot_write_outside_the_root(self) -> None:
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        target = outside / "ubuntu.sources"
        target.write_bytes(b"URIs: http://azure.archive.ubuntu.com/ubuntu\n")
        link = self.root / "sources.list"
        link.symlink_to(target)
        with self.assertRaises(ValueError):
            apt.prepare_apt(self.root)
        link.unlink()
        (self.root / "sources.list.d").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            apt.prepare_apt(self.root)
        self.assertEqual(target.read_bytes(), b"URIs: http://azure.archive.ubuntu.com/ubuntu\n")

    def test_read_and_write_errors_propagate_instead_of_reporting_success(self) -> None:
        self.write("apt-mirrors.txt", b"http://azure.archive.ubuntu.com/ubuntu\n")
        for operation in ("read_bytes", "write_bytes"):
            with (
                self.subTest(operation=operation),
                patch.object(
                    Path, operation, side_effect=PermissionError("private config content")
                ),
                self.assertRaises(PermissionError),
            ):
                apt.prepare_apt(self.root)

    def test_cli_reports_only_count_on_success_and_fails_for_missing_config(self) -> None:
        command = [sys.executable, str(SCRIPTS / "prepare_e2e_apt.py"), "--root", str(self.root)]
        failed = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(failed.returncode, 1)
        self.assertEqual(failed.stdout, "")
        self.write("apt-mirrors.txt", b"http://azure.archive.ubuntu.com/ubuntu\n")
        passed = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(passed.returncode, 0, passed.stderr)
        self.assertEqual(passed.stdout, "Prepared E2E APT configuration: updated_files=1.\n")
        self.assertNotIn("azure", passed.stdout)

    def test_cli_error_does_not_log_config_or_exception_details(self) -> None:
        stdout, stderr = io.StringIO(), io.StringIO()
        with (
            patch.object(apt, "prepare_apt", side_effect=PermissionError("private config content")),
            patch("sys.stdout", stdout),
            patch("sys.stderr", stderr),
        ):
            self.assertEqual(apt.main(["--root", str(self.root)]), 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertNotIn("private config content", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
