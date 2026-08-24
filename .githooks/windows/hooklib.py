from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Iterable


ZERO_SHA1 = "0" * 40
SUPPORTED_PYTHON = (3, 14)
DEFAULT_PROTECTED_BRANCHES = ("main", "master", "dev")
FORBIDDEN_SUFFIXES = (
    ".gb", ".gbc", ".gba", ".sav", ".srm", ".apk", ".aab", ".jks",
    ".keystore", ".p12", ".pfx", ".mobileprovision", ".love",
)
FORBIDDEN_NAMES = {
    ".env", ".env.local", ".env.development", ".env.production",
    ".env.test", "id_rsa", "id_ed25519",
}
SECRET_PATTERN = re.compile(
    rb"(-----BEGIN ([A-Z0-9 ]+ )?PRIVATE KEY-----|AKIA[0-9A-Z]{16}|"
    rb"github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9_]{30,}|"
    rb"sk-(proj-)?[A-Za-z0-9_-]{20,})"
)
CONFLICT_PATTERN = re.compile(rb"^(<<<<<<< |=======|>>>>>>> )", re.MULTILINE)
SUBJECT_PATTERN = re.compile(
    r"^[a-z][a-z0-9-]*(\([a-z0-9._/-]+\))?!?: [a-z0-9]"
)
VAGUE_SUBJECT_PATTERN = re.compile(
    r"^(wip|tmp|temp|test|fix|fixed|change|changes|update|updates|stuff|misc)[.!]?$",
    re.IGNORECASE,
)


class HookFailure(RuntimeError):
    def __init__(self, message: str, *, reported: bool = False):
        super().__init__(message)
        self.reported = reported


def require_supported_python() -> None:
    if sys.version_info[:2] != SUPPORTED_PYTHON:
        raise HookFailure(
            f"Python {SUPPORTED_PYTHON[0]}.{SUPPORTED_PYTHON[1]} is required; "
            f"got {sys.version_info.major}.{sys.version_info.minor}"
        )


