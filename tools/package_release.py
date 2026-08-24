#!/usr/bin/env python3
"""Build deterministic private test artifacts or a gated release package."""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import NamedTuple
import unicodedata
from urllib.parse import unquote, urlsplit, urlunsplit
import zipfile


PINNED_ENGINES = {
    "44f4680b24823629489ed5a2adad648d0dceb640",
    "06e06e305bbcefe97c216a31bb25265ffb5e6b18",
    "70d7b6383e2c005857013dc897fd096886b08f0b",
    "478e3bf8ebf7646edfda88320c6472cf32db2e67",
    "116a6ba450dd65f25c9be150952fc3c27be904c0",
}
GAME_ACCEPTANCE_GATES = {
    "red_runtime_acceptance": "red",
    "blue_runtime_acceptance": "blue",
    "yellow_runtime_acceptance": "yellow",
}
GAME_ACCEPTANCE_LOCATORS = {
    game: f"docs/release-matrix/game-acceptance/{game}.json"
    for game in GAME_ACCEPTANCE_GATES.values()
}
GAME_RESULT_FIELDS = {
    "schema",
    "game",
    "status",
    "release_ready",
    "required_cells",
    "passed_cells",
    "blockers",
    "runtime_source_commit",
    "runtime_source_tree",
    "runtime_content_sha256",
    "runtime_file_count",
    "engine_commit",
    "source_date_epoch",
    "package_sha256",
    "matrix_manifest_sha256",
}
RELEASE_MATRIX_GAME_CELL_COUNTS = {
    "red": 5940,
    "blue": 5940,
    "yellow": 5940,
}
RELEASE_MATRIX_CELL_COUNT = 17820
REQUIRED_RELEASE_GATES = (
    "companion_hosts",
    "corrected_feature_parity",
    "asset_rights",
    "platform_evidence",
    "visual_acceptance",
    "performance_and_leaks",
    "reproducible_packaging",
    "uninstall_integrity",
    "engine_reaudit",
    "community_review",
    *GAME_ACCEPTANCE_GATES,
)
REQUIRED_PRERELEASE_GATES = {
    "alpha": (
        "asset_rights",
        "automated_tests",
        "companion_contracts",
        "released_hosts",
        "migration_safety",
        "package_reproducibility",
        "source_integrity",
        "known_limitations",
        *GAME_ACCEPTANCE_GATES,
    ),
    "beta": (
        "asset_rights",
        "automated_tests",
        "companion_contracts",
        "released_hosts",
        "corrected_feature_parity",
        "migration_safety",
        "package_reproducibility",
        "source_integrity",
        "visual_acceptance",
        "known_limitations",
        *GAME_ACCEPTANCE_GATES,
    ),
    "rc": REQUIRED_RELEASE_GATES,
}
ROOT_FILES = (
    "manifest.json",
    "main.lua",
    "transform_birds.lua",
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
    "README.md",
    "CHANGELOG.md",
    "docs/legacy-panorama-inventory.json",
    "docs/legacy-sky-inventory.json",
)
RUNTIME_DIRS = ("src", "assets")
ASSET_FILES = (
    "assets/legacy/audio/ambient/amb-cave.mp3",
    "assets/legacy/audio/ambient/amb-forest.mp3",
    "assets/legacy/audio/ambient/amb-night.mp3",
    "assets/legacy/audio/ambient/amb-rain.mp3",
    "assets/legacy/audio/ambient/amb-route.mp3",
    "assets/legacy/audio/ambient/amb-town.mp3",
    "assets/legacy/audio/ambient/amb-water.mp3",
    "assets/legacy/audio/sfx/sfx-cavestep.mp3",
    "assets/legacy/audio/sfx/sfx-door.mp3",
    "assets/legacy/audio/sfx/sfx-grass1.mp3",
    "assets/legacy/audio/sfx/sfx-grass2.mp3",
    "assets/legacy/audio/sfx/sfx-shopdoor.mp3",
    "assets/legacy/audio/sfx/sfx-woodstep.mp3",
    "assets/legacy/horizons/backdrop.png",
    "assets/legacy/horizons/backdrop-2048.png",
    "assets/legacy/horizons/backdrop-1024.png",
    "assets/legacy/horizons/backdrop2.png",
    "assets/legacy/horizons/backdrop2-2048.png",
    "assets/legacy/horizons/backdrop2-1024.png",
    "assets/legacy/horizons/backdrop3.png",
    "assets/legacy/horizons/backdrop3-2048.png",
    "assets/legacy/horizons/backdrop3-1024.png",
    "assets/legacy/horizons/backdrop4.png",
    "assets/legacy/horizons/backdrop4-2048.png",
    "assets/legacy/horizons/backdrop4-1024.png",
    "assets/legacy/posters/posters-pokecenter.png",
    "assets/legacy/posters/posters-pokemart.png",
    "assets/legacy/posters/posters.png",
    "assets/legacy/sky/clouds-1.png",
    "assets/legacy/sky/clouds-2.png",
    "assets/legacy/sky/clouds-3.png",
)
HEX_64 = re.compile(r"^[0-9a-f]{64}$")
FINGERPRINT = re.compile(r"^[0-9A-F]{40,64}$")
UTC_TIMESTAMP = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"
)
EVIDENCE_KIND = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
EVIDENCE_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+~-]{0,127}$")
HTTPS_HOST = re.compile(
    r"^(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)*"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$"
)
CREDENTIAL_LIKE = re.compile(
    r"(?:"
    r"gh[pousr]_[A-Za-z0-9]{20,}"
    r"|github_pat_[A-Za-z0-9_]{20,}"
    r"|sk-(?:proj-)?[A-Za-z0-9_-]{20,}"
    r"|AKIA[0-9A-Z]{16}"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----"
    r"|(?:password|passwd|pwd|api[_-]?key|secret|token)"
    r"\s*[:=]\s*[^\s/&?#]+"
    r")",
    re.IGNORECASE,
)
OBJECT_ID = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
ARTIFACT_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$")
ARTIFACT_SUFFIXES = (
    ".modpkg",
    ".zip",
    "-SHA256SUMS.txt",
    "-attestation.json",
)
MAX_WINDOWS_COMPONENT_UNITS = 255
WINDOWS_DEVICE_SUFFIXES = (
    *(str(number) for number in range(1, 10)),
    "\N{SUPERSCRIPT ONE}",
    "\N{SUPERSCRIPT TWO}",
    "\N{SUPERSCRIPT THREE}",
)
WINDOWS_DEVICE_NAMES = {
    "AUX",
    "CON",
    "CONIN$",
    "CONOUT$",
    "NUL",
    "PRN",
    *(f"COM{suffix}" for suffix in WINDOWS_DEVICE_SUFFIXES),
    *(f"LPT{suffix}" for suffix in WINDOWS_DEVICE_SUFFIXES),
}
PRIVATE_EVIDENCE_COMPONENTS = {
    "baserom",
    "baseroms",
    "cache",
    "caches",
    "private-fixtures",
    "rom",
    "roms",
    "save",
    "saves",
    "pokemon roms",
    "pokemon saves",
}
PRIVATE_INPUT_SUFFIXES = {
    ".cache",
    ".gb",
    ".gba",
    ".gbc",
    ".rom",
    ".sav",
    ".srm",
}


