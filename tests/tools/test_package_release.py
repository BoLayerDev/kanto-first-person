import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
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
RUNTIME_SOURCE_COMMIT = "d" * 40
RUNTIME_SOURCE_TREE = "b" * 40
RUNTIME_CONTENT_SHA256 = "c" * 64
RUNTIME_FILE_COUNT = 42
ENGINE_COMMIT = sorted(PACKAGE_RELEASE.PINNED_ENGINES)[0]
SOURCE_DATE_EPOCH = 1787270400
PACKAGE_SHA256 = "e" * 64
TAG_COMMIT = "f" * 40
MATRIX_INPUT_SHA256 = "1" * 64
MATRIX_CELL_IDS_SHA256 = "2" * 64
MATRIX_ADAPTER_SHA256 = "3" * 64


def matrix_manifest(
    runtime_source_commit=RUNTIME_SOURCE_COMMIT,
    runtime_source_tree=RUNTIME_SOURCE_TREE,
    runtime_content_sha256=RUNTIME_CONTENT_SHA256,
    runtime_file_count=RUNTIME_FILE_COUNT,
    package_sha256=PACKAGE_SHA256,
    engine_commit=ENGINE_COMMIT,
    source_date_epoch=SOURCE_DATE_EPOCH,
):
    return {
        "schema": "kfp.release-matrix.manifest.v1",
        "schema_version": 1,
        "manifest_id": "kfp-alpha-release-matrix-v1",
        "created_at": "2026-08-23T12:00:00Z",
        "mode": "PRIVATE_RELEASE",
        "release_eligible": True,
        "candidate": {
            "runtime_source_commit": runtime_source_commit,
            "runtime_source_tree": runtime_source_tree,
            "runtime_content_sha256": runtime_content_sha256,
            "package_kind": "RELEASE_CANDIDATE",
            "package_sha256": package_sha256,
            "adapter_version": "1.0.0",
            "adapter_sha256": MATRIX_ADAPTER_SHA256,
        },
        "required_cell_set": {
            "schema": "kfp.release-matrix.required-cell-set.v1",
            "schema_version": 1,
            "manifest_input_sha256": MATRIX_INPUT_SHA256,
            "required_cell_count": PACKAGE_RELEASE.RELEASE_MATRIX_CELL_COUNT,
            "required_cell_ids_sha256": MATRIX_CELL_IDS_SHA256,
            "required_cells_by_game": dict(
                PACKAGE_RELEASE.RELEASE_MATRIX_GAME_CELL_COUNTS
            ),
        },
        "catalogs": {
            "engines": [
                {
                    "id": "selected-engine",
                    "source_commit": engine_commit,
                    "binding_kind": "PINNED_RUNTIME",
                }
            ]
        },
        "release_policy": {"cross_dimension_evidence": "REJECT"},
    }


def validate_matrix_fixture(value):
    if not isinstance(value, dict):
        raise RuntimeError("invalid fixture matrix")
    required = value.get("required_cell_set")
    if (
        not isinstance(required, dict)
        or required.get("manifest_input_sha256") != MATRIX_INPUT_SHA256
        or required.get("required_cell_ids_sha256") != MATRIX_CELL_IDS_SHA256
    ):
        raise RuntimeError("invalid fixture matrix binding")
    return json.loads(json.dumps(value))


def matrix_bytes(
    runtime_source_commit=RUNTIME_SOURCE_COMMIT,
    runtime_source_tree=RUNTIME_SOURCE_TREE,
    runtime_content_sha256=RUNTIME_CONTENT_SHA256,
    runtime_file_count=RUNTIME_FILE_COUNT,
    package_sha256=PACKAGE_SHA256,
    engine_commit=ENGINE_COMMIT,
    source_date_epoch=SOURCE_DATE_EPOCH,
):
    return (json.dumps(
        matrix_manifest(
            runtime_source_commit,
            runtime_source_tree,
            runtime_content_sha256,
            runtime_file_count,
            package_sha256,
            engine_commit,
            source_date_epoch,
        ),
        separators=(",", ":"),
        sort_keys=True,
    ) + "\n").encode()


