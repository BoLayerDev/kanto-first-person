"""Sandbox-safe temporary directories for repository tests only."""

from __future__ import annotations

import os
from pathlib import Path
import secrets
import shutil
import stat
import tempfile
import threading
from typing import Any


_ORIGINAL_PATH_MKDIR = Path.mkdir
_REGISTRY_LOCK = threading.RLock()
_WINDOWS_ROOTS: dict[str, "ScopedTestDirectory"] = {}
_MAX_COLLISION_ATTEMPTS = 64
_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x0400)
_READONLY_ATTRIBUTE = getattr(stat, "FILE_ATTRIBUTE_READONLY", 0x0001)


def _is_windows() -> bool:
    return os.name == "nt"


def _lexical_key(path: Path | str) -> str:
    return os.path.normcase(os.path.abspath(os.fspath(path)))


def _ordinary_directory_identity(path: Path) -> tuple[int, int]:
    try:
        observed = os.lstat(path)
    except OSError as exc:
        raise RuntimeError(f"scoped test directory is unavailable: {path}") from exc
    attributes = getattr(observed, "st_file_attributes", 0)
    if not stat.S_ISDIR(observed.st_mode) or attributes & _REPARSE_POINT:
        raise RuntimeError(f"scoped test directory is not ordinary: {path}")
    return observed.st_dev, observed.st_ino


def _is_registered_path(path: Path) -> bool:
    candidate = _lexical_key(path)
    with _REGISTRY_LOCK:
        roots = tuple(_WINDOWS_ROOTS)
    for root in roots:
        try:
            if os.path.commonpath((candidate, root)) == root:
                return True
        except ValueError:
            continue
    return False


def _scoped_path_mkdir(
    self: Path,
    mode: int = 0o777,
    parents: bool = False,
    exist_ok: bool = False,
) -> None:
    translated_mode = 0o777 if mode == 0o700 and _is_registered_path(self) else mode
    return _ORIGINAL_PATH_MKDIR(
        self, mode=translated_mode, parents=parents, exist_ok=exist_ok
    )


def _set_windows_file_attributes(path: Path, attributes: int) -> None:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    set_attributes = kernel32.SetFileAttributesW
    set_attributes.argtypes = (wintypes.LPCWSTR, wintypes.DWORD)
    set_attributes.restype = wintypes.BOOL
    if not set_attributes(str(path), attributes):
        raise ctypes.WinError(ctypes.get_last_error())


def _ordinary_file_state(path: Path) -> tuple[tuple[int, int], int]:
    try:
        observed = os.lstat(path)
    except OSError as exc:
        raise RuntimeError(f"scoped cleanup target is unavailable: {path}") from exc
    attributes = getattr(observed, "st_file_attributes", 0)
    if not stat.S_ISREG(observed.st_mode) or attributes & _REPARSE_POINT:
        raise RuntimeError(f"scoped cleanup target is not an ordinary file: {path}")
    return (observed.st_dev, observed.st_ino), attributes


