import os
from pathlib import Path
import shutil
import stat
import tempfile
import unittest
from unittest import mock

from tests.tools import _scoped_test_directory as scoped
from tests.tools._scoped_test_directory import ScopedTestDirectory
from tools.release_matrix import ledger


class ScopedTestDirectoryTests(unittest.TestCase):
    def test_context_and_manual_cleanup_have_temporary_directory_parity(self):
        with ScopedTestDirectory() as name:
            self.assertIsInstance(name, str)
            root = Path(name)
            self.assertTrue(root.is_dir())
            (root / "payload.txt").write_text("synthetic", encoding="utf-8")
        self.assertFalse(os.path.lexists(root))

        temporary = ScopedTestDirectory()
        root = Path(temporary.name)
        self.assertTrue(root.is_dir())
        temporary.cleanup()
        self.assertFalse(os.path.lexists(root))

    def test_cleanup_is_idempotent(self):
        temporary = ScopedTestDirectory()
        root = Path(temporary.name)
        temporary.cleanup()
        temporary.cleanup()
        self.assertFalse(os.path.lexists(root))

    @unittest.skipUnless(os.name == "nt", "Windows-only allocation policy")
    def test_collision_attempts_are_bounded(self):
        with mock.patch.object(scoped.secrets, "token_hex", return_value="0" * 32):
            with mock.patch.object(
                scoped.os, "mkdir", side_effect=FileExistsError("collision")
            ) as mkdir:
                with self.assertRaisesRegex(FileExistsError, "could not allocate"):
                    ScopedTestDirectory()
        self.assertEqual(mkdir.call_count, 64)

    @unittest.skipUnless(os.name == "nt", "Windows-only sibling policy")
    def test_cleanup_preserves_sibling_and_supports_two_live_roots(self):
        original = Path.mkdir
        first = ScopedTestDirectory()
        second = ScopedTestDirectory()
        first_root = Path(first.name)
        second_root = Path(second.name)
        self.assertIs(Path.mkdir, scoped._scoped_path_mkdir)
        first.cleanup()
        self.assertFalse(os.path.lexists(first_root))
        self.assertTrue(second_root.is_dir())
        self.assertIs(Path.mkdir, scoped._scoped_path_mkdir)
        second.cleanup()
        self.assertFalse(os.path.lexists(second_root))
        self.assertIs(Path.mkdir, original)

    @unittest.skipUnless(os.name == "nt", "Windows-only identity policy")
    def test_identity_mismatch_fails_closed_without_deleting_root(self):
        temporary = ScopedTestDirectory()
        root = Path(temporary.name)
        real_identity = scoped._ordinary_directory_identity

        def changed_identity(path):
            identity = real_identity(path)
            if Path(path) == root:
                return identity[0], identity[1] + 1
            return identity

        with mock.patch.object(
            scoped, "_ordinary_directory_identity", side_effect=changed_identity
        ):
            with self.assertRaisesRegex(RuntimeError, "identity changed"):
                temporary.cleanup()
        self.assertTrue(root.is_dir())
        shutil.rmtree(root)
        self.assertIs(Path.mkdir, scoped._ORIGINAL_PATH_MKDIR)

    @unittest.skipUnless(os.name == "nt", "Windows-only patch policy")
    def test_foreign_path_mkdir_patch_fails_closed_and_restores_original(self):
        temporary = ScopedTestDirectory()
        root = Path(temporary.name)

        def foreign_mkdir(self, mode=0o777, parents=False, exist_ok=False):
            raise AssertionError("foreign patch must not run")

        Path.mkdir = foreign_mkdir
        with self.assertRaisesRegex(RuntimeError, "foreign pathlib.Path.mkdir patch"):
            temporary.cleanup()
        self.assertTrue(root.is_dir())
        self.assertIs(Path.mkdir, scoped._ORIGINAL_PATH_MKDIR)
        shutil.rmtree(root)

    @unittest.skipUnless(os.name == "nt", "Windows-only ReadOnly policy")
    def test_readonly_cleanup_retries_exact_unlink_and_preserves_other_bits(self):
        temporary = ScopedTestDirectory()
        self.addCleanup(temporary.cleanup)
        target = Path(temporary.name) / "readonly.txt"
        target.write_text("synthetic", encoding="utf-8")
        identity = (41, 43)
        original_attributes = scoped._READONLY_ATTRIBUTE | 0x0002 | 0x0020
        state = {"attributes": original_attributes}

        def file_state(path):
            self.assertEqual(Path(path), target)
            return identity, state["attributes"]

        def set_attributes(path, attributes):
            self.assertEqual(Path(path), target)
            state["attributes"] = attributes

        denied = PermissionError(13, "denied", str(target), 5)
        with mock.patch.object(
            scoped, "_ordinary_file_state", side_effect=file_state
        ), mock.patch.object(
            scoped, "_set_windows_file_attributes", side_effect=set_attributes
        ) as setter, mock.patch.object(scoped.os, "unlink") as unlink:
            temporary._rmtree_onexc(unlink, str(target), denied)

        cleared = original_attributes & ~scoped._READONLY_ATTRIBUTE
        setter.assert_called_once_with(target, cleared)
        unlink.assert_called_once_with(str(target))
        self.assertEqual(state["attributes"], cleared)
        self.assertEqual(
            cleared & ~scoped._READONLY_ATTRIBUTE,
            original_attributes & ~scoped._READONLY_ATTRIBUTE,
        )

    @unittest.skipUnless(os.name == "nt", "Windows-only ReadOnly policy")
    def test_actual_readonly_file_cleanup_preserves_live_sibling(self):
        first = ScopedTestDirectory()
        second = ScopedTestDirectory()
        self.addCleanup(second.cleanup)
        self.addCleanup(first.cleanup)
        first_root = Path(first.name)
        second_root = Path(second.name)
        target = first_root / "readonly.txt"
        sibling = second_root / "sibling.txt"
        target.write_text("synthetic", encoding="utf-8")
        sibling.write_text("preserve", encoding="utf-8")
        attributes = os.lstat(target).st_file_attributes
        scoped._set_windows_file_attributes(
            target,
            attributes | scoped._READONLY_ATTRIBUTE,
        )

        first.cleanup()
        self.assertFalse(os.path.lexists(first_root))
        self.assertEqual(sibling.read_text(encoding="utf-8"), "preserve")
        second.cleanup()
        self.assertFalse(os.path.lexists(second_root))

    @unittest.skipUnless(os.name == "nt", "Windows-only ReadOnly policy")
    def test_failed_unlink_restores_exact_attributes_only_for_same_identity(self):
        temporary = ScopedTestDirectory()
        self.addCleanup(temporary.cleanup)
        target = Path(temporary.name) / "readonly.txt"
        target.write_text("synthetic", encoding="utf-8")
        identity = (47, 53)
        original_attributes = scoped._READONLY_ATTRIBUTE | 0x0002 | 0x0020
        state = {"attributes": original_attributes}

        def file_state(path):
            return identity, state["attributes"]

        def set_attributes(path, attributes):
            state["attributes"] = attributes

        denied = PermissionError(13, "denied", str(target), 5)
        retry_error = PermissionError(13, "still denied", str(target), 5)
        with mock.patch.object(
            scoped, "_ordinary_file_state", side_effect=file_state
        ), mock.patch.object(
            scoped, "_set_windows_file_attributes", side_effect=set_attributes
        ) as setter, mock.patch.object(
            scoped.os, "unlink", side_effect=retry_error
        ) as unlink:
            with self.assertRaises(PermissionError) as raised:
                temporary._rmtree_onexc(unlink, str(target), denied)

        self.assertIs(raised.exception, retry_error)
        self.assertEqual(
            setter.call_args_list,
            [
                mock.call(target, original_attributes & ~scoped._READONLY_ATTRIBUTE),
                mock.call(target, original_attributes),
            ],
        )
        self.assertEqual(state["attributes"], original_attributes)

    @unittest.skipUnless(os.name == "nt", "Windows-only ReadOnly policy")
    def test_readonly_cleanup_rejects_wrong_function_error_and_scope(self):
        first = ScopedTestDirectory()
        second = ScopedTestDirectory()
        self.addCleanup(first.cleanup)
        self.addCleanup(second.cleanup)
        root = Path(first.name)
        target = root / "readonly.txt"
        target.write_text("synthetic", encoding="utf-8")
        outside = Path(second.name) / "sibling.txt"
        outside.write_text("preserve", encoding="utf-8")
        denied = PermissionError(13, "denied", str(target), 5)
        wrong_error = PermissionError(13, "sharing violation", str(target), 32)

        with self.assertRaisesRegex(RuntimeError, "non-unlink"):
            first._rmtree_onexc(os.rmdir, str(target), denied)
        with self.assertRaises(PermissionError) as raised:
            first._rmtree_onexc(os.unlink, str(target), wrong_error)
        self.assertIs(raised.exception, wrong_error)
        with self.assertRaisesRegex(RuntimeError, "outside its root"):
            first._rmtree_onexc(os.unlink, str(root), denied)
        with self.assertRaisesRegex(RuntimeError, "outside its root"):
            first._rmtree_onexc(os.unlink, str(outside), denied)
        self.assertEqual(outside.read_text(encoding="utf-8"), "preserve")

    @unittest.skipUnless(os.name == "nt", "Windows-only ReadOnly policy")
    def test_readonly_cleanup_rejects_nonreadonly_and_target_identity_drift(self):
        temporary = ScopedTestDirectory()
        self.addCleanup(temporary.cleanup)
        target = Path(temporary.name) / "target.txt"
        target.write_text("synthetic", encoding="utf-8")
        denied = PermissionError(13, "denied", str(target), 5)

        with mock.patch.object(
            scoped,
            "_ordinary_file_state",
            return_value=((59, 61), 0x0020),
        ), mock.patch.object(scoped.os, "unlink") as unlink:
            with self.assertRaisesRegex(RuntimeError, "not ReadOnly"):
                temporary._rmtree_onexc(unlink, str(target), denied)
        unlink.assert_not_called()

        states = iter(
            (
                ((59, 61), scoped._READONLY_ATTRIBUTE | 0x0020),
                ((59, 67), 0x0020),
            )
        )
        with mock.patch.object(
            scoped, "_ordinary_file_state", side_effect=lambda path: next(states)
        ), mock.patch.object(
            scoped, "_set_windows_file_attributes"
        ) as setter, mock.patch.object(scoped.os, "unlink") as unlink:
            with self.assertRaisesRegex(RuntimeError, "target identity changed"):
                temporary._rmtree_onexc(unlink, str(target), denied)
        setter.assert_called_once_with(target, 0x0020)
        unlink.assert_not_called()

    @unittest.skipUnless(os.name == "nt", "Windows-only identity policy")
    def test_readonly_cleanup_rejects_parent_identity_drift_before_mutation(self):
        temporary = ScopedTestDirectory()
        self.addCleanup(temporary.cleanup)
        target = Path(temporary.name) / "target.txt"
        target.write_text("synthetic", encoding="utf-8")
        denied = PermissionError(13, "denied", str(target), 5)
        real_identity = scoped._ordinary_directory_identity

        def changed_parent(path):
            identity = real_identity(path)
            if Path(path) == temporary._parent:
                return identity[0], identity[1] + 1
            return identity

        with mock.patch.object(
            scoped,
            "_ordinary_directory_identity",
            side_effect=changed_parent,
        ), mock.patch.object(
            scoped, "_set_windows_file_attributes"
        ) as setter, mock.patch.object(scoped.os, "unlink") as unlink:
            with self.assertRaisesRegex(RuntimeError, "parent identity changed"):
                temporary._rmtree_onexc(unlink, str(target), denied)
        setter.assert_not_called()
        unlink.assert_not_called()

    def test_cleanup_file_state_rejects_directory_symlink_and_reparse(self):
        invalid_states = (
            mock.Mock(st_mode=stat.S_IFDIR | 0o755, st_file_attributes=0),
            mock.Mock(st_mode=stat.S_IFLNK | 0o777, st_file_attributes=0),
            mock.Mock(
                st_mode=stat.S_IFREG | 0o644,
                st_file_attributes=scoped._REPARSE_POINT,
            ),
        )
        for observed in invalid_states:
            with self.subTest(mode=observed.st_mode):
                with mock.patch.object(scoped.os, "lstat", return_value=observed):
                    with self.assertRaisesRegex(RuntimeError, "not an ordinary file"):
                        scoped._ordinary_file_state(Path("synthetic-target"))

    def test_reparse_directory_identity_is_rejected(self):
        fake = mock.Mock(
            st_mode=stat.S_IFDIR | 0o755,
            st_dev=1,
            st_ino=2,
            st_file_attributes=scoped._REPARSE_POINT,
        )
        with mock.patch.object(scoped.os, "lstat", return_value=fake):
            with self.assertRaisesRegex(RuntimeError, "not ordinary"):
                scoped._ordinary_directory_identity(Path("synthetic-reparse"))

    def test_posix_delegates_with_secure_prefix(self):
        delegate = mock.Mock()
        delegate.name = "/synthetic/kfp-test-delegate"
        with mock.patch.object(scoped, "_is_windows", return_value=False):
            with mock.patch.object(
                scoped.tempfile, "TemporaryDirectory", return_value=delegate
            ) as constructor:
                temporary = ScopedTestDirectory()
                self.assertEqual(temporary.name, delegate.name)
                temporary.cleanup()
        constructor.assert_called_once_with(prefix="kfp-test-")
        delegate.cleanup.assert_called_once_with()

    @unittest.skipUnless(os.name == "nt", "Windows-only adapter policy")
    def test_exact_adapter_restoration_and_descendant_ledger_writeability(self):
        original = Path.mkdir
        temporary = ScopedTestDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        child = root / "direct-700"
        child.mkdir(mode=0o700)
        (child / "payload.txt").write_text("synthetic", encoding="utf-8")
        self.assertEqual(
            (child / "payload.txt").read_text(encoding="utf-8"), "synthetic"
        )
        store = ledger.LedgerStore(root / "ledger")
        self.assertTrue(store.root.is_dir())
        temporary.cleanup()
        self.assertIs(Path.mkdir, original)

    def test_adapter_delegates_outside_paths_and_nonexact_modes_unchanged(self):
        registered = Path(tempfile.gettempdir()) / "registered-lexical-root"
        outside = Path(tempfile.gettempdir()) / "outside-lexical-root"
        root_key = scoped._lexical_key(registered)
        marker = object()
        with scoped._REGISTRY_LOCK:
            scoped._WINDOWS_ROOTS[root_key] = marker
        try:
            with mock.patch.object(scoped, "_ORIGINAL_PATH_MKDIR") as original:
                scoped._scoped_path_mkdir(outside, mode=0o700, parents=True, exist_ok=True)
                original.assert_called_once_with(
                    outside, mode=0o700, parents=True, exist_ok=True
                )
                for mode in (0o000, 0o600, 0o701, 0o755, 0o777):
                    original.reset_mock()
                    scoped._scoped_path_mkdir(
                        registered / "child", mode=mode, parents=False, exist_ok=False
                    )
                    original.assert_called_once_with(
                        registered / "child",
                        mode=mode,
                        parents=False,
                        exist_ok=False,
                    )
                original.reset_mock()
                scoped._scoped_path_mkdir(
                    registered / "child", mode=0o700, parents=False, exist_ok=False
                )
                original.assert_called_once_with(
                    registered / "child",
                    mode=0o777,
                    parents=False,
                    exist_ok=False,
                )
        finally:
            with scoped._REGISTRY_LOCK:
                scoped._WINDOWS_ROOTS.pop(root_key, None)


if __name__ == "__main__":
    unittest.main()
