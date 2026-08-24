import copy
import contextlib
import io
import json
import math
import pathlib
import sys
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[2]
QA = ROOT / "docs" / "qa"
sys.path.insert(0, str(ROOT / "tools"))

from validate_qa_contract import (  # noqa: E402
    BATTLE_ART_PACKAGE_SHA256 as VALIDATOR_BATTLE_ART_PACKAGE_SHA256,
    Draft202012ContractValidator,
    QaContractLoadError,
    QaContractLogicError,
    evaluate_release_readiness,
    json_equal,
    load_json as contract_load_json,
    main,
    meta_validate_schemas,
    parse_json,
    validate_defect_ledger,
    validate_gate_map,
    validate_matrix,
    validate_parent_release_ledger,
    validate_runtime_result,
)


SOURCE_COMMIT = "e540c3b3de25caa5fa855dd6c3c702449ed9e72c"
SHA256 = "a" * 64
BATTLE_ART_PACKAGE_SHA256 = (
    "28c06d4153087be28891090d2d85d039f7cd81ba69f74c56a069016b3adf58bd"
)
STALE_BATTLE_ART_PACKAGE_SHA256 = (
    "c2e440bdacdba07b170f353e7a7d239bda793554332bc66ff93bba76dc42a1db"
)
SCHEMA_DRAFT = "https://json-schema.org/draft/2020-12/schema"
QUALITIES = ["LOW", "BALANCED", "HIGH"]

SCENE_IDS = [
    "scene.indoor.v1",
    "scene.cave.v1",
    "scene.forest.v1",
    "scene.city-lavender.v1",
    "scene.route-neighbor-edge.v1",
    "scene.shore.v1",
    "scene.mountain.v1",
    "scene.day.v1",
    "scene.night.v1",
    "scene.rain.v1",
    "scene.storm.v1",
    "scene.battle-supported.v1",
    "scene.battle-unsupported.v1",
]
CONTROL_ID = "control.no-host-fail-closed.v1"
ADVISORY_ID = "advisory.dense-outdoor-64x64.v1"

GATE_IDS = [
    "alpha.qa-contract.v1",
    "alpha.no-host-fail-closed.v1",
    "alpha.authored-scenes.v1",
    "alpha.quality-low.v1",
    "alpha.quality-balanced.v1",
    "alpha.quality-high.v1",
    "alpha.battle-art-1.9.8.v1",
    "alpha.dramaless-released-companion.v1",
    "alpha.cleanup-integrity.v1",
    "alpha.public-evidence-privacy.v1",
    "alpha.dense-stress-advisory.v1",
]


