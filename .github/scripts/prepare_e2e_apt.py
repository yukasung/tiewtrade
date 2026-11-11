"""Use Ubuntu's archive instead of the failing Azure mirror on disposable E2E runners."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

CONFIG_FILES = ("apt-mirrors.txt", "sources.list", "sources.list.d/ubuntu.sources")
AZURE_URI = re.compile(rb"(?<!\S)https?://azure\.archive\.ubuntu\.com/ubuntu(?=/|[ \t\r\n]|$)")
AZURE_HOST = re.compile(rb"(?<![a-zA-Z0-9.-])azure\.archive\.ubuntu\.com(?![a-zA-Z0-9.-])")
UBUNTU_URI = re.compile(
    rb"(?<!\S)https?://(?:archive|security)\.ubuntu\.com/ubuntu(?=/|[ \t\r\n]|$)"
)


def _prepare_config(original: bytes) -> tuple[bytes, bool]:
    """Prepare file contents without filesystem writes or changes to unrelated bytes."""
    lines = []
    recognized = False
    for line in original.splitlines(keepends=True):
        if line.lstrip().startswith(b"#"):
            lines.append(line)
            continue
        updated = AZURE_URI.sub(b"https://archive.ubuntu.com/ubuntu", line)
        if AZURE_HOST.search(updated):
            raise ValueError("Unsupported Azure mirror URI.")
        recognized = recognized or bool(UBUNTU_URI.search(updated))
        lines.append(updated)
    return b"".join(lines), recognized


def prepare_apt(root: Path) -> int:
    """Validate every known config before writing; preserve bytes outside matched URIs."""
    changes: list[tuple[Path, bytes]] = []
    recognized = False
    for relative in CONFIG_FILES:
        path = root / relative
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError("Unsupported APT configuration layout.")
        if not path.exists():
            continue
        original = path.read_bytes()
        replacement, has_ubuntu_uri = _prepare_config(original)
        recognized = recognized or has_ubuntu_uri
        if replacement != original:
            changes.append((path, replacement))
    if not recognized:
        raise ValueError("No supported Ubuntu APT configuration found.")
    for path, replacement in changes:
        path.write_bytes(replacement)
    return len(changes)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("/etc/apt"))
    args = parser.parse_args(argv)
    try:
        changed = prepare_apt(args.root)
    except (OSError, ValueError):
        sys.stderr.write("E2E APT preparation failed: unsupported layout or unavailable config.\n")
        return 1
    sys.stdout.write(f"Prepared E2E APT configuration: updated_files={changed}.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
