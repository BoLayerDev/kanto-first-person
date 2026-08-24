"""Append-only, atomic ledger primitives for the KFP release matrix."""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
import hashlib
import os
from pathlib import Path
import re
import stat
from typing import Any, Iterable, Mapping
import uuid

from tools.release_matrix.model import (
    CELL_STATUSES,
    EVIDENCE_BINDING_FIELDS,
    EVIDENCE_BINDING_SCHEMA,
    MAX_EVIDENCE_BYTES,
    MAX_EVIDENCE_ITEMS,
    MatrixCell,
    MatrixModelError,
    ValidatedResultSet,
    _validated_result_set_from_ledger,
    canonical_json_bytes,
    expand_cells,
    make_attempt_id,
    make_evidence_binding,
    make_evidence_receipt,
    sha256_value,
    strict_json_loads,
    validate_cell_result,
    validate_evidence_receipt,
    validate_manual_verdict,
)


ATTEMPT_SCHEMA = "kfp.release-matrix.attempt.v1"
LEDGER_EVENT_SCHEMA = "kfp.release-matrix.ledger-event.v1"
RECOVERY_SCHEMA = "kfp.release-matrix.recovery.v1"
RECOVERY_REVIEW_SCHEMA = "kfp.release-matrix.recovery-review.v1"
ATTEMPT_SNAPSHOT_SCHEMA = "kfp.release-matrix.attempt-snapshot.v1"
LEDGER_SNAPSHOT_SCHEMA = "kfp.release-matrix.ledger-snapshot.v1"
STAGING_SNAPSHOT_SCHEMA = "kfp.release-matrix.staging-snapshot.v1"
STAGING_RECOVERY_REVIEW_SCHEMA = (
    "kfp.release-matrix.staging-recovery-review.v1"
)
STAGING_RECOVERY_SCHEMA = "kfp.release-matrix.staging-recovery.v1"
CELL_RECORD_SCHEMA = "kfp.release-matrix.cell-record.v1"
LEDGER_ROOT_SCHEMA = "kfp.release-matrix.ledger-root.v1"
SCHEMA_VERSION = 1
MAX_ATTEMPTS = 999_999
MAX_EVENT_SEQUENCE = 2_147_483_647
MAX_STAGING_ENTRIES = 4_096
MANUAL_OBJECTIVE_PREREQUISITES = {
    "human-visual-review": "logs-captures",
    "physical-platform-review": "environment-binding",
}
MANUAL_REVIEW_PACKET_KINDS = {
    "human-visual-review": "visual-review-packet",
    "physical-platform-review": "physical-review-packet",
}

EVENT_TYPES = (
    "GATE_STARTED",
    "GATE_PASSED",
    "GATE_FAILED",
    "CLEANUP_PASSED",
    "CLEANUP_FAILED",
    "ATTEMPT_PASSED",
    "ATTEMPT_FAILED",
    "ATTEMPT_BLOCKED",
    "ATTEMPT_AMBIGUOUS",
    "RESULT_COMMITTED",
)
TERMINAL_EVENTS = (
    "ATTEMPT_PASSED",
    "ATTEMPT_FAILED",
    "ATTEMPT_BLOCKED",
    "ATTEMPT_AMBIGUOUS",
    "RESULT_COMMITTED",
)

_CELL_RE = re.compile(r"^cell-[0-9a-f]{64}$")
_ATTEMPT_RE = re.compile(r"^attempt-[0-9a-f]{64}$")
_ATTEMPT_DIR_RE = re.compile(r"^([0-9]{6})-(attempt-[0-9a-f]{64})$")
_RECOVERY_RE = re.compile(r"^recovery-[0-9a-f]{64}$")
_STAGING_RECOVERY_RE = re.compile(r"^staging-recovery-[0-9a-f]{64}$")
_PENDING_STAGING_RECOVERY_RE = re.compile(
    r"^\.pending-(staging-recovery-[0-9a-f]{64})$"
)
_EVENT_FILE_RE = re.compile(r"^([0-9]{10})-([0-9a-f]{64})\.json$")
_EVIDENCE_FILE_RE = re.compile(
    r"^([a-z0-9]+(?:[._-][a-z0-9]+)*)-([0-9a-f]{64})\.blob$"
)
_EVIDENCE_RECEIPT_FILE_RE = re.compile(
    r"^([a-z0-9]+(?:[._-][a-z0-9]+)*)-([0-9a-f]{64})\.receipt\.json$"
)
_LEDGER_ROOT_RE = re.compile(r"^ledger-root-[0-9a-f]{64}$")
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")
_UTC_RE = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"
)


class LedgerError(RuntimeError):
    """Controlled append-only ledger failure."""

    def __init__(self, code: str, path: str = "ledger") -> None:
        self.code = code
        self.path = path
        super().__init__(f"{code} at {path}")


class LedgerConflict(LedgerError):
    pass


class LedgerAmbiguous(LedgerError):
    pass


@dataclass(frozen=True)
class AttemptInspection:
    attempt_id: str
    attempt_number: int
    state: str
    terminal_event: str | None
    event_count: int
    passed_gates: tuple[str, ...]
    failed_gate: str | None
    cleanup: str | None
    last_event_sha256: str | None
    cell_result_sha256: str | None


def _expect_mapping(value: Any, code: str, path: str) -> Mapping[str, Any]:
    if type(value) is not dict:
        raise LedgerAmbiguous(code, path)
    return value


def _expect_keys(
    value: Mapping[str, Any], expected: Iterable[str], code: str, path: str
) -> None:
    if set(value) != set(expected):
        raise LedgerAmbiguous(code, path)


def _expect_text(
    value: Any, pattern: re.Pattern[str], code: str, path: str
) -> str:
    if (
        type(value) is not str
        or (pattern is _ID_RE and len(value) > 96)
        or pattern.fullmatch(value) is None
    ):
        raise LedgerAmbiguous(code, path)
    return value


def _parse_utc(value: Any, code: str, path: str) -> datetime:
    text = _expect_text(value, _UTC_RE, code, path)
    try:
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise LedgerAmbiguous(code, path) from exc


def _is_reparse_or_link(path: Path) -> bool:
    try:
        details = os.lstat(path)
    except OSError as exc:
        raise LedgerAmbiguous("E_LEDGER_LSTAT", str(path)) from exc
    if stat.S_ISLNK(details.st_mode):
        return True
    attributes = getattr(details, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & reparse_flag)


def _assert_plain_directory(path: Path) -> None:
    if not path.is_dir() or _is_reparse_or_link(path):
        raise LedgerAmbiguous("E_LEDGER_DIRECTORY", str(path))


def _plain_directory_identity(path: Path) -> tuple[int, int]:
    _assert_plain_directory(path)
    try:
        details = os.stat(path, follow_symlinks=False)
    except OSError as exc:
        raise LedgerAmbiguous("E_LEDGER_DIRECTORY", str(path)) from exc
    if not stat.S_ISDIR(details.st_mode):
        raise LedgerAmbiguous("E_LEDGER_DIRECTORY", str(path))
    return details.st_dev, details.st_ino


def _plain_file_identity(path: Path, code: str) -> tuple[int, int]:
    if not path.is_file() or _is_reparse_or_link(path):
        raise LedgerAmbiguous(code, str(path))
    try:
        details = os.stat(path, follow_symlinks=False)
    except OSError as exc:
        raise LedgerAmbiguous(code, str(path)) from exc
    if not stat.S_ISREG(details.st_mode):
        raise LedgerAmbiguous(code, str(path))
    return details.st_dev, details.st_ino


def _read_record(path: Path) -> Mapping[str, Any]:
    if not path.is_file() or _is_reparse_or_link(path):
        raise LedgerAmbiguous("E_LEDGER_RECORD_PATH", str(path))
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise LedgerAmbiguous("E_LEDGER_READ", str(path)) from exc
    try:
        record = strict_json_loads(raw, max_bytes=1_048_576)
    except MatrixModelError as exc:
        raise LedgerAmbiguous("E_LEDGER_JSON", str(path)) from exc
    checked = _expect_mapping(record, "E_LEDGER_RECORD_TYPE", str(path))
    try:
        canonical = canonical_json_bytes(dict(checked))
    except MatrixModelError as exc:
        raise LedgerAmbiguous("E_LEDGER_RECORD_CANONICAL", str(path)) from exc
    if raw != canonical:
        raise LedgerAmbiguous("E_LEDGER_RECORD_CANONICAL", str(path))
    return checked


def _read_bounded_plain_bytes(
    path: Path, code: str, *, max_bytes: int = 1_048_576
) -> bytes:
    if not path.is_file() or _is_reparse_or_link(path):
        raise LedgerAmbiguous(code, str(path))
    try:
        if path.stat().st_size > max_bytes:
            raise LedgerAmbiguous(code, str(path))
        return path.read_bytes()
    except LedgerError:
        raise
    except OSError as exc:
        raise LedgerAmbiguous(code, str(path)) from exc


def _exact_entry_names(path: Path, expected: Iterable[str], code: str) -> None:
    _assert_plain_directory(path)
    try:
        observed = {entry.name for entry in os.scandir(path)}
    except OSError as exc:
        raise LedgerAmbiguous(code, str(path)) from exc
    if observed != set(expected):
        raise LedgerAmbiguous(code, str(path))


def _evidence_records(
    value: Any,
    path: str,
    *,
    cell_id: str,
    input_fingerprint: str,
    attempt_id: str,
    gate_id: str | None = None,
    allowed_gate_ids: Iterable[str] = (),
) -> list[dict[str, Any]]:
    if type(value) is not list:
        raise LedgerAmbiguous("E_LEDGER_EVIDENCE_TYPE", path)
    if len(value) > MAX_EVIDENCE_ITEMS:
        raise LedgerAmbiguous("E_LEDGER_EVIDENCE_COUNT", path)
    result: list[dict[str, Any]] = []
    kinds: set[str] = set()
    for index, raw in enumerate(value):
        item_path = f"{path}[{index}]"
        item = _expect_mapping(raw, "E_LEDGER_EVIDENCE_TYPE", item_path)
        _expect_keys(
            item,
            EVIDENCE_BINDING_FIELDS,
            "E_LEDGER_EVIDENCE_FIELDS",
            item_path,
        )
        if (
            item["schema"] != EVIDENCE_BINDING_SCHEMA
            or type(item["schema_version"]) is not int
            or item["schema_version"] != 1
        ):
            raise LedgerAmbiguous("E_LEDGER_EVIDENCE_SCHEMA", item_path)
        if (
            item["cell_id"] != cell_id
            or item["input_fingerprint"] != input_fingerprint
        ):
            raise LedgerAmbiguous("E_LEDGER_EVIDENCE_CELL_BINDING", item_path)
        if item["attempt_id"] != attempt_id:
            raise LedgerAmbiguous("E_LEDGER_EVIDENCE_ATTEMPT_BINDING", item_path)
        checked_gate = _expect_text(
            item["gate_id"], _ID_RE, "E_LEDGER_EVIDENCE_GATE", item_path
        )
        if gate_id is not None and checked_gate != gate_id:
            raise LedgerAmbiguous("E_LEDGER_EVIDENCE_GATE_BINDING", item_path)
        allowed_gates = tuple(allowed_gate_ids)
        if allowed_gates and checked_gate not in allowed_gates:
            raise LedgerAmbiguous("E_LEDGER_EVIDENCE_GATE_BINDING", item_path)
        kind = _expect_text(
            item["kind"], _ID_RE, "E_LEDGER_EVIDENCE_KIND", item_path
        )
        if kind in kinds:
            raise LedgerAmbiguous("E_LEDGER_EVIDENCE_DUPLICATE", item_path)
        kinds.add(kind)
        digest = _expect_text(
            item["sha256"], _SHA_RE, "E_LEDGER_EVIDENCE_HASH", item_path
        )
        if (
            type(item["bytes"]) is not int
            or item["bytes"] < 1
            or item["bytes"] > MAX_EVIDENCE_BYTES
        ):
            raise LedgerAmbiguous("E_LEDGER_EVIDENCE_BYTES", item_path)
        binding = _expect_text(
            item["binding_sha256"],
            _SHA_RE,
            "E_LEDGER_EVIDENCE_BINDING_HASH",
            item_path,
        )
        basis = {field: item[field] for field in EVIDENCE_BINDING_FIELDS[:-1]}
        try:
            expected_binding = sha256_value(basis)
        except MatrixModelError as exc:
            raise LedgerAmbiguous(
                "E_LEDGER_EVIDENCE_BINDING_VALUE", item_path
            ) from exc
        if binding != expected_binding:
            raise LedgerAmbiguous("E_LEDGER_EVIDENCE_BINDING_DIGEST", item_path)
        result.append(deepcopy(dict(item)))
    return result