def git(*args: str, input_bytes: bytes | None = None, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(
        ["git", *args],
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode != 0:
        message = result.stderr.decode("utf-8", "replace").strip()
        raise HookFailure(message or f"git {' '.join(args)} failed")
    return result


def protected_branches() -> tuple[str, ...]:
    result = git("config", "--get-all", "guard.protectedBranch", check=False)
    values = tuple(
        line.strip() for line in result.stdout.decode("utf-8", "replace").splitlines() if line.strip()
    )
    return values or DEFAULT_PROTECTED_BRANCHES


def fail(prefix: str, message: str) -> None:
    print(f"{prefix}: {message}", file=sys.stderr)
    raise HookFailure(message, reported=True)


def validate_commit_subject(subject: str) -> None:
    if not subject:
        raise HookFailure("the subject is empty")
    if subject != subject.strip():
        raise HookFailure("the subject does not match the repository style")
    if subject.startswith(("Merge ", "Revert \"", "fixup! ", "squash! ")):
        return
    if len(subject) < 10:
        raise HookFailure("the subject is too short to explain the change")
    if len(subject) > 72:
        raise HookFailure("the subject is longer than 72 characters")
    if VAGUE_SUBJECT_PATTERN.fullmatch(subject):
        raise HookFailure("the subject is too vague")
    if not SUBJECT_PATTERN.match(subject):
        raise HookFailure("the subject does not match the repository style")
    if subject.endswith("."):
        raise HookFailure("do not end the subject with a period")


def first_subject(message_file: Path) -> str:
    for line in message_file.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if stripped and not line.lstrip().startswith("#"):
            return line
    return ""


def staged_paths() -> list[str]:
    output = git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z").stdout
    return [os.fsdecode(item) for item in output.split(b"\0") if item]


def validate_staged_path(path: str, max_bytes: int) -> None:
    lowered = path.lower()
    base = Path(lowered).name
    if lowered.endswith(FORBIDDEN_SUFFIXES):
        raise HookFailure(f"'{path}' is private source data, a credential, or a generated build artifact.")
    if base in FORBIDDEN_NAMES:
        raise HookFailure(f"'{path}' can contain credentials and must not be committed.")
    size_text = git("cat-file", "-s", f":{path}").stdout.decode("ascii", "strict").strip()
    if int(size_text) > max_bytes:
        raise HookFailure(
            f"'{path}' is {size_text} bytes; the local limit is {max_bytes} bytes. "
            "Use Git LFS or an artifact store."
        )
    content = git("show", f":{path}", check=False).stdout
    if b"\0" not in content[:8192] and CONFLICT_PATTERN.search(content):
        raise HookFailure(f"'{path}' contains unresolved merge-conflict markers.")


def added_lines() -> bytes:
    diff = git("diff", "--cached", "--no-ext-diff", "--unified=0", "--", ".").stdout
    return b"\n".join(
        line[1:]
        for line in diff.splitlines()
        if line.startswith(b"+") and len(line) > 1 and line[1:2] != b"+"
    )


def run_pre_commit() -> None:
    branch_result = git("symbolic-ref", "--quiet", "--short", "HEAD", check=False)
    branch = branch_result.stdout.decode("utf-8", "replace").strip()
    if branch and branch in protected_branches():
        fail("pre-commit", f"direct commits to '{branch}' are blocked. Create a focused branch first.")
    check_result = git("diff", "--cached", "--check", check=False)
    if check_result.returncode != 0:
        sys.stderr.buffer.write(check_result.stdout + check_result.stderr)
        fail("pre-commit", "staged changes contain whitespace errors or conflict markers.")
    paths = staged_paths()
    if not paths:
        return
    max_result = git("config", "--get", "guard.maxFileBytes", check=False)
    max_text = max_result.stdout.decode("ascii", "replace").strip() or "10485760"
    if not max_text.isdigit():
        fail("pre-commit", "guard.maxFileBytes must be an integer.")
    for path in paths:
        validate_staged_path(path, int(max_text))
    if SECRET_PATTERN.search(added_lines()):
        fail("pre-commit", "staged additions look like a private key or access token.")
    print("pre-commit: safeguards passed")


def run_commit_msg(message_file: Path) -> None:
    try:
        validate_commit_subject(first_subject(message_file))
    except HookFailure as error:
        print(f"commit-msg: {error}", file=sys.stderr)
        print("Use: type(scope): imperative summary", file=sys.stderr)
        print("Example: android(input): preserve Touch focus after resume", file=sys.stderr)
        error.reported = True
        raise
    print("commit-msg: message passed")


def parse_push_lines(lines: Iterable[str]) -> list[tuple[str, str, str, str]]:
    parsed = []
    for line in lines:
        fields = line.split()
        if not fields:
            continue
        if len(fields) != 4:
            raise HookFailure("pre-push input must contain four fields")
        parsed.append(tuple(fields))
    return parsed


def run_pre_push(remote_name: str, lines: Iterable[str]) -> None:
    if remote_name == "upstream":
        fail("pre-push", "pushes to upstream are blocked. Push a branch to origin and open a pull request.")
    for local_ref, local_sha, _remote_ref, remote_sha in parse_push_lines(lines):
        if local_sha == ZERO_SHA1:
            continue
        branch = local_ref.removeprefix("refs/heads/")
        if branch in protected_branches():
            upstream_ref = f"refs/remotes/upstream/{branch}"
            found = git("show-ref", "--verify", "--quiet", upstream_ref, check=False).returncode == 0
            exact = found and local_sha == git("rev-parse", upstream_ref).stdout.decode("ascii").strip()
            if not exact:
                fail("pre-push", f"direct development pushes to '{branch}' are blocked.")
        if remote_sha != ZERO_SHA1:
            result = git("diff", "--check", f"{remote_sha}..{local_sha}", check=False)
            if result.returncode != 0:
                sys.stderr.buffer.write(result.stdout + result.stderr)
                raise HookFailure("pre-push diff check failed")
    command = git("config", "--get", "guard.prePushCommand", check=False).stdout.decode(
        "utf-8", "replace"
    ).rstrip("\r\n")
    if command:
        fail(
            "pre-push",
            "guard.prePushCommand is configured, but shell commands are not supported by the native Windows hook.",
        )
    print("pre-push: safeguards passed")
