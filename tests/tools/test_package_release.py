import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest import mock
import zipfile

from tests.tools._scoped_test_directory import ScopedTestDirectory

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


def run_git(repo, *args, env=None):
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        env=env,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()


def fixture_git_environment(parent):
    environment = os.environ.copy()
    global_config = parent / "empty-git-global-config"
    global_config.write_bytes(b"")
    environment["GIT_CONFIG_GLOBAL"] = str(global_config)
    environment["GIT_CONFIG_NOSYSTEM"] = "1"
    environment.pop("GIT_CONFIG_PARAMETERS", None)
    environment.pop("GIT_CONFIG_COUNT", None)
    environment.pop("GIT_TEMPLATE_DIR", None)
    for name in tuple(environment):
        if name.startswith("GIT_CONFIG_KEY_") or name.startswith(
            "GIT_CONFIG_VALUE_"
        ):
            environment.pop(name)
    return environment


def create_minimal_runtime_repo(parent):
    environment = fixture_git_environment(parent)
    template = parent / "empty-git-template"
    template.mkdir()
    repo = parent / "repo"
    repo.mkdir()
    run_git(
        repo,
        "init",
        "--quiet",
        f"--template={template}",
        "--initial-branch=fixture",
        "--shared=false",
        env=environment,
    )
    run_git(
        repo,
        "config",
        "--local",
        "core.sharedRepository",
        "false",
        env=environment,
    )
    run_git(repo, "config", "user.name", "Package Test", env=environment)
    run_git(
        repo,
        "config",
        "user.email",
        "package-test@example.invalid",
        env=environment,
    )
    run_git(repo, "config", "core.autocrlf", "false", env=environment)
    run_git(repo, "config", "core.eol", "lf", env=environment)
    (repo / ".gitattributes").write_bytes(b"* text=auto\n")
    (repo / ".gitignore").write_bytes(b"src/ignored.lua\n")
    (repo / "manifest.json").write_bytes(
        b'{"id":"fixture","version":"1.0.0"}\n'
    )
    (repo / "LICENSE").write_bytes(b"line one\nline two\n")
    (repo / "src").mkdir()
    (repo / "src" / "Main.lua").write_bytes(b"return true\n")
    run_git(repo, "add", ".", env=environment)
    run_git(
        repo,
        "commit",
        "--quiet",
        "-m",
        "test(fixture): create minimal runtime source",
        env=environment,
    )
    return (
        repo,
        run_git(repo, "rev-parse", "HEAD", env=environment),
        environment,
    )


def minimal_runtime_constants():
    return mock.patch.multiple(
        PACKAGE_RELEASE,
        ROOT_FILES=("manifest.json", "LICENSE"),
        ASSET_FILES=(),
        RUNTIME_DIRS=("src",),
    )


