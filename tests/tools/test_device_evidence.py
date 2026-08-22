import copy
import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "docs" / "release-evidence" / "device-result.schema.json"
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def resolve_ref(ref):
    assert ref.startswith("#/$defs/")
    return SCHEMA["$defs"][ref.removeprefix("#/$defs/")]


def validate(instance, schema=None, path="$"):
    """Small validator for the schema features used by this project test."""
    schema = SCHEMA if schema is None else schema
    if "$ref" in schema:
        validate(instance, resolve_ref(schema["$ref"]), path)
    for branch in schema.get("allOf", []):
        validate(instance, branch, path)
    if "oneOf" in schema:
        errors = []
        for branch in schema["oneOf"]:
            try:
                validate(instance, branch, path)
            except AssertionError as error:
                errors.append(str(error))
            else:
                break
        else:
            raise AssertionError(f"{path}: no oneOf branch matched: {errors}")
    if "if" in schema and is_valid(instance, schema["if"]):
        validate(instance, schema["then"], path)

    if "const" in schema:
        assert instance == schema["const"], f"{path}: expected {schema['const']!r}"
    if "enum" in schema:
        assert instance in schema["enum"], f"{path}: value is not allowed"

    expected_type = schema.get("type")
    if expected_type is not None:
        allowed = expected_type if isinstance(expected_type, list) else [expected_type]
        checks = {
            "null": lambda value: value is None,
            "boolean": lambda value: isinstance(value, bool),
            "integer": lambda value: isinstance(value, int) and not isinstance(value, bool),
            "number": lambda value: isinstance(value, (int, float)) and not isinstance(value, bool),
            "string": lambda value: isinstance(value, str),
            "array": lambda value: isinstance(value, list),
            "object": lambda value: isinstance(value, dict),
        }
        assert any(checks[name](instance) for name in allowed), f"{path}: wrong type"

    if isinstance(instance, str):
        assert len(instance) >= schema.get("minLength", 0), f"{path}: string is too short"
        assert len(instance) <= schema.get("maxLength", float("inf")), f"{path}: string is too long"
        if "pattern" in schema:
            assert re.fullmatch(schema["pattern"], instance), f"{path}: string pattern failed"

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        assert instance >= schema.get("minimum", -float("inf")), f"{path}: below minimum"
        assert instance <= schema.get("maximum", float("inf")), f"{path}: above maximum"

    if isinstance(instance, list):
        assert len(instance) >= schema.get("minItems", 0), f"{path}: too few items"
        assert len(instance) <= schema.get("maxItems", float("inf")), f"{path}: too many items"
        if schema.get("uniqueItems"):
            encoded = [json.dumps(value, sort_keys=True) for value in instance]
            assert len(encoded) == len(set(encoded)), f"{path}: duplicate items"
        for index, value in enumerate(instance):
            validate(value, schema.get("items", {}), f"{path}[{index}]")
        if "contains" in schema:
            assert any(is_valid(value, schema["contains"]) for value in instance), f"{path}: contains failed"

    if isinstance(instance, dict):
        required = schema.get("required", [])
        for name in required:
            assert name in instance, f"{path}: missing {name}"
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            unknown = set(instance) - set(properties)
            assert not unknown, f"{path}: unknown fields {sorted(unknown)}"
        for name, child_schema in properties.items():
            if name in instance:
                validate(instance[name], child_schema, f"{path}.{name}")


def is_valid(instance, schema):
    try:
        validate(instance, schema)
    except AssertionError:
        return False
    return True


def passing_record():
    digest = "a" * 64
    build = {
        "version": "2.0.0",
        "source_commit": "b" * 40,
        "package_sha256": digest,
        "released": True,
    }
    status_keys = (
        "scene_corpus", "camera_modes", "input", "no_host", "one_host",
        "multiple_hosts", "incompatible_api", "legacy_marker",
        "callback_faults", "lifecycle",
    )
    return {
        "schema": 1,
        "result_id": "windows-battle-art-001",
        "recorded_at": "2026-08-21T12:00:00Z",
        "classification": "pass",
        "failure_summary": None,
        "tester": {"alias": "Device Tester 01"},
        "platform": {
            "platform_class": "windows",
            "execution": "native_hardware",
            "os_name": "Windows 11",
            "os_version": "24H2",
            "architecture": "x86_64",
            "device_class": "Desktop reference",
            "gpu": "Reference GPU",
            "driver": "32.0.15",
            "memory_mib": 32768,
            "power_mode": "ac_power",
            "display_scale_percent": 100,
            "native_resolution": {"width": 2560, "height": 1440},
            "test_resolution": {"width": 1920, "height": 1080},
            "resolution_mode": "reference_1080p",
        },
        "builds": {
            "kfp": copy.deepcopy(build),
            "host": {**copy.deepcopy(build), "id": "BATTLE_ART_VOXEL_FORK"},
            "gen1recomp": copy.deepcopy(build),
        },
        "test_environment": {
            "quality_tier": "high",
            "fixed_clock": "12:00",
            "feature_seed": 12345,
            "options_sha256": digest,
            "input_modes": ["keyboard", "gamepad"],
            "game_coverage": ["red", "blue", "yellow"],
            "thermal_state": "stable",
        },
        "checks": {
            "functional": {name: "pass" for name in status_keys},
            "visual": {
                "human_review": "pass",
                "host_regression": "pass",
                "ui_layering": "pass",
                "photosensitivity_review": "pass",
            },
            "performance": {
                "status": "pass",
                "thresholds_met": True,
                "runs_per_variant": 5,
                "sample_seconds": 60,
                "kfp_cpu_p95_ms": 1.8,
                "host_only_frame_p95_ms": 15.0,
                "host_plus_kfp_frame_p95_ms": 16.0,
                "frame_regression_percent": 6.67,
                "max_build_over_budget_ms": 0.1,
                "uncached_scene_ready_ms": 220.0,
                "added_draw_calls_max": 40,
            },
            "leak": {
                "status": "pass",
                "transitions": 100,
                "soak_minutes": 30,
                "lua_heap_drift_percent": 3.0,
                "resource_growth": {
                    "mesh": 0, "image": 0, "canvas": 0,
                    "shader": 0, "audio_source": 0,
                },
            },
            "uninstall": {
                "status": "pass",
                "host_tree_before_sha256": digest,
                "host_tree_after_sha256": digest,
                "kfp_tree_before_sha256": digest,
                "kfp_tree_after_sha256": digest,
                "automatic_repair_or_delete": False,
                "unexpected_changes": 0,
            },
        },
        "evidence": [{
            "kind": "functional_report",
            "sha256": digest,
            "bytes": 4096,
            "media_type": "application/json",
            "redacted": True,
        }],
        "deviations": [],
        "attestation": {
            "native_device_truthful": True,
            "legally_owned_imports": True,
            "no_rom_data_public": True,
            "privacy_reviewed": True,
            "hashes_verified": True,
        },
    }