class LedgerStore:
    """A no-overwrite ledger rooted in a private, caller-selected directory."""

    def __init__(self, root: Path | str, *, create: bool = True) -> None:
        candidate = Path(root)
        if not candidate.is_absolute():
            raise LedgerError("E_LEDGER_ROOT_NOT_ABSOLUTE", str(candidate))
        root_existed = os.path.lexists(candidate)
        existing_root_entries: set[str] = set()
        if root_existed:
            _assert_plain_directory(candidate)
            try:
                existing_root_entries = {
                    entry.name for entry in os.scandir(candidate)
                }
            except OSError as exc:
                raise LedgerError("E_LEDGER_ROOT_SCAN", str(candidate)) from exc
        self.root = candidate
        if create:
            try:
                self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
            except OSError as exc:
                raise LedgerError("E_LEDGER_ROOT_CREATE", str(candidate)) from exc
        _assert_plain_directory(self.root)
        self.cells_root = self.root / "cells"
        if create:
            try:
                self.cells_root.mkdir(exist_ok=True, mode=0o700)
            except OSError as exc:
                raise LedgerError("E_LEDGER_CELLS_CREATE", str(self.cells_root)) from exc
        _assert_plain_directory(self.cells_root)
        self.locks_root = self.root / ".locks"
        self.staging_root = self.root / ".staging"
        self.staging_recoveries_root = self.root / ".staging-recoveries"
        if create:
            self._mkdir(self.locks_root)
            self._mkdir(self.staging_root)
            self._mkdir(self.staging_recoveries_root)
        else:
            _assert_plain_directory(self.locks_root)
            _assert_plain_directory(self.staging_root)
            _assert_plain_directory(self.staging_recoveries_root)
        self.root_record_path = self.root / "ledger-root.json"
        if not self.root_record_path.exists():
            if not create or existing_root_entries:
                raise LedgerAmbiguous(
                    "E_LEDGER_ROOT_RECEIPT_MISSING", str(self.root_record_path)
                )
            self._atomic_create(
                self.root_record_path,
                {
                    "schema": LEDGER_ROOT_SCHEMA,
                    "schema_version": SCHEMA_VERSION,
                    "ledger_root_id": "ledger-root-"
                    + uuid.uuid4().hex
                    + uuid.uuid4().hex,
                },
            )
        self.ledger_root_id = self._load_ledger_root_record()
        self.root_lock_path = self.locks_root / "ledger-root.lock"
        self._initialize_root_lock(create=create)
        self._assert_root_layout()
        self._validate_staging_recovery_archives(allow_pending=True)

    def _load_ledger_root_record(self) -> str:
        record = _read_record(self.root_record_path)
        _expect_keys(
            record,
            ("schema", "schema_version", "ledger_root_id"),
            "E_LEDGER_ROOT_RECEIPT_FIELDS",
            str(self.root_record_path),
        )
        if (
            record["schema"] != LEDGER_ROOT_SCHEMA
            or type(record["schema_version"]) is not int
            or record["schema_version"] != 1
        ):
            raise LedgerAmbiguous(
                "E_LEDGER_ROOT_RECEIPT_SCHEMA", str(self.root_record_path)
            )
        return _expect_text(
            record["ledger_root_id"],
            _LEDGER_ROOT_RE,
            "E_LEDGER_ROOT_RECEIPT_ID",
            str(self.root_record_path),
        )

    def _inside(self, path: Path) -> None:
        try:
            common = os.path.commonpath((str(self.root), str(path)))
        except ValueError as exc:
            raise LedgerError("E_LEDGER_PATH_SCOPE", str(path)) from exc
        if os.path.normcase(common) != os.path.normcase(str(self.root)):
            raise LedgerError("E_LEDGER_PATH_SCOPE", str(path))

    def _mkdir(self, path: Path) -> None:
        self._inside(path)
        try:
            path.mkdir(exist_ok=True, mode=0o700)
        except OSError as exc:
            raise LedgerError("E_LEDGER_DIRECTORY_CREATE", str(path)) from exc
        _assert_plain_directory(path)

    @contextmanager
    def _root_lock(self):
        """Acquire the bounded repository-wide ledger consistency lock."""

        path = self.root_lock_path
        self._inside(path)
        _assert_plain_directory(self.root)
        before = _plain_directory_identity(self.locks_root)
        flags = os.O_RDWR | getattr(os, "O_BINARY", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(path, flags)
        except OSError as exc:
            raise LedgerConflict("E_LEDGER_ROOT_LOCK", str(path)) from exc
        locked = False
        try:
            details = os.fstat(descriptor)
            if (
                not stat.S_ISREG(details.st_mode)
                or details.st_size != 1
                or _is_reparse_or_link(path)
            ):
                raise LedgerConflict("E_LEDGER_ROOT_LOCK_PATH", str(path))
            after = _plain_directory_identity(self.locks_root)
            file_identity = (details.st_dev, details.st_ino)
            if (
                before != after
                or file_identity
                != _plain_file_identity(path, "E_LEDGER_ROOT_LOCK_PATH")
            ):
                raise LedgerConflict("E_LEDGER_ROOT_LOCK_PATH", str(path))
            os.lseek(descriptor, 0, os.SEEK_SET)
            try:
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
            except (OSError, ImportError) as exc:
                raise LedgerConflict("E_LEDGER_ROOT_BUSY", str(path)) from exc
            yield
            if (
                before != _plain_directory_identity(self.locks_root)
                or file_identity
                != _plain_file_identity(path, "E_LEDGER_ROOT_LOCK_PATH")
            ):
                raise LedgerConflict("E_LEDGER_ROOT_LOCK_PATH", str(path))
        finally:
            if locked:
                try:
                    os.lseek(descriptor, 0, os.SEEK_SET)
                    if os.name == "nt":
                        import msvcrt

                        msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(descriptor, fcntl.LOCK_UN)
                except (OSError, ImportError):
                    pass
            os.close(descriptor)

    def _initialize_root_lock(self, *, create: bool) -> None:
        path = self.root_lock_path
        self._inside(path)
        _assert_plain_directory(self.root)
        before = _plain_directory_identity(self.locks_root)
        flags = os.O_RDWR | getattr(os, "O_BINARY", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        if create:
            flags |= os.O_CREAT
        try:
            descriptor = os.open(path, flags, 0o600)
        except OSError as exc:
            raise LedgerError("E_LEDGER_ROOT_LOCK_OPEN", str(path)) from exc
        try:
            details = os.fstat(descriptor)
            if not stat.S_ISREG(details.st_mode) or _is_reparse_or_link(path):
                raise LedgerError("E_LEDGER_ROOT_LOCK_PATH", str(path))
            after = _plain_directory_identity(self.locks_root)
            if (
                before != after
                or (details.st_dev, details.st_ino)
                != _plain_file_identity(path, "E_LEDGER_ROOT_LOCK_PATH")
            ):
                raise LedgerError("E_LEDGER_ROOT_LOCK_PATH", str(path))
            if details.st_size == 0 and create:
                os.write(descriptor, b"\0")
                os.fsync(descriptor)
                details = os.fstat(descriptor)
            if details.st_size != 1:
                raise LedgerError("E_LEDGER_ROOT_LOCK_SIZE", str(path))
        finally:
            os.close(descriptor)

    def _assert_root_layout(self) -> None:
        _assert_plain_directory(self.root)
        _exact_entry_names(
            self.root,
            (
                ".locks",
                ".staging",
                ".staging-recoveries",
                "cells",
                "ledger-root.json",
            ),
            "E_LEDGER_ROOT_LAYOUT",
        )
        if self._load_ledger_root_record() != self.ledger_root_id:
            raise LedgerAmbiguous(
                "E_LEDGER_ROOT_RECEIPT_DRIFT", str(self.root_record_path)
            )
        for path in (
            self.locks_root,
            self.staging_root,
            self.staging_recoveries_root,
            self.cells_root,
        ):
            _assert_plain_directory(path)

    def _staging_snapshot(self, directory: Path) -> tuple[int, str]:
        """Hash one staging tree without exposing paths outside the ledger."""

        self._inside(directory)
        _assert_plain_directory(directory)
        entries: list[dict[str, Any]] = []

        def visit(current: Path, relative: str) -> None:
            try:
                children = sorted(
                    os.scandir(current), key=lambda item: item.name
                )
            except OSError as exc:
                raise LedgerAmbiguous(
                    "E_LEDGER_STAGING_SCAN", str(current)
                ) from exc
            for child in children:
                if len(entries) >= MAX_STAGING_ENTRIES:
                    raise LedgerAmbiguous(
                        "E_LEDGER_STAGING_ENTRY_LIMIT", str(directory)
                    )
                child_path = Path(child.path)
                child_relative = (
                    f"{relative}/{child.name}" if relative else child.name
                )
                if child.is_dir(follow_symlinks=False):
                    if _is_reparse_or_link(child_path):
                        raise LedgerAmbiguous(
                            "E_LEDGER_STAGING_REPARSE", child.path
                        )
                    entries.append(
                        {"path": child_relative, "kind": "directory"}
                    )
                    visit(child_path, child_relative)
                    continue
                if (
                    not child.is_file(follow_symlinks=False)
                    or _is_reparse_or_link(child_path)
                ):
                    raise LedgerAmbiguous(
                        "E_LEDGER_STAGING_ENTRY", child.path
                    )
                digest = hashlib.sha256()
                size = 0
                try:
                    with child_path.open("rb") as handle:
                        while True:
                            chunk = handle.read(1_048_576)
                            if not chunk:
                                break
                            size += len(chunk)
                            digest.update(chunk)
                except OSError as exc:
                    raise LedgerAmbiguous(
                        "E_LEDGER_STAGING_READ", child.path
                    ) from exc
                entries.append(
                    {
                        "path": child_relative,
                        "kind": "file",
                        "bytes": size,
                        "sha256": digest.hexdigest(),
                    }
                )

        visit(directory, "")
        return len(entries), sha256_value(
            {
                "schema": STAGING_SNAPSHOT_SCHEMA,
                "schema_version": SCHEMA_VERSION,
                "entries": entries,
            }
        )

    def _validate_staging_recovery_review(
        self,
        review: Any,
        *,
        staging_entry_count: int,
        staging_snapshot_sha256: str,
    ) -> Mapping[str, Any]:
        path = "staging-recovery-review"
        value = _expect_mapping(
            review, "E_LEDGER_STAGING_RECOVERY_REVIEW_TYPE", path
        )
        _expect_keys(
            value,
            (
                "schema",
                "schema_version",
                "staging_entry_count",
                "staging_snapshot_sha256",
                "operator_id",
                "reviewer_id",
                "reviewed_at",
                "finding_ids",
                "disposition",
            ),
            "E_LEDGER_STAGING_RECOVERY_REVIEW_FIELDS",
            path,
        )
        if (
            value["schema"] != STAGING_RECOVERY_REVIEW_SCHEMA
            or type(value["schema_version"]) is not int
            or value["schema_version"] != 1
            or type(value["staging_entry_count"]) is not int
            or value["staging_entry_count"] != staging_entry_count
            or value["staging_snapshot_sha256"]
            != staging_snapshot_sha256
            or value["disposition"] != "ARCHIVE_PRESERVED_STAGING"
        ):
            raise LedgerConflict(
                "E_LEDGER_STAGING_RECOVERY_REVIEW_STALE", path
            )
        if not 1 <= staging_entry_count <= MAX_STAGING_ENTRIES:
            raise LedgerConflict("E_LEDGER_STAGING_RECOVERY_COUNT", path)
        _expect_text(
            value["staging_snapshot_sha256"],
            _SHA_RE,
            "E_LEDGER_STAGING_RECOVERY_HASH",
            path,
        )
        operator_id = _expect_text(
            value["operator_id"], _ID_RE, "E_LEDGER_OPERATOR", path
        )
        reviewer_id = _expect_text(
            value["reviewer_id"], _ID_RE, "E_LEDGER_REVIEWER", path
        )
        if operator_id == reviewer_id:
            raise LedgerConflict(
                "E_LEDGER_STAGING_RECOVERY_REVIEWER_NOT_INDEPENDENT", path
            )
        _parse_utc(
            value["reviewed_at"], "E_LEDGER_STAGING_RECOVERY_TIME", path
        )
        findings = value["finding_ids"]
        if type(findings) is not list or not 1 <= len(findings) <= 32:
            raise LedgerConflict("E_LEDGER_STAGING_RECOVERY_FINDINGS", path)
        checked_findings: list[str] = []
        for finding in findings:
            checked = _expect_text(
                finding,
                _ID_RE,
                "E_LEDGER_STAGING_RECOVERY_FINDINGS",
                path,
            )
            if checked in checked_findings:
                raise LedgerConflict(
                    "E_LEDGER_STAGING_RECOVERY_FINDINGS", path
                )
            checked_findings.append(checked)
        if checked_findings != sorted(checked_findings):
            raise LedgerConflict("E_LEDGER_STAGING_RECOVERY_FINDINGS", path)
        canonical_json_bytes(dict(value))
        return deepcopy(dict(value))

    def make_staging_recovery_review(
        self,
        *,
        operator_id: str,
        reviewer_id: str,
        reviewed_at: str,
        finding_ids: Iterable[str],
    ) -> Mapping[str, Any]:
        """Bind independent review to the exact preserved staging bytes."""

        with self._root_lock():
            self._assert_root_layout()
            self._validate_staging_recovery_archives()
            count, snapshot = self._staging_snapshot(self.staging_root)
            if count == 0:
                raise LedgerConflict(
                    "E_LEDGER_STAGING_RECOVERY_EMPTY", str(self.staging_root)
                )
            review = {
                "schema": STAGING_RECOVERY_REVIEW_SCHEMA,
                "schema_version": SCHEMA_VERSION,
                "staging_entry_count": count,
                "staging_snapshot_sha256": snapshot,
                "operator_id": operator_id,
                "reviewer_id": reviewer_id,
                "reviewed_at": reviewed_at,
                "finding_ids": list(finding_ids),
                "disposition": "ARCHIVE_PRESERVED_STAGING",
            }
            checked = self._validate_staging_recovery_review(
                review,
                staging_entry_count=count,
                staging_snapshot_sha256=snapshot,
            )
            final_count, final_snapshot = self._staging_snapshot(
                self.staging_root
            )
            if (count, snapshot) != (final_count, final_snapshot):
                raise LedgerAmbiguous(
                    "E_LEDGER_STAGING_CHANGED", str(self.staging_root)
                )
            return checked

    def _make_staging_recovery_id(
        self, review: Mapping[str, Any], review_sha256: str
    ) -> str:
        return "staging-recovery-" + sha256_value(
            {
                "staging_entry_count": review["staging_entry_count"],
                "staging_snapshot_sha256": review[
                    "staging_snapshot_sha256"
                ],
                "operator_id": review["operator_id"],
                "reviewer_id": review["reviewer_id"],
                "approved_at": review["reviewed_at"],
                "review_sha256": review_sha256,
                "disposition": "ARCHIVE_PRESERVED_STAGING",
            }
        )

    def _write_exclusive_bytes(self, path: Path, payload: bytes) -> None:
        self._inside(path)
        _assert_plain_directory(path.parent)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        flags |= getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(path, flags, 0o600)
            try:
                written = 0
                while written < len(payload):
                    count = os.write(descriptor, payload[written:])
                    if count <= 0:
                        raise OSError("short write")
                    written += count
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        except FileExistsError as exc:
            raise LedgerConflict(
                "E_LEDGER_STAGING_RECOVERY_EXISTS", str(path)
            ) from exc
        except OSError as exc:
            raise LedgerAmbiguous(
                "E_LEDGER_STAGING_RECOVERY_WRITE", str(path)
            ) from exc

    def _write_or_resume_exclusive_bytes(
        self, path: Path, payload: bytes
    ) -> None:
        """Publish one metadata file from a resumable exact-prefix write."""

        self._inside(path)
        partial = path.with_name(path.name + ".partial")
        if os.path.lexists(path):
            if _read_bounded_plain_bytes(
                path, "E_LEDGER_STAGING_RECOVERY_METADATA"
            ) != payload:
                raise LedgerAmbiguous(
                    "E_LEDGER_STAGING_RECOVERY_METADATA", str(path)
                )
            if os.path.lexists(partial):
                if _read_bounded_plain_bytes(
                    partial, "E_LEDGER_STAGING_RECOVERY_METADATA"
                ) != payload:
                    raise LedgerAmbiguous(
                        "E_LEDGER_STAGING_RECOVERY_METADATA", str(partial)
                    )
                try:
                    os.unlink(partial)
                except OSError as exc:
                    raise LedgerAmbiguous(
                        "E_LEDGER_STAGING_RECOVERY_WRITE", str(partial)
                    ) from exc
            return
        if os.path.lexists(partial):
            existing = _read_bounded_plain_bytes(
                partial, "E_LEDGER_STAGING_RECOVERY_METADATA"
            )
            if not payload.startswith(existing):
                raise LedgerAmbiguous(
                    "E_LEDGER_STAGING_RECOVERY_METADATA", str(partial)
                )
        else:
            existing = b""
            self._write_exclusive_bytes(partial, b"")
        flags = os.O_WRONLY | os.O_APPEND
        flags |= getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(partial, flags)
            try:
                written = len(existing)
                while written < len(payload):
                    count = os.write(descriptor, payload[written:])
                    if count <= 0:
                        raise OSError("short write")
                    written += count
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            if _read_bounded_plain_bytes(
                partial, "E_LEDGER_STAGING_RECOVERY_METADATA"
            ) != payload:
                raise OSError("metadata verification failed")
            os.link(partial, path)
            os.unlink(partial)
        except FileExistsError as exc:
            raise LedgerConflict(
                "E_LEDGER_STAGING_RECOVERY_EXISTS", str(path)
            ) from exc
        except OSError as exc:
            raise LedgerAmbiguous(
                "E_LEDGER_STAGING_RECOVERY_WRITE", str(path)
            ) from exc

    def _validate_staging_recovery_record(
        self,
        recovery: Any,
        checked_review: Mapping[str, Any],
        *,
        recovery_id: str,
        staging_entry_count: int,
        staging_snapshot_sha256: str,
        path: Path,
    ) -> Mapping[str, Any]:
        record = _expect_mapping(
            recovery, "E_LEDGER_STAGING_RECOVERY_TYPE", str(path)
        )
        _expect_keys(
            record,
            (
                "schema",
                "schema_version",
                "recovery_id",
                "staging_entry_count",
                "staging_snapshot_sha256",
                "operator_id",
                "reviewer_id",
                "approved_at",
                "review_sha256",
                "review",
                "disposition",
            ),
            "E_LEDGER_STAGING_RECOVERY_FIELDS",
            str(path),
        )
        review_sha256 = sha256_value(checked_review)
        expected_id = self._make_staging_recovery_id(
            checked_review, review_sha256
        )
        if (
            record["schema"] != STAGING_RECOVERY_SCHEMA
            or type(record["schema_version"]) is not int
            or record["schema_version"] != 1
            or record["recovery_id"] != recovery_id
            or record["recovery_id"] != expected_id
            or type(record["staging_entry_count"]) is not int
            or record["staging_entry_count"] != staging_entry_count
            or record["staging_snapshot_sha256"]
            != staging_snapshot_sha256
            or record["operator_id"] != checked_review["operator_id"]
            or record["reviewer_id"] != checked_review["reviewer_id"]
            or record["approved_at"] != checked_review["reviewed_at"]
            or record["review_sha256"] != review_sha256
            or canonical_json_bytes(record["review"])
            != canonical_json_bytes(checked_review)
            or record["disposition"] != "ARCHIVE_PRESERVED_STAGING"
        ):
            raise LedgerAmbiguous(
                "E_LEDGER_STAGING_RECOVERY_BINDING", str(path)
            )
        return deepcopy(dict(record))

    def _validate_complete_staging_recovery(
        self, path: Path, recovery_id: str
    ) -> None:
        _exact_entry_names(
            path,
            ("preserved", "recovery.json", "review.json"),
            "E_LEDGER_STAGING_RECOVERY_LAYOUT",
        )
        review = _read_record(path / "review.json")
        recovery = _read_record(path / "recovery.json")
        count, snapshot = self._staging_snapshot(path / "preserved")
        checked_review = self._validate_staging_recovery_review(
            review,
            staging_entry_count=count,
            staging_snapshot_sha256=snapshot,
        )
        self._validate_staging_recovery_record(
            recovery,
            checked_review,
            recovery_id=recovery_id,
            staging_entry_count=count,
            staging_snapshot_sha256=snapshot,
            path=path,
        )

    def _validate_pending_staging_recovery(
        self, path: Path, recovery_id: str
    ) -> None:
        _assert_plain_directory(path)
        try:
            observed = {entry.name for entry in os.scandir(path)}
        except OSError as exc:
            raise LedgerAmbiguous(
                "E_LEDGER_STAGING_RECOVERY_SCAN", str(path)
            ) from exc
        valid_phases = (
            frozenset(),
            frozenset(("review.json.partial",)),
            frozenset(("review.json", "review.json.partial")),
            frozenset(("review.json",)),
            frozenset(("review.json", "recovery.json.partial")),
            frozenset(
                ("review.json", "recovery.json", "recovery.json.partial")
            ),
            frozenset(("review.json", "recovery.json")),
            frozenset(("review.json", "recovery.json", "preserved")),
        )
        if frozenset(observed) not in valid_phases:
            raise LedgerAmbiguous(
                "E_LEDGER_STAGING_RECOVERY_PENDING_LAYOUT", str(path)
            )
        if "review.json.partial" in observed and "review.json" not in observed:
            partial = path / "review.json.partial"
            _read_bounded_plain_bytes(
                partial, "E_LEDGER_STAGING_RECOVERY_METADATA"
            )
            return
        if "review.json" not in observed:
            return
        review = _read_record(path / "review.json")
        if "review.json.partial" in observed:
            partial = path / "review.json.partial"
            if _read_bounded_plain_bytes(
                partial, "E_LEDGER_STAGING_RECOVERY_METADATA"
            ) != canonical_json_bytes(review):
                raise LedgerAmbiguous(
                    "E_LEDGER_STAGING_RECOVERY_METADATA", str(partial)
                )
        checked_review = self._validate_staging_recovery_review(
            review,
            staging_entry_count=review.get("staging_entry_count"),
            staging_snapshot_sha256=review.get(
                "staging_snapshot_sha256"
            ),
        )
        review_sha256 = sha256_value(checked_review)
        if self._make_staging_recovery_id(
            checked_review, review_sha256
        ) != recovery_id:
            raise LedgerAmbiguous(
                "E_LEDGER_STAGING_RECOVERY_BINDING", str(path)
            )
        if "recovery.json.partial" in observed and "recovery.json" not in observed:
            partial = path / "recovery.json.partial"
            _read_bounded_plain_bytes(
                partial, "E_LEDGER_STAGING_RECOVERY_METADATA"
            )
            return
        if "recovery.json" not in observed:
            return
        recovery = _read_record(path / "recovery.json")
        if "recovery.json.partial" in observed:
            partial = path / "recovery.json.partial"
            if _read_bounded_plain_bytes(
                partial, "E_LEDGER_STAGING_RECOVERY_METADATA"
            ) != canonical_json_bytes(recovery):
                raise LedgerAmbiguous(
                    "E_LEDGER_STAGING_RECOVERY_METADATA", str(partial)
                )
        count = checked_review["staging_entry_count"]
        snapshot = checked_review["staging_snapshot_sha256"]
        if "preserved" in observed:
            count, snapshot = self._staging_snapshot(path / "preserved")
            checked_review = self._validate_staging_recovery_review(
                review,
                staging_entry_count=count,
                staging_snapshot_sha256=snapshot,
            )
        self._validate_staging_recovery_record(
            recovery,
            checked_review,
            recovery_id=recovery_id,
            staging_entry_count=count,
            staging_snapshot_sha256=snapshot,
            path=path,
        )

    def _validate_staging_recovery_archives(
        self, *, allow_pending: bool = False
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        _assert_plain_directory(self.staging_recoveries_root)
        try:
            entries = sorted(
                os.scandir(self.staging_recoveries_root),
                key=lambda item: item.name,
            )
        except OSError as exc:
            raise LedgerAmbiguous(
                "E_LEDGER_STAGING_RECOVERY_SCAN",
                str(self.staging_recoveries_root),
            ) from exc
        recovery_ids: list[str] = []
        pending_ids: list[str] = []
        for entry in entries:
            path = Path(entry.path)
            pending_match = _PENDING_STAGING_RECOVERY_RE.fullmatch(
                entry.name
            )
            if pending_match is not None:
                if (
                    not entry.is_dir(follow_symlinks=False)
                    or _is_reparse_or_link(path)
                ):
                    raise LedgerAmbiguous(
                        "E_LEDGER_STAGING_RECOVERY_ENTRY", entry.path
                    )
                recovery_id = pending_match.group(1)
                self._validate_pending_staging_recovery(path, recovery_id)
                pending_ids.append(recovery_id)
                continue
            if (
                _STAGING_RECOVERY_RE.fullmatch(entry.name) is None
                or not entry.is_dir(follow_symlinks=False)
                or _is_reparse_or_link(path)
            ):
                raise LedgerAmbiguous(
                    "E_LEDGER_STAGING_RECOVERY_ENTRY", entry.path
                )
            self._validate_complete_staging_recovery(path, entry.name)
            recovery_ids.append(entry.name)
        if len(pending_ids) > 1 or set(pending_ids) & set(recovery_ids):
            raise LedgerAmbiguous(
                "E_LEDGER_STAGING_RECOVERY_PENDING_COUNT",
                str(self.staging_recoveries_root),
            )
        if pending_ids and not allow_pending:
            raise LedgerAmbiguous(
                "E_LEDGER_STAGING_RECOVERY_PENDING",
                str(self.staging_recoveries_root),
            )
        return tuple(recovery_ids), tuple(pending_ids)

    def resolve_staging(
        self, review: Mapping[str, Any]
    ) -> str:
        """Archive reviewed staging bytes and restore an empty staging root."""

        with self._root_lock():
            self._assert_root_layout()
            recovery_ids, pending_ids = (
                self._validate_staging_recovery_archives(
                    allow_pending=True
                )
            )
            review_value = _expect_mapping(
                review,
                "E_LEDGER_STAGING_RECOVERY_REVIEW_TYPE",
                "staging-recovery-review",
            )
            checked_review = self._validate_staging_recovery_review(
                review_value,
                staging_entry_count=review_value.get(
                    "staging_entry_count"
                ),
                staging_snapshot_sha256=review_value.get(
                    "staging_snapshot_sha256"
                ),
            )
            review_sha256 = sha256_value(checked_review)
            recovery_id = self._make_staging_recovery_id(
                checked_review, review_sha256
            )
            final = self.staging_recoveries_root / recovery_id
            pending = self.staging_recoveries_root / (
                ".pending-" + recovery_id
            )
            if recovery_id in recovery_ids:
                if pending_ids:
                    raise LedgerAmbiguous(
                        "E_LEDGER_STAGING_RECOVERY_PENDING_COUNT",
                        str(self.staging_recoveries_root),
                    )
                self._assert_staging_empty()
                archived_review = _read_record(final / "review.json")
                if canonical_json_bytes(archived_review) != canonical_json_bytes(
                    checked_review
                ):
                    raise LedgerConflict(
                        "E_LEDGER_STAGING_RECOVERY_EXISTS", recovery_id
                    )
                return recovery_id
            if pending_ids and pending_ids != (recovery_id,):
                raise LedgerConflict(
                    "E_LEDGER_STAGING_RECOVERY_PENDING", pending_ids[0]
                )
            preserved = pending / "preserved"
            current_count, current_snapshot = self._staging_snapshot(
                self.staging_root
            )
            preserved_exists = os.path.lexists(preserved)
            if preserved_exists:
                if current_count != 0:
                    raise LedgerAmbiguous(
                        "E_LEDGER_STAGING_RECOVERY_DUPLICATE_SOURCE",
                        str(pending),
                    )
                count, snapshot = self._staging_snapshot(preserved)
            else:
                count, snapshot = current_count, current_snapshot
            if count == 0:
                raise LedgerConflict(
                    "E_LEDGER_STAGING_RECOVERY_EMPTY", str(self.staging_root)
                )
            checked_review = self._validate_staging_recovery_review(
                checked_review,
                staging_entry_count=count,
                staging_snapshot_sha256=snapshot,
            )
            if not os.path.lexists(pending):
                try:
                    pending.mkdir(mode=0o700)
                except OSError as exc:
                    raise LedgerAmbiguous(
                        "E_LEDGER_STAGING_RECOVERY_CREATE", str(pending)
                    ) from exc
            _assert_plain_directory(pending)
            record = {
                "schema": STAGING_RECOVERY_SCHEMA,
                "schema_version": SCHEMA_VERSION,
                "recovery_id": recovery_id,
                "staging_entry_count": count,
                "staging_snapshot_sha256": snapshot,
                "operator_id": checked_review["operator_id"],
                "reviewer_id": checked_review["reviewer_id"],
                "approved_at": checked_review["reviewed_at"],
                "review_sha256": review_sha256,
                "review": checked_review,
                "disposition": "ARCHIVE_PRESERVED_STAGING",
            }
            self._write_or_resume_exclusive_bytes(
                pending / "review.json",
                canonical_json_bytes(checked_review),
            )
            self._write_or_resume_exclusive_bytes(
                pending / "recovery.json", canonical_json_bytes(record)
            )
            if not preserved_exists:
                final_count, final_snapshot = self._staging_snapshot(
                    self.staging_root
                )
                if (count, snapshot) != (final_count, final_snapshot):
                    raise LedgerAmbiguous(
                        "E_LEDGER_STAGING_CHANGED", str(self.staging_root)
                    )
                try:
                    os.rename(self.staging_root, preserved)
                    self.staging_root.mkdir(mode=0o700)
                except OSError as exc:
                    raise LedgerAmbiguous(
                        "E_LEDGER_STAGING_RECOVERY_PUBLISH", str(pending)
                    ) from exc
            self._assert_staging_empty()
            self._validate_pending_staging_recovery(pending, recovery_id)
            try:
                os.rename(pending, final)
            except OSError as exc:
                raise LedgerAmbiguous(
                    "E_LEDGER_STAGING_RECOVERY_PUBLISH", str(pending)
                ) from exc
            self._validate_staging_recovery_archives()
            return recovery_id

    @contextmanager
    def _mutation_lock(self, cell_id: str):
        """Serialize one mutation against root validation and the cell."""

        with self._root_lock():
            self._assert_root_layout()
            self._validate_staging_recovery_archives()
            self._assert_staging_empty()
            with self._cell_lock(cell_id):
                yield
            self._assert_staging_empty()
            self._validate_staging_recovery_archives()

    @contextmanager
    def _cell_lock(self, cell_id: str):
        """Serialize every mutation for one cell across local processes."""

        _expect_text(cell_id, _CELL_RE, "E_LEDGER_CELL_ID", "cell_id")
        path = self.locks_root / f"{cell_id}.lock"
        self._inside(path)
        flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_BINARY", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(path, flags, 0o600)
        except OSError as exc:
            raise LedgerConflict("E_LEDGER_CELL_LOCK", str(path)) from exc
        locked = False
        try:
            details = os.fstat(descriptor)
            if not stat.S_ISREG(details.st_mode) or _is_reparse_or_link(path):
                raise LedgerConflict("E_LEDGER_CELL_LOCK_PATH", str(path))
            if details.st_size == 0:
                os.write(descriptor, b"\0")
                os.fsync(descriptor)
            os.lseek(descriptor, 0, os.SEEK_SET)
            try:
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
            except (OSError, ImportError) as exc:
                raise LedgerConflict("E_LEDGER_CELL_BUSY", cell_id) from exc
            yield
        finally:
            if locked:
                try:
                    os.lseek(descriptor, 0, os.SEEK_SET)
                    if os.name == "nt":
                        import msvcrt

                        msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(descriptor, fcntl.LOCK_UN)
                except (OSError, ImportError):
                    pass
            os.close(descriptor)

    def _atomic_create_bytes(self, target: Path, payload: bytes) -> str:
        """Publish immutable bytes with exclusive hard-link finalization."""

        self._inside(target)
        _assert_plain_directory(target.parent)
        if target.exists():
            raise LedgerConflict("E_LEDGER_TARGET_EXISTS", str(target))
        partial = self.staging_root / (
            f"{target.name}.{uuid.uuid4().hex}.partial"
        )
        self._inside(partial)
        descriptor: int | None = None
        try:
            descriptor = os.open(
                partial,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0),
                0o600,
            )
            offset = 0
            while offset < len(payload):
                written = os.write(descriptor, payload[offset:])
                if written <= 0:
                    raise OSError("short ledger write")
                offset += written
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = None
            os.link(partial, target)
            if os.name != "nt":
                directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
                parent_descriptor = os.open(target.parent, directory_flags)
                try:
                    os.fsync(parent_descriptor)
                finally:
                    os.close(parent_descriptor)
            os.unlink(partial)
        except FileExistsError as exc:
            raise LedgerConflict("E_LEDGER_TARGET_RACE", str(target)) from exc
        except OSError as exc:
            # The partial file is evidence of an ambiguous write and is preserved.
            raise LedgerAmbiguous("E_LEDGER_ATOMIC_CREATE", str(target)) from exc
        finally:
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
        return hashlib.sha256(payload).hexdigest()

    def _atomic_create(self, target: Path, record: Mapping[str, Any]) -> str:
        """Publish one canonical immutable JSON file."""

        return self._atomic_create_bytes(
            target, canonical_json_bytes(dict(record))
        )

    def _cell_dir(self, cell_id: str) -> Path:
        if type(cell_id) is not str or _CELL_RE.fullmatch(cell_id) is None:
            raise LedgerError("E_LEDGER_CELL_ID", "cell_id")
        return self.cells_root / cell_id

    def _ensure_cell(self, cell: MatrixCell) -> Path:
        cell_dir = self._cell_dir(cell.cell_id)
        self._mkdir(cell_dir)
        cell_record = cell_dir / "cell.json"
        expected = {
            "schema": CELL_RECORD_SCHEMA,
            "schema_version": SCHEMA_VERSION,
            "cell_id": cell.cell_id,
            "input_fingerprint": cell.input_fingerprint,
            "identity": deepcopy(dict(cell.identity)),
        }
        if not cell_record.exists():
            self._atomic_create(cell_record, expected)
        else:
            actual = _read_record(cell_record)
            if canonical_json_bytes(actual) != canonical_json_bytes(expected):
                raise LedgerConflict("E_LEDGER_CELL_DRIFT", str(cell_record))
        attempts = cell_dir / "attempts"
        recoveries = cell_dir / "recoveries"
        self._mkdir(attempts)
        self._mkdir(recoveries)
        _exact_entry_names(
            cell_dir,
            ("cell.json", "attempts", "recoveries"),
            "E_LEDGER_CELL_LAYOUT",
        )
        return cell_dir

    def _attempt_directories(self, cell_dir: Path) -> list[tuple[int, str, Path]]:
        attempts_dir = cell_dir / "attempts"
        _assert_plain_directory(attempts_dir)
        result: list[tuple[int, str, Path]] = []
        try:
            entries = sorted(os.scandir(attempts_dir), key=lambda entry: entry.name)
        except OSError as exc:
            raise LedgerAmbiguous("E_LEDGER_ATTEMPT_SCAN", str(attempts_dir)) from exc
        for entry in entries:
            match = _ATTEMPT_DIR_RE.fullmatch(entry.name)
            if match is None or not entry.is_dir(follow_symlinks=False):
                raise LedgerAmbiguous("E_LEDGER_ATTEMPT_ENTRY", entry.path)
            path = Path(entry.path)
            if _is_reparse_or_link(path):
                raise LedgerAmbiguous("E_LEDGER_ATTEMPT_REPARSE", entry.path)
            result.append((int(match.group(1)), match.group(2), path))
        numbers = [number for number, _, _ in result]
        if numbers and numbers != list(range(1, len(numbers) + 1)):
            raise LedgerAmbiguous("E_LEDGER_ATTEMPT_SEQUENCE", str(attempts_dir))
        return result

    def _load_cell_record(self, cell_dir: Path) -> Mapping[str, Any]:
        _exact_entry_names(
            cell_dir,
            ("cell.json", "attempts", "recoveries"),
            "E_LEDGER_CELL_LAYOUT",
        )
        path = cell_dir / "cell.json"
        record = _read_record(path)
        _expect_keys(
            record,
            ("schema", "schema_version", "cell_id", "input_fingerprint", "identity"),
            "E_LEDGER_CELL_FIELDS",
            str(path),
        )
        if (
            record["schema"] != CELL_RECORD_SCHEMA
            or type(record["schema_version"]) is not int
            or record["schema_version"] != 1
        ):
            raise LedgerAmbiguous("E_LEDGER_CELL_SCHEMA", str(path))
        cell_id = _expect_text(record["cell_id"], _CELL_RE, "E_LEDGER_CELL_ID", str(path))
        fingerprint = _expect_text(
            record["input_fingerprint"], _SHA_RE, "E_LEDGER_FINGERPRINT", str(path)
        )
        identity = _expect_mapping(
            record["identity"], "E_LEDGER_CELL_IDENTITY", str(path)
        )
        expected_fingerprint = sha256_value(identity)
        if fingerprint != expected_fingerprint or cell_id != f"cell-{expected_fingerprint}":
            raise LedgerAmbiguous("E_LEDGER_CELL_DIGEST", str(path))
        return record

    def _find_attempt(self, cell_id: str, attempt_id: str) -> tuple[int, Path]:
        if type(attempt_id) is not str or _ATTEMPT_RE.fullmatch(attempt_id) is None:
            raise LedgerError("E_LEDGER_ATTEMPT_ID", "attempt_id")
        cell_dir = self._cell_dir(cell_id)
        if not cell_dir.is_dir():
            raise LedgerError("E_LEDGER_CELL_MISSING", str(cell_dir))
        cell_record = self._load_cell_record(cell_dir)
        if cell_record["cell_id"] != cell_id:
            raise LedgerAmbiguous("E_LEDGER_CELL_IDENTITY", str(cell_dir))
        matches = [
            (number, path)
            for number, observed_id, path in self._attempt_directories(cell_dir)
            if observed_id == attempt_id
        ]
        if len(matches) != 1:
            raise LedgerAmbiguous("E_LEDGER_ATTEMPT_LOOKUP", attempt_id)
        return matches[0]

    def _load_attempt_record(
        self, path: Path, expected_number: int, expected_id: str
    ) -> Mapping[str, Any]:
        _assert_plain_directory(path)
        try:
            observed = {entry.name for entry in os.scandir(path)}
        except OSError as exc:
            raise LedgerAmbiguous("E_LEDGER_ATTEMPT_LAYOUT", str(path)) from exc
        required = {"attempt.json", "events", "evidence"}
        allowed = required | {"result.json"}
        legacy_partials = {
            name
            for name in observed
            if re.fullmatch(r"\.(?:attempt|result)\.json\.partial-[0-9a-f]{32}", name)
        }
        if legacy_partials:
            raise LedgerAmbiguous("E_LEDGER_LEGACY_PARTIAL", str(path))
        if (
            not required.issubset(observed)
            or not observed.issubset(allowed)
        ):
            raise LedgerAmbiguous("E_LEDGER_ATTEMPT_LAYOUT", str(path))
        _assert_plain_directory(path / "events")
        _assert_plain_directory(path / "evidence")
        if "result.json" in observed:
            result_path = path / "result.json"
            if not result_path.is_file() or _is_reparse_or_link(result_path):
                raise LedgerAmbiguous("E_LEDGER_RESULT_PATH", str(result_path))
        record_path = path / "attempt.json"
        record = _read_record(record_path)
        _expect_keys(
            record,
            (
                "schema",
                "schema_version",
                "attempt_id",
                "attempt_number",
                "cell_id",
                "input_fingerprint",
                "owner_id",
                "started_at",
                "recovery_id",
            ),
            "E_LEDGER_ATTEMPT_FIELDS",
            str(record_path),
        )
        if (
            record["schema"] != ATTEMPT_SCHEMA
            or type(record["schema_version"]) is not int
            or record["schema_version"] != 1
        ):
            raise LedgerAmbiguous("E_LEDGER_ATTEMPT_SCHEMA", str(record_path))
        if (
            record["attempt_id"] != expected_id
            or type(record["attempt_number"]) is not int
            or record["attempt_number"] != expected_number
        ):
            raise LedgerAmbiguous("E_LEDGER_ATTEMPT_IDENTITY", str(record_path))
        cell_id = _expect_text(
            record["cell_id"], _CELL_RE, "E_LEDGER_CELL_ID", str(record_path)
        )
        fingerprint = _expect_text(
            record["input_fingerprint"], _SHA_RE, "E_LEDGER_FINGERPRINT", str(record_path)
        )
        owner_id = _expect_text(
            record["owner_id"], _ID_RE, "E_LEDGER_OWNER", str(record_path)
        )
        _parse_utc(
            record["started_at"], "E_LEDGER_ATTEMPT_TIME", str(record_path)
        )
        recovery_id = record["recovery_id"]
        if recovery_id is not None:
            _expect_text(recovery_id, _RECOVERY_RE, "E_LEDGER_RECOVERY_ID", str(record_path))
        expected_attempt_id = "attempt-" + sha256_value(
            {
                "cell_id": cell_id,
                "input_fingerprint": fingerprint,
                "attempt_number": expected_number,
                "started_at": record["started_at"],
                "owner_id": owner_id,
                "recovery_id": recovery_id,
            }
        )
        if expected_attempt_id != expected_id:
            raise LedgerAmbiguous("E_LEDGER_ATTEMPT_DIGEST", str(record_path))
        return record

    def _attempt_snapshot_sha256(self, attempt_path: Path) -> str:
        """Hash every plain directory and file in one attempt without parsing it."""

        _assert_plain_directory(attempt_path)
        entries: list[dict[str, Any]] = []

        def visit(directory: Path, relative: str) -> None:
            try:
                children = sorted(os.scandir(directory), key=lambda item: item.name)
            except OSError as exc:
                raise LedgerAmbiguous(
                    "E_LEDGER_SNAPSHOT_SCAN", str(directory)
                ) from exc
            for child in children:
                child_path = Path(child.path)
                child_relative = (
                    f"{relative}/{child.name}" if relative else child.name
                )
                if child.is_dir(follow_symlinks=False):
                    if _is_reparse_or_link(child_path):
                        raise LedgerAmbiguous(
                            "E_LEDGER_SNAPSHOT_REPARSE", child.path
                        )
                    entries.append({"path": child_relative, "kind": "directory"})
                    visit(child_path, child_relative)
                    continue
                if not child.is_file(follow_symlinks=False) or _is_reparse_or_link(
                    child_path
                ):
                    raise LedgerAmbiguous("E_LEDGER_SNAPSHOT_ENTRY", child.path)
                digest = hashlib.sha256()
                size = 0
                try:
                    with child_path.open("rb") as handle:
                        while True:
                            chunk = handle.read(1_048_576)
                            if not chunk:
                                break
                            size += len(chunk)
                            digest.update(chunk)
                except OSError as exc:
                    raise LedgerAmbiguous(
                        "E_LEDGER_SNAPSHOT_READ", child.path
                    ) from exc
                entries.append(
                    {
                        "path": child_relative,
                        "kind": "file",
                        "bytes": size,
                        "sha256": digest.hexdigest(),
                    }
                )

        visit(attempt_path, "")
        return sha256_value(
            {
                "schema": ATTEMPT_SNAPSHOT_SCHEMA,
                "schema_version": SCHEMA_VERSION,
                "entries": entries,
            }
        )

    def _latest_attempt_recorded_at(
        self, attempt_path: Path, attempt: Mapping[str, Any]
    ) -> str:
        latest = attempt["started_at"]
        latest_value = _parse_utc(
            latest, "E_LEDGER_ATTEMPT_TIME", str(attempt_path)
        )
        candidates: list[Path] = []
        events_dir = attempt_path / "events"
        if events_dir.is_dir() and not _is_reparse_or_link(events_dir):
            try:
                candidates.extend(
                    Path(item.path)
                    for item in os.scandir(events_dir)
                    if item.is_file(follow_symlinks=False)
                )
            except OSError:
                pass
        result_path = attempt_path / "result.json"
        if result_path.is_file() and not _is_reparse_or_link(result_path):
            candidates.append(result_path)
        for candidate in candidates:
            try:
                raw = candidate.read_bytes()
                record = _expect_mapping(
                    strict_json_loads(raw, max_bytes=1_048_576),
                    "E_LEDGER_RECOVERY_TIME",
                    str(candidate),
                )
                timestamp = record.get("recorded_at", record.get("finished_at"))
                parsed = _parse_utc(timestamp, "E_LEDGER_RECOVERY_TIME", str(candidate))
            except (OSError, LedgerError, MatrixModelError, AttributeError):
                continue
            if parsed > latest_value:
                latest = timestamp
                latest_value = parsed
        return latest

    def recovery_review_context(
        self, cell: MatrixCell, failed_attempt_id: str
    ) -> Mapping[str, Any]:
        """Return the exact immutable facts that an independent review must bind."""

        with self._mutation_lock(cell.cell_id):
            cell_dir = self._ensure_cell(cell)
            attempts = self._attempt_directories(cell_dir)
            if not attempts or attempts[-1][1] != failed_attempt_id:
                raise LedgerConflict(
                    "E_LEDGER_RECOVERY_NOT_LATEST", failed_attempt_id
                )
            self._validate_recovery_records(cell, attempts)
            number, attempt_id, attempt_path = attempts[-1]
            attempt = self._load_attempt_record(attempt_path, number, attempt_id)
            try:
                inspection, _ = self._inspect_attempt_state(
                    cell.cell_id, failed_attempt_id
                )
            except LedgerAmbiguous:
                inspection = None
            if inspection is not None and inspection.state == "PASS":
                raise LedgerConflict("E_LEDGER_COMPLETED_CELL", failed_attempt_id)
            return {
                "cell_id": cell.cell_id,
                "input_fingerprint": cell.input_fingerprint,
                "failed_attempt_id": failed_attempt_id,
                "failed_attempt_state_sha256": self._attempt_snapshot_sha256(
                    attempt_path
                ),
                "latest_recorded_at": self._latest_attempt_recorded_at(
                    attempt_path, attempt
                ),
            }

    def make_recovery_review(
        self,
        cell: MatrixCell,
        failed_attempt_id: str,
        *,
        reviewed_at: str,
        reviewer_id: str,
        finding_ids: Iterable[str],
    ) -> Mapping[str, Any]:
        """Build canonical review bytes from a separately observed context."""

        context = self.recovery_review_context(cell, failed_attempt_id)
        return {
            "schema": RECOVERY_REVIEW_SCHEMA,
            "schema_version": SCHEMA_VERSION,
            **context,
            "reviewed_at": reviewed_at,
            "reviewer_id": reviewer_id,
            "finding_ids": list(finding_ids),
            "disposition": "AUTHORIZE_NEW_ATTEMPT",
        }

    def _validate_recovery_review(
        self,
        review: Any,
        cell: MatrixCell,
        failed_attempt_id: str,
        attempt_path: Path,
        attempt: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        path = "recovery-review"
        value = _expect_mapping(review, "E_LEDGER_RECOVERY_REVIEW_TYPE", path)
        _expect_keys(
            value,
            (
                "schema",
                "schema_version",
                "cell_id",
                "input_fingerprint",
                "failed_attempt_id",
                "failed_attempt_state_sha256",
                "latest_recorded_at",
                "reviewed_at",
                "reviewer_id",
                "finding_ids",
                "disposition",
            ),
            "E_LEDGER_RECOVERY_REVIEW_FIELDS",
            path,
        )
        if (
            value["schema"] != RECOVERY_REVIEW_SCHEMA
            or type(value["schema_version"]) is not int
            or value["schema_version"] != 1
            or value["cell_id"] != cell.cell_id
            or value["input_fingerprint"] != cell.input_fingerprint
            or value["failed_attempt_id"] != failed_attempt_id
            or value["disposition"] != "AUTHORIZE_NEW_ATTEMPT"
        ):
            raise LedgerConflict("E_LEDGER_RECOVERY_REVIEW_BINDING", path)
        snapshot = self._attempt_snapshot_sha256(attempt_path)
        latest = self._latest_attempt_recorded_at(attempt_path, attempt)
        if (
            _expect_text(
                value["failed_attempt_state_sha256"],
                _SHA_RE,
                "E_LEDGER_RECOVERY_REVIEW_HASH",
                path,
            )
            != snapshot
            or value["latest_recorded_at"] != latest
        ):
            raise LedgerConflict("E_LEDGER_RECOVERY_REVIEW_STALE", path)
        latest_time = _parse_utc(latest, "E_LEDGER_RECOVERY_TIME", path)
        reviewed_time = _parse_utc(
            value["reviewed_at"], "E_LEDGER_RECOVERY_TIME", path
        )
        if reviewed_time <= latest_time:
            raise LedgerConflict("E_LEDGER_RECOVERY_REVIEW_TIME", path)
        _expect_text(
            value["reviewer_id"], _ID_RE, "E_LEDGER_REVIEWER", path
        )
        findings = value["finding_ids"]
        if type(findings) is not list or not 1 <= len(findings) <= 32:
            raise LedgerConflict("E_LEDGER_RECOVERY_FINDINGS", path)
        observed: set[str] = set()
        for finding in findings:
            checked = _expect_text(
                finding, _ID_RE, "E_LEDGER_RECOVERY_FINDINGS", path
            )
            if checked in observed:
                raise LedgerConflict("E_LEDGER_RECOVERY_FINDINGS", path)
            observed.add(checked)
        canonical_json_bytes(dict(value))
        return deepcopy(dict(value))

    def _assert_attempt_writable(
        self, cell: MatrixCell, attempt_id: str
    ) -> None:
        cell_dir = self._cell_dir(cell.cell_id)
        attempts = self._attempt_directories(cell_dir)
        if not attempts or attempts[-1][1] != attempt_id:
            raise LedgerConflict("E_LEDGER_ATTEMPT_SEALED", attempt_id)
        if self._validate_recovery_records(cell, attempts) is not None:
            raise LedgerConflict("E_LEDGER_ATTEMPT_SEALED", attempt_id)

    def _evidence_path(
        self, attempt_path: Path, kind: str, digest: str
    ) -> Path:
        checked_kind = _expect_text(
            kind, _ID_RE, "E_LEDGER_EVIDENCE_KIND", "kind"
        )
        checked_digest = _expect_text(
            digest, _SHA_RE, "E_LEDGER_EVIDENCE_HASH", "sha256"
        )
        return attempt_path / "evidence" / f"{checked_kind}-{checked_digest}.blob"

    def _evidence_receipt_path(
        self, attempt_path: Path, kind: str, digest: str
    ) -> Path:
        checked_kind = _expect_text(
            kind, _ID_RE, "E_LEDGER_EVIDENCE_KIND", "kind"
        )
        checked_digest = _expect_text(
            digest, _SHA_RE, "E_LEDGER_EVIDENCE_HASH", "sha256"
        )
        return (
            attempt_path
            / "evidence"
            / f"{checked_kind}-{checked_digest}.receipt.json"
        )

    def _scan_evidence_directory(
        self, attempt_path: Path
    ) -> dict[tuple[str, str], tuple[Path, Path]]:
        evidence_dir = attempt_path / "evidence"
        _assert_plain_directory(evidence_dir)
        partial: dict[tuple[str, str], dict[str, Path]] = {}
        try:
            entries = sorted(os.scandir(evidence_dir), key=lambda entry: entry.name)
        except OSError as exc:
            raise LedgerAmbiguous(
                "E_LEDGER_EVIDENCE_SCAN", str(evidence_dir)
            ) from exc
        for entry in entries:
            if ".partial-" in entry.name:
                raise LedgerAmbiguous("E_LEDGER_PARTIAL_EVIDENCE", entry.path)
            blob_match = _EVIDENCE_FILE_RE.fullmatch(entry.name)
            receipt_match = _EVIDENCE_RECEIPT_FILE_RE.fullmatch(entry.name)
            match = blob_match or receipt_match
            if match is None or not entry.is_file(follow_symlinks=False):
                raise LedgerAmbiguous("E_LEDGER_EVIDENCE_ENTRY", entry.path)
            path = Path(entry.path)
            if _is_reparse_or_link(path):
                raise LedgerAmbiguous("E_LEDGER_EVIDENCE_REPARSE", entry.path)
            key = (match.group(1), match.group(2))
            part = "blob" if blob_match is not None else "receipt"
            pair = partial.setdefault(key, {})
            if part in pair:
                raise LedgerAmbiguous("E_LEDGER_EVIDENCE_DUPLICATE", entry.path)
            pair[part] = path
        observed: dict[tuple[str, str], tuple[Path, Path]] = {}
        for key, pair in partial.items():
            if "blob" not in pair:
                raise LedgerAmbiguous(
                    "E_LEDGER_EVIDENCE_PAYLOAD_MISSING", str(evidence_dir)
                )
            if "receipt" not in pair:
                raise LedgerAmbiguous(
                    "E_LEDGER_EVIDENCE_RECEIPT_MISSING", str(evidence_dir)
                )
            observed[key] = (pair["blob"], pair["receipt"])
        return observed

    def _read_evidence_receipt(
        self,
        receipt_path: Path,
        *,
        cell: MatrixCell,
        attempt_id: str,
        gate_id: str | None,
        allowed_gate_ids: Iterable[str],
    ) -> Mapping[str, Any]:
        try:
            raw = _read_record(receipt_path)
        except LedgerError as exc:
            raise LedgerAmbiguous(
                "E_LEDGER_EVIDENCE_RECEIPT_MALFORMED", str(receipt_path)
            ) from exc
        try:
            checked = validate_evidence_receipt(
                raw,
                cell,
                self.ledger_root_id,
                attempt_id=attempt_id,
                gate_id=gate_id,
                allowed_gate_ids=(tuple(allowed_gate_ids) or None),
                path=str(receipt_path),
            )
        except MatrixModelError as exc:
            code_by_model = {
                "E_EVIDENCE_RECEIPT_FIELDS": "E_LEDGER_EVIDENCE_RECEIPT_FIELDS",
                "E_EVIDENCE_RECEIPT_SCHEMA": "E_LEDGER_EVIDENCE_RECEIPT_SCHEMA",
                "E_EVIDENCE_RECEIPT_ROOT": "E_LEDGER_EVIDENCE_RECEIPT_ROOT",
                "E_EVIDENCE_RECEIPT_DIGEST": "E_LEDGER_EVIDENCE_RECEIPT_DIGEST",
            }
            code = code_by_model.get(
                exc.code, "E_LEDGER_EVIDENCE_RECEIPT_BINDING"
            )
            raise LedgerAmbiguous(code, str(receipt_path)) from exc
        return checked["evidence"]

    def _verify_evidence_blobs(
        self,
        attempt_path: Path,
        evidence: Any,
        path: str,
        *,
        cell_id: str,
        input_fingerprint: str,
        attempt_id: str,
        gate_id: str | None = None,
        allowed_gate_ids: Iterable[str] = (),
        exact: bool = False,
        additional_exact_keys: Iterable[tuple[str, str]] = (),
    ) -> list[dict[str, Any]]:
        records = _evidence_records(
            evidence,
            path,
            cell_id=cell_id,
            input_fingerprint=input_fingerprint,
            attempt_id=attempt_id,
            gate_id=gate_id,
            allowed_gate_ids=allowed_gate_ids,
        )
        observed = self._scan_evidence_directory(attempt_path)
        expected_records: dict[tuple[str, str], Mapping[str, Any]] = {}
        for record in records:
            key = (record["kind"], record["sha256"])
            expected_records[key] = record
        expected_keys = set(expected_records)
        expected_keys.update(additional_exact_keys)
        cell = MatrixCell(
            cell_id=cell_id,
            input_fingerprint=input_fingerprint,
            identity={},
        )
        verified_records: list[dict[str, Any]] = []
        for key in expected_keys:
            pair = observed.get(key)
            if pair is None:
                raise LedgerAmbiguous("E_LEDGER_EVIDENCE_MISSING", path)
            blob, receipt_path = pair
            stored_record = self._read_evidence_receipt(
                receipt_path,
                cell=cell,
                attempt_id=attempt_id,
                gate_id=gate_id,
                allowed_gate_ids=allowed_gate_ids,
            )
            if (
                stored_record["kind"], stored_record["sha256"]
            ) != key:
                raise LedgerAmbiguous(
                    "E_LEDGER_EVIDENCE_RECEIPT_PATH", str(receipt_path)
                )
            expected_record = expected_records.get(key)
            if expected_record is not None and stored_record != expected_record:
                raise LedgerAmbiguous(
                    "E_LEDGER_EVIDENCE_RECEIPT_MISMATCH", str(receipt_path)
                )
            verified_records.append(deepcopy(dict(stored_record)))
            try:
                size = blob.stat().st_size
                digest = hashlib.sha256()
                with blob.open("rb") as handle:
                    while True:
                        chunk = handle.read(1_048_576)
                        if not chunk:
                            break
                        digest.update(chunk)
            except OSError as exc:
                raise LedgerAmbiguous("E_LEDGER_EVIDENCE_READ", path) from exc
            if (
                size != stored_record["bytes"]
                or digest.hexdigest() != stored_record["sha256"]
            ):
                raise LedgerAmbiguous("E_LEDGER_EVIDENCE_DIGEST", path)
        if exact and set(observed) != expected_keys:
            raise LedgerAmbiguous("E_LEDGER_EVIDENCE_SET", path)
        return verified_records

    def _verify_all_stored_evidence(
        self,
        attempt_path: Path,
        cell: MatrixCell,
        attempt_id: str,
    ) -> None:
        observed = self._scan_evidence_directory(attempt_path)
        records = self._verify_evidence_blobs(
            attempt_path,
            [],
            str(attempt_path / "evidence"),
            cell_id=cell.cell_id,
            input_fingerprint=cell.input_fingerprint,
            attempt_id=attempt_id,
            allowed_gate_ids=cell.identity["required_gate_ids"],
            exact=True,
            additional_exact_keys=observed,
        )
        allowed_kinds = set(cell.identity["required_evidence_kinds"])
        if cell.identity["test_execution"] == "MANUAL":
            allowed_kinds.add("objective-result")
        if any(record["kind"] not in allowed_kinds for record in records):
            raise LedgerAmbiguous(
                "E_LEDGER_EVIDENCE_RECEIPT_KIND", str(attempt_path / "evidence")
            )

    def _validate_manual_verdict_blob(
        self,
        attempt_path: Path,
        result: Mapping[str, Any],
        cell: MatrixCell,
        events: Iterable[Mapping[str, Any]],
    ) -> set[tuple[str, str]]:
        digest = result["manual_verdict_sha256"]
        if digest is None:
            return set()
        path = self._evidence_path(attempt_path, "manual-verdict", digest)
        if not path.is_file() or _is_reparse_or_link(path):
            raise LedgerAmbiguous("E_LEDGER_MANUAL_VERDICT_MISSING", str(path))
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise LedgerAmbiguous("E_LEDGER_MANUAL_VERDICT_READ", str(path)) from exc
        if not 1 <= len(raw) <= 1_048_576 or hashlib.sha256(raw).hexdigest() != digest:
            raise LedgerAmbiguous("E_LEDGER_MANUAL_VERDICT_DIGEST", str(path))
        try:
            verdict = strict_json_loads(raw, max_bytes=1_048_576)
            if canonical_json_bytes(verdict) != raw:
                raise MatrixModelError("E_MANUAL_VERDICT_CANONICAL")
            checked = validate_manual_verdict(verdict, cell)
        except MatrixModelError as exc:
            raise LedgerAmbiguous("E_LEDGER_MANUAL_VERDICT_MODEL", str(path)) from exc
        expected_packet_kind = MANUAL_REVIEW_PACKET_KINDS.get(
            cell.identity.get("test_class")
        )
        packet_records = [
            item
            for item in result["evidence"]
            if item["kind"] == expected_packet_kind
        ]
        if (
            expected_packet_kind is None
            or len(packet_records) != 1
            or checked["review_packet_sha256"] != packet_records[0]["sha256"]
            or checked["verdict"] != result["status"]
        ):
            raise LedgerAmbiguous("E_LEDGER_MANUAL_VERDICT_BINDING", str(path))
        consuming_times = [
            _parse_utc(
                event["recorded_at"],
                "E_LEDGER_MANUAL_VERDICT_TIME",
                str(path),
            )
            for event in events
            if any(
                item["kind"] == "manual-verdict" and item["sha256"] == digest
                for item in event["evidence"]
            )
        ]
        reviewed_at = _parse_utc(
            checked["reviewed_at"],
            "E_LEDGER_MANUAL_VERDICT_TIME",
            str(path),
        )
        if (
            not consuming_times
            or reviewed_at
            < _parse_utc(
                result["started_at"],
                "E_LEDGER_MANUAL_VERDICT_TIME",
                str(path),
            )
            or reviewed_at > min(consuming_times)
            or reviewed_at
            > _parse_utc(
                result["finished_at"],
                "E_LEDGER_MANUAL_VERDICT_TIME",
                str(path),
            )
        ):
            raise LedgerAmbiguous("E_LEDGER_MANUAL_VERDICT_TIME", str(path))
        objective_key = self._validate_objective_result_blob(
            attempt_path, checked, cell
        )
        return {("manual-verdict", digest), objective_key}

    def _validate_objective_result_blob(
        self,
        attempt_path: Path,
        verdict: Mapping[str, Any],
        manual_cell: MatrixCell,
    ) -> tuple[str, str]:
        digest = verdict["objective_result_sha256"]
        path = self._evidence_path(attempt_path, "objective-result", digest)
        if not path.is_file() or _is_reparse_or_link(path):
            raise LedgerAmbiguous("E_LEDGER_OBJECTIVE_RESULT_MISSING", str(path))
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise LedgerAmbiguous("E_LEDGER_OBJECTIVE_RESULT_READ", str(path)) from exc
        if hashlib.sha256(raw).hexdigest() != digest:
            raise LedgerAmbiguous("E_LEDGER_OBJECTIVE_RESULT_DIGEST", str(path))
        objective_record = _read_record(path)
        cell_id = _expect_text(
            objective_record.get("cell_id"),
            _CELL_RE,
            "E_LEDGER_OBJECTIVE_RESULT_CELL",
            str(path),
        )
        attempt_id = _expect_text(
            objective_record.get("attempt_id"),
            _ATTEMPT_RE,
            "E_LEDGER_OBJECTIVE_RESULT_ATTEMPT",
            str(path),
        )
        objective_cell_record = self._load_cell_record(self._cell_dir(cell_id))
        identity = _expect_mapping(
            objective_cell_record["identity"],
            "E_LEDGER_OBJECTIVE_RESULT_IDENTITY",
            str(path),
        )
        objective_cell = MatrixCell(
            cell_id=objective_cell_record["cell_id"],
            input_fingerprint=objective_cell_record["input_fingerprint"],
            identity=deepcopy(dict(identity)),
        )
        try:
            checked_result = validate_cell_result(objective_record, objective_cell)
        except MatrixModelError as exc:
            raise LedgerAmbiguous(
                "E_LEDGER_OBJECTIVE_RESULT_MODEL", str(path)
            ) from exc
        inspection = self._inspect_attempt_locked(cell_id, attempt_id)
        if (
            inspection.state != "PASS"
            or inspection.cell_result_sha256 != digest
            or checked_result["status"] != "PASS"
            or not checked_result["objective"]
        ):
            raise LedgerAmbiguous("E_LEDGER_OBJECTIVE_RESULT_STATUS", str(path))
        _, objective_attempt_path = self._find_attempt(cell_id, attempt_id)
        if (objective_attempt_path / "result.json").read_bytes() != raw:
            raise LedgerAmbiguous("E_LEDGER_OBJECTIVE_RESULT_BYTES", str(path))
        expected_class = MANUAL_OBJECTIVE_PREREQUISITES.get(
            manual_cell.identity["test_class"]
        )
        if expected_class is None or objective_cell.identity.get("test_class") != expected_class:
            raise LedgerAmbiguous("E_LEDGER_OBJECTIVE_RESULT_CLASS", str(path))
        shared_fields = (
            "manifest_id",
            "manifest_input_sha256",
            "mode",
            "release_eligible",
            "runtime_source_commit",
            "runtime_source_tree",
            "runtime_content_sha256",
            "package_kind",
            "package_sha256",
            "matrix_adapter_version",
            "matrix_adapter_sha256",
            "game",
            "host",
            "engine",
            "tier",
            "platform",
            "host_mode",
        )
        for field in shared_fields:
            if canonical_json_bytes(objective_cell.identity.get(field)) != canonical_json_bytes(
                manual_cell.identity.get(field)
            ):
                raise LedgerAmbiguous(
                    "E_LEDGER_OBJECTIVE_RESULT_DIMENSION", str(path)
                )
        if _parse_utc(
            checked_result["finished_at"],
            "E_LEDGER_OBJECTIVE_RESULT_TIME",
            str(path),
        ) > _parse_utc(
            verdict["reviewed_at"],
            "E_LEDGER_MANUAL_VERDICT_TIME",
            str(path),
        ):
            raise LedgerAmbiguous("E_LEDGER_OBJECTIVE_RESULT_TIME", str(path))
        return ("objective-result", digest)

    def _load_events(
        self, attempt_path: Path, attempt: Mapping[str, Any]
    ) -> tuple[list[Mapping[str, Any]], list[str]]:
        events_dir = attempt_path / "events"
        _assert_plain_directory(events_dir)
        events: list[Mapping[str, Any]] = []
        file_hashes: list[str] = []
        try:
            entries = sorted(os.scandir(events_dir), key=lambda entry: entry.name)
        except OSError as exc:
            raise LedgerAmbiguous("E_LEDGER_EVENT_SCAN", str(events_dir)) from exc
        for expected_sequence, entry in enumerate(entries):
            if ".partial-" in entry.name:
                raise LedgerAmbiguous("E_LEDGER_PARTIAL_EVENT", entry.path)
            match = _EVENT_FILE_RE.fullmatch(entry.name)
            if match is None or not entry.is_file(follow_symlinks=False):
                raise LedgerAmbiguous("E_LEDGER_EVENT_ENTRY", entry.path)
            if int(match.group(1)) != expected_sequence:
                raise LedgerAmbiguous("E_LEDGER_EVENT_SEQUENCE", entry.path)
            path = Path(entry.path)
            if _is_reparse_or_link(path):
                raise LedgerAmbiguous("E_LEDGER_EVENT_REPARSE", entry.path)
            raw = path.read_bytes()
            file_hash = hashlib.sha256(raw).hexdigest()
            try:
                event = strict_json_loads(raw, max_bytes=1_048_576)
            except MatrixModelError as exc:
                raise LedgerAmbiguous("E_LEDGER_EVENT_JSON", entry.path) from exc
            event = _expect_mapping(event, "E_LEDGER_EVENT_TYPE", entry.path)
            try:
                canonical = canonical_json_bytes(dict(event))
            except MatrixModelError as exc:
                raise LedgerAmbiguous("E_LEDGER_EVENT_CANONICAL", entry.path) from exc
            if raw != canonical:
                raise LedgerAmbiguous("E_LEDGER_EVENT_CANONICAL", entry.path)
            self._validate_event_record(
                event,
                attempt,
                expected_sequence,
                match.group(2),
                file_hashes[-1] if file_hashes else None,
                entry.path,
            )
            self._verify_evidence_blobs(
                attempt_path,
                event["evidence"],
                entry.path,
                cell_id=attempt["cell_id"],
                input_fingerprint=attempt["input_fingerprint"],
                attempt_id=attempt["attempt_id"],
                gate_id=(
                    event["gate_id"]
                    if event["event_type"] == "GATE_PASSED"
                    else None
                ),
            )
            events.append(event)
            file_hashes.append(file_hash)
        return events, file_hashes

    def _validate_event_record(
        self,
        event: Mapping[str, Any],
        attempt: Mapping[str, Any],
        sequence: int,
        file_event_id: str,
        previous_hash: str | None,
        path: str,
    ) -> None:
        _expect_keys(
            event,
            (
                "schema",
                "schema_version",
                "event_id",
                "cell_id",
                "input_fingerprint",
                "attempt_id",
                "sequence",
                "previous_event_sha256",
                "recorded_at",
                "event_type",
                "gate_id",
                "evidence",
                "cell_result_sha256",
            ),
            "E_LEDGER_EVENT_FIELDS",
            path,
        )
        if (
            event["schema"] != LEDGER_EVENT_SCHEMA
            or type(event["schema_version"]) is not int
            or event["schema_version"] != 1
        ):
            raise LedgerAmbiguous("E_LEDGER_EVENT_SCHEMA", path)
        if (
            event["cell_id"] != attempt["cell_id"]
            or event["input_fingerprint"] != attempt["input_fingerprint"]
            or event["attempt_id"] != attempt["attempt_id"]
            or type(event["sequence"]) is not int
            or event["sequence"] > MAX_EVENT_SEQUENCE
            or event["sequence"] != sequence
            or event["previous_event_sha256"] != previous_hash
        ):
            raise LedgerAmbiguous("E_LEDGER_EVENT_BINDING", path)
        _parse_utc(event["recorded_at"], "E_LEDGER_EVENT_TIME", path)
        if event["event_type"] not in EVENT_TYPES:
            raise LedgerAmbiguous("E_LEDGER_EVENT_ENUM", path)
        if event["gate_id"] is not None:
            _expect_text(event["gate_id"], _ID_RE, "E_LEDGER_GATE_ID", path)
        _evidence_records(
            event["evidence"],
            path,
            cell_id=attempt["cell_id"],
            input_fingerprint=attempt["input_fingerprint"],
            attempt_id=attempt["attempt_id"],
            gate_id=(
                event["gate_id"] if event["event_type"] == "GATE_PASSED" else None
            ),
        )
        if event["cell_result_sha256"] is not None:
            _expect_text(
                event["cell_result_sha256"],
                _SHA_RE,
                "E_LEDGER_RESULT_HASH",
                path,
            )
        body = dict(event)
        observed_event_id = body.pop("event_id", None)
        expected_event_id = sha256_value(body)
        if observed_event_id != expected_event_id or file_event_id != expected_event_id:
            raise LedgerAmbiguous("E_LEDGER_EVENT_ID", path)

    def _reduce_events(
        self,
        attempt: Mapping[str, Any],
        events: list[Mapping[str, Any]],
        required_gate_ids: Iterable[str],
        required_evidence_kinds: Iterable[str],
    ) -> AttemptInspection:
        required_gates: list[str] = []
        for gate_id in required_gate_ids:
            gate = _expect_text(
                gate_id, _ID_RE, "E_LEDGER_REQUIRED_GATE", attempt["cell_id"]
            )
            if gate in required_gates:
                raise LedgerAmbiguous("E_LEDGER_REQUIRED_GATE_DUPLICATE", attempt["cell_id"])
            required_gates.append(gate)
        if not required_gates:
            raise LedgerAmbiguous("E_LEDGER_REQUIRED_GATE_EMPTY", attempt["cell_id"])
        required_evidence: list[str] = []
        for evidence_kind in required_evidence_kinds:
            kind = _expect_text(
                evidence_kind,
                _ID_RE,
                "E_LEDGER_REQUIRED_EVIDENCE",
                attempt["cell_id"],
            )
            if kind in required_evidence:
                raise LedgerAmbiguous(
                    "E_LEDGER_REQUIRED_EVIDENCE_DUPLICATE", attempt["cell_id"]
                )
            required_evidence.append(kind)
        if not required_evidence:
            raise LedgerAmbiguous(
                "E_LEDGER_REQUIRED_EVIDENCE_EMPTY", attempt["cell_id"]
            )
        started = _parse_utc(
            attempt["started_at"], "E_LEDGER_ATTEMPT_TIME", attempt["attempt_id"]
        )
        last_time = started
        active_gate: str | None = None
        passed: list[str] = []
        passed_evidence: list[dict[str, Any]] = []
        failed_gate: str | None = None
        cleanup: str | None = None
        terminal: str | None = None
        result_commit: str | None = None

        for event in events:
            recorded = _parse_utc(
                event["recorded_at"], "E_LEDGER_EVENT_TIME", event["event_id"]
            )
            if recorded < last_time:
                raise LedgerAmbiguous("E_LEDGER_TIME_ORDER", event["event_id"])
            last_time = recorded
            kind = event["event_type"]
            gate = event["gate_id"]
            if result_commit is not None:
                raise LedgerAmbiguous("E_LEDGER_EVENT_AFTER_TERMINAL", event["event_id"])
            if terminal is not None and kind != "RESULT_COMMITTED":
                raise LedgerAmbiguous("E_LEDGER_EVENT_AFTER_OUTCOME", event["event_id"])
            if kind != "RESULT_COMMITTED" and event["cell_result_sha256"] is not None:
                raise LedgerAmbiguous("E_LEDGER_UNEXPECTED_RESULT_HASH", event["event_id"])
            if kind == "GATE_STARTED":
                if gate is None or active_gate is not None or failed_gate is not None or cleanup is not None:
                    raise LedgerAmbiguous("E_LEDGER_GATE_START_STATE", event["event_id"])
                if gate not in required_gates:
                    raise LedgerAmbiguous("E_LEDGER_GATE_NOT_REQUIRED", event["event_id"])
                if gate in passed:
                    raise LedgerAmbiguous("E_LEDGER_GATE_RESTART", event["event_id"])
                active_gate = gate
            elif kind == "GATE_PASSED":
                if gate is None or gate != active_gate:
                    raise LedgerAmbiguous("E_LEDGER_GATE_PASS_STATE", event["event_id"])
                passed.append(gate)
                for evidence_record in _evidence_records(
                    event["evidence"],
                    event["event_id"],
                    cell_id=attempt["cell_id"],
                    input_fingerprint=attempt["input_fingerprint"],
                    attempt_id=attempt["attempt_id"],
                    gate_id=gate,
                ):
                    if any(
                        item["kind"] == evidence_record["kind"]
                        for item in passed_evidence
                    ):
                        raise LedgerAmbiguous(
                            "E_LEDGER_GATE_EVIDENCE_DUPLICATE", event["event_id"]
                        )
                    passed_evidence.append(evidence_record)
                active_gate = None
            elif kind == "GATE_FAILED":
                if gate is None or gate != active_gate:
                    raise LedgerAmbiguous("E_LEDGER_GATE_FAIL_STATE", event["event_id"])
                failed_gate = gate
                active_gate = None
            elif kind == "CLEANUP_PASSED":
                if gate is not None or active_gate is not None or cleanup is not None:
                    raise LedgerAmbiguous("E_LEDGER_CLEANUP_STATE", event["event_id"])
                cleanup = "PASS"
            elif kind == "CLEANUP_FAILED":
                if gate is not None or cleanup is not None:
                    raise LedgerAmbiguous("E_LEDGER_CLEANUP_STATE", event["event_id"])
                cleanup = "FAIL"
            elif kind == "ATTEMPT_PASSED":
                terminal_evidence = _evidence_records(
                    event["evidence"],
                    event["event_id"],
                    cell_id=attempt["cell_id"],
                    input_fingerprint=attempt["input_fingerprint"],
                    attempt_id=attempt["attempt_id"],
                    allowed_gate_ids=required_gates,
                )
                if (
                    gate is not None
                    or active_gate is not None
                    or failed_gate is not None
                    or cleanup != "PASS"
                    or passed != required_gates
                    or [item["kind"] for item in terminal_evidence]
                    != required_evidence
                    or terminal_evidence != passed_evidence
                ):
                    raise LedgerAmbiguous("E_LEDGER_PASS_STATE", event["event_id"])
                terminal = kind
            elif kind == "ATTEMPT_FAILED":
                if (
                    gate is not None
                    or active_gate is not None
                    or failed_gate is None
                    or cleanup != "PASS"
                ):
                    raise LedgerAmbiguous("E_LEDGER_FAIL_STATE", event["event_id"])
                terminal = kind
            elif kind == "ATTEMPT_BLOCKED":
                if gate is not None or active_gate is not None or cleanup not in (None, "PASS"):
                    raise LedgerAmbiguous("E_LEDGER_BLOCKED_STATE", event["event_id"])
                terminal = kind
            elif kind == "ATTEMPT_AMBIGUOUS":
                if gate is not None:
                    raise LedgerAmbiguous("E_LEDGER_AMBIGUOUS_STATE", event["event_id"])
                terminal = kind
            elif kind == "RESULT_COMMITTED":
                if (
                    terminal is None
                    or gate is not None
                    or event["evidence"]
                    or event["cell_result_sha256"] is None
                ):
                    raise LedgerAmbiguous("E_LEDGER_RESULT_COMMIT_STATE", event["event_id"])
                result_commit = event["cell_result_sha256"]

        state = "AMBIGUOUS"
        if terminal == "ATTEMPT_PASSED":
            state = "PASS"
        elif terminal == "ATTEMPT_FAILED":
            state = "FAIL"
        elif terminal == "ATTEMPT_BLOCKED":
            state = "BLOCKED"
        elif terminal == "ATTEMPT_AMBIGUOUS":
            state = "AMBIGUOUS"

        return AttemptInspection(
            attempt_id=attempt["attempt_id"],
            attempt_number=attempt["attempt_number"],
            state=state,
            terminal_event=terminal,
            event_count=len(events),
            passed_gates=tuple(passed),
            failed_gate=failed_gate,
            cleanup=cleanup,
            last_event_sha256=None,
            cell_result_sha256=result_commit,
        )

    def _load_attempt_state(
        self, cell_id: str, attempt_id: str
    ) -> tuple[
        int,
        Path,
        Mapping[str, Any],
        MatrixCell,
        list[Mapping[str, Any]],
        list[str],
        AttemptInspection,
    ]:
        number, path = self._find_attempt(cell_id, attempt_id)
        attempt = self._load_attempt_record(path, number, attempt_id)
        cell_record = self._load_cell_record(self._cell_dir(cell_id))
        if (
            attempt["cell_id"] != cell_id
            or attempt["input_fingerprint"] != cell_record["input_fingerprint"]
        ):
            raise LedgerAmbiguous("E_LEDGER_ATTEMPT_CELL", str(path))
        attempt_directories = self._attempt_directories(self._cell_dir(cell_id))
        if number == 1:
            if attempt["recovery_id"] is not None:
                raise LedgerAmbiguous("E_LEDGER_UNEXPECTED_RECOVERY", str(path))
        else:
            if attempt["recovery_id"] is None:
                raise LedgerAmbiguous("E_LEDGER_RECOVERY_MISSING", str(path))
            previous_attempt_id = attempt_directories[number - 2][1]
            bound_cell = MatrixCell(
                cell_id=cell_id,
                input_fingerprint=attempt["input_fingerprint"],
                identity={},
            )
            self._load_recovery(
                bound_cell, attempt["recovery_id"], previous_attempt_id
            )
        events, hashes = self._load_events(path, attempt)
        identity = _expect_mapping(
            cell_record["identity"], "E_LEDGER_CELL_IDENTITY", str(path)
        )
        required_gate_ids = identity.get("required_gate_ids")
        if type(required_gate_ids) is not list:
            raise LedgerAmbiguous("E_LEDGER_REQUIRED_GATE_TYPE", str(path))
        required_evidence_kinds = identity.get("required_evidence_kinds")
        if type(required_evidence_kinds) is not list:
            raise LedgerAmbiguous("E_LEDGER_REQUIRED_EVIDENCE_TYPE", str(path))
        reduced = self._reduce_events(
            attempt, events, required_gate_ids, required_evidence_kinds
        )
        cell = MatrixCell(
            cell_id=cell_record["cell_id"],
            input_fingerprint=cell_record["input_fingerprint"],
            identity=deepcopy(dict(identity)),
        )
        self._verify_all_stored_evidence(path, cell, attempt_id)
        return number, path, attempt, cell, events, hashes, reduced

    def _validate_result_record(
        self,
        attempt_path: Path,
        attempt: Mapping[str, Any],
        cell: MatrixCell,
        events: list[Mapping[str, Any]],
        reduced: AttemptInspection,
    ) -> tuple[Mapping[str, Any], str]:
        result_path = attempt_path / "result.json"
        record = _read_record(result_path)
        try:
            checked = validate_cell_result(record, cell)
        except MatrixModelError as exc:
            raise LedgerAmbiguous("E_LEDGER_RESULT_MODEL", str(result_path)) from exc
        if reduced.terminal_event is None or not events:
            raise LedgerAmbiguous("E_LEDGER_RESULT_WITHOUT_TERMINAL", str(result_path))
        outcome = next(
            (
                event
                for event in reversed(events)
                if event["event_type"] == reduced.terminal_event
            ),
            None,
        )
        if outcome is None:
            raise LedgerAmbiguous("E_LEDGER_RESULT_WITHOUT_TERMINAL", str(result_path))
        status_by_terminal = {
            "ATTEMPT_PASSED": "PASS",
            "ATTEMPT_FAILED": "FAIL",
            "ATTEMPT_BLOCKED": "BLOCKED",
            "ATTEMPT_AMBIGUOUS": "AMBIGUOUS",
        }
        expected_cleanup = reduced.cleanup
        if expected_cleanup is None:
            expected_cleanup = (
                "UNKNOWN"
                if reduced.terminal_event == "ATTEMPT_AMBIGUOUS"
                else "NOT_RUN"
            )
        if (
            checked["attempt_id"] != attempt["attempt_id"]
            or checked["started_at"] != attempt["started_at"]
            or checked["finished_at"] != outcome["recorded_at"]
            or checked["status"] != status_by_terminal[reduced.terminal_event]
            or checked["cleanup"] != expected_cleanup
            or checked["evidence"] != outcome["evidence"]
        ):
            raise LedgerAmbiguous("E_LEDGER_RESULT_BINDING", str(result_path))
        manual_keys = self._validate_manual_verdict_blob(
            attempt_path, checked, cell, events
        )
        self._verify_evidence_blobs(
            attempt_path,
            checked["evidence"],
            str(result_path),
            cell_id=cell.cell_id,
            input_fingerprint=cell.input_fingerprint,
            attempt_id=attempt["attempt_id"],
            allowed_gate_ids=cell.identity["required_gate_ids"],
            exact=checked["status"] == "PASS",
            additional_exact_keys=manual_keys,
        )
        raw = result_path.read_bytes()
        return checked, hashlib.sha256(raw).hexdigest()

    def inspect_attempt(self, cell_id: str, attempt_id: str) -> AttemptInspection:
        """Inspect one attempt under one stable, read-only ledger view."""

        with self._root_lock():
            self._assert_root_layout()
            self._validate_staging_recovery_archives()
            self._assert_staging_empty()
            initial_snapshot = self._ledger_snapshot_sha256()
            inspection = self._inspect_attempt_locked(cell_id, attempt_id)
            self._assert_root_layout()
            self._validate_staging_recovery_archives()
            self._assert_staging_empty()
            final_snapshot = self._ledger_snapshot_sha256()
            if initial_snapshot != final_snapshot:
                raise LedgerAmbiguous("E_LEDGER_ROOT_CHANGED", str(self.root))
            return inspection

    def _inspect_attempt_locked(
        self, cell_id: str, attempt_id: str
    ) -> AttemptInspection:
        """Inspect one attempt while the caller holds the root lock."""

        inspection, cell = self._inspect_attempt_state(
            cell_id, attempt_id
        )
        self._validate_recovery_records(
            cell,
            self._attempt_directories(self._cell_dir(cell_id)),
        )
        return inspection

    def _inspect_attempt_state(
        self, cell_id: str, attempt_id: str
    ) -> tuple[AttemptInspection, MatrixCell]:
        """Validate one attempt without recursively checking its ancestry."""

        (
            _,
            path,
            attempt,
            cell,
            events,
            hashes,
            reduced,
        ) = self._load_attempt_state(cell_id, attempt_id)
        result_path = path / "result.json"
        result_sha256: str | None = None
        state = reduced.state
        if reduced.terminal_event is None:
            if result_path.exists():
                raise LedgerAmbiguous("E_LEDGER_RESULT_WITHOUT_TERMINAL", str(result_path))
        elif not result_path.exists() or reduced.cell_result_sha256 is None:
            state = "AMBIGUOUS"
        else:
            _, result_sha256 = self._validate_result_record(
                path, attempt, cell, events, reduced
            )
            if result_sha256 != reduced.cell_result_sha256:
                raise LedgerAmbiguous("E_LEDGER_RESULT_COMMIT", str(result_path))
        return (
            AttemptInspection(
                attempt_id=reduced.attempt_id,
                attempt_number=reduced.attempt_number,
                state=state,
                terminal_event=reduced.terminal_event,
                event_count=reduced.event_count,
                passed_gates=reduced.passed_gates,
                failed_gate=reduced.failed_gate,
                cleanup=reduced.cleanup,
                last_event_sha256=hashes[-1] if hashes else None,
                cell_result_sha256=result_sha256,
            ),
            cell,
        )

    def _validate_recovery_records(
        self,
        cell: MatrixCell,
        attempts: list[tuple[int, str, Path]],
    ) -> str | None:
        cell_dir = self._cell_dir(cell.cell_id)
        recoveries_dir = cell_dir / "recoveries"
        _assert_plain_directory(recoveries_dir)
        referenced: dict[str, str] = {}
        for index, (number, attempt_id, attempt_path) in enumerate(attempts):
            attempt = self._load_attempt_record(attempt_path, number, attempt_id)
            recovery_id = attempt["recovery_id"]
            if index == 0:
                if recovery_id is not None:
                    raise LedgerAmbiguous("E_LEDGER_UNEXPECTED_RECOVERY", str(attempt_path))
                continue
            if recovery_id is None or recovery_id in referenced:
                raise LedgerAmbiguous("E_LEDGER_RECOVERY_REFERENCE", str(attempt_path))
            previous_attempt_id = attempts[index - 1][1]
            recovery = self._load_recovery(
                cell, recovery_id, previous_attempt_id
            )
            previous, _ = self._inspect_attempt_state(
                cell.cell_id, previous_attempt_id
            )
            if previous.state == "PASS":
                raise LedgerAmbiguous(
                    "E_LEDGER_SUCCESSOR_AFTER_PASS", str(attempt_path)
                )
            if _parse_utc(
                attempt["started_at"],
                "E_LEDGER_ATTEMPT_TIME",
                str(attempt_path),
            ) <= _parse_utc(
                recovery["approved_at"],
                "E_LEDGER_RECOVERY_TIME",
                recovery_id,
            ):
                raise LedgerAmbiguous(
                    "E_LEDGER_SUCCESSOR_TIME", str(attempt_path)
                )
            referenced[recovery_id] = previous_attempt_id

        observed: set[str] = set()
        try:
            entries = sorted(os.scandir(recoveries_dir), key=lambda item: item.name)
        except OSError as exc:
            raise LedgerAmbiguous("E_LEDGER_RECOVERY_SCAN", str(recoveries_dir)) from exc
        for entry in entries:
            if not entry.is_file(follow_symlinks=False) or not entry.name.endswith(".json"):
                raise LedgerAmbiguous("E_LEDGER_RECOVERY_ENTRY", entry.path)
            recovery_id = entry.name[:-5]
            if _RECOVERY_RE.fullmatch(recovery_id) is None or recovery_id in observed:
                raise LedgerAmbiguous("E_LEDGER_RECOVERY_ENTRY", entry.path)
            observed.add(recovery_id)

        if not set(referenced).issubset(observed):
            raise LedgerAmbiguous("E_LEDGER_RECOVERY_MISSING", str(recoveries_dir))
        pending = observed - set(referenced)
        if len(pending) > 1 or (pending and not attempts):
            raise LedgerAmbiguous("E_LEDGER_RECOVERY_DANGLING", str(recoveries_dir))
        if pending:
            recovery_id = next(iter(pending))
            self._load_recovery(cell, recovery_id, attempts[-1][1])
            previous, _ = self._inspect_attempt_state(
                cell.cell_id, attempts[-1][1]
            )
            if previous.state == "PASS":
                raise LedgerAmbiguous(
                    "E_LEDGER_RECOVERY_AFTER_PASS", recovery_id
                )
            return recovery_id
        return None

    def make_recovery_id(
        self,
        cell_id: str,
        failed_attempt_id: str,
        approved_at: str,
        reviewer_id: str,
        failed_attempt_state_sha256: str,
        review_sha256: str,
    ) -> str:
        _expect_text(cell_id, _CELL_RE, "E_LEDGER_CELL_ID", "cell_id")
        _expect_text(
            failed_attempt_id, _ATTEMPT_RE, "E_LEDGER_ATTEMPT_ID", "failed_attempt_id"
        )
        _parse_utc(approved_at, "E_LEDGER_RECOVERY_TIME", "approved_at")
        _expect_text(reviewer_id, _ID_RE, "E_LEDGER_REVIEWER", "reviewer_id")
        _expect_text(
            failed_attempt_state_sha256,
            _SHA_RE,
            "E_LEDGER_RECOVERY_HASH",
            "failed_attempt_state_sha256",
        )
        _expect_text(review_sha256, _SHA_RE, "E_LEDGER_RECOVERY_HASH", "review_sha256")
        return "recovery-" + sha256_value(
            {
                "cell_id": cell_id,
                "failed_attempt_id": failed_attempt_id,
                "approved_at": approved_at,
                "reviewer_id": reviewer_id,
                "failed_attempt_state_sha256": failed_attempt_state_sha256,
                "review_sha256": review_sha256,
                "disposition": "AUTHORIZE_NEW_ATTEMPT",
            }
        )

    def record_recovery(
        self,
        cell: MatrixCell,
        failed_attempt_id: str,
        review: Mapping[str, Any],
    ) -> str:
        with self._mutation_lock(cell.cell_id):
            return self._record_recovery(cell, failed_attempt_id, review)

    def _record_recovery(
        self,
        cell: MatrixCell,
        failed_attempt_id: str,
        review: Mapping[str, Any],
    ) -> str:
        cell_dir = self._ensure_cell(cell)
        attempts = self._attempt_directories(cell_dir)
        if not attempts or attempts[-1][1] != failed_attempt_id:
            raise LedgerConflict("E_LEDGER_RECOVERY_NOT_LATEST", failed_attempt_id)
        pending_recovery = self._validate_recovery_records(cell, attempts)
        if pending_recovery is not None:
            raise LedgerConflict("E_LEDGER_RECOVERY_ALREADY_RECORDED", pending_recovery)
        try:
            latest = self._inspect_attempt_locked(
                cell.cell_id, failed_attempt_id
            )
        except LedgerAmbiguous:
            latest = None
        if latest is not None and latest.state == "PASS":
            raise LedgerConflict("E_LEDGER_COMPLETED_CELL", failed_attempt_id)
        latest_record = self._load_attempt_record(
            attempts[-1][2], attempts[-1][0], attempts[-1][1]
        )
        checked_review = self._validate_recovery_review(
            review,
            cell,
            failed_attempt_id,
            attempts[-1][2],
            latest_record,
        )
        reviewer_id = checked_review["reviewer_id"]
        if reviewer_id == latest_record["owner_id"]:
            raise LedgerConflict(
                "E_LEDGER_RECOVERY_REVIEWER_NOT_INDEPENDENT", reviewer_id
            )
        review_sha256 = sha256_value(checked_review)
        approved_at = checked_review["reviewed_at"]
        failed_state = checked_review["failed_attempt_state_sha256"]
        recovery_id = self.make_recovery_id(
            cell.cell_id,
            failed_attempt_id,
            approved_at,
            reviewer_id,
            failed_state,
            review_sha256,
        )
        record = {
            "schema": RECOVERY_SCHEMA,
            "schema_version": SCHEMA_VERSION,
            "recovery_id": recovery_id,
            "cell_id": cell.cell_id,
            "input_fingerprint": cell.input_fingerprint,
            "failed_attempt_id": failed_attempt_id,
            "failed_attempt_state_sha256": failed_state,
            "approved_at": approved_at,
            "reviewer_id": reviewer_id,
            "review_sha256": review_sha256,
            "review": checked_review,
            "disposition": "AUTHORIZE_NEW_ATTEMPT",
        }
        target = cell_dir / "recoveries" / f"{recovery_id}.json"
        self._atomic_create(target, record)
        return recovery_id

    def _load_recovery(
        self, cell: MatrixCell, recovery_id: str, expected_attempt_id: str
    ) -> Mapping[str, Any]:
        if type(recovery_id) is not str or _RECOVERY_RE.fullmatch(recovery_id) is None:
            raise LedgerConflict("E_LEDGER_RECOVERY_ID", "recovery_id")
        path = self._cell_dir(cell.cell_id) / "recoveries" / f"{recovery_id}.json"
        record = _read_record(path)
        _expect_keys(
            record,
            (
                "schema",
                "schema_version",
                "recovery_id",
                "cell_id",
                "input_fingerprint",
                "failed_attempt_id",
                "failed_attempt_state_sha256",
                "approved_at",
                "reviewer_id",
                "review_sha256",
                "review",
                "disposition",
            ),
            "E_LEDGER_RECOVERY_FIELDS",
            str(path),
        )
        if (
            record["schema"] != RECOVERY_SCHEMA
            or type(record["schema_version"]) is not int
            or record["schema_version"] != 1
            or record["recovery_id"] != recovery_id
            or record["cell_id"] != cell.cell_id
            or record["input_fingerprint"] != cell.input_fingerprint
            or record["failed_attempt_id"] != expected_attempt_id
            or record["disposition"] != "AUTHORIZE_NEW_ATTEMPT"
        ):
            raise LedgerConflict("E_LEDGER_RECOVERY_BINDING", str(path))
        _parse_utc(record["approved_at"], "E_LEDGER_RECOVERY_TIME", str(path))
        _expect_text(
            record["reviewer_id"], _ID_RE, "E_LEDGER_REVIEWER", str(path)
        )
        _expect_text(
            record["failed_attempt_state_sha256"],
            _SHA_RE,
            "E_LEDGER_RECOVERY_HASH",
            str(path),
        )
        _expect_text(
            record["review_sha256"], _SHA_RE, "E_LEDGER_RECOVERY_HASH", str(path)
        )
        previous_number, previous_path = self._find_attempt(
            cell.cell_id, expected_attempt_id
        )
        previous_attempt = self._load_attempt_record(
            previous_path, previous_number, expected_attempt_id
        )
        checked_review = self._validate_recovery_review(
            record["review"],
            cell,
            expected_attempt_id,
            previous_path,
            previous_attempt,
        )
        if (
            sha256_value(checked_review) != record["review_sha256"]
            or checked_review["reviewed_at"] != record["approved_at"]
            or checked_review["reviewer_id"] != record["reviewer_id"]
            or checked_review["failed_attempt_state_sha256"]
            != record["failed_attempt_state_sha256"]
        ):
            raise LedgerConflict("E_LEDGER_RECOVERY_REVIEW_DIGEST", str(path))
        expected_recovery_id = self.make_recovery_id(
            record["cell_id"],
            record["failed_attempt_id"],
            record["approved_at"],
            record["reviewer_id"],
            record["failed_attempt_state_sha256"],
            record["review_sha256"],
        )
        if expected_recovery_id != recovery_id:
            raise LedgerConflict("E_LEDGER_RECOVERY_DIGEST", str(path))
        if record["reviewer_id"] == previous_attempt["owner_id"]:
            raise LedgerConflict(
                "E_LEDGER_RECOVERY_REVIEWER_NOT_INDEPENDENT", str(path)
            )
        return record

    def begin_attempt(
        self,
        cell: MatrixCell,
        *,
        attempt_number: int,
        started_at: str,
        owner_id: str,
        recovery_id: str | None = None,
    ) -> str:
        with self._mutation_lock(cell.cell_id):
            return self._begin_attempt(
                cell,
                attempt_number=attempt_number,
                started_at=started_at,
                owner_id=owner_id,
                recovery_id=recovery_id,
            )

    def _begin_attempt(
        self,
        cell: MatrixCell,
        *,
        attempt_number: int,
        started_at: str,
        owner_id: str,
        recovery_id: str | None = None,
    ) -> str:
        cell_dir = self._ensure_cell(cell)
        attempts = self._attempt_directories(cell_dir)
        pending_recovery = self._validate_recovery_records(cell, attempts)
        expected_number = len(attempts) + 1
        if type(attempt_number) is not int or not 1 <= attempt_number <= MAX_ATTEMPTS:
            raise LedgerConflict("E_LEDGER_ATTEMPT_NUMBER_LIMIT", "attempt_number")
        if attempt_number != expected_number:
            raise LedgerConflict("E_LEDGER_ATTEMPT_NUMBER", "attempt_number")
        if not attempts:
            if recovery_id is not None:
                raise LedgerConflict("E_LEDGER_UNEXPECTED_RECOVERY", "recovery_id")
        else:
            previous_id = attempts[-1][1]
            try:
                previous = self._inspect_attempt_locked(
                    cell.cell_id, previous_id
                )
            except LedgerAmbiguous:
                previous = None
            if previous is not None and previous.state == "PASS":
                raise LedgerConflict("E_LEDGER_COMPLETED_CELL", cell.cell_id)
            if recovery_id is None:
                raise LedgerConflict("E_LEDGER_RECOVERY_REQUIRED", previous_id)
            if recovery_id != pending_recovery:
                raise LedgerConflict("E_LEDGER_RECOVERY_NOT_PENDING", recovery_id)
            recovery = self._load_recovery(cell, recovery_id, previous_id)
            if _parse_utc(
                started_at, "E_LEDGER_ATTEMPT_TIME", "started_at"
            ) <= _parse_utc(
                recovery["approved_at"],
                "E_LEDGER_RECOVERY_TIME",
                recovery_id,
            ):
                raise LedgerConflict("E_LEDGER_SUCCESSOR_TIME", started_at)

        attempt_id = make_attempt_id(
            cell,
            attempt_number,
            started_at,
            owner_id,
            recovery_id,
        )
        directory = cell_dir / "attempts" / f"{attempt_number:06d}-{attempt_id}"
        if directory.exists():
            raise LedgerConflict("E_LEDGER_ATTEMPT_EXISTS", str(directory))
        stage = self.staging_root / f"attempt-{uuid.uuid4().hex}.stage"
        self._inside(stage)
        try:
            stage.mkdir(mode=0o700)
        except OSError as exc:
            raise LedgerAmbiguous("E_LEDGER_ATTEMPT_CREATE", str(stage)) from exc
        _assert_plain_directory(stage)
        events = stage / "events"
        evidence = stage / "evidence"
        self._mkdir(events)
        self._mkdir(evidence)
        record = {
            "schema": ATTEMPT_SCHEMA,
            "schema_version": SCHEMA_VERSION,
            "attempt_id": attempt_id,
            "attempt_number": attempt_number,
            "cell_id": cell.cell_id,
            "input_fingerprint": cell.input_fingerprint,
            "owner_id": owner_id,
            "started_at": started_at,
            "recovery_id": recovery_id,
        }
        self._atomic_create(stage / "attempt.json", record)
        try:
            os.rename(stage, directory)
        except FileExistsError as exc:
            raise LedgerConflict("E_LEDGER_ATTEMPT_EXISTS", str(directory)) from exc
        except OSError as exc:
            raise LedgerAmbiguous("E_LEDGER_ATTEMPT_PUBLISH", str(stage)) from exc
        return attempt_id

    def record_evidence(
        self,
        cell: MatrixCell,
        attempt_id: str,
        *,
        gate_id: str,
        kind: str,
        payload: bytes,
    ) -> Mapping[str, Any]:
        """Store one immutable evidence blob and return its public-safe binding."""

        with self._mutation_lock(cell.cell_id):
            return self._record_evidence(
                cell, attempt_id, gate_id=gate_id, kind=kind, payload=payload
            )

    def _record_evidence(
        self,
        cell: MatrixCell,
        attempt_id: str,
        *,
        gate_id: str,
        kind: str,
        payload: bytes,
    ) -> Mapping[str, Any]:

        self._ensure_cell(cell)
        self._assert_attempt_writable(cell, attempt_id)
        if type(payload) is not bytes:
            raise LedgerError("E_LEDGER_EVIDENCE_PAYLOAD", "payload")
        if not 1 <= len(payload) <= MAX_EVIDENCE_BYTES:
            raise LedgerError("E_LEDGER_EVIDENCE_BYTES", "payload")
        number, attempt_path = self._find_attempt(cell.cell_id, attempt_id)
        attempt = self._load_attempt_record(attempt_path, number, attempt_id)
        if attempt["input_fingerprint"] != cell.input_fingerprint:
            raise LedgerConflict("E_LEDGER_CELL_DRIFT", attempt_id)
        _, _, _, stored_cell, events, _, reduced = self._load_attempt_state(
            cell.cell_id, attempt_id
        )
        if reduced.terminal_event is not None or (attempt_path / "result.json").exists():
            raise LedgerConflict("E_LEDGER_EVIDENCE_AFTER_TERMINAL", attempt_id)
        checked_kind = _expect_text(
            kind, _ID_RE, "E_LEDGER_EVIDENCE_KIND", "kind"
        )
        checked_gate = _expect_text(
            gate_id, _ID_RE, "E_LEDGER_EVIDENCE_GATE", "gate_id"
        )
        required_gates = tuple(stored_cell.identity["required_gate_ids"])
        if checked_gate not in required_gates:
            raise LedgerConflict(
                "E_LEDGER_EVIDENCE_GATE_NOT_REQUIRED", checked_gate
            )
        allowed_kinds = set(stored_cell.identity["required_evidence_kinds"])
        if stored_cell.identity["test_execution"] == "MANUAL":
            allowed_kinds.add("objective-result")
        if checked_kind not in allowed_kinds:
            raise LedgerConflict("E_LEDGER_EVIDENCE_NOT_REQUIRED", checked_kind)
        active_gate: str | None = None
        for event in events:
            if event["event_type"] == "GATE_STARTED":
                active_gate = event["gate_id"]
            elif event["event_type"] in ("GATE_PASSED", "GATE_FAILED"):
                active_gate = None
        if active_gate != checked_gate:
            raise LedgerConflict("E_LEDGER_EVIDENCE_GATE_NOT_OPEN", checked_gate)
        observed = self._scan_evidence_directory(attempt_path)
        if len(observed) >= MAX_EVIDENCE_ITEMS:
            raise LedgerConflict("E_LEDGER_EVIDENCE_COUNT", attempt_id)
        if any(existing_kind == checked_kind for existing_kind, _ in observed):
            raise LedgerConflict("E_LEDGER_EVIDENCE_KIND_EXISTS", checked_kind)
        digest = hashlib.sha256(payload).hexdigest()
        try:
            binding = make_evidence_binding(
                stored_cell,
                attempt_id,
                checked_gate,
                checked_kind,
                digest,
                len(payload),
            )
        except MatrixModelError as exc:
            raise LedgerConflict(
                "E_LEDGER_EVIDENCE_BINDING", checked_kind
            ) from exc
        try:
            receipt = make_evidence_receipt(
                binding,
                stored_cell,
                self.ledger_root_id,
                attempt_id=attempt_id,
                gate_id=checked_gate,
            )
        except MatrixModelError as exc:
            raise LedgerConflict(
                "E_LEDGER_EVIDENCE_RECEIPT", checked_kind
            ) from exc
        target = self._evidence_path(attempt_path, checked_kind, digest)
        receipt_target = self._evidence_receipt_path(
            attempt_path, checked_kind, digest
        )
        self._atomic_create(receipt_target, receipt)
        self._atomic_create_bytes(target, payload)
        self._verify_evidence_blobs(
            attempt_path,
            [binding],
            str(receipt_target),
            cell_id=stored_cell.cell_id,
            input_fingerprint=stored_cell.input_fingerprint,
            attempt_id=attempt_id,
            gate_id=checked_gate,
            allowed_gate_ids=required_gates,
        )
        return binding

    def record_result(
        self,
        cell: MatrixCell,
        attempt_id: str,
        result: Mapping[str, Any],
    ) -> str:
        """Store one terminal result after exact attempt and evidence validation."""

        with self._mutation_lock(cell.cell_id):
            return self._record_result(cell, attempt_id, result)

    def _record_result(
        self,
        cell: MatrixCell,
        attempt_id: str,
        result: Mapping[str, Any],
    ) -> str:

        self._ensure_cell(cell)
        self._assert_attempt_writable(cell, attempt_id)
        (
            _,
            attempt_path,
            attempt,
            stored_cell,
            events,
            _,
            reduced,
        ) = self._load_attempt_state(cell.cell_id, attempt_id)
        if canonical_json_bytes(stored_cell.as_dict()) != canonical_json_bytes(
            cell.as_dict()
        ):
            raise LedgerConflict("E_LEDGER_CELL_DRIFT", attempt_id)
        if reduced.terminal_event is None:
            raise LedgerConflict("E_LEDGER_RESULT_BEFORE_TERMINAL", attempt_id)
        result_path = attempt_path / "result.json"
        if result_path.exists():
            raise LedgerConflict("E_LEDGER_RESULT_EXISTS", str(result_path))
        try:
            checked = validate_cell_result(result, cell)
        except MatrixModelError as exc:
            raise LedgerConflict("E_LEDGER_RESULT_MODEL", str(result_path)) from exc
        payload = canonical_json_bytes(dict(checked))
        # Validate the exact bytes in a task-owned temporary location only in
        # memory before the non-overwriting publish operation.
        terminal = events[-1]
        status_by_terminal = {
            "ATTEMPT_PASSED": "PASS",
            "ATTEMPT_FAILED": "FAIL",
            "ATTEMPT_BLOCKED": "BLOCKED",
            "ATTEMPT_AMBIGUOUS": "AMBIGUOUS",
        }
        expected_cleanup = reduced.cleanup
        if expected_cleanup is None:
            expected_cleanup = (
                "UNKNOWN"
                if reduced.terminal_event == "ATTEMPT_AMBIGUOUS"
                else "NOT_RUN"
            )
        if (
            checked["attempt_id"] != attempt["attempt_id"]
            or checked["started_at"] != attempt["started_at"]
            or checked["finished_at"] != terminal["recorded_at"]
            or checked["status"] != status_by_terminal[reduced.terminal_event]
            or checked["cleanup"] != expected_cleanup
            or checked["evidence"] != terminal["evidence"]
        ):
            raise LedgerConflict("E_LEDGER_RESULT_BINDING", str(result_path))
        try:
            manual_keys = self._validate_manual_verdict_blob(
                attempt_path, checked, cell, events
            )
            self._verify_evidence_blobs(
                attempt_path,
                checked["evidence"],
                str(result_path),
                cell_id=cell.cell_id,
                input_fingerprint=cell.input_fingerprint,
                attempt_id=attempt["attempt_id"],
                allowed_gate_ids=cell.identity["required_gate_ids"],
                exact=checked["status"] == "PASS",
                additional_exact_keys=manual_keys,
            )
        except LedgerAmbiguous as exc:
            raise LedgerConflict("E_LEDGER_RESULT_EVIDENCE", str(result_path)) from exc
        digest = self._atomic_create_bytes(result_path, payload)
        self._append_event(
            cell,
            attempt_id,
            event_type="RESULT_COMMITTED",
            recorded_at=checked["finished_at"],
            cell_result_sha256=digest,
        )
        inspection = self._inspect_attempt_locked(cell.cell_id, attempt_id)
        if inspection.cell_result_sha256 != digest:
            raise LedgerAmbiguous("E_LEDGER_RESULT_PUBLISH", str(result_path))
        return digest

    def append_event(
        self,
        cell: MatrixCell,
        attempt_id: str,
        *,
        event_type: str,
        recorded_at: str,
        gate_id: str | None = None,
        evidence: Iterable[Mapping[str, Any]] = (),
        cell_result_sha256: str | None = None,
    ) -> str:
        if event_type == "RESULT_COMMITTED" or cell_result_sha256 is not None:
            raise LedgerError("E_LEDGER_RESULT_COMMIT_INTERNAL", "event_type")
        with self._mutation_lock(cell.cell_id):
            return self._append_event(
                cell,
                attempt_id,
                event_type=event_type,
                recorded_at=recorded_at,
                gate_id=gate_id,
                evidence=evidence,
                cell_result_sha256=None,
            )

    def _append_event(
        self,
        cell: MatrixCell,
        attempt_id: str,
        *,
        event_type: str,
        recorded_at: str,
        gate_id: str | None = None,
        evidence: Iterable[Mapping[str, Any]] = (),
        cell_result_sha256: str | None = None,
    ) -> str:
        if event_type not in EVENT_TYPES:
            raise LedgerError("E_LEDGER_EVENT_ENUM", "event_type")
        self._ensure_cell(cell)
        self._assert_attempt_writable(cell, attempt_id)
        number, attempt_path = self._find_attempt(cell.cell_id, attempt_id)
        # This validates the immutable cell record, recovery binding, and all
        # existing events before one new event is considered.
        self._inspect_attempt_locked(cell.cell_id, attempt_id)
        attempt = self._load_attempt_record(attempt_path, number, attempt_id)
        if attempt["input_fingerprint"] != cell.input_fingerprint:
            raise LedgerConflict("E_LEDGER_CELL_DRIFT", attempt_id)
        events, hashes = self._load_events(attempt_path, attempt)
        required_gate_ids = cell.identity.get("required_gate_ids")
        if type(required_gate_ids) is not list:
            raise LedgerConflict("E_LEDGER_REQUIRED_GATE_TYPE", cell.cell_id)
        required_evidence_kinds = cell.identity.get("required_evidence_kinds")
        if type(required_evidence_kinds) is not list:
            raise LedgerConflict("E_LEDGER_REQUIRED_EVIDENCE_TYPE", cell.cell_id)
        self._reduce_events(
            attempt, events, required_gate_ids, required_evidence_kinds
        )
        evidence_list = [dict(item) for item in evidence]
        evidence_gate_id = gate_id if event_type == "GATE_PASSED" else None
        _evidence_records(
            evidence_list,
            "evidence",
            cell_id=cell.cell_id,
            input_fingerprint=cell.input_fingerprint,
            attempt_id=attempt_id,
            gate_id=evidence_gate_id,
            allowed_gate_ids=required_gate_ids,
        )
        self._verify_evidence_blobs(
            attempt_path,
            evidence_list,
            "evidence",
            cell_id=cell.cell_id,
            input_fingerprint=cell.input_fingerprint,
            attempt_id=attempt_id,
            gate_id=evidence_gate_id,
            allowed_gate_ids=required_gate_ids,
        )
        if gate_id is not None:
            _expect_text(gate_id, _ID_RE, "E_LEDGER_GATE_ID", "gate_id")
        sequence = len(events)
        if sequence > MAX_EVENT_SEQUENCE:
            raise LedgerConflict("E_LEDGER_EVENT_SEQUENCE_LIMIT", attempt_id)
        body = {
            "schema": LEDGER_EVENT_SCHEMA,
            "schema_version": SCHEMA_VERSION,
            "cell_id": cell.cell_id,
            "input_fingerprint": cell.input_fingerprint,
            "attempt_id": attempt_id,
            "sequence": sequence,
            "previous_event_sha256": hashes[-1] if hashes else None,
            "recorded_at": recorded_at,
            "event_type": event_type,
            "gate_id": gate_id,
            "evidence": evidence_list,
            "cell_result_sha256": cell_result_sha256,
        }
        event_id = sha256_value(body)
        record = {"event_id": event_id, **body}
        # Validate the prospective event against the complete state machine.
        self._validate_event_record(
            record,
            attempt,
            sequence,
            event_id,
            hashes[-1] if hashes else None,
            "prospective-event",
        )
        self._reduce_events(
            attempt,
            [*events, record],
            required_gate_ids,
            required_evidence_kinds,
        )
        target = attempt_path / "events" / f"{sequence:010d}-{event_id}.json"
        self._atomic_create(target, record)
        return event_id

    def resume_decision(self, cell: MatrixCell) -> Mapping[str, Any]:
        """Return a fail-closed next action without changing the ledger."""

        with self._root_lock():
            self._assert_root_layout()
            self._validate_staging_recovery_archives()
            self._assert_staging_empty()
            decision = self._resume_decision_locked(cell)
            self._assert_staging_empty()
            self._validate_staging_recovery_archives()
            return decision

    def _resume_decision_locked(self, cell: MatrixCell) -> Mapping[str, Any]:
        """Read one resume decision while the root consistency lock is held."""

        cell_dir = self._cell_dir(cell.cell_id)
        if not os.path.lexists(cell_dir):
            return {"action": "START_NEW", "attempt_number": 1, "recovery_id": None}
        stored_cell = self._load_cell_record(cell_dir)
        if canonical_json_bytes(stored_cell) != canonical_json_bytes(
            {
                "schema": CELL_RECORD_SCHEMA,
                "schema_version": SCHEMA_VERSION,
                "cell_id": cell.cell_id,
                "input_fingerprint": cell.input_fingerprint,
                "identity": deepcopy(dict(cell.identity)),
            }
        ):
            raise LedgerAmbiguous("E_LEDGER_CELL_DRIFT", str(cell_dir))
        attempts = self._attempt_directories(cell_dir)
        if not attempts:
            return {"action": "START_NEW", "attempt_number": 1, "recovery_id": None}
        pending_recovery = self._validate_recovery_records(cell, attempts)
        number, attempt_id, _ = attempts[-1]
        try:
            inspection = self._inspect_attempt_locked(
                cell.cell_id, attempt_id
            )
        except LedgerAmbiguous:
            inspection = None
        if inspection is not None and inspection.state == "PASS":
            if pending_recovery is not None:
                raise LedgerAmbiguous("E_LEDGER_RECOVERY_AFTER_PASS", pending_recovery)
            return {
                "action": "REUSE_PASS",
                "attempt_number": number,
                "attempt_id": attempt_id,
                "recovery_id": None,
            }
        if pending_recovery is not None:
            return {
                "action": "START_NEW",
                "attempt_number": number + 1,
                "previous_attempt_id": attempt_id,
                "recovery_id": pending_recovery,
            }
        return {
            "action": "RECOVERY_REQUIRED",
            "attempt_number": number,
            "attempt_id": attempt_id,
            "state": inspection.state if inspection is not None else "AMBIGUOUS",
            "recovery_id": None,
        }

    def _assert_staging_empty(self) -> None:
        _exact_entry_names(
            self.staging_root,
            (),
            "E_LEDGER_STAGING_NOT_EMPTY",
        )

    def _validation_layout(self, expected_cell_ids: set[str]) -> tuple[str, ...]:
        _exact_entry_names(
            self.root,
            (
                ".locks",
                ".staging",
                ".staging-recoveries",
                "cells",
                "ledger-root.json",
            ),
            "E_LEDGER_ROOT_LAYOUT",
        )
        if self._load_ledger_root_record() != self.ledger_root_id:
            raise LedgerAmbiguous(
                "E_LEDGER_ROOT_RECEIPT_DRIFT", str(self.root_record_path)
            )
        self._validate_staging_recovery_archives()
        self._assert_staging_empty()
        try:
            entries = sorted(
                os.scandir(self.cells_root), key=lambda entry: entry.name
            )
        except OSError as exc:
            raise LedgerAmbiguous(
                "E_LEDGER_RESULT_SET_SCAN", str(self.cells_root)
            ) from exc
        observed: list[str] = []
        for entry in entries:
            path = Path(entry.path)
            if (
                _CELL_RE.fullmatch(entry.name) is None
                or entry.name not in expected_cell_ids
                or not entry.is_dir(follow_symlinks=False)
                or _is_reparse_or_link(path)
            ):
                raise LedgerAmbiguous(
                    "E_LEDGER_RESULT_SET_UNKNOWN_CELL", entry.path
                )
            observed.append(entry.name)
        return tuple(observed)

    def _ledger_snapshot_sha256(self) -> str:
        """Hash every evidence-bearing ledger byte under cells."""

        entries: list[dict[str, Any]] = [
            {"path": ".staging", "kind": "directory"},
            {"path": ".staging-recoveries", "kind": "directory"},
            {"path": "cells", "kind": "directory"},
        ]
        root_record_bytes = _read_bounded_plain_bytes(
            self.root_record_path,
            "E_LEDGER_ROOT_RECEIPT_READ",
        )
        entries.append(
            {
                "path": "ledger-root.json",
                "kind": "file",
                "bytes": len(root_record_bytes),
                "sha256": hashlib.sha256(root_record_bytes).hexdigest(),
            }
        )

        def visit(directory: Path, relative: str) -> None:
            _assert_plain_directory(directory)
            try:
                children = sorted(
                    os.scandir(directory), key=lambda item: item.name
                )
            except OSError as exc:
                raise LedgerAmbiguous(
                    "E_LEDGER_ROOT_SNAPSHOT_SCAN", str(directory)
                ) from exc
            for child in children:
                child_path = Path(child.path)
                child_relative = f"{relative}/{child.name}"
                if child.is_dir(follow_symlinks=False):
                    if _is_reparse_or_link(child_path):
                        raise LedgerAmbiguous(
                            "E_LEDGER_ROOT_SNAPSHOT_REPARSE", child.path
                        )
                    entries.append(
                        {"path": child_relative, "kind": "directory"}
                    )
                    visit(child_path, child_relative)
                    continue
                if (
                    not child.is_file(follow_symlinks=False)
                    or _is_reparse_or_link(child_path)
                ):
                    raise LedgerAmbiguous(
                        "E_LEDGER_ROOT_SNAPSHOT_ENTRY", child.path
                    )
                digest = hashlib.sha256()
                size = 0
                try:
                    with child_path.open("rb") as handle:
                        while True:
                            chunk = handle.read(1_048_576)
                            if not chunk:
                                break
                            size += len(chunk)
                            digest.update(chunk)
                except OSError as exc:
                    raise LedgerAmbiguous(
                        "E_LEDGER_ROOT_SNAPSHOT_READ", child.path
                    ) from exc
                entries.append(
                    {
                        "path": child_relative,
                        "kind": "file",
                        "bytes": size,
                        "sha256": digest.hexdigest(),
                    }
                )

        visit(self.staging_recoveries_root, ".staging-recoveries")
        visit(self.cells_root, "cells")
        return sha256_value(
            {
                "schema": LEDGER_SNAPSHOT_SCHEMA,
                "schema_version": SCHEMA_VERSION,
                "entries": entries,
            }
        )

    def validated_result_set(self, manifest: Any) -> ValidatedResultSet:
        """Validate every required cell under one stable root view."""

        with self._root_lock():
            return self._validated_result_set_locked(manifest)

    def _validated_result_set_locked(self, manifest: Any) -> ValidatedResultSet:
        """Validate all cells while the root consistency lock is held.

        Missing, incomplete, corrupt, or ambiguous cells stay blocking records.
        Only a fully inspected terminal result contributes to the validated
        result count.  This operation is read-only.  No private path or
        evidence payload enters the summary.
        """

        cells = expand_cells(manifest)
        expected_cell_ids = {cell.cell_id for cell in cells}
        initial_layout = self._validation_layout(expected_cell_ids)
        initial_snapshot = self._ledger_snapshot_sha256()

        records: list[dict[str, Any]] = []
        for cell in cells:
            record: dict[str, Any] = {
                "cell_id": cell.cell_id,
                "input_fingerprint": cell.input_fingerprint,
                "status": "MISSING",
                "attempt_id": None,
                "last_event_sha256": None,
                "cell_result_sha256": None,
            }
            cell_dir = self._cell_dir(cell.cell_id)
            if not os.path.lexists(cell_dir):
                records.append(record)
                continue
            try:
                stored_cell = self._load_cell_record(cell_dir)
                expected_cell = {
                    "schema": CELL_RECORD_SCHEMA,
                    "schema_version": SCHEMA_VERSION,
                    "cell_id": cell.cell_id,
                    "input_fingerprint": cell.input_fingerprint,
                    "identity": deepcopy(dict(cell.identity)),
                }
                if canonical_json_bytes(stored_cell) != canonical_json_bytes(
                    expected_cell
                ):
                    raise LedgerAmbiguous(
                        "E_LEDGER_RESULT_SET_CELL_DRIFT", str(cell_dir)
                    )
                attempts = self._attempt_directories(cell_dir)
                pending_recovery = self._validate_recovery_records(
                    cell, attempts
                )
                if not attempts:
                    record["status"] = "NOT_RUN"
                else:
                    attempt_id = attempts[-1][1]
                    inspection = self._inspect_attempt_locked(
                        cell.cell_id, attempt_id
                    )
                    status = inspection.state
                    if status not in CELL_STATUSES:
                        raise LedgerAmbiguous(
                            "E_LEDGER_RESULT_SET_STATUS", cell.cell_id
                        )
                    if pending_recovery is not None and status == "PASS":
                        raise LedgerAmbiguous(
                            "E_LEDGER_RECOVERY_AFTER_PASS", cell.cell_id
                        )
                    record.update(
                        status=status,
                        attempt_id=inspection.attempt_id,
                        last_event_sha256=inspection.last_event_sha256,
                        cell_result_sha256=inspection.cell_result_sha256,
                    )
            except LedgerError:
                record.update(
                    status="AMBIGUOUS",
                    attempt_id=None,
                    last_event_sha256=None,
                    cell_result_sha256=None,
                )
            records.append(record)
        final_layout = self._validation_layout(expected_cell_ids)
        final_snapshot = self._ledger_snapshot_sha256()
        if initial_layout != final_layout or initial_snapshot != final_snapshot:
            raise LedgerAmbiguous("E_LEDGER_ROOT_CHANGED", str(self.root))
        return _validated_result_set_from_ledger(
            manifest,
            records,
            ledger_snapshot_sha256=final_snapshot,
        )


__all__ = [
    "ATTEMPT_SCHEMA",
    "CELL_RECORD_SCHEMA",
    "EVENT_TYPES",
    "LEDGER_EVENT_SCHEMA",
    "RECOVERY_SCHEMA",
    "AttemptInspection",
    "LedgerAmbiguous",
    "LedgerConflict",
    "LedgerError",
    "LedgerStore",
]