def reject_duplicate_keys(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def load_json(name):
    return json.loads(
        (QA / name).read_text(encoding="utf-8"),
        object_pairs_hook=reject_duplicate_keys,
    )


def artifact():
    return {
        "artifact_id": "artifact.synthetic-report.v1",
        "sha256": SHA256,
        "byte_count": 128,
        "media_type": "application/json",
        "redacted": True,
        "privacy_reviewed": True,
    }


def battle_art_result():
    return {
        "schema_version": "1.0.0",
        "result_id": "result.battle-art.synthetic.v1",
        "recorded_at": "2026-08-23T00:00:00Z",
        "source": {"commit": SOURCE_COMMIT, "package_sha256": SHA256},
        "engine": {"version": "gen1recomp-0.2.19"},
        "host": {
            "host_id": "BATTLE_ART_VOXEL_FORK",
            "release": "1.9.8",
            "commit": "6586ef5f7a86c1bfefcea931bd6571538c9f8d15",
            "package_sha256": BATTLE_ART_PACKAGE_SHA256,
            "released": True,
            "eligibility": "ELIGIBLE",
        },
        "game_version": "SYNTHETIC",
        "quality": "HIGH",
        "checkpoint_id": "scene.indoor.v1",
        "gate_id": "alpha.quality-high.v1",
        "kfp_audio": {
            "master_gain": 1.0,
            "ambient_gain": 0.4,
            "sfx_gain": 0.55,
            "ambient_sound": "MID",
            "grass_steps": True,
            "footsteps": True,
            "door_sound": True,
        },
        "status": "PASS",
        "evidence_class": "SYNTHETIC_CONTRACT",
        "cleanup": {
            "status": "PASS",
            "resources_released": True,
            "task_artifacts_removed": True,
            "source_trees_unchanged": True,
        },
        "artifacts": [artifact()],
    }


def no_host_result(gate_id, checkpoint_id, evidence_class):
    result = battle_art_result()
    result["result_id"] = f"result.{gate_id}.v1"
    result["host"] = {
        "host_id": "NO_HOST",
        "release": "none",
        "commit": None,
        "package_sha256": None,
        "released": False,
        "eligibility": "CONTROL_ONLY",
    }
    result["gate_id"] = gate_id
    result["checkpoint_id"] = checkpoint_id
    result["evidence_class"] = evidence_class
    return result


def dramaless_result():
    result = battle_art_result()
    result.update(
        {
            "result_id": "result.dramaless.candidate.v1",
            "host": {
                "host_id": "DRAMALESS_SHAPE",
                "release": "candidate-pr47",
                "commit": None,
                "package_sha256": None,
                "released": False,
                "eligibility": "INELIGIBLE_UNTIL_RELEASED",
            },
            "gate_id": "alpha.dramaless-released-companion.v1",
            "game_version": "RED",
            "status": "INELIGIBLE",
            "evidence_class": "PRIVATE_REDACTED_SUMMARY",
            "private_capture_sha256": SHA256,
            "cleanup": {
                "status": "NOT_RUN",
                "resources_released": False,
                "task_artifacts_removed": False,
                "source_trees_unchanged": True,
            },
        }
    )
    return result


def defect_ledger():
    transitions = [
        (None, "REPORTED"),
        ("REPORTED", "TRIAGED"),
        ("TRIAGED", "IN_PROGRESS"),
        ("IN_PROGRESS", "FIXED"),
        ("FIXED", "VERIFIED"),
    ]
    return {
        "schema_version": "1.0.0",
        "ledger_id": "ledger.alpha.v1",
        "source_commit": SOURCE_COMMIT,
        "package_sha256": SHA256,
        "defects": [
            {
                "defect_id": "defect.synthetic.v1",
                "title": "Synthetic contract defect",
                "gate_id": "alpha.qa-contract.v1",
                "checkpoint_id": CONTROL_ID,
                "severity": "S2_MEDIUM",
                "current_status": "VERIFIED",
                "evidence_class": "SYNTHETIC_CONTRACT",
                "artifact_hashes": [SHA256],
                "transitions": [
                    {
                        "transition_id": f"transition.{index}.v1",
                        "recorded_at": f"2026-08-23T00:00:0{index}Z",
                        "from_status": old,
                        "to_status": new,
                        "evidence_sha256": SHA256,
                    }
                    for index, (old, new) in enumerate(transitions)
                ],
            }
        ],
    }


class QaContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.matrix = load_json("visual-scene-matrix-v1.json")
        cls.route = load_json("smoke-route-v1.json")
        cls.defect_schema = load_json("defect-ledger.schema.json")
        cls.runtime_schema = load_json("runtime-result.schema.json")
        cls.gate_map = load_json("release-gate-map-v1.json")
        cls.parent_ledger = json.loads(
            (ROOT / "docs" / "prerelease-gates.json").read_text(encoding="utf-8")
        )
        cls.runtime_validator = Draft202012ContractValidator(cls.runtime_schema)
        cls.defect_validator = Draft202012ContractValidator(cls.defect_schema)

    def assertValid(self, validator, instance):
        errors = validator.errors(instance)
        self.assertEqual(errors, [], "\n".join(errors))

    def assertInvalid(self, validator, instance):
        self.assertTrue(validator.errors(instance), "fixture unexpectedly passed")

    def assertRuntimeValid(self, instance):
        errors = validate_runtime_result(instance, self.runtime_schema, self.gate_map)
        self.assertEqual(errors, [], "\n".join(errors))

    def assertRuntimeInvalid(self, instance):
        self.assertTrue(
            validate_runtime_result(instance, self.runtime_schema, self.gate_map),
            "runtime fixture unexpectedly passed",
        )

    def assertDefectValid(self, instance):
        errors = validate_defect_ledger(instance, self.defect_schema)
        self.assertEqual(errors, [], "\n".join(errors))

    def assertDefectInvalid(self, instance):
        self.assertTrue(
            validate_defect_ledger(instance, self.defect_schema),
            "defect fixture unexpectedly passed",
        )

    def test_contract_files_are_strict_versioned_json(self):
        self.assertEqual(self.defect_schema["$schema"], SCHEMA_DRAFT)
        self.assertEqual(self.runtime_schema["$schema"], SCHEMA_DRAFT)
        for document in (self.matrix, self.route, self.gate_map):
            self.assertEqual(document["contract_version"], "1.0.0")
            self.assertEqual(document["source_commit"], SOURCE_COMMIT)
        for schema in (self.runtime_schema, self.defect_schema):
            self.assertEqual(schema["additionalProperties"], False)
            self._assert_object_schemas_are_closed(schema)

    def _assert_object_schemas_are_closed(self, node, path="$"):
        if isinstance(node, dict):
            if node.get("type") == "object":
                self.assertIs(
                    node.get("additionalProperties"),
                    False,
                    f"open object schema at {path}",
                )
            for key, value in node.items():
                self._assert_object_schemas_are_closed(value, f"{path}.{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                self._assert_object_schemas_are_closed(value, f"{path}[{index}]")

    def test_scene_matrix_and_smoke_route_use_stable_rom_free_ids(self):
        matrix_ids = [item["scene_class_id"] for item in self.matrix["scene_classes"]]
        route_ids = [item["checkpoint_id"] for item in self.route["checkpoints"]]
        self.assertEqual(matrix_ids, SCENE_IDS)
        self.assertEqual(route_ids, [CONTROL_ID, *SCENE_IDS, ADVISORY_ID])
        self.assertEqual(
            [item["order"] for item in self.route["checkpoints"]],
            list(range(1, 16)),
        )
        self.assertEqual(self.route["coordinate_policy"], "DESCRIPTIVE_SCENE_CLASSES_ONLY")
        for checkpoint in self.route["checkpoints"]:
            self.assertEqual(checkpoint["qualities"], QUALITIES)
            for forbidden in ("coordinates", "map_id", "map_name", "rom_id", "save_id"):
                self.assertNotIn(forbidden, checkpoint)
        self.assertEqual(self.matrix["advisory_stress"]["checkpoint_id"], ADVISORY_ID)
        self.assertFalse(self.matrix["advisory_stress"]["release_blocking"])
        self.assertEqual(validate_matrix(self.matrix, self.route), [])

        expected_dimensions = {
            "game",
            "map_class",
            "weather",
            "time",
            "interior",
            "battle",
            "host",
            "camera_checkpoint",
            "expected_owner",
            "required_evidence",
            "quality_case_ids",
        }
        case_ids = []
        rows = [*self.matrix["scene_classes"], self.matrix["advisory_stress"]]
        for row in rows:
            with self.subTest(scene=row["scene_class"]):
                self.assertTrue(expected_dimensions.issubset(row))
                self.assertEqual(list(row["quality_case_ids"]), QUALITIES)
                case_base = row.get("authored_case_id", "dense_outdoor_64x64")
                self.assertEqual(
                    row["quality_case_ids"],
                    {
                        quality: f"{case_base}.{quality.lower()}.v1"
                        for quality in QUALITIES
                    },
                )
                case_ids.extend(row["quality_case_ids"].values())
        self.assertEqual(len(case_ids), len(set(case_ids)))

        invalid_matrix = copy.deepcopy(self.matrix)
        invalid_matrix["scene_classes"][0]["quality_case_ids"]["HIGH"] = (
            "indoor.high.changed.v1"
        )
        self.assertTrue(validate_matrix(invalid_matrix, self.route))

    def test_matrix_rejects_empty_wrong_and_broken_cross_link_values(self):
        mutations = [
            lambda matrix, route: matrix.__setitem__(
                "matrix_dimensions", matrix["matrix_dimensions"][:-1]
            ),
            lambda matrix, route: matrix["scene_classes"][0].__setitem__("game", []),
            lambda matrix, route: matrix["scene_classes"][0].__setitem__(
                "required_evidence", []
            ),
            lambda matrix, route: matrix["scene_classes"][0].__setitem__("host", "NO_HOST"),
            lambda matrix, route: matrix["scene_classes"][0].__setitem__(
                "quality_case_ids", {}
            ),
            lambda matrix, route: route["checkpoints"][1].__setitem__(
                "scene_class", "Wrong scene"
            ),
            lambda matrix, route: route["checkpoints"][1].__setitem__("qualities", []),
            lambda matrix, route: route["checkpoints"][1].__setitem__("host_scope", []),
            lambda matrix, route: route["checkpoints"][1].__setitem__(
                "fixture_class", "wrong"
            ),
            lambda matrix, route: route["checkpoints"][1].__setitem__(
                "release_role", "ADVISORY"
            ),
            lambda matrix, route: route["checkpoints"][0].__setitem__(
                "host_scope", []
            ),
        ]
        for mutate in mutations:
            matrix = copy.deepcopy(self.matrix)
            route = copy.deepcopy(self.route)
            mutate(matrix, route)
            with self.subTest(matrix=matrix, route=route):
                self.assertTrue(validate_matrix(matrix, route))

    def test_matrix_malformed_quality_ids_return_controlled_errors(self):
        fixtures = []
        malformed_object = copy.deepcopy(self.matrix)
        malformed_object["scene_classes"][0]["quality_case_ids"] = []
        fixtures.append(malformed_object)

        malformed_value = copy.deepcopy(self.matrix)
        malformed_value["scene_classes"][0]["quality_case_ids"]["LOW"] = []
        fixtures.append(malformed_value)

        malformed_scene_id = copy.deepcopy(self.matrix)
        malformed_scene_id["scene_classes"][0]["scene_class_id"] = []
        fixtures.append(malformed_scene_id)

        for fixture in fixtures:
            with self.subTest(fixture=fixture):
                errors = validate_matrix(fixture, self.route)
                self.assertTrue(errors)

    def test_matrix_and_route_reject_unknown_fields_at_every_object_level(self):
        mutations = [
            lambda matrix, route: matrix.__setitem__("unknown_field", True),
            lambda matrix, route: matrix["quality_tiers"][0].__setitem__(
                "unknown_field", True
            ),
            lambda matrix, route: matrix["host_matrix"][1].__setitem__(
                "unknown_field", True
            ),
            lambda matrix, route: matrix["scene_classes"][0].__setitem__(
                "unknown_field", True
            ),
            lambda matrix, route: matrix["scene_classes"][0][
                "quality_case_ids"
            ].__setitem__("UNKNOWN", "indoor.unknown.v1"),
            lambda matrix, route: matrix["advisory_stress"].__setitem__(
                "unknown_field", True
            ),
            lambda matrix, route: route.__setitem__("unknown_field", True),
            lambda matrix, route: route["checkpoints"][0].__setitem__(
                "unknown_field", True
            ),
        ]
        for mutate in mutations:
            matrix = copy.deepcopy(self.matrix)
            route = copy.deepcopy(self.route)
            mutate(matrix, route)
            with self.subTest(matrix=matrix, route=route):
                self.assertTrue(validate_matrix(matrix, route))

    def test_recursive_canonical_equality_is_type_strict(self):
        for right in (1, 1.0):
            fixtures = (
                ({"outer": {"value": True}}, {"outer": {"value": right}}),
                (["outer", [True]], ["outer", [right]]),
                (("outer", (True,)), ("outer", (right,))),
            )
            for left, changed in fixtures:
                with self.subTest(right=right, fixture=left):
                    self.assertFalse(json_equal(left, changed))
                    self.assertTrue(json_equal(left, copy.deepcopy(left)))

    def test_matrix_binds_exact_host_facts_route_scopes_and_evidence(self):
        mutations = [
            lambda matrix, route: matrix["host_matrix"][1].__setitem__(
                "host_id", "NO_HOST"
            ),
            lambda matrix, route: matrix["host_matrix"][1].__setitem__(
                "release", "1.9.9"
            ),
            lambda matrix, route: matrix["host_matrix"][1].__setitem__(
                "commit", "0" * 40
            ),
            lambda matrix, route: matrix["host_matrix"][1].__setitem__(
                "released", False
            ),
            lambda matrix, route: matrix["host_matrix"][1].__setitem__(
                "eligibility", "CONTROL_ONLY"
            ),
            lambda matrix, route: matrix["scene_classes"][0].__setitem__(
                "required_evidence",
                ["SYNTHETIC_CONTRACT", "NATIVE_REDACTED_SUMMARY"],
            ),
            lambda matrix, route: matrix["scene_classes"][0].__setitem__(
                "required_evidence",
                [
                    "SYNTHETIC_CONTRACT",
                    "NATIVE_REDACTED_SUMMARY",
                    "PRIVATE_REDACTED_SUMMARY",
                    "CONTROL",
                ],
            ),
            lambda matrix, route: route["checkpoints"][1].__setitem__(
                "host_scope", ["BATTLE_ART_VOXEL_FORK"]
            ),
            lambda matrix, route: route["checkpoints"][1].__setitem__(
                "host_scope",
                ["BATTLE_ART_VOXEL_FORK", "DRAMALESS_SHAPE", "NO_HOST"],
            ),
        ]
        for mutate in mutations:
            matrix = copy.deepcopy(self.matrix)
            route = copy.deepcopy(self.route)
            mutate(matrix, route)
            with self.subTest(matrix=matrix, route=route):
                self.assertTrue(validate_matrix(matrix, route))

    def test_list_and_object_checkpoint_ids_return_controlled_errors(self):
        for malformed in ([], {}):
            matrix = copy.deepcopy(self.matrix)
            matrix["scene_classes"][0]["scene_class_id"] = malformed
            self.assertTrue(validate_matrix(matrix, self.route))

            route = copy.deepcopy(self.route)
            route["checkpoints"][1]["checkpoint_id"] = malformed
            self.assertTrue(validate_matrix(self.matrix, route))

            runtime = battle_art_result()
            runtime["checkpoint_id"] = malformed
            self.assertRuntimeInvalid(runtime)

    def test_valid_runtime_results_cover_declared_special_gates(self):
        fixtures = [
            battle_art_result(),
            no_host_result("alpha.qa-contract.v1", CONTROL_ID, "SYNTHETIC_CONTRACT"),
            no_host_result("alpha.no-host-fail-closed.v1", CONTROL_ID, "CONTROL"),
            no_host_result("alpha.dense-stress-advisory.v1", ADVISORY_ID, "SYNTHETIC_CONTRACT"),
        ]
        dramaless = dramaless_result()
        fixtures.append(dramaless)
        for fixture in fixtures:
            with self.subTest(result_id=fixture["result_id"]):
                self.assertRuntimeValid(fixture)

    def test_runtime_rejects_private_paths_fields_raw_captures_and_secrets(self):
        mutations = []
        for field in ("rom_path", "save_path", "cache_path", "raw_capture"):
            mutations.append(lambda item, field=field: item.__setitem__(field, "forbidden"))
        mutations.extend(
            [
                lambda item: item["engine"].__setitem__("version", r"C:\\Users\\bo\\private"),
                lambda item: item["engine"].__setitem__("version", "/home/bo/private"),
                lambda item: item["engine"].__setitem__("version", "bo@example.invalid"),
                lambda item: item["engine"].__setitem__(
                    "version", "ghp" + "_secretvalue"
                ),
                lambda item: item["artifacts"][0].__setitem__("media_type", "image/png"),
                lambda item: item["artifacts"][0].__setitem__("raw_capture", True),
            ]
        )
        for mutate in mutations:
            fixture = battle_art_result()
            mutate(fixture)
            with self.subTest(fixture=fixture):
                self.assertRuntimeInvalid(fixture)

    def test_runtime_rejects_unknown_gates_missing_hashes_and_failed_cleanup(self):
        fixtures = []
        unknown_gate = battle_art_result()
        unknown_gate["gate_id"] = "alpha.unknown.v1"
        fixtures.append(unknown_gate)

        missing_package_hash = battle_art_result()
        del missing_package_hash["source"]["package_sha256"]
        fixtures.append(missing_package_hash)

        missing_artifact_hash = battle_art_result()
        del missing_artifact_hash["artifacts"][0]["sha256"]
        fixtures.append(missing_artifact_hash)

        failed_cleanup = battle_art_result()
        failed_cleanup["cleanup"]["status"] = "FAIL"
        failed_cleanup["cleanup"]["resources_released"] = False
        fixtures.append(failed_cleanup)

        extra_nested_field = battle_art_result()
        extra_nested_field["host"]["path"] = "relative"
        fixtures.append(extra_nested_field)

        for fixture in fixtures:
            with self.subTest(fixture=fixture):
                self.assertRuntimeInvalid(fixture)

    def test_runtime_gate_bindings_fail_closed(self):
        wrong_quality = battle_art_result()
        wrong_quality["quality"] = "LOW"
        self.assertRuntimeInvalid(wrong_quality)

        wrong_battle_release = battle_art_result()
        wrong_battle_release["host"]["release"] = "1.9.9"
        self.assertRuntimeInvalid(wrong_battle_release)

        control_with_synthetic_evidence = no_host_result(
            "alpha.no-host-fail-closed.v1", CONTROL_ID, "SYNTHETIC_CONTRACT"
        )
        self.assertRuntimeInvalid(control_with_synthetic_evidence)

        advisory_with_control_evidence = no_host_result(
            "alpha.dense-stress-advisory.v1", ADVISORY_ID, "CONTROL"
        )
        self.assertRuntimeInvalid(advisory_with_control_evidence)

        dramaless_pass = battle_art_result()
        dramaless_pass["host"] = {
            "host_id": "DRAMALESS_SHAPE",
            "release": "candidate-pr47",
            "commit": None,
            "package_sha256": None,
            "released": False,
            "eligibility": "INELIGIBLE_UNTIL_RELEASED",
        }
        self.assertRuntimeInvalid(dramaless_pass)

    def test_battle_art_corrected_hash_is_accepted_and_stale_hash_is_rejected(self):
        self.assertEqual(
            self.runtime_schema["$defs"]["battle_art_identity"]["properties"]
            ["package_sha256"]["const"],
            BATTLE_ART_PACKAGE_SHA256,
        )
        self.assertEqual(VALIDATOR_BATTLE_ART_PACKAGE_SHA256, BATTLE_ART_PACKAGE_SHA256)
        self.assertEqual(
            self.matrix["host_matrix"][1]["package_sha256"],
            BATTLE_ART_PACKAGE_SHA256,
        )
        self.assertRuntimeValid(battle_art_result())

        stale_runtime_fixture = battle_art_result()
        stale_runtime_fixture["host"]["package_sha256"] = (
            STALE_BATTLE_ART_PACKAGE_SHA256
        )
        self.assertRuntimeInvalid(stale_runtime_fixture)

        stale_visual_matrix_fixture = copy.deepcopy(self.matrix)
        stale_visual_matrix_fixture["host_matrix"][1]["package_sha256"] = (
            STALE_BATTLE_ART_PACKAGE_SHA256
        )
        self.assertTrue(validate_matrix(stale_visual_matrix_fixture, self.route))

    def test_runtime_rejects_wrong_game_host_quality_and_synthetic_battle_evidence(self):
        valid_battle = battle_art_result()
        valid_battle.update(
            {
                "gate_id": "alpha.battle-art-1.9.8.v1",
                "game_version": "RED",
                "evidence_class": "PRIVATE_REDACTED_SUMMARY",
                "private_capture_sha256": "b" * 64,
            }
        )
        self.assertRuntimeValid(valid_battle)

        wrong_game = copy.deepcopy(valid_battle)
        wrong_game["game_version"] = "SYNTHETIC"
        self.assertRuntimeInvalid(wrong_game)

        wrong_host = copy.deepcopy(valid_battle)
        wrong_host["host"] = {
            "host_id": "DRAMALESS_SHAPE",
            "release": "candidate-pr47",
            "commit": None,
            "package_sha256": None,
            "released": False,
            "eligibility": "INELIGIBLE_UNTIL_RELEASED",
        }
        self.assertRuntimeInvalid(wrong_host)

        wrong_quality = battle_art_result()
        wrong_quality["quality"] = "LOW"
        self.assertRuntimeInvalid(wrong_quality)

        synthetic_evidence = copy.deepcopy(valid_battle)
        synthetic_evidence["evidence_class"] = "SYNTHETIC_CONTRACT"
        del synthetic_evidence["private_capture_sha256"]
        self.assertRuntimeInvalid(synthetic_evidence)

    def test_runtime_couples_evidence_class_to_game_version(self):
        private_synthetic = battle_art_result()
        private_synthetic.update(
            {
                "gate_id": "alpha.authored-scenes.v1",
                "evidence_class": "PRIVATE_REDACTED_SUMMARY",
                "private_capture_sha256": "b" * 64,
            }
        )
        self.assertRuntimeInvalid(private_synthetic)

        native_synthetic = battle_art_result()
        native_synthetic.update(
            {
                "gate_id": "alpha.authored-scenes.v1",
                "evidence_class": "NATIVE_REDACTED_SUMMARY",
            }
        )
        self.assertRuntimeInvalid(native_synthetic)

        synthetic_real = battle_art_result()
        synthetic_real["game_version"] = "RED"
        self.assertRuntimeInvalid(synthetic_real)

        valid_private = copy.deepcopy(private_synthetic)
        valid_private["game_version"] = "YELLOW"
        self.assertRuntimeValid(valid_private)

        valid_native = copy.deepcopy(native_synthetic)
        valid_native["game_version"] = "BLUE"
        self.assertRuntimeValid(valid_native)

    def test_gate_map_rejects_invalid_battle_control_dense_and_no_host_authored(self):
        battle_control = battle_art_result()
        battle_control.update(
            {
                "gate_id": "alpha.no-host-fail-closed.v1",
                "checkpoint_id": CONTROL_ID,
                "evidence_class": "CONTROL",
            }
        )

        battle_dense = battle_art_result()
        battle_dense.update(
            {
                "gate_id": "alpha.dense-stress-advisory.v1",
                "checkpoint_id": ADVISORY_ID,
                "evidence_class": "SYNTHETIC_CONTRACT",
            }
        )

        no_host_authored = no_host_result(
            "alpha.authored-scenes.v1", "scene.indoor.v1", "SYNTHETIC_CONTRACT"
        )
        self.assertEqual(no_host_authored["status"], "PASS")

        battle_cleanup_control = battle_art_result()
        battle_cleanup_control.update(
            {
                "gate_id": "alpha.cleanup-integrity.v1",
                "checkpoint_id": CONTROL_ID,
                "evidence_class": "CONTROL",
            }
        )

        for fixture in (
            battle_control,
            battle_dense,
            no_host_authored,
            battle_cleanup_control,
        ):
            with self.subTest(result_id=fixture["result_id"], gate=fixture["gate_id"]):
                self.assertRuntimeInvalid(fixture)

    def test_runtime_requires_exact_host_audio_and_private_capture_bindings(self):
        hosts = {item["host_id"]: item for item in self.matrix["host_matrix"]}
        self.assertEqual(
            hosts["BATTLE_ART_VOXEL_FORK"]["commit"],
            "6586ef5f7a86c1bfefcea931bd6571538c9f8d15",
        )
        self.assertIsNone(hosts["DRAMALESS_SHAPE"]["commit"])

        valid_private = battle_art_result()
        valid_private.update(
            {
                "gate_id": "alpha.battle-art-1.9.8.v1",
                "game_version": "RED",
                "evidence_class": "PRIVATE_REDACTED_SUMMARY",
                "private_capture_sha256": "b" * 64,
            }
        )
        self.assertRuntimeValid(valid_private)

        mutations = [
            lambda item: item["host"].__setitem__("host_id", "NO_HOST"),
            lambda item: item["host"].__setitem__("release", "1.9.9"),
            lambda item: item["host"].pop("commit"),
            lambda item: item["host"].__setitem__("commit", "0" * 40),
            lambda item: item["host"].__setitem__("released", False),
            lambda item: item["host"].__setitem__("eligibility", "CONTROL_ONLY"),
            lambda item: item["kfp_audio"].pop("master_gain"),
            lambda item: item["kfp_audio"].pop("ambient_gain"),
            lambda item: item["kfp_audio"].pop("sfx_gain"),
            lambda item: item["kfp_audio"].__setitem__("master_gain", 1.01),
        ]
        for mutate in mutations:
            fixture = battle_art_result()
            mutate(fixture)
            with self.subTest(fixture=fixture):
                self.assertRuntimeInvalid(fixture)

        private_without_hash = copy.deepcopy(valid_private)
        del private_without_hash["private_capture_sha256"]
        self.assertRuntimeInvalid(private_without_hash)

        public_with_private_hash = battle_art_result()
        public_with_private_hash["private_capture_sha256"] = "b" * 64
        self.assertRuntimeInvalid(public_with_private_hash)

        malformed_private_hash = copy.deepcopy(valid_private)
        malformed_private_hash["private_capture_sha256"] = []
        self.assertRuntimeInvalid(malformed_private_hash)

        for forbidden in ("private_capture_path", "private_capture_content"):
            fixture = copy.deepcopy(valid_private)
            fixture[forbidden] = "forbidden"
            self.assertRuntimeInvalid(fixture)

    def test_defect_ledger_accepts_valid_history_and_rejects_private_data(self):
        valid = defect_ledger()
        self.assertDefectValid(valid)

        mutations = [
            lambda item: item.__setitem__("package_sha256", ""),
            lambda item: item["defects"][0].__setitem__("rom_path", "relative"),
            lambda item: item["defects"][0].__setitem__("title", r"C:\\Users\\bo\\private"),
            lambda item: item["defects"][0].__setitem__("title", "bo@example.invalid"),
            lambda item: item["defects"][0].__setitem__(
                "title", "ghp" + "_secretvalue"
            ),
            lambda item: item["defects"][0].__setitem__("artifact_hashes", []),
            lambda item: item["defects"][0]["transitions"][0].pop("evidence_sha256"),
        ]
        for mutate in mutations:
            fixture = defect_ledger()
            mutate(fixture)
            with self.subTest(fixture=fixture):
                self.assertDefectInvalid(fixture)

    def test_defect_schema_allows_only_declared_status_transitions(self):
        statuses = [
            "REPORTED",
            "TRIAGED",
            "IN_PROGRESS",
            "BLOCKED",
            "FIXED",
            "VERIFIED",
            "REOPENED",
            "CLOSED",
        ]
        allowed = {
            (None, "REPORTED"),
            ("REPORTED", "TRIAGED"),
            ("TRIAGED", "IN_PROGRESS"),
            ("TRIAGED", "BLOCKED"),
            ("TRIAGED", "CLOSED"),
            ("IN_PROGRESS", "BLOCKED"),
            ("IN_PROGRESS", "FIXED"),
            ("BLOCKED", "IN_PROGRESS"),
            ("BLOCKED", "FIXED"),
            ("BLOCKED", "CLOSED"),
            ("FIXED", "VERIFIED"),
            ("FIXED", "REOPENED"),
            ("VERIFIED", "CLOSED"),
            ("VERIFIED", "REOPENED"),
            ("REOPENED", "IN_PROGRESS"),
            ("REOPENED", "BLOCKED"),
            ("REOPENED", "FIXED"),
            ("CLOSED", "REOPENED"),
        }
        transition_schema = self.defect_schema["$defs"]["transition"]
        for old in [None, *statuses]:
            for new in statuses:
                transition = {
                    "transition_id": "transition.matrix.v1",
                    "recorded_at": "2026-08-23T00:00:00Z",
                    "from_status": old,
                    "to_status": new,
                    "evidence_sha256": SHA256,
                }
                errors = self.defect_validator.errors(transition, transition_schema)
                with self.subTest(old=old, new=new):
                    self.assertEqual(not errors, (old, new) in allowed, errors)

    def test_defect_semantics_reject_duplicate_ids_broken_chains_and_stale_status(self):
        valid = defect_ledger()
        self.assertDefectValid(valid)

        duplicate_transition = defect_ledger()
        duplicate_transition["defects"][0]["transitions"][1]["transition_id"] = (
            duplicate_transition["defects"][0]["transitions"][0]["transition_id"]
        )

        broken_chain = defect_ledger()
        broken_chain["defects"][0]["transitions"][2]["from_status"] = "BLOCKED"

        non_null_start = defect_ledger()
        non_null_start["defects"][0]["transitions"] = non_null_start["defects"][0][
            "transitions"
        ][1:]

        stale_current_status = defect_ledger()
        stale_current_status["defects"][0]["current_status"] = "FIXED"

        duplicate_across_defects = defect_ledger()
        second = copy.deepcopy(duplicate_across_defects["defects"][0])
        second["defect_id"] = "defect.second.v1"
        duplicate_across_defects["defects"].append(second)

        for fixture in (
            duplicate_transition,
            broken_chain,
            non_null_start,
            stale_current_status,
            duplicate_across_defects,
        ):
            with self.subTest(fixture=fixture):
                self.assertDefectInvalid(fixture)

    def test_malformed_defect_ids_return_controlled_validation_errors(self):
        malformed_defect = defect_ledger()
        malformed_defect["defects"][0]["defect_id"] = []

        malformed_transition = defect_ledger()
        malformed_transition["defects"][0]["transitions"][0]["transition_id"] = {}

        for fixture in (malformed_defect, malformed_transition):
            with self.subTest(fixture=fixture):
                errors = validate_defect_ledger(fixture, self.defect_schema)
                self.assertTrue(errors)

    def test_schemas_meta_validate_as_draft_2020_12_when_dependency_is_available(self):
        version, errors = meta_validate_schemas(
            {
                "runtime-result.schema.json": self.runtime_schema,
                "defect-ledger.schema.json": self.defect_schema,
            }
        )
        if version is None:
            self.skipTest("jsonschema dependency is not available in this interpreter")
        self.assertEqual(version, "4.25.1")
        self.assertEqual(errors, [])

    def test_runtime_schema_explicitly_requires_semantic_validation(self):
        requirement = self.runtime_schema.get("$comment", "")
        self.assertIn("Semantic validation is mandatory", requirement)
        self.assertIn("tools/validate_qa_contract.py --runtime-result", requirement)

        schema_only_misuse = battle_art_result()
        schema_only_misuse["quality"] = "LOW"
        self.assertEqual(self.runtime_validator.errors(schema_only_misuse), [])
        self.assertTrue(
            validate_runtime_result(
                schema_only_misuse, self.runtime_schema, self.gate_map
            )
        )

    def test_gate_map_rejects_unknown_fields_rules_and_required_gate_weakening(self):
        mutations = [
            lambda gate_map: gate_map.__setitem__("unknown_field", True),
            lambda gate_map: gate_map["gates"][0].__setitem__("unknown_field", True),
            lambda gate_map: gate_map["gates"][0]["result_rules"][0].__setitem__(
                "unknown_field", []
            ),
            lambda gate_map: gate_map["gates"][0].__setitem__(
                "pass_rule", "ALWAYS_PASS"
            ),
            lambda gate_map: gate_map["gates"][6].__setitem__("required", False),
            lambda gate_map: gate_map["gates"][6]["result_rules"][0].__setitem__(
                "game_versions", []
            ),
            lambda gate_map: gate_map["gates"][6].__setitem__(
                "cleanup_required", "true"
            ),
        ]
        for mutate in mutations:
            gate_map = copy.deepcopy(self.gate_map)
            mutate(gate_map)
            with self.subTest(gate_map=gate_map):
                self.assertTrue(validate_gate_map(gate_map, self.runtime_schema))

    def test_battle_release_gate_rejects_checkpoint_and_game_set_drift(self):
        def battle_rule(gate_map):
            gate = next(
                gate
                for gate in gate_map["gates"]
                if gate["gate_id"] == "alpha.battle-art-1.9.8.v1"
            )
            return gate["result_rules"][0]

        mutations = [
            lambda gate_map: battle_rule(gate_map).__setitem__(
                "checkpoint_ids", SCENE_IDS[:-1]
            ),
            lambda gate_map: battle_rule(gate_map).__setitem__(
                "checkpoint_ids", [*SCENE_IDS, CONTROL_ID]
            ),
            lambda gate_map: battle_rule(gate_map).__setitem__(
                "checkpoint_ids", [*SCENE_IDS[:-1], "checkpoint.unknown.v1"]
            ),
            lambda gate_map: battle_rule(gate_map).__setitem__(
                "game_versions", ["RED", "BLUE"]
            ),
            lambda gate_map: battle_rule(gate_map).__setitem__(
                "game_versions", ["RED", "BLUE", "YELLOW", "SYNTHETIC"]
            ),
            lambda gate_map: battle_rule(gate_map).__setitem__(
                "game_versions", ["RED", "BLUE", "UNKNOWN"]
            ),
        ]
        for mutate in mutations:
            gate_map = copy.deepcopy(self.gate_map)
            mutate(gate_map)
            with self.subTest(gate_map=gate_map):
                self.assertTrue(validate_gate_map(gate_map, self.runtime_schema))

    def test_gate_map_malformed_ids_return_controlled_errors(self):
        fixtures = []

        malformed_gate_id = copy.deepcopy(self.gate_map)
        malformed_gate_id["gates"][0]["gate_id"] = []
        fixtures.append(malformed_gate_id)

        malformed_checkpoint = copy.deepcopy(self.gate_map)
        malformed_checkpoint["gates"][0]["result_rules"][0][
            "checkpoint_ids"
        ] = [[]]
        fixtures.append(malformed_checkpoint)

        malformed_checkpoint_object = copy.deepcopy(self.gate_map)
        malformed_checkpoint_object["gates"][0]["result_rules"][0][
            "checkpoint_ids"
        ] = [{}]
        fixtures.append(malformed_checkpoint_object)

        for fixture in fixtures:
            with self.subTest(fixture=fixture):
                self.assertTrue(validate_gate_map(fixture, self.runtime_schema))

    def test_release_map_is_complete_and_fail_closed(self):
        self.assertEqual(self.gate_map["unknown_gate_policy"], "REJECT")
        self.assertEqual(
            self.gate_map["result_match_policy"],
            "ANY_DECLARED_RULE_MATCHES_OR_REJECT",
        )
        self.assertEqual(
            self.gate_map["release_ready_rule"],
            "ALL_QA_REQUIRED_GATES_PASS_AND_PARENT_PRERELEASE_LEDGER_APPROVED",
        )
        gates = self.gate_map["gates"]
        self.assertEqual([gate["gate_id"] for gate in gates], GATE_IDS)
        self.assertEqual(validate_gate_map(self.gate_map, self.runtime_schema), [])

        schema_gate_ids = self.runtime_schema["$defs"]["gate_id"]["enum"]
        schema_checkpoint_ids = self.runtime_schema["$defs"]["checkpoint_id"]["enum"]
        schema_games = self.runtime_schema["properties"]["game_version"]["enum"]
        schema_evidence = self.runtime_schema["$defs"]["evidence_class"]["enum"]
        schema_hosts = self.runtime_schema["$defs"]["host_identity"]["properties"]["host_id"]["enum"]
        for gate in gates:
            self.assertIn(gate["gate_id"], schema_gate_ids)
            self.assertTrue(set(gate["eligible_host_ids"]).issubset(schema_hosts))
            for rule in gate["result_rules"]:
                self.assertEqual(
                    set(rule),
                    {
                        "checkpoint_ids",
                        "game_versions",
                        "host_ids",
                        "qualities",
                        "statuses",
                        "evidence_classes",
                        "private_capture_policy",
                    },
                )
                self.assertTrue(set(rule["checkpoint_ids"]).issubset(schema_checkpoint_ids))
                self.assertTrue(set(rule["game_versions"]).issubset(schema_games))
                self.assertTrue(set(rule["evidence_classes"]).issubset(schema_evidence))
                self.assertTrue(set(rule["host_ids"]).issubset(schema_hosts))
                self.assertEqual(
                    rule["private_capture_policy"],
                    "REQUIRED_FOR_PRIVATE_EVIDENCE_FORBIDDEN_OTHERWISE",
                )
            self.assertTrue(gate["cleanup_required"])
            if gate["required"]:
                self.assertTrue(gate["release_blocking"])
                self.assertIn(gate["default_status"], ("BLOCKED", "INELIGIBLE"))
                self.assertNotEqual(gate["pass_rule"], "ADVISORY_ONLY")

        dramaless = next(
            gate for gate in gates
            if gate["gate_id"] == "alpha.dramaless-released-companion.v1"
        )
        self.assertEqual(dramaless["default_status"], "INELIGIBLE")
        self.assertEqual(dramaless["eligible_host_ids"], [])

        advisory = next(
            gate for gate in gates
            if gate["gate_id"] == "alpha.dense-stress-advisory.v1"
        )
        self.assertFalse(advisory["required"])
        self.assertFalse(advisory["release_blocking"])
        self.assertEqual(advisory["pass_rule"], "ADVISORY_ONLY")

    def test_matrix_semantics_are_frozen_against_substitution(self):
        mutations = [
            (
                "indoor-map-class",
                lambda matrix: matrix["scene_classes"][0].__setitem__(
                    "map_class", "CAVE"
                ),
            ),
            (
                "live-camera",
                lambda matrix: matrix["scene_classes"][0].__setitem__(
                    "camera_checkpoint", "SYNTHETIC_STRESS_FRAME"
                ),
            ),
            (
                "tier-string",
                lambda matrix: matrix["quality_tiers"][0].__setitem__(
                    "build_budget_ms", "0.5"
                ),
            ),
            (
                "tier-value",
                lambda matrix: matrix["quality_tiers"][0].__setitem__(
                    "build_budget_ms", 0.51
                ),
            ),
            (
                "authored-advisory",
                lambda matrix: matrix["scene_classes"][0].__setitem__(
                    "release_blocking", False
                ),
            ),
            (
                "advisory-blocking",
                lambda matrix: matrix["advisory_stress"].__setitem__(
                    "release_blocking", True
                ),
            ),
            (
                "matrix-source",
                lambda matrix: matrix.__setitem__("source_commit", "0" * 40),
            ),
            (
                "matrix-version",
                lambda matrix: matrix.__setitem__("contract_version", "1.0.1"),
            ),
        ]
        for label, mutate in mutations:
            matrix = copy.deepcopy(self.matrix)
            mutate(matrix)
            with self.subTest(case=label):
                errors = validate_matrix(matrix, self.route)
                self.assertTrue(errors)

    def test_matrix_route_and_parent_numeric_types_fail_closed(self):
        matrix_mutations = [
            ("authored-interior", lambda item: item["scene_classes"][0].__setitem__("interior", 1)),
            ("authored-blocking", lambda item: item["scene_classes"][0].__setitem__("release_blocking", 1)),
            ("advisory-interior", lambda item: item["advisory_stress"].__setitem__("interior", 0)),
            ("advisory-blocking", lambda item: item["advisory_stress"].__setitem__("release_blocking", 0)),
            ("host-released", lambda item: item["host_matrix"][1].__setitem__("released", 1)),
        ]
        for field in ("build_budget_ms", "density"):
            for value in (True, math.nan, math.inf, -math.inf):
                matrix_mutations.append(
                    (
                        f"{field}-{value!r}",
                        lambda item, field=field, value=value: item["quality_tiers"][0].__setitem__(field, value),
                    )
                )
        for field in ("cache_bytes", "draw_call_target", "panorama_width"):
            canonical = self.matrix["quality_tiers"][0][field]
            for value in (True, float(canonical)):
                matrix_mutations.append(
                    (
                        f"{field}-{value!r}",
                        lambda item, field=field, value=value: item["quality_tiers"][0].__setitem__(field, value),
                    )
                )
        for label, mutate in matrix_mutations:
            matrix = copy.deepcopy(self.matrix)
            mutate(matrix)
            with self.subTest(case=label):
                self.assertTrue(validate_matrix(matrix, self.route))

        for value in (True, 1.0):
            route = copy.deepcopy(self.route)
            route["checkpoints"][0]["order"] = value
            with self.subTest(route_order=value):
                self.assertTrue(validate_matrix(self.matrix, route))

            gate_map = copy.deepcopy(self.gate_map)
            gate_map["parent_release_gate"]["schema"] = value
            with self.subTest(parent_map_schema=value):
                self.assertTrue(validate_gate_map(gate_map, self.runtime_schema))

            parent = copy.deepcopy(self.parent_ledger)
            parent["schema"] = value
            with self.subTest(parent_ledger_schema=value):
                self.assertTrue(validate_parent_release_ledger(parent, self.gate_map))

        approval_not_boolean = copy.deepcopy(self.gate_map)
        approval_not_boolean["parent_release_gate"]["approval_required"] = 1
        self.assertTrue(validate_gate_map(approval_not_boolean, self.runtime_schema))

        changed_control = copy.deepcopy(self.route)
        changed_control["checkpoints"][0]["scene_class"] = "Changed control"
        self.assertTrue(validate_matrix(self.matrix, changed_control))

        self.assertEqual(validate_matrix(self.matrix, self.route), [])
        self.assertEqual(validate_gate_map(self.gate_map, self.runtime_schema), [])
        self.assertEqual(
            validate_parent_release_ledger(self.parent_ledger, self.gate_map), []
        )

    def test_host_package_identity_is_exact_and_null_when_unreleased(self):
        self.assertEqual(
            self.matrix["host_matrix"][1]["package_sha256"],
            BATTLE_ART_PACKAGE_SHA256,
        )
        self.assertRuntimeValid(battle_art_result())
        self.assertRuntimeValid(
            no_host_result("alpha.qa-contract.v1", CONTROL_ID, "SYNTHETIC_CONTRACT")
        )
        self.assertRuntimeValid(dramaless_result())

        invalid = []
        missing = battle_art_result()
        missing["host"].pop("package_sha256")
        invalid.append(("battle-missing", missing))
        wrong = battle_art_result()
        wrong["host"]["package_sha256"] = "b" * 64
        invalid.append(("battle-wrong", wrong))
        malformed = battle_art_result()
        malformed["host"]["package_sha256"] = "not-a-sha256"
        invalid.append(("battle-malformed", malformed))
        no_host_digest = no_host_result(
            "alpha.qa-contract.v1", CONTROL_ID, "SYNTHETIC_CONTRACT"
        )
        no_host_digest["host"]["package_sha256"] = SHA256
        invalid.append(("no-host-non-null", no_host_digest))
        dramaless_digest = dramaless_result()
        dramaless_digest["host"]["package_sha256"] = SHA256
        invalid.append(("dramaless-non-null", dramaless_digest))
        for label, fixture in invalid:
            with self.subTest(case=label):
                self.assertRuntimeInvalid(fixture)

        matrix_mutations = [
            (
                "matrix-battle-missing",
                lambda matrix: matrix["host_matrix"][1].pop("package_sha256"),
            ),
            (
                "matrix-battle-wrong",
                lambda matrix: matrix["host_matrix"][1].__setitem__(
                    "package_sha256", "b" * 64
                ),
            ),
            (
                "matrix-no-host-non-null",
                lambda matrix: matrix["host_matrix"][0].__setitem__(
                    "package_sha256", SHA256
                ),
            ),
            (
                "matrix-dramaless-non-null",
                lambda matrix: matrix["host_matrix"][2].__setitem__(
                    "package_sha256", SHA256
                ),
            ),
        ]
        for label, mutate in matrix_mutations:
            matrix = copy.deepcopy(self.matrix)
            mutate(matrix)
            with self.subTest(case=label):
                self.assertTrue(validate_matrix(matrix, self.route))

    def test_strict_json_loading_rejects_nonstandard_constants_and_main_catches(self):
        for constant in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(constant=constant):
                with self.assertRaises(QaContractLoadError):
                    parse_json(f'{{"value": {constant}}}', "runtime result")

        decode_error = UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid")
        with mock.patch.object(pathlib.Path, "read_text", side_effect=decode_error):
            with self.assertRaises(QaContractLoadError):
                contract_load_json(pathlib.Path("private-input.json"), "runtime result")

        stderr = io.StringIO()
        with mock.patch(
            "validate_qa_contract.load_json",
            side_effect=QaContractLoadError("runtime result"),
        ), contextlib.redirect_stderr(stderr):
            self.assertEqual(main([]), 1)
        output = stderr.getvalue()
        self.assertEqual(output, "qa-contract: runtime result: invalid JSON input\n")
        self.assertNotIn("Traceback", output)
        self.assertNotIn("C:\\", output)

    def test_numeric_and_timestamp_values_fail_closed(self):
        boundary = battle_art_result()
        boundary["kfp_audio"]["master_gain"] = 0
        boundary["kfp_audio"]["ambient_gain"] = 1
        boundary["kfp_audio"]["sfx_gain"] = 0.0
        boundary["recorded_at"] = "2026-08-23T23:59:59Z"
        self.assertRuntimeValid(boundary)

        for value in (math.nan, math.inf, -math.inf):
            fixture = battle_art_result()
            fixture["kfp_audio"]["master_gain"] = value
            with self.subTest(non_finite=value):
                self.assertRuntimeInvalid(fixture)

        boolean_gain = battle_art_result()
        boolean_gain["kfp_audio"]["master_gain"] = True
        self.assertRuntimeInvalid(boolean_gain)

        for timestamp in ("2026-02-30T00:00:00Z", "2026-08-23T00:00:00"):
            fixture = battle_art_result()
            fixture["recorded_at"] = timestamp
            with self.subTest(timestamp=timestamp):
                self.assertRuntimeInvalid(fixture)

        non_monotonic = defect_ledger()
        non_monotonic["defects"][0]["transitions"][2]["recorded_at"] = (
            "2026-08-23T00:00:01Z"
        )
        self.assertDefectInvalid(non_monotonic)

        impossible = defect_ledger()
        impossible["defects"][0]["transitions"][1]["recorded_at"] = (
            "2026-02-30T00:00:01Z"
        )
        self.assertDefectInvalid(impossible)

        timezone_free = defect_ledger()
        timezone_free["defects"][0]["transitions"][1]["recorded_at"] = (
            "2026-08-23T00:00:01"
        )
        self.assertDefectInvalid(timezone_free)

    def test_closed_defect_can_reopen_only_with_later_utc_transition(self):
        ledger = defect_ledger()
        transitions = ledger["defects"][0]["transitions"]
        transitions.extend(
            [
                {
                    "transition_id": "transition.5.v1",
                    "recorded_at": "2026-08-23T00:00:05Z",
                    "from_status": "VERIFIED",
                    "to_status": "CLOSED",
                    "evidence_sha256": SHA256,
                },
                {
                    "transition_id": "transition.6.v1",
                    "recorded_at": "2026-08-23T00:00:06Z",
                    "from_status": "CLOSED",
                    "to_status": "REOPENED",
                    "evidence_sha256": SHA256,
                },
                {
                    "transition_id": "transition.7.v1",
                    "recorded_at": "2026-08-23T00:00:07Z",
                    "from_status": "REOPENED",
                    "to_status": "FIXED",
                    "evidence_sha256": SHA256,
                },
            ]
        )
        ledger["defects"][0]["current_status"] = "FIXED"
        self.assertDefectValid(ledger)

    def test_readiness_composes_canonical_legal_statuses_with_parent_approval(self):
        self.assertEqual(
            validate_parent_release_ledger(self.parent_ledger, self.gate_map), []
        )
        self.assertIs(self.parent_ledger["approved"], False)
        statuses = {
            gate["gate_id"]: gate["default_status"]
            for gate in self.gate_map["gates"]
        }
        for gate in self.gate_map["gates"]:
            if gate["required"] and gate["gate_id"] != (
                "alpha.dramaless-released-companion.v1"
            ):
                statuses[gate["gate_id"]] = "PASS"
        self.assertFalse(
            evaluate_release_readiness(
                self.gate_map, self.parent_ledger, statuses
            )
        )

        approved_parent = copy.deepcopy(self.parent_ledger)
        approved_parent["approved"] = True
        self.assertFalse(
            evaluate_release_readiness(self.gate_map, approved_parent, statuses)
        )

        dramaless_pass = dict(statuses)
        dramaless_pass["alpha.dramaless-released-companion.v1"] = "PASS"
        with self.assertRaises(QaContractLogicError):
            evaluate_release_readiness(
                self.gate_map, approved_parent, dramaless_pass
            )

    def test_readiness_rejects_noncanonical_declarations_and_status_maps(self):
        approved_parent = copy.deepcopy(self.parent_ledger)
        approved_parent["approved"] = True
        statuses = {
            gate["gate_id"]: gate["default_status"]
            for gate in self.gate_map["gates"]
        }
        for gate in self.gate_map["gates"]:
            if gate["required"] and gate["gate_id"] != (
                "alpha.dramaless-released-companion.v1"
            ):
                statuses[gate["gate_id"]] = "PASS"

        declaration_mutations = [
            ("empty", lambda item: item.__setitem__("gates", [])),
            ("missing", lambda item: item["gates"].pop()),
            (
                "reordered",
                lambda item: item["gates"].__setitem__(
                    slice(0, 2), [item["gates"][1], item["gates"][0]]
                ),
            ),
            ("duplicated", lambda item: item["gates"].append(copy.deepcopy(item["gates"][0]))),
            (
                "altered",
                lambda item: item["gates"][0].__setitem__("default_status", "NOT_RUN"),
            ),
        ]
        for label, mutate in declaration_mutations:
            gate_map = copy.deepcopy(self.gate_map)
            mutate(gate_map)
            with self.subTest(declaration=label):
                self.assertTrue(validate_gate_map(gate_map, self.runtime_schema))
                with self.assertRaises(QaContractLogicError):
                    evaluate_release_readiness(gate_map, approved_parent, statuses)

        status_mutations = [
            (
                "missing-required",
                lambda item: item.pop("alpha.qa-contract.v1"),
            ),
            (
                "missing-advisory",
                lambda item: item.pop("alpha.dense-stress-advisory.v1"),
            ),
            ("unknown-gate", lambda item: item.__setitem__("alpha.unknown.v1", "PASS")),
            ("unknown-status", lambda item: item.__setitem__("alpha.qa-contract.v1", "UNKNOWN")),
            (
                "illegal-status",
                lambda item: item.__setitem__("alpha.dense-stress-advisory.v1", "INELIGIBLE"),
            ),
        ]
        for label, mutate in status_mutations:
            changed = dict(statuses)
            mutate(changed)
            with self.subTest(status=label):
                with self.assertRaises(QaContractLogicError):
                    evaluate_release_readiness(self.gate_map, approved_parent, changed)

        noncanonical_parent = copy.deepcopy(approved_parent)
        noncanonical_parent["schema"] = 2
        with self.assertRaises(QaContractLogicError):
            evaluate_release_readiness(self.gate_map, noncanonical_parent, statuses)

    def test_parent_mapping_and_gate_identity_are_immutable(self):
        mutations = [
            ("missing-parent", lambda item: item.pop("parent_release_gate")),
            (
                "parent-path",
                lambda item: item["parent_release_gate"].__setitem__(
                    "path", "docs/alternate.json"
                ),
            ),
            (
                "parent-schema",
                lambda item: item["parent_release_gate"].__setitem__("schema", 2),
            ),
            (
                "parent-version",
                lambda item: item["parent_release_gate"].__setitem__(
                    "release_version", "2.0.0-alpha.2"
                ),
            ),
            (
                "parent-tag",
                lambda item: item["parent_release_gate"].__setitem__(
                    "tag", "v2.0.0-alpha.2"
                ),
            ),
            (
                "parent-approval-field",
                lambda item: item["parent_release_gate"].__setitem__(
                    "approval_field", "passed"
                ),
            ),
            (
                "parent-not-required",
                lambda item: item["parent_release_gate"].__setitem__(
                    "approval_required", False
                ),
            ),
            (
                "old-readiness-rule",
                lambda item: item.__setitem__(
                    "release_ready_rule", "ALL_REQUIRED_GATES_PASS"
                ),
            ),
            (
                "gate-source",
                lambda item: item.__setitem__("source_commit", "0" * 40),
            ),
            (
                "gate-version",
                lambda item: item.__setitem__("contract_version", "1.0.1"),
            ),
        ]
        for label, mutate in mutations:
            gate_map = copy.deepcopy(self.gate_map)
            mutate(gate_map)
            with self.subTest(case=label):
                self.assertTrue(validate_gate_map(gate_map, self.runtime_schema))

        invalid_parent = copy.deepcopy(self.parent_ledger)
        invalid_parent["approved"] = "false"
        self.assertTrue(
            validate_parent_release_ledger(invalid_parent, self.gate_map)
        )
        for field, value in (
            ("schema", 2),
            ("release_version", "2.0.0-alpha.2"),
            ("tag", "v2.0.0-alpha.2"),
        ):
            parent = copy.deepcopy(self.parent_ledger)
            parent[field] = value
            with self.subTest(parent_field=field):
                self.assertTrue(
                    validate_parent_release_ledger(parent, self.gate_map)
                )


if __name__ == "__main__":
    unittest.main()