def walk_schemas(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk_schemas(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk_schemas(value)


class DeviceEvidenceSchemaTests(unittest.TestCase):
    def test_passing_record_is_valid(self):
        validate(passing_record())

    def test_platform_classes_are_complete_and_dramatic_shape_is_absent(self):
        allowed = set(resolve_ref("#/$defs/platform")["properties"]["platform_class"]["enum"])
        self.assertEqual(allowed, {
            "windows", "linux_x86_64", "linux_arm64", "macos_x86_64",
            "macos_arm64", "android", "ios_love12", "xbox_uwp",
            "nintendo_switch", "portmaster", "anbernic_stock",
        })
        host_ids = set(resolve_ref("#/$defs/host_identity")["properties"]["id"]["enum"])
        self.assertEqual(host_ids, {"BATTLE_ART_VOXEL_FORK", "DRAMALESS_SHAPE"})

    def test_every_free_string_and_array_is_bounded(self):
        for node in walk_schemas(SCHEMA):
            if node.get("type") == "string" and "const" not in node and "enum" not in node:
                self.assertIn("maxLength", node, node)
            if node.get("type") == "array":
                self.assertIn("maxItems", node, node)

    def test_private_paths_email_urls_and_long_text_are_rejected(self):
        for unsafe in (
            r"C:\\Users\\tester\\report.txt",
            "/home/tester/report.txt",
            "tester@example.com",
            "https://example.com/report",
            "x" * 161,
        ):
            record = passing_record()
            record["classification"] = "fail"
            record["failure_summary"] = unsafe
            with self.assertRaises(AssertionError, msg=unsafe):
                validate(record)

    def test_unknown_fields_are_rejected(self):
        record = passing_record()
        record["private_path"] = "hidden"
        with self.assertRaisesRegex(AssertionError, "unknown fields"):
            validate(record)

    def test_hashes_and_commits_must_be_immutable_full_values(self):
        record = passing_record()
        record["builds"]["kfp"]["source_commit"] = "b" * 12
        with self.assertRaises(AssertionError):
            validate(record)
        record = passing_record()
        record["builds"]["host"]["package_sha256"] = "A" * 64
        with self.assertRaises(AssertionError):
            validate(record)

    def test_reference_resolution_is_exactly_1080p(self):
        record = passing_record()
        record["platform"]["test_resolution"] = {"width": 1280, "height": 720}
        with self.assertRaises(AssertionError):
            validate(record)

    def test_pass_requires_native_released_complete_evidence(self):
        mutations = [
            lambda record: record["builds"]["host"].update(released=False),
            lambda record: record["platform"].update(execution="emulator"),
            lambda record: record["test_environment"].update(game_coverage=["yellow"]),
            lambda record: record["checks"]["visual"].update(human_review="not_run"),
            lambda record: record["checks"]["performance"].update(runs_per_variant=4),
            lambda record: record["checks"]["leak"].update(transitions=99),
            lambda record: record["checks"]["uninstall"].update(unexpected_changes=1),
            lambda record: record["attestation"].update(no_rom_data_public=False),
        ]
        for mutate in mutations:
            record = passing_record()
            mutate(record)
            with self.assertRaises(AssertionError):
                validate(record)

    def test_experimental_allows_incomplete_but_not_failed_checks(self):
        record = passing_record()
        record["classification"] = "experimental"
        record["builds"]["host"]["released"] = False
        record["checks"]["visual"]["human_review"] = "not_run"
        validate(record)
        record["checks"]["visual"]["human_review"] = "fail"
        with self.assertRaises(AssertionError):
            validate(record)

    def test_fail_requires_public_safe_summary(self):
        record = passing_record()
        record["classification"] = "fail"
        record["checks"]["functional"]["lifecycle"] = "fail"
        record["failure_summary"] = "Host stopped after the injected callback fault"
        validate(record)
        record["failure_summary"] = None
        with self.assertRaises(AssertionError):
            validate(record)


if __name__ == "__main__":
    unittest.main()