def game_evidence(
    game,
    runtime_source_commit=RUNTIME_SOURCE_COMMIT,
    runtime_source_tree=RUNTIME_SOURCE_TREE,
    runtime_content_sha256=RUNTIME_CONTENT_SHA256,
    runtime_file_count=RUNTIME_FILE_COUNT,
    engine_commit=ENGINE_COMMIT,
    source_date_epoch=SOURCE_DATE_EPOCH,
    package_sha256=PACKAGE_SHA256,
):
    manifest_sha256 = hashlib.sha256(
        matrix_bytes(
            runtime_source_commit,
            runtime_source_tree,
            runtime_content_sha256,
            runtime_file_count,
            package_sha256,
            engine_commit,
            source_date_epoch,
        )
    ).hexdigest()
    result = {
        "schema": 1,
        "game": game,
        "status": "PASS",
        "release_ready": True,
        "required_cells": PACKAGE_RELEASE.RELEASE_MATRIX_GAME_CELL_COUNTS[game],
        "passed_cells": PACKAGE_RELEASE.RELEASE_MATRIX_GAME_CELL_COUNTS[game],
        "blockers": [],
        "runtime_source_commit": runtime_source_commit,
        "runtime_source_tree": runtime_source_tree,
        "runtime_content_sha256": runtime_content_sha256,
        "runtime_file_count": runtime_file_count,
        "engine_commit": engine_commit,
        "source_date_epoch": source_date_epoch,
        "package_sha256": package_sha256,
        "matrix_manifest_sha256": manifest_sha256,
    }
    return {
        "kind": "release_matrix_game_acceptance",
        "locator": PACKAGE_RELEASE.GAME_ACCEPTANCE_LOCATORS[game],
        "sha256": PACKAGE_RELEASE.game_result_sha256(result),
        "game": game,
        "result": result,
    }


def approved_records(
    version="2.0.0",
    channel="stable",
    runtime_source_commit=RUNTIME_SOURCE_COMMIT,
    runtime_source_tree=RUNTIME_SOURCE_TREE,
    runtime_content_sha256=RUNTIME_CONTENT_SHA256,
    runtime_file_count=RUNTIME_FILE_COUNT,
    engine_commit=ENGINE_COMMIT,
    source_date_epoch=SOURCE_DATE_EPOCH,
    package_sha256=PACKAGE_SHA256,
):
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
    gates = {}
    for name in required_gates:
        evidence = dict(EVIDENCE)
        if name in PACKAGE_RELEASE.GAME_ACCEPTANCE_GATES:
            evidence = game_evidence(
                PACKAGE_RELEASE.GAME_ACCEPTANCE_GATES[name],
                runtime_source_commit,
                runtime_source_tree,
                runtime_content_sha256,
                runtime_file_count,
                engine_commit,
                source_date_epoch,
                package_sha256,
            )
        gates[name] = {"passed": True, "evidence": [evidence]}
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


def game_documents(
    runtime_source_commit=RUNTIME_SOURCE_COMMIT,
    runtime_source_tree=RUNTIME_SOURCE_TREE,
    runtime_content_sha256=RUNTIME_CONTENT_SHA256,
    runtime_file_count=RUNTIME_FILE_COUNT,
    engine_commit=ENGINE_COMMIT,
    source_date_epoch=SOURCE_DATE_EPOCH,
    package_sha256=PACKAGE_SHA256,
):
    return {
        game: PACKAGE_RELEASE.game_result_bytes(
            game_evidence(
                game,
                runtime_source_commit,
                runtime_source_tree,
                runtime_content_sha256,
                runtime_file_count,
                engine_commit,
                source_date_epoch,
                package_sha256,
            )["result"]
        )
        for game in PACKAGE_RELEASE.GAME_ACCEPTANCE_GATES.values()
    }


def validate_records(
    rights,
    ledger,
    version,
    expected_tag,
    runtime_source_commit=RUNTIME_SOURCE_COMMIT,
    runtime_source_tree=RUNTIME_SOURCE_TREE,
    runtime_content_sha256=RUNTIME_CONTENT_SHA256,
    runtime_file_count=RUNTIME_FILE_COUNT,
    engine_commit=ENGINE_COMMIT,
    source_date_epoch=SOURCE_DATE_EPOCH,
    package_sha256=PACKAGE_SHA256,
    manifest=None,
    documents=None,
):
    with mock.patch.object(
        PACKAGE_RELEASE,
        "validate_release_matrix_manifest",
        side_effect=validate_matrix_fixture,
    ):
        return PACKAGE_RELEASE.validate_release_records(
            rights,
            ledger,
            version,
            expected_tag,
            expected_engine_commit=engine_commit,
            expected_epoch=source_date_epoch,
            game_documents=(
                game_documents(
                    runtime_source_commit,
                    runtime_source_tree,
                    runtime_content_sha256,
                    runtime_file_count,
                    engine_commit,
                    source_date_epoch,
                    package_sha256,
                )
                if documents is None
                else documents
            ),
            matrix_manifest_bytes=(
                matrix_bytes(
                    runtime_source_commit,
                    runtime_source_tree,
                    runtime_content_sha256,
                    runtime_file_count,
                    package_sha256,
                    engine_commit,
                    source_date_epoch,
                )
                if manifest is None
                else manifest
            ),
        )


