#!/usr/bin/env python3
"""Build deterministic private test artifacts or a gated release package."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile


PINNED_ENGINES = {
    "44f4680b24823629489ed5a2adad648d0dceb640",
    "06e06e305bbcefe97c216a31bb25265ffb5e6b18",
    "70d7b6383e2c005857013dc897fd096886b08f0b",
    "478e3bf8ebf7646edfda88320c6472cf32db2e67",
    "116a6ba450dd65f25c9be150952fc3c27be904c0",
}
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


def strict_json_loads(value: str) -> object:
    return json.loads(value, object_pairs_hook=reject_duplicate_keys)


def strict_json_bytes(value: bytes) -> object:
    return strict_json_loads(value.decode("utf-8"))


def strict_json_file(path: Path) -> object:
    try:
        return strict_json_loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise RuntimeError(f"invalid or duplicate JSON in {path.name}") from error


def load_manifest(path: Path) -> dict[str, object]:
    manifest = strict_json_file(path)
    if not isinstance(manifest, dict):
        raise RuntimeError("manifest root must be a JSON object")
    for field in ("id", "version"):
        if not isinstance(manifest.get(field), str) or not manifest[field]:
            raise RuntimeError(f"manifest {field} must be a non-empty string")
    return manifest


def allowed_runtime_path(relative: str) -> bool:
    if relative in ROOT_FILES or relative in ASSET_FILES:
        return True
    return relative.startswith("src/") and relative.endswith(".lua")


def listed_runtime_files(source: Path) -> list[str]:
    raw = run_bytes(
        "git",
        "ls-files",
        "-z",
        "--cached",
        "--others",
        "--exclude-standard",
        "--",
        *ROOT_FILES,
        *RUNTIME_DIRS,
        cwd=source,
    )
    try:
        candidates = [item for item in raw.decode("utf-8").split("\0") if item]
    except UnicodeDecodeError as error:
        raise RuntimeError("runtime path is not valid UTF-8") from error
    invalid = sorted(path for path in candidates if not allowed_runtime_path(path))
    if invalid:
        raise RuntimeError(
            "runtime tree contains non-allowlisted files: " + ", ".join(invalid)
        )
    return sorted(set(candidates))


def copy_runtime(source: Path, staging: Path) -> list[str]:
    candidates = listed_runtime_files(source)
    required = set(ROOT_FILES + ASSET_FILES)
    missing = sorted(required.difference(candidates))
    if missing:
        raise RuntimeError("required package files are missing: " + ", ".join(missing))
    if not any(path.startswith("src/") for path in candidates):
        raise RuntimeError("required runtime source is missing")

    copied: list[str] = []
    for relative in candidates:
        src = source / relative
        if not src.is_file() or src.is_symlink() or not inside(src.resolve(), source):
            raise RuntimeError(f"required package file is missing: {relative}")
        dst = staging / relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        copied.append(relative)
    return sorted(copied)


def copy_runtime_from_tag(
    source: Path, tag: str, staging: Path, temporary: Path
) -> list[str]:
    archive_path = temporary / "signed-source.zip"
    run(
        "git",
        "archive",
        "--format=zip",
        f"--output={archive_path}",
        tag,
        "--",
        *ROOT_FILES,
        *RUNTIME_DIRS,
        cwd=source,
    )
    copied: list[str] = []
    with zipfile.ZipFile(archive_path, "r") as archive:
        for entry in sorted(archive.infolist(), key=lambda item: item.filename):
            if entry.is_dir():
                continue
            relative = entry.filename.replace("\\", "/")
            parts = relative.split("/")
            mode = (entry.external_attr >> 16) & 0o170000
            if (
                not relative
                or relative.startswith("/")
                or any(part in ("", ".", "..") for part in parts)
                or mode == 0o120000
            ):
                raise RuntimeError("signed source archive contains an unsafe path")
            if not allowed_runtime_path(relative):
                raise RuntimeError(
                    "signed source contains a non-allowlisted file: " + relative
                )
            destination = staging.joinpath(*parts).resolve()
            if not inside(destination, staging.resolve()):
                raise RuntimeError("signed source archive escapes staging")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(archive.read(entry))
            copied.append(relative)

    required = set(ROOT_FILES + ASSET_FILES)
    missing = sorted(required.difference(copied))
    if missing:
        raise RuntimeError(
            "signed source archive is missing required files: " + ", ".join(missing)
        )
    if (
        not any(path.startswith("src/") for path in copied)
        or not any(path.startswith("assets/") for path in copied)
    ):
        raise RuntimeError("signed source archive is missing runtime directories")
    return sorted(copied)


def copy_engine_from_commit(
    engine: Path, commit: str, staging: Path, temporary: Path
) -> None:
    archive_path = temporary / "engine-source.zip"
    run(
        "git",
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
        for relative in files:
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, (source / relative).read_bytes(), compresslevel=9)


def inside(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def valid_evidence(value: object) -> bool:
    if not isinstance(value, dict) or set(value) != {"kind", "locator", "sha256"}:
        return False
    kind, locator, digest = value["kind"], value["locator"], value["sha256"]
    return (
        isinstance(kind, str)
        and EVIDENCE_KIND.fullmatch(kind) is not None
        and isinstance(locator, str)
        and 1 <= len(locator) <= 512
        and all(ord(character) >= 32 for character in locator)
        and isinstance(digest, str)
        and HEX_64.fullmatch(digest) is not None
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
) -> None:
    selected_channel, _, selected_gates = release_policy(version)
    channel = channel or selected_channel
    required_gates = required_gates or selected_gates
    if not isinstance(rights_record, dict) or rights_record.get("schema") != 1:
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

    if not isinstance(record, dict) or record.get("schema") != 1:
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
    if not isinstance(approved_at, str) or UTC_TIMESTAMP.fullmatch(approved_at) is None:
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
        if (
            not isinstance(gate, dict)
            or set(gate) != {"passed", "evidence"}
            or gate.get("passed") is not True
            or not isinstance(evidence, list)
            or not evidence
            or not all(valid_evidence(item) for item in evidence)
        ):
            incomplete.append(name)
    if incomplete:
        raise RuntimeError(
            "release blocked: incomplete gates: " + ", ".join(incomplete)
        )


def require_release_approval(
    source: Path,
    version: str,
    source_commit: str,
    trusted_signing_key: str | None,
) -> dict[str, str]:
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
    validate_release_records(
        rights_record,
        record,
        version,
        expected_tag,
        channel,
        required_gates,
    )

    return {
        "tag": expected_tag,
        "channel": channel,
        "tag_commit": tag_commit,
        "signing_key_fingerprint": trusted,
        "rights_sha256": sha256_bytes(rights_bytes),
        "ledger_sha256": sha256_bytes(ledger_bytes),
    }


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
    dirty = bool(run("git", "status", "--porcelain", cwd=source))
    if dirty and not args.allow_dirty:
        raise RuntimeError("source tree is dirty; use --allow-dirty only for a private test build")

    release_approval = None
    if args.release:
        if dirty:
            raise RuntimeError("a release build cannot use dirty source")
        manifest_for_gate = load_manifest(source / "manifest.json")
        release_approval = require_release_approval(
            source,
            manifest_for_gate["version"],
            source_commit,
            args.trusted_signing_key,
        )

    epoch = args.epoch
    if epoch is None:
        raw_epoch = os.environ.get("SOURCE_DATE_EPOCH")
        if raw_epoch is None:
            raise RuntimeError("set SOURCE_DATE_EPOCH or pass --epoch")
        epoch = int(raw_epoch)
    if epoch < 0:
        raise RuntimeError("epoch must be nonnegative")

    manifest = load_manifest(source / "manifest.json")
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
        if release_approval:
            files = copy_runtime_from_tag(
                source, release_approval["tag"], staging, temporary_path
            )
        else:
            files = copy_runtime(source, staging)
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
        deterministic_zip(staging, root_zip, files)

        records = []
        for relative in files:
            path = staging / relative
            records.append({
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            })

    artifact_hashes = {path.name: sha256(path) for path in (modpkg, root_zip)}
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
            "source_dirty": dirty,
            "engine_commit": engine_commit,
            "source_date_epoch": epoch,
            "publishable": release_approval is not None,
            "release_approval": release_approval,
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
