import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import unittest
from unittest import mock

from tests.tools._scoped_test_directory import ScopedTestDirectory
from tools.release_matrix import ledger
from tools.release_matrix import model


ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = ROOT / "docs" / "release-matrix" / "matrix-v1.json"
SCHEMA_PATHS = (
    ROOT / "docs" / "release-matrix" / "manifest-v1.schema.json",
    ROOT / "docs" / "release-matrix" / "cell-result-v1.schema.json",
    ROOT / "docs" / "release-matrix" / "ledger-event-v1.schema.json",
    ROOT / "docs" / "release-matrix" / "manual-verdict-v1.schema.json",
    ROOT / "docs" / "release-matrix" / "public-status-v1.schema.json",
)


def fresh_manifest():
    return json.loads(MATRIX_PATH.read_text(encoding="utf-8"))


def evidence_for(cell, attempt_id):
    gate_id = cell.identity["required_gate_ids"][0]
    return [
        model.make_evidence_binding(
            cell,
            attempt_id,
            gate_id,
            kind,
            "b" * 64 if kind == "manual-verdict" else "a" * 64,
            index + 1,
        )
        for index, kind in enumerate(cell.identity["required_evidence_kinds"])
    ]


def passing_result(cell, attempt_id):
    manual = None
    if cell.identity["test_execution"] == "MANUAL":
        manual = "b" * 64
    return {
        "schema": model.CELL_RESULT_SCHEMA,
        "schema_version": 1,
        "cell_id": cell.cell_id,
        "input_fingerprint": cell.input_fingerprint,
        "attempt_id": attempt_id,
        "started_at": "2026-08-23T12:00:00Z",
        "finished_at": "2026-08-23T12:00:01Z",
        "status": "PASS",
        "cleanup": "PASS",
        "objective": cell.identity["test_execution"] == "OBJECTIVE",
        "evidence": evidence_for(cell, attempt_id),
        "manual_verdict_sha256": manual,
        "failure_code": None,
    }


def private_release_manifest():
    manifest = fresh_manifest()
    manifest["mode"] = "PRIVATE_RELEASE"
    manifest["release_eligible"] = True
    manifest["candidate"]["package_kind"] = "RELEASE_CANDIDATE"

    def acquire(container, key, path):
        container[key] = model.sha256_value(
            {
                "schema": "kfp.release-matrix.test-private-binding.v1",
                "path": path,
                "public_sha256": container[key],
            }
        )

    for name in (
        "runtime_content_sha256",
        "package_sha256",
        "adapter_sha256",
    ):
        acquire(manifest["candidate"], name, f"candidate.{name}")
    for game in manifest["catalogs"]["games"]:
        acquire(
            game,
            "adapter_sha256",
            f"catalogs.games.{game['id']}.adapter_sha256",
        )
    for engine in manifest["catalogs"]["engines"]:
        engine["binding_kind"] = "PINNED_RUNTIME"
        acquire(
            engine,
            "runtime_sha256",
            f"catalogs.engines.{engine['id']}.runtime_sha256",
        )
    for platform in manifest["catalogs"]["platforms"]:
        acquire(
            platform,
            "adapter_sha256",
            f"catalogs.platforms.{platform['id']}.adapter_sha256",
        )
    for host_mode in manifest["catalogs"]["host_modes"]:
        acquire(
            host_mode,
            "fixture_sha256",
            f"catalogs.host_modes.{host_mode['id']}.fixture_sha256",
        )
    for point in manifest["catalogs"]["test_points"]:
        for binding in point["required_input_hashes"]:
            acquire(
                binding,
                "sha256",
                "catalogs.test_points."
                f"{point['id']}.{binding['id']}.sha256",
            )
    acquisition_record_sha256 = model.sha256_value(
        {
            "schema": model.PRIVATE_BINDING_ACQUISITION_SCHEMA,
            "schema_version": 1,
            "source": "public-synthetic-test-fixture-only",
        }
    )
    manifest["binding_acquisition"] = model.derive_binding_acquisition(
        manifest,
        state="ACQUIRED_PRIVATE",
        acquisition_record_sha256=acquisition_record_sha256,
    )
    manifest["required_cell_set"] = model.derive_required_cell_set(manifest)
    return model.validate_manifest(manifest)


def relabeled_public_private_manifest():
    """Build the exact unsafe mode-only relabel used by adversarial tests."""

    manifest = fresh_manifest()
    manifest["mode"] = "PRIVATE_RELEASE"
    manifest["release_eligible"] = True
    manifest["candidate"]["package_kind"] = "RELEASE_CANDIDATE"
    for engine in manifest["catalogs"]["engines"]:
        engine["binding_kind"] = "PINNED_RUNTIME"
    manifest["binding_acquisition"].update(
        state="ACQUIRED_PRIVATE",
        acquisition_record_schema=model.PRIVATE_BINDING_ACQUISITION_SCHEMA,
        acquisition_record_sha256="f" * 64,
    )
    manifest["required_cell_set"] = model._derive_required_cell_set(manifest)
    return manifest


def public_status(manifest, result_set):
    contract = manifest["required_cell_set"]
    counts = dict(result_set.status_counts)
    passed_by_game = dict(result_set.passed_cells_by_game)
    ready = (
        manifest["release_eligible"]
        and result_set.validated_result_count == contract["required_cell_count"]
        and counts["PASS"] == contract["required_cell_count"]
        and all(counts[state] == 0 for state in model.BLOCKING_CELL_STATUSES)
    )
    return {
        "schema": model.PUBLIC_STATUS_SCHEMA,
        "schema_version": 1,
        "generated_at": "2026-08-23T12:00:00Z",
        "manifest_id": manifest["manifest_id"],
        "manifest_sha256": model.sha256_value(manifest),
        "manifest_input_sha256": contract["manifest_input_sha256"],
        "required_cell_ids_sha256": contract["required_cell_ids_sha256"],
        "source_commit": manifest["candidate"]["runtime_source_commit"],
        "package_sha256": manifest["candidate"]["package_sha256"],
        "ledger_snapshot_sha256": result_set.ledger_snapshot_sha256,
        "validated_result_set_sha256": result_set.validated_result_set_sha256,
        "validated_result_count": result_set.validated_result_count,
        "release_eligible": manifest["release_eligible"],
        "readiness": "READY" if ready else "NOT_READY",
        "release": "NOT_RELEASED",
        "required_cells": contract["required_cell_count"],
        "status_counts": counts,
        "games": [
            {
                "id": game_id,
                "status": (
                    "PASS"
                    if passed_by_game[game_id]
                    == contract["required_cells_by_game"][game_id]
                    else "BLOCKED"
                ),
                "required_cells": contract["required_cells_by_game"][game_id],
                "passed_cells": passed_by_game[game_id],
            }
            for game_id in model.GAME_IDS
        ],
        "blockers": [] if ready else ["incomplete-result-set"],
    }


class MatrixModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = model.load_manifest(MATRIX_PATH)
        cls.cells = model.expand_cells(cls.manifest)
        cls.objective_cell = next(
            cell
            for cell in cls.cells
            if cell.identity["test_execution"] == "OBJECTIVE"
            and cell.identity["game"]["id"] == "red"
        )
        cls.manual_cell = next(
            cell for cell in cls.cells if cell.identity["test_execution"] == "MANUAL"
        )

    def test_reference_manifest_is_fail_closed_and_complete(self):
        self.assertEqual(self.manifest["mode"], "PUBLIC_SYNTHETIC")
        self.assertFalse(self.manifest["release_eligible"])
        self.assertEqual(
            tuple(game["id"] for game in self.manifest["catalogs"]["games"]),
            model.GAME_IDS,
        )
        self.assertEqual(
            tuple(engine["id"] for engine in self.manifest["catalogs"]["engines"]),
            model.ENGINE_IDS,
        )
        self.assertEqual(
            tuple(platform["id"] for platform in self.manifest["catalogs"]["platforms"]),
            model.PLATFORM_IDS,
        )
        self.assertEqual(
            tuple(item["id"] for item in self.manifest["catalogs"]["test_classes"]),
            model.TEST_CLASS_IDS,
        )
        self.assertEqual(
            tuple(item["id"] for item in self.manifest["catalogs"]["test_points"]),
            model.TEST_POINT_IDS,
        )
        self.assertEqual(
            {
                kind
                for item in self.manifest["catalogs"]["test_classes"]
                for kind in item["evidence_kinds"]
            },
            set(model.EVIDENCE_KIND_IDS),
        )
        self.assertEqual(
            self.manifest["release_policy"]["non_pass_states_block_release"],
            list(model.BLOCKING_CELL_STATUSES),
        )

    def test_only_released_eligible_host_expands(self):
        hosts = self.manifest["catalogs"]["hosts"]
        self.assertEqual(
            [(host["id"], host["released"], host["eligible"]) for host in hosts],
            [
                ("battle-art-1.9.8", True, True),
                ("dramaless-v2.0.3", True, False),
            ],
        )
        self.assertEqual(
            {cell.identity["host"]["id"] for cell in self.cells},
            {"battle-art-1.9.8"},
        )

    def test_expansion_is_deterministic_unique_and_full(self):
        self.assertEqual(len(self.cells), 17820)
        self.assertEqual(len({cell.cell_id for cell in self.cells}), len(self.cells))
        self.assertEqual(
            [cell.cell_id for cell in self.cells],
            [cell.cell_id for cell in model.expand_cells(fresh_manifest())],
        )
        self.assertEqual(
            {cell.identity["game"]["id"] for cell in self.cells}, set(model.GAME_IDS)
        )
        self.assertEqual(
            {cell.identity["tier"] for cell in self.cells}, set(model.TIER_IDS)
        )
        self.assertEqual(
            {cell.identity["platform"]["id"] for cell in self.cells},
            set(model.PLATFORM_IDS),
        )
        self.assertEqual(
            {cell.identity["engine"]["id"] for cell in self.cells},
            set(model.ENGINE_IDS),
        )
        self.assertEqual(
            {cell.identity["test_class"] for cell in self.cells},
            set(model.TEST_CLASS_IDS),
        )
        mode_bindings = {
            (cell.identity["host_mode"]["id"], cell.identity["host_mode"]["fixture_sha256"])
            for cell in self.cells
        }
        self.assertEqual(
            {mode for mode, _ in mode_bindings}, set(model.HOST_MODE_IDS)
        )
        self.assertEqual(len({digest for _, digest in mode_bindings}), 4)

    def test_cross_game_identity_cannot_transfer(self):
        reference = self.cells[0]
        blue = next(
            cell
            for cell in self.cells
            if cell.identity["game"]["id"] == "blue"
            and cell.identity["host"] == reference.identity["host"]
            and cell.identity["engine"] == reference.identity["engine"]
            and cell.identity["tier"] == reference.identity["tier"]
            and cell.identity["platform"] == reference.identity["platform"]
            and cell.identity["host_mode"] == reference.identity["host_mode"]
            and cell.identity["test_class"] == reference.identity["test_class"]
            and cell.identity["test_point"] == reference.identity["test_point"]
        )
        self.assertNotEqual(reference.cell_id, blue.cell_id)
        self.assertNotEqual(reference.input_fingerprint, blue.input_fingerprint)

    def test_every_cell_dimension_is_bound_into_result_identity(self):
        cell = self.objective_cell
        attempt_id = model.make_attempt_id(
            cell, 1, "2026-08-23T12:00:00Z", "matrix-test-owner"
        )
        mutations = {
            "game": lambda identity: identity["game"].update(
                id="blue", adapter_id="blue-opaque-v1", adapter_sha256="1" * 64
            ),
            "source": lambda identity: identity.update(
                runtime_source_commit="0" * 40
            ),
            "package": lambda identity: identity.update(package_sha256="0" * 64),
            "engine": lambda identity: identity["engine"].update(
                runtime_sha256="0" * 64
            ),
            "host": lambda identity: identity["host"].update(
                package_sha256="0" * 64
            ),
            "platform": lambda identity: identity["platform"].update(
                adapter_sha256="0" * 64
            ),
        }
        for dimension, mutate in mutations.items():
            identity = copy.deepcopy(dict(cell.identity))
            mutate(identity)
            fingerprint = model.sha256_value(identity)
            forged = model.MatrixCell(
                cell_id=f"cell-{fingerprint}",
                input_fingerprint=fingerprint,
                identity=identity,
            )
            changed = passing_result(cell, attempt_id)
            changed["cell_id"] = forged.cell_id
            changed["input_fingerprint"] = forged.input_fingerprint
            with self.subTest(dimension=dimension):
                with self.assertRaisesRegex(
                    model.MatrixModelError, "E_CELL_BINDING"
                ):
                    model.validate_cell_result(changed, cell)

    def test_manifest_object_key_order_does_not_change_identity(self):
        reordered = fresh_manifest()
        reordered = dict(reversed(list(reordered.items())))
        self.assertEqual(
            [cell.cell_id for cell in model.expand_cells(reordered)],
            [cell.cell_id for cell in self.cells],
        )

    def test_catalog_reorder_duplicate_and_unknown_are_rejected(self):
        changed = fresh_manifest()
        changed["catalogs"]["games"].reverse()
        with self.assertRaisesRegex(model.MatrixModelError, "E_CATALOG_IDENTITY"):
            model.validate_manifest(changed)

        changed = fresh_manifest()
        changed["catalogs"]["games"][1]["id"] = "red"
        with self.assertRaisesRegex(model.MatrixModelError, "E_DUPLICATE_ID"):
            model.validate_manifest(changed)

        changed = fresh_manifest()
        changed["catalogs"]["test_points"].append(
            copy.deepcopy(changed["catalogs"]["test_points"][0])
        )
        with self.assertRaisesRegex(model.MatrixModelError, "E_DUPLICATE_ID"):
            model.validate_manifest(changed)

        changed = fresh_manifest()
        changed["catalogs"]["test_points"][1]["id"] = changed["catalogs"][
            "test_points"
        ][0]["id"]
        with self.assertRaisesRegex(model.MatrixModelError, "E_DUPLICATE_ID"):
            model.validate_manifest(changed)

        changed = fresh_manifest()
        changed["catalogs"]["test_points"][0]["label"] = "Different label"
        with self.assertRaisesRegex(model.MatrixModelError, "E_TEST_POINT_BINDING"):
            model.validate_manifest(changed)

        changed = fresh_manifest()
        changed["catalogs"]["test_points"][0]["required_input_hashes"][0][
            "id"
        ] = "different-binding"
        with self.assertRaisesRegex(model.MatrixModelError, "E_CATALOG_IDENTITY"):
            model.validate_manifest(changed)

        changed = fresh_manifest()
        changed["catalogs"]["test_classes"][0]["evidence_kinds"] = [
            "unknown-report"
        ]
        with self.assertRaisesRegex(model.MatrixModelError, "E_REFERENCE"):
            model.validate_manifest(changed)

        changed = fresh_manifest()
        changed["unexpected"] = "field"
        with self.assertRaisesRegex(model.MatrixModelError, "E_UNKNOWN_FIELD"):
            model.validate_manifest(changed)

    def test_boolean_number_confusion_is_rejected(self):
        mutations = (
            lambda value: value.update(schema_version=True),
            lambda value: value.update(release_eligible=0),
            lambda value: value["catalogs"]["platforms"][0].update(claimed=1),
            lambda value: value["catalogs"]["test_classes"][0].update(required=1),
        )
        for mutate in mutations:
            changed = fresh_manifest()
            mutate(changed)
            with self.assertRaises(model.MatrixModelError):
                model.validate_manifest(changed)

    def test_unhashable_catalog_and_manual_values_fail_in_controlled_form(self):
        mutations = (
            lambda value: value["catalogs"]["test_classes"][0].update(
                host_modes=[{"id": "no-host"}]
            ),
            lambda value: value["catalogs"]["test_classes"][0].update(
                test_points=[["environment-binding"]]
            ),
            lambda value: value["catalogs"]["test_classes"][0].update(
                evidence_kinds=[{"kind": "environment-report"}]
            ),
        )
        for mutate in mutations:
            changed = fresh_manifest()
            mutate(changed)
            with self.assertRaises(model.MatrixModelError) as context:
                model.validate_manifest(changed)
            self.assertNotIsInstance(context.exception.__cause__, TypeError)

    def test_nonfinite_duplicate_and_invalid_json_are_rejected(self):
        for raw, code in (
            ('{"a":NaN}', "E_JSON_NONFINITE"),
            ('{"a":Infinity}', "E_JSON_NONFINITE"),
            ('{"a":1,"a":2}', "E_JSON_DUPLICATE_KEY"),
            ('{"a":', "E_JSON_INVALID"),
        ):
            with self.assertRaisesRegex(model.MatrixModelError, code):
                model.strict_json_loads(raw)
        with self.assertRaisesRegex(model.MatrixModelError, "E_JSON_INVALID"):
            model.strict_json_loads("1" + "0" * 5000)
        with self.assertRaisesRegex(model.MatrixModelError, "E_JSON_UTF8"):
            model.strict_json_loads("\ud800")

        cyclic = []
        cyclic.append(cyclic)
        with self.assertRaisesRegex(model.MatrixModelError, "E_CANONICAL_RECURSION"):
            model.canonical_json_bytes(cyclic)

    def test_invalid_timestamp_and_engine_binding_are_rejected(self):
        changed = fresh_manifest()
        changed["created_at"] = "2026-02-30T12:00:00Z"
        with self.assertRaisesRegex(model.MatrixModelError, "E_TIMESTAMP"):
            model.validate_manifest(changed)

        changed = fresh_manifest()
        changed["catalogs"]["engines"][0]["source_commit"] = "0" * 40
        with self.assertRaisesRegex(model.MatrixModelError, "E_ENGINE_PROVENANCE"):
            model.validate_manifest(changed)

    def test_synthetic_manifest_can_never_be_release_eligible(self):
        changed = fresh_manifest()
        changed["release_eligible"] = True
        with self.assertRaisesRegex(
            model.MatrixModelError, "E_SYNTHETIC_RELEASE_ELIGIBILITY"
        ):
            model.validate_manifest(changed)

    def test_all_public_synthetic_bindings_are_recomputable(self):
        manifest = self.manifest
        manifest_id = manifest["manifest_id"]
        candidate = manifest["candidate"]
        runtime_attributes = {
            "runtime_source_commit": candidate["runtime_source_commit"],
            "runtime_source_tree": candidate["runtime_source_tree"],
        }
        self.assertEqual(
            candidate["runtime_content_sha256"],
            model.synthetic_binding_sha256(
                manifest_id,
                "runtime-content",
                "runtime-content",
                runtime_attributes,
            ),
        )
        candidate_attributes = {
            **runtime_attributes,
            "runtime_content_sha256": candidate["runtime_content_sha256"],
        }
        self.assertEqual(
            candidate["package_sha256"],
            model.synthetic_binding_sha256(
                manifest_id,
                "candidate-package",
                "candidate-package",
                {
                    **candidate_attributes,
                    "package_kind": candidate["package_kind"],
                },
            ),
        )
        self.assertEqual(
            candidate["adapter_sha256"],
            model.synthetic_binding_sha256(
                manifest_id,
                "matrix-adapter",
                "matrix-adapter",
                {
                    **candidate_attributes,
                    "adapter_version": candidate["adapter_version"],
                },
            ),
        )
        for game in manifest["catalogs"]["games"]:
            self.assertEqual(
                game["adapter_sha256"],
                model.synthetic_binding_sha256(
                    manifest_id,
                    "game-adapter",
                    game["adapter_id"],
                    {
                        "game_id": game["id"],
                        "private_input": game["private_input"],
                    },
                ),
            )
        for engine in manifest["catalogs"]["engines"]:
            self.assertEqual(
                engine["runtime_sha256"],
                model.synthetic_binding_sha256(
                    manifest_id,
                    "engine-runtime",
                    engine["id"],
                    {
                        "version": engine["version"],
                        "source_commit": engine["source_commit"],
                        "binding_kind": engine["binding_kind"],
                    },
                ),
            )
        for platform in manifest["catalogs"]["platforms"]:
            self.assertEqual(
                platform["adapter_sha256"],
                model.synthetic_binding_sha256(
                    manifest_id,
                    "platform-adapter",
                    platform["adapter_id"],
                    {
                        "platform_id": platform["id"],
                        "physical_confirmation_required": platform[
                            "physical_confirmation_required"
                        ],
                    },
                ),
            )
        for host_mode in manifest["catalogs"]["host_modes"]:
            self.assertEqual(
                host_mode["fixture_sha256"],
                model.synthetic_binding_sha256(
                    manifest_id,
                    "host-mode-fixture",
                    host_mode["id"],
                    {"host_mode_id": host_mode["id"]},
                ),
            )
        for point in manifest["catalogs"]["test_points"]:
            for binding in point["required_input_hashes"]:
                self.assertEqual(
                    binding["sha256"],
                    model.synthetic_binding_sha256(
                        manifest_id,
                        "test-point-input",
                        f"{point['id']}.{binding['id']}",
                        {
                            "test_point_id": point["id"],
                            "test_point_kind": point["kind"],
                            "binding_id": binding["id"],
                        },
                    ),
                )

        changed = fresh_manifest()
        digest = changed["candidate"]["package_sha256"]
        changed["candidate"]["package_sha256"] = (
            ("0" if digest[0] != "0" else "1") + digest[1:]
        )
        with self.assertRaisesRegex(model.MatrixModelError, "E_SYNTHETIC_BINDING"):
            model.validate_manifest(changed)

    def test_frozen_runtime_and_required_cell_set_are_derived(self):
        candidate = self.manifest["candidate"]
        self.assertEqual(
            candidate["runtime_source_commit"],
            "f84679c70c64ac7ee3380c2f3185c6ae237c6da9",
        )
        self.assertEqual(
            candidate["runtime_source_tree"],
            "132490d94e75fe9abd1c268bc1bc896a93e93ff8",
        )
        derived = model.derive_required_cell_set(self.manifest)
        self.assertEqual(self.manifest["required_cell_set"], derived)
        self.assertEqual(derived["required_cell_count"], 17820)
        self.assertEqual(
            derived["required_cells_by_game"],
            {"red": 5940, "blue": 5940, "yellow": 5940},
        )
        self.assertEqual(
            derived["required_cell_ids_sha256"],
            "e952178256e2a6e00aad0a36feff833bfac2532726d9d3096da4a2453d3c0591",
        )
        changed = fresh_manifest()
        changed["required_cell_set"]["required_cell_count"] -= 1
        with self.assertRaisesRegex(
            model.MatrixModelError, "E_REQUIRED_CELL_SET_BINDING"
        ):
            model.validate_manifest(changed)

    def test_battle_art_asset_and_ios_label_are_portably_bound(self):
        battle = self.manifest["catalogs"]["hosts"][0]
        self.assertEqual(battle["id"], "battle-art-1.9.8")
        self.assertEqual(
            battle["package_sha256"],
            "28c06d4153087be28891090d2d85d039f7cd81ba69f74c56a069016b3adf58bd",
        )
        changed = fresh_manifest()
        changed["catalogs"]["hosts"][0]["package_sha256"] = "0" * 64
        with self.assertRaisesRegex(model.MatrixModelError, "E_HOST_PROVENANCE"):
            model.validate_manifest(changed)

        schema = model.strict_json_load(SCHEMA_PATHS[0])
        ios = next(
            platform
            for platform in self.manifest["catalogs"]["platforms"]
            if platform["id"] == "ios-love12"
        )
        self.assertEqual(ios["label"], "iOS LOVE 12")
        self.assertIsNotNone(re.fullmatch(schema["$defs"]["label"]["pattern"], ios["label"]))
        host_rules = schema["$defs"]["host"]["allOf"]
        self.assertTrue(
            any(
                rule.get("then", {})
                .get("properties", {})
                .get("package_sha256", {})
                .get("const")
                == model.BATTLE_ART_1_9_8_PACKAGE_SHA256
                for rule in host_rules
            )
        )

    def test_private_release_freezes_host_and_class_universe(self):
        private = private_release_manifest()
        self.assertEqual(
            private["required_cell_set"]["required_cell_count"], 17820
        )
        self.assertEqual(
            private["required_cell_set"]["required_cells_by_game"],
            {"red": 5940, "blue": 5940, "yellow": 5940},
        )
        hosts = private["catalogs"]["hosts"]
        self.assertTrue(hosts[0]["eligible"])
        self.assertFalse(hosts[1]["eligible"])

        host_swap = copy.deepcopy(private)
        host_swap["catalogs"]["hosts"][0].update(
            eligible=False,
            exclusion_reason="The released package lacks the approved companion runtime",
        )
        host_swap["catalogs"]["hosts"][1].update(
            eligible=True,
            exclusion_reason=None,
        )
        with self.assertRaisesRegex(
            model.MatrixModelError, "E_HOST_ELIGIBILITY_BINDING"
        ):
            model.validate_manifest(host_swap)

        evidence_swap = copy.deepcopy(private)
        evidence_swap["catalogs"]["test_classes"][0]["evidence_kinds"] = [
            "cleanup-report"
        ]
        with self.assertRaisesRegex(
            model.MatrixModelError, "E_TEST_CLASS_EVIDENCE"
        ):
            model.validate_manifest(evidence_swap)

        reduced = copy.deepcopy(private)
        reduced["catalogs"]["test_classes"][3]["host_modes"] = ["no-host"]
        reduced["catalogs"]["test_classes"][4]["test_points"] = [
            "route-pallet-bedroom"
        ]
        reduced["catalogs"]["test_classes"][19]["host_modes"] = ["no-host"]
        reduced["required_cell_set"].update(
            required_cell_count=12870,
            required_cells_by_game={
                "red": 4290,
                "blue": 4290,
                "yellow": 4290,
            },
        )
        with self.assertRaisesRegex(
            model.MatrixModelError,
            "E_TEST_CLASS_HOST_MODES|E_TEST_CLASS_POINTS|E_REQUIRED_CELL_UNIVERSE",
        ):
            model.validate_manifest(reduced)

    def test_private_release_requires_all_52_acquired_bindings(self):
        private = private_release_manifest()
        acquisition = private["binding_acquisition"]
        self.assertEqual(acquisition["state"], "ACQUIRED_PRIVATE")
        self.assertEqual(acquisition["binding_count"], 52)
        self.assertEqual(
            acquisition["acquisition_record_schema"],
            model.PRIVATE_BINDING_ACQUISITION_SCHEMA,
        )
        self.assertTrue(acquisition["acquisition_record_sha256"])

        relabeled = relabeled_public_private_manifest()
        with self.assertRaisesRegex(
            model.MatrixModelError,
            "E_PRIVATE_PUBLIC_BINDING",
        ):
            model.validate_manifest(relabeled)

        one_public = copy.deepcopy(private)
        one_public["catalogs"]["test_points"][-1]["required_input_hashes"][0][
            "sha256"
        ] = fresh_manifest()["catalogs"]["test_points"][-1][
            "required_input_hashes"
        ][0]["sha256"]
        one_public["binding_acquisition"] = model.derive_binding_acquisition(
            one_public,
            state="ACQUIRED_PRIVATE",
            acquisition_record_sha256=acquisition[
                "acquisition_record_sha256"
            ],
        )
        one_public["required_cell_set"] = model._derive_required_cell_set(
            one_public
        )
        with self.assertRaisesRegex(
            model.MatrixModelError,
            "E_PRIVATE_PUBLIC_BINDING",
        ):
            model.validate_manifest(one_public)

    def test_fixed_host_and_engine_provenance_rejects_recomputed_forgery(self):
        private = private_release_manifest()
        mutations = {
            "battle-version": lambda value: value["catalogs"]["hosts"][0].update(
                version="9.9.9"
            ),
            "battle-source": lambda value: value["catalogs"]["hosts"][0].update(
                source_commit="0" * 40
            ),
            "dramaless-version": lambda value: value["catalogs"]["hosts"][1].update(
                version="9.9.9"
            ),
            "engine-version": lambda value: value["catalogs"]["engines"][0].update(
                version="9.9.9"
            ),
            "engine-source": lambda value: value["catalogs"]["engines"][0].update(
                source_commit="0" * 40
            ),
        }
        for name, mutate in mutations.items():
            changed = copy.deepcopy(private)
            mutate(changed)
            changed["required_cell_set"] = model._derive_required_cell_set(changed)
            with self.subTest(mutation=name):
                with self.assertRaisesRegex(
                    model.MatrixModelError,
                    "E_HOST_PROVENANCE|E_ENGINE_PROVENANCE",
                ):
                    model.validate_manifest(changed)

    def test_native_draft_schema_matches_python_catalog_and_mode_contract(self):
        powershell = shutil.which("pwsh")
        if powershell is None:
            self.skipTest("PowerShell Test-Json is unavailable")
        def validate_with_powershell(instance):
            instance_text = str(instance).replace("'", "''")
            schema_text = str(SCHEMA_PATHS[0]).replace("'", "''")
            script = (
                f"$raw = Get-Content -Raw -LiteralPath '{instance_text}'; "
                f"$ok = Test-Json -Json $raw -SchemaFile '{schema_text}' "
                "-ErrorAction SilentlyContinue; "
                "if ($ok -eq $true) { exit 0 } else { exit 1 }"
            )
            return subprocess.run(
                [
                    powershell,
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    script,
                ],
                check=False,
                capture_output=True,
                text=True,
            )

        accepted = validate_with_powershell(MATRIX_PATH)
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        with ScopedTestDirectory() as temporary:
            private_instance = Path(temporary) / "private-release.json"
            private_instance.write_text(
                json.dumps(private_release_manifest()),
                encoding="utf-8",
            )
            private_accepted = validate_with_powershell(private_instance)
            self.assertEqual(
                private_accepted.returncode,
                0,
                private_accepted.stderr,
            )

            relabeled = relabeled_public_private_manifest()
            relabeled_instance = Path(temporary) / "private-public-hash-relabel.json"
            relabeled_instance.write_text(
                json.dumps(relabeled), encoding="utf-8"
            )
            relabeled_rejected = validate_with_powershell(relabeled_instance)
            self.assertNotEqual(relabeled_rejected.returncode, 0)
            with self.assertRaisesRegex(
                model.MatrixModelError, "E_PRIVATE_PUBLIC_BINDING"
            ):
                model.validate_manifest(relabeled)

            def swap_fields(value, catalog, fields):
                first, second = value["catalogs"][catalog][:2]
                first_values = {field: first[field] for field in fields}
                for field in fields:
                    first[field] = second[field]
                    second[field] = first_values[field]

            mutations = {
                "wrong-battle": lambda value: value["catalogs"]["hosts"][0].update(
                    package_sha256="0" * 64
                ),
                "game-order": lambda value: value["catalogs"]["games"].reverse(),
                "engine-order": lambda value: value["catalogs"]["engines"].reverse(),
                "engine-mode": lambda value: value["catalogs"]["engines"][0].update(
                    binding_kind="PINNED_RUNTIME"
                ),
                "invalid-created-at": lambda value: value.update(
                    created_at="2026-99-99T25:61:61Z"
                ),
                "one-cell-contract": lambda value: value[
                    "required_cell_set"
                ].update(
                    manifest_input_sha256="0" * 64,
                    required_cell_count=1,
                    required_cell_ids_sha256="0" * 64,
                    required_cells_by_game={"red": 1, "blue": 1, "yellow": 1},
                ),
                "synthetic-candidate-package": lambda value: value[
                    "candidate"
                ].update(package_sha256="0" * 64),
                "synthetic-candidate-runtime": lambda value: value[
                    "candidate"
                ].update(runtime_content_sha256="0" * 64),
                "game-adapter-swap": lambda value: swap_fields(
                    value, "games", ("adapter_id", "adapter_sha256")
                ),
                "host-binding-swap": lambda value: swap_fields(
                    value, "hosts", ("source_commit", "package_sha256")
                ),
                "engine-runtime-swap": lambda value: swap_fields(
                    value, "engines", ("runtime_sha256",)
                ),
                "platform-adapter-swap": lambda value: swap_fields(
                    value, "platforms", ("adapter_id", "adapter_sha256")
                ),
                "synthetic-host-mode-hash": lambda value: value["catalogs"][
                    "host_modes"
                ][0].update(fixture_sha256="0" * 64),
                "synthetic-test-point-hash": lambda value: value["catalogs"][
                    "test_points"
                ][0]["required_input_hashes"][0].update(sha256="0" * 64),
                "unknown-host-mode-reference": lambda value: value["catalogs"][
                    "test_classes"
                ][0].update(host_modes=["unknown-host"]),
                "unknown-test-point-reference": lambda value: value["catalogs"][
                    "test_classes"
                ][0].update(test_points=["unknown-point"]),
                "unknown-evidence-kind-reference": lambda value: value[
                    "catalogs"
                ]["test_classes"][0].update(evidence_kinds=["unknown-report"]),
                "objective-cleanup-evidence-substitution": lambda value: value[
                    "catalogs"
                ]["test_classes"][0].update(evidence_kinds=["cleanup-report"]),
                "class-point-substitution": lambda value: value["catalogs"][
                    "test_classes"
                ][0].update(test_points=["clean-install"]),
                "class-host-mode-substitution": lambda value: value[
                    "catalogs"
                ]["test_classes"][0].update(host_modes=["no-host"]),
                "policy-order": lambda value: value["release_policy"][
                    "required_games"
                ].reverse(),
                "class-order": lambda value: value["catalogs"]["test_classes"].reverse(),
                "point-duplicate": lambda value: value["catalogs"][
                    "test_points"
                ].append(copy.deepcopy(value["catalogs"]["test_points"][0])),
                "point-same-id-different-label": lambda value: value["catalogs"][
                    "test_points"
                ][1].update(id=value["catalogs"]["test_points"][0]["id"]),
                "point-different-label": lambda value: value["catalogs"][
                    "test_points"
                ][0].update(label="Different label"),
                "binding-same-id-different-hash": lambda value: value["catalogs"][
                    "test_points"
                ][0]["required_input_hashes"].append(
                    {
                        "id": value["catalogs"]["test_points"][0][
                            "required_input_hashes"
                        ][0]["id"],
                        "sha256": "0" * 64,
                    }
                ),
                "class-boundary": lambda value: value["catalogs"]["test_classes"][-1].update(
                    execution="OBJECTIVE"
                ),
                "manual-single-evidence": lambda value: value["catalogs"][
                    "test_classes"
                ][-1].update(evidence_kinds=["manual-verdict"]),
            }
            for name, mutate in mutations.items():
                changed = fresh_manifest()
                mutate(changed)
                instance = Path(temporary) / f"{name}.json"
                instance.write_text(json.dumps(changed), encoding="utf-8")
                rejected = validate_with_powershell(instance)
                with self.subTest(mutation=name):
                    self.assertNotEqual(rejected.returncode, 0)
                    with self.assertRaises(model.MatrixModelError):
                        model.validate_manifest(changed)

            private_mutations = {
                "private-battle-version": lambda value: value["catalogs"][
                    "hosts"
                ][0].update(version="9.9.9"),
                "private-battle-source": lambda value: value["catalogs"][
                    "hosts"
                ][0].update(source_commit="0" * 40),
                "private-engine-version": lambda value: value["catalogs"][
                    "engines"
                ][0].update(version="9.9.9"),
                "private-engine-source": lambda value: value["catalogs"][
                    "engines"
                ][0].update(source_commit="0" * 40),
                "private-host-eligibility-swap": lambda value: (
                    value["catalogs"]["hosts"][0].update(
                        eligible=False,
                        exclusion_reason="The released package lacks the approved companion runtime",
                    ),
                    value["catalogs"]["hosts"][1].update(
                        eligible=True,
                        exclusion_reason=None,
                    ),
                ),
                "private-12870-cell-rewrite": lambda value: (
                    value["catalogs"]["test_classes"][3].update(
                        host_modes=["no-host"]
                    ),
                    value["catalogs"]["test_classes"][4].update(
                        test_points=["route-pallet-bedroom"]
                    ),
                    value["catalogs"]["test_classes"][19].update(
                        host_modes=["no-host"]
                    ),
                    value["required_cell_set"].update(
                        required_cell_count=12870,
                        required_cells_by_game={
                            "red": 4290,
                            "blue": 4290,
                            "yellow": 4290,
                        },
                    ),
                ),
            }
            for name, mutate in private_mutations.items():
                changed = copy.deepcopy(private_release_manifest())
                mutate(changed)
                instance = Path(temporary) / f"{name}.json"
                instance.write_text(json.dumps(changed), encoding="utf-8")
                rejected = validate_with_powershell(instance)
                with self.subTest(mutation=name):
                    self.assertNotEqual(rejected.returncode, 0)
                    with self.assertRaises(model.MatrixModelError):
                        model.validate_manifest(changed)

    def test_native_schemas_reject_same_evidence_kind_with_different_digest(self):
        powershell = shutil.which("pwsh")
        if powershell is None:
            self.skipTest("PowerShell Test-Json is unavailable")

        def validate_with_powershell(instance, schema):
            instance_text = str(instance).replace("'", "''")
            schema_text = str(schema).replace("'", "''")
            script = (
                f"$raw = Get-Content -Raw -LiteralPath '{instance_text}'; "
                f"$ok = Test-Json -Json $raw -SchemaFile '{schema_text}' "
                "-ErrorAction SilentlyContinue; "
                "if ($ok -eq $true) { exit 0 } else { exit 1 }"
            )
            return subprocess.run(
                [
                    powershell,
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    script,
                ],
                check=False,
                capture_output=True,
                text=True,
            )

        cell = self.objective_cell
        attempt_id = model.make_attempt_id(
            cell, 1, "2026-08-23T12:00:00Z", "matrix-test-owner"
        )
        cell_result = passing_result(cell, attempt_id)
        ledger_event = {
            "schema": ledger.LEDGER_EVENT_SCHEMA,
            "schema_version": 1,
            "event_id": "a" * 64,
            "cell_id": cell.cell_id,
            "input_fingerprint": cell.input_fingerprint,
            "attempt_id": attempt_id,
            "sequence": 0,
            "previous_event_sha256": None,
            "recorded_at": "2026-08-23T12:00:00Z",
            "event_type": "GATE_STARTED",
            "gate_id": cell.identity["required_gate_ids"][0],
            "evidence": [copy.deepcopy(cell_result["evidence"][0])],
            "cell_result_sha256": None,
        }
        with ScopedTestDirectory() as temporary:
            temporary_path = Path(temporary)
            for name, baseline, schema in (
                ("cell-result", cell_result, SCHEMA_PATHS[1]),
                ("ledger-event", ledger_event, SCHEMA_PATHS[2]),
            ):
                instance = temporary_path / f"{name}.json"
                instance.write_text(json.dumps(baseline), encoding="utf-8")
                accepted = validate_with_powershell(instance, schema)
                with self.subTest(document=name, state="baseline"):
                    self.assertEqual(accepted.returncode, 0, accepted.stderr)

                changed = copy.deepcopy(baseline)
                duplicate = copy.deepcopy(changed["evidence"][0])
                duplicate["sha256"] = "c" * 64
                changed["evidence"].append(duplicate)
                instance.write_text(json.dumps(changed), encoding="utf-8")
                rejected = validate_with_powershell(instance, schema)
                with self.subTest(document=name, state="duplicate-kind"):
                    self.assertNotEqual(rejected.returncode, 0)

            cell_mutations = {
                "invalid-started-at": lambda value: value.update(
                    started_at="2026-99-99T25:61:61Z"
                ),
                "objective-manual-substitution": lambda value: value.update(
                    evidence=[
                        {"kind": "manual-verdict", "sha256": "b" * 64, "bytes": 1}
                    ]
                ),
            }
            for name, mutate in cell_mutations.items():
                changed = copy.deepcopy(cell_result)
                mutate(changed)
                instance = temporary_path / f"cell-{name}.json"
                instance.write_text(json.dumps(changed), encoding="utf-8")
                rejected = validate_with_powershell(instance, SCHEMA_PATHS[1])
                with self.subTest(document="cell-result", state=name):
                    self.assertNotEqual(rejected.returncode, 0)

            manual_attempt = model.make_attempt_id(
                self.manual_cell,
                1,
                "2026-08-23T12:00:00Z",
                "matrix-test-owner",
            )
            manual_result = passing_result(self.manual_cell, manual_attempt)
            without_packet = copy.deepcopy(manual_result)
            without_packet["evidence"] = [
                item
                for item in without_packet["evidence"]
                if item["kind"] == "manual-verdict"
            ]
            instance = temporary_path / "manual-without-packet.json"
            instance.write_text(json.dumps(without_packet), encoding="utf-8")
            rejected = validate_with_powershell(instance, SCHEMA_PATHS[1])
            self.assertNotEqual(rejected.returncode, 0)

            mismatched_verdict = copy.deepcopy(manual_result)
            mismatched_verdict["manual_verdict_sha256"] = "c" * 64
            instance = temporary_path / "manual-verdict-mismatch.json"
            instance.write_text(json.dumps(mismatched_verdict), encoding="utf-8")
            structurally_valid = validate_with_powershell(instance, SCHEMA_PATHS[1])
            self.assertEqual(structurally_valid.returncode, 0, structurally_valid.stderr)
            with self.assertRaisesRegex(
                model.MatrixModelError, "E_MANUAL_VERDICT_EVIDENCE"
            ):
                model.validate_cell_result(mismatched_verdict, self.manual_cell)

            reversed_time = copy.deepcopy(cell_result)
            reversed_time["started_at"] = "2026-08-23T12:00:01Z"
            reversed_time["finished_at"] = "2026-08-23T12:00:00Z"
            instance = temporary_path / "cell-reversed-time.json"
            instance.write_text(json.dumps(reversed_time), encoding="utf-8")
            structurally_valid = validate_with_powershell(instance, SCHEMA_PATHS[1])
            self.assertEqual(structurally_valid.returncode, 0, structurally_valid.stderr)
            with self.assertRaisesRegex(model.MatrixModelError, "E_TIMESTAMP_ORDER"):
                model.validate_cell_result(reversed_time, cell)

            event_mutations = {
                "sequence-seven-without-previous": lambda value: value.update(
                    sequence=7
                ),
                "sequence-zero-with-previous": lambda value: value.update(
                    previous_event_sha256="b" * 64
                ),
                "gate-without-gate-id": lambda value: value.update(gate_id=None),
                "attempt-with-gate-id": lambda value: value.update(
                    event_type="ATTEMPT_BLOCKED"
                ),
                "invalid-recorded-at": lambda value: value.update(
                    recorded_at="2026-99-99T25:61:61Z"
                ),
            }
            for name, mutate in event_mutations.items():
                changed = copy.deepcopy(ledger_event)
                mutate(changed)
                instance = temporary_path / f"event-{name}.json"
                instance.write_text(json.dumps(changed), encoding="utf-8")
                rejected = validate_with_powershell(instance, SCHEMA_PATHS[2])
                with self.subTest(document="ledger-event", state=name):
                    self.assertNotEqual(rejected.returncode, 0)

            manual_verdict = {
                "schema": model.MANUAL_VERDICT_SCHEMA,
                "schema_version": 1,
                "cell_id": self.manual_cell.cell_id,
                "input_fingerprint": self.manual_cell.input_fingerprint,
                "review_packet_sha256": "a" * 64,
                "objective_result_sha256": "b" * 64,
                "reviewer_id": "reviewer-one",
                "reviewed_at": "2026-08-23T12:05:00Z",
                "verdict": "PASS",
                "objective_checks_passed": True,
                "criteria": ["visual-correctness"],
            }
            instance = temporary_path / "manual-verdict.json"
            instance.write_text(json.dumps(manual_verdict), encoding="utf-8")
            accepted = validate_with_powershell(instance, SCHEMA_PATHS[3])
            self.assertEqual(accepted.returncode, 0, accepted.stderr)
            manual_verdict["reviewed_at"] = "2026-99-99T25:61:61Z"
            instance.write_text(json.dumps(manual_verdict), encoding="utf-8")
            rejected = validate_with_powershell(instance, SCHEMA_PATHS[3])
            self.assertNotEqual(rejected.returncode, 0)

    def test_public_status_requires_exact_validated_ledger_result_set(self):
        manifest = private_release_manifest()
        temporary = ScopedTestDirectory()
        self.addCleanup(temporary.cleanup)
        store = ledger.LedgerStore(Path(temporary.name) / "ledger")
        result_set = store.validated_result_set(manifest)
        status = public_status(manifest, result_set)
        self.assertEqual(
            model.validate_public_status(status, manifest, store.root), status
        )
        self.assertEqual(result_set.validated_result_count, 0)
        self.assertEqual(dict(result_set.status_counts)["MISSING"], 17820)

        no_ledger_summary = model._validated_result_set_from_ledger(
            manifest,
            [
                {
                    "cell_id": cell.cell_id,
                    "input_fingerprint": cell.input_fingerprint,
                    "status": "MISSING",
                    "attempt_id": None,
                    "last_event_sha256": None,
                    "cell_result_sha256": None,
                }
                for cell in model.expand_cells(manifest)
            ],
        )
        no_ledger_status = public_status(manifest, no_ledger_summary)
        self.assertEqual(
            model.validate_public_status(no_ledger_status, manifest),
            no_ledger_status,
        )

        with self.assertRaisesRegex(
            model.MatrixModelError, "E_PUBLIC_LEDGER_ROOT"
        ):
            model.validate_public_status(status, manifest, {})
        forged_result_set = model.ValidatedResultSet(
            manifest_sha256=result_set.manifest_sha256,
            manifest_input_sha256=result_set.manifest_input_sha256,
            required_cell_ids_sha256=result_set.required_cell_ids_sha256,
            required_cell_count=result_set.required_cell_count,
            ledger_snapshot_sha256="a" * 64,
            validated_result_set_sha256="b" * 64,
            validated_result_count=17820,
            status_counts=tuple(
                (state, 17820 if state == "PASS" else 0)
                for state in model.CELL_STATUSES
            ),
            passed_cells_by_game=tuple(
                (game_id, 5940) for game_id in model.GAME_IDS
            ),
        )
        with self.assertRaisesRegex(
            model.MatrixModelError, "E_PUBLIC_LEDGER_ROOT"
        ):
            model.validate_public_status(status, manifest, forged_result_set)

        mutations = (
            lambda value: value.update(blockers=False),
            lambda value: value.update(manifest_sha256="0" * 64),
            lambda value: value.update(manifest_input_sha256="0" * 64),
            lambda value: value.update(required_cell_ids_sha256="0" * 64),
            lambda value: value.update(source_commit="0" * 40),
            lambda value: value.update(package_sha256="0" * 64),
            lambda value: value.update(ledger_snapshot_sha256="0" * 64),
            lambda value: value.update(validated_result_set_sha256="0" * 64),
            lambda value: value.update(validated_result_count=1),
            lambda value: value["games"].__setitem__(1, copy.deepcopy(value["games"][0])),
            lambda value: value["games"].pop(),
            lambda value: value["status_counts"].update(PASS=2, NOT_RUN=1),
            lambda value: value.update(release="RELEASED"),
        )
        for mutate in mutations:
            changed = copy.deepcopy(status)
            mutate(changed)
            with self.subTest(changed=changed):
                with self.assertRaises(model.MatrixModelError):
                    model.validate_public_status(changed, manifest)

        truncated = copy.deepcopy(status)
        truncated["required_cells"] = 3
        truncated["status_counts"] = {
            state: 3 if state == "PASS" else 0 for state in model.CELL_STATUSES
        }
        for game in truncated["games"]:
            game["required_cells"] = 1
            game["passed_cells"] = 1
        with self.assertRaisesRegex(model.MatrixModelError, "E_PUBLIC_CELL_SET"):
            model.validate_public_status(truncated, manifest)

        false_ready = copy.deepcopy(status)
        false_ready["readiness"] = "READY"
        false_ready["blockers"] = []
        false_ready["validated_result_count"] = false_ready["required_cells"]
        false_ready["status_counts"] = {
            state: false_ready["required_cells"] if state == "PASS" else 0
            for state in model.CELL_STATUSES
        }
        for game in false_ready["games"]:
            game["status"] = "PASS"
            game["passed_cells"] = game["required_cells"]
        with self.assertRaisesRegex(
            model.MatrixModelError, "E_PUBLIC_LEDGER_REQUIRED"
        ):
            model.validate_public_status(false_ready, manifest)
        with self.assertRaisesRegex(
            model.MatrixModelError, "E_PUBLIC_RESULT_SET_BINDING"
        ):
            model.validate_public_status(false_ready, manifest, store.root)

        powershell = shutil.which("pwsh")
        if powershell is not None:
            with ScopedTestDirectory() as temporary:
                instance = Path(temporary) / "status.json"
                schema_text = str(SCHEMA_PATHS[4]).replace("'", "''")

                def native_status_exit(value):
                    instance.write_text(json.dumps(value), encoding="utf-8")
                    instance_text = str(instance).replace("'", "''")
                    script = (
                        f"$raw = Get-Content -Raw -LiteralPath '{instance_text}'; "
                        f"$ok = Test-Json -Json $raw -SchemaFile '{schema_text}' "
                        "-ErrorAction SilentlyContinue; "
                        "if ($ok -eq $true) { exit 0 } else { exit 1 }"
                    )
                    return subprocess.run(
                        [
                            powershell,
                            "-NoProfile",
                            "-NonInteractive",
                            "-Command",
                            script,
                        ],
                        check=False,
                        capture_output=True,
                        text=True,
                    ).returncode

                self.assertEqual(native_status_exit(status), 0)
                reviewer_false_ready = copy.deepcopy(status)
                reviewer_false_ready.update(
                    readiness="READY",
                    blockers=[],
                    validated_result_count=17820,
                )
                reviewer_false_ready["status_counts"] = {
                    state: 0 for state in model.CELL_STATUSES
                }
                for game in reviewer_false_ready["games"]:
                    game["status"] = "PASS"
                    game["passed_cells"] = 0
                self.assertNotEqual(native_status_exit(reviewer_false_ready), 0)
                invalid_time = copy.deepcopy(status)
                invalid_time["generated_at"] = "2026-99-99T25:61:61Z"
                self.assertNotEqual(native_status_exit(invalid_time), 0)

        synthetic_result_set = model._validated_result_set_from_ledger(
            self.manifest,
            [
                {
                    "cell_id": cell.cell_id,
                    "input_fingerprint": cell.input_fingerprint,
                    "status": "MISSING",
                    "attempt_id": None,
                    "last_event_sha256": None,
                    "cell_result_sha256": None,
                }
                for cell in self.cells
            ],
        )
        synthetic = public_status(self.manifest, synthetic_result_set)
        self.assertEqual(
            model.validate_public_status(synthetic, self.manifest),
            synthetic,
        )

    def test_caller_created_summary_cannot_authorize_ready(self):
        manifest = private_release_manifest()
        cells = model.expand_cells(manifest)
        forged_records = [
            {
                "cell_id": cell.cell_id,
                "input_fingerprint": cell.input_fingerprint,
                "status": "PASS",
                "attempt_id": "attempt-" + "a" * 64,
                "last_event_sha256": "b" * 64,
                "cell_result_sha256": "c" * 64,
            }
            for cell in cells
        ]
        forged_summary = model._validated_result_set_from_ledger(
            manifest, forged_records
        )
        forged_status = public_status(manifest, forged_summary)
        self.assertEqual(forged_status["readiness"], "READY")
        direct_summary = model.ValidatedResultSet(**forged_summary.__dict__)

        with self.assertRaisesRegex(
            model.MatrixModelError, "E_PUBLIC_LEDGER_REQUIRED"
        ):
            model.validate_public_status(forged_status, manifest)
        with self.assertRaisesRegex(
            model.MatrixModelError, "E_PUBLIC_LEDGER_ROOT"
        ):
            model.validate_public_status(
                forged_status, manifest, direct_summary
            )
        missing_root = ROOT / "never-created-m1-ledger"
        self.assertFalse(missing_root.exists())
        with self.assertRaisesRegex(
            model.MatrixModelError, "E_PUBLIC_LEDGER_VALIDATION"
        ):
            model.validate_public_status(forged_status, manifest, missing_root)

        with ScopedTestDirectory() as temporary:
            store = ledger.LedgerStore(Path(temporary) / "ledger")
            before = sorted(
                path.relative_to(store.root).as_posix()
                for path in store.root.rglob("*")
            )
            with self.assertRaisesRegex(
                model.MatrixModelError, "E_PUBLIC_RESULT_SET_BINDING"
            ):
                model.validate_public_status(
                    forged_status, manifest, store.root
                )
            after = sorted(
                path.relative_to(store.root).as_posix()
                for path in store.root.rglob("*")
            )
            self.assertEqual(before, after)

    def test_public_ready_rejects_partial_and_mismatched_ledgers(self):
        manifest = private_release_manifest()
        missing_summary = model._validated_result_set_from_ledger(
            manifest,
            [
                {
                    "cell_id": cell.cell_id,
                    "input_fingerprint": cell.input_fingerprint,
                    "status": "MISSING",
                    "attempt_id": None,
                    "last_event_sha256": None,
                    "cell_result_sha256": None,
                }
                for cell in model.expand_cells(manifest)
            ],
        )
        status = public_status(manifest, missing_summary)
        cell = model.expand_cells(manifest)[0]

        with self.subTest(case="interrupted-staging-write"):
            with ScopedTestDirectory() as temporary:
                store = ledger.LedgerStore(Path(temporary) / "ledger")
                (store.staging_root / "interrupted.partial").write_bytes(b"x")
                with self.assertRaisesRegex(
                    model.MatrixModelError, "E_PUBLIC_LEDGER_VALIDATION"
                ):
                    model.validate_public_status(status, manifest, store.root)

        with self.subTest(case="legacy-attempt-partial"):
            with ScopedTestDirectory() as temporary:
                store = ledger.LedgerStore(Path(temporary) / "ledger")
                attempt_id = store.begin_attempt(
                    cell,
                    attempt_number=1,
                    started_at="2026-08-23T12:00:00Z",
                    owner_id="matrix-test-owner",
                )
                _, attempt_path = store._find_attempt(cell.cell_id, attempt_id)
                partial = attempt_path / (".result.json.partial-" + "a" * 32)
                partial.write_bytes(b"{}")
                with self.assertRaisesRegex(
                    model.MatrixModelError, "E_PUBLIC_RESULT_SET_BINDING"
                ):
                    model.validate_public_status(status, manifest, store.root)

        with self.subTest(case="cell-identity-mismatch"):
            with ScopedTestDirectory() as temporary:
                store = ledger.LedgerStore(Path(temporary) / "ledger")
                store.begin_attempt(
                    cell,
                    attempt_number=1,
                    started_at="2026-08-23T12:00:00Z",
                    owner_id="matrix-test-owner",
                )
                cell_path = store.cells_root / cell.cell_id / "cell.json"
                changed = json.loads(cell_path.read_text(encoding="utf-8"))
                changed["identity"]["tier"] = "forged-tier"
                changed["input_fingerprint"] = model.sha256_value(
                    changed["identity"]
                )
                changed["cell_id"] = "cell-" + changed["input_fingerprint"]
                cell_path.write_bytes(model.canonical_json_bytes(changed))
                with self.assertRaisesRegex(
                    model.MatrixModelError, "E_PUBLIC_RESULT_SET_BINDING"
                ):
                    model.validate_public_status(status, manifest, store.root)

    def test_python_and_schema_bounds_match_and_fail_closed(self):
        cell = self.objective_cell
        attempt_id = model.make_attempt_id(
            cell, 1, "2026-08-23T12:00:00Z", "matrix-test-owner"
        )
        result = passing_result(cell, attempt_id)
        result["evidence"] = [
            {"kind": f"report-{index}", "sha256": "a" * 64, "bytes": 1}
            for index in range(model.MAX_EVIDENCE_ITEMS + 1)
        ]
        with self.assertRaisesRegex(model.MatrixModelError, "E_ARRAY_LENGTH"):
            model.validate_cell_result(result, cell)
        result = passing_result(cell, attempt_id)
        result["evidence"][0]["bytes"] = model.MAX_EVIDENCE_BYTES + 1
        with self.assertRaises(model.MatrixModelError):
            model.validate_cell_result(result, cell)

        verdict = {
            "schema": model.MANUAL_VERDICT_SCHEMA,
            "schema_version": 1,
            "cell_id": self.manual_cell.cell_id,
            "input_fingerprint": self.manual_cell.input_fingerprint,
            "review_packet_sha256": "c" * 64,
            "objective_result_sha256": "d" * 64,
            "reviewer_id": "reviewer-one",
            "reviewed_at": "2026-08-23T12:05:00Z",
            "verdict": "PASS",
            "objective_checks_passed": True,
            "criteria": [f"criterion-{index}" for index in range(33)],
        }
        with self.assertRaisesRegex(model.MatrixModelError, "E_ARRAY_LENGTH"):
            model.validate_manual_verdict(verdict, self.manual_cell)

        mutations = []
        changed = fresh_manifest()
        changed["catalogs"]["test_classes"][0]["test_points"] = ["x"] * 33
        mutations.append(changed)
        changed = fresh_manifest()
        changed["catalogs"]["test_classes"][0]["evidence_kinds"] = ["x"] * 17
        mutations.append(changed)
        for changed in mutations:
            with self.assertRaisesRegex(model.MatrixModelError, "E_ARRAY_LENGTH"):
                model.validate_manifest(changed)

        cell_schema = model.strict_json_load(SCHEMA_PATHS[1])
        event_schema = model.strict_json_load(SCHEMA_PATHS[2])
        manual_schema = model.strict_json_load(SCHEMA_PATHS[3])
        manifest_schema = model.strict_json_load(SCHEMA_PATHS[0])
        point_schema = manifest_schema["$defs"]["catalogs"]["properties"][
            "test_points"
        ]
        self.assertEqual(point_schema["minItems"], model.MAX_TEST_POINTS)
        self.assertEqual(point_schema["maxItems"], model.MAX_TEST_POINTS)
        for binding_name in (
            "single_contract_binding",
            "single_route_binding",
            "single_golden_binding",
        ):
            binding_schema = manifest_schema["$defs"][binding_name]
            self.assertEqual(binding_schema["minItems"], model.MAX_POINT_BINDINGS)
            self.assertEqual(binding_schema["maxItems"], model.MAX_POINT_BINDINGS)
        self.assertEqual(
            cell_schema["properties"]["evidence"]["maxItems"],
            model.MAX_EVIDENCE_ITEMS,
        )
        self.assertEqual(
            event_schema["properties"]["evidence"]["maxItems"],
            model.MAX_EVIDENCE_ITEMS,
        )
        self.assertTrue(cell_schema["properties"]["evidence"]["uniqueItems"])
        self.assertTrue(event_schema["properties"]["evidence"]["uniqueItems"])
        self.assertEqual(
            event_schema["properties"]["sequence"]["maximum"],
            ledger.MAX_EVENT_SEQUENCE,
        )
        self.assertEqual(
            cell_schema["$defs"]["evidence"]["properties"]["bytes"]["maximum"],
            model.MAX_EVIDENCE_BYTES,
        )
        for schema in (cell_schema, event_schema):
            evidence_schema = schema["$defs"]["evidence"]
            self.assertEqual(
                tuple(evidence_schema["required"]), model.EVIDENCE_BINDING_FIELDS
            )
            self.assertEqual(
                set(evidence_schema["properties"]),
                set(model.EVIDENCE_BINDING_FIELDS),
            )
            self.assertFalse(evidence_schema["additionalProperties"])
        self.assertEqual(
            manual_schema["properties"]["criteria"]["maxItems"],
            model.MAX_MANUAL_CRITERIA,
        )

    def test_cell_result_requires_exact_cell_and_evidence_binding(self):
        cell = self.objective_cell
        attempt_id = model.make_attempt_id(
            cell, 1, "2026-08-23T12:00:00Z", "matrix-test-owner"
        )
        result = passing_result(cell, attempt_id)
        self.assertEqual(model.validate_cell_result(result, cell), result)

        other = next(candidate for candidate in self.cells if candidate.cell_id != cell.cell_id)
        with self.assertRaisesRegex(model.MatrixModelError, "E_CELL_BINDING"):
            model.validate_cell_result(result, other)

        changed = copy.deepcopy(result)
        changed["evidence"][0]["kind"] = "wrong-report"
        with self.assertRaisesRegex(
            model.MatrixModelError, "E_EVIDENCE_BINDING_DIGEST"
        ):
            model.validate_cell_result(changed, cell)

        changed = copy.deepcopy(result)
        first = changed["evidence"][0]
        duplicate = model.make_evidence_binding(
            cell,
            attempt_id,
            first["gate_id"],
            first["kind"],
            "c" * 64,
            first["bytes"],
        )
        changed["evidence"].append(duplicate)
        with self.assertRaisesRegex(model.MatrixModelError, "E_DUPLICATE_EVIDENCE"):
            model.validate_cell_result(changed, cell)

    def test_evidence_digest_cannot_replay_across_bound_dimensions(self):
        source = self.objective_cell
        attempt_id = model.make_attempt_id(
            source, 1, "2026-08-23T12:00:00Z", "matrix-test-owner"
        )
        source_result = passing_result(source, attempt_id)
        mutations = {
            "game-red-to-blue": lambda identity: identity["game"].update(id="blue"),
            "host": lambda identity: identity["host"].update(id="other-host"),
            "engine": lambda identity: identity["engine"].update(id="other-engine"),
            "tier": lambda identity: identity.update(tier="other-tier"),
            "platform": lambda identity: identity["platform"].update(
                id="other-platform"
            ),
            "runtime-source": lambda identity: identity.update(
                runtime_source_commit="0" * 40
            ),
            "runtime-tree": lambda identity: identity.update(
                runtime_source_tree="1" * 40
            ),
            "runtime-content": lambda identity: identity.update(
                runtime_content_sha256="2" * 64
            ),
            "package-kind": lambda identity: identity.update(
                package_kind="OTHER_PACKAGE"
            ),
            "package-content": lambda identity: identity.update(
                package_sha256="3" * 64
            ),
        }
        for name, mutate in mutations.items():
            identity = copy.deepcopy(dict(source.identity))
            mutate(identity)
            fingerprint = model.sha256_value(identity)
            target = model.MatrixCell(
                cell_id=f"cell-{fingerprint}",
                input_fingerprint=fingerprint,
                identity=identity,
            )
            unchanged = passing_result(target, attempt_id)
            unchanged["evidence"] = copy.deepcopy(source_result["evidence"])
            self.assertEqual(
                unchanged["evidence"][0]["sha256"],
                source_result["evidence"][0]["sha256"],
            )
            with self.subTest(binding=name, replay="unchanged-record"):
                with self.assertRaisesRegex(
                    model.MatrixModelError, "E_EVIDENCE_BINDING_CELL"
                ):
                    model.validate_cell_result(unchanged, target)

            relabeled = copy.deepcopy(unchanged)
            for record in relabeled["evidence"]:
                record["cell_id"] = target.cell_id
                record["input_fingerprint"] = target.input_fingerprint
            with self.subTest(binding=name, replay="relabeled-old-hash"):
                with self.assertRaisesRegex(
                    model.MatrixModelError, "E_EVIDENCE_BINDING_DIGEST"
                ):
                    model.validate_cell_result(relabeled, target)

    def test_evidence_binding_rejects_malformed_attempt_gate_and_kind_replay(self):
        cell = self.objective_cell
        attempt_id = model.make_attempt_id(
            cell, 1, "2026-08-23T12:00:00Z", "matrix-test-owner"
        )
        gate_id = cell.identity["required_gate_ids"][0]
        baseline = evidence_for(cell, attempt_id)[0]
        self.assertEqual(tuple(baseline), model.EVIDENCE_BINDING_FIELDS)
        self.assertEqual(
            baseline["binding_sha256"],
            model.sha256_value(
                {
                    field: baseline[field]
                    for field in model.EVIDENCE_BINDING_FIELDS[:-1]
                }
            ),
        )

        cases = {
            "missing": (
                lambda value: value.pop("kind"),
                "E_EVIDENCE_BINDING_FIELDS",
            ),
            "extra": (
                lambda value: value.update(extra="rejected"),
                "E_EVIDENCE_BINDING_FIELDS",
            ),
            "boolean-schema-version": (
                lambda value: value.update(schema_version=True),
                "E_EVIDENCE_BINDING_SCHEMA",
            ),
            "boolean-bytes": (
                lambda value: value.update(bytes=True),
                "E_TYPE_INTEGER",
            ),
            "nan-bytes": (
                lambda value: value.update(bytes=float("nan")),
                "E_TYPE_INTEGER",
            ),
            "infinite-bytes": (
                lambda value: value.update(bytes=float("inf")),
                "E_TYPE_INTEGER",
            ),
            "attempt-replay": (
                lambda value: value.update(attempt_id="attempt-" + "0" * 64),
                "E_EVIDENCE_BINDING_ATTEMPT",
            ),
            "gate-replay": (
                lambda value: value.update(gate_id="other-gate"),
                "E_EVIDENCE_BINDING_GATE",
            ),
            "kind-relabel": (
                lambda value: value.update(kind="other-report"),
                "E_EVIDENCE_BINDING_DIGEST",
            ),
            "stale-binding": (
                lambda value: value.update(binding_sha256="0" * 64),
                "E_EVIDENCE_BINDING_DIGEST",
            ),
        }
        for name, (mutate, code) in cases.items():
            changed = copy.deepcopy(baseline)
            mutate(changed)
            with self.subTest(mutation=name):
                with self.assertRaisesRegex(model.MatrixModelError, code):
                    model.validate_evidence_binding(
                        changed,
                        cell,
                        attempt_id=attempt_id,
                        gate_id=gate_id,
                    )

        old_draft = {
            "kind": baseline["kind"],
            "sha256": baseline["sha256"],
            "bytes": baseline["bytes"],
        }
        with self.assertRaisesRegex(
            model.MatrixModelError, "E_EVIDENCE_BINDING_FIELDS"
        ):
            model.validate_evidence_binding(
                old_draft,
                cell,
                attempt_id=attempt_id,
                gate_id=gate_id,
            )

    def test_objective_result_rejects_manual_substitution(self):
        cell = self.objective_cell
        attempt_id = model.make_attempt_id(
            cell, 1, "2026-08-23T12:00:00Z", "matrix-test-owner"
        )
        changed = passing_result(cell, attempt_id)
        changed["manual_verdict_sha256"] = "b" * 64
        with self.assertRaisesRegex(
            model.MatrixModelError, "E_MANUAL_REPLACES_OBJECTIVE"
        ):
            model.validate_cell_result(changed, cell)

    def test_manual_verdict_requires_manual_cell_and_objective_prerequisite(self):
        cell = self.manual_cell
        verdict = {
            "schema": model.MANUAL_VERDICT_SCHEMA,
            "schema_version": 1,
            "cell_id": cell.cell_id,
            "input_fingerprint": cell.input_fingerprint,
            "review_packet_sha256": "c" * 64,
            "objective_result_sha256": "d" * 64,
            "reviewer_id": "reviewer-one",
            "reviewed_at": "2026-08-23T12:05:00Z",
            "verdict": "PASS",
            "objective_checks_passed": True,
            "criteria": ["visual-correctness", "no-render-defect"],
        }
        self.assertEqual(model.validate_manual_verdict(verdict, cell), verdict)
        changed = copy.deepcopy(verdict)
        changed["objective_checks_passed"] = False
        with self.assertRaisesRegex(model.MatrixModelError, "E_MANUAL_WITHOUT_OBJECTIVE"):
            model.validate_manual_verdict(changed, cell)
        with self.assertRaisesRegex(model.MatrixModelError, "E_MANUAL_REPLACES_OBJECTIVE"):
            model.validate_manual_verdict(verdict, self.objective_cell)
        other_manual = next(
            candidate
            for candidate in self.cells
            if candidate.identity["test_execution"] == "MANUAL"
            and candidate.identity["game"]["id"] != cell.identity["game"]["id"]
            and candidate.identity["test_class"] == cell.identity["test_class"]
        )
        with self.assertRaisesRegex(model.MatrixModelError, "E_CELL_BINDING"):
            model.validate_manual_verdict(verdict, other_manual)
        changed = copy.deepcopy(verdict)
        changed["criteria"] = [{"id": "visual-correctness"}]
        with self.assertRaises(model.MatrixModelError):
            model.validate_manual_verdict(changed, cell)

        changed_manifest = fresh_manifest()
        changed_manifest["catalogs"]["test_classes"][-1]["evidence_kinds"] = [
            "manual-verdict"
        ]
        with self.assertRaisesRegex(
            model.MatrixModelError, "E_TEST_CLASS_EVIDENCE"
        ):
            model.validate_manifest(changed_manifest)

    def test_public_files_contain_no_private_input_or_artifact_path(self):
        raw = MATRIX_PATH.read_text(encoding="utf-8").lower()
        forbidden = (
            "c:" + "\\users\\",
            "c:" + "/" + "user" + "s/",
            "/" + "ho" + "me/",
            "/" + "user" + "s/",
            "private" + "-evidence://",
            "private" + "-fixtures/",
            "base" + "ro" + "ms/",
            "r" + "o" + "ms/",
            ".g" + "b\"",
            ".g" + "b" + "c\"",
            ".sa" + "v\"",
            ".sr" + "m\"",
        )
        self.assertFalse({pattern for pattern in forbidden if pattern in raw})

    def test_evidence_receipt_is_exact_canonical_and_root_scoped(self):
        cell = self.objective_cell
        attempt_id = model.make_attempt_id(
            cell, 1, "2026-08-23T12:00:00Z", "matrix-test-owner"
        )
        gate_id = cell.identity["required_gate_ids"][0]
        kind = cell.identity["required_evidence_kinds"][0]
        binding = model.make_evidence_binding(
            cell,
            attempt_id,
            gate_id,
            kind,
            "a" * 64,
            17,
        )
        root_id = "ledger-root-" + "b" * 64
        receipt = model.make_evidence_receipt(
            binding,
            cell,
            root_id,
            attempt_id=attempt_id,
            gate_id=gate_id,
        )
        self.assertEqual(tuple(receipt), model.EVIDENCE_RECEIPT_FIELDS)
        self.assertEqual(
            model.validate_evidence_receipt(
                receipt,
                cell,
                root_id,
                attempt_id=attempt_id,
                gate_id=gate_id,
            ),
            receipt,
        )

        mutations = (
            (
                "extra",
                lambda value: value.update(extra="forbidden"),
                "E_EVIDENCE_RECEIPT_FIELDS",
            ),
            (
                "boolean-version",
                lambda value: value.update(schema_version=True),
                "E_EVIDENCE_RECEIPT_SCHEMA",
            ),
            (
                "cross-root",
                lambda value: None,
                "E_EVIDENCE_RECEIPT_ROOT",
            ),
            (
                "digest",
                lambda value: value.update(receipt_sha256="0" * 64),
                "E_EVIDENCE_RECEIPT_DIGEST",
            ),
        )
        for name, mutate, code in mutations:
            changed = copy.deepcopy(receipt)
            mutate(changed)
            checked_root = (
                "ledger-root-" + "c" * 64 if name == "cross-root" else root_id
            )
            with self.subTest(mutation=name):
                with self.assertRaisesRegex(model.MatrixModelError, code):
                    model.validate_evidence_receipt(
                        changed,
                        cell,
                        checked_root,
                        attempt_id=attempt_id,
                        gate_id=gate_id,
                    )

    def test_event_and_result_schemas_publish_the_exact_receipt_contract(self):
        for path in SCHEMA_PATHS[1:3]:
            schema = model.strict_json_load(path)
            receipt = schema["$defs"]["evidence_receipt"]
            self.assertFalse(receipt["additionalProperties"], path)
            self.assertEqual(
                receipt["required"], list(model.EVIDENCE_RECEIPT_FIELDS), path
            )
            self.assertEqual(
                receipt["properties"]["schema"],
                {"const": model.EVIDENCE_RECEIPT_SCHEMA},
                path,
            )
            self.assertIn("cross-root receipts fail closed", schema["$comment"])

    def test_objective_result_is_valid_only_inside_receipt_bindings(self):
        def allows(schema, fragment, value):
            if "$ref" in fragment:
                prefix = "#/$defs/"
                self.assertTrue(fragment["$ref"].startswith(prefix))
                return allows(schema, schema["$defs"][fragment["$ref"][len(prefix) :]], value)
            if "anyOf" in fragment:
                return any(allows(schema, choice, value) for choice in fragment["anyOf"])
            if "enum" in fragment:
                return value in fragment["enum"]
            if "const" in fragment:
                return value == fragment["const"]
            self.fail(f"unsupported kind schema: {fragment!r}")

        for path in SCHEMA_PATHS[1:3]:
            schema = model.strict_json_load(path)
            definitions = schema["$defs"]
            normal_binding = definitions["evidence"]
            receipt_binding = definitions["receipt_evidence_binding"]
            self.assertEqual(
                schema["properties"]["evidence"]["items"],
                {"$ref": "#/$defs/evidence"},
                path,
            )
            self.assertEqual(
                definitions["evidence_receipt"]["properties"]["evidence"],
                {"$ref": "#/$defs/receipt_evidence_binding"},
                path,
            )
            self.assertFalse(
                allows(schema, normal_binding["properties"]["kind"], "objective-result"),
                path,
            )
            self.assertTrue(
                allows(schema, receipt_binding["properties"]["kind"], "objective-result"),
                path,
            )
            self.assertTrue(
                allows(schema, normal_binding["properties"]["kind"], "manual-verdict"),
                path,
            )
            self.assertTrue(
                allows(schema, receipt_binding["properties"]["kind"], "manual-verdict"),
                path,
            )

    def test_all_five_json_schemas_are_strict_and_versioned(self):
        for path in SCHEMA_PATHS:
            schema = model.strict_json_load(path)
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            self.assertFalse(schema["additionalProperties"], path)
            self.assertIn("schema_version", schema["required"], path)
            self.assertEqual(schema["properties"]["schema_version"], {"const": 1})

    def test_public_status_contract_requires_absolute_stable_ledger_root(self):
        schema = model.strict_json_load(SCHEMA_PATHS[-1])
        contract = schema["$comment"]
        self.assertIn("absolute ledger-root path", contract)
        self.assertIn("opens that root read-only", contract)
        self.assertIn("stable append-only snapshot", contract)
        self.assertIn("Caller-built summaries or attestations have no authority", contract)


class LedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        manifest = model.load_manifest(MATRIX_PATH)
        cells = model.expand_cells(manifest)
        cls.manifest = manifest
        cls.cells = cells
        cls.cell = next(
            cell
            for cell in cells
            if cell.identity["test_execution"] == "OBJECTIVE"
            and cell.identity["game"]["id"] == "red"
        )
        cls.manual_cell = next(
            cell
            for cell in cells
            if cell.identity["test_execution"] == "MANUAL"
        )
        cls.manual_objective_cell = next(
            cell
            for cell in cells
            if cell.identity["test_class"] == "logs-captures"
            and all(
                cell.identity[field] == cls.manual_cell.identity[field]
                for field in (
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
            )
        )
        cls.cross_game_objective_cell = next(
            cell
            for cell in cells
            if cell.identity["test_class"] == "logs-captures"
            and cell.identity["game"]["id"] == "blue"
            and all(
                cell.identity[field] == cls.manual_cell.identity[field]
                for field in (
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
                    "host",
                    "engine",
                    "tier",
                    "platform",
                    "host_mode",
                )
            )
        )

    def new_store(self):
        temporary = ScopedTestDirectory()
        self.addCleanup(temporary.cleanup)
        store = ledger.LedgerStore(Path(temporary.name) / "state")
        return store

    def begin(self, store, number=1, recovery_id=None, minute=0):
        return store.begin_attempt(
            self.cell,
            attempt_number=number,
            started_at=f"2026-08-23T12:{minute:02d}:00Z",
            owner_id="matrix-test-owner",
            recovery_id=recovery_id,
        )

    def changed_cell(self, source, mutate):
        identity = copy.deepcopy(dict(source.identity))
        mutate(identity)
        fingerprint = model.sha256_value(identity)
        return model.MatrixCell(
            cell_id=f"cell-{fingerprint}",
            input_fingerprint=fingerprint,
            identity=identity,
        )

    def evidence_pair_paths(self, store, cell, attempt_id, record):
        _, attempt_path = store._find_attempt(cell.cell_id, attempt_id)
        stem = f"{record['kind']}-{record['sha256']}"
        return (
            attempt_path / "evidence" / f"{stem}.blob",
            attempt_path / "evidence" / f"{stem}.receipt.json",
        )

    def recovery_review(
        self,
        store,
        attempt_id,
        *,
        reviewed_at="2026-08-23T12:05:00Z",
        reviewer_id="independent-reviewer",
    ):
        return store.make_recovery_review(
            self.cell,
            attempt_id,
            reviewed_at=reviewed_at,
            reviewer_id=reviewer_id,
            finding_ids=("failed-or-ambiguous-attempt",),
        )

    def staging_recovery_review(
        self,
        store,
        *,
        reviewer_id="independent-staging-reviewer",
        reviewed_at="2026-08-23T12:30:00Z",
    ):
        return store.make_staging_recovery_review(
            operator_id="matrix-test-owner",
            reviewer_id=reviewer_id,
            reviewed_at=reviewed_at,
            finding_ids=("preserved-staging",),
        )

    def publish_attempt_record(
        self,
        store,
        cell,
        *,
        attempt_number,
        started_at,
        recovery_id,
        owner_id="matrix-test-owner",
    ):
        attempt_id = model.make_attempt_id(
            cell,
            attempt_number,
            started_at,
            owner_id,
            recovery_id,
        )
        attempt_path = (
            store._cell_dir(cell.cell_id)
            / "attempts"
            / f"{attempt_number:06d}-{attempt_id}"
        )
        attempt_path.mkdir()
        (attempt_path / "events").mkdir()
        (attempt_path / "evidence").mkdir()
        record = {
            "schema": ledger.ATTEMPT_SCHEMA,
            "schema_version": 1,
            "attempt_id": attempt_id,
            "attempt_number": attempt_number,
            "cell_id": cell.cell_id,
            "input_fingerprint": cell.input_fingerprint,
            "owner_id": owner_id,
            "started_at": started_at,
            "recovery_id": recovery_id,
        }
        (attempt_path / "attempt.json").write_bytes(
            model.canonical_json_bytes(record)
        )
        return attempt_id

    def publish_recovery_record(self, store, cell, attempt_id, review):
        review_sha256 = model.sha256_value(review)
        recovery_id = store.make_recovery_id(
            cell.cell_id,
            attempt_id,
            review["reviewed_at"],
            review["reviewer_id"],
            review["failed_attempt_state_sha256"],
            review_sha256,
        )
        record = {
            "schema": ledger.RECOVERY_SCHEMA,
            "schema_version": 1,
            "recovery_id": recovery_id,
            "cell_id": cell.cell_id,
            "input_fingerprint": cell.input_fingerprint,
            "failed_attempt_id": attempt_id,
            "failed_attempt_state_sha256": review[
                "failed_attempt_state_sha256"
            ],
            "approved_at": review["reviewed_at"],
            "reviewer_id": review["reviewer_id"],
            "review_sha256": review_sha256,
            "review": review,
            "disposition": "AUTHORIZE_NEW_ATTEMPT",
        }
        path = (
            store._cell_dir(cell.cell_id)
            / "recoveries"
            / f"{recovery_id}.json"
        )
        path.write_bytes(model.canonical_json_bytes(record))
        return recovery_id

    def complete_three_attempt_chain(self, store):
        first = self.begin(store)
        self.fail_attempt(store, first)
        recovery_one = store.record_recovery(
            self.cell,
            first,
            self.recovery_review(store, first),
        )
        second = self.begin(
            store,
            number=2,
            recovery_id=recovery_one,
            minute=6,
        )
        self.fail_attempt(store, second, minute=6)
        recovery_two = store.record_recovery(
            self.cell,
            second,
            self.recovery_review(
                store,
                second,
                reviewed_at="2026-08-23T12:11:00Z",
                reviewer_id="second-independent-reviewer",
            ),
        )
        third = self.begin(
            store,
            number=3,
            recovery_id=recovery_two,
            minute=12,
        )
        self.pass_attempt(store, third, minute=12)
        return first, recovery_one, second, recovery_two, third

    def complete_objective(
        self,
        store,
        cell,
        *,
        attempt_number=1,
        recovery_id=None,
        status="PASS",
        start="2026-08-23T11:50:00Z",
        event_times=(
            "2026-08-23T11:51:00Z",
            "2026-08-23T11:52:00Z",
            "2026-08-23T11:53:00Z",
            "2026-08-23T11:54:00Z",
        ),
    ):
        attempt_id = store.begin_attempt(
            cell,
            attempt_number=attempt_number,
            started_at=start,
            owner_id="objective-runner",
            recovery_id=recovery_id,
        )
        gate_id = cell.identity["required_gate_ids"][0]
        store.append_event(
            cell,
            attempt_id,
            event_type="GATE_STARTED",
            gate_id=gate_id,
            recorded_at=event_times[0],
        )
        evidence = [
            store.record_evidence(
                cell,
                attempt_id,
                gate_id=gate_id,
                kind=kind,
                payload=f"{kind}:{attempt_id}".encode("ascii"),
            )
            for kind in cell.identity["required_evidence_kinds"]
        ]
        gate_event = "GATE_PASSED" if status == "PASS" else "GATE_FAILED"
        store.append_event(
            cell,
            attempt_id,
            event_type=gate_event,
            gate_id=gate_id,
            recorded_at=event_times[1],
            evidence=evidence if status == "PASS" else (),
        )
        store.append_event(
            cell,
            attempt_id,
            event_type="CLEANUP_PASSED",
            recorded_at=event_times[2],
        )
        terminal = "ATTEMPT_PASSED" if status == "PASS" else "ATTEMPT_FAILED"
        store.append_event(
            cell,
            attempt_id,
            event_type=terminal,
            recorded_at=event_times[3],
            evidence=evidence if status == "PASS" else (),
        )
        result = {
            "schema": model.CELL_RESULT_SCHEMA,
            "schema_version": 1,
            "cell_id": cell.cell_id,
            "input_fingerprint": cell.input_fingerprint,
            "attempt_id": attempt_id,
            "started_at": start,
            "finished_at": event_times[3],
            "status": status,
            "cleanup": "PASS",
            "objective": True,
            "evidence": evidence if status == "PASS" else [],
            "manual_verdict_sha256": None,
            "failure_code": None if status == "PASS" else "objective-gate-failed",
        }
        digest = store.record_result(cell, attempt_id, result)
        _, attempt_path = store._find_attempt(cell.cell_id, attempt_id)
        raw = (attempt_path / "result.json").read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), digest)
        return attempt_id, raw, digest

    def record_manual_pass(
        self,
        store,
        *,
        objective_raw=None,
        objective_digest=None,
        reviewed_at="2026-08-23T12:02:00Z",
    ):
        cell = self.manual_cell
        attempt_id = store.begin_attempt(
            cell,
            attempt_number=1,
            started_at="2026-08-23T12:00:00Z",
            owner_id="matrix-test-owner",
        )
        gate_id = cell.identity["required_gate_ids"][0]
        store.append_event(
            cell,
            attempt_id,
            event_type="GATE_STARTED",
            gate_id=gate_id,
            recorded_at="2026-08-23T12:01:00Z",
        )
        packet_kind = next(
            kind
            for kind in cell.identity["required_evidence_kinds"]
            if kind != "manual-verdict"
        )
        packet = store.record_evidence(
            cell,
            attempt_id,
            gate_id=gate_id,
            kind=packet_kind,
            payload=b"fixed-review-packet",
        )
        if objective_raw is not None:
            objective_record = store.record_evidence(
                cell,
                attempt_id,
                gate_id=gate_id,
                kind="objective-result",
                payload=objective_raw,
            )
            if objective_digest is not None:
                self.assertEqual(objective_record["sha256"], objective_digest)
            objective_digest = objective_record["sha256"]
        if objective_digest is None:
            objective_digest = "d" * 64
        verdict = {
            "schema": model.MANUAL_VERDICT_SCHEMA,
            "schema_version": 1,
            "cell_id": cell.cell_id,
            "input_fingerprint": cell.input_fingerprint,
            "review_packet_sha256": packet["sha256"],
            "objective_result_sha256": objective_digest,
            "reviewer_id": "reviewer-one",
            "reviewed_at": reviewed_at,
            "verdict": "PASS",
            "objective_checks_passed": True,
            "criteria": ["visual-correctness"],
        }
        verdict_record = store.record_evidence(
            cell,
            attempt_id,
            gate_id=gate_id,
            kind="manual-verdict",
            payload=model.canonical_json_bytes(verdict),
        )
        evidence = [packet, verdict_record]
        store.append_event(
            cell,
            attempt_id,
            event_type="GATE_PASSED",
            gate_id=gate_id,
            recorded_at="2026-08-23T12:02:00Z",
            evidence=evidence,
        )
        store.append_event(
            cell,
            attempt_id,
            event_type="CLEANUP_PASSED",
            recorded_at="2026-08-23T12:03:00Z",
        )
        store.append_event(
            cell,
            attempt_id,
            event_type="ATTEMPT_PASSED",
            recorded_at="2026-08-23T12:04:00Z",
            evidence=evidence,
        )
        result = {
            "schema": model.CELL_RESULT_SCHEMA,
            "schema_version": 1,
            "cell_id": cell.cell_id,
            "input_fingerprint": cell.input_fingerprint,
            "attempt_id": attempt_id,
            "started_at": "2026-08-23T12:00:00Z",
            "finished_at": "2026-08-23T12:04:00Z",
            "status": "PASS",
            "cleanup": "PASS",
            "objective": False,
            "evidence": evidence,
            "manual_verdict_sha256": verdict_record["sha256"],
            "failure_code": None,
        }
        return attempt_id, store.record_result(cell, attempt_id, result)

    @property
    def gate_id(self):
        return self.cell.identity["required_gate_ids"][0]

    def pass_terminal(self, store, attempt_id, minute=0):
        store.append_event(
            self.cell,
            attempt_id,
            event_type="GATE_STARTED",
            gate_id=self.gate_id,
            recorded_at=f"2026-08-23T12:{minute + 1:02d}:00Z",
        )
        evidence = [
            store.record_evidence(
                self.cell,
                attempt_id,
                gate_id=self.gate_id,
                kind=kind,
                payload=f"{kind}:{attempt_id}".encode("ascii"),
            )
            for kind in self.cell.identity["required_evidence_kinds"]
        ]
        store.append_event(
            self.cell,
            attempt_id,
            event_type="GATE_PASSED",
            gate_id=self.gate_id,
            recorded_at=f"2026-08-23T12:{minute + 2:02d}:00Z",
            evidence=evidence,
        )
        store.append_event(
            self.cell,
            attempt_id,
            event_type="CLEANUP_PASSED",
            recorded_at=f"2026-08-23T12:{minute + 3:02d}:00Z",
        )
        store.append_event(
            self.cell,
            attempt_id,
            event_type="ATTEMPT_PASSED",
            recorded_at=f"2026-08-23T12:{minute + 4:02d}:00Z",
            evidence=evidence,
        )
        return evidence

    def pass_attempt(self, store, attempt_id, minute=0):
        evidence = self.pass_terminal(store, attempt_id, minute)
        result = {
            "schema": model.CELL_RESULT_SCHEMA,
            "schema_version": 1,
            "cell_id": self.cell.cell_id,
            "input_fingerprint": self.cell.input_fingerprint,
            "attempt_id": attempt_id,
            "started_at": f"2026-08-23T12:{minute:02d}:00Z",
            "finished_at": f"2026-08-23T12:{minute + 4:02d}:00Z",
            "status": "PASS",
            "cleanup": "PASS",
            "objective": True,
            "evidence": evidence,
            "manual_verdict_sha256": None,
            "failure_code": None,
        }
        return store.record_result(self.cell, attempt_id, result)

    def passing_ledger_result(self, attempt_id, evidence, minute=0):
        return {
            "schema": model.CELL_RESULT_SCHEMA,
            "schema_version": 1,
            "cell_id": self.cell.cell_id,
            "input_fingerprint": self.cell.input_fingerprint,
            "attempt_id": attempt_id,
            "started_at": f"2026-08-23T12:{minute:02d}:00Z",
            "finished_at": f"2026-08-23T12:{minute + 4:02d}:00Z",
            "status": "PASS",
            "cleanup": "PASS",
            "objective": True,
            "evidence": evidence,
            "manual_verdict_sha256": None,
            "failure_code": None,
        }

    def fail_attempt(self, store, attempt_id, minute=0):
        store.append_event(
            self.cell,
            attempt_id,
            event_type="GATE_STARTED",
            gate_id=self.gate_id,
            recorded_at=f"2026-08-23T12:{minute + 1:02d}:00Z",
        )
        store.append_event(
            self.cell,
            attempt_id,
            event_type="GATE_FAILED",
            gate_id=self.gate_id,
            recorded_at=f"2026-08-23T12:{minute + 2:02d}:00Z",
        )
        store.append_event(
            self.cell,
            attempt_id,
            event_type="CLEANUP_PASSED",
            recorded_at=f"2026-08-23T12:{minute + 3:02d}:00Z",
        )
        store.append_event(
            self.cell,
            attempt_id,
            event_type="ATTEMPT_FAILED",
            recorded_at=f"2026-08-23T12:{minute + 4:02d}:00Z",
        )
        result = {
            "schema": model.CELL_RESULT_SCHEMA,
            "schema_version": 1,
            "cell_id": self.cell.cell_id,
            "input_fingerprint": self.cell.input_fingerprint,
            "attempt_id": attempt_id,
            "started_at": f"2026-08-23T12:{minute:02d}:00Z",
            "finished_at": f"2026-08-23T12:{minute + 4:02d}:00Z",
            "status": "FAIL",
            "cleanup": "PASS",
            "objective": True,
            "evidence": [],
            "manual_verdict_sha256": None,
            "failure_code": "gate-failed",
        }
        return store.record_result(self.cell, attempt_id, result)

    def test_atomic_hash_chained_pass_is_reused(self):
        store = self.new_store()
        attempt_id = self.begin(store)
        result_sha256 = self.pass_attempt(store, attempt_id)
        inspection = store.inspect_attempt(self.cell.cell_id, attempt_id)
        self.assertEqual(inspection.state, "PASS")
        self.assertEqual(inspection.event_count, 5)
        self.assertEqual(inspection.cell_result_sha256, result_sha256)
        self.assertIsNotNone(inspection.last_event_sha256)
        decision = store.resume_decision(self.cell)
        self.assertEqual(decision["action"], "REUSE_PASS")
        self.assertEqual(decision["attempt_id"], attempt_id)

        _, attempt_path = store._find_attempt(self.cell.cell_id, attempt_id)
        event_files = sorted((attempt_path / "events").iterdir())
        self.assertEqual(len(event_files), 5)
        self.assertTrue(all(path.read_bytes().endswith(b"\n") for path in event_files))
        for index, path in enumerate(event_files):
            record = model.strict_json_load(path)
            if index == 0:
                self.assertIsNone(record["previous_event_sha256"])
            else:
                prior_hash = hashlib.sha256(event_files[index - 1].read_bytes()).hexdigest()
                self.assertEqual(record["previous_event_sha256"], prior_hash)

    def test_legacy_attempt_or_result_partial_blocks_pass_reuse(self):
        for base_name in ("attempt", "result"):
            store = self.new_store()
            attempt_id = self.begin(store)
            self.pass_attempt(store, attempt_id)
            _, attempt_path = store._find_attempt(self.cell.cell_id, attempt_id)
            partial = attempt_path / f".{base_name}.json.partial-{'0' * 32}"
            partial.write_bytes(b"conflicting legacy partial\n")
            with self.subTest(base_name=base_name):
                with self.assertRaisesRegex(
                    ledger.LedgerAmbiguous, "E_LEDGER_LEGACY_PARTIAL"
                ):
                    store.inspect_attempt(self.cell.cell_id, attempt_id)
                with self.assertRaisesRegex(
                    ledger.LedgerAmbiguous, "E_LEDGER_LEGACY_PARTIAL"
                ):
                    store.resume_decision(self.cell)

    def test_pass_needs_verified_evidence_bytes_and_exact_result_commit(self):
        for mutation in ("tamper", "missing"):
            store = self.new_store()
            attempt_id = self.begin(store)
            self.pass_attempt(store, attempt_id)
            _, attempt_path = store._find_attempt(self.cell.cell_id, attempt_id)
            blob = next((attempt_path / "evidence").glob("*.blob"))
            if mutation == "tamper":
                raw = blob.read_bytes()
                blob.write_bytes((b"X" if raw[:1] != b"X" else b"Y") + raw[1:])
                code = "E_LEDGER_EVIDENCE_DIGEST"
            else:
                blob.unlink()
                code = "E_LEDGER_EVIDENCE_PAYLOAD_MISSING"
            with self.subTest(mutation=mutation):
                with self.assertRaisesRegex(ledger.LedgerAmbiguous, code):
                    store.inspect_attempt(self.cell.cell_id, attempt_id)

        store = self.new_store()
        attempt_id = self.begin(store)
        with self.assertRaisesRegex(
            ledger.LedgerConflict, "E_LEDGER_EVIDENCE_NOT_REQUIRED"
        ):
            store.record_evidence(
                self.cell,
                attempt_id,
                gate_id=self.gate_id,
                kind="unclaimed-report",
                payload=b"unclaimed",
            )
        self.pass_attempt(store, attempt_id)

    def test_record_evidence_requires_the_exact_open_required_gate(self):
        store = self.new_store()
        attempt_id = self.begin(store)
        required_kind = self.cell.identity["required_evidence_kinds"][0]
        with self.assertRaisesRegex(
            ledger.LedgerConflict, "E_LEDGER_EVIDENCE_GATE_NOT_OPEN"
        ):
            store.record_evidence(
                self.cell,
                attempt_id,
                gate_id=self.gate_id,
                kind=required_kind,
                payload=b"synthetic-before-open",
            )
        with self.assertRaisesRegex(
            ledger.LedgerConflict, "E_LEDGER_EVIDENCE_GATE_NOT_REQUIRED"
        ):
            store.record_evidence(
                self.cell,
                attempt_id,
                gate_id="other-gate",
                kind=required_kind,
                payload=b"synthetic-wrong-gate",
            )
        store.append_event(
            self.cell,
            attempt_id,
            event_type="GATE_STARTED",
            gate_id=self.gate_id,
            recorded_at="2026-08-23T12:01:00Z",
        )
        record = store.record_evidence(
            self.cell,
            attempt_id,
            gate_id=self.gate_id,
            kind=required_kind,
            payload=b"synthetic-open-gate",
        )
        self.assertEqual(tuple(record), model.EVIDENCE_BINDING_FIELDS)
        blob_path, receipt_path = self.evidence_pair_paths(
            store, self.cell, attempt_id, record
        )
        self.assertEqual(blob_path.read_bytes(), b"synthetic-open-gate")
        receipt = model.strict_json_load(receipt_path)
        self.assertEqual(receipt["evidence"], record)
        self.assertEqual(receipt["ledger_root_id"], store.ledger_root_id)
        self.assertEqual(receipt_path.read_bytes(), model.canonical_json_bytes(receipt))
        store.append_event(
            self.cell,
            attempt_id,
            event_type="GATE_PASSED",
            gate_id=self.gate_id,
            recorded_at="2026-08-23T12:02:00Z",
            evidence=[record],
        )
        with self.assertRaisesRegex(
            ledger.LedgerConflict, "E_LEDGER_EVIDENCE_GATE_NOT_OPEN"
        ):
            store.record_evidence(
                self.cell,
                attempt_id,
                gate_id=self.gate_id,
                kind=required_kind,
                payload=b"synthetic-after-close",
            )

    def test_bad_bound_payload_hash_and_size_are_rejected_before_gate_pass(self):
        for mutation in ("hash", "size"):
            store = self.new_store()
            attempt_id = self.begin(store)
            store.append_event(
                self.cell,
                attempt_id,
                event_type="GATE_STARTED",
                gate_id=self.gate_id,
                recorded_at="2026-08-23T12:01:00Z",
            )
            kind = self.cell.identity["required_evidence_kinds"][0]
            record = store.record_evidence(
                self.cell,
                attempt_id,
                gate_id=self.gate_id,
                kind=kind,
                payload=b"synthetic-payload",
            )
            forged = model.make_evidence_binding(
                self.cell,
                attempt_id,
                self.gate_id,
                kind,
                "0" * 64 if mutation == "hash" else record["sha256"],
                record["bytes"] + 1 if mutation == "size" else record["bytes"],
            )
            code = (
                "E_LEDGER_EVIDENCE_MISSING"
                if mutation == "hash"
                else "E_LEDGER_EVIDENCE_RECEIPT_MISMATCH"
            )
            with self.subTest(mutation=mutation):
                with self.assertRaisesRegex(ledger.LedgerAmbiguous, code):
                    store.append_event(
                        self.cell,
                        attempt_id,
                        event_type="GATE_PASSED",
                        gate_id=self.gate_id,
                        recorded_at="2026-08-23T12:02:00Z",
                        evidence=[forged],
                    )
            self.assertEqual(
                store.inspect_attempt(self.cell.cell_id, attempt_id).state,
                "AMBIGUOUS",
            )

    def test_old_three_field_evidence_requires_reviewed_recovery(self):
        store = self.new_store()
        attempt_id = self.begin(store)
        self.pass_terminal(store, attempt_id)
        _, attempt_path = store._find_attempt(self.cell.cell_id, attempt_id)
        gate_event_path = sorted((attempt_path / "events").iterdir())[1]
        event = model.strict_json_load(gate_event_path)
        bound = event["evidence"][0]
        event["evidence"][0] = {
            "kind": bound["kind"],
            "sha256": bound["sha256"],
            "bytes": bound["bytes"],
        }
        gate_event_path.write_bytes(model.canonical_json_bytes(event))
        with self.assertRaisesRegex(
            ledger.LedgerAmbiguous, "E_LEDGER_EVIDENCE_FIELDS"
        ):
            store.inspect_attempt(self.cell.cell_id, attempt_id)
        decision = store.resume_decision(self.cell)
        self.assertEqual(decision["action"], "RECOVERY_REQUIRED")
        self.assertEqual(decision["state"], "AMBIGUOUS")

    def test_copied_raw_blob_and_record_cannot_pass_cross_game_or_be_ready(self):
        source = self.cell
        target = next(
            cell
            for cell in self.cells
            if cell.identity["game"]["id"] == "blue"
            and all(
                cell.identity[key] == source.identity[key]
                for key in source.identity
                if key != "game"
            )
        )
        store = self.new_store()
        source_attempt = store.begin_attempt(
            source,
            attempt_number=1,
            started_at="2026-08-23T12:00:00Z",
            owner_id="synthetic-source-owner",
        )
        source_gate = source.identity["required_gate_ids"][0]
        store.append_event(
            source,
            source_attempt,
            event_type="GATE_STARTED",
            gate_id=source_gate,
            recorded_at="2026-08-23T12:01:00Z",
        )
        kind = source.identity["required_evidence_kinds"][0]
        source_record = store.record_evidence(
            source,
            source_attempt,
            gate_id=source_gate,
            kind=kind,
            payload=b"synthetic-cross-game-payload",
        )
        _, source_path = store._find_attempt(source.cell_id, source_attempt)
        source_blob = next((source_path / "evidence").glob("*.blob"))

        target_attempt = store.begin_attempt(
            target,
            attempt_number=1,
            started_at="2026-08-23T12:00:00Z",
            owner_id="synthetic-target-owner",
        )
        target_gate = target.identity["required_gate_ids"][0]
        store.append_event(
            target,
            target_attempt,
            event_type="GATE_STARTED",
            gate_id=target_gate,
            recorded_at="2026-08-23T12:01:00Z",
        )
        _, target_path = store._find_attempt(target.cell_id, target_attempt)
        with self.assertRaisesRegex(
            ledger.LedgerAmbiguous, "E_LEDGER_EVIDENCE_CELL_BINDING"
        ):
            store.append_event(
                target,
                target_attempt,
                event_type="GATE_PASSED",
                gate_id=target_gate,
                recorded_at="2026-08-23T12:02:00Z",
                evidence=[source_record],
            )
        shutil.copyfile(source_blob, target_path / "evidence" / source_blob.name)
        recomputed = model.make_evidence_binding(
            target,
            target_attempt,
            target_gate,
            kind,
            source_record["sha256"],
            source_record["bytes"],
        )
        with self.assertRaisesRegex(
            ledger.LedgerAmbiguous, "E_LEDGER_EVIDENCE_RECEIPT_MISSING"
        ):
            store.append_event(
                target,
                target_attempt,
                event_type="GATE_PASSED",
                gate_id=target_gate,
                recorded_at="2026-08-23T12:02:00Z",
                evidence=[recomputed],
            )
        with self.assertRaisesRegex(
            ledger.LedgerAmbiguous, "E_LEDGER_EVIDENCE_RECEIPT_MISSING"
        ):
            store.inspect_attempt(target.cell_id, target_attempt)
        decision = store.resume_decision(target)
        self.assertEqual(decision["action"], "RECOVERY_REQUIRED")
        self.assertEqual(decision["state"], "AMBIGUOUS")
        result_set = store.validated_result_set(self.manifest)
        status = public_status(self.manifest, result_set)
        self.assertEqual(status["readiness"], "NOT_READY")
        self.assertEqual(
            model.validate_public_status(status, self.manifest, store.root), status
        )
        forged_ready = copy.deepcopy(status)
        forged_ready["readiness"] = "READY"
        forged_ready["blockers"] = []
        with self.assertRaisesRegex(model.MatrixModelError, "E_PUBLIC_READINESS"):
            model.validate_public_status(forged_ready, self.manifest, store.root)

    def test_copied_pair_and_recomputed_binding_fail_across_every_dimension(self):
        red = self.cell
        blue = self.changed_cell(
            red, lambda identity: identity["game"].update(id="blue")
        )
        cases = (
            ("red-to-blue", red, blue),
            ("blue-to-red", blue, red),
            (
                "host",
                red,
                self.changed_cell(
                    red, lambda identity: identity["host"].update(id="other-host")
                ),
            ),
            (
                "engine",
                red,
                self.changed_cell(
                    red,
                    lambda identity: identity["engine"].update(id="other-engine"),
                ),
            ),
            (
                "tier",
                red,
                self.changed_cell(
                    red, lambda identity: identity.update(tier="other-tier")
                ),
            ),
            (
                "platform",
                red,
                self.changed_cell(
                    red,
                    lambda identity: identity["platform"].update(
                        id="other-platform"
                    ),
                ),
            ),
            (
                "runtime-source",
                red,
                self.changed_cell(
                    red,
                    lambda identity: identity.update(
                        runtime_source_commit="0" * 40
                    ),
                ),
            ),
            (
                "runtime-tree",
                red,
                self.changed_cell(
                    red,
                    lambda identity: identity.update(runtime_source_tree="1" * 40),
                ),
            ),
            (
                "runtime-content",
                red,
                self.changed_cell(
                    red,
                    lambda identity: identity.update(
                        runtime_content_sha256="2" * 64
                    ),
                ),
            ),
            (
                "package",
                red,
                self.changed_cell(
                    red,
                    lambda identity: identity.update(package_sha256="3" * 64),
                ),
            ),
        )
        for name, source, target in cases:
            store = self.new_store()
            source_attempt = store.begin_attempt(
                source,
                attempt_number=1,
                started_at="2026-08-23T12:00:00Z",
                owner_id="source-owner",
            )
            source_gate = source.identity["required_gate_ids"][0]
            source_kind = source.identity["required_evidence_kinds"][0]
            store.append_event(
                source,
                source_attempt,
                event_type="GATE_STARTED",
                gate_id=source_gate,
                recorded_at="2026-08-23T12:01:00Z",
            )
            source_record = store.record_evidence(
                source,
                source_attempt,
                gate_id=source_gate,
                kind=source_kind,
                payload=b"synthetic-dimension-replay",
            )
            source_blob, source_receipt = self.evidence_pair_paths(
                store, source, source_attempt, source_record
            )

            target_attempt = store.begin_attempt(
                target,
                attempt_number=1,
                started_at="2026-08-23T12:00:00Z",
                owner_id="target-owner",
            )
            target_gate = target.identity["required_gate_ids"][0]
            target_kind = target.identity["required_evidence_kinds"][0]
            store.append_event(
                target,
                target_attempt,
                event_type="GATE_STARTED",
                gate_id=target_gate,
                recorded_at="2026-08-23T12:01:00Z",
            )
            target_blob, target_receipt = self.evidence_pair_paths(
                store,
                target,
                target_attempt,
                {
                    "kind": target_kind,
                    "sha256": source_record["sha256"],
                },
            )
            shutil.copyfile(source_blob, target_blob)
            shutil.copyfile(source_receipt, target_receipt)
            recomputed = model.make_evidence_binding(
                target,
                target_attempt,
                target_gate,
                target_kind,
                source_record["sha256"],
                source_record["bytes"],
            )
            with self.subTest(dimension=name):
                with self.assertRaisesRegex(
                    ledger.LedgerAmbiguous,
                    "E_LEDGER_EVIDENCE_RECEIPT_BINDING",
                ):
                    store.append_event(
                        target,
                        target_attempt,
                        event_type="GATE_PASSED",
                        gate_id=target_gate,
                        recorded_at="2026-08-23T12:02:00Z",
                        evidence=[recomputed],
                    )
                with self.assertRaisesRegex(
                    ledger.LedgerAmbiguous,
                    "E_LEDGER_EVIDENCE_RECEIPT_BINDING",
                ):
                    store.inspect_attempt(target.cell_id, target_attempt)
                decision = store.resume_decision(target)
                self.assertEqual(decision["action"], "RECOVERY_REQUIRED")
                self.assertEqual(decision["state"], "AMBIGUOUS")

    def test_receipt_rejects_cross_root_attempt_gate_and_kind_replay(self):
        cell = self.cell
        source_store = self.new_store()
        target_store = self.new_store()
        source_attempt = self.begin(source_store)
        target_attempt = self.begin(target_store)
        self.assertEqual(source_attempt, target_attempt)
        for store, attempt_id in (
            (source_store, source_attempt),
            (target_store, target_attempt),
        ):
            store.append_event(
                cell,
                attempt_id,
                event_type="GATE_STARTED",
                gate_id=self.gate_id,
                recorded_at="2026-08-23T12:01:00Z",
            )
        record = source_store.record_evidence(
            cell,
            source_attempt,
            gate_id=self.gate_id,
            kind=cell.identity["required_evidence_kinds"][0],
            payload=b"synthetic-cross-root",
        )
        source_pair = self.evidence_pair_paths(
            source_store, cell, source_attempt, record
        )
        target_pair = self.evidence_pair_paths(
            target_store, cell, target_attempt, record
        )
        for source_path, target_path in zip(source_pair, target_pair):
            shutil.copyfile(source_path, target_path)
        with self.assertRaisesRegex(
            ledger.LedgerAmbiguous, "E_LEDGER_EVIDENCE_RECEIPT_ROOT"
        ):
            target_store.append_event(
                cell,
                target_attempt,
                event_type="GATE_PASSED",
                gate_id=self.gate_id,
                recorded_at="2026-08-23T12:02:00Z",
                evidence=[record],
            )

        attempt_store = self.new_store()
        first = self.begin(attempt_store)
        attempt_store.append_event(
            cell,
            first,
            event_type="GATE_STARTED",
            gate_id=self.gate_id,
            recorded_at="2026-08-23T12:01:00Z",
        )
        first_record = attempt_store.record_evidence(
            cell,
            first,
            gate_id=self.gate_id,
            kind=cell.identity["required_evidence_kinds"][0],
            payload=b"synthetic-attempt-replay",
        )
        first_pair = self.evidence_pair_paths(
            attempt_store, cell, first, first_record
        )
        attempt_store.append_event(
            cell,
            first,
            event_type="GATE_FAILED",
            gate_id=self.gate_id,
            recorded_at="2026-08-23T12:02:00Z",
        )
        attempt_store.append_event(
            cell,
            first,
            event_type="CLEANUP_PASSED",
            recorded_at="2026-08-23T12:03:00Z",
        )
        attempt_store.append_event(
            cell,
            first,
            event_type="ATTEMPT_FAILED",
            recorded_at="2026-08-23T12:04:00Z",
        )
        attempt_store.record_result(
            cell,
            first,
            {
                "schema": model.CELL_RESULT_SCHEMA,
                "schema_version": 1,
                "cell_id": cell.cell_id,
                "input_fingerprint": cell.input_fingerprint,
                "attempt_id": first,
                "started_at": "2026-08-23T12:00:00Z",
                "finished_at": "2026-08-23T12:04:00Z",
                "status": "FAIL",
                "cleanup": "PASS",
                "objective": True,
                "evidence": [],
                "manual_verdict_sha256": None,
                "failure_code": "synthetic-failure",
            },
        )
        recovery = attempt_store.record_recovery(
            cell,
            first,
            self.recovery_review(attempt_store, first),
        )
        second = self.begin(
            attempt_store,
            number=2,
            recovery_id=recovery,
            minute=6,
        )
        attempt_store.append_event(
            cell,
            second,
            event_type="GATE_STARTED",
            gate_id=self.gate_id,
            recorded_at="2026-08-23T12:07:00Z",
        )
        second_pair = self.evidence_pair_paths(
            attempt_store, cell, second, first_record
        )
        for source_path, target_path in zip(first_pair, second_pair):
            shutil.copyfile(source_path, target_path)
        recomputed_attempt = model.make_evidence_binding(
            cell,
            second,
            self.gate_id,
            first_record["kind"],
            first_record["sha256"],
            first_record["bytes"],
        )
        with self.assertRaisesRegex(
            ledger.LedgerAmbiguous, "E_LEDGER_EVIDENCE_RECEIPT_BINDING"
        ):
            attempt_store.append_event(
                cell,
                second,
                event_type="GATE_PASSED",
                gate_id=self.gate_id,
                recorded_at="2026-08-23T12:08:00Z",
                evidence=[recomputed_attempt],
            )

        two_gate_cell = self.changed_cell(
            cell,
            lambda identity: identity.update(
                required_gate_ids=["gate-one", "gate-two"]
            ),
        )
        gate_store = self.new_store()
        gate_attempt = gate_store.begin_attempt(
            two_gate_cell,
            attempt_number=1,
            started_at="2026-08-23T12:00:00Z",
            owner_id="gate-owner",
        )
        gate_store.append_event(
            two_gate_cell,
            gate_attempt,
            event_type="GATE_STARTED",
            gate_id="gate-one",
            recorded_at="2026-08-23T12:01:00Z",
        )
        gate_record = gate_store.record_evidence(
            two_gate_cell,
            gate_attempt,
            gate_id="gate-one",
            kind=two_gate_cell.identity["required_evidence_kinds"][0],
            payload=b"synthetic-gate-replay",
        )
        gate_store.append_event(
            two_gate_cell,
            gate_attempt,
            event_type="GATE_PASSED",
            gate_id="gate-one",
            recorded_at="2026-08-23T12:02:00Z",
            evidence=[gate_record],
        )
        gate_store.append_event(
            two_gate_cell,
            gate_attempt,
            event_type="GATE_STARTED",
            gate_id="gate-two",
            recorded_at="2026-08-23T12:03:00Z",
        )
        recomputed_gate = model.make_evidence_binding(
            two_gate_cell,
            gate_attempt,
            "gate-two",
            gate_record["kind"],
            gate_record["sha256"],
            gate_record["bytes"],
        )
        with self.assertRaisesRegex(
            ledger.LedgerAmbiguous, "E_LEDGER_EVIDENCE_RECEIPT_BINDING"
        ):
            gate_store.append_event(
                two_gate_cell,
                gate_attempt,
                event_type="GATE_PASSED",
                gate_id="gate-two",
                recorded_at="2026-08-23T12:04:00Z",
                evidence=[recomputed_gate],
            )

        first_kind = cell.identity["required_evidence_kinds"][0]
        second_kind = "second-synthetic-report"
        two_kind_cell = self.changed_cell(
            cell,
            lambda identity: identity.update(
                required_evidence_kinds=[first_kind, second_kind]
            ),
        )
        kind_store = self.new_store()
        kind_attempt = kind_store.begin_attempt(
            two_kind_cell,
            attempt_number=1,
            started_at="2026-08-23T12:00:00Z",
            owner_id="kind-owner",
        )
        kind_gate = two_kind_cell.identity["required_gate_ids"][0]
        kind_store.append_event(
            two_kind_cell,
            kind_attempt,
            event_type="GATE_STARTED",
            gate_id=kind_gate,
            recorded_at="2026-08-23T12:01:00Z",
        )
        kind_record = kind_store.record_evidence(
            two_kind_cell,
            kind_attempt,
            gate_id=kind_gate,
            kind=first_kind,
            payload=b"synthetic-kind-replay",
        )
        kind_source_pair = self.evidence_pair_paths(
            kind_store, two_kind_cell, kind_attempt, kind_record
        )
        kind_target_pair = self.evidence_pair_paths(
            kind_store,
            two_kind_cell,
            kind_attempt,
            {"kind": second_kind, "sha256": kind_record["sha256"]},
        )
        for source_path, target_path in zip(kind_source_pair, kind_target_pair):
            shutil.copyfile(source_path, target_path)
        recomputed_kind = model.make_evidence_binding(
            two_kind_cell,
            kind_attempt,
            kind_gate,
            second_kind,
            kind_record["sha256"],
            kind_record["bytes"],
        )
        with self.assertRaisesRegex(
            ledger.LedgerAmbiguous, "E_LEDGER_EVIDENCE_RECEIPT_PATH"
        ):
            kind_store.append_event(
                two_kind_cell,
                kind_attempt,
                event_type="GATE_PASSED",
                gate_id=kind_gate,
                recorded_at="2026-08-23T12:02:00Z",
                evidence=[kind_record, recomputed_kind],
            )

    def test_receipt_missing_legacy_malformed_tampered_and_overwritten_fail_closed(self):
        mutations = (
            (
                "missing",
                lambda path, receipt, store, attempt: path.unlink(),
                "E_LEDGER_EVIDENCE_RECEIPT_MISSING",
            ),
            (
                "legacy",
                lambda path, receipt, store, attempt: path.write_bytes(
                    model.canonical_json_bytes(receipt["evidence"])
                ),
                "E_LEDGER_EVIDENCE_RECEIPT_FIELDS",
            ),
            (
                "malformed",
                lambda path, receipt, store, attempt: path.write_bytes(b"{\n"),
                "E_LEDGER_EVIDENCE_RECEIPT_MALFORMED",
            ),
            (
                "extra-field",
                lambda path, receipt, store, attempt: (
                    receipt.update(extra="forbidden"),
                    path.write_bytes(model.canonical_json_bytes(receipt)),
                ),
                "E_LEDGER_EVIDENCE_RECEIPT_FIELDS",
            ),
            (
                "tampered-binding",
                lambda path, receipt, store, attempt: (
                    receipt["evidence"].update(bytes=receipt["evidence"]["bytes"] + 1),
                    path.write_bytes(model.canonical_json_bytes(receipt)),
                ),
                "E_LEDGER_EVIDENCE_RECEIPT_BINDING",
            ),
            (
                "tampered-receipt-digest",
                lambda path, receipt, store, attempt: (
                    receipt.update(receipt_sha256="0" * 64),
                    path.write_bytes(model.canonical_json_bytes(receipt)),
                ),
                "E_LEDGER_EVIDENCE_RECEIPT_DIGEST",
            ),
            (
                "overwritten-valid-receipt",
                lambda path, receipt, store, attempt: path.write_bytes(
                    model.canonical_json_bytes(
                        model.make_evidence_receipt(
                            model.make_evidence_binding(
                                self.cell,
                                attempt,
                                self.gate_id,
                                receipt["evidence"]["kind"],
                                receipt["evidence"]["sha256"],
                                receipt["evidence"]["bytes"] + 1,
                            ),
                            self.cell,
                            store.ledger_root_id,
                            attempt_id=attempt,
                            gate_id=self.gate_id,
                        )
                    )
                ),
                "E_LEDGER_EVIDENCE_RECEIPT_MISMATCH",
            ),
        )
        for name, mutate, code in mutations:
            store = self.new_store()
            attempt_id = self.begin(store)
            self.pass_attempt(store, attempt_id)
            _, attempt_path = store._find_attempt(self.cell.cell_id, attempt_id)
            result = model.strict_json_load(attempt_path / "result.json")
            record = result["evidence"][0]
            _, receipt_path = self.evidence_pair_paths(
                store, self.cell, attempt_id, record
            )
            receipt = model.strict_json_load(receipt_path)
            mutate(receipt_path, receipt, store, attempt_id)
            with self.subTest(mutation=name, consumer="inspection"):
                with self.assertRaisesRegex(ledger.LedgerAmbiguous, code):
                    store.inspect_attempt(self.cell.cell_id, attempt_id)
            decision = store.resume_decision(self.cell)
            self.assertEqual(decision["action"], "RECOVERY_REQUIRED")
            self.assertEqual(decision["state"], "AMBIGUOUS")
            if name == "overwritten-valid-receipt":
                result_set = store.validated_result_set(self.manifest)
                self.assertGreaterEqual(
                    dict(result_set.status_counts)["AMBIGUOUS"], 1
                )
                self.assertEqual(
                    public_status(self.manifest, result_set)["readiness"],
                    "NOT_READY",
                )

    def test_result_validation_requires_the_original_first_store_receipt(self):
        store = self.new_store()
        attempt_id = self.begin(store)
        evidence = self.pass_terminal(store, attempt_id)
        _, receipt_path = self.evidence_pair_paths(
            store, self.cell, attempt_id, evidence[0]
        )
        replacement_binding = model.make_evidence_binding(
            self.cell,
            attempt_id,
            self.gate_id,
            evidence[0]["kind"],
            evidence[0]["sha256"],
            evidence[0]["bytes"] + 1,
        )
        receipt_path.write_bytes(
            model.canonical_json_bytes(
                model.make_evidence_receipt(
                    replacement_binding,
                    self.cell,
                    store.ledger_root_id,
                    attempt_id=attempt_id,
                    gate_id=self.gate_id,
                )
            )
        )
        with self.assertRaisesRegex(
            ledger.LedgerAmbiguous,
            "E_LEDGER_EVIDENCE_RECEIPT_MISMATCH",
        ):
            store.record_result(
                self.cell,
                attempt_id,
                self.passing_ledger_result(attempt_id, evidence),
            )
        self.assertFalse(
            (store._find_attempt(self.cell.cell_id, attempt_id)[1] / "result.json").exists()
        )

    def test_interrupted_evidence_pair_publish_is_preserved_and_fail_closed(self):
        store = self.new_store()
        attempt_id = self.begin(store)
        store.append_event(
            self.cell,
            attempt_id,
            event_type="GATE_STARTED",
            gate_id=self.gate_id,
            recorded_at="2026-08-23T12:01:00Z",
        )
        real_link = ledger.os.link

        def fail_payload_link(source, target):
            if str(target).endswith(".blob"):
                raise OSError("injected payload publication failure")
            return real_link(source, target)

        with mock.patch.object(ledger.os, "link", side_effect=fail_payload_link):
            with self.assertRaisesRegex(
                ledger.LedgerAmbiguous, "E_LEDGER_ATOMIC_CREATE"
            ):
                store.record_evidence(
                    self.cell,
                    attempt_id,
                    gate_id=self.gate_id,
                    kind=self.cell.identity["required_evidence_kinds"][0],
                    payload=b"synthetic-interrupted-pair",
                )
        self.assertTrue(list(store.staging_root.glob("*.partial")))
        with self.assertRaisesRegex(
            ledger.LedgerAmbiguous, "E_LEDGER_STAGING_NOT_EMPTY"
        ):
            store.inspect_attempt(self.cell.cell_id, attempt_id)
        store.resolve_staging(self.staging_recovery_review(store))
        with self.assertRaisesRegex(
            ledger.LedgerAmbiguous, "E_LEDGER_EVIDENCE_PAYLOAD_MISSING"
        ):
            store.inspect_attempt(self.cell.cell_id, attempt_id)
        decision = store.resume_decision(self.cell)
        self.assertEqual(decision["action"], "RECOVERY_REQUIRED")
        self.assertEqual(decision["state"], "AMBIGUOUS")

    def test_terminal_without_result_is_ambiguous_and_needs_recovery(self):
        store = self.new_store()
        attempt_id = self.begin(store)
        self.pass_terminal(store, attempt_id)
        inspection = store.inspect_attempt(self.cell.cell_id, attempt_id)
        self.assertEqual(inspection.state, "AMBIGUOUS")
        self.assertEqual(inspection.terminal_event, "ATTEMPT_PASSED")
        self.assertIsNone(inspection.cell_result_sha256)
        self.assertEqual(store.resume_decision(self.cell)["action"], "RECOVERY_REQUIRED")

    def test_result_must_match_attempt_time_status_and_evidence(self):
        mutations = {
            "attempt": (
                lambda result: result.update(attempt_id="attempt-" + "0" * 64),
                "E_LEDGER_RESULT_MODEL",
            ),
            "start": (
                lambda result: result.update(started_at="2026-08-23T11:59:59Z"),
                "E_LEDGER_RESULT_BINDING",
            ),
            "finish": (
                lambda result: result.update(finished_at="2026-08-23T12:04:01Z"),
                "E_LEDGER_RESULT_BINDING",
            ),
            "status": (
                lambda result: result.update(
                    status="FAIL", failure_code="wrong-terminal"
                ),
                "E_LEDGER_RESULT_BINDING",
            ),
            "evidence": (
                lambda result: result["evidence"][0].update(sha256="0" * 64),
                "E_LEDGER_RESULT_MODEL",
            ),
        }
        for name, (mutate, code) in mutations.items():
            store = self.new_store()
            attempt_id = self.begin(store)
            evidence = self.pass_terminal(store, attempt_id)
            result = self.passing_ledger_result(attempt_id, evidence)
            mutate(result)
            with self.subTest(mutation=name):
                with self.assertRaisesRegex(
                    ledger.LedgerConflict, code
                ):
                    store.record_result(self.cell, attempt_id, result)

    def test_result_byte_tamper_breaks_result_commit_hash(self):
        store = self.new_store()
        attempt_id = self.begin(store)
        self.fail_attempt(store, attempt_id)
        _, attempt_path = store._find_attempt(self.cell.cell_id, attempt_id)
        result_path = attempt_path / "result.json"
        result = model.strict_json_load(result_path)
        result["failure_code"] = "different-failure"
        result_path.write_bytes(model.canonical_json_bytes(result))
        with self.assertRaisesRegex(ledger.LedgerAmbiguous, "E_LEDGER_RESULT_COMMIT"):
            store.inspect_attempt(self.cell.cell_id, attempt_id)

    def test_interrupted_result_commit_cannot_be_repaired_inside_attempt(self):
        store = self.new_store()
        attempt_id = self.begin(store)
        evidence = self.pass_terminal(store, attempt_id)
        result = self.passing_ledger_result(attempt_id, evidence)
        with mock.patch.object(
            store,
            "_append_event",
            side_effect=ledger.LedgerAmbiguous("E_INJECTED_RESULT_COMMIT"),
        ):
            with self.assertRaisesRegex(
                ledger.LedgerAmbiguous, "E_INJECTED_RESULT_COMMIT"
            ):
                store.record_result(self.cell, attempt_id, result)
        self.assertEqual(
            store.inspect_attempt(self.cell.cell_id, attempt_id).state,
            "AMBIGUOUS",
        )
        with self.assertRaisesRegex(
            ledger.LedgerError, "E_LEDGER_RESULT_COMMIT_INTERNAL"
        ):
            store.append_event(
                self.cell,
                attempt_id,
                event_type="RESULT_COMMITTED",
                recorded_at="2026-08-23T12:04:00Z",
                cell_result_sha256="a" * 64,
            )
        self.assertEqual(store.resume_decision(self.cell)["action"], "RECOVERY_REQUIRED")

    def test_manual_pass_requires_canonical_matching_verdict_bytes(self):
        for verdict_payload in (b"arbitrary-verdict", "FAIL", "WRONG_PACKET"):
            store = self.new_store()
            cell = self.manual_cell
            attempt_id = store.begin_attempt(
                cell,
                attempt_number=1,
                started_at="2026-08-23T12:00:00Z",
                owner_id="matrix-test-owner",
            )
            gate_id = cell.identity["required_gate_ids"][0]
            store.append_event(
                cell,
                attempt_id,
                event_type="GATE_STARTED",
                gate_id=gate_id,
                recorded_at="2026-08-23T12:01:00Z",
            )
            packet_kind = next(
                kind
                for kind in cell.identity["required_evidence_kinds"]
                if kind != "manual-verdict"
            )
            packet = store.record_evidence(
                cell,
                attempt_id,
                gate_id=gate_id,
                kind=packet_kind,
                payload=b"fixed-review-packet",
            )
            if verdict_payload in ("FAIL", "WRONG_PACKET"):
                verdict = {
                    "schema": model.MANUAL_VERDICT_SCHEMA,
                    "schema_version": 1,
                    "cell_id": cell.cell_id,
                    "input_fingerprint": cell.input_fingerprint,
                    "review_packet_sha256": (
                        "c" * 64
                        if verdict_payload == "WRONG_PACKET"
                        else packet["sha256"]
                    ),
                    "objective_result_sha256": "d" * 64,
                    "reviewer_id": "reviewer-one",
                    "reviewed_at": "2026-08-23T12:03:00Z",
                    "verdict": "FAIL" if verdict_payload == "FAIL" else "PASS",
                    "objective_checks_passed": True,
                    "criteria": ["visual-correctness"],
                }
                raw_verdict = model.canonical_json_bytes(verdict)
            else:
                raw_verdict = verdict_payload
            verdict_record = store.record_evidence(
                cell,
                attempt_id,
                gate_id=gate_id,
                kind="manual-verdict",
                payload=raw_verdict,
            )
            evidence = [packet, verdict_record]
            store.append_event(
                cell,
                attempt_id,
                event_type="GATE_PASSED",
                gate_id=gate_id,
                recorded_at="2026-08-23T12:02:00Z",
                evidence=evidence,
            )
            store.append_event(
                cell,
                attempt_id,
                event_type="CLEANUP_PASSED",
                recorded_at="2026-08-23T12:03:00Z",
            )
            store.append_event(
                cell,
                attempt_id,
                event_type="ATTEMPT_PASSED",
                recorded_at="2026-08-23T12:04:00Z",
                evidence=evidence,
            )
            result = {
                "schema": model.CELL_RESULT_SCHEMA,
                "schema_version": 1,
                "cell_id": cell.cell_id,
                "input_fingerprint": cell.input_fingerprint,
                "attempt_id": attempt_id,
                "started_at": "2026-08-23T12:00:00Z",
                "finished_at": "2026-08-23T12:04:00Z",
                "status": "PASS",
                "cleanup": "PASS",
                "objective": False,
                "evidence": evidence,
                "manual_verdict_sha256": verdict_record["sha256"],
                "failure_code": None,
            }
            with self.subTest(verdict=verdict_payload):
                with self.assertRaisesRegex(
                    ledger.LedgerConflict, "E_LEDGER_RESULT_EVIDENCE"
                ):
                    store.record_result(cell, attempt_id, result)

    def test_canonical_manual_pass_can_be_committed_and_reused(self):
        store = self.new_store()
        cell = self.manual_cell
        _, objective_raw, objective_digest = self.complete_objective(
            store, self.manual_objective_cell
        )
        attempt_id = store.begin_attempt(
            cell,
            attempt_number=1,
            started_at="2026-08-23T12:00:00Z",
            owner_id="matrix-test-owner",
        )
        gate_id = cell.identity["required_gate_ids"][0]
        store.append_event(
            cell,
            attempt_id,
            event_type="GATE_STARTED",
            gate_id=gate_id,
            recorded_at="2026-08-23T12:01:00Z",
        )
        packet_kind = next(
            kind
            for kind in cell.identity["required_evidence_kinds"]
            if kind != "manual-verdict"
        )
        packet = store.record_evidence(
            cell,
            attempt_id,
            gate_id=gate_id,
            kind=packet_kind,
            payload=b"fixed-review-packet",
        )
        objective_record = store.record_evidence(
            cell,
            attempt_id,
            gate_id=gate_id,
            kind="objective-result",
            payload=objective_raw,
        )
        self.assertEqual(objective_record["sha256"], objective_digest)
        verdict = {
            "schema": model.MANUAL_VERDICT_SCHEMA,
            "schema_version": 1,
            "cell_id": cell.cell_id,
            "input_fingerprint": cell.input_fingerprint,
            "review_packet_sha256": packet["sha256"],
            "objective_result_sha256": objective_digest,
            "reviewer_id": "reviewer-one",
            "reviewed_at": "2026-08-23T12:02:00Z",
            "verdict": "PASS",
            "objective_checks_passed": True,
            "criteria": ["visual-correctness"],
        }
        verdict_record = store.record_evidence(
            cell,
            attempt_id,
            gate_id=gate_id,
            kind="manual-verdict",
            payload=model.canonical_json_bytes(verdict),
        )
        evidence = [packet, verdict_record]
        store.append_event(
            cell,
            attempt_id,
            event_type="GATE_PASSED",
            gate_id=gate_id,
            recorded_at="2026-08-23T12:02:00Z",
            evidence=evidence,
        )
        store.append_event(
            cell,
            attempt_id,
            event_type="CLEANUP_PASSED",
            recorded_at="2026-08-23T12:03:00Z",
        )
        store.append_event(
            cell,
            attempt_id,
            event_type="ATTEMPT_PASSED",
            recorded_at="2026-08-23T12:04:00Z",
            evidence=evidence,
        )
        result = {
            "schema": model.CELL_RESULT_SCHEMA,
            "schema_version": 1,
            "cell_id": cell.cell_id,
            "input_fingerprint": cell.input_fingerprint,
            "attempt_id": attempt_id,
            "started_at": "2026-08-23T12:00:00Z",
            "finished_at": "2026-08-23T12:04:00Z",
            "status": "PASS",
            "cleanup": "PASS",
            "objective": False,
            "evidence": evidence,
            "manual_verdict_sha256": verdict_record["sha256"],
            "failure_code": None,
        }
        result_sha256 = store.record_result(cell, attempt_id, result)
        inspection = store.inspect_attempt(cell.cell_id, attempt_id)
        self.assertEqual(inspection.state, "PASS")
        self.assertEqual(inspection.cell_result_sha256, result_sha256)
        self.assertEqual(store.resume_decision(cell)["action"], "REUSE_PASS")

    def test_manual_pass_rejects_missing_arbitrary_objective_result(self):
        store = self.new_store()
        with self.assertRaisesRegex(
            ledger.LedgerConflict, "E_LEDGER_RESULT_EVIDENCE"
        ):
            self.record_manual_pass(store, objective_digest="d" * 64)

    def test_manual_pass_rejects_cross_game_objective_result(self):
        store = self.new_store()
        _, raw, digest = self.complete_objective(
            store, self.cross_game_objective_cell
        )
        with self.assertRaisesRegex(
            ledger.LedgerConflict, "E_LEDGER_RESULT_EVIDENCE"
        ):
            self.record_manual_pass(
                store,
                objective_raw=raw,
                objective_digest=digest,
            )

    def test_manual_pass_rejects_failed_or_late_objective_result(self):
        store = self.new_store()
        _, raw, digest = self.complete_objective(
            store, self.manual_objective_cell, status="FAIL"
        )
        with self.assertRaisesRegex(
            ledger.LedgerConflict, "E_LEDGER_RESULT_EVIDENCE"
        ):
            self.record_manual_pass(
                store,
                objective_raw=raw,
                objective_digest=digest,
            )

        store = self.new_store()
        _, raw, digest = self.complete_objective(
            store,
            self.manual_objective_cell,
            start="2026-08-23T12:05:00Z",
            event_times=(
                "2026-08-23T12:06:00Z",
                "2026-08-23T12:07:00Z",
                "2026-08-23T12:08:00Z",
                "2026-08-23T12:09:00Z",
            ),
        )
        with self.assertRaisesRegex(
            ledger.LedgerConflict, "E_LEDGER_RESULT_EVIDENCE"
        ):
            self.record_manual_pass(
                store,
                objective_raw=raw,
                objective_digest=digest,
                reviewed_at="2026-08-23T12:02:00Z",
            )

    def test_manual_verdict_time_is_inside_attempt_and_not_after_first_use(self):
        for reviewed_at in (
            "2026-08-23T11:59:59Z",
            "2026-08-23T12:02:01Z",
            "2026-08-23T13:00:00Z",
        ):
            store = self.new_store()
            _, raw, digest = self.complete_objective(
                store, self.manual_objective_cell
            )
            with self.subTest(reviewed_at=reviewed_at):
                with self.assertRaisesRegex(
                    ledger.LedgerConflict, "E_LEDGER_RESULT_EVIDENCE"
                ):
                    self.record_manual_pass(
                        store,
                        objective_raw=raw,
                        objective_digest=digest,
                        reviewed_at=reviewed_at,
                    )

    def test_ledger_rejects_schema_incompatible_id_and_evidence_bounds(self):
        store = self.new_store()
        attempt_id = self.begin(store)
        with self.assertRaisesRegex(ledger.LedgerError, "E_LEDGER_EVIDENCE_KIND"):
            store.record_evidence(
                self.cell,
                attempt_id,
                gate_id=self.gate_id,
                kind="a" * 97,
                payload=b"evidence",
            )
        oversized = [
            {"kind": f"report-{index}", "sha256": "a" * 64, "bytes": 1}
            for index in range(model.MAX_EVIDENCE_ITEMS + 1)
        ]
        with self.assertRaisesRegex(
            ledger.LedgerAmbiguous, "E_LEDGER_EVIDENCE_COUNT"
        ):
            store.append_event(
                self.cell,
                attempt_id,
                event_type="GATE_STARTED",
                gate_id=self.gate_id,
                recorded_at="2026-08-23T12:01:00Z",
                evidence=oversized,
            )

    def test_passed_cell_cannot_start_again(self):
        store = self.new_store()
        attempt_id = self.begin(store)
        self.pass_attempt(store, attempt_id)
        with self.assertRaisesRegex(ledger.LedgerConflict, "E_LEDGER_COMPLETED_CELL"):
            store.begin_attempt(
                self.cell,
                attempt_number=2,
                started_at="2026-08-23T13:00:00Z",
                owner_id="matrix-test-owner",
                recovery_id="recovery-" + "0" * 64,
            )

    def test_failed_attempt_needs_reviewed_recovery_before_new_attempt(self):
        store = self.new_store()
        first = self.begin(store)
        self.fail_attempt(store, first)
        self.assertEqual(store.resume_decision(self.cell)["action"], "RECOVERY_REQUIRED")
        with self.assertRaisesRegex(ledger.LedgerConflict, "E_LEDGER_RECOVERY_REQUIRED"):
            self.begin(store, number=2, minute=6)

        recovery = store.record_recovery(
            self.cell,
            first,
            self.recovery_review(store, first),
        )
        decision = store.resume_decision(self.cell)
        self.assertEqual(decision["action"], "START_NEW")
        self.assertEqual(decision["attempt_number"], 2)
        self.assertEqual(decision["recovery_id"], recovery)
        second = self.begin(store, number=2, recovery_id=recovery, minute=6)
        self.pass_attempt(store, second, minute=6)
        self.assertEqual(store.inspect_attempt(self.cell.cell_id, second).state, "PASS")

    def test_recovery_ancestry_binds_successor_and_downstream_hashes(self):
        def completed_chain(reviewer_id):
            store = self.new_store()
            first = self.begin(store)
            self.fail_attempt(store, first)
            review = self.recovery_review(
                store,
                first,
                reviewer_id=reviewer_id,
            )
            recovery_id = store.record_recovery(self.cell, first, review)
            second = self.begin(
                store,
                number=2,
                recovery_id=recovery_id,
                minute=6,
            )
            result_sha256 = self.pass_attempt(store, second, minute=6)
            inspection = store.inspect_attempt(self.cell.cell_id, second)
            recovery_path = (
                store._cell_dir(self.cell.cell_id)
                / "recoveries"
                / f"{recovery_id}.json"
            )
            recovery_record = model.strict_json_load(recovery_path)
            return (
                store,
                recovery_id,
                second,
                result_sha256,
                inspection.last_event_sha256,
                recovery_record,
                store._ledger_snapshot_sha256(),
            )

        first_chain = completed_chain("independent-reviewer-a")
        second_chain = completed_chain("independent-reviewer-b")
        (
            _,
            recovery_id,
            attempt_id,
            result_sha256,
            last_event_sha256,
            recovery_record,
            snapshot_sha256,
        ) = first_chain
        self.assertEqual(
            attempt_id,
            model.make_attempt_id(
                self.cell,
                2,
                "2026-08-23T12:06:00Z",
                "matrix-test-owner",
                recovery_id,
            ),
        )
        self.assertNotEqual(
            attempt_id,
            model.make_attempt_id(
                self.cell,
                2,
                "2026-08-23T12:06:00Z",
                "matrix-test-owner",
                None,
            ),
        )
        self.assertEqual(recovery_record["recovery_id"], recovery_id)
        self.assertEqual(
            recovery_record["reviewer_id"], "independent-reviewer-a"
        )
        self.assertEqual(
            recovery_record["review"]["reviewer_id"],
            "independent-reviewer-a",
        )
        for left, right in zip(first_chain[1:], second_chain[1:]):
            self.assertNotEqual(left, right)
        for digest in (
            result_sha256,
            last_event_sha256,
            snapshot_sha256,
        ):
            self.assertRegex(digest, r"^[0-9a-f]{64}$")

    def test_preserved_staging_blocks_resume_after_reviewed_recovery(self):
        store = self.new_store()
        first = self.begin(store)
        self.fail_attempt(store, first)
        recovery_id = store.record_recovery(
            self.cell,
            first,
            self.recovery_review(store, first),
        )
        preserved = store.staging_root / "preserved-attempt.stage"
        preserved.mkdir()
        (preserved / "attempt.json.partial").write_bytes(b"preserved\n")

        with self.assertRaisesRegex(
            ledger.LedgerAmbiguous,
            "E_LEDGER_STAGING_NOT_EMPTY",
        ):
            store.resume_decision(self.cell)
        self.assertTrue((preserved / "attempt.json.partial").is_file())
        recovery_path = (
            store._cell_dir(self.cell.cell_id)
            / "recoveries"
            / f"{recovery_id}.json"
        )
        self.assertTrue(recovery_path.is_file())

    def test_preserved_staging_blocks_every_normal_mutation(self):
        store = self.new_store()
        attempt_id = self.begin(store)
        preserved = store.staging_root / "preserved.partial"
        preserved.write_bytes(b"preserved\n")
        calls = (
            lambda: store.begin_attempt(
                self.cell,
                attempt_number=2,
                started_at="2026-08-23T12:06:00Z",
                owner_id="matrix-test-owner",
            ),
            lambda: store.record_evidence(
                self.cell,
                attempt_id,
                gate_id=self.gate_id,
                kind=self.cell.identity["required_evidence_kinds"][0],
                payload=b"evidence",
            ),
            lambda: store.append_event(
                self.cell,
                attempt_id,
                event_type="GATE_STARTED",
                gate_id=self.gate_id,
                recorded_at="2026-08-23T12:01:00Z",
            ),
            lambda: store.record_result(self.cell, attempt_id, {}),
            lambda: store.record_recovery(self.cell, attempt_id, {}),
            lambda: store.recovery_review_context(self.cell, attempt_id),
        )
        before = preserved.read_bytes()
        for call in calls:
            with self.subTest(call=repr(call)):
                with self.assertRaisesRegex(
                    ledger.LedgerAmbiguous,
                    "E_LEDGER_STAGING_NOT_EMPTY",
                ):
                    call()
                self.assertEqual(preserved.read_bytes(), before)

    def test_staging_recovery_binds_exact_reviewed_inventory(self):
        store = self.new_store()
        preserved = store.staging_root / "failed-write.stage"
        preserved.mkdir()
        partial = preserved / "record.json.partial"
        partial.write_bytes(b"first\n")
        stale_review = self.staging_recovery_review(store)
        partial.write_bytes(b"changed\n")
        with self.assertRaisesRegex(
            ledger.LedgerConflict,
            "E_LEDGER_STAGING_RECOVERY_REVIEW_STALE",
        ):
            store.resolve_staging(stale_review)
        self.assertEqual(partial.read_bytes(), b"changed\n")

        review = self.staging_recovery_review(store)
        forged = copy.deepcopy(review)
        forged["reviewer_id"] = forged["operator_id"]
        with self.assertRaisesRegex(
            ledger.LedgerConflict,
            "E_LEDGER_STAGING_RECOVERY_REVIEWER_NOT_INDEPENDENT",
        ):
            store.resolve_staging(forged)

        recovery_id = store.resolve_staging(review)
        self.assertRegex(recovery_id, r"^staging-recovery-[0-9a-f]{64}$")
        self.assertEqual(list(store.staging_root.iterdir()), [])
        archive = store.staging_recoveries_root / recovery_id
        self.assertEqual(
            (archive / "preserved" / "failed-write.stage"
             / "record.json.partial").read_bytes(),
            b"changed\n",
        )
        record = model.strict_json_load(archive / "recovery.json")
        self.assertEqual(record["review"], review)
        attempt_id = self.begin(store)
        self.assertEqual(
            store.inspect_attempt(self.cell.cell_id, attempt_id).state,
            "AMBIGUOUS",
        )

    def test_interrupted_staging_recovery_resumes_without_overwrite(self):
        store = self.new_store()
        (store.staging_root / "preserved.partial").write_bytes(b"first\n")
        review = self.staging_recovery_review(store)
        original_write = store._write_exclusive_bytes
        write_count = 0

        def fail_second_metadata_write(path, payload):
            nonlocal write_count
            write_count += 1
            if write_count == 2:
                raise ledger.LedgerAmbiguous(
                    "E_INJECTED_METADATA_INTERRUPTION", str(path)
                )
            return original_write(path, payload)

        with mock.patch.object(
            store,
            "_write_exclusive_bytes",
            fail_second_metadata_write,
        ):
            with self.assertRaisesRegex(
                ledger.LedgerAmbiguous,
                "E_INJECTED_METADATA_INTERRUPTION",
            ):
                store.resolve_staging(review)
        pending = list(store.staging_recoveries_root.iterdir())
        self.assertEqual(len(pending), 1)
        self.assertEqual(
            {item.name for item in pending[0].iterdir()},
            {"review.json"},
        )
        reopened = ledger.LedgerStore(store.root)
        with self.assertRaisesRegex(
            ledger.LedgerAmbiguous,
            "E_LEDGER_STAGING_RECOVERY_PENDING",
        ):
            self.begin(reopened)
        recovery_id = reopened.resolve_staging(review)
        self.assertEqual(
            (
                reopened.staging_recoveries_root
                / recovery_id
                / "preserved"
                / "preserved.partial"
            ).read_bytes(),
            b"first\n",
        )
        self.assertEqual(reopened.resolve_staging(review), recovery_id)

        moved_store = self.new_store()
        (moved_store.staging_root / "moved.partial").write_bytes(b"second\n")
        moved_review = self.staging_recovery_review(moved_store)
        original_rename = ledger.os.rename

        def move_then_interrupt(source, target):
            if Path(source) == moved_store.staging_root:
                original_rename(source, target)
                raise OSError("injected after staging move")
            return original_rename(source, target)

        with mock.patch.object(
            ledger.os,
            "rename",
            side_effect=move_then_interrupt,
        ):
            with self.assertRaisesRegex(
                ledger.LedgerAmbiguous,
                "E_LEDGER_STAGING_RECOVERY_PUBLISH",
            ):
                moved_store.resolve_staging(moved_review)
        self.assertFalse(moved_store.staging_root.exists())
        moved_reopened = ledger.LedgerStore(moved_store.root)
        moved_recovery_id = moved_reopened.resolve_staging(moved_review)
        self.assertEqual(
            (
                moved_reopened.staging_recoveries_root
                / moved_recovery_id
                / "preserved"
                / "moved.partial"
            ).read_bytes(),
            b"second\n",
        )

        linked_store = self.new_store()
        (linked_store.staging_root / "linked.partial").write_bytes(b"third\n")
        linked_review = self.staging_recovery_review(linked_store)
        original_unlink = ledger.os.unlink
        unlink_failed = False

        def fail_first_metadata_unlink(path):
            nonlocal unlink_failed
            if not unlink_failed and Path(path).name == "review.json.partial":
                unlink_failed = True
                raise OSError("injected after metadata link")
            return original_unlink(path)

        with mock.patch.object(
            ledger.os,
            "unlink",
            side_effect=fail_first_metadata_unlink,
        ):
            with self.assertRaisesRegex(
                ledger.LedgerAmbiguous,
                "E_LEDGER_STAGING_RECOVERY_WRITE",
            ):
                linked_store.resolve_staging(linked_review)
        linked_reopened = ledger.LedgerStore(linked_store.root)
        linked_recovery_id = linked_reopened.resolve_staging(linked_review)
        self.assertTrue(
            (
                linked_reopened.staging_recoveries_root
                / linked_recovery_id
                / "preserved"
                / "linked.partial"
            ).is_file()
        )

        final_store = self.new_store()
        (final_store.staging_root / "final.partial").write_bytes(b"fourth\n")
        final_review = self.staging_recovery_review(final_store)
        final_original_rename = ledger.os.rename

        def publish_then_interrupt(source, target):
            source_path = Path(source)
            target_path = Path(target)
            if (
                source_path.name.startswith(".pending-staging-recovery-")
                and target_path.name.startswith("staging-recovery-")
            ):
                final_original_rename(source, target)
                raise OSError("injected after final archive publish")
            return final_original_rename(source, target)

        with mock.patch.object(
            ledger.os,
            "rename",
            side_effect=publish_then_interrupt,
        ):
            with self.assertRaisesRegex(
                ledger.LedgerAmbiguous,
                "E_LEDGER_STAGING_RECOVERY_PUBLISH",
            ):
                final_store.resolve_staging(final_review)
        final_reopened = ledger.LedgerStore(final_store.root)
        final_recovery_id = next(
            item.name
            for item in final_reopened.staging_recoveries_root.iterdir()
        )
        self.assertEqual(
            final_reopened.resolve_staging(final_review), final_recovery_id
        )

    def test_staging_recovery_archive_rejects_boolean_count(self):
        store = self.new_store()
        (store.staging_root / "one.partial").write_bytes(b"one\n")
        review = self.staging_recovery_review(store)
        recovery_id = store.resolve_staging(review)
        recovery_path = (
            store.staging_recoveries_root / recovery_id / "recovery.json"
        )
        record = model.strict_json_load(recovery_path)
        self.assertEqual(record["staging_entry_count"], 1)
        record["staging_entry_count"] = True
        recovery_path.write_bytes(model.canonical_json_bytes(record))
        with self.assertRaisesRegex(
            ledger.LedgerAmbiguous,
            "E_LEDGER_STAGING_RECOVERY_BINDING",
        ):
            ledger.LedgerStore(store.root)

    def test_read_validation_rejects_impossible_successor_ancestry(self):
        chronology_store = self.new_store()
        first = self.begin(chronology_store)
        self.fail_attempt(chronology_store, first)
        recovery_id = chronology_store.record_recovery(
            self.cell,
            first,
            self.recovery_review(chronology_store, first),
        )
        impossible = self.publish_attempt_record(
            chronology_store,
            self.cell,
            attempt_number=2,
            started_at="2026-08-23T12:05:00Z",
            recovery_id=recovery_id,
        )
        for operation in (
            lambda: chronology_store.inspect_attempt(
                self.cell.cell_id, impossible
            ),
            lambda: chronology_store.recovery_review_context(
                self.cell, impossible
            ),
            lambda: chronology_store.make_recovery_review(
                self.cell,
                impossible,
                reviewed_at="2026-08-23T12:07:00Z",
                reviewer_id="independent-reviewer",
                finding_ids=("invalid-ancestry",),
            ),
            lambda: chronology_store.append_event(
                self.cell,
                impossible,
                event_type="GATE_STARTED",
                gate_id=self.gate_id,
                recorded_at="2026-08-23T12:06:00Z",
            ),
        ):
            with self.subTest(case="predated-successor"):
                with self.assertRaisesRegex(
                    ledger.LedgerAmbiguous,
                    "E_LEDGER_SUCCESSOR_TIME",
                ):
                    operation()

        pass_store = self.new_store()
        passed = self.begin(pass_store)
        self.pass_attempt(pass_store, passed)
        for operation in (
            lambda: pass_store.recovery_review_context(self.cell, passed),
            lambda: pass_store.make_recovery_review(
                self.cell,
                passed,
                reviewed_at="2026-08-23T12:05:00Z",
                reviewer_id="independent-reviewer",
                finding_ids=("invalid-pass-recovery",),
            ),
        ):
            with self.subTest(case="review-after-pass"):
                with self.assertRaisesRegex(
                    ledger.LedgerConflict,
                    "E_LEDGER_COMPLETED_CELL",
                ):
                    operation()
        pass_attempt_path = pass_store._attempt_directories(
            pass_store._cell_dir(self.cell.cell_id)
        )[-1][2]
        pass_attempt_record = model.strict_json_load(
            pass_attempt_path / "attempt.json"
        )
        review = {
            "schema": ledger.RECOVERY_REVIEW_SCHEMA,
            "schema_version": 1,
            "cell_id": self.cell.cell_id,
            "input_fingerprint": self.cell.input_fingerprint,
            "failed_attempt_id": passed,
            "failed_attempt_state_sha256": pass_store._attempt_snapshot_sha256(
                pass_attempt_path
            ),
            "latest_recorded_at": pass_store._latest_attempt_recorded_at(
                pass_attempt_path, pass_attempt_record
            ),
            "reviewed_at": "2026-08-23T12:05:00Z",
            "reviewer_id": "independent-reviewer",
            "finding_ids": ["invalid-pass-recovery"],
            "disposition": "AUTHORIZE_NEW_ATTEMPT",
        }
        forged_recovery = self.publish_recovery_record(
            pass_store, self.cell, passed, review
        )
        for operation in (
            lambda: pass_store.inspect_attempt(self.cell.cell_id, passed),
            lambda: pass_store.recovery_review_context(self.cell, passed),
            lambda: pass_store.make_recovery_review(
                self.cell,
                passed,
                reviewed_at="2026-08-23T12:06:00Z",
                reviewer_id="second-independent-reviewer",
                finding_ids=("invalid-pending-recovery",),
            ),
        ):
            with self.subTest(case="pending-recovery-after-pass"):
                with self.assertRaisesRegex(
                    ledger.LedgerAmbiguous,
                    "E_LEDGER_RECOVERY_AFTER_PASS",
                ):
                    operation()
        after_pass = self.publish_attempt_record(
            pass_store,
            self.cell,
            attempt_number=2,
            started_at="2026-08-23T12:06:00Z",
            recovery_id=forged_recovery,
        )
        for operation in (
            lambda: pass_store.inspect_attempt(
                self.cell.cell_id, after_pass
            ),
            lambda: pass_store.recovery_review_context(
                self.cell, after_pass
            ),
            lambda: pass_store.make_recovery_review(
                self.cell,
                after_pass,
                reviewed_at="2026-08-23T12:08:00Z",
                reviewer_id="second-independent-reviewer",
                finding_ids=("invalid-successor",),
            ),
            lambda: pass_store.append_event(
                self.cell,
                after_pass,
                event_type="GATE_STARTED",
                gate_id=self.gate_id,
                recorded_at="2026-08-23T12:07:00Z",
            ),
        ):
            with self.subTest(case="successor-after-pass"):
                with self.assertRaisesRegex(
                    ledger.LedgerAmbiguous,
                    "E_LEDGER_SUCCESSOR_AFTER_PASS",
                ):
                    operation()

    def test_root_lock_rejects_windows_junction_directory(self):
        if os.name != "nt":
            self.skipTest("Windows junction test")
        store = self.new_store()
        attempt_id = self.begin(store)
        external_locks = store.root.parent / "outside-locks"
        store.locks_root.rename(external_locks)
        created = subprocess.run(
            [
                "cmd",
                "/d",
                "/c",
                "mklink",
                "/J",
                str(store.locks_root),
                str(external_locks),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if created.returncode != 0:
            external_locks.rename(store.locks_root)
            self.skipTest("the current account cannot create a junction")
        try:
            with self.assertRaisesRegex(
                ledger.LedgerAmbiguous,
                "E_LEDGER_DIRECTORY",
            ):
                store.inspect_attempt(self.cell.cell_id, attempt_id)
        finally:
            os.rmdir(store.locks_root)
            external_locks.rename(store.locks_root)

    def test_inspect_attempt_uses_stable_locked_root(self):
        store = self.new_store()
        attempt_id = self.begin(store)
        self.assertEqual(
            store.inspect_attempt(self.cell.cell_id, attempt_id).state,
            "AMBIGUOUS",
        )
        with store._root_lock():
            with self.assertRaisesRegex(
                ledger.LedgerConflict,
                "E_LEDGER_ROOT_BUSY",
            ):
                store.inspect_attempt(self.cell.cell_id, attempt_id)

        original = ledger.LedgerStore._load_attempt_record
        changed = False

        def mutate_root_once(instance, *args, **kwargs):
            nonlocal changed
            record = original(instance, *args, **kwargs)
            if not changed:
                changed = True
                (instance.cells_root / "external-change.bin").write_bytes(
                    b"changed\n"
                )
            return record

        with mock.patch.object(
            ledger.LedgerStore,
            "_load_attempt_record",
            mutate_root_once,
        ):
            with self.assertRaisesRegex(
                ledger.LedgerAmbiguous,
                "E_LEDGER_ROOT_CHANGED",
            ):
                store.inspect_attempt(self.cell.cell_id, attempt_id)

        second_store = self.new_store()
        second_attempt = self.begin(second_store)
        (second_store.staging_root / "preserved.partial").write_bytes(b"x")
        with self.assertRaisesRegex(
            ledger.LedgerAmbiguous,
            "E_LEDGER_STAGING_NOT_EMPTY",
        ):
            second_store.inspect_attempt(self.cell.cell_id, second_attempt)

    def test_validated_result_set_rejects_root_change_during_read(self):
        manifest = private_release_manifest()
        store = self.new_store()
        private_cell = model.expand_cells(manifest)[0]
        store.begin_attempt(
            private_cell,
            attempt_number=1,
            started_at="2026-08-23T12:00:00Z",
            owner_id="matrix-test-owner",
        )
        stable = store.validated_result_set(manifest)
        self.assertRegex(stable.ledger_snapshot_sha256, r"^[0-9a-f]{64}$")

        original = ledger.LedgerStore._load_cell_record
        changed = False

        def mutate_root_once(instance, cell_dir):
            nonlocal changed
            record = original(instance, cell_dir)
            if not changed:
                changed = True
                unknown = instance.cells_root / ("cell-" + "f" * 64)
                unknown.mkdir()
            return record

        with mock.patch.object(
            ledger.LedgerStore,
            "_load_cell_record",
            new=mutate_root_once,
        ):
            with self.assertRaisesRegex(
                ledger.LedgerAmbiguous,
                "E_LEDGER_RESULT_SET_UNKNOWN_CELL|E_LEDGER_ROOT_CHANGED",
            ):
                store.validated_result_set(manifest)
        self.assertTrue(changed)

    def test_recovery_seals_failed_attempt_before_and_after_successor(self):
        store = self.new_store()
        first = self.begin(store)
        evidence = self.pass_terminal(store, first)
        recovery = store.record_recovery(
            self.cell,
            first,
            self.recovery_review(store, first),
        )
        stale_result = self.passing_ledger_result(first, evidence)
        for operation in (
            lambda: store.record_evidence(
                self.cell,
                first,
                gate_id=self.gate_id,
                kind=self.cell.identity["required_evidence_kinds"][0],
                payload=b"late-evidence",
            ),
            lambda: store.append_event(
                self.cell,
                first,
                event_type="ATTEMPT_AMBIGUOUS",
                recorded_at="2026-08-23T12:05:30Z",
            ),
            lambda: store.record_result(self.cell, first, stale_result),
        ):
            with self.subTest(phase="pending-recovery"):
                with self.assertRaisesRegex(
                    ledger.LedgerConflict, "E_LEDGER_ATTEMPT_SEALED"
                ):
                    operation()

        self.begin(store, number=2, recovery_id=recovery, minute=6)
        for operation in (
            lambda: store.record_evidence(
                self.cell,
                first,
                gate_id=self.gate_id,
                kind=self.cell.identity["required_evidence_kinds"][0],
                payload=b"later-evidence",
            ),
            lambda: store.append_event(
                self.cell,
                first,
                event_type="ATTEMPT_AMBIGUOUS",
                recorded_at="2026-08-23T12:07:00Z",
            ),
            lambda: store.record_result(self.cell, first, stale_result),
        ):
            with self.subTest(phase="successor-started"):
                with self.assertRaisesRegex(
                    ledger.LedgerConflict, "E_LEDGER_ATTEMPT_SEALED"
                ):
                    operation()

    def test_recovery_review_binds_bytes_snapshot_and_chronology(self):
        store = self.new_store()
        first = self.begin(store)
        self.fail_attempt(store, first)
        predated = self.recovery_review(
            store,
            first,
            reviewed_at="2026-08-23T12:04:00Z",
        )
        with self.assertRaisesRegex(
            ledger.LedgerConflict, "E_LEDGER_RECOVERY_REVIEW_TIME"
        ):
            store.record_recovery(self.cell, first, predated)

        stale = copy.deepcopy(self.recovery_review(store, first))
        stale["failed_attempt_state_sha256"] = "0" * 64
        with self.assertRaisesRegex(
            ledger.LedgerConflict, "E_LEDGER_RECOVERY_REVIEW_STALE"
        ):
            store.record_recovery(self.cell, first, stale)

        recovery = store.record_recovery(
            self.cell,
            first,
            self.recovery_review(store, first),
        )
        _, attempt_path = store._find_attempt(self.cell.cell_id, first)
        event_path = sorted((attempt_path / "events").iterdir())[0]
        event_path.write_bytes(event_path.read_bytes() + b" ")
        with self.assertRaisesRegex(
            ledger.LedgerConflict, "E_LEDGER_RECOVERY_REVIEW_STALE"
        ):
            self.begin(store, number=2, recovery_id=recovery, minute=6)

    def test_successor_must_start_after_recovery_review(self):
        store = self.new_store()
        first = self.begin(store)
        self.fail_attempt(store, first)
        recovery = store.record_recovery(
            self.cell,
            first,
            self.recovery_review(store, first),
        )
        with self.assertRaisesRegex(
            ledger.LedgerConflict, "E_LEDGER_SUCCESSOR_TIME"
        ):
            self.begin(store, number=2, recovery_id=recovery, minute=5)

    def test_inspection_rejects_missing_or_tampered_recovery_ancestor(self):
        for mutation in ("missing", "tampered"):
            store = self.new_store()
            _, recovery_one, _, _, third = self.complete_three_attempt_chain(store)
            recovery_path = (
                store._cell_dir(self.cell.cell_id)
                / "recoveries"
                / f"{recovery_one}.json"
            )
            if mutation == "missing":
                recovery_path.unlink()
            else:
                record = model.strict_json_load(recovery_path)
                record["reviewer_id"] = "tampered-reviewer"
                recovery_path.write_bytes(model.canonical_json_bytes(record))
            with self.subTest(mutation=mutation):
                with self.assertRaises(ledger.LedgerError):
                    store.inspect_attempt(self.cell.cell_id, third)

    def test_manual_objective_rejects_broken_recovery_ancestry(self):
        store = self.new_store()
        cell = self.manual_objective_cell
        first, _, _ = self.complete_objective(
            store,
            cell,
            status="FAIL",
            start="2026-08-23T11:20:00Z",
            event_times=(
                "2026-08-23T11:21:00Z",
                "2026-08-23T11:22:00Z",
                "2026-08-23T11:23:00Z",
                "2026-08-23T11:24:00Z",
            ),
        )
        review_one = store.make_recovery_review(
            cell,
            first,
            reviewed_at="2026-08-23T11:25:00Z",
            reviewer_id="first-independent-reviewer",
            finding_ids=("first-failure",),
        )
        recovery_one = store.record_recovery(cell, first, review_one)
        second, _, _ = self.complete_objective(
            store,
            cell,
            attempt_number=2,
            recovery_id=recovery_one,
            status="FAIL",
            start="2026-08-23T11:26:00Z",
            event_times=(
                "2026-08-23T11:27:00Z",
                "2026-08-23T11:28:00Z",
                "2026-08-23T11:29:00Z",
                "2026-08-23T11:30:00Z",
            ),
        )
        review_two = store.make_recovery_review(
            cell,
            second,
            reviewed_at="2026-08-23T11:31:00Z",
            reviewer_id="second-independent-reviewer",
            finding_ids=("second-failure",),
        )
        recovery_two = store.record_recovery(cell, second, review_two)
        _, objective_raw, objective_digest = self.complete_objective(
            store,
            cell,
            attempt_number=3,
            recovery_id=recovery_two,
            start="2026-08-23T11:32:00Z",
            event_times=(
                "2026-08-23T11:33:00Z",
                "2026-08-23T11:34:00Z",
                "2026-08-23T11:35:00Z",
                "2026-08-23T11:36:00Z",
            ),
        )
        recovery_path = (
            store._cell_dir(cell.cell_id)
            / "recoveries"
            / f"{recovery_one}.json"
        )
        recovery_path.unlink()
        with self.assertRaisesRegex(
            ledger.LedgerConflict, "E_LEDGER_RESULT_EVIDENCE"
        ):
            self.record_manual_pass(
                store,
                objective_raw=objective_raw,
                objective_digest=objective_digest,
            )

    def test_failed_gate_cannot_restart_inside_same_attempt(self):
        store = self.new_store()
        attempt_id = self.begin(store)
        store.append_event(
            self.cell,
            attempt_id,
            event_type="GATE_STARTED",
            gate_id=self.gate_id,
            recorded_at="2026-08-23T12:01:00Z",
        )
        store.append_event(
            self.cell,
            attempt_id,
            event_type="GATE_FAILED",
            gate_id=self.gate_id,
            recorded_at="2026-08-23T12:02:00Z",
        )
        with self.assertRaisesRegex(ledger.LedgerAmbiguous, "E_LEDGER_GATE_START_STATE"):
            store.append_event(
                self.cell,
                attempt_id,
                event_type="GATE_STARTED",
                gate_id="second-gate",
                recorded_at="2026-08-23T12:03:00Z",
            )

    def test_missing_terminal_is_fail_closed(self):
        store = self.new_store()
        attempt_id = self.begin(store)
        self.assertEqual(store.inspect_attempt(self.cell.cell_id, attempt_id).state, "AMBIGUOUS")
        decision = store.resume_decision(self.cell)
        self.assertEqual(decision["action"], "RECOVERY_REQUIRED")
        self.assertEqual(decision["state"], "AMBIGUOUS")

    def test_terminal_pass_requires_exact_gate_evidence(self):
        store = self.new_store()
        attempt_id = self.begin(store)
        store.append_event(
            self.cell,
            attempt_id,
            event_type="GATE_STARTED",
            gate_id=self.gate_id,
            recorded_at="2026-08-23T12:01:00Z",
        )
        evidence = [
            store.record_evidence(
                self.cell,
                attempt_id,
                gate_id=self.gate_id,
                kind=kind,
                payload=f"{kind}:{attempt_id}".encode("ascii"),
            )
            for kind in self.cell.identity["required_evidence_kinds"]
        ]
        store.append_event(
            self.cell,
            attempt_id,
            event_type="GATE_PASSED",
            gate_id=self.gate_id,
            recorded_at="2026-08-23T12:02:00Z",
            evidence=evidence,
        )
        store.append_event(
            self.cell,
            attempt_id,
            event_type="CLEANUP_PASSED",
            recorded_at="2026-08-23T12:03:00Z",
        )
        wrong = copy.deepcopy(evidence[-1])
        wrong["sha256"] = "0" * 64
        with self.assertRaisesRegex(
            ledger.LedgerAmbiguous, "E_LEDGER_EVIDENCE_BINDING_DIGEST"
        ):
            store.append_event(
                self.cell,
                attempt_id,
                event_type="ATTEMPT_PASSED",
                recorded_at="2026-08-23T12:04:00Z",
                evidence=evidence[:-1] + [wrong],
            )

    def test_interrupted_atomic_write_preserves_partial_and_is_ambiguous(self):
        store = self.new_store()
        attempt_id = self.begin(store)
        with mock.patch.object(ledger.os, "link", side_effect=OSError("injected")):
            with self.assertRaisesRegex(ledger.LedgerAmbiguous, "E_LEDGER_ATOMIC_CREATE"):
                store.append_event(
                    self.cell,
                    attempt_id,
                    event_type="GATE_STARTED",
                    gate_id=self.gate_id,
                    recorded_at="2026-08-23T12:01:00Z",
                )
        _, attempt_path = store._find_attempt(self.cell.cell_id, attempt_id)
        partials = list(store.staging_root.glob("*.partial"))
        self.assertEqual(len(partials), 1)
        with self.assertRaisesRegex(
            ledger.LedgerAmbiguous,
            "E_LEDGER_STAGING_NOT_EMPTY",
        ):
            store.inspect_attempt(self.cell.cell_id, attempt_id)
        self.assertEqual(list((attempt_path / "events").iterdir()), [])
        with self.assertRaisesRegex(
            ledger.LedgerAmbiguous,
            "E_LEDGER_STAGING_NOT_EMPTY",
        ):
            store.resume_decision(self.cell)
        self.assertEqual(list(store.staging_root.glob("*.partial")), partials)
        review = self.staging_recovery_review(store)
        store.resolve_staging(review)
        self.assertEqual(
            store.inspect_attempt(self.cell.cell_id, attempt_id).state,
            "AMBIGUOUS",
        )

    def test_interrupted_attempt_publication_does_not_create_partial_attempt(self):
        store = self.new_store()
        with mock.patch.object(ledger.os, "rename", side_effect=OSError("injected")):
            with self.assertRaisesRegex(
                ledger.LedgerAmbiguous, "E_LEDGER_ATTEMPT_PUBLISH"
            ):
                self.begin(store)
        cell_dir = store._cell_dir(self.cell.cell_id)
        self.assertEqual(store._attempt_directories(cell_dir), [])
        self.assertTrue(any(store.staging_root.glob("attempt-*.stage")))
        with self.assertRaisesRegex(
            ledger.LedgerAmbiguous,
            "E_LEDGER_STAGING_NOT_EMPTY",
        ):
            self.begin(store)
        review = self.staging_recovery_review(store)
        store.resolve_staging(review)
        attempt_id = self.begin(store)
        self.assertEqual(
            store.inspect_attempt(self.cell.cell_id, attempt_id).state,
            "AMBIGUOUS",
        )

    def test_interrupted_result_publication_can_recover_without_partial_layout(self):
        store = self.new_store()
        attempt_id = self.begin(store)
        evidence = self.pass_terminal(store, attempt_id)
        result = self.passing_ledger_result(attempt_id, evidence)
        with mock.patch.object(ledger.os, "link", side_effect=OSError("injected")):
            with self.assertRaisesRegex(
                ledger.LedgerAmbiguous, "E_LEDGER_ATOMIC_CREATE"
            ):
                store.record_result(self.cell, attempt_id, result)
        _, attempt_path = store._find_attempt(self.cell.cell_id, attempt_id)
        self.assertFalse((attempt_path / "result.json").exists())
        self.assertFalse(any("partial" in item.name for item in attempt_path.iterdir()))
        with self.assertRaisesRegex(
            ledger.LedgerAmbiguous,
            "E_LEDGER_STAGING_NOT_EMPTY",
        ):
            store.inspect_attempt(self.cell.cell_id, attempt_id)
        review = self.staging_recovery_review(store)
        store.resolve_staging(review)
        self.assertEqual(
            store.inspect_attempt(self.cell.cell_id, attempt_id).state,
            "AMBIGUOUS",
        )
        recovery = store.record_recovery(
            self.cell,
            attempt_id,
            self.recovery_review(store, attempt_id),
        )
        successor = self.begin(store, number=2, recovery_id=recovery, minute=6)
        self.pass_attempt(store, successor, minute=6)

    def test_evidence_store_rejects_poisoning_duplicates_and_overflow(self):
        store = self.new_store()
        attempt_id = self.begin(store)
        required_kind = self.cell.identity["required_evidence_kinds"][0]
        store.append_event(
            self.cell,
            attempt_id,
            event_type="GATE_STARTED",
            gate_id=self.gate_id,
            recorded_at="2026-08-23T12:01:00Z",
        )
        first_record = store.record_evidence(
            self.cell,
            attempt_id,
            gate_id=self.gate_id,
            kind=required_kind,
            payload=b"first",
        )
        with self.assertRaisesRegex(
            ledger.LedgerConflict, "E_LEDGER_EVIDENCE_KIND_EXISTS"
        ):
            store.record_evidence(
                self.cell,
                attempt_id,
                gate_id=self.gate_id,
                kind=required_kind,
                payload=b"different-bytes",
            )
        with self.assertRaisesRegex(
            ledger.LedgerConflict, "E_LEDGER_EVIDENCE_NOT_REQUIRED"
        ):
            store.record_evidence(
                self.cell,
                attempt_id,
                gate_id=self.gate_id,
                kind="poison-report",
                payload=b"poison",
            )
        duplicate = copy.deepcopy(first_record)
        duplicate["sha256"] = "c" * 64
        with self.assertRaisesRegex(
            ledger.LedgerAmbiguous, "E_LEDGER_EVIDENCE_DUPLICATE"
        ):
            store.append_event(
                self.cell,
                attempt_id,
                event_type="GATE_PASSED",
                gate_id=self.gate_id,
                recorded_at="2026-08-23T12:02:00Z",
                evidence=[first_record, duplicate],
            )

        identity = copy.deepcopy(dict(self.cell.identity))
        identity["required_evidence_kinds"] = [
            f"report-{index:02d}" for index in range(model.MAX_EVIDENCE_ITEMS + 1)
        ]
        fingerprint = model.sha256_value(identity)
        forged = model.MatrixCell(
            cell_id=f"cell-{fingerprint}",
            input_fingerprint=fingerprint,
            identity=identity,
        )
        overflow_attempt = store.begin_attempt(
            forged,
            attempt_number=1,
            started_at="2026-08-23T12:00:00Z",
            owner_id="matrix-test-owner",
        )
        forged_gate = forged.identity["required_gate_ids"][0]
        store.append_event(
            forged,
            overflow_attempt,
            event_type="GATE_STARTED",
            gate_id=forged_gate,
            recorded_at="2026-08-23T12:01:00Z",
        )
        for index in range(model.MAX_EVIDENCE_ITEMS):
            store.record_evidence(
                forged,
                overflow_attempt,
                gate_id=forged_gate,
                kind=f"report-{index:02d}",
                payload=f"payload-{index}".encode("ascii"),
            )
        with self.assertRaisesRegex(
            ledger.LedgerConflict, "E_LEDGER_EVIDENCE_COUNT"
        ):
            store.record_evidence(
                forged,
                overflow_attempt,
                gate_id=forged_gate,
                kind=f"report-{model.MAX_EVIDENCE_ITEMS:02d}",
                payload=b"overflow",
            )

    def test_numeric_limits_match_ledger_file_names(self):
        store = self.new_store()
        with self.assertRaisesRegex(
            ledger.LedgerConflict, "E_LEDGER_ATTEMPT_NUMBER_LIMIT"
        ):
            self.begin(store, number=ledger.MAX_ATTEMPTS + 1)
        event_name = f"{ledger.MAX_EVENT_SEQUENCE:010d}-{'0' * 64}.json"
        self.assertIsNotNone(ledger._EVENT_FILE_RE.fullmatch(event_name))
        attempt_id = self.begin(store)
        with mock.patch.object(ledger, "MAX_EVENT_SEQUENCE", -1):
            with self.assertRaisesRegex(
                ledger.LedgerConflict, "E_LEDGER_EVENT_SEQUENCE_LIMIT"
            ):
                store.append_event(
                    self.cell,
                    attempt_id,
                    event_type="GATE_STARTED",
                    gate_id=self.gate_id,
                    recorded_at="2026-08-23T12:01:00Z",
                )

    def test_event_tamper_breaks_chain(self):
        store = self.new_store()
        attempt_id = self.begin(store)
        self.pass_attempt(store, attempt_id)
        _, attempt_path = store._find_attempt(self.cell.cell_id, attempt_id)
        first = sorted((attempt_path / "events").iterdir())[0]
        raw = first.read_bytes()
        first.write_bytes(raw.replace(b"GATE_STARTED", b"GATE_PASSED ", 1))
        with self.assertRaises(ledger.LedgerAmbiguous):
            store.inspect_attempt(self.cell.cell_id, attempt_id)

    def test_noncanonical_record_is_ambiguous(self):
        store = self.new_store()
        attempt_id = self.begin(store)
        self.pass_attempt(store, attempt_id)
        _, attempt_path = store._find_attempt(self.cell.cell_id, attempt_id)
        last = sorted((attempt_path / "events").iterdir())[-1]
        raw = last.read_bytes()
        last.write_bytes(raw[:-1] + b" \n")
        with self.assertRaisesRegex(ledger.LedgerAmbiguous, "E_LEDGER_EVENT_CANONICAL"):
            store.inspect_attempt(self.cell.cell_id, attempt_id)

    def test_attempt_digest_and_exact_layout_are_verified(self):
        store = self.new_store()
        attempt_id = self.begin(store)
        _, attempt_path = store._find_attempt(self.cell.cell_id, attempt_id)
        record_path = attempt_path / "attempt.json"
        record = model.strict_json_load(record_path)
        record["owner_id"] = "different-owner"
        record_path.write_bytes(model.canonical_json_bytes(record))
        with self.assertRaisesRegex(ledger.LedgerAmbiguous, "E_LEDGER_ATTEMPT_DIGEST"):
            store.inspect_attempt(self.cell.cell_id, attempt_id)

        record["owner_id"] = "matrix-test-owner"
        record_path.write_bytes(model.canonical_json_bytes(record))
        (attempt_path / "unexpected.txt").write_text("unexpected\n", encoding="utf-8")
        with self.assertRaisesRegex(ledger.LedgerAmbiguous, "E_LEDGER_ATTEMPT_LAYOUT"):
            store.inspect_attempt(self.cell.cell_id, attempt_id)

    def test_recovery_digest_binds_the_independent_reviewer(self):
        store = self.new_store()
        first = self.begin(store)
        self.fail_attempt(store, first)
        recovery = store.record_recovery(
            self.cell,
            first,
            self.recovery_review(store, first),
        )
        recovery_path = (
            store._cell_dir(self.cell.cell_id)
            / "recoveries"
            / f"{recovery}.json"
        )
        record = model.strict_json_load(recovery_path)
        record["reviewer_id"] = "different-reviewer"
        recovery_path.write_bytes(model.canonical_json_bytes(record))
        with self.assertRaisesRegex(
            ledger.LedgerConflict, "E_LEDGER_RECOVERY_REVIEW_DIGEST"
        ):
            self.begin(store, number=2, recovery_id=recovery, minute=6)

    def test_recovery_reviewer_must_be_independent(self):
        store = self.new_store()
        first = self.begin(store)
        self.fail_attempt(store, first)
        with self.assertRaisesRegex(
            ledger.LedgerConflict,
            "E_LEDGER_RECOVERY_REVIEWER_NOT_INDEPENDENT",
        ):
            store.record_recovery(
                self.cell,
                first,
                self.recovery_review(
                    store,
                    first,
                    reviewer_id="matrix-test-owner",
                ),
            )

    def test_boolean_event_sequence_is_not_an_integer(self):
        store = self.new_store()
        attempt_id = self.begin(store)
        store.append_event(
            self.cell,
            attempt_id,
            event_type="GATE_STARTED",
            gate_id=self.gate_id,
            recorded_at="2026-08-23T12:01:00Z",
        )
        store.append_event(
            self.cell,
            attempt_id,
            event_type="GATE_PASSED",
            gate_id=self.gate_id,
            recorded_at="2026-08-23T12:02:00Z",
        )
        _, attempt_path = store._find_attempt(self.cell.cell_id, attempt_id)
        second = sorted((attempt_path / "events").iterdir())[1]
        record = model.strict_json_load(second)
        record["sequence"] = True
        second.write_bytes(model.canonical_json_bytes(record))
        with self.assertRaisesRegex(ledger.LedgerAmbiguous, "E_LEDGER_EVENT_BINDING"):
            store.inspect_attempt(self.cell.cell_id, attempt_id)

    def test_timestamp_regression_is_rejected_before_write(self):
        store = self.new_store()
        attempt_id = self.begin(store)
        store.append_event(
            self.cell,
            attempt_id,
            event_type="GATE_STARTED",
            gate_id=self.gate_id,
            recorded_at="2026-08-23T12:01:00Z",
        )
        with self.assertRaisesRegex(ledger.LedgerAmbiguous, "E_LEDGER_TIME_ORDER"):
            store.append_event(
                self.cell,
                attempt_id,
                event_type="GATE_PASSED",
                gate_id=self.gate_id,
                recorded_at="2026-08-23T12:00:30Z",
            )

    def test_unrelated_gate_cannot_create_release_evidence(self):
        store = self.new_store()
        attempt_id = self.begin(store)
        with self.assertRaisesRegex(ledger.LedgerAmbiguous, "E_LEDGER_GATE_NOT_REQUIRED"):
            store.append_event(
                self.cell,
                attempt_id,
                event_type="GATE_STARTED",
                gate_id="unrelated-gate",
                recorded_at="2026-08-23T12:01:00Z",
            )

    def test_cell_identity_drift_is_rejected(self):
        store = self.new_store()
        self.begin(store)
        forged_identity = copy.deepcopy(dict(self.cell.identity))
        forged_identity["game"]["id"] = "blue"
        forged = model.MatrixCell(
            cell_id=self.cell.cell_id,
            input_fingerprint=self.cell.input_fingerprint,
            identity=forged_identity,
        )
        with self.assertRaisesRegex(ledger.LedgerAmbiguous, "E_LEDGER_CELL_DRIFT"):
            store.resume_decision(forged)

        attempt_id = next(
            attempt_id
            for _, attempt_id, _ in store._attempt_directories(
                store._cell_dir(self.cell.cell_id)
            )
        )
        with self.assertRaisesRegex(ledger.LedgerConflict, "E_LEDGER_CELL_DRIFT"):
            store.append_event(
                forged,
                attempt_id,
                event_type="GATE_STARTED",
                gate_id=self.gate_id,
                recorded_at="2026-08-23T12:01:00Z",
            )

    @unittest.skipUnless(hasattr(os, "symlink"), "symlink support is unavailable")
    def test_symlink_state_root_is_rejected_when_supported(self):
        with ScopedTestDirectory() as temporary:
            base = Path(temporary)
            real = base / "real"
            real.mkdir()
            link = base / "link"
            try:
                os.symlink(real, link, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("the current account cannot create directory symlinks")
            with self.assertRaisesRegex(ledger.LedgerAmbiguous, "E_LEDGER_DIRECTORY"):
                ledger.LedgerStore(link)


if __name__ == "__main__":
    unittest.main()
