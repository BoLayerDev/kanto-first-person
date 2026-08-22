import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "package_release", ROOT / "tools" / "package_release.py"
)
PACKAGE_RELEASE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(PACKAGE_RELEASE)

FINGERPRINT = "A" * 40
EVIDENCE = {
    "kind": "test_report",
    "locator": "evidence://release/test-report",
    "sha256": "b" * 64,
}


def approved_records(version="2.0.0", channel="stable"):
    rights = {
        "schema": 1,
        "approved": True,
        "evidence_sha256": "c" * 64,
        "approval_record": dict(EVIDENCE),
    }
    required_gates = (
        PACKAGE_RELEASE.REQUIRED_RELEASE_GATES
        if channel == "stable"
        else PACKAGE_RELEASE.REQUIRED_PRERELEASE_GATES[channel]
    )
    gates = {
        name: {"passed": True, "evidence": [dict(EVIDENCE)]}
        for name in required_gates
    }
    ledger = {
        "schema": 1,
        "approved": True,
        "approved_by": "release-team",
        "approved_at": "2026-08-21T00:00:00Z",
        "release_version": "2.0.0",
        "tag": "v2.0.0",
        "gates": gates,
    }
    if channel != "stable":
        ledger["channel"] = channel
        ledger["release_version"] = version
        ledger["tag"] = "v" + version
    return rights, ledger