class ScopedTestDirectory:
    """Provide the TemporaryDirectory subset used by repository tests."""

    def __init__(self) -> None:
        self._delegate: Any | None = None
        self._closed = False
        self._parent: Path | None = None
        self._parent_identity: tuple[int, int] | None = None
        self._root: Path | None = None
        self._root_identity: tuple[int, int] | None = None
        self._root_key: str | None = None

        if not _is_windows():
            self._delegate = tempfile.TemporaryDirectory(prefix="kfp-test-")
            self.name = self._delegate.name
            return

        parent = Path(tempfile.gettempdir())
        if not parent.is_absolute():
            raise RuntimeError("test Temp parent must be absolute")
        parent_identity = _ordinary_directory_identity(parent)

        root: Path | None = None
        for _ in range(_MAX_COLLISION_ATTEMPTS):
            candidate = parent / f"kfp-test-{secrets.token_hex(16)}"
            try:
                os.mkdir(candidate)
            except FileExistsError:
                continue
            root = candidate
            break
        if root is None:
            raise FileExistsError("could not allocate a scoped test directory")

        root_identity = _ordinary_directory_identity(root)
        if _ordinary_directory_identity(parent) != parent_identity:
            shutil.rmtree(root)
            raise RuntimeError("test Temp parent identity changed during creation")

        root_key = _lexical_key(root)
        self._parent = parent
        self._parent_identity = parent_identity
        self._root = root
        self._root_identity = root_identity
        self._root_key = root_key
        self.name = str(root)
        try:
            with _REGISTRY_LOCK:
                if _WINDOWS_ROOTS:
                    if Path.mkdir is not _scoped_path_mkdir:
                        raise RuntimeError("foreign pathlib.Path.mkdir patch detected")
                else:
                    if Path.mkdir is not _ORIGINAL_PATH_MKDIR:
                        raise RuntimeError("foreign pathlib.Path.mkdir patch detected")
                    Path.mkdir = _scoped_path_mkdir
                if root_key in _WINDOWS_ROOTS:
                    raise RuntimeError("scoped test directory identity collision")
                _WINDOWS_ROOTS[root_key] = self
        except BaseException:
            if (
                _ordinary_directory_identity(parent) == parent_identity
                and _ordinary_directory_identity(root) == root_identity
            ):
                shutil.rmtree(root)
            raise

    def __enter__(self) -> str:
        return self.name

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.cleanup()

    def _validate_windows_cleanup_target(
        self,
        target: Path,
        *,
        expected_identity: tuple[int, int] | None = None,
    ) -> tuple[tuple[int, int], int]:
        assert self._parent is not None
        assert self._parent_identity is not None
        assert self._root is not None
        assert self._root_identity is not None
        assert self._root_key is not None

        with _REGISTRY_LOCK:
            if _WINDOWS_ROOTS.get(self._root_key) is not self:
                raise RuntimeError("scoped test directory registry drift detected")
            if Path.mkdir is not _scoped_path_mkdir:
                raise RuntimeError("foreign pathlib.Path.mkdir patch detected")
        if _ordinary_directory_identity(self._parent) != self._parent_identity:
            raise RuntimeError("test Temp parent identity changed")
        if _ordinary_directory_identity(self._root) != self._root_identity:
            raise RuntimeError("scoped test directory identity changed")

        root_key = self._root_key
        target_key = _lexical_key(target)
        try:
            common = os.path.commonpath((root_key, target_key))
        except ValueError as exc:
            raise RuntimeError("scoped cleanup target is outside its root") from exc
        if common != root_key or target_key == root_key:
            raise RuntimeError("scoped cleanup target is outside its root")

        relative = os.path.relpath(target_key, root_key)
        ancestor = self._root
        for part in Path(relative).parts[:-1]:
            ancestor /= part
            _ordinary_directory_identity(ancestor)

        identity, attributes = _ordinary_file_state(target)
        if expected_identity is not None and identity != expected_identity:
            raise RuntimeError("scoped cleanup target identity changed")
        return identity, attributes

    def _rmtree_onexc(
        self,
        function: Any,
        path: str,
        error: BaseException,
    ) -> None:
        if not _is_windows():
            raise error
        if function is not os.unlink:
            raise RuntimeError("scoped cleanup rejected a non-unlink failure") from error
        if not isinstance(error, PermissionError) or getattr(error, "winerror", None) != 5:
            raise error

        target = Path(path)
        identity, attributes = self._validate_windows_cleanup_target(target)
        if not attributes & _READONLY_ATTRIBUTE:
            raise RuntimeError("scoped cleanup target is not ReadOnly") from error

        cleared_attributes = attributes & ~_READONLY_ATTRIBUTE
        _set_windows_file_attributes(target, cleared_attributes)
        _, current_attributes = self._validate_windows_cleanup_target(
            target,
            expected_identity=identity,
        )
        if current_attributes != cleared_attributes:
            raise RuntimeError("scoped cleanup target attributes changed")
        try:
            function(path)
        except BaseException as retry_error:
            try:
                _, current_attributes = self._validate_windows_cleanup_target(
                    target,
                    expected_identity=identity,
                )
                if current_attributes != cleared_attributes:
                    raise RuntimeError(
                        "scoped cleanup target attributes changed"
                    )
                _set_windows_file_attributes(target, attributes)
            except BaseException as restore_error:
                raise restore_error from retry_error
            raise

    def cleanup(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._delegate is not None:
            self._delegate.cleanup()
            return

        assert self._parent is not None
        assert self._parent_identity is not None
        assert self._root is not None
        assert self._root_identity is not None
        assert self._root_key is not None
        cleanup_error: BaseException | None = None
        try:
            with _REGISTRY_LOCK:
                if _WINDOWS_ROOTS.get(self._root_key) is not self:
                    raise RuntimeError("scoped test directory registry drift detected")
                if Path.mkdir is not _scoped_path_mkdir:
                    raise RuntimeError("foreign pathlib.Path.mkdir patch detected")
            if _ordinary_directory_identity(self._parent) != self._parent_identity:
                raise RuntimeError("test Temp parent identity changed")
            if _ordinary_directory_identity(self._root) != self._root_identity:
                raise RuntimeError("scoped test directory identity changed")
            shutil.rmtree(self._root, onexc=self._rmtree_onexc)
            if os.path.lexists(self._root):
                raise RuntimeError("scoped test directory cleanup was incomplete")
        except BaseException as exc:
            cleanup_error = exc
        finally:
            try:
                with _REGISTRY_LOCK:
                    _WINDOWS_ROOTS.pop(self._root_key, None)
                    if not _WINDOWS_ROOTS:
                        if Path.mkdir is not _scoped_path_mkdir and cleanup_error is None:
                            cleanup_error = RuntimeError(
                                "foreign pathlib.Path.mkdir patch detected"
                            )
                        Path.mkdir = _ORIGINAL_PATH_MKDIR
            except BaseException as exc:
                if cleanup_error is None:
                    cleanup_error = exc
        if cleanup_error is not None:
            raise cleanup_error