class GitEntry(NamedTuple):
    path: str
    mode: str
    object_id: str


def run(*args: str, cwd: Path, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        args,
        cwd=cwd,
        env=env,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return result.stdout.strip()


def run_bytes(*args: str, cwd: Path) -> bytes:
    result = subprocess.run(
        args,
        cwd=cwd,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def reject_json_constant(value: str) -> object:
    raise ValueError(f"non-standard JSON constant: {value}")


def strict_json_loads(value: str) -> object:
    return json.loads(
        value,
        object_pairs_hook=reject_duplicate_keys,
        parse_constant=reject_json_constant,
    )


def strict_json_bytes(value: bytes) -> object:
    return strict_json_loads(value.decode("utf-8"))


def strict_json_file(path: Path) -> object:
    try:
        return strict_json_loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise RuntimeError(f"invalid or duplicate JSON in {path.name}") from error


def validate_release_matrix_manifest(value: object) -> dict[str, object]:
    MatrixModelError, validate_manifest = load_repository_release_matrix_validator()
    try:
        checked = validate_manifest(value)
    except MatrixModelError as error:
        raise RuntimeError(
            "release blocked: release-matrix manifest is invalid"
        ) from error
    if not isinstance(checked, dict):
        checked = dict(checked)
    return checked


def load_repository_release_matrix_validator() -> tuple[type[Exception], object]:
    repository = Path(__file__).resolve().parents[1]
    expected = repository / "tools" / "release_matrix" / "model.py"
    try:
        model_path = expected.resolve(strict=True)
    except OSError as error:
        raise RuntimeError(
            "release blocked: canonical release-matrix validator is unavailable"
        ) from error
    if model_path != expected or not model_path.is_file():
        raise RuntimeError(
            "release blocked: canonical release-matrix validator is unavailable"
        )
    spec = importlib.util.spec_from_file_location(
        "_kfp_repository_release_matrix_model",
        model_path,
    )
    if (
        spec is None
        or spec.loader is None
        or spec.origin is None
        or Path(spec.origin).resolve() != model_path
    ):
        raise RuntimeError(
            "release blocked: canonical release-matrix validator is unavailable"
        )
    module = importlib.util.module_from_spec(spec)
    module_name = spec.name
    previous = sys.modules.get(module_name)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as error:
        raise RuntimeError(
            "release blocked: canonical release-matrix validator is unavailable"
        ) from error
    finally:
        if previous is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = previous
    origin = getattr(module, "__file__", None)
    MatrixModelError = getattr(module, "MatrixModelError", None)
    validate_manifest = getattr(module, "validate_manifest", None)
    if (
        not isinstance(origin, str)
        or Path(origin).resolve() != model_path
        or not isinstance(MatrixModelError, type)
        or not issubclass(MatrixModelError, Exception)
        or not callable(validate_manifest)
    ):
        raise RuntimeError(
            "release blocked: canonical release-matrix validator is unavailable"
        )
    return MatrixModelError, validate_manifest


def load_manifest(path: Path) -> dict[str, object]:
    manifest = strict_json_file(path)
    return validate_manifest(manifest)


def load_manifest_bytes(value: bytes, name: str = "manifest.json") -> dict[str, object]:
    try:
        manifest = strict_json_bytes(value)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise RuntimeError(f"invalid or duplicate JSON in {name}") from error
    return validate_manifest(manifest)


def validate_manifest(manifest: object) -> dict[str, object]:
    if not isinstance(manifest, dict):
        raise RuntimeError("manifest root must be a JSON object")
    for field in ("id", "version"):
        value = manifest.get(field)
        if (
            not isinstance(value, str)
            or ARTIFACT_COMPONENT.fullmatch(value) is None
        ):
            raise RuntimeError(
                f"manifest {field} must be a portable artifact component"
            )
    stem = f"{manifest['id']}-{manifest['version']}"
    if any(
        len((stem + suffix).encode("utf-16-le")) // 2
        > MAX_WINDOWS_COMPONENT_UNITS
        for suffix in ARTIFACT_SUFFIXES
    ):
        raise RuntimeError("manifest id and version produce an overlong artifact name")
    return manifest


def allowed_runtime_path(relative: str) -> bool:
    if relative in ROOT_FILES or relative in ASSET_FILES:
        return True
    return relative.startswith("src/") and relative.endswith(".lua")


def validate_relative_path(relative: str) -> None:
    parts = relative.split("/")
    if (
        not relative
        or relative.startswith("/")
        or "\\" in relative
        or unicodedata.normalize("NFC", relative) != relative
        or any(ord(character) < 32 or ord(character) == 127 for character in relative)
        or any(
            part in ("", ".", "..", "__pycache__")
            or part.startswith(".")
            or len(part.encode("utf-16-le")) // 2 > MAX_WINDOWS_COMPONENT_UNITS
            for part in parts
        )
        or any(
            any(character in '<>:"|?*' for character in part)
            or part.endswith((" ", "."))
            for part in parts
        )
        or any(
            part.split(".", 1)[0].rstrip(" .").upper()
            in WINDOWS_DEVICE_NAMES
            for part in parts
        )
    ):
        raise RuntimeError(f"unsafe package path: {relative!r}")


def validate_runtime_entries(entries: list[GitEntry]) -> list[GitEntry]:
    seen: set[str] = set()
    portable_seen: set[str] = set()
    invalid: list[str] = []
    for entry in entries:
        validate_relative_path(entry.path)
        portable = unicodedata.normalize("NFC", entry.path).casefold()
        if entry.path in seen or portable in portable_seen:
            raise RuntimeError(f"duplicate package path: {entry.path}")
        seen.add(entry.path)
        portable_seen.add(portable)
        if entry.mode not in ("100644", "100755"):
            raise RuntimeError(
                f"package path is not a regular Git blob: {entry.path} ({entry.mode})"
            )
        if OBJECT_ID.fullmatch(entry.object_id) is None:
            raise RuntimeError(f"package path has an invalid Git object: {entry.path}")
        if not allowed_runtime_path(entry.path):
            invalid.append(entry.path)
    if invalid:
        raise RuntimeError(
            "runtime tree contains non-allowlisted files: " + ", ".join(sorted(invalid))
        )

    required = set(ROOT_FILES + ASSET_FILES)
    missing = sorted(required.difference(seen))
    if missing:
        raise RuntimeError("required package files are missing: " + ", ".join(missing))
    if not any(path.startswith("src/") for path in seen):
        raise RuntimeError("required runtime source is missing")
    return sorted(entries, key=lambda entry: entry.path)


def parse_tree_entries(raw: bytes) -> list[GitEntry]:
    entries: list[GitEntry] = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        try:
            metadata, raw_path = record.split(b"\t", 1)
            mode, kind, object_id = metadata.decode("ascii").split(" ")
            relative = raw_path.decode("utf-8")
        except (UnicodeDecodeError, ValueError) as error:
            raise RuntimeError("invalid Git tree entry in runtime source") from error
        if kind != "blob":
            raise RuntimeError(
                f"package path is not a Git blob: {relative} ({kind})"
            )
        entries.append(GitEntry(relative, mode, object_id))
    return validate_runtime_entries(entries)


def listed_runtime_entries_from_ref(source: Path, ref: str) -> list[GitEntry]:
    raw = run_bytes(
        "git",
        "ls-tree",
        "-rz",
        "--full-tree",
        ref,
        "--",
        *ROOT_FILES,
        *RUNTIME_DIRS,
        cwd=source,
    )
    return parse_tree_entries(raw)


def parse_index_entries(raw: bytes) -> list[GitEntry]:
    entries: list[GitEntry] = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        try:
            metadata, raw_path = record.split(b"\t", 1)
            mode, object_id, stage = metadata.decode("ascii").split(" ")
            relative = raw_path.decode("utf-8")
        except (UnicodeDecodeError, ValueError) as error:
            raise RuntimeError("invalid Git index entry in runtime source") from error
        if stage != "0":
            raise RuntimeError(f"unmerged runtime path is not packageable: {relative}")
        entries.append(GitEntry(relative, mode, object_id))
    return validate_runtime_entries(entries)


def listed_runtime_entries_from_worktree(source: Path) -> list[GitEntry]:
    untracked_raw = run_bytes(
        "git",
        "ls-files",
        "-z",
        "--others",
        "--",
        *ROOT_FILES,
        *RUNTIME_DIRS,
        cwd=source,
    )
    try:
        untracked = [
            item for item in untracked_raw.decode("utf-8").split("\0") if item
        ]
    except UnicodeDecodeError as error:
        raise RuntimeError("untracked runtime path is not valid UTF-8") from error
    for relative in untracked:
        validate_relative_path(relative)
    if untracked:
        raise RuntimeError(
            "untracked runtime files are not packageable: "
            + ", ".join(sorted(untracked))
        )

    raw = run_bytes(
        "git",
        "ls-files",
        "--stage",
        "-z",
        "--",
        *ROOT_FILES,
        *RUNTIME_DIRS,
        cwd=source,
    )
    return parse_index_entries(raw)


def listed_runtime_files(source: Path) -> list[str]:
    return [entry.path for entry in listed_runtime_entries_from_worktree(source)]


def path_has_link(path: Path, root: Path) -> bool:
    current = root
    relative = path.relative_to(root)
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            return True
        is_junction = getattr(current, "is_junction", None)
        if is_junction is not None and is_junction():
            return True
    return False


def load_worktree_manifest(source: Path) -> dict[str, object]:
    source = source.resolve()
    path = source / "manifest.json"
    if (
        not path.is_file()
        or path_has_link(path, source)
        or not inside(path.resolve(), source)
    ):
        raise RuntimeError("required package file is missing: manifest.json")
    return load_manifest(path)


def safe_staging_path(staging: Path, relative: str) -> Path:
    destination = staging.joinpath(*relative.split("/")).resolve()
    if not inside(destination, staging.resolve()):
        raise RuntimeError(f"package path escapes staging: {relative}")
    return destination


def copy_runtime(source: Path, staging: Path) -> list[str]:
    source = source.resolve()
    entries = listed_runtime_entries_from_worktree(source)
    copied: list[str] = []
    for entry in entries:
        relative = entry.path
        src = source.joinpath(*relative.split("/"))
        if (
            not src.is_file()
            or path_has_link(src, source)
            or not inside(src.resolve(), source)
        ):
            raise RuntimeError(f"required package file is missing: {relative}")
        dst = safe_staging_path(staging, relative)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        copied.append(relative)
    return sorted(copied)


def copy_runtime_from_ref(source: Path, ref: str, staging: Path) -> list[str]:
    entries = listed_runtime_entries_from_ref(source, ref)
    copied: list[str] = []
    for entry in entries:
        destination = safe_staging_path(staging, entry.path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(
            run_bytes("git", "cat-file", "blob", entry.object_id, cwd=source)
        )
        copied.append(entry.path)
    return sorted(copied)


def copy_runtime_from_tag(
    source: Path, tag: str, staging: Path, temporary: Path
) -> list[str]:
    del temporary
    return copy_runtime_from_ref(source, tag, staging)


def copy_engine_from_commit(
    engine: Path, commit: str, staging: Path, temporary: Path
) -> None:
    archive_path = temporary / "engine-source.zip"
    run(
        "git",
        "-c",
        "core.autocrlf=false",
        "-c",
        "core.eol=lf",
        "archive",
        "--format=zip",
        f"--output={archive_path}",
        commit,
        cwd=engine,
    )
    staging.mkdir()
    seen: set[str] = set()
    with zipfile.ZipFile(archive_path, "r") as archive:
        for entry in sorted(archive.infolist(), key=lambda item: item.filename):
            if entry.is_dir():
                continue
            relative = entry.filename.replace("\\", "/")
            parts = relative.split("/")
            mode = (entry.external_attr >> 16) & 0o170000
            if (
                not relative
                or relative in seen
                or relative.startswith("/")
                or any(part in ("", ".", "..") for part in parts)
                or mode == 0o120000
            ):
                raise RuntimeError("engine archive contains an unsafe path")
            destination = staging.joinpath(*parts).resolve()
            if not inside(destination, staging.resolve()):
                raise RuntimeError("engine archive escapes staging")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(archive.read(entry))
            seen.add(relative)
    for required in (
        "tools/modkit.py",
        "tools/rom_manifest.json",
        "src/mods/Loader.lua",
    ):
        if required not in seen:
            raise RuntimeError("pinned engine archive is incomplete: " + required)


def deterministic_zip(source: Path, output: Path, files: list[str]) -> None:
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for relative in sorted(files):
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, (source / relative).read_bytes(), compresslevel=9)


def verify_modpkg_runtime(modpkg: Path, staging: Path, files: list[str]) -> None:
    expected_runtime = set(files)
    expected_entries = expected_runtime | {".modkit/pack.json"}
    with zipfile.ZipFile(modpkg, "r") as archive:
        names = [entry.filename for entry in archive.infolist()]
        if len(names) != len(set(names)):
            raise RuntimeError("modpkg contains duplicate package paths")
        actual_entries = set(names)
        if actual_entries != expected_entries:
            missing = sorted(expected_entries.difference(actual_entries))
            unexpected = sorted(actual_entries.difference(expected_entries))
            details = []
            if missing:
                details.append("missing: " + ", ".join(missing))
            if unexpected:
                details.append("unexpected: " + ", ".join(unexpected))
            raise RuntimeError("modpkg path set differs from staging (" + "; ".join(details) + ")")
        for relative in sorted(expected_runtime):
            staged = staging.joinpath(*relative.split("/")).read_bytes()
            if archive.read(relative) != staged:
                raise RuntimeError(
                    f"modpkg content differs from staging: {relative}"
                )


def runtime_content_fingerprint(source: Path, files: list[str]) -> dict[str, object]:
    return runtime_bytes_fingerprint(
        [
            (relative, source.joinpath(*relative.split("/")).read_bytes())
            for relative in files
        ]
    )


def runtime_content_fingerprint_from_ref(
    source: Path, ref: str
) -> dict[str, object]:
    return runtime_bytes_fingerprint([
        (
            entry.path,
            run_bytes("git", "cat-file", "blob", entry.object_id, cwd=source),
        )
        for entry in listed_runtime_entries_from_ref(source, ref)
    ])


def runtime_bytes_fingerprint(
    items: list[tuple[str, bytes]],
) -> dict[str, object]:
    digest = hashlib.sha256()
    digest.update(b"kfp-runtime-content-v1\0")
    seen: set[str] = set()
    for relative, content in sorted(items):
        validate_relative_path(relative)
        if relative in seen:
            raise RuntimeError(f"duplicate runtime content path: {relative}")
        seen.add(relative)
        path_bytes = relative.encode("utf-8")
        digest.update(len(path_bytes).to_bytes(8, "big"))
        digest.update(path_bytes)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return {
        "algorithm": "sha256-framed-path-content-v1",
        "file_count": len(items),
        "sha256": digest.hexdigest(),
    }


def select_source_mode(
    *, release: bool, allow_dirty: bool, git_status_dirty: bool
) -> tuple[str, bool]:
    if release and allow_dirty:
        raise RuntimeError("a release build cannot use --allow-dirty")
    if git_status_dirty and not allow_dirty:
        raise RuntimeError(
            "source tree is dirty; use --allow-dirty only for a private test build"
        )
    if allow_dirty:
        return "worktree", True
    if release:
        return "signed-tag", False
    return "git-commit", False


def resolve_epoch(value: int | None, environment: dict[str, str]) -> int:
    if value is None:
        raw_epoch = environment.get("SOURCE_DATE_EPOCH")
        if raw_epoch is None:
            raise RuntimeError("set SOURCE_DATE_EPOCH or pass --epoch")
        try:
            value = int(raw_epoch)
        except ValueError as error:
            raise RuntimeError("SOURCE_DATE_EPOCH must be an integer") from error
    if value < 0:
        raise RuntimeError("epoch must be nonnegative")
    return value


def inside(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def valid_evidence_components(value: str) -> bool:
    components = value.split("/")
    return (
        bool(components)
        and all(
            EVIDENCE_COMPONENT.fullmatch(component) is not None
            and component.rstrip(" .") == component
            and component.split(".", 1)[0].upper() not in WINDOWS_DEVICE_NAMES
            and component.casefold() not in PRIVATE_EVIDENCE_COMPONENTS
            and Path(component).suffix.casefold() not in PRIVATE_INPUT_SUFFIXES
            for component in components
        )
    )


def valid_evidence_locator(value: object) -> bool:
    if (
        not isinstance(value, str)
        or not (1 <= len(value) <= 512)
        or value.strip() != value
        or unicodedata.normalize("NFC", value) != value
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        return False
    decoded = value
    for _ in range(2):
        expanded = unquote(decoded)
        if expanded == decoded:
            break
        decoded = expanded
    if (
        decoded != value
        or "\\" in decoded
        or re.search(r"(?:^|[^A-Za-z0-9])[A-Za-z]:/", decoded) is not None
        or "file:" in decoded.casefold()
        or CREDENTIAL_LIKE.search(decoded) is not None
    ):
        return False
    for prefix in ("evidence://", "private-evidence://", "docs/"):
        if decoded.startswith(prefix):
            return valid_evidence_components(decoded[len(prefix):])
    try:
        parsed = urlsplit(decoded)
        port = parsed.port
    except ValueError:
        return False
    host = parsed.hostname
    expected_netloc = (
        host if port is None else f"{host}:{port}"
    ) if isinstance(host, str) else None
    return (
        parsed.scheme == "https"
        and isinstance(host, str)
        and HTTPS_HOST.fullmatch(host) is not None
        and parsed.netloc == expected_netloc
        and parsed.username is None
        and parsed.password is None
        and port in (None, 443)
        and not parsed.query
        and not parsed.fragment
        and parsed.path.startswith("/")
        and valid_evidence_components(parsed.path[1:])
        and urlunsplit(parsed) == decoded
    )


def valid_utc_timestamp(value: object) -> bool:
    if not isinstance(value, str) or UTC_TIMESTAMP.fullmatch(value) is None:
        return False
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return False
    return True


def valid_evidence_fields(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    kind, locator, digest = value["kind"], value["locator"], value["sha256"]
    return (
        isinstance(kind, str)
        and EVIDENCE_KIND.fullmatch(kind) is not None
        and valid_evidence_locator(locator)
        and isinstance(digest, str)
        and HEX_64.fullmatch(digest) is not None
    )


def valid_evidence(value: object) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == {"kind", "locator", "sha256"}
        and valid_evidence_fields(value)
    )


def valid_game_acceptance_evidence_shape(value: object) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == {"kind", "locator", "sha256", "game", "result"}
        and valid_evidence_fields(value)
        and value.get("kind") == "release_matrix_game_acceptance"
    )


def game_result_bytes(value: object) -> bytes | None:
    try:
        return (json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ) + "\n").encode("utf-8")
    except (TypeError, ValueError):
        return None


def game_result_sha256(value: object) -> str | None:
    encoded = game_result_bytes(value)
    return sha256_bytes(encoded) if encoded is not None else None


def valid_game_acceptance_evidence(value: object, expected_game: str) -> bool:
    if not valid_game_acceptance_evidence_shape(value) or not isinstance(value, dict):
        return False
    result = value.get("result")
    if not isinstance(result, dict) or set(result) != GAME_RESULT_FIELDS:
        return False
    required_cells = result.get("required_cells")
    passed_cells = result.get("passed_cells")
    blockers = result.get("blockers")
    return (
        value.get("game") == expected_game
        and value.get("locator") == GAME_ACCEPTANCE_LOCATORS[expected_game]
        and type(result.get("schema")) is int
        and result.get("schema") == 1
        and result.get("game") == expected_game
        and result.get("status") == "PASS"
        and result.get("release_ready") is True
        and type(required_cells) is int
        and required_cells > 0
        and type(passed_cells) is int
        and passed_cells == required_cells
        and blockers == []
        and isinstance(result.get("runtime_source_commit"), str)
        and OBJECT_ID.fullmatch(result["runtime_source_commit"]) is not None
        and isinstance(result.get("runtime_source_tree"), str)
        and OBJECT_ID.fullmatch(result["runtime_source_tree"]) is not None
        and isinstance(result.get("runtime_content_sha256"), str)
        and HEX_64.fullmatch(result["runtime_content_sha256"]) is not None
        and type(result.get("runtime_file_count")) is int
        and result["runtime_file_count"] > 0
        and isinstance(result.get("engine_commit"), str)
        and result["engine_commit"] in PINNED_ENGINES
        and type(result.get("source_date_epoch")) is int
        and result["source_date_epoch"] >= 0
        and isinstance(result.get("package_sha256"), str)
        and HEX_64.fullmatch(result["package_sha256"]) is not None
        and isinstance(result.get("matrix_manifest_sha256"), str)
        and HEX_64.fullmatch(result["matrix_manifest_sha256"]) is not None
        and game_result_sha256(result) == value.get("sha256")
    )


def release_channel(version: str) -> str:
    match = re.search(r"-(alpha|beta|rc)\.[0-9]+$", version)
    if match:
        return match.group(1)
    if "-" in version:
        raise RuntimeError("release blocked: unsupported prerelease channel")
    return "stable"


def release_policy(version: str) -> tuple[str, str, tuple[str, ...]]:
    channel = release_channel(version)
    if channel == "stable":
        return channel, "docs/release-gates.json", REQUIRED_RELEASE_GATES
    return channel, "docs/prerelease-gates.json", REQUIRED_PRERELEASE_GATES[channel]


def validate_release_records(
    rights_record: object,
    record: object,
    version: str,
    expected_tag: str,
    channel: str | None = None,
    required_gates: tuple[str, ...] | None = None,
    expected_engine_commit: str | None = None,
    expected_epoch: int | None = None,
    game_documents: dict[str, bytes] | None = None,
    matrix_manifest_bytes: bytes | None = None,
) -> dict[str, object]:
    selected_channel, _, selected_gates = release_policy(version)
    channel = channel or selected_channel
    required_gates = required_gates or selected_gates
    if (
        not isinstance(rights_record, dict)
        or type(rights_record.get("schema")) is not int
        or rights_record.get("schema") != 1
    ):
        raise RuntimeError("release blocked: rights approval schema is invalid")
    if rights_record.get("approved") is not True:
        raise RuntimeError(
            "release blocked: asset redistribution approval is not affirmative"
        )
    evidence_digest = rights_record.get("evidence_sha256")
    if not isinstance(evidence_digest, str) or HEX_64.fullmatch(evidence_digest) is None:
        raise RuntimeError("release blocked: rights evidence hash is invalid")
    if not valid_evidence(rights_record.get("approval_record")):
        raise RuntimeError("release blocked: rights approval record is invalid")

    if (
        not isinstance(record, dict)
        or type(record.get("schema")) is not int
        or record.get("schema") != 1
    ):
        raise RuntimeError("release blocked: release gate ledger schema is invalid")
    if record.get("approved") is not True:
        raise RuntimeError("release blocked: release gate ledger is not approved")
    if record.get("release_version") != version:
        raise RuntimeError("release blocked: gate ledger version does not match manifest")
    if record.get("channel", "stable") != channel:
        raise RuntimeError("release blocked: gate ledger channel does not match manifest")
    approved_by, approved_at = record.get("approved_by"), record.get("approved_at")
    if not isinstance(approved_by, str) or not (1 <= len(approved_by) <= 128):
        raise RuntimeError("release blocked: gate approval identity is invalid")
    if not valid_utc_timestamp(approved_at):
        raise RuntimeError("release blocked: gate approval timestamp is invalid")
    if record.get("tag") != expected_tag:
        raise RuntimeError("release blocked: gate ledger tag does not match manifest")

    gates = record.get("gates")
    if not isinstance(gates, dict) or set(gates) != set(required_gates):
        raise RuntimeError("release blocked: gate ledger set is invalid")
    incomplete = []
    for name in required_gates:
        gate = gates[name]
        evidence = gate.get("evidence") if isinstance(gate, dict) else None
        evidence_is_valid = (
            isinstance(evidence, list)
            and bool(evidence)
            and all(
                valid_game_acceptance_evidence_shape(item)
                if name in GAME_ACCEPTANCE_GATES
                else valid_evidence(item)
                for item in evidence
            )
        )
        if (
            not isinstance(gate, dict)
            or set(gate) != {"passed", "evidence"}
            or gate.get("passed") is not True
            or not evidence_is_valid
        ):
            incomplete.append(name)
    if incomplete:
        raise RuntimeError(
            "release blocked: incomplete gates: " + ", ".join(incomplete)
        )
    invalid_game_evidence = []
    package_hashes = set()
    manifest_hashes = set()
    runtime_source_commits = set()
    runtime_source_trees = set()
    runtime_content_hashes = set()
    runtime_file_counts = set()
    manifest_digest = (
        sha256_bytes(matrix_manifest_bytes)
        if isinstance(matrix_manifest_bytes, bytes)
        else None
    )
    try:
        matrix_manifest = validate_release_matrix_manifest(
            strict_json_bytes(matrix_manifest_bytes)
        ) if isinstance(matrix_manifest_bytes, bytes) else None
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
        RuntimeError,
    ):
        matrix_manifest = None
    candidate = (
        matrix_manifest.get("candidate")
        if isinstance(matrix_manifest, dict)
        else None
    )
    required_cell_set = (
        matrix_manifest.get("required_cell_set")
        if isinstance(matrix_manifest, dict)
        else None
    )
    required_game_cells = (
        required_cell_set.get("required_cells_by_game")
        if isinstance(required_cell_set, dict)
        else None
    )
    required_cell_count = (
        required_cell_set.get("required_cell_count")
        if isinstance(required_cell_set, dict)
        else None
    )
    catalogs = (
        matrix_manifest.get("catalogs")
        if isinstance(matrix_manifest, dict)
        else None
    )
    engines = catalogs.get("engines") if isinstance(catalogs, dict) else None
    engine_is_bound = (
        isinstance(engines, list)
        and sum(
            1
            for engine in engines
            if isinstance(engine, dict)
            and engine.get("source_commit") == expected_engine_commit
            and engine.get("binding_kind") == "PINNED_RUNTIME"
        ) == 1
    )
    required_game_cells_are_exact = (
        isinstance(required_game_cells, dict)
        and set(required_game_cells) == set(RELEASE_MATRIX_GAME_CELL_COUNTS)
        and all(
            type(required_game_cells[game]) is int
            and required_game_cells[game] == expected
            for game, expected in RELEASE_MATRIX_GAME_CELL_COUNTS.items()
        )
    )
    matrix_is_bound = (
        isinstance(matrix_manifest, dict)
        and matrix_manifest.get("schema") == "kfp.release-matrix.manifest.v1"
        and type(matrix_manifest.get("schema_version")) is int
        and matrix_manifest.get("schema_version") == 1
        and matrix_manifest.get("mode") == "PRIVATE_RELEASE"
        and matrix_manifest.get("release_eligible") is True
        and isinstance(candidate, dict)
        and candidate.get("package_kind") == "RELEASE_CANDIDATE"
        and isinstance(candidate.get("runtime_source_commit"), str)
        and OBJECT_ID.fullmatch(candidate["runtime_source_commit"]) is not None
        and isinstance(candidate.get("runtime_source_tree"), str)
        and OBJECT_ID.fullmatch(candidate["runtime_source_tree"]) is not None
        and isinstance(candidate.get("runtime_content_sha256"), str)
        and HEX_64.fullmatch(candidate["runtime_content_sha256"]) is not None
        and isinstance(candidate.get("package_sha256"), str)
        and HEX_64.fullmatch(candidate["package_sha256"]) is not None
        and isinstance(required_cell_set, dict)
        and required_cell_set.get("schema")
        == "kfp.release-matrix.required-cell-set.v1"
        and type(required_cell_set.get("schema_version")) is int
        and required_cell_set.get("schema_version") == 1
        and isinstance(required_cell_set.get("manifest_input_sha256"), str)
        and HEX_64.fullmatch(required_cell_set["manifest_input_sha256"])
        is not None
        and isinstance(required_cell_set.get("required_cell_ids_sha256"), str)
        and HEX_64.fullmatch(required_cell_set["required_cell_ids_sha256"])
        is not None
        and required_game_cells_are_exact
        and type(required_cell_count) is int
        and required_cell_count == RELEASE_MATRIX_CELL_COUNT
        and engine_is_bound
    )
    for name, game in GAME_ACCEPTANCE_GATES.items():
        if name not in required_gates:
            continue
        evidence = gates[name]["evidence"]
        item = evidence[0] if len(evidence) == 1 else None
        result = item.get("result") if isinstance(item, dict) else None
        document = game_documents.get(game) if isinstance(game_documents, dict) else None
        expected_document = game_result_bytes(result)
        if (
            not valid_game_acceptance_evidence(item, game)
            or not isinstance(document, bytes)
            or expected_document is None
            or document != expected_document
            or sha256_bytes(document) != item.get("sha256")
            or not matrix_is_bound
            or result.get("runtime_source_commit")
            != candidate.get("runtime_source_commit")
            or result.get("runtime_source_tree")
            != candidate.get("runtime_source_tree")
            or result.get("runtime_content_sha256")
            != candidate.get("runtime_content_sha256")
            or result.get("engine_commit") != expected_engine_commit
            or result.get("source_date_epoch") != expected_epoch
            or result.get("required_cells") != required_game_cells.get(game)
            or result.get("matrix_manifest_sha256") != manifest_digest
            or result.get("package_sha256") != candidate.get("package_sha256")
        ):
            invalid_game_evidence.append(name)
            continue
        package_hashes.add(result["package_sha256"])
        manifest_hashes.add(result["matrix_manifest_sha256"])
        runtime_source_commits.add(result["runtime_source_commit"])
        runtime_source_trees.add(result["runtime_source_tree"])
        runtime_content_hashes.add(result["runtime_content_sha256"])
        runtime_file_counts.add(result["runtime_file_count"])
    if invalid_game_evidence:
        raise RuntimeError(
            "release blocked: invalid game acceptance evidence: "
            + ", ".join(invalid_game_evidence)
        )
    if (
        len(package_hashes) != 1
        or len(manifest_hashes) != 1
        or len(runtime_source_commits) != 1
        or len(runtime_source_trees) != 1
        or len(runtime_content_hashes) != 1
        or len(runtime_file_counts) != 1
    ):
        raise RuntimeError("release blocked: game acceptance bindings disagree")
    return {
        "package_sha256": package_hashes.pop(),
        "matrix_manifest_sha256": manifest_hashes.pop(),
        "runtime_source_commit": runtime_source_commits.pop(),
        "runtime_source_tree": runtime_source_trees.pop(),
        "runtime_content_sha256": runtime_content_hashes.pop(),
        "runtime_file_count": runtime_file_counts.pop(),
        "engine_commit": expected_engine_commit,
        "source_date_epoch": expected_epoch,
    }


def require_release_approval(
    source: Path,
    version: str,
    source_commit: str,
    trusted_signing_key: str | None,
    engine_commit: str,
    source_date_epoch: int,
) -> dict[str, object]:
    expected_tag = "v" + version
    channel, ledger_path, required_gates = release_policy(version)
    trusted = (trusted_signing_key or "").replace(" ", "").upper()
    if FINGERPRINT.fullmatch(trusted) is None:
        raise RuntimeError("release blocked: trusted signing-key fingerprint is absent")
    try:
        exact_tag = run("git", "describe", "--tags", "--exact-match", cwd=source)
        tag_type = run("git", "cat-file", "-t", expected_tag, cwd=source)
        tag_commit = run("git", "rev-list", "-n", "1", expected_tag, cwd=source)
        verification = run("git", "verify-tag", "--raw", expected_tag, cwd=source)
        rights_bytes = run_bytes(
            "git", "show", f"{expected_tag}:docs/rights-approval.json", cwd=source
        )
        ledger_bytes = run_bytes(
            "git", "show", f"{expected_tag}:{ledger_path}", cwd=source
        )
        game_documents = {
            game: run_bytes(
                "git",
                "show",
                f"{expected_tag}:{GAME_ACCEPTANCE_LOCATORS[game]}",
                cwd=source,
            )
            for game in GAME_ACCEPTANCE_LOCATORS
        }
        matrix_manifest_bytes = run_bytes(
            "git", "show", f"{expected_tag}:docs/release-matrix/matrix-v1.json",
            cwd=source,
        )
    except subprocess.CalledProcessError as error:
        raise RuntimeError(
            "release blocked: signed tag or tagged approval records are absent"
        ) from error
    valid_signatures = re.findall(r"\[GNUPG:\] VALIDSIG ([0-9A-F]+)", verification)
    if (
        exact_tag != expected_tag
        or tag_type != "tag"
        or tag_commit != source_commit
        or trusted not in valid_signatures
    ):
        raise RuntimeError(
            "release blocked: source is not the approved tag from the trusted signer"
        )

    try:
        rights_record = strict_json_bytes(rights_bytes)
        record = strict_json_bytes(ledger_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise RuntimeError("release blocked: tagged approval JSON is invalid") from error
    game_bindings = validate_release_records(
        rights_record,
        record,
        version,
        expected_tag,
        channel,
        required_gates,
        engine_commit,
        source_date_epoch,
        game_documents,
        matrix_manifest_bytes,
    )
    runtime_source_commit = str(game_bindings["runtime_source_commit"])
    try:
        runtime_source_tree = run(
            "git", "rev-parse", f"{runtime_source_commit}^{{tree}}", cwd=source
        )
        run(
            "git", "merge-base", "--is-ancestor", runtime_source_commit,
            tag_commit, cwd=source,
        )
    except subprocess.CalledProcessError as error:
        raise RuntimeError(
            "release blocked: frozen runtime source is not an ancestor of the tag"
        ) from error
    if runtime_source_tree != game_bindings["runtime_source_tree"]:
        raise RuntimeError("release blocked: frozen runtime source tree is invalid")
    runtime_content = runtime_content_fingerprint_from_ref(
        source, runtime_source_commit
    )
    verify_accepted_runtime(game_bindings, runtime_content)

    return {
        "tag": expected_tag,
        "channel": channel,
        "tag_commit": tag_commit,
        "signing_key_fingerprint": trusted,
        "rights_sha256": sha256_bytes(rights_bytes),
        "ledger_sha256": sha256_bytes(ledger_bytes),
        "package_sha256": game_bindings["package_sha256"],
        "matrix_manifest_sha256": game_bindings["matrix_manifest_sha256"],
        "runtime_source_commit": runtime_source_commit,
        "runtime_source_tree": runtime_source_tree,
        "runtime_content_sha256": game_bindings["runtime_content_sha256"],
        "runtime_file_count": game_bindings["runtime_file_count"],
        "engine_commit": engine_commit,
        "source_date_epoch": source_date_epoch,
    }


def verify_accepted_package(
    release_approval: dict[str, object] | None,
    actual_sha256: str,
) -> None:
    if (
        release_approval is not None
        and actual_sha256 != release_approval.get("package_sha256")
    ):
        raise RuntimeError(
            "release blocked: built package does not match accepted runtime package"
        )


def verify_accepted_runtime(
    release_approval: dict[str, object] | None,
    runtime_content: dict[str, object],
) -> None:
    if release_approval is None:
        return
    if (
        runtime_content.get("algorithm") != "sha256-framed-path-content-v1"
        or runtime_content.get("sha256")
        != release_approval.get("runtime_content_sha256")
        or runtime_content.get("file_count")
        != release_approval.get("runtime_file_count")
    ):
        raise RuntimeError(
            "release blocked: tagged runtime content differs from accepted source"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--epoch", type=int, default=None)
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument("--release", action="store_true")
    parser.add_argument(
        "--trusted-signing-key",
        default=os.environ.get("KFP_TRUSTED_SIGNING_KEY"),
        help="full trusted release signing-key fingerprint; required with --release",
    )
    args = parser.parse_args()

    source = args.source.resolve()
    engine = args.engine.resolve()
    output_dir = args.output_dir.resolve()
    if inside(output_dir, source):
        raise RuntimeError("output directory must be outside the mod source tree")
    engine_commit = run("git", "rev-parse", "HEAD", cwd=engine)
    if engine_commit not in PINNED_ENGINES:
        raise RuntimeError(f"engine commit is not an audited baseline: {engine_commit}")
    source_commit = run("git", "rev-parse", "HEAD", cwd=source)
    git_status_dirty = bool(
        run_bytes(
            "git",
            "status",
            "--porcelain=v1",
            "-z",
            "--untracked-files=all",
            cwd=source,
        )
    )
    source_mode, attested_dirty = select_source_mode(
        release=args.release,
        allow_dirty=args.allow_dirty,
        git_status_dirty=git_status_dirty,
    )

    if source_mode == "worktree":
        manifest_for_build = load_worktree_manifest(source)
    else:
        manifest_for_build = load_manifest_bytes(
            run_bytes(
                "git", "show", f"{source_commit}:manifest.json", cwd=source
            )
        )

    epoch = resolve_epoch(args.epoch, os.environ)

    release_approval = None
    if args.release:
        release_approval = require_release_approval(
            source,
            manifest_for_build["version"],
            source_commit,
            args.trusted_signing_key,
            engine_commit,
            epoch,
        )

    manifest = manifest_for_build
    stem = f"{manifest['id']}-{manifest['version']}"
    output_dir.mkdir(parents=True, exist_ok=True)
    modpkg = output_dir / f"{stem}.modpkg"
    root_zip = output_dir / f"{stem}.zip"
    sums = output_dir / f"{stem}-SHA256SUMS.txt"
    attestation = output_dir / f"{stem}-attestation.json"
    targets = (modpkg, root_zip, sums, attestation)
    existing = [str(path) for path in targets if path.exists()]
    if existing:
        raise RuntimeError("refusing to overwrite existing artifacts: " + ", ".join(existing))

    with tempfile.TemporaryDirectory(prefix="kfp-package-") as temporary:
        temporary_path = Path(temporary)
        engine_staging = temporary_path / "engine"
        copy_engine_from_commit(engine, engine_commit, engine_staging, temporary_path)
        staging = temporary_path / "mod"
        staging.mkdir()
        if source_mode == "signed-tag":
            assert release_approval is not None
            files = copy_runtime_from_tag(
                source, release_approval["tag_commit"], staging, temporary_path
            )
        elif source_mode == "worktree":
            files = copy_runtime(source, staging)
        else:
            files = copy_runtime_from_ref(source, source_commit, staging)
        staged_manifest = load_manifest(staging / "manifest.json")
        if (
            staged_manifest.get("id") != manifest.get("id")
            or staged_manifest.get("version") != manifest.get("version")
        ):
            raise RuntimeError("packaged manifest does not match selected source tag")
        manifest = staged_manifest
        env = dict(os.environ)
        env["SOURCE_DATE_EPOCH"] = str(epoch)
        python = sys.executable
        modkit = engine_staging / "tools" / "modkit.py"
        print(run(python, str(modkit), "validate", "--strict", "--base", "fixture",
                  str(staging), cwd=engine_staging, env=env))
        print(run(python, str(modkit), "lint", str(staging), cwd=engine_staging,
                  env=env))
        print(run(python, str(modkit), "pack", "--base", "fixture", "-o",
                  str(modpkg), str(staging), cwd=engine_staging, env=env))
        verify_modpkg_runtime(modpkg, staging, files)
        deterministic_zip(staging, root_zip, files)

        records = []
        for relative in files:
            path = staging / relative
            records.append({
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            })
        runtime_content = runtime_content_fingerprint(staging, files)
        verify_accepted_runtime(release_approval, runtime_content)

    artifact_hashes = {path.name: sha256(path) for path in (modpkg, root_zip)}
    verify_accepted_package(release_approval, artifact_hashes[modpkg.name])
    sums.write_text(
        "".join(f"{digest}  {name}\n" for name, digest in sorted(artifact_hashes.items())),
        encoding="utf-8",
        newline="\n",
    )
    attestation.write_text(
        json.dumps({
            "schema": 1,
            "id": manifest["id"],
            "version": manifest["version"],
            "source_commit": source_commit,
            "source_dirty": attested_dirty,
            "git_status_dirty": git_status_dirty,
            "source_content_mode": source_mode,
            "engine_commit": engine_commit,
            "source_date_epoch": epoch,
            "publishable": release_approval is not None,
            "release_approval": release_approval,
            "runtime_content": runtime_content,
            "artifacts": artifact_hashes,
            "files": records,
        }, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"built {len(files)} runtime files in {output_dir}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"package failed: {error}", file=sys.stderr)
        raise SystemExit(1)
