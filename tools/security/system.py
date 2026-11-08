"""Bounded downloads, quiet subprocesses and immutable candidate identification."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import subprocess
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from tools.security.model import Candidate, PolicyError, array, digest, obj, read_json, sha, string


def quiet(args: list[str], cwd: Path, allowed: tuple[int, ...] = (0,), timeout: int = 600) -> bytes:
    # Tool output can contain credentials, including on failed commands. Never echo it.
    with tempfile.TemporaryFile() as output:
        completed = subprocess.run(
            args, cwd=cwd, stdout=output, stderr=subprocess.DEVNULL, timeout=timeout, check=False
        )
        if completed.returncode not in allowed:
            raise PolicyError("COMMAND_FAILED")
        if output.tell() > 128 * 1024 * 1024:
            raise PolicyError("OVERSIZE_COMMAND_OUTPUT")
        output.seek(0)
        return output.read()


def git(root: Path, *args: str) -> str:
    return quiet(["git", "-c", "core.hooksPath=/dev/null", *args], root).decode().strip()


def configuration(root: Path) -> str:
    paths = sorted((root / ".github/security").glob("*"))
    if not paths or any(not p.is_file() or p.is_symlink() for p in paths):
        raise PolicyError("INVALID_POLICY_DIRECTORY")
    # Includes helper sources: different evaluators cannot combine their attestations.
    paths += sorted((root / "tools/security").glob("*.py"))
    paths.append(root / ".github/workflows/security.yml")
    return digest(
        {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    )


def candidate(root: Path) -> Candidate:
    event = obj(read_json(Path(os.environ["GITHUB_EVENT_PATH"])))
    commit = sha(os.environ["GITHUB_SHA"])
    if git(root, "rev-parse", "HEAD") != commit:
        raise PolicyError("CHECKOUT_MISMATCH")
    head = base = commit
    if os.environ["GITHUB_EVENT_NAME"] == "pull_request":
        pr = obj(event.get("pull_request"))
        head, base = sha(obj(pr.get("head")).get("sha")), sha(obj(pr.get("base")).get("sha"))
        if git(root, "show", "-s", "--format=%P", commit).split() != [base, head]:
            raise PolicyError("MERGE_PARENT_MISMATCH")
        number = pr.get("number")
        repository = os.environ["GITHUB_REPOSITORY"]
        if (
            type(number) is not int
            or not repository
            or any(
                c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_./"
                for c in repository
            )
        ):
            raise PolicyError("INVALID_PR_IDENTITY")
        request = urllib.request.Request(
            f"https://api.github.com/repos/{repository}/pulls/{number}",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": "Bearer " + os.environ["GH_TOKEN"],
            },
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            current = obj(json.loads(response.read(2 * 1024 * 1024)))
        if (
            obj(current.get("head")).get("sha"),
            obj(current.get("base")).get("sha"),
            current.get("merge_commit_sha"),
        ) != (head, base, commit):
            raise PolicyError("CANDIDATE_CHANGED")
    return Candidate(
        commit, head, base, os.environ["GITHUB_RUN_ID"], os.environ["GITHUB_RUN_ATTEMPT"]
    )


def _release_asset_request(url: str) -> urllib.request.Request:
    """Resolve only the exact public release asset named by an existing pin."""
    match = re.fullmatch(
        r"https://github\.com/([\w.-]+)/([\w.-]+)/releases/download/([\w.-]+)/([\w.-]+)",
        url,
        flags=re.ASCII,
    )
    if match is None or any(part in {".", ".."} for part in match.groups()):
        raise PolicyError("INVALID_TOOL_PIN")
    owner, repository, tag, filename = match.groups()
    api = f"https://api.github.com/repos/{owner}/{repository}/releases"
    headers = {"User-Agent": "TiewTrade-security", "X-GitHub-Api-Version": "2022-11-28"}
    request = urllib.request.Request(
        f"{api}/tags/{tag}", headers={**headers, "Accept": "application/vnd.github+json"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read(2 * 1024 * 1024 + 1)
    if len(raw) > 2 * 1024 * 1024:
        raise PolicyError("INVALID_TOOL_RELEASE")
    try:
        release = obj(json.loads(raw))
    except (ValueError, UnicodeError):
        raise PolicyError("INVALID_TOOL_RELEASE") from None
    assets = [obj(asset) for asset in array(release.get("assets"))]
    matches = [
        asset
        for asset in assets
        if asset.get("name") == filename and asset.get("browser_download_url") == url
    ]
    if len(matches) != 1 or matches[0].get("state") != "uploaded":
        raise PolicyError("INVALID_TOOL_RELEASE")
    identity = matches[0].get("id")
    if type(identity) is not int or identity <= 0:
        raise PolicyError("INVALID_TOOL_RELEASE")
    # Construct the endpoint: never follow an arbitrary URL from release metadata.
    return urllib.request.Request(
        f"{api}/assets/{identity}", headers={**headers, "Accept": "application/octet-stream"}
    )


def download_verified(url: str, archive: Path, expected: str) -> None:
    """Retry only transient reads; every attempt starts fresh and checks the pin."""
    fallback = False
    for attempt in range(3):
        checksum = hashlib.sha256()
        total = 0
        try:
            request = _release_asset_request(url) if fallback else url
            with (
                urllib.request.urlopen(request, timeout=60) as response,
                archive.open("wb") as stream,
            ):
                if fallback and response.headers.get_content_type() != "application/octet-stream":
                    raise PolicyError("INVALID_TOOL_RELEASE")
                while chunk := response.read(1024 * 1024):
                    total += len(chunk)
                    if total > 4 * 1024 * 1024 * 1024:
                        raise PolicyError("TOOL_DOWNLOAD_TOO_LARGE")
                    checksum.update(chunk)
                    stream.write(chunk)
        except urllib.error.HTTPError as error:
            if error.code not in {408, 429, 500, 502, 503, 504}:
                raise PolicyError("TOOL_HTTP_ERROR") from None
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            pass
        else:
            if checksum.hexdigest() != expected:
                raise PolicyError("TOOL_CHECKSUM_MISMATCH")
            return
        fallback = True
        if attempt < 2:
            time.sleep(attempt + 1)
    raise PolicyError("TOOL_NETWORK_FAILURE")


def install(root: Path, name: str, destination: Path) -> Path:
    manifest = obj(read_json(root / ".github/security/tools.json"))
    tool = obj(obj(manifest.get("tools")).get(name))
    system = f"{platform.system()}-{platform.machine()}"
    asset = obj(obj(tool.get("platforms")).get(system))
    url, expected = string(asset.get("url")), string(asset.get("sha256"))
    if not url.startswith("https://github.com/") or len(expected) != 64:
        raise PolicyError("INVALID_TOOL_PIN")
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = destination / (name + (".tar.gz" if name == "codeql" else ""))
    with tempfile.TemporaryDirectory(dir=destination) as temporary:
        archive = Path(temporary) / "download"
        download_verified(url, archive, expected)
        member = asset.get("member")
        if member is None:
            archive.replace(target)
        else:
            with tarfile.open(archive, "r:gz") as bundle:
                info = bundle.getmember(string(member))
                if not info.isfile() or info.size > 512 * 1024 * 1024:
                    raise PolicyError("INVALID_TOOL_ARCHIVE")
                extracted = bundle.extractfile(info)
                if extracted is None:
                    raise PolicyError("MISSING_TOOL_BINARY")
                with extracted:
                    target.write_bytes(extracted.read())
    target.chmod(0o700)
    return target