class ReleaseGateTests(unittest.TestCase):
    def test_all_audited_engine_commits_are_pinned(self):
        self.assertEqual(
            PACKAGE_RELEASE.PINNED_ENGINES,
            {
                "44f4680b24823629489ed5a2adad648d0dceb640",
                "06e06e305bbcefe97c216a31bb25265ffb5e6b18",
                "70d7b6383e2c005857013dc897fd096886b08f0b",
                "087a2751895899ad6e79800599ae27a8f40cf1e3",
            },
        )

    def test_unapproved_public_ledger_covers_every_required_gate(self):
        ledger = json.loads(
            (ROOT / "docs" / "release-gates.json").read_text(encoding="utf-8")
        )
        self.assertFalse(ledger["approved"])
        self.assertEqual(
            set(ledger["gates"]), set(PACKAGE_RELEASE.REQUIRED_RELEASE_GATES)
        )
        self.assertTrue(all(not gate["passed"] for gate in ledger["gates"].values()))

    def test_unapproved_alpha_ledger_covers_every_required_gate(self):
        ledger = json.loads(
            (ROOT / "docs" / "prerelease-gates.json").read_text(encoding="utf-8")
        )
        self.assertFalse(ledger["approved"])
        self.assertEqual(ledger["channel"], "alpha")
        self.assertEqual(ledger["release_version"], "2.0.0-alpha.1")
        self.assertEqual(
            set(ledger["gates"]),
            set(PACKAGE_RELEASE.REQUIRED_PRERELEASE_GATES["alpha"]),
        )
        self.assertTrue(all(not gate["passed"] for gate in ledger["gates"].values()))

    def test_release_policy_selects_prerelease_and_stable_ledgers(self):
        self.assertEqual(
            PACKAGE_RELEASE.release_policy("2.0.0-alpha.1")[:2],
            ("alpha", "docs/prerelease-gates.json"),
        )
        self.assertEqual(
            PACKAGE_RELEASE.release_policy("2.0.0-beta.2")[:2],
            ("beta", "docs/prerelease-gates.json"),
        )
        self.assertEqual(
            PACKAGE_RELEASE.release_policy("2.0.0-rc.1")[:2],
            ("rc", "docs/prerelease-gates.json"),
        )
        self.assertEqual(
            PACKAGE_RELEASE.release_policy("2.0.0")[:2],
            ("stable", "docs/release-gates.json"),
        )
        with self.assertRaisesRegex(RuntimeError, "unsupported prerelease channel"):
            PACKAGE_RELEASE.release_policy("2.0.0-preview.1")

    def test_approval_schema_rejects_weak_hashes_and_evidence(self):
        rights, ledger = approved_records()
        rights["evidence_sha256"] = "A" * 64
        with self.assertRaisesRegex(RuntimeError, "rights evidence hash"):
            PACKAGE_RELEASE.validate_release_records(
                rights, ledger, "2.0.0", "v2.0.0"
            )

        rights, ledger = approved_records()
        ledger["gates"][PACKAGE_RELEASE.REQUIRED_RELEASE_GATES[0]]["evidence"] = [
            None
        ]
        with self.assertRaisesRegex(RuntimeError, "incomplete gates"):
            PACKAGE_RELEASE.validate_release_records(
                rights, ledger, "2.0.0", "v2.0.0"
            )

    def test_complete_signed_tag_approval_uses_tagged_records(self):
        rights, ledger = approved_records()
        commit = "d" * 40

        def fake_run(*args, cwd, env=None):
            command = tuple(args[1:])
            if command == ("describe", "--tags", "--exact-match"):
                return "v2.0.0"
            if command == ("cat-file", "-t", "v2.0.0"):
                return "tag"
            if command == ("rev-list", "-n", "1", "v2.0.0"):
                return commit
            if command == ("verify-tag", "--raw", "v2.0.0"):
                return "[GNUPG:] VALIDSIG " + FINGERPRINT + " 2026"
            raise AssertionError(command)

        def fake_run_bytes(*args, cwd):
            target = args[-1]
            if target.endswith("rights-approval.json"):
                return json.dumps(rights, sort_keys=True).encode()
            if target.endswith("release-gates.json"):
                return json.dumps(ledger, sort_keys=True).encode()
            raise AssertionError(target)

        with mock.patch.object(PACKAGE_RELEASE, "run", side_effect=fake_run), \
                mock.patch.object(
                    PACKAGE_RELEASE, "run_bytes", side_effect=fake_run_bytes
                ):
            approval = PACKAGE_RELEASE.require_release_approval(
                Path("signed-source"), "2.0.0", commit, FINGERPRINT
            )
        self.assertEqual(approval["tag_commit"], commit)
        self.assertEqual(approval["signing_key_fingerprint"], FINGERPRINT)

    def test_complete_signed_alpha_uses_tagged_prerelease_ledger(self):
        version = "2.0.0-alpha.1"
        rights, ledger = approved_records(version, "alpha")
        commit = "e" * 40

        def fake_run(*args, cwd, env=None):
            command = tuple(args[1:])
            if command == ("describe", "--tags", "--exact-match"):
                return "v" + version
            if command == ("cat-file", "-t", "v" + version):
                return "tag"
            if command == ("rev-list", "-n", "1", "v" + version):
                return commit
            if command == ("verify-tag", "--raw", "v" + version):
                return "[GNUPG:] VALIDSIG " + FINGERPRINT + " 2026"
            raise AssertionError(command)

        def fake_run_bytes(*args, cwd):
            target = args[-1]
            if target.endswith("rights-approval.json"):
                return json.dumps(rights, sort_keys=True).encode()
            if target.endswith("prerelease-gates.json"):
                return json.dumps(ledger, sort_keys=True).encode()
            raise AssertionError(target)

        with mock.patch.object(PACKAGE_RELEASE, "run", side_effect=fake_run), \
                mock.patch.object(
                    PACKAGE_RELEASE, "run_bytes", side_effect=fake_run_bytes
                ):
            approval = PACKAGE_RELEASE.require_release_approval(
                Path("signed-source"), version, commit, FINGERPRINT
            )
        self.assertEqual(approval["channel"], "alpha")
        self.assertEqual(approval["tag"], "v" + version)

    def test_release_needs_an_external_trusted_signer(self):
        with self.assertRaisesRegex(RuntimeError, "trusted signing-key"):
            PACKAGE_RELEASE.require_release_approval(
                Path("source"), "2.0.0", "d" * 40, None
            )

    def test_strict_json_rejects_duplicate_keys(self):
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            PACKAGE_RELEASE.strict_json_loads('{"permissions":[],"permissions":["filesystem"]}')

    def test_runtime_package_paths_use_an_explicit_allowlist(self):
        self.assertTrue(PACKAGE_RELEASE.allowed_runtime_path("src/core/RNG.lua"))
        self.assertTrue(
            PACKAGE_RELEASE.allowed_runtime_path(
                "assets/legacy/horizons/backdrop.png"
            )
        )
        self.assertFalse(
            PACKAGE_RELEASE.allowed_runtime_path("assets/roms/local.pem")
        )
        self.assertFalse(PACKAGE_RELEASE.allowed_runtime_path("src/private.env"))

    def test_engine_tools_are_copied_from_the_pinned_commit(self):
        with tempfile.TemporaryDirectory() as raw:
            temporary = Path(raw)
            engine = temporary / "source-engine"
            dirty_tool = engine / "tools" / "modkit.py"
            dirty_tool.parent.mkdir(parents=True)
            dirty_tool.write_text("dirty worktree", encoding="utf-8")
            staging = temporary / "staged-engine"

            def fake_run(*args, cwd, env=None):
                output = next(arg for arg in args if arg.startswith("--output="))
                archive_path = Path(output.split("=", 1)[1])
                with zipfile.ZipFile(archive_path, "w") as archive:
                    archive.writestr("tools/modkit.py", "pinned commit")
                    archive.writestr("tools/rom_manifest.json", "{}")
                    archive.writestr("src/mods/Loader.lua", "return {}")
                return ""

            with mock.patch.object(PACKAGE_RELEASE, "run", side_effect=fake_run):
                PACKAGE_RELEASE.copy_engine_from_commit(
                    engine, "a" * 40, staging, temporary
                )
            self.assertEqual(
                (staging / "tools" / "modkit.py").read_text(encoding="utf-8"),
                "pinned commit",
            )


if __name__ == "__main__":
    unittest.main()
