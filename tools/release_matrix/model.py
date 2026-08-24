"""Strict, ROM-free data model for the KFP release matrix.

This module is deliberately standard-library only.  It owns immutable matrix
identity and basic result binding.  Runtime execution, private adapters,
privacy scanning, and public reporting are separate lanes.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import itertools
import json
import math
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence


MANIFEST_SCHEMA = "kfp.release-matrix.manifest.v1"
CELL_IDENTITY_SCHEMA = "kfp.release-matrix.cell-identity.v1"
CELL_RESULT_SCHEMA = "kfp.release-matrix.cell-result.v1"
EVIDENCE_BINDING_SCHEMA = "kfp.release-matrix.evidence-binding.v1"
EVIDENCE_RECEIPT_SCHEMA = "kfp.release-matrix.evidence-receipt.v1"
MANUAL_VERDICT_SCHEMA = "kfp.release-matrix.manual-verdict.v1"
PUBLIC_STATUS_SCHEMA = "kfp.release-matrix.public-status.v1"
RESULT_SET_SCHEMA = "kfp.release-matrix.validated-result-set.v1"
SYNTHETIC_BINDING_SCHEMA = "kfp.release-matrix.synthetic-binding.v1"
BINDING_ACQUISITION_SCHEMA = "kfp.release-matrix.binding-acquisition.v1"
BINDING_SET_SCHEMA = "kfp.release-matrix.binding-set.v1"
PRIVATE_BINDING_ACQUISITION_SCHEMA = (
    "kfp.release-matrix.private-binding-acquisition.v1"
)
REQUIRED_CELL_SET_SCHEMA = "kfp.release-matrix.required-cell-set.v1"
SCHEMA_VERSION = 1

MAX_EVIDENCE_ITEMS = 32
MAX_EVIDENCE_BYTES = 1_099_511_627_776
MAX_TEST_POINTS = 26
MAX_POINT_BINDINGS = 1
MAX_CLASS_POINTS = 32
MAX_EVIDENCE_KINDS = 16
MAX_MANUAL_CRITERIA = 32
MAX_PUBLIC_BLOCKERS = 256
MAX_PUBLIC_CELLS = 10_000_000

EVIDENCE_BINDING_FIELDS = (
    "schema",
    "schema_version",
    "cell_id",
    "input_fingerprint",
    "attempt_id",
    "gate_id",
    "kind",
    "sha256",
    "bytes",
    "binding_sha256",
)
EVIDENCE_RECEIPT_FIELDS = (
    "schema",
    "schema_version",
    "ledger_root_id",
    "evidence",
    "receipt_sha256",
)

GAME_IDS = ("red", "blue", "yellow")
TIER_IDS = ("low", "balanced", "high")
ENGINE_PROVENANCE_V1 = {
    "gen1recomp-v0.2.17": (
        "Gen1recomp 0.2.17",
        "0.2.17",
        "44f4680b24823629489ed5a2adad648d0dceb640",
    ),
    "gen1recomp-v0.2.18": (
        "Gen1recomp 0.2.18",
        "0.2.18",
        "70d7b6383e2c005857013dc897fd096886b08f0b",
    ),
    "gen1recomp-v0.2.19": (
        "Gen1recomp 0.2.19",
        "0.2.19",
        "116a6ba450dd65f25c9be150952fc3c27be904c0",
    ),
    "gen1recomp-dev-baseline": (
        "Gen1recomp dev baseline",
        "dev-baseline",
        "06e06e305bbcefe97c216a31bb25265ffb5e6b18",
    ),
    "gen1recomp-dev-current": (
        "Gen1recomp dev current",
        "dev-current",
        "478e3bf8ebf7646edfda88320c6472cf32db2e67",
    ),
}
ENGINE_BINDINGS = {
    engine_id: provenance[2]
    for engine_id, provenance in ENGINE_PROVENANCE_V1.items()
}
ENGINE_IDS = tuple(ENGINE_PROVENANCE_V1)
PLATFORM_IDS = (
    "windows",
    "linux-x86-64",
    "linux-arm64",
    "macos-x86-64",
    "macos-arm64",
    "android",
    "ios-love12",
    "xbox-uwp",
    "nintendo-switch",
    "portmaster",
    "anbernic-stock",
)
HOST_MODE_IDS = ("no-host", "one-host", "multi-host", "fault-isolation")
TEST_CLASS_SPECS = (
    ("environment-binding", "OBJECTIVE", ("no-host", "one-host"), ("environment-binding",), ("environment-report",)),
    ("install-state", "OBJECTIVE", ("no-host", "one-host"), ("clean-install",), ("install-report",)),
    ("enable-disable-state", "OBJECTIVE", ("no-host", "one-host", "multi-host"), ("enable-disable",), ("state-report",)),
    ("lifecycle", "OBJECTIVE", ("no-host", "one-host", "multi-host", "fault-isolation"), ("lifecycle-control",), ("lifecycle-report",)),
    ("route-scene", "OBJECTIVE", ("one-host",), ("route-pallet-bedroom", "route-pallet-outdoor", "route-viridian-forest", "route-mt-moon", "route-celadon-mart"), ("scene-report",)),
    ("packet-golden", "OBJECTIVE", ("one-host",), ("packet-golden",), ("packet-report",)),
    ("config-audio", "OBJECTIVE", ("one-host",), ("config-audio",), ("config-report", "audio-report")),
    ("logs-captures", "OBJECTIVE", ("one-host",), ("logs-captures",), ("sanitized-log-report", "capture-index")),
    ("performance-native", "OBJECTIVE", ("one-host",), ("performance-native",), ("performance-report",)),
    ("uncached-entry", "OBJECTIVE", ("one-host",), ("uncached-entry",), ("uncached-report",)),
    ("transitions-100", "OBJECTIVE", ("one-host",), ("transitions-100",), ("transition-report",)),
    ("soak-30m", "OBJECTIVE", ("one-host",), ("soak-30m",), ("soak-report",)),
    ("leak-resource", "OBJECTIVE", ("one-host",), ("leak-resource",), ("resource-report",)),
    ("migration", "OBJECTIVE", ("one-host",), ("migration-previous",), ("migration-report",)),
    ("rollback", "OBJECTIVE", ("one-host",), ("rollback-previous",), ("rollback-report",)),
    ("uninstall-integrity", "OBJECTIVE", ("one-host",), ("uninstall-integrity",), ("uninstall-report",)),
    ("package-reproducibility", "OBJECTIVE", ("no-host",), ("package-reproducibility",), ("reproducibility-report",)),
    ("privacy-scan", "OBJECTIVE", ("no-host",), ("privacy-scan",), ("privacy-report",)),
    ("schema-validation", "OBJECTIVE", ("no-host",), ("schema-validation",), ("schema-report",)),
    ("cleanup", "OBJECTIVE", ("no-host", "one-host", "multi-host", "fault-isolation"), ("cleanup",), ("cleanup-report",)),
    ("human-visual-review", "MANUAL", ("one-host",), ("human-visual-review",), ("visual-review-packet", "manual-verdict")),
    ("physical-platform-review", "MANUAL", ("one-host",), ("physical-platform-review",), ("physical-review-packet", "manual-verdict")),
)
TEST_CLASS_IDS = tuple(spec[0] for spec in TEST_CLASS_SPECS)
TEST_POINT_SPECS = (
    ("environment-binding", "environment", "Environment and hash binding", "contract"),
    ("clean-install", "install", "Clean install state", "contract"),
    ("enable-disable", "install", "Enable disable and KFP off state", "contract"),
    ("lifecycle-control", "lifecycle", "Host and KFP lifecycle control", "contract"),
    ("route-pallet-bedroom", "route", "Pallet bedroom entry", "route"),
    ("route-pallet-outdoor", "route", "Pallet outdoor entry", "route"),
    ("route-viridian-forest", "route", "Viridian Forest entry", "route"),
    ("route-mt-moon", "route", "Mt Moon cave entry", "route"),
    ("route-celadon-mart", "route", "Celadon Mart entry", "route"),
    ("packet-golden", "scene", "Packet and golden comparison", "golden"),
    ("config-audio", "config", "Config migration and KFP only audio", "contract"),
    ("logs-captures", "environment", "Sanitized logs and captures", "contract"),
    ("performance-native", "performance", "Native performance sampling", "contract"),
    ("uncached-entry", "performance", "Uncached scene entry", "contract"),
    ("transitions-100", "transition", "One hundred transitions", "contract"),
    ("soak-30m", "soak", "Thirty minute soak", "contract"),
    ("leak-resource", "performance", "Leak and resource cleanup", "contract"),
    ("migration-previous", "migration", "Migration from previous KFP", "contract"),
    ("rollback-previous", "rollback", "Rollback to previous KFP", "contract"),
    ("uninstall-integrity", "uninstall", "Uninstall integrity", "contract"),
    (
        "package-reproducibility",
        "package",
        "Package and hash reproducibility",
        "contract",
    ),
    ("privacy-scan", "privacy", "Privacy ROM secret and path scan", "contract"),
    ("schema-validation", "schema", "Evidence schema validation", "contract"),
    ("cleanup", "cleanup", "Process and resource cleanup", "contract"),
    ("human-visual-review", "review", "Fixed visual review packet", "contract"),
    (
        "physical-platform-review",
        "review",
        "Physical platform confirmation",
        "contract",
    ),
)
TEST_POINT_IDS = tuple(item[0] for item in TEST_POINT_SPECS)
EVIDENCE_KIND_IDS = (
    "environment-report",
    "install-report",
    "state-report",
    "lifecycle-report",
    "scene-report",
    "packet-report",
    "config-report",
    "audio-report",
    "sanitized-log-report",
    "capture-index",
    "performance-report",
    "uncached-report",
    "transition-report",
    "soak-report",
    "resource-report",
    "migration-report",
    "rollback-report",
    "uninstall-report",
    "reproducibility-report",
    "privacy-report",
    "schema-report",
    "cleanup-report",
    "visual-review-packet",
    "manual-verdict",
    "physical-review-packet",
)
MANUAL_TEST_CLASS_IDS = (
    "human-visual-review",
    "physical-platform-review",
)
CELL_STATUSES = (
    "PASS",
    "FAIL",
    "BLOCKED",
    "AMBIGUOUS",
    "MISSING",
    "SKIPPED",
    "NOT_RUN",
)
BLOCKING_CELL_STATUSES = (
    "FAIL",
    "BLOCKED",
    "AMBIGUOUS",
    "MISSING",
    "SKIPPED",
    "NOT_RUN",
)
BATTLE_ART_1_9_8_PACKAGE_SHA256 = (
    "28c06d4153087be28891090d2d85d039f7cd81ba69f74c56a069016b3adf58bd"
)
HOST_PROVENANCE_V1 = {
    "battle-art-1.9.8": (
        "Battle Art 1.9.8",
        "1.9.8",
        "6586ef5f7a86c1bfefcea931bd6571538c9f8d15",
        BATTLE_ART_1_9_8_PACKAGE_SHA256,
    ),
    "dramaless-v2.0.3": (
        "Dramaless 2.0.3",
        "2.0.3",
        "23750150ae6f939e09f9ac6ca6d80c382ec9997a",
        "89f6fa078c78a6f6e34c98074ea50ff4f971eead992f27684b52eae0f4f5a1a2",
    ),
}
HOST_ELIGIBILITY_V1 = {
    "battle-art-1.9.8": (True, True, None),
    "dramaless-v2.0.3": (
        True,
        False,
        "The released package lacks the approved companion runtime",
    ),
}
REQUIRED_CELL_COUNT_V1 = 17_820
REQUIRED_CELLS_BY_GAME_V1 = {game_id: 5_940 for game_id in GAME_IDS}
PRIVATE_BINDING_COUNT_V1 = 52
PUBLIC_CANDIDATE_PROVENANCE_V1 = (
    "f84679c70c64ac7ee3380c2f3185c6ae237c6da9",
    "132490d94e75fe9abd1c268bc1bc896a93e93ff8",
    "1.0.0",
)
PUBLIC_BINDING_SET_SHA256_V1 = (
    "ba19faba48c1a463b23ffdc3474225fad85cfe0f9eaac8985508a41fcb90796e"
)
PUBLIC_SYNTHETIC_HASHES_V1 = frozenset(
    (
        "957f5ae3025adacf4fc4c57c347854814d955e22f174eaa3603957391f370ad6",
        "9dbfe518f33edf9c8a8be2a0bea5e0cc37f3cda7da1b3a19a90636362f1e7647",
        "6f68da1e15edfe54bbbde627acf4e9cebdca02a591c05c6833832506d5c5ca34",
        "16b741d9919f92c6329bc1bc90d9478291e1e10aff045d763379945c2147b48a",
        "2ee8b7a40eb2fb540d06c7f28dfa273ac406df5cca5fcf0319a2c15824593237",
        "8dad65257bb2a1454d77df778a5885b9a88e9cfeacc9fc6c69b9acb4103dda6e",
        "78fb9161ee49bc5a4bf8eadeba537aad5831253006abf30eb5cb83cb57699408",
        "3d0efef014b8fba68773662a3b5015424c2c3888bc65f08620e7505f272a5aaa",
        "5f1acfc7d2199b0f79f72b2caabfbca924f04456a027691f2f4f191cc201b404",
        "f07e1493e00b6da4eb6048c7e03b5831f650bef5133ad3cf2d2691617ed8a3de",
        "86e84e35e3b9c9f6ddb1adf22bc6373e775af4b445efdcb3fc23e4e52b9934d5",
        "35e2cc3225d324ccad076216a18cdffd9e4e2c740eaab312396e69090fbbfe63",
        "b597a9b201de8e9763858382cd3e0795e1b83b888e72f3fe9d995d46f55df4d9",
        "1ed48cefbe531d0c4211523a05a9cf5ba4c3e3101fd289f41c4c3af3b4fe743b",
        "bc9aa5b97ffd94c7a8be0063f88b9277970375d3a8b725b7e99ccd1cb7a51bb8",
        "ef9339b84ad977a3c3e0bd130b9bef369dc56d61c25b3d15840a4a5811956021",
        "befad2e817a5f1ea55ea8224da1719e91a7307517f4251fe620bb62d0908de91",
        "fb4669100c83ee29d4ffd12bafe62da2ccb40e2f9691bd4fc1f6507c9364348c",
        "3a59a50d08f7927026441e1e2e70e03451cf54c836694ba7784eb2253979560a",
        "b86d85ac1c676ab72f871ec79513f13a25f074fc84f4920b3991eba6d002e9c0",
        "dc60d9ffc93a6d02ec6363f898aa8a6f3a40a54c85c140be86c9b26b80cde394",
        "0accd49551d1dc3048944059b29eaa8fcdf58ffa1f1bb4af65c3d586fa84e86f",
        "e497fffe1fff86b3cf43be8e0001a3231bd93296cc6d25dee20833258e6485ce",
        "e43a9fa32d92453106d7dfd045f342d80a35ba765a516bccb1292690b8a555fb",
        "0655588523e9281ef4009a36413dc74b2aab072c7d03a3972af763cb570ce2d1",
        "2895a694708f26872b6dd72fcf40c5f158b5cc974918b44031aaa3753ce4b757",
        "c8ba85122b3dac594fe5ef3c4c42b3e4ce4ed6f4ffb09303f8011667026a9545",
        "7201c7b6e12913dd13d8c5edd1d4ed84e19f3269cb89fe9049dd4395b33b1b41",
        "2a2f04c30f76b4876f3134f18e8ece7a2be1dc0021989fe22c1a3258b50be1ba",
        "115be82f95615bc0d9259476cdb1f7a61d77b768360034b775d24e081065ba38",
        "8f7513e52d79e017b87790fecce28b15c896010ebabdd7c4646349c488b38fd6",
        "98132a28fa68d5679d32457d57c190e405cba53604795e82b6825f92d3050b0d",
        "4980d13df46618b5eb17e81a23ba9a690e35d80e84a67c31b939c76cecf37061",
        "858047bc177445e2117153cb90b7ce88278dda20294021f8750b301f79bad0d6",
        "ca7c26ffc9921208faf0bcb5c0a1ad7a25f0ee8a49cab65a5866e6930ff4eef8",
        "d965cd9a6614c9ee676bbc79142d9b3a674fb159e7659f1c3b7afeb686e76c24",
        "c1a5d7a4af79c6be5c8fde4240ac7117b9727a13c06d82567529233ff7aebea3",
        "965ddf772e3ce2517b45beeedafb04bab0580210673d835f3752b8ad4336b22d",
        "d32de03d110ceefbbaf3a6588847ae2b98831702facc15b280f789c990103dba",
        "536ecbe7070366f073f886fcff104190a5316d8470ad55ea5af8e9d86abd65fd",
        "7264445dd1e888ec82b170aa7c7a9486be92e7dd401726286dd24723ac3bf334",
        "4ea71ae7673e2eced0d3c70eb96747ee653e22bde61930da052c9355d3872609",
        "bf50ac8046d4784ef5eb4cdfd927abbbda5f02b700381c762fd374ada49ad50c",
        "e3fbd28a143f2ac789d198f5dab2acde8d1ee80077e1f20829385fc3b5e634b9",
        "9343c4f28c11ed4b5f1863e97228b5f789edf2b997497b3bde0f5c9ec6be7c6f",
        "ba3c836a44d5b1f6a7f8f29a0d28eff018a7762f54356e0f3a02bedfe3f799c1",
        "5b195db0468a3b04dc0a686638ba4cb50a2a030255d10197b7bba45229060021",
        "d35da2828946ac94052e4b9dba1dad6ad1f752bdbdb5ab63542edd6e3ae691bc",
        "6d39a84e1b17d33dc8e128f398f6984e6c0eef6fb437251e772c3b74e0db28d3",
        "7f5fb710c83255e19abf9fd5812e5e703a9645b3ea01e09d57abf8f82dbd0b0b",
        "90ce401faae60527152a9f89f88eae31976f2ffd19330e740d948d255f6a257d",
        "aa1aafaec6336b4aeeb9d155a68519a679cdc5fd5f19e2ed7dd802d4995daf26",
    )
)

_ID_RE = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")
_LABEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._+()'/-]*$")
_VERSION_RE = re.compile(r"^[0-9A-Za-z][0-9A-Za-z.+_-]*$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_CELL_ID_RE = re.compile(r"^cell-[0-9a-f]{64}$")
_ATTEMPT_ID_RE = re.compile(r"^attempt-[0-9a-f]{64}$")
_LEDGER_ROOT_ID_RE = re.compile(r"^ledger-root-[0-9a-f]{64}$")
_RECOVERY_ID_RE = re.compile(r"^recovery-[0-9a-f]{64}$")
_UTC_RE = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"
)


class MatrixModelError(ValueError):
    """Controlled model rejection with a stable public-safe code."""

    def __init__(self, code: str, path: str = "$") -> None:
        self.code = code
        self.path = path
        super().__init__(f"{code} at {path}")


class _DuplicateKeyError(ValueError):
    pass


def _object_no_duplicates(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError("duplicate JSON key")
        result[key] = value
    return result


def strict_json_loads(data: bytes | str, *, max_bytes: int = 8_388_608) -> Any:
    """Parse strict UTF-8 JSON and reject duplicates and non-finite numbers."""

    if isinstance(data, bytes):
        if len(data) > max_bytes:
            raise MatrixModelError("E_JSON_TOO_LARGE")
        if data.startswith(b"\xef\xbb\xbf"):
            raise MatrixModelError("E_JSON_BOM")
        try:
            text = data.decode("utf-8", "strict")
        except UnicodeDecodeError as exc:
            raise MatrixModelError("E_JSON_UTF8") from exc
    elif type(data) is str:
        try:
            encoded_size = len(data.encode("utf-8", "strict"))
        except UnicodeEncodeError as exc:
            raise MatrixModelError("E_JSON_UTF8") from exc
        if encoded_size > max_bytes:
            raise MatrixModelError("E_JSON_TOO_LARGE")
        if data.startswith("\ufeff"):
            raise MatrixModelError("E_JSON_BOM")
        text = data
    else:
        raise MatrixModelError("E_JSON_INPUT_TYPE")

    def reject_constant(_: str) -> None:
        raise MatrixModelError("E_JSON_NONFINITE")

    try:
        return json.loads(
            text,
            object_pairs_hook=_object_no_duplicates,
            parse_constant=reject_constant,
        )
    except MatrixModelError:
        raise
    except _DuplicateKeyError as exc:
        raise MatrixModelError("E_JSON_DUPLICATE_KEY") from exc
    except (ValueError, RecursionError) as exc:
        raise MatrixModelError("E_JSON_INVALID") from exc


def strict_json_load(path: Path | str, *, max_bytes: int = 8_388_608) -> Any:
    candidate = Path(path)
    try:
        data = candidate.read_bytes()
    except OSError as exc:
        raise MatrixModelError("E_JSON_READ") from exc
    return strict_json_loads(data, max_bytes=max_bytes)


def _assert_canonical_value(value: Any, path: str = "$") -> None:
    if value is None or type(value) in (bool, int, str):
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise MatrixModelError("E_JSON_NONFINITE", path)
        raise MatrixModelError("E_CANONICAL_FLOAT", path)
    if type(value) is list:
        for index, item in enumerate(value):
            _assert_canonical_value(item, f"{path}[{index}]")
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise MatrixModelError("E_CANONICAL_KEY_TYPE", path)
            _assert_canonical_value(item, f"{path}.{key}")
        return
    raise MatrixModelError("E_CANONICAL_TYPE", path)


def canonical_json_bytes(value: Any) -> bytes:
    """Encode one stable JSON record with LF termination."""

    try:
        _assert_canonical_value(value)
    except MatrixModelError:
        raise
    except RecursionError as exc:
        raise MatrixModelError("E_CANONICAL_RECURSION") from exc
    try:
        text = json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError, RecursionError) as exc:
        raise MatrixModelError("E_CANONICAL_ENCODE") from exc
    return text.encode("ascii") + b"\n"


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def make_evidence_binding(
    cell: MatrixCell,
    attempt_id: str,
    gate_id: str,
    kind: str,
    sha256: str,
    byte_count: int,
) -> Mapping[str, Any]:
    """Create one public-safe binding for a private evidence payload."""

    basis = {
        "schema": EVIDENCE_BINDING_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "cell_id": cell.cell_id,
        "input_fingerprint": cell.input_fingerprint,
        "attempt_id": attempt_id,
        "gate_id": gate_id,
        "kind": kind,
        "sha256": sha256,
        "bytes": byte_count,
    }
    record = {**basis, "binding_sha256": sha256_value(basis)}
    return validate_evidence_binding(
        record,
        cell,
        attempt_id=attempt_id,
        gate_id=gate_id,
    )


def validate_evidence_binding(
    record: Any,
    cell: MatrixCell,
    *,
    attempt_id: str | None = None,
    gate_id: str | None = None,
    allowed_gate_ids: Iterable[str] | None = None,
    path: str = "$",
) -> Mapping[str, Any]:
    """Reject evidence that is not bound to the exact cell, attempt, and gate."""

    value = _expect_mapping(record, path)
    try:
        _expect_exact_keys(value, EVIDENCE_BINDING_FIELDS, path)
    except MatrixModelError as exc:
        raise MatrixModelError("E_EVIDENCE_BINDING_FIELDS", path) from exc
    if value["schema"] != EVIDENCE_BINDING_SCHEMA:
        raise MatrixModelError("E_EVIDENCE_BINDING_SCHEMA", f"{path}.schema")
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise MatrixModelError(
            "E_EVIDENCE_BINDING_SCHEMA", f"{path}.schema_version"
        )
    checked_cell_id = _expect_string(
        value["cell_id"],
        f"{path}.cell_id",
        pattern=_CELL_ID_RE,
        minimum=69,
        maximum=69,
    )
    checked_fingerprint = _expect_sha(
        value["input_fingerprint"], f"{path}.input_fingerprint"
    )
    if (
        checked_cell_id != cell.cell_id
        or checked_fingerprint != cell.input_fingerprint
    ):
        raise MatrixModelError("E_EVIDENCE_BINDING_CELL", path)
    checked_attempt = _expect_string(
        value["attempt_id"],
        f"{path}.attempt_id",
        pattern=_ATTEMPT_ID_RE,
        minimum=72,
        maximum=72,
    )
    if attempt_id is not None and checked_attempt != attempt_id:
        raise MatrixModelError("E_EVIDENCE_BINDING_ATTEMPT", f"{path}.attempt_id")
    checked_gate = _expect_id(value["gate_id"], f"{path}.gate_id")
    if gate_id is not None and checked_gate != gate_id:
        raise MatrixModelError("E_EVIDENCE_BINDING_GATE", f"{path}.gate_id")
    if allowed_gate_ids is not None and checked_gate not in tuple(allowed_gate_ids):
        raise MatrixModelError("E_EVIDENCE_BINDING_GATE", f"{path}.gate_id")
    _expect_id(value["kind"], f"{path}.kind")
    _expect_sha(value["sha256"], f"{path}.sha256")
    _expect_int(value["bytes"], f"{path}.bytes", 1, MAX_EVIDENCE_BYTES)
    checked_binding = _expect_sha(
        value["binding_sha256"], f"{path}.binding_sha256"
    )
    basis = {field: value[field] for field in EVIDENCE_BINDING_FIELDS[:-1]}
    if checked_binding != sha256_value(basis):
        raise MatrixModelError("E_EVIDENCE_BINDING_DIGEST", f"{path}.binding_sha256")
    _assert_canonical_value(value, path)
    return deepcopy(dict(value))


def make_evidence_receipt(
    evidence: Mapping[str, Any],
    cell: MatrixCell,
    ledger_root_id: str,
    *,
    attempt_id: str,
    gate_id: str,
) -> Mapping[str, Any]:
    """Bind one first-store evidence record to one immutable ledger root."""

    checked_evidence = validate_evidence_binding(
        evidence,
        cell,
        attempt_id=attempt_id,
        gate_id=gate_id,
        path="$.evidence",
    )
    checked_root_id = _expect_string(
        ledger_root_id,
        "$.ledger_root_id",
        pattern=_LEDGER_ROOT_ID_RE,
        minimum=76,
        maximum=76,
    )
    basis = {
        "schema": EVIDENCE_RECEIPT_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "ledger_root_id": checked_root_id,
        "evidence": checked_evidence,
    }
    return {**basis, "receipt_sha256": sha256_value(basis)}


def validate_evidence_receipt(
    receipt: Any,
    cell: MatrixCell,
    ledger_root_id: str,
    *,
    attempt_id: str,
    gate_id: str | None = None,
    allowed_gate_ids: Iterable[str] | None = None,
    path: str = "$",
) -> Mapping[str, Any]:
    """Reject a receipt not bound to the exact root and evidence record."""

    value = _expect_mapping(receipt, path)
    if set(value) != set(EVIDENCE_RECEIPT_FIELDS):
        raise MatrixModelError("E_EVIDENCE_RECEIPT_FIELDS", path)
    if value["schema"] != EVIDENCE_RECEIPT_SCHEMA:
        raise MatrixModelError("E_EVIDENCE_RECEIPT_SCHEMA", f"{path}.schema")
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise MatrixModelError(
            "E_EVIDENCE_RECEIPT_SCHEMA", f"{path}.schema_version"
        )
    checked_root_id = _expect_string(
        value["ledger_root_id"],
        f"{path}.ledger_root_id",
        pattern=_LEDGER_ROOT_ID_RE,
        minimum=76,
        maximum=76,
    )
    if checked_root_id != ledger_root_id:
        raise MatrixModelError("E_EVIDENCE_RECEIPT_ROOT", f"{path}.ledger_root_id")
    checked_evidence = validate_evidence_binding(
        value["evidence"],
        cell,
        attempt_id=attempt_id,
        gate_id=gate_id,
        allowed_gate_ids=allowed_gate_ids,
        path=f"{path}.evidence",
    )
    checked_digest = _expect_sha(
        value["receipt_sha256"], f"{path}.receipt_sha256"
    )
    basis = {
        "schema": value["schema"],
        "schema_version": value["schema_version"],
        "ledger_root_id": value["ledger_root_id"],
        "evidence": value["evidence"],
    }
    if checked_digest != sha256_value(basis):
        raise MatrixModelError(
            "E_EVIDENCE_RECEIPT_DIGEST", f"{path}.receipt_sha256"
        )
    _assert_canonical_value(value, path)
    result = deepcopy(dict(value))
    result["evidence"] = checked_evidence
    return result


def _expect_mapping(value: Any, path: str) -> Mapping[str, Any]:
    if type(value) is not dict:
        raise MatrixModelError("E_TYPE_OBJECT", path)
    return value


def _expect_list(value: Any, path: str) -> list[Any]:
    if type(value) is not list:
        raise MatrixModelError("E_TYPE_ARRAY", path)
    return value


def _expect_exact_keys(
    value: Mapping[str, Any], expected: Iterable[str], path: str
) -> None:
    expected_set = set(expected)
    actual_set = set(value)
    if actual_set != expected_set:
        if expected_set - actual_set:
            raise MatrixModelError("E_REQUIRED_FIELD", path)
        raise MatrixModelError("E_UNKNOWN_FIELD", path)


def _expect_string(
    value: Any,
    path: str,
    *,
    pattern: re.Pattern[str] | None = None,
    allowed: Iterable[str] | None = None,
    minimum: int = 1,
    maximum: int = 160,
) -> str:
    if type(value) is not str:
        raise MatrixModelError("E_TYPE_STRING", path)
    if not minimum <= len(value) <= maximum:
        raise MatrixModelError("E_STRING_LENGTH", path)
    if pattern is not None and pattern.fullmatch(value) is None:
        raise MatrixModelError("E_STRING_FORMAT", path)
    if allowed is not None and value not in allowed:
        raise MatrixModelError("E_ENUM", path)
    return value


def _expect_label(value: Any, path: str) -> str:
    return _expect_string(value, path, pattern=_LABEL_RE, maximum=96)


def _expect_version(value: Any, path: str) -> str:
    return _expect_string(value, path, pattern=_VERSION_RE, maximum=32)


def _expect_bool(value: Any, path: str) -> bool:
    if type(value) is not bool:
        raise MatrixModelError("E_TYPE_BOOLEAN", path)
    return value


def _expect_int(
    value: Any,
    path: str,
    minimum: int = 0,
    maximum: int | None = None,
) -> int:
    if type(value) is not int:
        raise MatrixModelError("E_TYPE_INTEGER", path)
    if value < minimum or (maximum is not None and value > maximum):
        raise MatrixModelError("E_INTEGER_RANGE", path)
    return value


def _expect_id(value: Any, path: str) -> str:
    return _expect_string(value, path, pattern=_ID_RE, maximum=96)


def _expect_sha(value: Any, path: str) -> str:
    return _expect_string(value, path, pattern=_SHA256_RE, minimum=64, maximum=64)


def _expect_commit(value: Any, path: str) -> str:
    return _expect_string(value, path, pattern=_COMMIT_RE, minimum=40, maximum=40)


def _parse_utc(value: Any, path: str) -> datetime:
    text = _expect_string(value, path, pattern=_UTC_RE, minimum=20, maximum=20)
    try:
        parsed = datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise MatrixModelError("E_TIMESTAMP", path) from exc
    return parsed


def _expect_unique_ids(
    records: Any,
    path: str,
    *,
    exact_ids: Sequence[str] | None = None,
    maximum: int | None = None,
) -> list[Mapping[str, Any]]:
    values = _expect_list(records, path)
    if not values:
        raise MatrixModelError("E_EMPTY_CATALOG", path)
    if maximum is not None and len(values) > maximum:
        raise MatrixModelError("E_ARRAY_LENGTH", path)
    result: list[Mapping[str, Any]] = []
    ids: list[str] = []
    for index, raw in enumerate(values):
        record = _expect_mapping(raw, f"{path}[{index}]")
        identifier = _expect_id(record.get("id"), f"{path}[{index}].id")
        if identifier in ids:
            raise MatrixModelError("E_DUPLICATE_ID", f"{path}[{index}].id")
        ids.append(identifier)
        result.append(record)
    if exact_ids is not None and tuple(ids) != tuple(exact_ids):
        raise MatrixModelError("E_CATALOG_IDENTITY", path)
    return result


def _expect_exact_string_list(
    value: Any, path: str, expected: Sequence[str]
) -> list[str]:
    values = _expect_list(value, path)
    for index, item in enumerate(values):
        _expect_string(item, f"{path}[{index}]", maximum=96)
    if tuple(values) != tuple(expected):
        raise MatrixModelError("E_ORDERED_SET", path)
    return values


def _expect_unique_string_list(
    value: Any,
    path: str,
    *,
    allowed: Sequence[str] | None = None,
    id_format: bool = False,
    maximum: int | None = None,
) -> list[str]:
    values = _expect_list(value, path)
    if not values:
        raise MatrixModelError("E_EMPTY_SET", path)
    if maximum is not None and len(values) > maximum:
        raise MatrixModelError("E_ARRAY_LENGTH", path)
    checked: list[str] = []
    for index, item in enumerate(values):
        item_path = f"{path}[{index}]"
        text = _expect_id(item, item_path) if id_format else _expect_string(
            item, item_path, maximum=96
        )
        if allowed is not None and text not in allowed:
            raise MatrixModelError("E_REFERENCE", item_path)
        if text in checked:
            raise MatrixModelError("E_DUPLICATE_VALUE", item_path)
        checked.append(text)
    return checked


def synthetic_binding_sha256(
    manifest_id: str,
    kind: str,
    binding_id: str,
    attributes: Mapping[str, Any],
) -> str:
    """Return the digest of one public synthetic binding descriptor."""

    checked_manifest_id = _expect_id(manifest_id, "$.manifest_id")
    checked_kind = _expect_id(kind, "$.kind")
    checked_binding_id = _expect_id(binding_id, "$.binding_id")
    checked_attributes = _expect_mapping(attributes, "$.attributes")
    descriptor = {
        "schema": SYNTHETIC_BINDING_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "manifest_id": checked_manifest_id,
        "kind": checked_kind,
        "binding_id": checked_binding_id,
        "attributes": deepcopy(dict(checked_attributes)),
    }
    return sha256_value(descriptor)


def _expect_synthetic_binding(
    actual: Any,
    path: str,
    manifest_id: str,
    kind: str,
    binding_id: str,
    attributes: Mapping[str, Any],
) -> None:
    digest = _expect_sha(actual, path)
    expected = synthetic_binding_sha256(
        manifest_id, kind, binding_id, attributes
    )
    if digest != expected:
        raise MatrixModelError("E_SYNTHETIC_BINDING", path)


def _binding_records(
    candidate: Mapping[str, Any], catalogs: Mapping[str, Any]
) -> tuple[dict[str, str], ...]:
    """Return the exact ordered v1 set of opaque runtime binding hashes."""

    records: list[dict[str, str]] = []

    def add(path: str, value: Any) -> None:
        records.append({"path": path, "sha256": _expect_sha(value, path)})

    for name in (
        "runtime_content_sha256",
        "package_sha256",
        "adapter_sha256",
    ):
        add(f"candidate.{name}", candidate[name])
    for game in catalogs["games"]:
        add(
            f"catalogs.games.{game['id']}.adapter_sha256",
            game["adapter_sha256"],
        )
    for engine in catalogs["engines"]:
        add(
            f"catalogs.engines.{engine['id']}.runtime_sha256",
            engine["runtime_sha256"],
        )
    for platform in catalogs["platforms"]:
        add(
            f"catalogs.platforms.{platform['id']}.adapter_sha256",
            platform["adapter_sha256"],
        )
    for host_mode in catalogs["host_modes"]:
        add(
            f"catalogs.host_modes.{host_mode['id']}.fixture_sha256",
            host_mode["fixture_sha256"],
        )
    for point in catalogs["test_points"]:
        for binding in point["required_input_hashes"]:
            add(
                "catalogs.test_points."
                f"{point['id']}.{binding['id']}.sha256",
                binding["sha256"],
            )
    if len(records) != PRIVATE_BINDING_COUNT_V1:
        raise MatrixModelError("E_BINDING_COUNT", "$.binding_acquisition")
    return tuple(records)


def _binding_set_sha256(records: Sequence[Mapping[str, Any]]) -> str:
    return sha256_value(
        {
            "schema": BINDING_SET_SCHEMA,
            "schema_version": SCHEMA_VERSION,
            "bindings": [deepcopy(dict(record)) for record in records],
        }
    )


def derive_binding_acquisition(
    manifest: Any,
    *,
    state: str,
    acquisition_record_sha256: str | None,
) -> Mapping[str, Any]:
    """Derive a public-safe acquisition binding without private values."""

    value = _expect_mapping(manifest, "$")
    candidate = _expect_mapping(value.get("candidate"), "$.candidate")
    catalogs = _expect_mapping(value.get("catalogs"), "$.catalogs")
    records = _binding_records(candidate, catalogs)
    checked_state = _expect_string(
        state,
        "$.binding_acquisition.state",
        allowed=("PUBLIC_SYNTHETIC", "ACQUIRED_PRIVATE"),
        maximum=32,
    )
    if checked_state == "PUBLIC_SYNTHETIC":
        if acquisition_record_sha256 is not None:
            raise MatrixModelError(
                "E_BINDING_ACQUISITION_RECORD",
                "$.binding_acquisition.acquisition_record_sha256",
            )
        record_schema = None
    else:
        _expect_sha(
            acquisition_record_sha256,
            "$.binding_acquisition.acquisition_record_sha256",
        )
        record_schema = PRIVATE_BINDING_ACQUISITION_SCHEMA
    return {
        "schema": BINDING_ACQUISITION_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "state": checked_state,
        "binding_count": len(records),
        "binding_set_sha256": _binding_set_sha256(records),
        "acquisition_record_schema": record_schema,
        "acquisition_record_sha256": acquisition_record_sha256,
    }


def _validate_binding_acquisition(
    acquisition: Any,
    mode: str,
    candidate: Mapping[str, Any],
    catalogs: Mapping[str, Any],
) -> None:
    path = "$.binding_acquisition"
    value = _expect_mapping(acquisition, path)
    _expect_exact_keys(
        value,
        (
            "schema",
            "schema_version",
            "state",
            "binding_count",
            "binding_set_sha256",
            "acquisition_record_schema",
            "acquisition_record_sha256",
        ),
        path,
    )
    _expect_string(
        value["schema"], path + ".schema", allowed=(BINDING_ACQUISITION_SCHEMA,)
    )
    if _expect_int(value["schema_version"], path + ".schema_version", 1, 1) != 1:
        raise MatrixModelError("E_SCHEMA_VERSION", path + ".schema_version")
    records = _binding_records(candidate, catalogs)
    count = _expect_int(
        value["binding_count"], path + ".binding_count", 1, PRIVATE_BINDING_COUNT_V1
    )
    digest = _expect_sha(
        value["binding_set_sha256"], path + ".binding_set_sha256"
    )
    if count != PRIVATE_BINDING_COUNT_V1 or digest != _binding_set_sha256(records):
        raise MatrixModelError("E_BINDING_SET", path)
    state = _expect_string(
        value["state"],
        path + ".state",
        allowed=("PUBLIC_SYNTHETIC", "ACQUIRED_PRIVATE"),
        maximum=32,
    )
    if mode == "PUBLIC_SYNTHETIC":
        if (
            state != "PUBLIC_SYNTHETIC"
            or value["acquisition_record_schema"] is not None
            or value["acquisition_record_sha256"] is not None
            or digest != PUBLIC_BINDING_SET_SHA256_V1
            or frozenset(record["sha256"] for record in records)
            != PUBLIC_SYNTHETIC_HASHES_V1
        ):
            raise MatrixModelError("E_PUBLIC_BINDING_ACQUISITION", path)
        return
    if state != "ACQUIRED_PRIVATE":
        raise MatrixModelError("E_PRIVATE_BINDING_ACQUISITION", path + ".state")
    _expect_string(
        value["acquisition_record_schema"],
        path + ".acquisition_record_schema",
        allowed=(PRIVATE_BINDING_ACQUISITION_SCHEMA,),
        maximum=96,
    )
    _expect_sha(
        value["acquisition_record_sha256"],
        path + ".acquisition_record_sha256",
    )
    for record in records:
        if record["sha256"] in PUBLIC_SYNTHETIC_HASHES_V1:
            raise MatrixModelError("E_PRIVATE_PUBLIC_BINDING", record["path"])


def _validate_candidate(
    candidate: Any,
    mode: str,
    release_eligible: bool,
    manifest_id: str,
) -> None:
    path = "$.candidate"
    value = _expect_mapping(candidate, path)
    _expect_exact_keys(
        value,
        (
            "runtime_source_commit",
            "runtime_source_tree",
            "runtime_content_sha256",
            "package_kind",
            "package_sha256",
            "adapter_version",
            "adapter_sha256",
        ),
        path,
    )
    _expect_commit(
        value["runtime_source_commit"], f"{path}.runtime_source_commit"
    )
    _expect_commit(value["runtime_source_tree"], f"{path}.runtime_source_tree")
    _expect_sha(
        value["runtime_content_sha256"], f"{path}.runtime_content_sha256"
    )
    package_kind = _expect_string(
        value["package_kind"],
        f"{path}.package_kind",
        allowed=("SYNTHETIC_FIXTURE", "RELEASE_CANDIDATE"),
        maximum=32,
    )
    _expect_sha(value["package_sha256"], f"{path}.package_sha256")
    _expect_string(
        value["adapter_version"],
        f"{path}.adapter_version",
        pattern=re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$"),
        maximum=32,
    )
    _expect_sha(value["adapter_sha256"], f"{path}.adapter_sha256")
    if mode == "PUBLIC_SYNTHETIC":
        if release_eligible or package_kind != "SYNTHETIC_FIXTURE":
            raise MatrixModelError("E_SYNTHETIC_RELEASE_ELIGIBILITY", path)
        if (
            value["runtime_source_commit"],
            value["runtime_source_tree"],
            value["adapter_version"],
        ) != PUBLIC_CANDIDATE_PROVENANCE_V1:
            raise MatrixModelError("E_CANDIDATE_PROVENANCE", path)
        _expect_synthetic_binding(
            value["runtime_content_sha256"],
            f"{path}.runtime_content_sha256",
            manifest_id,
            "runtime-content",
            "runtime-content",
            {
                "runtime_source_commit": value["runtime_source_commit"],
                "runtime_source_tree": value["runtime_source_tree"],
            },
        )
        _expect_synthetic_binding(
            value["package_sha256"],
            f"{path}.package_sha256",
            manifest_id,
            "candidate-package",
            "candidate-package",
            {
                "runtime_source_commit": value["runtime_source_commit"],
                "runtime_source_tree": value["runtime_source_tree"],
                "runtime_content_sha256": value["runtime_content_sha256"],
                "package_kind": package_kind,
            },
        )
        _expect_synthetic_binding(
            value["adapter_sha256"],
            f"{path}.adapter_sha256",
            manifest_id,
            "matrix-adapter",
            "matrix-adapter",
            {
                "runtime_source_commit": value["runtime_source_commit"],
                "runtime_source_tree": value["runtime_source_tree"],
                "runtime_content_sha256": value["runtime_content_sha256"],
                "adapter_version": value["adapter_version"],
            },
        )
    elif not release_eligible or package_kind != "RELEASE_CANDIDATE":
        raise MatrixModelError("E_PRIVATE_RELEASE_BINDING", path)


def _validate_catalogs(catalogs: Any, mode: str, manifest_id: str) -> None:
    path = "$.catalogs"
    value = _expect_mapping(catalogs, path)
    _expect_exact_keys(
        value,
        (
            "games",
            "hosts",
            "engines",
            "tiers",
            "platforms",
            "host_modes",
            "test_points",
            "test_classes",
        ),
        path,
    )

    games = _expect_unique_ids(value["games"], f"{path}.games", exact_ids=GAME_IDS)
    for index, game in enumerate(games):
        item_path = f"{path}.games[{index}]"
        _expect_exact_keys(
            game,
            ("id", "label", "adapter_id", "adapter_sha256", "private_input"),
            item_path,
        )
        _expect_label(game["label"], f"{item_path}.label")
        _expect_id(game["adapter_id"], f"{item_path}.adapter_id")
        _expect_sha(game["adapter_sha256"], f"{item_path}.adapter_sha256")
        _expect_string(
            game["private_input"],
            f"{item_path}.private_input",
            allowed=("OPAQUE_RUNTIME_ONLY",),
            maximum=32,
        )
        if mode == "PUBLIC_SYNTHETIC":
            _expect_synthetic_binding(
                game["adapter_sha256"],
                f"{item_path}.adapter_sha256",
                manifest_id,
                "game-adapter",
                game["adapter_id"],
                {
                    "game_id": game["id"],
                    "private_input": game["private_input"],
                },
            )

    hosts = _expect_unique_ids(
        value["hosts"],
        f"{path}.hosts",
        exact_ids=("battle-art-1.9.8", "dramaless-v2.0.3"),
    )
    eligible_hosts = 0
    for index, host in enumerate(hosts):
        item_path = f"{path}.hosts[{index}]"
        _expect_exact_keys(
            host,
            (
                "id",
                "label",
                "version",
                "source_commit",
                "package_sha256",
                "released",
                "eligible",
                "exclusion_reason",
            ),
            item_path,
        )
        label = _expect_label(host["label"], f"{item_path}.label")
        version = _expect_version(host["version"], f"{item_path}.version")
        commit = _expect_commit(host["source_commit"], f"{item_path}.source_commit")
        package = _expect_sha(host["package_sha256"], f"{item_path}.package_sha256")
        if (label, version, commit, package) != HOST_PROVENANCE_V1[host["id"]]:
            raise MatrixModelError("E_HOST_PROVENANCE", item_path)
        released = _expect_bool(host["released"], f"{item_path}.released")
        eligible = _expect_bool(host["eligible"], f"{item_path}.eligible")
        reason = host["exclusion_reason"]
        expected_released, expected_eligible, expected_reason = (
            HOST_ELIGIBILITY_V1[host["id"]]
        )
        if (
            released != expected_released
            or eligible != expected_eligible
            or reason != expected_reason
        ):
            raise MatrixModelError("E_HOST_ELIGIBILITY_BINDING", item_path)
        if eligible:
            eligible_hosts += 1
            if not released or reason is not None:
                raise MatrixModelError("E_HOST_ELIGIBILITY", item_path)
        else:
            _expect_string(reason, f"{item_path}.exclusion_reason", maximum=160)
    if eligible_hosts < 1:
        raise MatrixModelError("E_NO_ELIGIBLE_RELEASED_HOST", f"{path}.hosts")

    engines = _expect_unique_ids(
        value["engines"], f"{path}.engines", exact_ids=ENGINE_IDS
    )
    for index, engine in enumerate(engines):
        item_path = f"{path}.engines[{index}]"
        _expect_exact_keys(
            engine,
            (
                "id",
                "label",
                "version",
                "source_commit",
                "runtime_sha256",
                "binding_kind",
            ),
            item_path,
        )
        label = _expect_label(engine["label"], f"{item_path}.label")
        version = _expect_version(engine["version"], f"{item_path}.version")
        commit = _expect_commit(engine["source_commit"], f"{item_path}.source_commit")
        if (label, version, commit) != ENGINE_PROVENANCE_V1[engine["id"]]:
            raise MatrixModelError("E_ENGINE_PROVENANCE", item_path)
        _expect_sha(engine["runtime_sha256"], f"{item_path}.runtime_sha256")
        binding_kind = _expect_string(
            engine["binding_kind"],
            f"{item_path}.binding_kind",
            allowed=("SYNTHETIC_FIXTURE", "PINNED_RUNTIME"),
            maximum=32,
        )
        expected_kind = (
            "SYNTHETIC_FIXTURE" if mode == "PUBLIC_SYNTHETIC" else "PINNED_RUNTIME"
        )
        if binding_kind != expected_kind:
            raise MatrixModelError("E_ENGINE_BINDING_KIND", item_path)
        if mode == "PUBLIC_SYNTHETIC":
            _expect_synthetic_binding(
                engine["runtime_sha256"],
                f"{item_path}.runtime_sha256",
                manifest_id,
                "engine-runtime",
                engine["id"],
                {
                    "version": engine["version"],
                    "source_commit": engine["source_commit"],
                    "binding_kind": binding_kind,
                },
            )

    tiers = _expect_unique_ids(value["tiers"], f"{path}.tiers", exact_ids=TIER_IDS)
    for index, tier in enumerate(tiers):
        item_path = f"{path}.tiers[{index}]"
        _expect_exact_keys(tier, ("id", "label"), item_path)
        _expect_label(tier["label"], f"{item_path}.label")

    platforms = _expect_unique_ids(
        value["platforms"], f"{path}.platforms", exact_ids=PLATFORM_IDS
    )
    for index, platform in enumerate(platforms):
        item_path = f"{path}.platforms[{index}]"
        _expect_exact_keys(
            platform,
            (
                "id",
                "label",
                "claimed",
                "adapter_id",
                "adapter_sha256",
                "physical_confirmation_required",
            ),
            item_path,
        )
        _expect_label(platform["label"], f"{item_path}.label")
        if not _expect_bool(platform["claimed"], f"{item_path}.claimed"):
            raise MatrixModelError("E_REQUIRED_PLATFORM_UNCLAIMED", item_path)
        _expect_id(platform["adapter_id"], f"{item_path}.adapter_id")
        _expect_sha(platform["adapter_sha256"], f"{item_path}.adapter_sha256")
        _expect_bool(
            platform["physical_confirmation_required"],
            f"{item_path}.physical_confirmation_required",
        )
        if mode == "PUBLIC_SYNTHETIC":
            _expect_synthetic_binding(
                platform["adapter_sha256"],
                f"{item_path}.adapter_sha256",
                manifest_id,
                "platform-adapter",
                platform["adapter_id"],
                {
                    "platform_id": platform["id"],
                    "physical_confirmation_required": platform[
                        "physical_confirmation_required"
                    ],
                },
            )

    modes = _expect_unique_ids(
        value["host_modes"], f"{path}.host_modes", exact_ids=HOST_MODE_IDS
    )
    for index, host_mode in enumerate(modes):
        item_path = f"{path}.host_modes[{index}]"
        _expect_exact_keys(host_mode, ("id", "label", "fixture_sha256"), item_path)
        _expect_label(host_mode["label"], f"{item_path}.label")
        _expect_sha(host_mode["fixture_sha256"], f"{item_path}.fixture_sha256")
        if mode == "PUBLIC_SYNTHETIC":
            _expect_synthetic_binding(
                host_mode["fixture_sha256"],
                f"{item_path}.fixture_sha256",
                manifest_id,
                "host-mode-fixture",
                host_mode["id"],
                {"host_mode_id": host_mode["id"]},
            )

    points = _expect_unique_ids(
        value["test_points"],
        f"{path}.test_points",
        exact_ids=TEST_POINT_IDS,
    )
    point_ids = tuple(point["id"] for point in points)
    for index, point in enumerate(points):
        item_path = f"{path}.test_points[{index}]"
        expected_id, expected_kind, expected_label, expected_binding_id = (
            TEST_POINT_SPECS[index]
        )
        _expect_exact_keys(
            point, ("id", "kind", "label", "required_input_hashes"), item_path
        )
        kind = _expect_string(
            point["kind"],
            f"{item_path}.kind",
            allowed=(
                "environment",
                "install",
                "lifecycle",
                "route",
                "scene",
                "config",
                "performance",
                "transition",
                "soak",
                "migration",
                "rollback",
                "uninstall",
                "package",
                "privacy",
                "schema",
                "cleanup",
                "review",
            ),
            maximum=32,
        )
        label = _expect_label(point["label"], f"{item_path}.label")
        if (
            point["id"] != expected_id
            or kind != expected_kind
            or label != expected_label
        ):
            raise MatrixModelError("E_TEST_POINT_BINDING", item_path)
        hashes = _expect_unique_ids(
            point["required_input_hashes"],
            f"{item_path}.required_input_hashes",
            exact_ids=(expected_binding_id,),
        )
        for hash_index, binding in enumerate(hashes):
            binding_path = f"{item_path}.required_input_hashes[{hash_index}]"
            _expect_exact_keys(binding, ("id", "sha256"), binding_path)
            _expect_sha(binding["sha256"], f"{binding_path}.sha256")
            if mode == "PUBLIC_SYNTHETIC":
                _expect_synthetic_binding(
                    binding["sha256"],
                    f"{binding_path}.sha256",
                    manifest_id,
                    "test-point-input",
                    f"{point['id']}.{binding['id']}",
                    {
                        "test_point_id": point["id"],
                        "test_point_kind": point["kind"],
                        "binding_id": binding["id"],
                    },
                )

    classes = _expect_unique_ids(
        value["test_classes"],
        f"{path}.test_classes",
        exact_ids=TEST_CLASS_IDS,
    )
    point_usage: set[str] = set()
    for index, test_class in enumerate(classes):
        item_path = f"{path}.test_classes[{index}]"
        (
            expected_id,
            expected_execution,
            expected_host_modes,
            expected_class_points,
            expected_evidence_kinds,
        ) = TEST_CLASS_SPECS[index]
        _expect_exact_keys(
            test_class,
            (
                "id",
                "label",
                "execution",
                "required",
                "host_modes",
                "test_points",
                "evidence_kinds",
            ),
            item_path,
        )
        _expect_label(test_class["label"], f"{item_path}.label")
        execution = _expect_string(
            test_class["execution"],
            f"{item_path}.execution",
            allowed=("OBJECTIVE", "MANUAL"),
            maximum=16,
        )
        if test_class["id"] != expected_id or execution != expected_execution:
            raise MatrixModelError("E_EXECUTION_BOUNDARY", item_path)
        if not _expect_bool(test_class["required"], f"{item_path}.required"):
            raise MatrixModelError("E_REQUIRED_CLASS_DISABLED", item_path)
        host_modes = _expect_unique_string_list(
            test_class["host_modes"],
            f"{item_path}.host_modes",
            allowed=HOST_MODE_IDS,
            id_format=True,
            maximum=len(HOST_MODE_IDS),
        )
        if tuple(host_modes) != expected_host_modes:
            raise MatrixModelError(
                "E_TEST_CLASS_HOST_MODES", f"{item_path}.host_modes"
            )
        class_points = _expect_unique_string_list(
            test_class["test_points"],
            f"{item_path}.test_points",
            allowed=point_ids,
            id_format=True,
            maximum=MAX_CLASS_POINTS,
        )
        if tuple(class_points) != expected_class_points:
            raise MatrixModelError(
                "E_TEST_CLASS_POINTS", f"{item_path}.test_points"
            )
        for point_id in class_points:
            point_usage.add(point_id)
        evidence_kinds = _expect_unique_string_list(
            test_class["evidence_kinds"],
            f"{item_path}.evidence_kinds",
            allowed=EVIDENCE_KIND_IDS,
            id_format=True,
            maximum=MAX_EVIDENCE_KINDS,
        )
        if tuple(evidence_kinds) != expected_evidence_kinds:
            raise MatrixModelError(
                "E_TEST_CLASS_EVIDENCE", f"{item_path}.evidence_kinds"
            )
        if execution == "MANUAL":
            if (
                len(evidence_kinds) < 2
                or "manual-verdict" not in evidence_kinds
                or not any(kind != "manual-verdict" for kind in evidence_kinds)
            ):
                raise MatrixModelError(
                    "E_MANUAL_VERDICT_EVIDENCE", f"{item_path}.evidence_kinds"
                )
        elif "manual-verdict" in evidence_kinds:
            raise MatrixModelError(
                "E_MANUAL_REPLACES_OBJECTIVE", f"{item_path}.evidence_kinds"
            )
    if point_usage != set(point_ids):
        raise MatrixModelError("E_UNUSED_TEST_POINT", f"{path}.test_points")


def _validate_policy(policy: Any) -> None:
    path = "$.release_policy"
    value = _expect_mapping(policy, path)
    _expect_exact_keys(
        value,
        (
            "required_games",
            "required_tiers",
            "required_engine_ids",
            "required_platforms",
            "required_test_classes",
            "required_host_modes",
            "non_pass_states_block_release",
            "missing_cell_state",
            "manual_cannot_replace_objective",
            "cross_dimension_evidence",
        ),
        path,
    )
    _expect_exact_string_list(value["required_games"], f"{path}.required_games", GAME_IDS)
    _expect_exact_string_list(value["required_tiers"], f"{path}.required_tiers", TIER_IDS)
    _expect_exact_string_list(
        value["required_engine_ids"], f"{path}.required_engine_ids", ENGINE_IDS
    )
    _expect_exact_string_list(
        value["required_platforms"], f"{path}.required_platforms", PLATFORM_IDS
    )
    _expect_exact_string_list(
        value["required_test_classes"],
        f"{path}.required_test_classes",
        TEST_CLASS_IDS,
    )
    _expect_exact_string_list(
        value["required_host_modes"],
        f"{path}.required_host_modes",
        HOST_MODE_IDS,
    )
    _expect_exact_string_list(
        value["non_pass_states_block_release"],
        f"{path}.non_pass_states_block_release",
        BLOCKING_CELL_STATUSES,
    )
    _expect_string(
        value["missing_cell_state"],
        f"{path}.missing_cell_state",
        allowed=("BLOCKED",),
        maximum=16,
    )
    if not _expect_bool(
        value["manual_cannot_replace_objective"],
        f"{path}.manual_cannot_replace_objective",
    ):
        raise MatrixModelError("E_MANUAL_OBJECTIVE_BOUNDARY", path)
    _expect_string(
        value["cross_dimension_evidence"],
        f"{path}.cross_dimension_evidence",
        allowed=("REJECT",),
        maximum=16,
    )


def _validate_required_cell_set_shape(cell_set: Any) -> None:
    path = "$.required_cell_set"
    value = _expect_mapping(cell_set, path)
    _expect_exact_keys(
        value,
        (
            "schema",
            "schema_version",
            "manifest_input_sha256",
            "required_cell_count",
            "required_cell_ids_sha256",
            "required_cells_by_game",
        ),
        path,
    )
    _expect_string(
        value["schema"], path + ".schema", allowed=(REQUIRED_CELL_SET_SCHEMA,)
    )
    if _expect_int(value["schema_version"], path + ".schema_version", 1, 1) != 1:
        raise MatrixModelError("E_SCHEMA_VERSION", path + ".schema_version")
    _expect_sha(value["manifest_input_sha256"], path + ".manifest_input_sha256")
    _expect_int(
        value["required_cell_count"],
        path + ".required_cell_count",
        1,
        MAX_PUBLIC_CELLS,
    )
    _expect_sha(
        value["required_cell_ids_sha256"], path + ".required_cell_ids_sha256"
    )
    games = _expect_mapping(
        value["required_cells_by_game"], path + ".required_cells_by_game"
    )
    _expect_exact_keys(games, GAME_IDS, path + ".required_cells_by_game")
    for game_id in GAME_IDS:
        _expect_int(
            games[game_id],
            path + f".required_cells_by_game.{game_id}",
            1,
            MAX_PUBLIC_CELLS,
        )
def validate_manifest(manifest: Any) -> Mapping[str, Any]:
    """Validate one v1 manifest and return a defensive deep copy."""

    value = _expect_mapping(manifest, "$")
    _expect_exact_keys(
        value,
        (
            "schema",
            "schema_version",
            "manifest_id",
            "created_at",
            "mode",
            "release_eligible",
            "candidate",
            "binding_acquisition",
            "required_cell_set",
            "catalogs",
            "release_policy",
        ),
        "$",
    )
    _expect_string(
        value["schema"], "$ .schema".replace(" ", ""), allowed=(MANIFEST_SCHEMA,)
    )
    if _expect_int(value["schema_version"], "$.schema_version", 1) != SCHEMA_VERSION:
        raise MatrixModelError("E_SCHEMA_VERSION", "$.schema_version")
    manifest_id = _expect_id(value["manifest_id"], "$.manifest_id")
    _parse_utc(value["created_at"], "$.created_at")
    mode = _expect_string(
        value["mode"],
        "$.mode",
        allowed=("PUBLIC_SYNTHETIC", "PRIVATE_RELEASE"),
        maximum=32,
    )
    release_eligible = _expect_bool(value["release_eligible"], "$.release_eligible")
    _validate_candidate(value["candidate"], mode, release_eligible, manifest_id)
    _validate_required_cell_set_shape(value["required_cell_set"])
    _validate_catalogs(value["catalogs"], mode, manifest_id)
    _validate_binding_acquisition(
        value["binding_acquisition"],
        mode,
        value["candidate"],
        value["catalogs"],
    )
    _validate_policy(value["release_policy"])
    _assert_canonical_value(value)
    derived_cell_set = _derive_required_cell_set(value)
    if value["required_cell_set"] != derived_cell_set:
        raise MatrixModelError(
            "E_REQUIRED_CELL_SET_BINDING", "$.required_cell_set"
        )
    if (
        derived_cell_set["required_cell_count"] != REQUIRED_CELL_COUNT_V1
        or derived_cell_set["required_cells_by_game"]
        != REQUIRED_CELLS_BY_GAME_V1
    ):
        raise MatrixModelError(
            "E_REQUIRED_CELL_UNIVERSE", "$.required_cell_set"
        )
    return deepcopy(value)


def load_manifest(path: Path | str) -> Mapping[str, Any]:
    return validate_manifest(strict_json_load(path))


@dataclass(frozen=True)
class MatrixCell:
    cell_id: str
    input_fingerprint: str
    identity: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "cell_id": self.cell_id,
            "input_fingerprint": self.input_fingerprint,
            "identity": deepcopy(dict(self.identity)),
        }


@dataclass(frozen=True)
class ValidatedResultSet:
    """Public-safe summary of one complete ledger validation pass.

    This value is data, not an authority token.  ``validate_public_status``
    never trusts a caller-supplied instance and reads the ledger itself before
    it can approve READY.
    """

    manifest_sha256: str
    manifest_input_sha256: str
    required_cell_ids_sha256: str
    required_cell_count: int
    ledger_snapshot_sha256: str
    validated_result_set_sha256: str
    validated_result_count: int
    status_counts: tuple[tuple[str, int], ...]
    passed_cells_by_game: tuple[tuple[str, int], ...]


def _records_by_id(records: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    return {record["id"]: record for record in records}


def _make_cell(
    manifest: Mapping[str, Any],
    manifest_input_sha256: str,
    game: Mapping[str, Any],
    host: Mapping[str, Any],
    engine: Mapping[str, Any],
    tier: Mapping[str, Any],
    platform: Mapping[str, Any],
    host_mode: Mapping[str, Any],
    test_class: Mapping[str, Any],
    test_point: Mapping[str, Any],
) -> MatrixCell:
    candidate = manifest["candidate"]
    identity = {
        "schema": CELL_IDENTITY_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "manifest_id": manifest["manifest_id"],
        "manifest_input_sha256": manifest_input_sha256,
        "mode": manifest["mode"],
        "release_eligible": manifest["release_eligible"],
        "runtime_source_commit": candidate["runtime_source_commit"],
        "runtime_source_tree": candidate["runtime_source_tree"],
        "runtime_content_sha256": candidate["runtime_content_sha256"],
        "package_kind": candidate["package_kind"],
        "package_sha256": candidate["package_sha256"],
        "matrix_adapter_version": candidate["adapter_version"],
        "matrix_adapter_sha256": candidate["adapter_sha256"],
        "game": {
            "id": game["id"],
            "adapter_id": game["adapter_id"],
            "adapter_sha256": game["adapter_sha256"],
        },
        "host": {
            "id": host["id"],
            "version": host["version"],
            "source_commit": host["source_commit"],
            "package_sha256": host["package_sha256"],
        },
        "engine": {
            "id": engine["id"],
            "version": engine["version"],
            "source_commit": engine["source_commit"],
            "runtime_sha256": engine["runtime_sha256"],
            "binding_kind": engine["binding_kind"],
        },
        "tier": tier["id"],
        "platform": {
            "id": platform["id"],
            "adapter_id": platform["adapter_id"],
            "adapter_sha256": platform["adapter_sha256"],
            "physical_confirmation_required": platform[
                "physical_confirmation_required"
            ],
        },
        "host_mode": {
            "id": host_mode["id"],
            "fixture_sha256": host_mode["fixture_sha256"],
        },
        "test_class": test_class["id"],
        "test_execution": test_class["execution"],
        "required_gate_ids": [test_class["id"]],
        "test_point": {
            "id": test_point["id"],
            "kind": test_point["kind"],
            "required_input_hashes": deepcopy(test_point["required_input_hashes"]),
        },
        "required_evidence_kinds": list(test_class["evidence_kinds"]),
    }
    fingerprint = sha256_value(identity)
    return MatrixCell(
        cell_id=f"cell-{fingerprint}",
        input_fingerprint=fingerprint,
        identity=identity,
    )


def _manifest_input_sha256(manifest: Mapping[str, Any]) -> str:
    basis = deepcopy(dict(manifest))
    basis.pop("required_cell_set", None)
    return sha256_value(basis)


def _expand_cells_from_checked(
    checked: Mapping[str, Any],
) -> tuple[MatrixCell, ...]:
    catalogs = checked["catalogs"]
    manifest_input_sha256 = _manifest_input_sha256(checked)
    games = catalogs["games"]
    hosts = [host for host in catalogs["hosts"] if host["eligible"]]
    engines = catalogs["engines"]
    tiers = catalogs["tiers"]
    platforms = [platform for platform in catalogs["platforms"] if platform["claimed"]]
    host_modes = _records_by_id(catalogs["host_modes"])
    points = _records_by_id(catalogs["test_points"])
    cells: list[MatrixCell] = []
    ids: set[str] = set()

    for game, host, engine, tier, platform, test_class in itertools.product(
        games,
        hosts,
        engines,
        tiers,
        platforms,
        catalogs["test_classes"],
    ):
        if not test_class["required"]:
            continue
        for host_mode_id in test_class["host_modes"]:
            for point_id in test_class["test_points"]:
                cell = _make_cell(
                    checked,
                    manifest_input_sha256,
                    game,
                    host,
                    engine,
                    tier,
                    platform,
                    host_modes[host_mode_id],
                    test_class,
                    points[point_id],
                )
                if cell.cell_id in ids:
                    raise MatrixModelError("E_DUPLICATE_CELL_ID")
                ids.add(cell.cell_id)
                cells.append(cell)
    if not cells:
        raise MatrixModelError("E_EMPTY_MATRIX")
    return tuple(cells)


def _derive_required_cell_set(
    checked: Mapping[str, Any],
) -> Mapping[str, Any]:
    manifest_input_sha256 = _manifest_input_sha256(checked)
    cells = _expand_cells_from_checked(checked)
    cell_ids = [cell.cell_id for cell in cells]
    counts = {
        game_id: sum(
            1 for cell in cells if cell.identity["game"]["id"] == game_id
        )
        for game_id in GAME_IDS
    }
    digest = sha256_value(
        {
            "schema": REQUIRED_CELL_SET_SCHEMA,
            "schema_version": SCHEMA_VERSION,
            "manifest_id": checked["manifest_id"],
            "manifest_input_sha256": manifest_input_sha256,
            "cell_ids": cell_ids,
        }
    )
    return {
        "schema": REQUIRED_CELL_SET_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "manifest_input_sha256": manifest_input_sha256,
        "required_cell_count": len(cells),
        "required_cell_ids_sha256": digest,
        "required_cells_by_game": counts,
    }


def derive_required_cell_set(manifest: Any) -> Mapping[str, Any]:
    """Derive the required-cell contract from validated non-contract inputs."""

    value = _expect_mapping(manifest, "$")
    # Validation checks every non-derived input before this helper is useful.
    # A well-formed placeholder contract is allowed so callers can regenerate it.
    candidate = deepcopy(dict(value))
    placeholder = candidate.get("required_cell_set")
    _validate_required_cell_set_shape(placeholder)
    candidate["required_cell_set"] = deepcopy(dict(placeholder))
    _expect_exact_keys(
        candidate,
        (
            "schema",
            "schema_version",
            "manifest_id",
            "created_at",
            "mode",
            "release_eligible",
            "candidate",
            "binding_acquisition",
            "required_cell_set",
            "catalogs",
            "release_policy",
        ),
        "$",
    )
    _expect_string(candidate["schema"], "$.schema", allowed=(MANIFEST_SCHEMA,))
    if _expect_int(candidate["schema_version"], "$.schema_version", 1, 1) != 1:
        raise MatrixModelError("E_SCHEMA_VERSION", "$.schema_version")
    manifest_id = _expect_id(candidate["manifest_id"], "$.manifest_id")
    _parse_utc(candidate["created_at"], "$.created_at")
    mode = _expect_string(
        candidate["mode"],
        "$.mode",
        allowed=("PUBLIC_SYNTHETIC", "PRIVATE_RELEASE"),
        maximum=32,
    )
    release_eligible = _expect_bool(
        candidate["release_eligible"], "$.release_eligible"
    )
    _validate_candidate(
        candidate["candidate"], mode, release_eligible, manifest_id
    )
    _validate_catalogs(candidate["catalogs"], mode, manifest_id)
    _validate_binding_acquisition(
        candidate["binding_acquisition"],
        mode,
        candidate["candidate"],
        candidate["catalogs"],
    )
    _validate_policy(candidate["release_policy"])
    _assert_canonical_value(candidate)
    return deepcopy(dict(_derive_required_cell_set(candidate)))


def expand_cells(manifest: Any) -> tuple[MatrixCell, ...]:
    """Expand every required immutable matrix cell in deterministic order."""

    return _expand_cells_from_checked(validate_manifest(manifest))


def _validated_result_set_from_ledger(
    manifest: Any,
    records: Sequence[Mapping[str, Any]],
    *,
    ledger_snapshot_sha256: str | None = None,
) -> ValidatedResultSet:
    """Summarize a complete, ordered set of ledger validation records.

    The summary is not an authority boundary.  The READY validator ignores
    caller-created summaries and obtains its own records through a read-only
    ``LedgerStore`` pass.
    """

    checked_manifest = validate_manifest(manifest)
    cells = _expand_cells_from_checked(checked_manifest)
    if type(records) not in (list, tuple) or len(records) != len(cells):
        raise MatrixModelError("E_RESULT_SET_SIZE", "$.records")

    checked_records: list[dict[str, Any]] = []
    counts = {status: 0 for status in CELL_STATUSES}
    passed_by_game = {game_id: 0 for game_id in GAME_IDS}
    result_records: list[dict[str, Any]] = []
    for index, (cell, raw_record) in enumerate(zip(cells, records)):
        path = f"$.records[{index}]"
        record = _expect_mapping(raw_record, path)
        _expect_exact_keys(
            record,
            (
                "cell_id",
                "input_fingerprint",
                "status",
                "attempt_id",
                "last_event_sha256",
                "cell_result_sha256",
            ),
            path,
        )
        cell_id = _expect_string(
            record["cell_id"],
            path + ".cell_id",
            pattern=_CELL_ID_RE,
            minimum=69,
            maximum=69,
        )
        fingerprint = _expect_sha(
            record["input_fingerprint"], path + ".input_fingerprint"
        )
        if cell_id != cell.cell_id or fingerprint != cell.input_fingerprint:
            raise MatrixModelError("E_RESULT_SET_CELL_BINDING", path)
        status = _expect_string(
            record["status"], path + ".status", allowed=CELL_STATUSES, maximum=16
        )

        attempt_id = record["attempt_id"]
        if attempt_id is not None:
            attempt_id = _expect_string(
                attempt_id,
                path + ".attempt_id",
                pattern=_ATTEMPT_ID_RE,
                minimum=72,
                maximum=72,
            )
        last_event_sha256 = record["last_event_sha256"]
        if last_event_sha256 is not None:
            last_event_sha256 = _expect_sha(
                last_event_sha256, path + ".last_event_sha256"
            )
        cell_result_sha256 = record["cell_result_sha256"]
        if cell_result_sha256 is not None:
            cell_result_sha256 = _expect_sha(
                cell_result_sha256, path + ".cell_result_sha256"
            )
        if cell_result_sha256 is not None and (
            attempt_id is None or last_event_sha256 is None
        ):
            raise MatrixModelError("E_RESULT_SET_RESULT_BINDING", path)
        if status == "PASS" and (
            attempt_id is None
            or last_event_sha256 is None
            or cell_result_sha256 is None
        ):
            raise MatrixModelError("E_RESULT_SET_PASS_BINDING", path)

        checked = {
            "cell_id": cell_id,
            "input_fingerprint": fingerprint,
            "status": status,
            "attempt_id": attempt_id,
            "last_event_sha256": last_event_sha256,
            "cell_result_sha256": cell_result_sha256,
        }
        checked_records.append(checked)
        counts[status] += 1
        if status == "PASS":
            passed_by_game[cell.identity["game"]["id"]] += 1
        if cell_result_sha256 is not None:
            result_records.append(checked)

    required_cell_set = checked_manifest["required_cell_set"]
    manifest_sha256 = sha256_value(checked_manifest)
    digest_basis = {
        "schema": RESULT_SET_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "manifest_sha256": manifest_sha256,
        "manifest_input_sha256": required_cell_set["manifest_input_sha256"],
        "required_cell_ids_sha256": required_cell_set[
            "required_cell_ids_sha256"
        ],
    }
    if ledger_snapshot_sha256 is None:
        ledger_snapshot_sha256 = sha256_value(
            {**digest_basis, "records": checked_records}
        )
    else:
        ledger_snapshot_sha256 = _expect_sha(
            ledger_snapshot_sha256, "$.ledger_snapshot_sha256"
        )
    validated_result_set_sha256 = sha256_value(
        {
            **digest_basis,
            "ledger_snapshot_sha256": ledger_snapshot_sha256,
            "results": result_records,
        }
    )
    return ValidatedResultSet(
        manifest_sha256=manifest_sha256,
        manifest_input_sha256=required_cell_set["manifest_input_sha256"],
        required_cell_ids_sha256=required_cell_set["required_cell_ids_sha256"],
        required_cell_count=len(cells),
        ledger_snapshot_sha256=ledger_snapshot_sha256,
        validated_result_set_sha256=validated_result_set_sha256,
        validated_result_count=len(result_records),
        status_counts=tuple((status, counts[status]) for status in CELL_STATUSES),
        passed_cells_by_game=tuple(
            (game_id, passed_by_game[game_id]) for game_id in GAME_IDS
        ),
    )


def make_attempt_id(
    cell: MatrixCell,
    attempt_number: int,
    started_at: str,
    owner_id: str,
    recovery_id: str | None = None,
) -> str:
    if type(attempt_number) is not int or attempt_number < 1:
        raise MatrixModelError("E_ATTEMPT_NUMBER")
    _parse_utc(started_at, "$.started_at")
    _expect_id(owner_id, "$.owner_id")
    if recovery_id is not None:
        _expect_string(
            recovery_id,
            "$.recovery_id",
            pattern=_RECOVERY_ID_RE,
            minimum=73,
            maximum=73,
        )
    payload = {
        "cell_id": cell.cell_id,
        "input_fingerprint": cell.input_fingerprint,
        "attempt_number": attempt_number,
        "started_at": started_at,
        "owner_id": owner_id,
        "recovery_id": recovery_id,
    }
    return f"attempt-{sha256_value(payload)}"


def validate_cell_result(result: Any, cell: MatrixCell) -> Mapping[str, Any]:
    """Reject stale, cross-cell, incomplete, or type-confused result records."""

    value = _expect_mapping(result, "$")
    _expect_exact_keys(
        value,
        (
            "schema",
            "schema_version",
            "cell_id",
            "input_fingerprint",
            "attempt_id",
            "started_at",
            "finished_at",
            "status",
            "cleanup",
            "objective",
            "evidence",
            "manual_verdict_sha256",
            "failure_code",
        ),
        "$",
    )
    _expect_string(value["schema"], "$.schema", allowed=(CELL_RESULT_SCHEMA,))
    if _expect_int(value["schema_version"], "$.schema_version", 1) != 1:
        raise MatrixModelError("E_SCHEMA_VERSION", "$.schema_version")
    if _expect_string(
        value["cell_id"], "$.cell_id", pattern=_CELL_ID_RE, minimum=69, maximum=69
    ) != cell.cell_id:
        raise MatrixModelError("E_CELL_BINDING", "$.cell_id")
    if _expect_sha(value["input_fingerprint"], "$.input_fingerprint") != cell.input_fingerprint:
        raise MatrixModelError("E_CELL_BINDING", "$.input_fingerprint")
    _expect_string(
        value["attempt_id"],
        "$.attempt_id",
        pattern=_ATTEMPT_ID_RE,
        minimum=72,
        maximum=72,
    )
    started = _parse_utc(value["started_at"], "$.started_at")
    finished = _parse_utc(value["finished_at"], "$.finished_at")
    if finished < started:
        raise MatrixModelError("E_TIMESTAMP_ORDER", "$.finished_at")
    status = _expect_string(
        value["status"], "$.status", allowed=CELL_STATUSES, maximum=16
    )
    cleanup = _expect_string(
        value["cleanup"],
        "$.cleanup",
        allowed=("PASS", "FAIL", "UNKNOWN", "NOT_RUN"),
        maximum=16,
    )
    objective = _expect_bool(value["objective"], "$.objective")
    expected_objective = cell.identity["test_execution"] == "OBJECTIVE"
    if objective != expected_objective:
        raise MatrixModelError("E_EXECUTION_BOUNDARY", "$.objective")

    evidence = _expect_list(value["evidence"], "$.evidence")
    if len(evidence) > MAX_EVIDENCE_ITEMS:
        raise MatrixModelError("E_ARRAY_LENGTH", "$.evidence")
    evidence_kinds: list[str] = []
    for index, raw_evidence in enumerate(evidence):
        item_path = f"$.evidence[{index}]"
        item = validate_evidence_binding(
            raw_evidence,
            cell,
            attempt_id=value["attempt_id"],
            allowed_gate_ids=cell.identity["required_gate_ids"],
            path=item_path,
        )
        kind = _expect_id(item["kind"], f"{item_path}.kind")
        if kind in evidence_kinds:
            raise MatrixModelError("E_DUPLICATE_EVIDENCE", item_path)
        evidence_kinds.append(kind)
        _expect_sha(item["sha256"], f"{item_path}.sha256")
        _expect_int(
            item["bytes"],
            f"{item_path}.bytes",
            1,
            MAX_EVIDENCE_BYTES,
        )

    expected_kinds = list(cell.identity["required_evidence_kinds"])
    if status == "PASS":
        if cleanup != "PASS":
            raise MatrixModelError("E_PASS_WITHOUT_CLEANUP", "$.cleanup")
        if evidence_kinds != expected_kinds:
            raise MatrixModelError("E_PASS_EVIDENCE_SET", "$.evidence")
        if value["failure_code"] is not None:
            raise MatrixModelError("E_PASS_FAILURE_CODE", "$.failure_code")
    else:
        for kind in evidence_kinds:
            if kind not in expected_kinds:
                raise MatrixModelError("E_EVIDENCE_KIND", "$.evidence")
        _expect_id(value["failure_code"], "$.failure_code")

    manual_hash = value["manual_verdict_sha256"]
    if expected_objective:
        if manual_hash is not None:
            raise MatrixModelError("E_MANUAL_REPLACES_OBJECTIVE", "$.manual_verdict_sha256")
    elif status == "PASS":
        checked_manual_hash = _expect_sha(
            manual_hash, "$.manual_verdict_sha256"
        )
        matching_verdicts = [
            item
            for item in evidence
            if item["kind"] == "manual-verdict"
        ]
        if (
            len(matching_verdicts) != 1
            or matching_verdicts[0]["sha256"] != checked_manual_hash
        ):
            raise MatrixModelError(
                "E_MANUAL_VERDICT_EVIDENCE", "$.manual_verdict_sha256"
            )
    elif manual_hash is not None:
        _expect_sha(manual_hash, "$.manual_verdict_sha256")
    _assert_canonical_value(value)
    return deepcopy(value)


def validate_manual_verdict(verdict: Any, cell: MatrixCell) -> Mapping[str, Any]:
    """Validate a schema-bound manual verdict for a manual-only cell."""

    if cell.identity["test_execution"] != "MANUAL":
        raise MatrixModelError("E_MANUAL_REPLACES_OBJECTIVE", "$.cell_id")
    value = _expect_mapping(verdict, "$")
    _expect_exact_keys(
        value,
        (
            "schema",
            "schema_version",
            "cell_id",
            "input_fingerprint",
            "review_packet_sha256",
            "objective_result_sha256",
            "reviewer_id",
            "reviewed_at",
            "verdict",
            "objective_checks_passed",
            "criteria",
        ),
        "$",
    )
    _expect_string(value["schema"], "$.schema", allowed=(MANUAL_VERDICT_SCHEMA,))
    if _expect_int(value["schema_version"], "$.schema_version", 1) != 1:
        raise MatrixModelError("E_SCHEMA_VERSION", "$.schema_version")
    if _expect_string(
        value["cell_id"], "$.cell_id", pattern=_CELL_ID_RE, minimum=69, maximum=69
    ) != cell.cell_id:
        raise MatrixModelError("E_CELL_BINDING", "$.cell_id")
    if _expect_sha(value["input_fingerprint"], "$.input_fingerprint") != cell.input_fingerprint:
        raise MatrixModelError("E_CELL_BINDING", "$.input_fingerprint")
    _expect_sha(value["review_packet_sha256"], "$.review_packet_sha256")
    _expect_sha(value["objective_result_sha256"], "$.objective_result_sha256")
    _expect_id(value["reviewer_id"], "$.reviewer_id")
    _parse_utc(value["reviewed_at"], "$.reviewed_at")
    _expect_string(value["verdict"], "$.verdict", allowed=("PASS", "FAIL"))
    if not _expect_bool(
        value["objective_checks_passed"], "$.objective_checks_passed"
    ):
        raise MatrixModelError("E_MANUAL_WITHOUT_OBJECTIVE", "$.objective_checks_passed")
    _expect_unique_string_list(
        value["criteria"],
        "$.criteria",
        id_format=True,
        maximum=MAX_MANUAL_CRITERIA,
    )
    _assert_canonical_value(value)
    return deepcopy(value)


def validate_public_status(
    status: Any,
    manifest: Any,
    ledger_root: Path | str | None = None,
) -> Mapping[str, Any]:
    """Validate public status against an independently read ledger snapshot.

    READY always requires an absolute ledger root.  The function constructs a
    read-only ``LedgerStore`` and validates the real append-only records.  A
    missing root is allowed only for the deterministic all-MISSING NOT_READY
    state.  Caller-created summaries and attestations are never accepted.
    """

    checked_manifest = validate_manifest(manifest)
    required_cell_set = checked_manifest["required_cell_set"]
    value = _expect_mapping(status, "$")
    _expect_exact_keys(
        value,
        (
            "schema",
            "schema_version",
            "generated_at",
            "manifest_id",
            "manifest_sha256",
            "manifest_input_sha256",
            "required_cell_ids_sha256",
            "source_commit",
            "package_sha256",
            "ledger_snapshot_sha256",
            "validated_result_set_sha256",
            "validated_result_count",
            "release_eligible",
            "readiness",
            "release",
            "required_cells",
            "status_counts",
            "games",
            "blockers",
        ),
        "$",
    )
    _expect_string(value["schema"], "$.schema", allowed=(PUBLIC_STATUS_SCHEMA,))
    if _expect_int(value["schema_version"], "$.schema_version", 1, 1) != 1:
        raise MatrixModelError("E_SCHEMA_VERSION", "$.schema_version")
    _parse_utc(value["generated_at"], "$.generated_at")
    manifest_id = _expect_id(value["manifest_id"], "$.manifest_id")
    manifest_sha256 = _expect_sha(value["manifest_sha256"], "$.manifest_sha256")
    manifest_input_sha256 = _expect_sha(
        value["manifest_input_sha256"], "$.manifest_input_sha256"
    )
    required_cell_ids_sha256 = _expect_sha(
        value["required_cell_ids_sha256"], "$.required_cell_ids_sha256"
    )
    source_commit = _expect_commit(value["source_commit"], "$.source_commit")
    package_sha256 = _expect_sha(value["package_sha256"], "$.package_sha256")
    ledger_snapshot_sha256 = _expect_sha(
        value["ledger_snapshot_sha256"], "$.ledger_snapshot_sha256"
    )
    validated_result_set_sha256 = _expect_sha(
        value["validated_result_set_sha256"], "$.validated_result_set_sha256"
    )
    validated_result_count = _expect_int(
        value["validated_result_count"],
        "$.validated_result_count",
        0,
        MAX_PUBLIC_CELLS,
    )
    candidate = checked_manifest["candidate"]
    if (
        manifest_id != checked_manifest["manifest_id"]
        or manifest_sha256 != sha256_value(checked_manifest)
        or manifest_input_sha256
        != required_cell_set["manifest_input_sha256"]
        or required_cell_ids_sha256
        != required_cell_set["required_cell_ids_sha256"]
        or source_commit != candidate["runtime_source_commit"]
        or package_sha256 != candidate["package_sha256"]
    ):
        raise MatrixModelError("E_PUBLIC_MANIFEST_BINDING", "$")
    release_eligible = _expect_bool(
        value["release_eligible"], "$.release_eligible"
    )
    if release_eligible != checked_manifest["release_eligible"]:
        raise MatrixModelError(
            "E_PUBLIC_MANIFEST_BINDING", "$.release_eligible"
        )
    readiness = _expect_string(
        value["readiness"],
        "$.readiness",
        allowed=("READY", "NOT_READY"),
        maximum=16,
    )
    release = _expect_string(
        value["release"],
        "$.release",
        allowed=("NOT_RELEASED",),
        maximum=16,
    )
    required_cells = _expect_int(
        value["required_cells"],
        "$.required_cells",
        1,
        MAX_PUBLIC_CELLS,
    )
    if required_cells != required_cell_set["required_cell_count"]:
        raise MatrixModelError("E_PUBLIC_CELL_SET", "$.required_cells")

    counts = _expect_mapping(value["status_counts"], "$.status_counts")
    _expect_exact_keys(counts, CELL_STATUSES, "$.status_counts")
    checked_counts = {
        state: _expect_int(
            counts[state],
            f"$.status_counts.{state}",
            0,
            MAX_PUBLIC_CELLS,
        )
        for state in CELL_STATUSES
    }
    if sum(checked_counts.values()) != required_cells:
        raise MatrixModelError("E_PUBLIC_COUNT_TOTAL", "$.status_counts")
    games = _expect_list(value["games"], "$.games")
    if len(games) != len(GAME_IDS):
        raise MatrixModelError("E_PUBLIC_GAME_SET", "$.games")
    game_required_total = 0
    game_pass_total = 0
    for index, expected_game_id in enumerate(GAME_IDS):
        game_path = f"$.games[{index}]"
        game = _expect_mapping(games[index], game_path)
        _expect_exact_keys(
            game,
            ("id", "status", "required_cells", "passed_cells"),
            game_path,
        )
        game_id = _expect_string(
            game["id"], game_path + ".id", allowed=GAME_IDS, maximum=16
        )
        if game_id != expected_game_id:
            raise MatrixModelError("E_PUBLIC_GAME_SET", game_path + ".id")
        game_required = _expect_int(
            game["required_cells"],
            game_path + ".required_cells",
            1,
            MAX_PUBLIC_CELLS,
        )
        game_passed = _expect_int(
            game["passed_cells"],
            game_path + ".passed_cells",
            0,
            MAX_PUBLIC_CELLS,
        )
        if game_passed > game_required:
            raise MatrixModelError("E_PUBLIC_GAME_COUNT", game_path)
        if game_required != required_cell_set["required_cells_by_game"][game_id]:
            raise MatrixModelError("E_PUBLIC_CELL_SET", game_path + ".required_cells")
        game_status = _expect_string(
            game["status"],
            game_path + ".status",
            allowed=("PASS", "BLOCKED"),
            maximum=16,
        )
        expected_status = "PASS" if game_passed == game_required else "BLOCKED"
        if game_status != expected_status:
            raise MatrixModelError("E_PUBLIC_GAME_STATUS", game_path + ".status")
        game_required_total += game_required
        game_pass_total += game_passed

    if game_required_total != required_cells:
        raise MatrixModelError("E_PUBLIC_GAME_TOTAL", "$.games")
    if game_pass_total != checked_counts["PASS"]:
        raise MatrixModelError("E_PUBLIC_PASS_TOTAL", "$.games")
    blockers_value = _expect_list(value["blockers"], "$.blockers")
    blockers = _expect_unique_string_list(
        value["blockers"],
        "$.blockers",
        id_format=True,
        maximum=MAX_PUBLIC_BLOCKERS,
    ) if blockers_value else []
    if blockers != sorted(blockers):
        raise MatrixModelError("E_PUBLIC_BLOCKER_ORDER", "$.blockers")

    if ledger_root is None:
        if readiness == "READY":
            raise MatrixModelError("E_PUBLIC_LEDGER_REQUIRED", "ledger_root")
        missing_records = [
            {
                "cell_id": cell.cell_id,
                "input_fingerprint": cell.input_fingerprint,
                "status": "MISSING",
                "attempt_id": None,
                "last_event_sha256": None,
                "cell_result_sha256": None,
            }
            for cell in _expand_cells_from_checked(checked_manifest)
        ]
        result_set = _validated_result_set_from_ledger(
            checked_manifest, missing_records
        )
    else:
        if not isinstance(ledger_root, (str, Path)):
            raise MatrixModelError("E_PUBLIC_LEDGER_ROOT", "ledger_root")
        try:
            ledger_path = Path(ledger_root)
        except (TypeError, ValueError, OSError) as exc:
            raise MatrixModelError(
                "E_PUBLIC_LEDGER_ROOT", "ledger_root"
            ) from exc
        if not ledger_path.is_absolute():
            raise MatrixModelError("E_PUBLIC_LEDGER_ROOT", "ledger_root")
        try:
            from tools.release_matrix.ledger import LedgerError, LedgerStore

            result_set = LedgerStore(
                ledger_path, create=False
            ).validated_result_set(checked_manifest)
        except (LedgerError, OSError) as exc:
            raise MatrixModelError(
                "E_PUBLIC_LEDGER_VALIDATION", "ledger_root"
            ) from exc
    if (
        result_set.manifest_sha256 != sha256_value(checked_manifest)
        or result_set.manifest_input_sha256
        != required_cell_set["manifest_input_sha256"]
        or result_set.required_cell_ids_sha256
        != required_cell_set["required_cell_ids_sha256"]
        or result_set.required_cell_count
        != required_cell_set["required_cell_count"]
    ):
        raise MatrixModelError("E_PUBLIC_RESULT_SET_MANIFEST", "ledger_root")
    if (
        ledger_snapshot_sha256 != result_set.ledger_snapshot_sha256
        or validated_result_set_sha256
        != result_set.validated_result_set_sha256
        or validated_result_count != result_set.validated_result_count
    ):
        raise MatrixModelError("E_PUBLIC_RESULT_SET_BINDING", "$")
    if tuple((state, checked_counts[state]) for state in CELL_STATUSES) != (
        result_set.status_counts
    ):
        raise MatrixModelError("E_PUBLIC_RESULT_SET_COUNTS", "$.status_counts")
    if tuple(
        (game["id"], game["passed_cells"]) for game in games
    ) != result_set.passed_cells_by_game:
        raise MatrixModelError("E_PUBLIC_RESULT_SET_GAMES", "$.games")

    all_cells_pass = (
        checked_counts["PASS"] == required_cells
        and validated_result_count == required_cells
        and all(checked_counts[state] == 0 for state in BLOCKING_CELL_STATUSES)
        and all(game["status"] == "PASS" for game in games)
    )
    ready_allowed = release_eligible and all_cells_pass and not blockers
    expected_readiness = "READY" if ready_allowed else "NOT_READY"
    if readiness != expected_readiness:
        raise MatrixModelError("E_PUBLIC_READINESS", "$.readiness")
    if readiness == "NOT_READY" and not blockers:
        raise MatrixModelError("E_PUBLIC_BLOCKERS_REQUIRED", "$.blockers")
    _assert_canonical_value(value)
    return deepcopy(value)


__all__ = [
    "BINDING_ACQUISITION_SCHEMA",
    "BINDING_SET_SCHEMA",
    "BLOCKING_CELL_STATUSES",
    "BATTLE_ART_1_9_8_PACKAGE_SHA256",
    "CELL_RESULT_SCHEMA",
    "CELL_STATUSES",
    "ENGINE_BINDINGS",
    "ENGINE_IDS",
    "EVIDENCE_BINDING_FIELDS",
    "EVIDENCE_BINDING_SCHEMA",
    "EVIDENCE_RECEIPT_FIELDS",
    "EVIDENCE_RECEIPT_SCHEMA",
    "EVIDENCE_KIND_IDS",
    "GAME_IDS",
    "HOST_MODE_IDS",
    "MANIFEST_SCHEMA",
    "MANUAL_TEST_CLASS_IDS",
    "MANUAL_VERDICT_SCHEMA",
    "MAX_EVIDENCE_BYTES",
    "MAX_EVIDENCE_ITEMS",
    "MAX_MANUAL_CRITERIA",
    "MAX_PUBLIC_BLOCKERS",
    "MAX_PUBLIC_CELLS",
    "MatrixCell",
    "MatrixModelError",
    "PLATFORM_IDS",
    "PRIVATE_BINDING_ACQUISITION_SCHEMA",
    "PRIVATE_BINDING_COUNT_V1",
    "PUBLIC_BINDING_SET_SHA256_V1",
    "PUBLIC_SYNTHETIC_HASHES_V1",
    "PUBLIC_STATUS_SCHEMA",
    "REQUIRED_CELL_SET_SCHEMA",
    "RESULT_SET_SCHEMA",
    "SCHEMA_VERSION",
    "TEST_CLASS_IDS",
    "TEST_POINT_IDS",
    "TEST_POINT_SPECS",
    "TIER_IDS",
    "ValidatedResultSet",
    "canonical_json_bytes",
    "derive_binding_acquisition",
    "derive_required_cell_set",
    "expand_cells",
    "load_manifest",
    "make_attempt_id",
    "make_evidence_binding",
    "make_evidence_receipt",
    "sha256_value",
    "strict_json_load",
    "strict_json_loads",
    "synthetic_binding_sha256",
    "validate_cell_result",
    "validate_evidence_binding",
    "validate_evidence_receipt",
    "validate_manifest",
    "validate_manual_verdict",
    "validate_public_status",
]