class ReleaseGateTests(unittest.TestCase):
    def test_all_audited_engine_commits_are_pinned(self):
        self.assertEqual(
            PACKAGE_RELEASE.PINNED_ENGINES,
            {
                "44f4680b24823629489ed5a2adad648d0dceb640",
                "06e06e305bbcefe97c216a31bb25265ffb5e6b18",
                "70d7b6383e2c005857013dc897fd096886b08f0b",
                "478e3bf8ebf7646edfda88320c6472cf32db2e67",
                "116a6ba450dd65f25c9be150952fc3c27be904c0",
            },
        )

    def test_unapproved_public_ledger_records_completed_asset_rights(self):
        ledger = json.loads(
            (ROOT / "docs" / "release-gates.json").read_text(encoding="utf-8")
        )
        rights = json.loads(
            (ROOT / "docs" / "rights-approval.json").read_text(encoding="utf-8")
        )
        self.assertFalse(ledger["approved"])
        self.assertEqual(
            set(ledger["gates"]), set(PACKAGE_RELEASE.REQUIRED_RELEASE_GATES)
        )
        self.assertTrue(rights["approved"])
        self.assertEqual(
            rights["evidence_sha256"], rights["approval_record"]["sha256"]
        )
        self.assertTrue(ledger["gates"]["asset_rights"]["passed"])
        self.assertEqual(
            ledger["gates"]["asset_rights"]["evidence"],
            [rights["approval_record"]],
        )
        self.assertTrue(ledger["gates"]["engine_reaudit"]["passed"])
        engine_evidence = ledger["gates"]["engine_reaudit"]["evidence"]
        self.assertEqual(len(engine_evidence), 1)
        report = ROOT / engine_evidence[0]["locator"]
        self.assertEqual(
            hashlib.sha256(report.read_bytes()).hexdigest(),
            engine_evidence[0]["sha256"],
        )
        self.assertTrue(all(
            not gate["passed"]
            for name, gate in ledger["gates"].items()
            if name not in {"asset_rights", "engine_reaudit"}
        ))

    def test_unapproved_alpha_ledger_records_exact_checkpoint_gates(self):
        ledger = json.loads(
            (ROOT / "docs" / "prerelease-gates.json").read_text(encoding="utf-8")
        )
        rights = json.loads(
            (ROOT / "docs" / "rights-approval.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            set(ledger),
            {
                "approved",
                "approved_at",
                "approved_by",
                "channel",
                "gates",
                "release_version",
                "schema",
                "tag",
            },
        )
        self.assertEqual(ledger["schema"], 1)
        self.assertFalse(ledger["approved"])
        self.assertIsNone(ledger["approved_at"])
        self.assertIsNone(ledger["approved_by"])
        self.assertEqual(ledger["channel"], "alpha")
        self.assertEqual(ledger["release_version"], "2.0.0-alpha.1")
        self.assertEqual(ledger["tag"], "v2.0.0-alpha.1")
        self.assertEqual(
            set(ledger["gates"]),
            set(PACKAGE_RELEASE.REQUIRED_PRERELEASE_GATES["alpha"]),
        )

        for gate in ledger["gates"].values():
            self.assertEqual(set(gate), {"passed", "evidence"})
            self.assertIsInstance(gate["passed"], bool)
            self.assertIsInstance(gate["evidence"], list)

        self.assertTrue(rights["approved"])
        self.assertEqual(
            rights["evidence_sha256"], rights["approval_record"]["sha256"]
        )
        self.assertTrue(PACKAGE_RELEASE.valid_evidence(rights["approval_record"]))
        self.assertTrue(ledger["gates"]["asset_rights"]["passed"])
        self.assertEqual(
            ledger["gates"]["asset_rights"]["evidence"],
            [rights["approval_record"]],
        )

        passed = {
            "asset_rights",
            "automated_tests",
            "companion_contracts",
            "known_limitations",
            "package_reproducibility",
            "source_integrity",
        }
        open_gates = {"released_hosts", "migration_safety"}
        self.assertEqual(
            {name for name, gate in ledger["gates"].items() if gate["passed"]},
            passed,
        )
        self.assertEqual(
            {name for name, gate in ledger["gates"].items() if not gate["passed"]},
            open_gates,
        )
        self.assertEqual(ledger["gates"]["migration_safety"]["evidence"], [])
        host_evidence = ledger["gates"]["released_hosts"]["evidence"]
        self.assertEqual(
            host_evidence,
            [{
                "kind": "host_release_delta",
                "locator": (
                    "docs/release-evidence/"
                    "host-release-delta-2026-08-22.json"
                ),
                "sha256": (
                    "59356c814b4e7b2bb966acfc485bfbab"
                    "6aaafd7ccc4246d715ff5d39d8dee4bd"
                ),
            }],
        )
        self.assertTrue(PACKAGE_RELEASE.valid_evidence(host_evidence[0]))
        host_delta_path = ROOT / host_evidence[0]["locator"]
        self.assertEqual(
            hashlib.sha256(host_delta_path.read_bytes()).hexdigest(),
            host_evidence[0]["sha256"],
        )
        host_delta = json.loads(host_delta_path.read_text(encoding="utf-8"))
        self.assertEqual(host_delta["observed_at"], "2026-08-22T19:56:35Z")
        self.assertEqual(
            host_delta["kfp_base_binding"],
            {
                "public_branch": "v2-rewrite",
                "base_commit": "e4fec6792cd9bfad28270860c44a9ab080aaa4b9",
                "evidence_parent": "79b385131d3628f405ad264a01973c479991fc43",
                "source_checkpoint": "cfc045bec72c2ceecd558b24bcd643c8e0b720dc",
            },
        )

        battle_art = host_delta["battle_art"]
        self.assertEqual(battle_art["owner_pr"]["state"], "MERGED")
        self.assertEqual(
            battle_art["owner_pr"]["head_commit"],
            "cee25fd117d881aa63ad7ef0bc7905ca0063fb29",
        )
        self.assertEqual(
            battle_art["owner_pr"]["merge_commit"],
            "5c0051b84fb9bca7d14b0ed9e44f81d662af25bd",
        )
        battle_release = battle_art["owner_release"]
        self.assertEqual(battle_release["tag"], "1.9.8")
        self.assertFalse(battle_release["draft"])
        self.assertFalse(battle_release["prerelease"])
        self.assertEqual(
            battle_release["tag_commit"],
            "6586ef5f7a86c1bfefcea931bd6571538c9f8d15",
        )
        self.assertEqual(
            battle_release["asset"],
            {
                "name": "BATTLE_ART_VOXEL_FORK-1.9.8.zip",
                "size_bytes": 123682063,
                "sha256": (
                    "c2e440bdacdba07b170f353e7a7d239"
                    "bda793554332bc66ff93bba76dc42a1db"
                ),
            },
        )
        battle_audit = battle_art["static_audit"]
        self.assertTrue(battle_audit["companion_runtime_present"])
        self.assertEqual(
            battle_audit["audit"]["sha256"],
            "08707de5f0bbafb629edd562768f0b088c131aed44df35973c27b085babe34c2",
        )
        self.assertEqual(
            battle_audit["extraction"]["sha256"],
            "1e092b9cdd4953d0457f120e198b70460aa7c1223331d6d1082a256901129cbb",
        )

        dramaless = host_delta["dramaless"]
        dramaless_release = dramaless["owner_release"]
        self.assertEqual(dramaless_release["tag"], "v2.0.3")
        self.assertFalse(dramaless_release["draft"])
        self.assertFalse(dramaless_release["prerelease"])
        self.assertEqual(
            dramaless_release["tag_commit"],
            "23750150ae6f939e09f9ac6ca6d80c382ec9997a",
        )
        self.assertFalse(dramaless_release["tag_signature_verified"])
        self.assertEqual(
            dramaless_release["asset"],
            {
                "name": "DRAMALESS_SHAPE-2.0.3.zip",
                "size_bytes": 549781,
                "sha256": (
                    "89f6fa078c78a6f6e34c98074ea50ff"
                    "4f971eead992f27684b52eae0f4f5a1a2"
                ),
            },
        )
        dramaless_pr = dramaless["owner_pr"]
        self.assertEqual(dramaless_pr["state"], "OPEN")
        self.assertFalse(dramaless_pr["draft"])
        self.assertFalse(dramaless_pr["mergeable"])
        self.assertEqual(dramaless_pr["merge_state"], "DIRTY")
        self.assertEqual(
            dramaless_pr["head_commit"],
            "f7575445d00593b7db1ecd66f93e8c26989f4136",
        )
        self.assertEqual(
            dramaless_pr["conflict_paths"],
            ["CHANGELOG.md", "lib/VoxelScene.lua", "main.lua"],
        )
        dramaless_audit = dramaless["static_audit"]
        self.assertEqual(
            dramaless_audit["sha256"],
            "2030981605f4c8e1c5636326c2ce897e211651852c5ace092fc5ee4a53a4cb74",
        )
        self.assertTrue(dramaless_audit["release_asset_matches_github_digest"])
        self.assertFalse(
            dramaless_audit["approved_companion_runtime_present_in_tag"]
        )
        self.assertFalse(
            dramaless_audit["approved_companion_runtime_present_in_release_asset"]
        )
        self.assertFalse(
            dramaless_audit["required_voxel_companion_export_present"]
        )
        self.assertEqual(
            dramaless["private_qa_candidate"],
            {
                "head_commit": "f7575445d00593b7db1ecd66f93e8c26989f4136",
                "released": False,
                "keep_staged": True,
                "reason": (
                    "The v2.0.3 owner release does not contain the approved "
                    "companion runtime."
                ),
            },
        )
        self.assertEqual(
            host_delta["decision"],
            {
                "battle_art_owner_release_evidence_exists": True,
                "battle_art_live_behavior_proven": False,
                "dramaless_owner_release_exists": True,
                "dramaless_companion_support_released": False,
                "released_hosts": False,
                "kfp_release_approved": False,
                "live_visual_acceptance": False,
                "migration_safety": False,
                "native_performance": False,
                "full_scene_performance": False,
                "signed_tag": False,
            },
        )
        registry = ROOT / "docs" / "project-coordination" / "source-registry.md"
        self.assertIn(
            "[host-release-delta-2026-08-22.json]"
            "(../release-evidence/host-release-delta-2026-08-22.json)",
            registry.read_text(encoding="utf-8"),
        )

        expected_kinds = {
            "automated_tests": "ci_run",
            "companion_contracts": "companion_contracts",
            "known_limitations": "known_limitations",
            "package_reproducibility": "package_reproduction",
        }
        evidence_paths = set()
        for name, kind in expected_kinds.items():
            items = ledger["gates"][name]["evidence"]
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["kind"], kind)
            self.assertTrue(PACKAGE_RELEASE.valid_evidence(items[0]))
            report = ROOT / items[0]["locator"]
            self.assertEqual(
                hashlib.sha256(report.read_bytes()).hexdigest(),
                items[0]["sha256"],
            )
            evidence_paths.add(report)
        self.assertEqual(len(evidence_paths), 1)

        checkpoint = json.loads(evidence_paths.pop().read_text(encoding="utf-8"))
        for name in passed:
            self.assertTrue(checkpoint["prerelease_gates"][name])
        for name in (
            "approved",
            "released_hosts",
            "migration_safety",
            "live_visual_acceptance",
            "native_performance",
            "full_scene_performance",
            "signed_tag",
        ):
            self.assertFalse(checkpoint["prerelease_gates"][name])
        self.assertTrue(all(checkpoint["open_evidence"].values()))

        ci = checkpoint["kfp"]["ci"]
        self.assertEqual(
            checkpoint["kfp"]["commit"],
            "cfc045bec72c2ceecd558b24bcd643c8e0b720dc",
        )
        self.assertEqual(
            checkpoint["kfp"]["git_tree"],
            "7ef75f14ec471ed8e78dae68e438dda4063b0efd",
        )
        self.assertEqual(ci["run_id"], 32570167507)
        self.assertEqual(ci["conclusion"], "success")
        self.assertEqual(ci["job_count"], 11)
        self.assertEqual(
            ci["head_commit"],
            "cfc045bec72c2ceecd558b24bcd643c8e0b720dc",
        )
        self.assertEqual(
            {item["commit"] for item in ci["engine_pins"]},
            PACKAGE_RELEASE.PINNED_ENGINES,
        )
        self.assertEqual(ci["source_checks"]["lua_syntax"]["compiled"], 94)
        self.assertEqual(ci["source_checks"]["lua_tests"]["passed"], 301)
        self.assertEqual(ci["source_checks"]["python_tests"]["passed"], 46)
        self.assertEqual(ci["website"]["job_id"], 97024413545)
        self.assertEqual(ci["website"]["responsive_tests"]["passed"], 3)
        self.assertEqual(ci["package_reproduction"]["job_id"], 97024413501)
        self.assertEqual(
            ci["package_reproduction"]["result"], "byte-for-byte-pass"
        )
        self.assertFalse(ci["package_reproduction"]["publishable"])
        self.assertEqual(
            ci["packet_seal_stress"]["timing_claim"], "advisory-only"
        )
        compatibility = ci["luajit_hash_compatibility"]
        self.assertEqual(compatibility["result"], "pass")
        self.assertEqual(compatibility["selected_tests_per_runtime"], 26)
        self.assertFalse(compatibility["performance_claim"])
        self.assertEqual(
            {
                (
                    item["target"],
                    item["commit"],
                    item["jit_version"],
                    item["job_id"],
                )
                for item in compatibility["runtimes"]
            },
            {
                (
                    "gen1recomp-embedded",
                    "43d0a19158ceabaa51b0462c1ebc97612b420a2e",
                    "LuaJIT 2.1.1700008891",
                    97024413529,
                ),
                (
                    "current-ci",
                    "1ee778a4e37122d8ca7d5733c590a47dafd6b15c",
                    "LuaJIT 2.1.1787165859",
                    97024413561,
                ),
            },
        )

        for field in ("companion_api", "shared_fixture", "synthetic_scene_test"):
            item = checkpoint["kfp"][field]
            self.assertEqual(
                hashlib.sha256((ROOT / item["path"]).read_bytes()).hexdigest(),
                item["sha256"],
            )
        limitations = checkpoint["known_limitations"]
        self.assertEqual(
            hashlib.sha256((ROOT / limitations["path"]).read_bytes()).hexdigest(),
            limitations["sha256"],
        )

        source = checkpoint["source_integrity"]
        self.assertTrue(source["passed"])
        self.assertTrue(source["fresh_clone_clean"])
        self.assertTrue(source["remote_commit_exact"])
        self.assertEqual(source["tracked_file_count"], 197)
        self.assertEqual(
            source["tracked_path_list_sha256"],
            "ec59c52e054063908a0aaf61c240f1d1f582616bf2e5b536687d424a779fa09b",
        )
        self.assertEqual(source["unsafe_path_count"], 0)
        self.assertEqual(source["secret_finding_count"], 0)
        self.assertEqual(
            source["git_archive_sha256"],
            "9793a9aa5dab78ae79f44ea320e85f0430aa14efd8a2d07b3eed7da3e53b849a",
        )
        self.assertEqual(
            source["record"],
            {
                "kind": "source_integrity",
                "locator": (
                    "private-evidence://source-integrity/"
                    "2026-08-22-cfc045b/source-integrity.json"
                ),
                "sha256": (
                    "152fef45e4201951d95b1bbc9c6bdc08"
                    "d2f6be8f56355f8a4680dedbf016b95e"
                ),
            },
        )
        package = source["private_package_reproduction"]
        self.assertTrue(package["two_builds_byte_identical"])
        self.assertFalse(package["publishable"])
        self.assertEqual(package["runtime_file_count"], 76)
        self.assertEqual(
            package["runtime_content_sha256"],
            "534a6aa7af6d97985d34781031dc8bb27031bc3c93014482c8e4e49be21cb756",
        )
        self.assertEqual(
            package["zip_sha256"],
            "84b62b890a1eb6a86d2a1426b4f5b4afc0e150d8d71deaa0f3664c65696b81a4",
        )
        self.assertEqual(
            package["modpkg_sha256"],
            "dbe52f2d023a3a3fcd2fd4f0d553119e318af79966e0a74a9a1c590415d4b4c2",
        )
        self.assertEqual(
            ledger["gates"]["source_integrity"]["evidence"],
            [source["record"]],
        )

        hosts = {item["host"]: item for item in checkpoint["voxel_hosts"]}
        self.assertEqual(
            hosts["Battle Art"]["pr"]["head_commit"],
            "cee25fd117d881aa63ad7ef0bc7905ca0063fb29",
        )
        self.assertEqual(
            hosts["Dramaless"]["pr"]["head_commit"],
            "f7575445d00593b7db1ecd66f93e8c26989f4136",
        )
        self.assertTrue(all(item["released"] is False for item in hosts.values()))

        historical = (
            ROOT
            / "docs"
            / "release-evidence"
            / "alpha-readiness-2026-08-22-0683051.json"
        )
        self.assertEqual(
            hashlib.sha256(historical.read_bytes()).hexdigest(),
            "688cc40cfd3b6011f74b6a92611caf72765bdbc64fec139364099d0690ef4e6b",
        )
        historical_record = json.loads(historical.read_text(encoding="utf-8"))
        self.assertEqual(
            historical_record["kfp"]["commit"],
            "0683051a9ade567df8f5a5a73a2693646274e578",
        )


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

    def test_manifest_rejects_unsafe_artifact_components(self):
        self.assertEqual(
            PACKAGE_RELEASE.load_manifest_bytes(
                b'{"id":"ds_fp_ceiling","version":"2.0.0-alpha.1"}'
            )["version"],
            "2.0.0-alpha.1",
        )
        for field, value in (
            ("id", "../outside"),
            ("id", "C:\\outside"),
            ("version", "/absolute"),
            ("version", "2.0.0 beta"),
        ):
            manifest = {"id": "fixture", "version": "1.0.0"}
            manifest[field] = value
            with self.subTest(field=field, value=value):
                with self.assertRaisesRegex(
                    RuntimeError, "portable artifact component"
                ):
                    PACKAGE_RELEASE.validate_manifest(manifest)

        longest_suffix = max(
            PACKAGE_RELEASE.ARTIFACT_SUFFIXES,
            key=lambda value: len(value.encode("utf-16-le")),
        )
        max_stem_units = (
            PACKAGE_RELEASE.MAX_WINDOWS_COMPONENT_UNITS
            - len(longest_suffix.encode("utf-16-le")) // 2
        )
        safe_id = "i" * 128
        safe_version = "1" * (max_stem_units - len(safe_id) - 1)
        safe = {"id": safe_id, "version": safe_version}
        self.assertEqual(PACKAGE_RELEASE.validate_manifest(safe), safe)
        with self.assertRaisesRegex(RuntimeError, "overlong artifact name"):
            PACKAGE_RELEASE.validate_manifest(
                {"id": safe_id, "version": safe_version + "1"}
            )

    def test_runtime_package_paths_use_an_explicit_allowlist(self):
        self.assertTrue(PACKAGE_RELEASE.allowed_runtime_path("src/core/RNG.lua"))
        self.assertTrue(
            PACKAGE_RELEASE.allowed_runtime_path(
                "assets/legacy/horizons/backdrop.png"
            )
        )
        self.assertTrue(
            PACKAGE_RELEASE.allowed_runtime_path(
                "assets/legacy/horizons/backdrop-2048.png"
            )
        )
        self.assertTrue(
            PACKAGE_RELEASE.allowed_runtime_path(
                "assets/legacy/horizons/backdrop-1024.png"
            )
        )
        self.assertTrue(
            PACKAGE_RELEASE.allowed_runtime_path(
                "docs/legacy-panorama-inventory.json"
            )
        )
        self.assertTrue(
            PACKAGE_RELEASE.allowed_runtime_path("assets/legacy/sky/clouds-1.png")
        )
        self.assertTrue(
            PACKAGE_RELEASE.allowed_runtime_path("docs/legacy-sky-inventory.json")
        )
        self.assertFalse(
            PACKAGE_RELEASE.allowed_runtime_path("assets/roms/local.pem")
        )
        self.assertFalse(PACKAGE_RELEASE.allowed_runtime_path("src/private.env"))

    def test_repository_license_blob_is_exact_lf_content(self):
        value = PACKAGE_RELEASE.run_bytes(
            "git", "cat-file", "blob", "HEAD:LICENSE", cwd=ROOT
        )
        self.assertEqual(len(value), 1088)
        self.assertEqual(value.count(b"\n"), 21)
        self.assertEqual(value.count(b"\r"), 0)
        self.assertEqual(
            hashlib.sha256(value).hexdigest(),
            "8893010ccbca83da9f41be870c95d57fd97ad1e1e01e02c8ad4782125f3cfdf0",
        )

    def test_fixture_git_environment_rejects_all_inherited_configuration(self):
        with ScopedTestDirectory() as raw:
            root = Path(raw)
            inherited_hooks = root / "inherited-hooks"
            inherited_template = root / "inherited-template"
            inherited_template_hooks = inherited_template / "hooks"
            inherited_hooks.mkdir()
            inherited_template_hooks.mkdir(parents=True)

            hook_bytes = b"#!/bin/sh\nexit 97\n"
            for hook in (
                inherited_hooks / "pre-commit",
                inherited_template_hooks / "pre-commit",
            ):
                descriptor = os.open(
                    hook,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    0o700,
                )
                try:
                    os.write(descriptor, hook_bytes)
                finally:
                    os.close(descriptor)

            inherited_global = root / "inherited-global-config"
            inherited_global.write_text(
                "[core]\n"
                "\tsharedRepository = group\n"
                f"\thooksPath = {inherited_hooks.as_posix()}\n"
                "[init]\n"
                f"\ttemplateDir = {inherited_template.as_posix()}\n",
                encoding="utf-8",
            )
            inherited = {
                "GIT_CONFIG_GLOBAL": str(inherited_global),
                "GIT_CONFIG_NOSYSTEM": "0",
                "GIT_CONFIG_PARAMETERS": "malformed",
                "GIT_CONFIG_COUNT": "3",
                "GIT_CONFIG_KEY_0": "core.sharedRepository",
                "GIT_CONFIG_VALUE_0": "group",
                "GIT_CONFIG_KEY_1": "core.hooksPath",
                "GIT_CONFIG_VALUE_1": str(inherited_hooks),
                "GIT_CONFIG_KEY_2": "init.templateDir",
                "GIT_CONFIG_VALUE_2": str(inherited_template),
                "GIT_CONFIG_KEY_99": "core.sharedRepository",
                "GIT_CONFIG_VALUE_99": "group",
                "GIT_TEMPLATE_DIR": str(inherited_template),
            }
            with mock.patch.dict(os.environ, inherited, clear=False):
                repo, _, environment = create_minimal_runtime_repo(root)

            self.assertEqual(
                environment["GIT_CONFIG_GLOBAL"],
                str(root / "empty-git-global-config"),
            )
            self.assertEqual(
                Path(environment["GIT_CONFIG_GLOBAL"]).read_bytes(), b""
            )
            self.assertEqual(environment["GIT_CONFIG_NOSYSTEM"], "1")
            for name in inherited:
                if name not in ("GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM"):
                    self.assertNotIn(name, environment)

            configuration = run_git(
                repo,
                "config",
                "--show-origin",
                "--list",
                env=environment,
            ).lower()
            self.assertNotIn("sharedrepository=group", configuration)
            self.assertNotIn("core.hookspath", configuration)
            self.assertNotIn("init.templatedir", configuration)
            self.assertEqual(
                run_git(
                    repo,
                    "config",
                    "--local",
                    "--type=bool",
                    "--get",
                    "core.sharedRepository",
                    env=environment,
                ),
                "false",
            )
            self.assertFalse((repo / ".git" / "hooks" / "pre-commit").exists())

            (repo / "second.txt").write_text("synthetic\n", encoding="utf-8")
            run_git(repo, "add", "second.txt", env=environment)
            run_git(
                repo,
                "commit",
                "--quiet",
                "-m",
                "test(fixture): add second synthetic change",
                env=environment,
            )
            self.assertEqual(
                run_git(repo, "rev-list", "--count", "HEAD", env=environment),
                "2",
            )

    def test_clean_commit_copy_ignores_windows_crlf_checkout_conversion(self):
        with ScopedTestDirectory() as raw:
            root = Path(raw)
            repo, commit, environment = create_minimal_runtime_repo(root)
            run_git(repo, "config", "core.autocrlf", "true", env=environment)
            (repo / "LICENSE").unlink()
            run_git(repo, "checkout", "--", "LICENSE", env=environment)
            self.assertEqual(
                (repo / "LICENSE").read_bytes(), b"line one\r\nline two\r\n"
            )
            self.assertEqual(
                run_git(repo, "status", "--porcelain", env=environment), ""
            )
            staging = root / "staging"
            staging.mkdir()
            with minimal_runtime_constants():
                files = PACKAGE_RELEASE.copy_runtime_from_ref(
                    repo, commit, staging
                )
            self.assertEqual(
                files, ["LICENSE", "manifest.json", "src/Main.lua"]
            )
            self.assertEqual(
                (staging / "LICENSE").read_bytes(), b"line one\nline two\n"
            )

    def test_allow_dirty_copy_preserves_worktree_bytes_and_attests_dirty(self):
        with ScopedTestDirectory() as raw:
            root = Path(raw)
            repo, _, environment = create_minimal_runtime_repo(root)
            checkout = b"line one\r\nline two\r\n"
            run_git(repo, "config", "core.autocrlf", "true", env=environment)
            (repo / "LICENSE").unlink()
            run_git(repo, "checkout", "--", "LICENSE", env=environment)
            self.assertEqual((repo / "LICENSE").read_bytes(), checkout)
            self.assertEqual(
                run_git(repo, "status", "--porcelain", env=environment), ""
            )
            staging = root / "staging"
            staging.mkdir()
            with minimal_runtime_constants():
                PACKAGE_RELEASE.copy_runtime(repo, staging)
            self.assertEqual((staging / "LICENSE").read_bytes(), checkout)
            self.assertEqual(
                PACKAGE_RELEASE.select_source_mode(
                    release=False,
                    allow_dirty=True,
                    git_status_dirty=False,
                ),
                ("worktree", True),
            )

    def test_allow_dirty_manifest_rejects_link_or_reparse_path(self):
        with ScopedTestDirectory() as raw:
            root = Path(raw)
            (root / "manifest.json").write_bytes(
                b'{"id":"fixture","version":"1.0.0"}\n'
            )
            with mock.patch.object(
                PACKAGE_RELEASE, "path_has_link", return_value=True
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "required package file is missing"
                ):
                    PACKAGE_RELEASE.load_worktree_manifest(root)

    def test_source_mode_fails_closed_and_separates_release_content(self):
        self.assertEqual(
            PACKAGE_RELEASE.select_source_mode(
                release=False, allow_dirty=False, git_status_dirty=False
            ),
            ("git-commit", False),
        )
        self.assertEqual(
            PACKAGE_RELEASE.select_source_mode(
                release=True, allow_dirty=False, git_status_dirty=False
            ),
            ("signed-tag", False),
        )
        with self.assertRaisesRegex(RuntimeError, "cannot use --allow-dirty"):
            PACKAGE_RELEASE.select_source_mode(
                release=True, allow_dirty=True, git_status_dirty=False
            )
        with self.assertRaisesRegex(RuntimeError, "source tree is dirty"):
            PACKAGE_RELEASE.select_source_mode(
                release=False, allow_dirty=False, git_status_dirty=True
            )

    def test_tree_parser_rejects_duplicate_unsafe_and_symlink_paths(self):
        object_id = b"a" * 40
        with minimal_runtime_constants():
            duplicate = (
                b"100644 blob " + object_id + b"\tsrc/A.lua\0"
                b"100644 blob " + object_id + b"\tsrc/a.lua\0"
            )
            with self.assertRaisesRegex(RuntimeError, "duplicate package path"):
                PACKAGE_RELEASE.parse_tree_entries(duplicate)

            unsafe = b"100644 blob " + object_id + b"\tsrc/../bad.lua\0"
            with self.assertRaisesRegex(RuntimeError, "unsafe package path"):
                PACKAGE_RELEASE.parse_tree_entries(unsafe)

            reserved = b"100644 blob " + object_id + b"\tsrc/CON.lua\0"
            with self.assertRaisesRegex(RuntimeError, "unsafe package path"):
                PACKAGE_RELEASE.parse_tree_entries(reserved)

            symlink = b"120000 blob " + object_id + b"\tsrc/link.lua\0"
            with self.assertRaisesRegex(RuntimeError, "not a regular Git blob"):
                PACKAGE_RELEASE.parse_tree_entries(symlink)

            gitlink = b"160000 commit " + object_id + b"\tsrc/link.lua\0"
            with self.assertRaisesRegex(RuntimeError, "not a Git blob"):
                PACKAGE_RELEASE.parse_tree_entries(gitlink)

    def test_relative_paths_reject_all_nonportable_windows_forms(self):
        PACKAGE_RELEASE.validate_relative_path("src/valid-name.lua")
        invalid = (
            "/src/absolute.lua",
            "C:/src/drive.lua",
            "src\\backslash.lua",
            "src/../traversal.lua",
            "src/CON.lua",
            "src/CONIN$.lua",
            "src/conout$.txt.lua",
            "src/CON .lua",
            "src/COM1 .lua",
            "src/COM\N{SUPERSCRIPT ONE}.lua",
            "src/COM\N{SUPERSCRIPT TWO}.txt.lua",
            "src/COM\N{SUPERSCRIPT THREE}.lua",
            "src/LPT\N{SUPERSCRIPT ONE}.lua",
            "src/LPT\N{SUPERSCRIPT TWO}.txt.lua",
            "src/LPT\N{SUPERSCRIPT THREE}.lua",
            "src/trailing.",
            "src/trailing ",
            "src/.secret.lua",
            "src/.hidden/file.lua",
            "src/__pycache__/file.lua",
            "src/decomposed-e\u0301.lua",
            *(f"src/bad{character}name.lua" for character in '<>:"|?*'),
        )
        for relative in invalid:
            with self.subTest(relative=relative):
                with self.assertRaisesRegex(RuntimeError, "unsafe package path"):
                    PACKAGE_RELEASE.validate_relative_path(relative)

        PACKAGE_RELEASE.validate_relative_path(
            "src/" + "a" * 251 + ".lua"
        )
        for overlong in (
            "src/" + "a" * 252 + ".lua",
            "src/" + "\N{GRINNING FACE}" * 126 + ".lua",
        ):
            with self.assertRaisesRegex(RuntimeError, "unsafe package path"):
                PACKAGE_RELEASE.validate_relative_path(overlong)

    def test_modpkg_runtime_must_match_staging_paths_and_bytes(self):
        with ScopedTestDirectory() as raw:
            root = Path(raw)
            staging = root / "staging"
            staging.mkdir()
            (staging / "manifest.json").write_bytes(b"manifest\n")
            (staging / "main.lua").write_bytes(b"return true\n")
            files = ["manifest.json", "main.lua"]

            matching = root / "matching.modpkg"
            with zipfile.ZipFile(matching, "w") as archive:
                for relative in files:
                    archive.writestr(relative, (staging / relative).read_bytes())
                archive.writestr(".modkit/pack.json", b"{}\n")
            PACKAGE_RELEASE.verify_modpkg_runtime(matching, staging, files)

            missing = root / "missing.modpkg"
            with zipfile.ZipFile(missing, "w") as archive:
                archive.writestr("manifest.json", b"manifest\n")
                archive.writestr(".modkit/pack.json", b"{}\n")
            with self.assertRaisesRegex(RuntimeError, "path set differs"):
                PACKAGE_RELEASE.verify_modpkg_runtime(missing, staging, files)

            changed = root / "changed.modpkg"
            with zipfile.ZipFile(changed, "w") as archive:
                archive.writestr("manifest.json", b"changed\n")
                archive.writestr("main.lua", b"return true\n")
                archive.writestr(".modkit/pack.json", b"{}\n")
            with self.assertRaisesRegex(RuntimeError, "content differs"):
                PACKAGE_RELEASE.verify_modpkg_runtime(changed, staging, files)

            duplicate = root / "duplicate.modpkg"
            with zipfile.ZipFile(duplicate, "w") as archive:
                archive.writestr("manifest.json", b"manifest\n")
                with self.assertWarns(UserWarning):
                    archive.writestr("manifest.json", b"manifest\n")
                archive.writestr("main.lua", b"return true\n")
                archive.writestr(".modkit/pack.json", b"{}\n")
            with self.assertRaisesRegex(RuntimeError, "duplicate package paths"):
                PACKAGE_RELEASE.verify_modpkg_runtime(duplicate, staging, files)

    def test_worktree_copy_rejects_untracked_runtime_files(self):
        with ScopedTestDirectory() as raw:
            root = Path(raw)
            repo, _, _ = create_minimal_runtime_repo(root)
            (repo / "src" / "local.lua").write_bytes(b"return false\n")
            with minimal_runtime_constants():
                with self.assertRaisesRegex(
                    RuntimeError, "untracked runtime files are not packageable"
                ):
                    PACKAGE_RELEASE.listed_runtime_entries_from_worktree(repo)

    def test_worktree_copy_rejects_ignored_runtime_files(self):
        with ScopedTestDirectory() as raw:
            root = Path(raw)
            repo, _, environment = create_minimal_runtime_repo(root)
            (repo / "src" / "ignored.lua").write_bytes(b"return false\n")
            self.assertEqual(
                run_git(repo, "status", "--porcelain", env=environment), ""
            )
            with minimal_runtime_constants():
                with self.assertRaisesRegex(
                    RuntimeError, "untracked runtime files are not packageable"
                ):
                    PACKAGE_RELEASE.listed_runtime_entries_from_worktree(repo)

    def test_worktree_copy_rejects_missing_tracked_runtime_file(self):
        with ScopedTestDirectory() as raw:
            root = Path(raw)
            repo, _, _ = create_minimal_runtime_repo(root)
            (repo / "LICENSE").unlink()
            staging = root / "staging"
            staging.mkdir()
            with minimal_runtime_constants():
                with self.assertRaisesRegex(
                    RuntimeError, "required package file is missing: LICENSE"
                ):
                    PACKAGE_RELEASE.copy_runtime(repo, staging)

    def test_runtime_content_fingerprint_is_framed_and_order_independent(self):
        with ScopedTestDirectory() as raw:
            root = Path(raw)
            (root / "a.txt").write_bytes(b"alpha\n")
            (root / "b.txt").write_bytes(b"beta\n")
            first = PACKAGE_RELEASE.runtime_content_fingerprint(
                root, ["b.txt", "a.txt"]
            )
            second = PACKAGE_RELEASE.runtime_content_fingerprint(
                root, ["a.txt", "b.txt"]
            )
            self.assertEqual(first, second)
            self.assertEqual(
                first["algorithm"], "sha256-framed-path-content-v1"
            )
            self.assertEqual(first["file_count"], 2)
            self.assertRegex(first["sha256"], r"^[0-9a-f]{64}$")
            (root / "a.txt").write_bytes(b"changed\n")
            self.assertNotEqual(
                first["sha256"],
                PACKAGE_RELEASE.runtime_content_fingerprint(
                    root, ["a.txt", "b.txt"]
                )["sha256"],
            )

    def test_deterministic_zip_ignores_mtime_and_input_order(self):
        with ScopedTestDirectory() as raw:
            root = Path(raw)
            (root / "a.txt").write_bytes(b"alpha\n")
            (root / "b.txt").write_bytes(b"beta\n")
            first = root / "first.zip"
            second = root / "second.zip"
            PACKAGE_RELEASE.deterministic_zip(
                root, first, ["b.txt", "a.txt"]
            )
            os.utime(root / "a.txt", (1_500_000_000, 1_500_000_000))
            os.utime(root / "b.txt", (1_900_000_000, 1_900_000_000))
            PACKAGE_RELEASE.deterministic_zip(
                root, second, ["a.txt", "b.txt"]
            )
            self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_epoch_resolution_is_explicit_and_host_independent(self):
        environment = {
            "SOURCE_DATE_EPOCH": "1787270400",
            "TZ": "Pacific/Auckland",
        }
        self.assertEqual(
            PACKAGE_RELEASE.resolve_epoch(None, environment), 1787270400
        )
        self.assertEqual(
            PACKAGE_RELEASE.resolve_epoch(123, environment), 123
        )
        with self.assertRaisesRegex(RuntimeError, "set SOURCE_DATE_EPOCH"):
            PACKAGE_RELEASE.resolve_epoch(None, {})
        with self.assertRaisesRegex(RuntimeError, "must be an integer"):
            PACKAGE_RELEASE.resolve_epoch(
                None, {"SOURCE_DATE_EPOCH": "not-an-epoch"}
            )
        with self.assertRaisesRegex(RuntimeError, "nonnegative"):
            PACKAGE_RELEASE.resolve_epoch(-1, environment)

    def test_engine_tools_are_copied_from_the_pinned_commit(self):
        with ScopedTestDirectory() as raw:
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
