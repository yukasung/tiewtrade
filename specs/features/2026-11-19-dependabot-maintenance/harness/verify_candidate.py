"""Verify pinned Stage B bytes; independent of npm cache/lifecycle behavior."""

import hashlib
from pathlib import Path

ARTIFACT_SHA256 = "9be37a4009537bea9b41adfa375adc7881cd4080e6fbe528a54772c3cd92615d"
PARSER_SHA256 = "2e76e1f01b355131969a1fe4efeea3262b48a2e337f9b81b737ea52f1b5beb9d"


class CandidateRejected(ValueError):
    """Required candidate evidence is missing or differs from reviewed bytes."""


def verify_candidate(
    frontend: Path,
    *,
    artifact_sha256: str = ARTIFACT_SHA256,
    parser_sha256: str = PARSER_SHA256,
    artifact_relative_path: str = "vendor/picomatch-4.0.7-lp03.tgz",
) -> None:
    """Reject missing, linked or altered vendor/installed files before acceptance.

    This is byte verification only: it does not certify npm rejection, library-wide
    ReDoS safety, matching compatibility, source-policy approval or other packages.
    """
    if artifact_relative_path not in {
        "vendor/picomatch-4.0.7-lp03.tgz",
        "vendor/picomatch-4.0.7-lp04.tgz",
    }:
        raise CandidateRejected("unsupported candidate artifact path")
    frontend = frontend.resolve()
    files = (
        (artifact_relative_path, artifact_sha256),
        ("node_modules/picomatch/lib/parse.js", parser_sha256),
    )
    for relative, expected in files:
        path = frontend / relative
        if any(part.is_symlink() for part in (path, *path.parents)):
            raise CandidateRejected(f"linked candidate file: {relative}")
        try:
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as error:
            raise CandidateRejected(f"unreadable candidate file: {relative}") from error
        if actual != expected:
            raise CandidateRejected(f"candidate hash mismatch: {relative}")