def run_git(repo, *args):
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()


def create_minimal_runtime_repo(parent):
    repo = parent / "repo"
    repo.mkdir()
    run_git(repo, "init", "--quiet", "--initial-branch=fixture")
    run_git(repo, "config", "user.name", "Package Test")
    run_git(repo, "config", "user.email", "package-test@example.invalid")
    run_git(repo, "config", "core.autocrlf", "false")
    run_git(repo, "config", "core.eol", "lf")
    (repo / ".gitattributes").write_bytes(b"* text=auto\n")
    (repo / ".gitignore").write_bytes(b"src/ignored.lua\n")
    (repo / "manifest.json").write_bytes(
        b'{"id":"fixture","version":"1.0.0"}\n'
    )
    (repo / "LICENSE").write_bytes(b"line one\nline two\n")
    (repo / "src").mkdir()
    (repo / "src" / "Main.lua").write_bytes(b"return true\n")
    run_git(repo, "add", ".")
    run_git(
        repo,
        "commit",
        "--quiet",
        "-m",
        "test(fixture): create minimal runtime source",
    )
    return repo, run_git(repo, "rev-parse", "HEAD")


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
        open_gates = {
            "released_hosts",
            "migration_safety",
            *PACKAGE_RELEASE.GAME_ACCEPTANCE_GATES,
        }
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

    def test_every_public_channel_requires_separate_game_acceptance(self):
        expected = set(PACKAGE_RELEASE.GAME_ACCEPTANCE_GATES)
        self.assertEqual(len(expected), 3)
        self.assertTrue(expected.issubset(PACKAGE_RELEASE.REQUIRED_RELEASE_GATES))
        for channel, gates in PACKAGE_RELEASE.REQUIRED_PRERELEASE_GATES.items():
            with self.subTest(channel=channel):
                self.assertTrue(expected.issubset(gates))

    def test_release_rejects_cross_game_or_untyped_game_evidence(self):
        version = "2.0.0-alpha.1"
        for value in ("yellow", True, None):
            rights, ledger = approved_records(version, "alpha")
            ledger["gates"]["red_runtime_acceptance"]["evidence"][0]["game"] = value
            with self.subTest(game=value), self.assertRaisesRegex(
                RuntimeError,
                "invalid game acceptance evidence: red_runtime_acceptance",
            ):
                validate_records(
                    rights, ledger, version, "v" + version
                )

    def test_game_results_are_distinct_and_content_bound(self):
        rights, ledger = approved_records("2.0.0-alpha.1", "alpha")
        evidence = [
            ledger["gates"][name]["evidence"][0]
            for name in PACKAGE_RELEASE.GAME_ACCEPTANCE_GATES
        ]
        self.assertEqual(len({item["locator"] for item in evidence}), 3)
        self.assertEqual(len({item["sha256"] for item in evidence}), 3)
        validate_records(
            rights, ledger, "2.0.0-alpha.1", "v2.0.0-alpha.1"
        )

        yellow = json.loads(json.dumps(
            ledger["gates"]["yellow_runtime_acceptance"]["evidence"][0]
        ))
        yellow["game"] = "red"
        ledger["gates"]["red_runtime_acceptance"]["evidence"] = [yellow]
        with self.assertRaisesRegex(
            RuntimeError,
            "invalid game acceptance evidence: red_runtime_acceptance",
        ):
            validate_records(
                rights, ledger, "2.0.0-alpha.1", "v2.0.0-alpha.1"
            )

    def test_game_gate_rejects_duplicates_missing_documents_and_tampering(self):
        rights, ledger = approved_records()
        red_gate = ledger["gates"]["red_runtime_acceptance"]
        red_gate["evidence"].append(json.loads(json.dumps(red_gate["evidence"][0])))
        with self.assertRaisesRegex(
            RuntimeError,
            "invalid game acceptance evidence: red_runtime_acceptance",
        ):
            validate_records(rights, ledger, "2.0.0", "v2.0.0")

        rights, ledger = approved_records()
        documents = game_documents()
        documents.pop("blue")
        with self.assertRaisesRegex(
            RuntimeError,
            "invalid game acceptance evidence: blue_runtime_acceptance",
        ):
            validate_records(
                rights, ledger, "2.0.0", "v2.0.0", documents=documents
            )

        documents = game_documents()
        documents["yellow"] += b" "
        with self.assertRaisesRegex(
            RuntimeError,
            "invalid game acceptance evidence: yellow_runtime_acceptance",
        ):
            validate_records(
                rights, ledger, "2.0.0", "v2.0.0", documents=documents
            )

    def test_game_result_bindings_reject_recomputed_mismatches(self):
        mutations = (
            ("runtime_source_commit", "a" * 40),
            ("runtime_source_tree", "a" * 40),
            ("runtime_content_sha256", "a" * 64),
            ("runtime_file_count", 1),
            ("engine_commit", sorted(PACKAGE_RELEASE.PINNED_ENGINES)[1]),
            ("source_date_epoch", SOURCE_DATE_EPOCH + 1),
            ("package_sha256", "a" * 64),
            ("matrix_manifest_sha256", "a" * 64),
            ("required_cells", 1),
        )
        for field, value in mutations:
            rights, ledger = approved_records()
            item = ledger["gates"]["red_runtime_acceptance"]["evidence"][0]
            item["result"][field] = value
            if field == "required_cells":
                item["result"]["passed_cells"] = value
            item["sha256"] = PACKAGE_RELEASE.game_result_sha256(item["result"])
            documents = game_documents()
            documents["red"] = PACKAGE_RELEASE.game_result_bytes(item["result"])
            expected_error = (
                "game acceptance bindings disagree"
                if field == "runtime_file_count"
                else "invalid game acceptance evidence: red_runtime_acceptance"
            )
            with self.subTest(field=field), self.assertRaisesRegex(
                RuntimeError,
                expected_error,
            ):
                validate_records(
                    rights,
                    ledger,
                    "2.0.0",
                    "v2.0.0",
                    documents=documents,
                )

    def test_matrix_manifest_and_built_package_are_exact_bindings(self):
        rights, ledger = approved_records()
        altered = matrix_manifest()
        altered["release_eligible"] = False
        altered_bytes = (json.dumps(
            altered, separators=(",", ":"), sort_keys=True
        ) + "\n").encode()
        with self.assertRaisesRegex(
            RuntimeError,
            "invalid game acceptance evidence",
        ):
            validate_records(
                rights,
                ledger,
                "2.0.0",
                "v2.0.0",
                manifest=altered_bytes,
            )

        PACKAGE_RELEASE.verify_accepted_package(
            {"package_sha256": PACKAGE_SHA256}, PACKAGE_SHA256
        )
        with self.assertRaisesRegex(
            RuntimeError,
            "built package does not match accepted runtime package",
        ):
            PACKAGE_RELEASE.verify_accepted_package(
                {"package_sha256": PACKAGE_SHA256}, "a" * 64
            )

        accepted_runtime = {
            "runtime_content_sha256": RUNTIME_CONTENT_SHA256,
            "runtime_file_count": RUNTIME_FILE_COUNT,
        }
        runtime_content = {
            "algorithm": "sha256-framed-path-content-v1",
            "sha256": RUNTIME_CONTENT_SHA256,
            "file_count": RUNTIME_FILE_COUNT,
        }
        PACKAGE_RELEASE.verify_accepted_runtime(
            accepted_runtime, runtime_content
        )
        with self.assertRaisesRegex(
            RuntimeError,
            "tagged runtime content differs from accepted source",
        ):
            PACKAGE_RELEASE.verify_accepted_runtime(
                accepted_runtime,
                {**runtime_content, "sha256": "a" * 64},
            )

    def test_release_matrix_validator_dependency_fails_closed(self):
        unavailable = {
            "release_matrix": None,
            "release_matrix.model": None,
            "tools.release_matrix": None,
            "tools.release_matrix.model": None,
        }
        with mock.patch.dict(sys.modules, unavailable):
            with self.assertRaisesRegex(
                RuntimeError,
                "canonical release-matrix validator is unavailable",
            ):
                PACKAGE_RELEASE.validate_release_matrix_manifest(
                    matrix_manifest()
                )

    def test_release_matrix_validator_rejects_ambient_unqualified_package(self):
        ambient_package = types.ModuleType("release_matrix")
        ambient_package.__path__ = []
        ambient_model = types.ModuleType("release_matrix.model")
        ambient_calls = []

        class AmbientMatrixModelError(ValueError):
            pass

        def ambient_validate(value):
            ambient_calls.append(value)
            return value

        ambient_model.MatrixModelError = AmbientMatrixModelError
        ambient_model.validate_manifest = ambient_validate
        with mock.patch.dict(
            sys.modules,
            {
                "release_matrix": ambient_package,
                "release_matrix.model": ambient_model,
            },
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "canonical release-matrix validator is unavailable",
            ):
                PACKAGE_RELEASE.validate_release_matrix_manifest(
                    matrix_manifest()
                )
        self.assertEqual(ambient_calls, [])

    def test_matrix_rejects_fully_recomputed_incomplete_or_unknown_cell_sets(self):
        mutations = (
            (
                "one cell per game",
                lambda manifest: manifest["required_cell_set"].update({
                    "required_cell_count": 3,
                    "required_cells_by_game": {
                        "red": 1,
                        "blue": 1,
                        "yellow": 1,
                    },
                }),
            ),
            (
                "unknown manifest input",
                lambda manifest: manifest["required_cell_set"].update(
                    manifest_input_sha256="a" * 64
                ),
            ),
            (
                "unknown required cells",
                lambda manifest: manifest["required_cell_set"].update(
                    required_cell_ids_sha256="a" * 64
                ),
            ),
        )
        for label, mutate in mutations:
            manifest = matrix_manifest()
            mutate(manifest)
            manifest_bytes = (json.dumps(
                manifest, separators=(",", ":"), sort_keys=True
            ) + "\n").encode()
            manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
            rights, ledger = approved_records()
            documents = {}
            game_counts = manifest["required_cell_set"]["required_cells_by_game"]
            for gate, game in PACKAGE_RELEASE.GAME_ACCEPTANCE_GATES.items():
                item = ledger["gates"][gate]["evidence"][0]
                result = item["result"]
                result["required_cells"] = game_counts[game]
                result["passed_cells"] = game_counts[game]
                result["matrix_manifest_sha256"] = manifest_sha256
                item["sha256"] = PACKAGE_RELEASE.game_result_sha256(result)
                documents[game] = PACKAGE_RELEASE.game_result_bytes(result)
            with self.subTest(label=label), self.assertRaisesRegex(
                RuntimeError,
                "invalid game acceptance evidence",
            ):
                validate_records(
                    rights,
                    ledger,
                    "2.0.0",
                    "v2.0.0",
                    manifest=manifest_bytes,
                    documents=documents,
                )

        manifest = matrix_manifest()
        manifest["required_cell_set"]["required_cells_by_game"] = {
            game: float(count)
            for game, count in PACKAGE_RELEASE.RELEASE_MATRIX_GAME_CELL_COUNTS.items()
        }
        manifest_bytes = (json.dumps(
            manifest, separators=(",", ":"), sort_keys=True
        ) + "\n").encode()
        manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
        rights, ledger = approved_records()
        documents = {}
        for gate, game in PACKAGE_RELEASE.GAME_ACCEPTANCE_GATES.items():
            item = ledger["gates"][gate]["evidence"][0]
            item["result"]["matrix_manifest_sha256"] = manifest_sha256
            item["sha256"] = PACKAGE_RELEASE.game_result_sha256(item["result"])
            documents[game] = PACKAGE_RELEASE.game_result_bytes(item["result"])
        with self.assertRaisesRegex(
            RuntimeError,
            "invalid game acceptance evidence",
        ):
            validate_records(
                rights,
                ledger,
                "2.0.0",
                "v2.0.0",
                manifest=manifest_bytes,
                documents=documents,
            )

    def test_game_result_rejects_private_locator_and_stale_hash(self):
        rights, ledger = approved_records()
        red = ledger["gates"]["red_runtime_acceptance"]["evidence"][0]
        for mutation in (
            lambda item: item.update(locator=r"C:\Users\person\Pokemon ROMs\red.gb"),
            lambda item: item["result"].update(passed_cells=99),
            lambda item: item["result"].update(release_ready=1),
            lambda item: item["result"].update(schema=True),
        ):
            candidate = json.loads(json.dumps(red))
            mutation(candidate)
            ledger["gates"]["red_runtime_acceptance"]["evidence"] = [candidate]
            with self.assertRaisesRegex(
                RuntimeError,
                (
                    "(?:incomplete gates|invalid game acceptance evidence): "
                    "red_runtime_acceptance"
                ),
            ):
                validate_records(
                    rights, ledger, "2.0.0", "v2.0.0"
                )
        ledger["gates"]["red_runtime_acceptance"]["evidence"] = [red]

    def test_generic_evidence_locator_is_public_safe_and_fail_closed(self):
        safe = (
            "evidence://release/test-report",
            (
                "private-evidence://source-integrity/"
                "2026-08-22-cfc045b/source-integrity.json"
            ),
            "docs/release-evidence/alpha-readiness-2026-08-22.json",
            (
                "https://github.com/BoLayerDev/kanto-first-person/"
                "releases/tag/v2.0.0"
            ),
        )
        for locator in safe:
            with self.subTest(locator=locator):
                self.assertTrue(PACKAGE_RELEASE.valid_evidence_locator(locator))

        synthetic_windows_path = (
            "C:" + "\\Users\\person\\Pokemon ROMs\\red.gb"
        )
        unsafe = (
            synthetic_windows_path,
            "evidence://release/" + synthetic_windows_path,
            "/home/person/roms/red.gb",
            "private-evidence:///home/person/roms/red.gb",
            "private-evidence://runtime/roms/red.gb",
            "docs/release-evidence/cache/state.json",
            "docs/release-evidence/cache./state.json",
            "docs/release-evidence/red.sav",
            "docs/release-evidence/red.sav.",
            "docs/release-evidence/CON.json",
            "docs/release-evidence/report%2Ejson",
            "evidence://release/C%3A%2FUsers%2Fperson%2Fred.gb",
            "file:" + "///home/person/red.gb",
            "\\\\server\\share\\red.sav",
            "evidence://release/" + "password" + "=synthetic-value",
            "evidence://release/ghp_" + "A" * 24,
            "evidence://release/github_pat_" + "A" * 24,
            "evidence://release/sk-" + "A" * 24,
            "evidence://release/AKIA" + "A" * 16,
            "evidence://release/-----BEGIN-PRIVATE-KEY-----",
            "https://user:" + "synthetic@example.com/report.json",
            " https://example.com/report.json",
            "https://example.com/report.json ",
            "https://example.com:/report.json",
            "https://example.com/report.json?",
            "https://example.com/report.json#",
            True,
            None,
        )
        for locator in unsafe:
            with self.subTest(locator=locator):
                self.assertFalse(PACKAGE_RELEASE.valid_evidence_locator(locator))

        rights, ledger = approved_records("2.0.0-alpha.1", "alpha")
        ledger["gates"]["migration_safety"]["evidence"][0][
            "locator"
        ] = synthetic_windows_path
        with self.assertRaisesRegex(
            RuntimeError,
            "incomplete gates: migration_safety",
        ):
            validate_records(
                rights, ledger, "2.0.0-alpha.1", "v2.0.0-alpha.1"
            )

    def test_release_approval_timestamp_is_a_real_utc_instant(self):
        self.assertTrue(
            PACKAGE_RELEASE.valid_utc_timestamp("2024-02-29T23:59:59Z")
        )
        invalid = (
            "2026-99-99T99:99:99Z",
            "2026-02-29T00:00:00Z",
            "2026-01-01T24:00:00Z",
            "2026-01-01T23:59:60Z",
            "2026-01-01T00:00:00+00:00",
            True,
            None,
        )
        for timestamp in invalid:
            with self.subTest(timestamp=timestamp):
                self.assertFalse(PACKAGE_RELEASE.valid_utc_timestamp(timestamp))

        rights, ledger = approved_records()
        ledger["approved_at"] = "2026-99-99T99:99:99Z"
        with self.assertRaisesRegex(
            RuntimeError,
            "gate approval timestamp is invalid",
        ):
            validate_records(rights, ledger, "2.0.0", "v2.0.0")

    def test_release_records_reject_boolean_schema_versions(self):
        rights, ledger = approved_records()
        rights["schema"] = True
        with self.assertRaisesRegex(RuntimeError, "rights approval schema"):
            validate_records(
                rights, ledger, "2.0.0", "v2.0.0"
            )

        rights, ledger = approved_records()
        ledger["schema"] = True
        with self.assertRaisesRegex(RuntimeError, "gate ledger schema"):
            validate_records(
                rights, ledger, "2.0.0", "v2.0.0"
            )

    def test_release_rejects_generic_evidence_for_a_game_gate(self):
        rights, ledger = approved_records()
        ledger["gates"]["blue_runtime_acceptance"]["evidence"] = [dict(EVIDENCE)]
        with self.assertRaisesRegex(
            RuntimeError,
            "incomplete gates: blue_runtime_acceptance",
        ):
            validate_records(
                rights, ledger, "2.0.0", "v2.0.0"
            )

    def test_approval_schema_rejects_weak_hashes_and_evidence(self):
        rights, ledger = approved_records()
        rights["evidence_sha256"] = "A" * 64
        with self.assertRaisesRegex(RuntimeError, "rights evidence hash"):
            validate_records(
                rights, ledger, "2.0.0", "v2.0.0"
            )

        rights, ledger = approved_records()
        ledger["gates"][PACKAGE_RELEASE.REQUIRED_RELEASE_GATES[0]]["evidence"] = [
            None
        ]
        with self.assertRaisesRegex(RuntimeError, "incomplete gates"):
            validate_records(
                rights, ledger, "2.0.0", "v2.0.0"
            )

    def test_complete_signed_tag_approval_uses_tagged_records(self):
        commit = TAG_COMMIT
        rights, ledger = approved_records()
        documents = game_documents()
        manifest = matrix_bytes()

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
            if command == ("rev-parse", f"{RUNTIME_SOURCE_COMMIT}^{{tree}}"):
                return RUNTIME_SOURCE_TREE
            if command == (
                "merge-base", "--is-ancestor", RUNTIME_SOURCE_COMMIT, commit
            ):
                return ""
            raise AssertionError(command)

        def fake_run_bytes(*args, cwd):
            target = args[-1]
            if target.endswith("rights-approval.json"):
                return json.dumps(rights, sort_keys=True).encode()
            if target.endswith("release-gates.json"):
                return json.dumps(ledger, sort_keys=True).encode()
            if target.endswith("docs/release-matrix/matrix-v1.json"):
                return manifest
            for game, locator in PACKAGE_RELEASE.GAME_ACCEPTANCE_LOCATORS.items():
                if target.endswith(locator):
                    return documents[game]
            raise AssertionError(target)

        accepted_runtime = {
            "algorithm": "sha256-framed-path-content-v1",
            "sha256": RUNTIME_CONTENT_SHA256,
            "file_count": RUNTIME_FILE_COUNT,
        }
        with mock.patch.object(PACKAGE_RELEASE, "run", side_effect=fake_run), \
                mock.patch.object(
                    PACKAGE_RELEASE, "run_bytes", side_effect=fake_run_bytes
                ), mock.patch.object(
                    PACKAGE_RELEASE,
                    "runtime_content_fingerprint_from_ref",
                    return_value=accepted_runtime,
                ), mock.patch.object(
                    PACKAGE_RELEASE,
                    "validate_release_matrix_manifest",
                    side_effect=validate_matrix_fixture,
                ):
            approval = PACKAGE_RELEASE.require_release_approval(
                Path("signed-source"), "2.0.0", commit, FINGERPRINT,
                ENGINE_COMMIT, SOURCE_DATE_EPOCH,
            )
        self.assertEqual(approval["tag_commit"], commit)
        self.assertEqual(approval["signing_key_fingerprint"], FINGERPRINT)

    def test_complete_signed_alpha_uses_tagged_prerelease_ledger(self):
        version = "2.0.0-alpha.1"
        commit = "e" * 40
        rights, ledger = approved_records(version, "alpha")
        documents = game_documents()
        manifest = matrix_bytes()

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
            if command == ("rev-parse", f"{RUNTIME_SOURCE_COMMIT}^{{tree}}"):
                return RUNTIME_SOURCE_TREE
            if command == (
                "merge-base", "--is-ancestor", RUNTIME_SOURCE_COMMIT, commit
            ):
                return ""
            raise AssertionError(command)

        def fake_run_bytes(*args, cwd):
            target = args[-1]
            if target.endswith("rights-approval.json"):
                return json.dumps(rights, sort_keys=True).encode()
            if target.endswith("prerelease-gates.json"):
                return json.dumps(ledger, sort_keys=True).encode()
            if target.endswith("docs/release-matrix/matrix-v1.json"):
                return manifest
            for game, locator in PACKAGE_RELEASE.GAME_ACCEPTANCE_LOCATORS.items():
                if target.endswith(locator):
                    return documents[game]
            raise AssertionError(target)

        accepted_runtime = {
            "algorithm": "sha256-framed-path-content-v1",
            "sha256": RUNTIME_CONTENT_SHA256,
            "file_count": RUNTIME_FILE_COUNT,
        }
        with mock.patch.object(PACKAGE_RELEASE, "run", side_effect=fake_run), \
                mock.patch.object(
                    PACKAGE_RELEASE, "run_bytes", side_effect=fake_run_bytes
                ), mock.patch.object(
                    PACKAGE_RELEASE,
                    "runtime_content_fingerprint_from_ref",
                    return_value=accepted_runtime,
                ), mock.patch.object(
                    PACKAGE_RELEASE,
                    "validate_release_matrix_manifest",
                    side_effect=validate_matrix_fixture,
                ):
            approval = PACKAGE_RELEASE.require_release_approval(
                Path("signed-source"), version, commit, FINGERPRINT,
                ENGINE_COMMIT, SOURCE_DATE_EPOCH,
            )
        self.assertEqual(approval["channel"], "alpha")
        self.assertEqual(approval["tag"], "v" + version)

    def test_release_needs_an_external_trusted_signer(self):
        with self.assertRaisesRegex(RuntimeError, "trusted signing-key"):
            PACKAGE_RELEASE.require_release_approval(
                Path("source"), "2.0.0", TAG_COMMIT, None,
                ENGINE_COMMIT, SOURCE_DATE_EPOCH,
            )

    def test_strict_json_rejects_duplicate_keys(self):
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            PACKAGE_RELEASE.strict_json_loads('{"permissions":[],"permissions":["filesystem"]}')
        for constant in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(constant=constant), self.assertRaisesRegex(
                ValueError,
                "non-standard JSON constant",
            ):
                PACKAGE_RELEASE.strict_json_loads(
                    '{"release_eligible":true,"extra":' + constant + "}"
                )

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

    def test_clean_commit_copy_ignores_windows_crlf_checkout_conversion(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            repo, commit = create_minimal_runtime_repo(root)
            run_git(repo, "config", "core.autocrlf", "true")
            (repo / "LICENSE").unlink()
            run_git(repo, "checkout", "--", "LICENSE")
            self.assertEqual(
                (repo / "LICENSE").read_bytes(), b"line one\r\nline two\r\n"
            )
            self.assertEqual(run_git(repo, "status", "--porcelain"), "")
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
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            repo, _ = create_minimal_runtime_repo(root)
            checkout = b"line one\r\nline two\r\n"
            run_git(repo, "config", "core.autocrlf", "true")
            (repo / "LICENSE").unlink()
            run_git(repo, "checkout", "--", "LICENSE")
            self.assertEqual((repo / "LICENSE").read_bytes(), checkout)
            self.assertEqual(run_git(repo, "status", "--porcelain"), "")
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
        with tempfile.TemporaryDirectory() as raw:
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
        with tempfile.TemporaryDirectory() as raw:
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
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            repo, _ = create_minimal_runtime_repo(root)
            (repo / "src" / "local.lua").write_bytes(b"return false\n")
            with minimal_runtime_constants():
                with self.assertRaisesRegex(
                    RuntimeError, "untracked runtime files are not packageable"
                ):
                    PACKAGE_RELEASE.listed_runtime_entries_from_worktree(repo)

    def test_worktree_copy_rejects_ignored_runtime_files(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            repo, _ = create_minimal_runtime_repo(root)
            (repo / "src" / "ignored.lua").write_bytes(b"return false\n")
            self.assertEqual(run_git(repo, "status", "--porcelain"), "")
            with minimal_runtime_constants():
                with self.assertRaisesRegex(
                    RuntimeError, "untracked runtime files are not packageable"
                ):
                    PACKAGE_RELEASE.listed_runtime_entries_from_worktree(repo)

    def test_worktree_copy_rejects_missing_tracked_runtime_file(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            repo, _ = create_minimal_runtime_repo(root)
            (repo / "LICENSE").unlink()
            staging = root / "staging"
            staging.mkdir()
            with minimal_runtime_constants():
                with self.assertRaisesRegex(
                    RuntimeError, "required package file is missing: LICENSE"
                ):
                    PACKAGE_RELEASE.copy_runtime(repo, staging)

    def test_runtime_content_fingerprint_is_framed_and_order_independent(self):
        with tempfile.TemporaryDirectory() as raw:
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

    def test_frozen_git_ref_fingerprint_matches_its_exact_runtime_blobs(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            repo, commit = create_minimal_runtime_repo(root)
            staging = root / "staging"
            staging.mkdir()
            with minimal_runtime_constants():
                files = PACKAGE_RELEASE.copy_runtime_from_ref(
                    repo, commit, staging
                )
                expected = PACKAGE_RELEASE.runtime_content_fingerprint(
                    staging, files
                )
                actual = PACKAGE_RELEASE.runtime_content_fingerprint_from_ref(
                    repo, commit
                )
                self.assertEqual(actual, expected)

                (repo / "src" / "Main.lua").write_bytes(b"return false\n")
                run_git(repo, "add", "src/Main.lua")
                run_git(
                    repo,
                    "commit",
                    "--quiet",
                    "-m",
                    "test(fixture): change runtime",
                )
                changed = PACKAGE_RELEASE.runtime_content_fingerprint_from_ref(
                    repo, run_git(repo, "rev-parse", "HEAD")
                )
                self.assertNotEqual(changed["sha256"], expected["sha256"])

    def test_deterministic_zip_ignores_mtime_and_input_order(self):
        with tempfile.TemporaryDirectory() as raw:
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
