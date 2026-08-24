#!/usr/bin/env python3
"""Generate public, deterministic alpha-quality status data from safe fixtures."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURES = ROOT / "tests" / "fixtures" / "alpha_quality"
DEFAULT_OUTPUT = ROOT / "website" / "public" / "alpha-quality-status.json"

GATE_ORDER = ("camera", "config", "audio", "companion")
QUALITY_ORDER = ("Low", "Balanced", "High")
RESULT_STATUSES = {"PASS", "FAIL", "INELIGIBLE"}
CLEANUP_STATUSES = {"PASS", "FAIL", "NOT_APPLICABLE"}
ELIGIBILITY_STATUSES = {"ELIGIBLE", "INELIGIBLE", "CONTROL"}
APPROVED_COHORT = (
    "alpha-quality-synthetic-v1",
    "e540c3b3de25caa5fa855dd6c3c702449ed9e72c",
    "cdc415907e244cbce7ff9e46f1dffdbdee07d713",
    "f31044dfcc4dcdd3a68536424293058aec70b0390f99ed243e1af18189b5e620",
    "gen1recomp",
    "Gen1Recomp",
    "0.2.19",
)
RESULT_CATALOG = {
    "audio-high-battle-art": (
        "audio",
        "battle-art",
        "Battle Art",
        "1.9.8",
        "ELIGIBLE",
        "High",
        "audio-kfp-owned-mix",
    ),
    "camera-low-battle-art": (
        "camera",
        "battle-art",
        "Battle Art",
        "1.9.8",
        "ELIGIBLE",
        "Low",
        "camera-bedroom-entry",
    ),
    "companion-battle-art-balanced": (
        "companion",
        "battle-art",
        "Battle Art",
        "1.9.8",
        "ELIGIBLE",
        "Balanced",
        "companion-battle-art-contract",
    ),
    "companion-dramaless-ineligible": (
        "companion",
        "dramaless",
        "Dramaless",
        "unreleased",
        "INELIGIBLE",
        "High",
        "companion-dramaless-release",
    ),
    "companion-kfp-no-host-control": (
        "companion",
        "kfp-no-host",
        "KFP no-host fail-closed control",
        "none",
        "CONTROL",
        "Low",
        "companion-no-host-fail-closed",
    ),
    "config-balanced-battle-art": (
        "config",
        "battle-art",
        "Battle Art",
        "1.9.8",
        "ELIGIBLE",
        "Balanced",
        "config-round-trip",
    ),
}
HASH_40 = re.compile(r"^[0-9a-f]{40}$")
HASH_64 = re.compile(r"^[0-9a-f]{64}$")
IDENTIFIER = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
PUBLIC_REFERENCE = re.compile(
    r"^public-evidence://[a-z0-9][a-z0-9-]*(?:/[a-z0-9][a-z0-9-]*)*"
    r"(?:#[a-z0-9][a-z0-9-]*)?$"
)
PUBLIC_REFERENCE_SEGMENT = re.compile(r"^[a-z0-9][a-z0-9-]*$")
WINDOWS_DRIVE_PATH = re.compile(r"(?<![A-Za-z0-9+.-])[A-Za-z]:(?=\S)")
WINDOWS_ROOT_RELATIVE_PATH = re.compile(r"(?<![\\A-Za-z0-9])\\(?![\\\s])")
UNC_PATH = re.compile(
    r"(?:(?<!:)//|\\\\)[^\\/\s]+[\\/][^\\/\s]+"
)
POSIX_ABSOLUTE_PATH = re.compile(r"(?<![A-Za-z0-9+.:/_-])/(?!/|\s)")
FILE_URI = re.compile(r"file:(?:/{1,3}|\\\\)", re.IGNORECASE)
PATH_TRAVERSAL = re.compile(r"(?<![A-Za-z0-9.])\.\.(?:$|[/\\])")
DOT_PATH_SEGMENT = re.compile(r"(?<![A-Za-z0-9.])\.(?:$|[/\\])")
ENCODED_PATH_PART = re.compile(r"%(?:25)*(?:2e|2f|5c)", re.IGNORECASE)
PRIVATE_PATH = re.compile(
    r"(?:^|[/\\])(?:appdata|private-fixtures|baseroms|roms|saves?|cache)(?:[/\\]|$)",
    re.IGNORECASE,
)
FORBIDDEN_MEDIA_SUFFIX = re.compile(
    r"\.(?:aac|aiff?|au|bmp|caf|flac|gif|jpe?g|log|m4a|midi?|mov|mp3|mp4|oga|ogg|opus|png|wav|wave|webm|webp|wma)(?:#.*)?$",
    re.IGNORECASE,
)
FORBIDDEN_FIELD_PARTS = {
    "appdata",
    "cache",
    "capture",
    "credential",
    "image",
    "log",
    "password",
    "private",
    "rom",
    "save",
    "screenshot",
    "secret",
    "token",
    "video",
}
SECRET_PATTERNS = (
    re.compile(
        r"-----(?:BEGIN|END)(?: [A-Z0-9]+)* PRIVATE KEY-----", re.IGNORECASE
    ),
    re.compile(
        r"\bbearer(?:[ \t]+|[ \t]*[:=][ \t]*)"
        r"[A-Za-z0-9][A-Za-z0-9._~+/-]{19,}={0,2}"
        r"(?![A-Za-z0-9._~+/-])",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    re.compile(r"\bsk-(?:proj-|ant-[A-Za-z0-9-]*-)?[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    re.compile(r"\b(?:xox[baprs]-[A-Za-z0-9-]{10,}|xapp-[A-Za-z0-9-]{10,})\b"),
    re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bAIza[A-Za-z0-9_-]{35}\b"),
    re.compile(r"\bnpm_[A-Za-z0-9]{36}\b"),
    re.compile(r"\b(?:sk|rk)_live_[A-Za-z0-9]{16,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
)


class ValidationError(ValueError):
    """A fixture is not safe or does not match the public result contract."""


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError("duplicate JSON key")
        result[key] = value
    return result


def exact_keys(value: Any, expected: set[str], context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValidationError(f"{context} must be an object")
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        details = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if unknown:
            details.append(f"{len(unknown)} unknown field(s)")
        raise ValidationError(f"{context} has " + "; ".join(details))
    return value


def text(
    value: Any,
    context: str,
    *,
    pattern: re.Pattern[str] | None = None,
    maximum: int = 160,
) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise ValidationError(f"{context} must be a non-empty string of at most {maximum} characters")
    if any(ord(character) < 32 for character in value):
        raise ValidationError(f"{context} contains a control character")
    if pattern is not None and pattern.fullmatch(value) is None:
        raise ValidationError(f"{context} has an invalid format")
    reject_unsafe_string(value, context)
    return value


def reject_unsafe_string(value: str, context: str) -> None:
    if (
        WINDOWS_DRIVE_PATH.search(value)
        or WINDOWS_ROOT_RELATIVE_PATH.search(value)
        or UNC_PATH.search(value)
        or POSIX_ABSOLUTE_PATH.search(value)
        or FILE_URI.search(value)
        or PATH_TRAVERSAL.search(value)
        or DOT_PATH_SEGMENT.search(value)
        or ENCODED_PATH_PART.search(value)
    ):
        raise ValidationError(f"{context} contains an unsafe path")
    if PRIVATE_PATH.search(value) or "private-evidence://" in value.lower():
        raise ValidationError(f"{context} contains a private path")
    for pattern in SECRET_PATTERNS:
        if pattern.search(value):
            raise ValidationError(f"{context} contains a possible secret")


def reject_forbidden_fields(value: Any, context: str = "fixture") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            parts = {part for part in re.split(r"[^a-z0-9]+", key.lower()) if part}
            forbidden = sorted(parts & FORBIDDEN_FIELD_PARTS)
            if forbidden:
                raise ValidationError(f"{context} contains a forbidden field")
            reject_forbidden_fields(child, f"{context}.field")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            reject_forbidden_fields(child, f"{context}[{index}]")
    elif isinstance(value, str):
        reject_unsafe_string(value, context)


def validate_hash(value: Any, context: str, pattern: re.Pattern[str]) -> str:
    return text(value, context, pattern=pattern, maximum=64)


def validate_fixture(value: Any, context: str = "fixture") -> dict[str, Any]:
    fixture = exact_keys(
        value,
        {
            "schema",
            "suite_id",
            "result_id",
            "source",
            "package",
            "engine",
            "host",
            "quality",
            "checkpoint_id",
            "gate_id",
            "status",
            "cleanup",
            "summary",
            "evidence",
        },
        context,
    )
    reject_forbidden_fields(fixture, context)

    if type(fixture["schema"]) is not int or fixture["schema"] != 1:
        raise ValidationError(f"{context}.schema must equal 1")
    text(fixture["suite_id"], f"{context}.suite_id", pattern=IDENTIFIER)
    text(fixture["result_id"], f"{context}.result_id", pattern=IDENTIFIER)

    source = exact_keys(
        fixture["source"], {"commit_sha", "tree_sha"}, f"{context}.source"
    )
    validate_hash(source["commit_sha"], f"{context}.source.commit_sha", HASH_40)
    validate_hash(source["tree_sha"], f"{context}.source.tree_sha", HASH_40)

    package = exact_keys(fixture["package"], {"sha256"}, f"{context}.package")
    validate_hash(package["sha256"], f"{context}.package.sha256", HASH_64)

    engine = exact_keys(
        fixture["engine"], {"id", "label", "version"}, f"{context}.engine"
    )
    text(engine["id"], f"{context}.engine.id", pattern=IDENTIFIER)
    text(engine["label"], f"{context}.engine.label")
    text(engine["version"], f"{context}.engine.version", maximum=64)

    host = exact_keys(
        fixture["host"],
        {"id", "label", "release", "eligibility"},
        f"{context}.host",
    )
    text(host["id"], f"{context}.host.id", pattern=IDENTIFIER)
    text(host["label"], f"{context}.host.label")
    text(host["release"], f"{context}.host.release", maximum=64)
    if (
        not isinstance(host["eligibility"], str)
        or host["eligibility"] not in ELIGIBILITY_STATUSES
    ):
        raise ValidationError(f"{context}.host.eligibility is invalid")

    if fixture["quality"] not in QUALITY_ORDER:
        raise ValidationError(f"{context}.quality is invalid")
    text(fixture["checkpoint_id"], f"{context}.checkpoint_id", pattern=IDENTIFIER)
    if fixture["gate_id"] not in GATE_ORDER:
        raise ValidationError(f"{context}.gate_id is unknown")
    if not isinstance(fixture["status"], str) or fixture["status"] not in RESULT_STATUSES:
        raise ValidationError(f"{context}.status is invalid")
    if (
        not isinstance(fixture["cleanup"], str)
        or fixture["cleanup"] not in CLEANUP_STATUSES
    ):
        raise ValidationError(f"{context}.cleanup is invalid")
    text(fixture["summary"], f"{context}.summary", maximum=240)

    eligibility = host["eligibility"]
    status = fixture["status"]
    cleanup = fixture["cleanup"]
    if status == "PASS" and cleanup != "PASS":
        raise ValidationError(f"{context} cannot pass unless cleanup passes")
    if eligibility == "INELIGIBLE" and status != "INELIGIBLE":
        raise ValidationError(f"{context} ineligible host must use INELIGIBLE status")
    if eligibility != "INELIGIBLE" and status == "INELIGIBLE":
        raise ValidationError(f"{context} eligible or control host cannot be INELIGIBLE")
    if status == "INELIGIBLE" and cleanup != "NOT_APPLICABLE":
        raise ValidationError(f"{context} ineligible result cleanup must be NOT_APPLICABLE")

    evidence = fixture["evidence"]
    if not isinstance(evidence, list) or not evidence:
        raise ValidationError(f"{context}.evidence must be a non-empty array")
    evidence_ids: set[str] = set()
    for index, item_value in enumerate(evidence):
        item_context = f"{context}.evidence[{index}]"
        item = exact_keys(
            item_value, {"id", "kind", "reference", "sha256"}, item_context
        )
        evidence_id = text(item["id"], f"{item_context}.id", pattern=IDENTIFIER)
        if evidence_id in evidence_ids:
            raise ValidationError(f"{context} has duplicate evidence id {evidence_id}")
        evidence_ids.add(evidence_id)
        text(item["kind"], f"{item_context}.kind", pattern=IDENTIFIER)
        reference = text(
            item["reference"],
            f"{item_context}.reference",
            pattern=PUBLIC_REFERENCE,
            maximum=240,
        )
        reference_path = reference.removeprefix("public-evidence://").split("#", 1)[0]
        if any(
            PUBLIC_REFERENCE_SEGMENT.fullmatch(segment) is None
            for segment in reference_path.split("/")
        ):
            raise ValidationError(f"{item_context}.reference has an unsafe path segment")
        if FORBIDDEN_MEDIA_SUFFIX.search(reference):
            raise ValidationError(f"{item_context}.reference names raw media or a log")
        validate_hash(item["sha256"], f"{item_context}.sha256", HASH_64)

    return fixture


def load_fixtures(fixtures_dir: Path) -> list[dict[str, Any]]:
    if not fixtures_dir.is_dir():
        raise ValidationError("fixture directory does not exist")
    paths = sorted(fixtures_dir.rglob("*.json"), key=lambda path: path.relative_to(fixtures_dir).as_posix())
    if not paths:
        raise ValidationError("fixture directory contains no JSON fixtures")

    fixtures: list[dict[str, Any]] = []
    result_ids: set[str] = set()
    for index, path in enumerate(paths):
        if path.is_symlink() or not path.is_file():
            raise ValidationError("fixture entries must be regular files")
        try:
            raw = path.read_bytes()
            value = json.loads(raw.decode("utf-8"), object_pairs_hook=strict_object)
        except UnicodeDecodeError as error:
            raise ValidationError(f"fixture {index} is not UTF-8") from error
        except json.JSONDecodeError as error:
            raise ValidationError(f"fixture {index} is invalid JSON") from error
        fixture = validate_fixture(value, f"fixture[{index}]")
        result_id = fixture["result_id"]
        if result_id in result_ids:
            raise ValidationError(f"duplicate result id: {result_id}")
        result_ids.add(result_id)
        fixtures.append(fixture)
    return fixtures


def _add_unique(
    target: dict[str, dict[str, Any]], key: str, value: dict[str, Any], context: str
) -> None:
    previous = target.get(key)
    if previous is not None and previous != value:
        raise ValidationError(f"conflicting {context}: {key}")
    target[key] = value


def cohort_key(fixture: dict[str, Any]) -> tuple[str, str, str, str, str, str, str]:
    return (
        fixture["suite_id"],
        fixture["source"]["commit_sha"],
        fixture["source"]["tree_sha"],
        fixture["package"]["sha256"],
        fixture["engine"]["id"],
        fixture["engine"]["label"],
        fixture["engine"]["version"],
    )


def result_catalog_key(fixture: dict[str, Any]) -> tuple[str, str, str, str, str, str, str]:
    host = fixture["host"]
    return (
        fixture["gate_id"],
        host["id"],
        host["label"],
        host["release"],
        host["eligibility"],
        fixture["quality"],
        fixture["checkpoint_id"],
    )


def build_status(fixtures: list[dict[str, Any]]) -> dict[str, Any]:
    if not fixtures:
        raise ValidationError("at least one fixture is required")

    fixtures = [
        validate_fixture(fixture, f"fixture[{index}]")
        for index, fixture in enumerate(fixtures)
    ]
    result_ids = [fixture["result_id"] for fixture in fixtures]
    if len(set(result_ids)) != len(result_ids):
        raise ValidationError("duplicate result id")
    if set(result_ids) != set(RESULT_CATALOG):
        raise ValidationError("result catalog is incomplete or contains an unknown result")
    for fixture in fixtures:
        if result_catalog_key(fixture) != RESULT_CATALOG[fixture["result_id"]]:
            raise ValidationError("result catalog entry does not match its approved identity")

    cohorts = {cohort_key(fixture) for fixture in fixtures}
    if cohorts != {APPROVED_COHORT}:
        raise ValidationError("fixtures do not match the approved source/package/engine cohort")

    sources: dict[str, dict[str, Any]] = {}
    packages: set[str] = set()
    engines: dict[str, dict[str, Any]] = {}
    hosts: dict[str, dict[str, Any]] = {}
    evidence: dict[str, dict[str, Any]] = {}
    checkpoints: set[str] = set()
    qualities: set[str] = set()
    results: list[dict[str, Any]] = []

    for fixture in fixtures:
        source = dict(fixture["source"])
        _add_unique(sources, source["commit_sha"], source, "source commit")
        packages.add(fixture["package"]["sha256"])
        engine = dict(fixture["engine"])
        _add_unique(engines, engine["id"], engine, "engine")
        host = dict(fixture["host"])
        _add_unique(hosts, host["id"], host, "host")
        checkpoints.add(fixture["checkpoint_id"])
        qualities.add(fixture["quality"])

        evidence_ids = []
        for item in fixture["evidence"]:
            item_copy = dict(item)
            if item_copy["id"] in evidence:
                raise ValidationError(f"duplicate evidence id: {item_copy['id']}")
            evidence[item_copy["id"]] = item_copy
            evidence_ids.append(item_copy["id"])

        results.append(
            {
                "checkpoint_id": fixture["checkpoint_id"],
                "cleanup": fixture["cleanup"],
                "engine_id": engine["id"],
                "evidence_ids": sorted(evidence_ids),
                "gate_id": fixture["gate_id"],
                "host_id": host["id"],
                "package_sha256": fixture["package"]["sha256"],
                "quality": fixture["quality"],
                "result_id": fixture["result_id"],
                "source_commit_sha": source["commit_sha"],
                "status": fixture["status"],
                "summary": fixture["summary"],
                "suite_id": fixture["suite_id"],
            }
        )

    results.sort(key=lambda item: item["result_id"])
    gate_summaries = []
    for gate_id in GATE_ORDER:
        selected = [item for item in results if item["gate_id"] == gate_id]
        eligible = [item for item in selected if hosts[item["host_id"]]["eligibility"] == "ELIGIBLE"]
        if any(item["status"] == "FAIL" or item["cleanup"] == "FAIL" for item in selected):
            gate_status = "FAIL"
        elif any(item["status"] == "INELIGIBLE" for item in selected):
            gate_status = "BLOCKED"
        elif eligible and all(item["status"] == "PASS" for item in eligible):
            gate_status = "PASS"
        else:
            gate_status = "NOT_RUN"
        counts = Counter(item["status"] for item in selected)
        gate_summaries.append(
            {
                "counts": {
                    "fail": counts["FAIL"],
                    "ineligible": counts["INELIGIBLE"],
                    "pass": counts["PASS"],
                    "total": len(selected),
                },
                "gate_id": gate_id,
                "required": True,
                "result_ids": [item["result_id"] for item in selected],
                "status": gate_status,
            }
        )

    passed_gates = sum(item["status"] == "PASS" for item in gate_summaries)
    readiness = "READY" if passed_gates == len(GATE_ORDER) else "NOT READY"
    result_counts = Counter(item["status"] for item in results)

    return {
        "checkpoints": sorted(checkpoints),
        "engines": [engines[key] for key in sorted(engines)],
        "evidence_references": [evidence[key] for key in sorted(evidence)],
        "gates": gate_summaries,
        "generated_by": "tools/generate_alpha_quality_status.py",
        "hosts": [hosts[key] for key in sorted(hosts)],
        "packages": [{"sha256": value} for value in sorted(packages)],
        "qualities": [quality for quality in QUALITY_ORDER if quality in qualities],
        "readiness_status": readiness,
        "release_status": "NOT RELEASED",
        "results": results,
        "schema": 1,
        "sources": [sources[key] for key in sorted(sources)],
        "summary": {
            "failed_results": result_counts["FAIL"],
            "ineligible_results": result_counts["INELIGIBLE"],
            "passed_results": result_counts["PASS"],
            "required_gates": len(GATE_ORDER),
            "required_gates_passed": passed_gates,
            "total_results": len(results),
        },
    }


def canonical_bytes(status: dict[str, Any]) -> bytes:
    return (json.dumps(status, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def generate(fixtures_dir: Path) -> bytes:
    return canonical_bytes(build_status(load_fixtures(fixtures_dir)))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--check", action="store_true", help="fail if the output is not canonical and current"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        expected = generate(args.fixtures)
        if args.check:
            if not args.output.is_file() or args.output.read_bytes() != expected:
                print("alpha quality status is missing or stale", file=sys.stderr)
                return 1
            print("alpha quality status check passed")
            return 0
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(expected)
        print("alpha quality status generated")
        return 0
    except TypeError:
        print("alpha quality status failed: invalid value type", file=sys.stderr)
        return 1
    except (OSError, ValidationError) as error:
        print(f"alpha quality status failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
