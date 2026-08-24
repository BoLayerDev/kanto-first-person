import argparse
import datetime
import hashlib
import importlib.metadata
import json
import math
import pathlib
import re
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
QA = ROOT / "docs" / "qa"

GATE_MAP_FIELDS = {
    "contract_id",
    "contract_version",
    "source_commit",
    "unknown_gate_policy",
    "result_match_policy",
    "readiness_scope",
    "parent_release_gate",
    "release_ready_rule",
    "gates",
}
PARENT_RELEASE_GATE_FIELDS = {
    "path",
    "schema",
    "release_version",
    "tag",
    "approval_field",
    "approval_required",
}
GATE_MAP_IDENTITY = (
    "kfp.release-gate-map.v1",
    "1.0.0",
    "e540c3b3de25caa5fa855dd6c3c702449ed9e72c",
)
PARENT_RELEASE_GATE = {
    "path": "docs/prerelease-gates.json",
    "schema": 1,
    "release_version": "2.0.0-alpha.1",
    "tag": "v2.0.0-alpha.1",
    "approval_field": "approved",
    "approval_required": True,
}
RELEASE_READY_RULE = (
    "ALL_QA_REQUIRED_GATES_PASS_AND_PARENT_PRERELEASE_LEDGER_APPROVED"
)
BATTLE_ART_PACKAGE_SHA256 = (
    "28c06d4153087be28891090d2d85d039f7cd81ba69f74c56a069016b3adf58bd"
)
CANONICAL_GATE_DECLARATIONS_SHA256 = (
    "cca5e5cf1647f6b879daad1f55b33b133d6f95424c98ab2a8776883dd1b6dcff"
)
GATE_FIELDS = {
    "gate_id",
    "required",
    "release_blocking",
    "default_status",
    "pass_rule",
    "result_rules",
    "eligible_host_ids",
    "cleanup_required",
}
RULE_FIELDS = {
    "checkpoint_ids",
    "game_versions",
    "host_ids",
    "qualities",
    "statuses",
    "evidence_classes",
    "private_capture_policy",
}
PRIVATE_CAPTURE_POLICY = "REQUIRED_FOR_PRIVATE_EVIDENCE_FORBIDDEN_OTHERWISE"
PASS_RULES = {
    "ALL_MATCHING_RESULTS_PASS",
    "RELEASED_ELIGIBLE_HOST_AND_ALL_MATCHING_RESULTS_PASS",
    "ADVISORY_ONLY",
}
REQUIRED_GATE_INVARIANTS = {
    "alpha.qa-contract.v1": ("BLOCKED", "ALL_MATCHING_RESULTS_PASS", ["NO_HOST"]),
    "alpha.no-host-fail-closed.v1": (
        "BLOCKED",
        "ALL_MATCHING_RESULTS_PASS",
        ["NO_HOST"],
    ),
    "alpha.authored-scenes.v1": (
        "BLOCKED",
        "ALL_MATCHING_RESULTS_PASS",
        ["BATTLE_ART_VOXEL_FORK"],
    ),
    "alpha.quality-low.v1": (
        "BLOCKED",
        "ALL_MATCHING_RESULTS_PASS",
        ["BATTLE_ART_VOXEL_FORK"],
    ),
    "alpha.quality-balanced.v1": (
        "BLOCKED",
        "ALL_MATCHING_RESULTS_PASS",
        ["BATTLE_ART_VOXEL_FORK"],
    ),
    "alpha.quality-high.v1": (
        "BLOCKED",
        "ALL_MATCHING_RESULTS_PASS",
        ["BATTLE_ART_VOXEL_FORK"],
    ),
    "alpha.battle-art-1.9.8.v1": (
        "BLOCKED",
        "ALL_MATCHING_RESULTS_PASS",
        ["BATTLE_ART_VOXEL_FORK"],
    ),
    "alpha.dramaless-released-companion.v1": (
        "INELIGIBLE",
        "RELEASED_ELIGIBLE_HOST_AND_ALL_MATCHING_RESULTS_PASS",
        [],
    ),
    "alpha.cleanup-integrity.v1": (
        "BLOCKED",
        "ALL_MATCHING_RESULTS_PASS",
        ["NO_HOST", "BATTLE_ART_VOXEL_FORK"],
    ),
    "alpha.public-evidence-privacy.v1": (
        "BLOCKED",
        "ALL_MATCHING_RESULTS_PASS",
        ["NO_HOST", "BATTLE_ART_VOXEL_FORK"],
    ),
}
ADVISORY_GATE_INVARIANT = (
    "alpha.dense-stress-advisory.v1",
    "ADVISORY",
    "ADVISORY_ONLY",
    ["NO_HOST"],
)

MATRIX_DIMENSIONS = [
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
]
MATRIX_SCENE_IDS = [
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
REAL_GAME_VERSIONS = ["RED", "BLUE", "YELLOW"]
BATTLE_ART_HOST = {
    "host_id": "BATTLE_ART_VOXEL_FORK",
    "release": "1.9.8",
    "commit": "6586ef5f7a86c1bfefcea931bd6571538c9f8d15",
    "package_sha256": BATTLE_ART_PACKAGE_SHA256,
    "released": True,
    "eligibility": "ELIGIBLE",
    "role": "REQUIRED_HOST",
}
MATRIX_FIELDS = {
    "contract_id",
    "contract_version",
    "source_commit",
    "fixture_kind",
    "matrix_dimensions",
    "quality_tiers",
    "host_matrix",
    "scene_classes",
    "advisory_stress",
}
QUALITY_TIER_FIELDS = {
    "quality",
    "build_budget_ms",
    "cache_bytes",
    "density",
    "draw_call_target",
    "panorama_width",
}
HOST_MATRIX_FIELDS = {
    "host_id",
    "release",
    "commit",
    "package_sha256",
    "released",
    "eligibility",
    "role",
}
SCENE_FIELDS = {
    "scene_class_id",
    "authored_case_id",
    "scene_class",
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
    "coverage",
    "qualities",
    "release_blocking",
}
ADVISORY_FIELDS = {
    "checkpoint_id",
    "scene_class",
    "fixture_kind",
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
    "qualities",
    "release_blocking",
    "claim",
}
QUALITY_CASE_FIELDS = {"LOW", "BALANCED", "HIGH"}
ROUTE_FIELDS = {
    "contract_id",
    "contract_version",
    "source_commit",
    "coordinate_policy",
    "checkpoints",
}
ROUTE_CHECKPOINT_FIELDS = {
    "checkpoint_id",
    "order",
    "scene_class",
    "fixture_class",
    "qualities",
    "host_scope",
    "release_role",
}
MATRIX_ALLOWED_VALUES = {
    "game": {"RED", "BLUE", "YELLOW", "SYNTHETIC"},
    "map_class": {
        "INDOOR",
        "CAVE",
        "FOREST",
        "CITY",
        "ROUTE",
        "OUTDOOR",
        "SHORE",
        "MOUNTAIN",
        "BATTLE",
        "DENSE_OUTDOOR_64X64",
    },
    "weather": {"NONE", "CLEAR", "RAIN", "STORM"},
    "time": {"ANY", "DAY", "NIGHT"},
    "battle": {"NONE", "SUPPORTED", "UNSUPPORTED"},
    "host": {"BATTLE_ART_VOXEL_FORK", "NO_HOST"},
    "camera_checkpoint": {"FIRST_PERSON_SETTLED", "SYNTHETIC_STRESS_FRAME"},
    "expected_owner": {"KFP"},
    "required_evidence": {
        "SYNTHETIC_CONTRACT",
        "NATIVE_REDACTED_SUMMARY",
        "PRIVATE_REDACTED_SUMMARY",
    },
}

MATRIX_IDENTITY = (
    "kfp.visual-scene-matrix.v1",
    "1.0.0",
    "e540c3b3de25caa5fa855dd6c3c702449ed9e72c",
    "authored-rom-free-synthetic-v1",
)
ROUTE_IDENTITY = (
    "kfp.smoke-route.v1",
    "1.0.0",
    "e540c3b3de25caa5fa855dd6c3c702449ed9e72c",
)
FROZEN_MATRIX_DIMENSIONS = tuple(MATRIX_DIMENSIONS)
FROZEN_QUALITY_TIERS = (
    ("LOW", 0.5, 33554432, 0.3, 20, 1024),
    ("BALANCED", 1.0, 67108864, 0.6, 32, 2048),
    ("HIGH", 2.0, 134217728, 1.0, 48, 4096),
)
FROZEN_HOST_MATRIX = (
    ("NO_HOST", "none", None, None, False, "CONTROL_ONLY", "FAIL_CLOSED_CONTROL"),
    (
        "BATTLE_ART_VOXEL_FORK",
        "1.9.8",
        "6586ef5f7a86c1bfefcea931bd6571538c9f8d15",
        BATTLE_ART_PACKAGE_SHA256,
        True,
        "ELIGIBLE",
        "REQUIRED_HOST",
    ),
    (
        "DRAMALESS_SHAPE",
        "candidate-pr47",
        None,
        None,
        False,
        "INELIGIBLE_UNTIL_RELEASED",
        "CANDIDATE_HOST",
    ),
)
FROZEN_SCENE_SEMANTICS = (
    ("scene.indoor.v1", "indoor", "Indoor authored scene", ("RED", "BLUE", "YELLOW"), "INDOOR", "NONE", "ANY", True, "NONE", "BATTLE_ART_VOXEL_FORK", "FIRST_PERSON_SETTLED", "KFP", ("SYNTHETIC_CONTRACT", "NATIVE_REDACTED_SUMMARY", "PRIVATE_REDACTED_SUMMARY"), (("LOW", "indoor.low.v1"), ("BALANCED", "indoor.balanced.v1"), ("HIGH", "indoor.high.v1")), ("ceiling", "cutaway", "doors", "windows", "posters", "rails", "lamp_fittings"), ("LOW", "BALANCED", "HIGH"), True),
    ("scene.cave.v1", "cave", "Cave authored scene", ("RED", "BLUE", "YELLOW"), "CAVE", "NONE", "ANY", True, "NONE", "BATTLE_ART_VOXEL_FORK", "FIRST_PERSON_SETTLED", "KFP", ("SYNTHETIC_CONTRACT", "NATIVE_REDACTED_SUMMARY", "PRIVATE_REDACTED_SUMMARY"), (("LOW", "cave.low.v1"), ("BALANCED", "cave.balanced.v1"), ("HIGH", "cave.high.v1")), ("roof", "formations", "water", "sconces", "particles"), ("LOW", "BALANCED", "HIGH"), True),
    ("scene.forest.v1", "forest", "Forest authored scene", ("RED", "BLUE", "YELLOW"), "FOREST", "CLEAR", "DAY", False, "NONE", "BATTLE_ART_VOXEL_FORK", "FIRST_PERSON_SETTLED", "KFP", ("SYNTHETIC_CONTRACT", "NATIVE_REDACTED_SUMMARY", "PRIVATE_REDACTED_SUMMARY"), (("LOW", "forest.low.v1"), ("BALANCED", "forest.balanced.v1"), ("HIGH", "forest.high.v1")), ("canopy", "vines", "grass", "sun_shafts", "tree_support"), ("LOW", "BALANCED", "HIGH"), True),
    ("scene.city-lavender.v1", "city_lavender", "Lavender city authored scene", ("RED", "BLUE", "YELLOW"), "CITY", "CLEAR", "ANY", False, "NONE", "BATTLE_ART_VOXEL_FORK", "FIRST_PERSON_SETTLED", "KFP", ("SYNTHETIC_CONTRACT", "NATIVE_REDACTED_SUMMARY", "PRIVATE_REDACTED_SUMMARY"), (("LOW", "city_lavender.low.v1"), ("BALANCED", "city_lavender.balanced.v1"), ("HIGH", "city_lavender.high.v1")), ("city_horizon", "buildings", "chimneys", "tree_support"), ("LOW", "BALANCED", "HIGH"), True),
    ("scene.route-neighbor-edge.v1", "route_neighbor_edge", "Route neighbor-edge authored scene", ("RED", "BLUE", "YELLOW"), "ROUTE", "CLEAR", "DAY", False, "NONE", "BATTLE_ART_VOXEL_FORK", "FIRST_PERSON_SETTLED", "KFP", ("SYNTHETIC_CONTRACT", "NATIVE_REDACTED_SUMMARY", "PRIVATE_REDACTED_SUMMARY"), (("LOW", "route_neighbor_edge.low.v1"), ("BALANCED", "route_neighbor_edge.balanced.v1"), ("HIGH", "route_neighbor_edge.high.v1")), ("world_apron", "neighbor_seam", "trees", "object_shadows"), ("LOW", "BALANCED", "HIGH"), True),
    ("scene.shore.v1", "shore", "Shore authored scene", ("RED", "BLUE", "YELLOW"), "SHORE", "CLEAR", "DAY", False, "NONE", "BATTLE_ART_VOXEL_FORK", "FIRST_PERSON_SETTLED", "KFP", ("SYNTHETIC_CONTRACT", "NATIVE_REDACTED_SUMMARY", "PRIVATE_REDACTED_SUMMARY"), (("LOW", "shore.low.v1"), ("BALANCED", "shore.balanced.v1"), ("HIGH", "shore.high.v1")), ("water_boundary", "shore_foam", "world_apron"), ("LOW", "BALANCED", "HIGH"), True),
    ("scene.mountain.v1", "mountain", "Mountain authored scene", ("RED", "BLUE", "YELLOW"), "MOUNTAIN", "CLEAR", "DAY", False, "NONE", "BATTLE_ART_VOXEL_FORK", "FIRST_PERSON_SETTLED", "KFP", ("SYNTHETIC_CONTRACT", "NATIVE_REDACTED_SUMMARY", "PRIVATE_REDACTED_SUMMARY"), (("LOW", "mountain.low.v1"), ("BALANCED", "mountain.balanced.v1"), ("HIGH", "mountain.high.v1")), ("peaks", "supports", "boulder_trees", "shadow_casters"), ("LOW", "BALANCED", "HIGH"), True),
    ("scene.day.v1", "day", "Day sky authored scene", ("RED", "BLUE", "YELLOW"), "OUTDOOR", "CLEAR", "DAY", False, "NONE", "BATTLE_ART_VOXEL_FORK", "FIRST_PERSON_SETTLED", "KFP", ("SYNTHETIC_CONTRACT", "NATIVE_REDACTED_SUMMARY", "PRIVATE_REDACTED_SUMMARY"), (("LOW", "day.low.v1"), ("BALANCED", "day.balanced.v1"), ("HIGH", "day.high.v1")), ("horizon", "clouds", "tree_support"), ("LOW", "BALANCED", "HIGH"), True),
    ("scene.night.v1", "night", "Night sky authored scene", ("RED", "BLUE", "YELLOW"), "OUTDOOR", "CLEAR", "NIGHT", False, "NONE", "BATTLE_ART_VOXEL_FORK", "FIRST_PERSON_SETTLED", "KFP", ("SYNTHETIC_CONTRACT", "NATIVE_REDACTED_SUMMARY", "PRIVATE_REDACTED_SUMMARY"), (("LOW", "night.low.v1"), ("BALANCED", "night.balanced.v1"), ("HIGH", "night.high.v1")), ("stars", "fireflies", "tree_support"), ("LOW", "BALANCED", "HIGH"), True),
    ("scene.rain.v1", "rain", "Rain weather authored scene", ("RED", "BLUE", "YELLOW"), "OUTDOOR", "RAIN", "ANY", False, "NONE", "BATTLE_ART_VOXEL_FORK", "FIRST_PERSON_SETTLED", "KFP", ("SYNTHETIC_CONTRACT", "NATIVE_REDACTED_SUMMARY", "PRIVATE_REDACTED_SUMMARY"), (("LOW", "rain.low.v1"), ("BALANCED", "rain.balanced.v1"), ("HIGH", "rain.high.v1")), ("rain", "umbrella", "weather_layering"), ("LOW", "BALANCED", "HIGH"), True),
    ("scene.storm.v1", "storm", "Storm weather authored scene", ("RED", "BLUE", "YELLOW"), "OUTDOOR", "STORM", "ANY", False, "NONE", "BATTLE_ART_VOXEL_FORK", "FIRST_PERSON_SETTLED", "KFP", ("SYNTHETIC_CONTRACT", "NATIVE_REDACTED_SUMMARY", "PRIVATE_REDACTED_SUMMARY"), (("LOW", "storm.low.v1"), ("BALANCED", "storm.balanced.v1"), ("HIGH", "storm.high.v1")), ("storm_rain", "weather_layering", "host_continuity"), ("LOW", "BALANCED", "HIGH"), True),
    ("scene.battle-supported.v1", "battle_supported", "Battle pass supported authored scene", ("RED", "BLUE", "YELLOW"), "BATTLE", "NONE", "ANY", False, "SUPPORTED", "BATTLE_ART_VOXEL_FORK", "FIRST_PERSON_SETTLED", "KFP", ("SYNTHETIC_CONTRACT", "NATIVE_REDACTED_SUMMARY", "PRIVATE_REDACTED_SUMMARY"), (("LOW", "battle_supported.low.v1"), ("BALANCED", "battle_supported.balanced.v1"), ("HIGH", "battle_supported.high.v1")), ("battle_props", "tree_support", "mountain_support", "host_continuity"), ("LOW", "BALANCED", "HIGH"), True),
    ("scene.battle-unsupported.v1", "battle_unsupported", "Battle pass unsupported authored scene", ("RED", "BLUE", "YELLOW"), "BATTLE", "NONE", "ANY", False, "UNSUPPORTED", "BATTLE_ART_VOXEL_FORK", "FIRST_PERSON_SETTLED", "KFP", ("SYNTHETIC_CONTRACT", "NATIVE_REDACTED_SUMMARY", "PRIVATE_REDACTED_SUMMARY"), (("LOW", "battle_unsupported.low.v1"), ("BALANCED", "battle_unsupported.balanced.v1"), ("HIGH", "battle_unsupported.high.v1")), ("empty_battle_pass", "tree_support", "mountain_support", "host_continuity"), ("LOW", "BALANCED", "HIGH"), True),
)
FROZEN_ADVISORY_SEMANTICS = (
    "advisory.dense-outdoor-64x64.v1",
    "Dense outdoor advisory stress",
    "generated-rom-free-synthetic-v1",
    ("SYNTHETIC",),
    "DENSE_OUTDOOR_64X64",
    "CLEAR",
    "DAY",
    False,
    "NONE",
    "NO_HOST",
    "SYNTHETIC_STRESS_FRAME",
    "KFP",
    ("SYNTHETIC_CONTRACT",),
    (("LOW", "dense_outdoor_64x64.low.v1"), ("BALANCED", "dense_outdoor_64x64.balanced.v1"), ("HIGH", "dense_outdoor_64x64.high.v1")),
    ("LOW", "BALANCED", "HIGH"),
    False,
    "STRUCTURAL_AND_ADVISORY_ONLY",
)


class QaContractLoadError(Exception):
    """A sanitized, controlled JSON load failure."""

    def __init__(self, label):
        super().__init__(f"{label}: invalid JSON input")
        self.label = label


class QaContractLogicError(Exception):
    """A controlled fail-closed contract logic failure."""


class _JsonParseConstantError(ValueError):
    pass


class _DuplicateJsonKeyError(ValueError):
    pass


def reject_duplicate_keys(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise _DuplicateJsonKeyError
        value[key] = item
    return value


def _reject_json_constant(_value):
    raise _JsonParseConstantError


def parse_json(text, label="JSON input"):
    try:
        return json.loads(
            text,
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except (json.JSONDecodeError, _JsonParseConstantError, _DuplicateJsonKeyError, TypeError):
        raise QaContractLoadError(label) from None


def load_json(path, label="JSON input"):
    try:
        text = pathlib.Path(path).read_text(encoding="utf-8")
        return parse_json(text, label)
    except QaContractLoadError:
        raise
    except (UnicodeDecodeError, OSError):
        raise QaContractLoadError(label) from None


def _parse_utc_timestamp(value):
    if not isinstance(value, str) or re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", value
    ) is None:
        raise ValueError("timestamp must use strict RFC 3339 UTC form")
    parsed = datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    return parsed.replace(tzinfo=datetime.timezone.utc)


def json_equal(left, right):
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return set(left) == set(right) and all(
            json_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, (list, tuple)):
        return len(left) == len(right) and all(
            json_equal(left_item, right_item)
            for left_item, right_item in zip(left, right)
        )
    return left == right


def _is_strict_json_value(value):
    if value is None or type(value) in (str, bool, int):
        return True
    if type(value) is float:
        return math.isfinite(value)
    if type(value) is list:
        return all(_is_strict_json_value(item) for item in value)
    if type(value) is dict:
        return all(
            type(key) is str and _is_strict_json_value(item)
            for key, item in value.items()
        )
    return False


def _is_canonical_gate_map(gate_map):
    if type(gate_map) is not dict or set(gate_map) != GATE_MAP_FIELDS:
        return False
    identity = (
        gate_map.get("contract_id"),
        gate_map.get("contract_version"),
        gate_map.get("source_commit"),
    )
    if not json_equal(identity, GATE_MAP_IDENTITY):
        return False
    if gate_map.get("unknown_gate_policy") != "REJECT":
        return False
    if gate_map.get("result_match_policy") != "ANY_DECLARED_RULE_MATCHES_OR_REJECT":
        return False
    if gate_map.get("readiness_scope") != "QA_SUBGATE_ONLY":
        return False
    if not json_equal(gate_map.get("parent_release_gate"), PARENT_RELEASE_GATE):
        return False
    if gate_map.get("release_ready_rule") != RELEASE_READY_RULE:
        return False
    gates = gate_map.get("gates")
    if type(gates) is not list or not _is_strict_json_value(gates):
        return False
    try:
        payload = json.dumps(
            gates,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError):
        return False
    return hashlib.sha256(payload).hexdigest() == CANONICAL_GATE_DECLARATIONS_SHA256


class Draft202012ContractValidator:
    """Validate the Draft 2020-12 keywords used by the KFP QA schemas."""

    def __init__(self, root_schema):
        self.root = root_schema

    def errors(self, instance, schema=None, path="$"):
        schema = self.root if schema is None else schema
        errors = []

        if "$ref" in schema:
            target = self.root
            reference = schema["$ref"]
            if not reference.startswith("#/"):
                return [f"{path}: unsupported non-local reference {reference}"]
            for part in reference[2:].split("/"):
                target = target[part.replace("~1", "/").replace("~0", "~")]
            errors.extend(self.errors(instance, target, path))

        for child in schema.get("allOf", []):
            errors.extend(self.errors(instance, child, path))

        if "oneOf" in schema:
            matches = sum(
                not self.errors(instance, child, path)
                for child in schema["oneOf"]
            )
            if matches != 1:
                errors.append(f"{path}: expected one oneOf match, got {matches}")

        if "if" in schema and not self.errors(instance, schema["if"], path):
            errors.extend(self.errors(instance, schema.get("then", {}), path))

        if "const" in schema and not json_equal(instance, schema["const"]):
            errors.append(f"{path}: value does not match const")

        if "enum" in schema and not any(
            json_equal(instance, item) for item in schema["enum"]
        ):
            errors.append(f"{path}: value is not in enum")

        expected_type = schema.get("type")
        if expected_type and not self._has_type(instance, expected_type):
            errors.append(f"{path}: expected type {expected_type}")
            return errors
        if isinstance(instance, float) and not math.isfinite(instance):
            errors.append(f"{path}: non-finite numbers are not valid JSON values")
            return errors

        if isinstance(instance, dict):
            for key in schema.get("required", []):
                if key not in instance:
                    errors.append(f"{path}: missing required property {key}")

            properties = schema.get("properties", {})
            if schema.get("additionalProperties") is False:
                for key in instance.keys() - properties.keys():
                    errors.append(f"{path}: unknown property {key}")
            for key, child in properties.items():
                if key in instance:
                    errors.extend(self.errors(instance[key], child, f"{path}.{key}"))

        if isinstance(instance, list):
            if len(instance) < schema.get("minItems", 0):
                errors.append(f"{path}: too few items")
            if "maxItems" in schema and len(instance) > schema["maxItems"]:
                errors.append(f"{path}: too many items")
            if schema.get("uniqueItems"):
                canonical = [
                    json.dumps(item, sort_keys=True, separators=(",", ":"))
                    for item in instance
                ]
                if len(canonical) != len(set(canonical)):
                    errors.append(f"{path}: duplicate items")
            if "items" in schema:
                for index, item in enumerate(instance):
                    errors.extend(
                        self.errors(item, schema["items"], f"{path}[{index}]")
                    )

        if isinstance(instance, str):
            if len(instance) < schema.get("minLength", 0):
                errors.append(f"{path}: string is too short")
            if "maxLength" in schema and len(instance) > schema["maxLength"]:
                errors.append(f"{path}: string is too long")
            if "pattern" in schema and re.search(schema["pattern"], instance) is None:
                errors.append(f"{path}: string does not match pattern")
            if schema.get("format") == "date-time":
                try:
                    _parse_utc_timestamp(instance)
                except ValueError:
                    errors.append(f"{path}: expected a strict RFC 3339 UTC date-time")

        if isinstance(instance, (int, float)) and not isinstance(instance, bool):
            if "minimum" in schema and instance < schema["minimum"]:
                errors.append(f"{path}: number is below minimum")
            if "maximum" in schema and instance > schema["maximum"]:
                errors.append(f"{path}: number is above maximum")

        return errors

    @staticmethod
    def _has_type(instance, expected):
        checks = {
            "object": lambda value: isinstance(value, dict),
            "array": lambda value: isinstance(value, list),
            "string": lambda value: isinstance(value, str),
            "boolean": lambda value: isinstance(value, bool),
            "integer": lambda value: isinstance(value, int)
            and not isinstance(value, bool),
            "number": lambda value: isinstance(value, (int, float))
            and not isinstance(value, bool),
            "null": lambda value: value is None,
        }
        if isinstance(expected, list):
            return any(checks[item](instance) for item in expected)
        return checks[expected](instance)


def _duplicates(values):
    seen = set()
    duplicates = set()
    for value in values:
        if not isinstance(value, str):
            continue
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return sorted(duplicates)


def _closed_fields(value, expected, path, errors):
    if not isinstance(value, dict):
        errors.append(f"{path}: expected an object")
        return False
    if set(value) != expected:
        errors.append(f"{path}: fields are not closed and complete")
        return False
    return True


def _string_list(value, allowed, path, errors, allow_empty=False):
    if not isinstance(value, list):
        errors.append(f"{path}: expected an array")
        return []
    if not value and not allow_empty:
        errors.append(f"{path}: values must not be empty")
    if any(not isinstance(item, str) for item in value):
        errors.append(f"{path}: values must be strings")
        return []
    if len(value) != len(set(value)):
        errors.append(f"{path}: values must be unique")
    if not set(value).issubset(allowed):
        errors.append(f"{path}: value is not declared by contract")
    return value


def validate_gate_map(gate_map, runtime_schema):
    errors = []
    if not _closed_fields(gate_map, GATE_MAP_FIELDS, "gate map", errors):
        if not isinstance(gate_map, dict):
            return errors
    if not _is_canonical_gate_map(gate_map):
        errors.append("gate map declarations do not match the canonical ordered contract")
    identity = (
        gate_map.get("contract_id"),
        gate_map.get("contract_version"),
        gate_map.get("source_commit"),
    )
    if identity != GATE_MAP_IDENTITY:
        errors.append("gate map contract identity changed")
    if gate_map.get("unknown_gate_policy") != "REJECT":
        errors.append("gate map must reject unknown gates")
    if gate_map.get("result_match_policy") != "ANY_DECLARED_RULE_MATCHES_OR_REJECT":
        errors.append("gate map must reject results that match no declared rule")
    if gate_map.get("readiness_scope") != "QA_SUBGATE_ONLY":
        errors.append("gate map readiness scope must remain QA subgate only")
    parent_gate = gate_map.get("parent_release_gate")
    if _closed_fields(
        parent_gate, PARENT_RELEASE_GATE_FIELDS, "parent release gate", errors
    ) and not json_equal(parent_gate, PARENT_RELEASE_GATE):
        errors.append("parent release gate identity or approval requirement changed")
    if gate_map.get("release_ready_rule") != RELEASE_READY_RULE:
        errors.append("gate map release rule must compose QA and parent approval")

    schema_values = {
        "gate_id": set(runtime_schema["$defs"]["gate_id"]["enum"]),
        "checkpoint_ids": set(runtime_schema["$defs"]["checkpoint_id"]["enum"]),
        "game_versions": set(runtime_schema["properties"]["game_version"]["enum"]),
        "host_ids": set(
            runtime_schema["$defs"]["host_identity"]["properties"]["host_id"]["enum"]
        ),
        "qualities": set(runtime_schema["properties"]["quality"]["enum"]),
        "statuses": set(runtime_schema["$defs"]["result_status"]["enum"]),
        "evidence_classes": set(runtime_schema["$defs"]["evidence_class"]["enum"]),
    }
    gates = gate_map.get("gates", [])
    if not isinstance(gates, list):
        errors.append("gate map.gates: expected an array")
        return errors
    gate_ids = [gate.get("gate_id") for gate in gates if isinstance(gate, dict)]
    if any(not isinstance(gate_id, str) for gate_id in gate_ids):
        errors.append("gate map IDs must be strings")
    for duplicate in _duplicates(gate_ids):
        errors.append(f"duplicate gate_id: {duplicate}")
    if set(gate_id for gate_id in gate_ids if isinstance(gate_id, str)) != schema_values["gate_id"]:
        errors.append("gate map IDs must exactly match the runtime schema gate IDs")

    required_ids = set()
    for index, gate in enumerate(gates):
        gate_path = f"gates[{index}]"
        if not _closed_fields(gate, GATE_FIELDS, gate_path, errors):
            if not isinstance(gate, dict):
                continue
        gate_id = gate.get("gate_id", "<missing>")
        if gate.get("pass_rule") not in PASS_RULES:
            errors.append(f"{gate_id}: unknown pass_rule")
        rules = gate.get("result_rules", [])
        if not isinstance(rules, list):
            errors.append(f"{gate_id}.result_rules: expected an array")
            rules = []
        if not rules:
            errors.append(f"{gate_id}: result_rules must not be empty")
        rule_hosts = set()
        for index, rule in enumerate(rules):
            rule_path = f"{gate_id}.result_rules[{index}]"
            if not _closed_fields(rule, RULE_FIELDS, rule_path, errors):
                if not isinstance(rule, dict):
                    continue
            for field in RULE_FIELDS - {"private_capture_policy"}:
                values = _string_list(
                    rule.get(field), schema_values[field], f"{rule_path}.{field}", errors
                )
                if field == "host_ids":
                    rule_hosts.update(values)
            if rule.get("private_capture_policy") != PRIVATE_CAPTURE_POLICY:
                errors.append(f"{rule_path}: private capture policy is not fail closed")
            evidence = rule.get("evidence_classes")
            games = rule.get("game_versions")
            if isinstance(evidence, list) and all(
                isinstance(item, str) for item in evidence
            ) and isinstance(games, list) and all(
                isinstance(item, str) for item in games
            ):
                evidence_set = set(evidence)
                game_set = set(games)
                synthetic_evidence = {"SYNTHETIC_CONTRACT", "CONTROL"}
                real_evidence = {
                    "NATIVE_REDACTED_SUMMARY",
                    "PRIVATE_REDACTED_SUMMARY",
                }
                if evidence_set & synthetic_evidence and evidence_set & real_evidence:
                    errors.append(
                        f"{rule_path}: synthetic and real-game evidence must use separate rules"
                    )
                if evidence_set & synthetic_evidence and game_set != {"SYNTHETIC"}:
                    errors.append(
                        f"{rule_path}: synthetic evidence must bind only SYNTHETIC"
                    )
                if evidence_set & real_evidence and game_set != set(REAL_GAME_VERSIONS):
                    errors.append(
                        f"{rule_path}: native/private evidence must bind exactly RED, BLUE, and YELLOW"
                    )

        eligible_values = _string_list(
            gate.get("eligible_host_ids"),
            schema_values["host_ids"],
            f"{gate_id}.eligible_host_ids",
            errors,
            allow_empty=True,
        )
        eligible_hosts = set(eligible_values)
        if not eligible_hosts.issubset(rule_hosts):
            errors.append(f"{gate_id}: eligible hosts must occur in result rules")
        if gate.get("required") is True and isinstance(gate_id, str):
            required_ids.add(gate_id)
        invariant = REQUIRED_GATE_INVARIANTS.get(gate_id) if isinstance(gate_id, str) else None
        if invariant is not None:
            default_status, pass_rule, expected_hosts = invariant
            if gate.get("required") is not True:
                errors.append(f"{gate_id}: required invariant cannot be weakened")
            if gate.get("release_blocking") is not True:
                errors.append(f"{gate_id}: release-blocking invariant cannot be weakened")
            if gate.get("default_status") != default_status:
                errors.append(f"{gate_id}: default status invariant cannot be weakened")
            if gate.get("pass_rule") != pass_rule:
                errors.append(f"{gate_id}: pass rule invariant cannot be weakened")
            if eligible_values != expected_hosts:
                errors.append(f"{gate_id}: eligible host invariant cannot be weakened")
        if gate.get("pass_rule") == "ADVISORY_ONLY":
            if gate.get("required") or gate.get("release_blocking"):
                errors.append(f"{gate_id}: advisory gate cannot block release")
            if gate.get("default_status") != "ADVISORY":
                errors.append(f"{gate_id}: advisory gate must default advisory")
        if gate.get("default_status") == "INELIGIBLE":
            if eligible_hosts:
                errors.append(f"{gate_id}: ineligible gate cannot declare eligible hosts")
            if any("PASS" in rule.get("statuses", []) for rule in rules):
                errors.append(f"{gate_id}: ineligible gate cannot accept PASS")
        if gate.get("cleanup_required") is not True:
            errors.append(f"{gate_id}: cleanup evidence is required")

        if gate_id == "alpha.battle-art-1.9.8.v1":
            if len(rules) != 1 or not isinstance(rules[0], dict):
                errors.append(f"{gate_id}: exactly one result rule is required")
            else:
                battle_rule = rules[0]
                if battle_rule.get("checkpoint_ids") != MATRIX_SCENE_IDS:
                    errors.append(
                        f"{gate_id}: checkpoint set must exactly match the released Battle Art gate"
                    )
                if battle_rule.get("game_versions") != REAL_GAME_VERSIONS:
                    errors.append(
                        f"{gate_id}: game-version set must be exactly RED, BLUE, and YELLOW"
                    )
                if battle_rule.get("host_ids") != ["BATTLE_ART_VOXEL_FORK"]:
                    errors.append(f"{gate_id}: host identity must be exact")
                if battle_rule.get("qualities") != ["LOW", "BALANCED", "HIGH"]:
                    errors.append(f"{gate_id}: quality set must be exact")
                if battle_rule.get("statuses") != [
                    "PASS",
                    "FAIL",
                    "BLOCKED",
                    "NOT_RUN",
                ]:
                    errors.append(f"{gate_id}: status set must be exact")
                if battle_rule.get("evidence_classes") != [
                    "NATIVE_REDACTED_SUMMARY",
                    "PRIVATE_REDACTED_SUMMARY",
                ]:
                    errors.append(f"{gate_id}: evidence set must be exact")

    if required_ids != set(REQUIRED_GATE_INVARIANTS):
        errors.append("gate map required gate set does not match immutable invariants")
    advisory_id, advisory_status, advisory_rule, advisory_hosts = ADVISORY_GATE_INVARIANT
    advisory = next(
        (gate for gate in gates if isinstance(gate, dict) and gate.get("gate_id") == advisory_id),
        None,
    )
    if advisory is not None and (
        advisory.get("required") is not False
        or advisory.get("release_blocking") is not False
        or advisory.get("default_status") != advisory_status
        or advisory.get("pass_rule") != advisory_rule
        or advisory.get("eligible_host_ids") != advisory_hosts
    ):
        errors.append(f"{advisory_id}: advisory invariant changed")
    return errors


def validate_parent_release_ledger(parent_ledger, gate_map):
    errors = []
    if not isinstance(parent_ledger, dict):
        return ["parent prerelease ledger: expected an object"]
    parent_gate = gate_map.get("parent_release_gate") if isinstance(gate_map, dict) else None
    if not _is_canonical_gate_map(gate_map) or not json_equal(
        parent_gate, PARENT_RELEASE_GATE
    ):
        errors.append("parent prerelease ledger mapping is not canonical")
        return errors
    for field in ("schema", "release_version", "tag"):
        if not json_equal(parent_ledger.get(field), parent_gate[field]):
            errors.append(f"parent prerelease ledger {field} identity changed")
    approval_field = parent_gate["approval_field"]
    if type(parent_ledger.get(approval_field)) is not bool:
        errors.append("parent prerelease ledger approval field must be boolean")
    return errors


KNOWN_GATE_STATUSES = {
    "PASS",
    "FAIL",
    "BLOCKED",
    "NOT_RUN",
    "INELIGIBLE",
    "ADVISORY",
}


def evaluate_release_readiness(gate_map, parent_ledger, gate_statuses):
    """Evaluate composition only; this function never asserts current approval."""
    if not isinstance(gate_map, dict) or not isinstance(parent_ledger, dict):
        raise QaContractLogicError("validated gate map and parent ledger are required")
    if not _is_canonical_gate_map(gate_map):
        raise QaContractLogicError("gate declarations are not canonical")
    if validate_parent_release_ledger(parent_ledger, gate_map):
        raise QaContractLogicError("parent prerelease ledger identity is not canonical")
    approval = parent_ledger.get(PARENT_RELEASE_GATE["approval_field"])
    if type(approval) is not bool:
        raise QaContractLogicError("parent approval is not boolean")
    gates = gate_map.get("gates")
    declared_ids = [gate.get("gate_id") for gate in gates]
    if not isinstance(gate_statuses, dict):
        raise QaContractLogicError("gate statuses must be an exact mapping")
    unknown_gates = set(gate_statuses) - set(declared_ids)
    if unknown_gates:
        raise QaContractLogicError("gate status mapping contains an unknown gate")
    if set(gate_statuses) != set(declared_ids):
        raise QaContractLogicError("gate status mapping is incomplete")
    for gate in gates:
        status = gate_statuses[gate["gate_id"]]
        if not isinstance(status, str) or status not in KNOWN_GATE_STATUSES:
            raise QaContractLogicError("gate status mapping contains an unknown status")
        legal_statuses = {gate["default_status"]}
        for rule in gate["result_rules"]:
            legal_statuses.update(rule["statuses"])
        if status not in legal_statuses:
            raise QaContractLogicError("gate status is illegal for its declaration")
    required_ids = [gate["gate_id"] for gate in gates if gate.get("required") is True]
    qa_ready = all(gate_statuses[gate_id] == "PASS" for gate_id in required_ids)
    return approval is True and qa_ready


def validate_runtime_result(instance, runtime_schema, gate_map):
    errors = Draft202012ContractValidator(runtime_schema).errors(instance)
    errors.extend(validate_gate_map(gate_map, runtime_schema))
    gate_id = instance.get("gate_id") if isinstance(instance, dict) else None
    gate = next(
        (
            item
            for item in gate_map.get("gates", [])
            if isinstance(item, dict) and item.get("gate_id") == gate_id
        ),
        None,
    )
    if gate is None:
        errors.append(f"$.gate_id: unknown gate {gate_id!r}")
        return errors

    host = instance.get("host", {})
    result_values = {
        "checkpoint_ids": instance.get("checkpoint_id"),
        "game_versions": instance.get("game_version"),
        "host_ids": host.get("host_id") if isinstance(host, dict) else None,
        "qualities": instance.get("quality"),
        "statuses": instance.get("status"),
        "evidence_classes": instance.get("evidence_class"),
    }
    matched = False
    for rule in gate.get("result_rules", []):
        if not isinstance(rule, dict):
            continue
        rule_matches = True
        for field, value in result_values.items():
            allowed = rule.get(field)
            if not isinstance(value, str) or not isinstance(allowed, list):
                rule_matches = False
                break
            if any(not isinstance(item, str) for item in allowed) or value not in allowed:
                rule_matches = False
                break
        if rule_matches:
            matched = True
            break
    if not matched:
        errors.append(
            "$: gate/checkpoint/host/quality/status/evidence combination is not declared"
        )
    if instance.get("status") == "PASS" and result_values["host_ids"] not in gate.get(
        "eligible_host_ids", []
    ):
        errors.append("$.status: PASS requires a gate-eligible host")

    private_hash = instance.get("private_capture_sha256")
    if instance.get("evidence_class") == "PRIVATE_REDACTED_SUMMARY":
        if private_hash is None:
            errors.append(
                "$.private_capture_sha256: private evidence requires a SHA-256 binding"
            )
    elif private_hash is not None:
        errors.append(
            "$.private_capture_sha256: public evidence must not carry a private binding"
        )
    return errors


def validate_defect_ledger(instance, defect_schema):
    errors = Draft202012ContractValidator(defect_schema).errors(instance)
    defects = instance.get("defects", []) if isinstance(instance, dict) else []
    if not isinstance(defects, list):
        return errors
    defect_ids = [item.get("defect_id") for item in defects if isinstance(item, dict)]
    for duplicate in _duplicates(defect_ids):
        errors.append(f"$.defects: duplicate defect_id {duplicate}")

    transition_ids = []
    for defect_index, defect in enumerate(defects):
        if not isinstance(defect, dict):
            continue
        path = f"$.defects[{defect_index}]"
        transitions = defect.get("transitions", [])
        if not isinstance(transitions, list):
            continue
        previous_recorded_at = None
        for transition_index, transition in enumerate(transitions):
            if isinstance(transition, dict):
                transition_ids.append(transition.get("transition_id"))
                try:
                    recorded_at = _parse_utc_timestamp(transition.get("recorded_at"))
                except (TypeError, ValueError):
                    errors.append(
                        f"{path}.transitions[{transition_index}].recorded_at: "
                        "must be a valid UTC timestamp"
                    )
                    recorded_at = None
                if (
                    recorded_at is not None
                    and previous_recorded_at is not None
                    and recorded_at <= previous_recorded_at
                ):
                    errors.append(
                        f"{path}.transitions[{transition_index}].recorded_at: "
                        "transition timestamps must be strictly increasing"
                    )
                if recorded_at is not None:
                    previous_recorded_at = recorded_at
        if not transitions:
            continue
        first = transitions[0]
        if isinstance(first, dict) and first.get("from_status") is not None:
            errors.append(f"{path}.transitions[0].from_status: first transition must start null")
        for index in range(1, len(transitions)):
            previous = transitions[index - 1]
            current = transitions[index]
            if not isinstance(previous, dict) or not isinstance(current, dict):
                continue
            if current.get("from_status") != previous.get("to_status"):
                errors.append(
                    f"{path}.transitions[{index}].from_status: transition chain is not continuous"
                )
            if previous.get("to_status") == "CLOSED" and (
                current.get("from_status"), current.get("to_status")
            ) != ("CLOSED", "REOPENED"):
                errors.append(
                    f"{path}.transitions[{index}]: CLOSED may only transition to REOPENED"
                )
        final = transitions[-1]
        if isinstance(final, dict) and defect.get("current_status") != final.get(
            "to_status"
        ):
            errors.append(f"{path}.current_status: must equal final transition to_status")

    for duplicate in _duplicates(transition_ids):
        errors.append(f"$.defects: duplicate transition_id {duplicate}")
    return errors


def _list_tuple(value):
    return tuple(value) if isinstance(value, list) else value


def _dict_items_tuple(value):
    return tuple(value.items()) if isinstance(value, dict) else value


def _quality_tier_semantics(item):
    if not isinstance(item, dict):
        return None
    return (
        item.get("quality"),
        item.get("build_budget_ms"),
        item.get("cache_bytes"),
        item.get("density"),
        item.get("draw_call_target"),
        item.get("panorama_width"),
    )


def _host_semantics(item):
    if not isinstance(item, dict):
        return None
    return (
        item.get("host_id"),
        item.get("release"),
        item.get("commit"),
        item.get("package_sha256"),
        item.get("released"),
        item.get("eligibility"),
        item.get("role"),
    )


def _scene_semantics(scene):
    if not isinstance(scene, dict):
        return None
    return (
        scene.get("scene_class_id"),
        scene.get("authored_case_id"),
        scene.get("scene_class"),
        _list_tuple(scene.get("game")),
        scene.get("map_class"),
        scene.get("weather"),
        scene.get("time"),
        scene.get("interior"),
        scene.get("battle"),
        scene.get("host"),
        scene.get("camera_checkpoint"),
        scene.get("expected_owner"),
        _list_tuple(scene.get("required_evidence")),
        _dict_items_tuple(scene.get("quality_case_ids")),
        _list_tuple(scene.get("coverage")),
        _list_tuple(scene.get("qualities")),
        scene.get("release_blocking"),
    )


def _advisory_semantics(scene):
    if not isinstance(scene, dict):
        return None
    return (
        scene.get("checkpoint_id"),
        scene.get("scene_class"),
        scene.get("fixture_kind"),
        _list_tuple(scene.get("game")),
        scene.get("map_class"),
        scene.get("weather"),
        scene.get("time"),
        scene.get("interior"),
        scene.get("battle"),
        scene.get("host"),
        scene.get("camera_checkpoint"),
        scene.get("expected_owner"),
        _list_tuple(scene.get("required_evidence")),
        _dict_items_tuple(scene.get("quality_case_ids")),
        _list_tuple(scene.get("qualities")),
        scene.get("release_blocking"),
        scene.get("claim"),
    )


def validate_matrix(matrix, route):
    errors = []
    if not isinstance(matrix, dict):
        return ["visual matrix: expected an object"]
    if not isinstance(route, dict):
        return ["smoke route: expected an object"]
    _closed_fields(matrix, MATRIX_FIELDS, "visual matrix", errors)
    _closed_fields(route, ROUTE_FIELDS, "smoke route", errors)
    matrix_identity = (
        matrix.get("contract_id"),
        matrix.get("contract_version"),
        matrix.get("source_commit"),
        matrix.get("fixture_kind"),
    )
    if matrix_identity != MATRIX_IDENTITY:
        errors.append("visual matrix contract identity changed")
    route_identity = (
        route.get("contract_id"),
        route.get("contract_version"),
        route.get("source_commit"),
    )
    if route_identity != ROUTE_IDENTITY:
        errors.append("smoke route contract identity changed")
    if route.get("coordinate_policy") != "DESCRIPTIVE_SCENE_CLASSES_ONLY":
        errors.append("smoke route coordinate policy changed")
    if not json_equal(_list_tuple(matrix.get("matrix_dimensions")), FROZEN_MATRIX_DIMENSIONS):
        errors.append("visual matrix dimensions are incomplete or out of order")

    quality_tiers = matrix.get("quality_tiers", [])
    quality_names = [
        item.get("quality")
        for item in quality_tiers
        if isinstance(item, dict)
    ] if isinstance(quality_tiers, list) else []
    if quality_names != ["LOW", "BALANCED", "HIGH"]:
        errors.append("visual matrix quality tiers are incomplete or out of order")
    if isinstance(quality_tiers, list):
        for index, item in enumerate(quality_tiers):
            _closed_fields(
                item, QUALITY_TIER_FIELDS, f"quality_tiers[{index}]", errors
            )
            if isinstance(item, dict):
                for field in ("build_budget_ms", "density"):
                    value = item.get(field)
                    if type(value) not in (int, float) or not math.isfinite(value):
                        errors.append(
                            f"quality_tiers[{index}].{field}: expected a finite number"
                        )
                for field in ("cache_bytes", "draw_call_target", "panorama_width"):
                    if type(item.get(field)) is not int:
                        errors.append(
                            f"quality_tiers[{index}].{field}: expected an integer"
                        )
        if not json_equal(
            tuple(_quality_tier_semantics(item) for item in quality_tiers),
            FROZEN_QUALITY_TIERS,
        ):
            errors.append("visual matrix quality tier values changed")

    host_matrix = matrix.get("host_matrix", [])
    host_ids = [
        item.get("host_id")
        for item in host_matrix
        if isinstance(item, dict)
    ] if isinstance(host_matrix, list) else []
    if host_ids != ["NO_HOST", "BATTLE_ART_VOXEL_FORK", "DRAMALESS_SHAPE"]:
        errors.append("visual matrix host identities are incomplete or out of order")
    if isinstance(host_matrix, list):
        for index, item in enumerate(host_matrix):
            _closed_fields(item, HOST_MATRIX_FIELDS, f"host_matrix[{index}]", errors)
            if isinstance(item, dict) and type(item.get("released")) is not bool:
                errors.append(f"host_matrix[{index}].released: expected a boolean")
    if isinstance(host_matrix, list) and not json_equal(
        tuple(_host_semantics(item) for item in host_matrix), FROZEN_HOST_MATRIX
    ):
        errors.append("visual matrix host facts do not match frozen identities")

    scene_classes = matrix.get("scene_classes", [])
    if not isinstance(scene_classes, list):
        errors.append("visual matrix scene_classes must be an array")
        scene_classes = []
    advisory = matrix.get("advisory_stress", {})
    if not isinstance(advisory, dict):
        errors.append("visual matrix advisory_stress must be an object")
        advisory = {}

    matrix_ids = [
        item.get("scene_class_id")
        for item in scene_classes
        if isinstance(item, dict)
    ]
    if matrix_ids != MATRIX_SCENE_IDS:
        errors.append("visual matrix scene IDs are incomplete or out of order")
    if not json_equal(
        tuple(_scene_semantics(scene) for scene in scene_classes),
        FROZEN_SCENE_SEMANTICS,
    ):
        errors.append("visual matrix authored scene semantics changed")
    if not json_equal(_advisory_semantics(advisory), FROZEN_ADVISORY_SEMANTICS):
        errors.append("visual matrix advisory semantics changed")

    quality_ids = []
    for scene_index, scene in enumerate([*scene_classes, advisory]):
        if not isinstance(scene, dict):
            errors.append(f"visual matrix row {scene_index}: expected an object")
            continue
        scene_name = scene.get("scene_class", "<unknown>")
        expected_fields = (
            SCENE_FIELDS if scene_index < len(scene_classes) else ADVISORY_FIELDS
        )
        _closed_fields(scene, expected_fields, f"visual matrix row {scene_index}", errors)
        for dimension in MATRIX_DIMENSIONS:
            if dimension not in scene:
                errors.append(f"{scene_name}: missing {dimension}")
                continue
            value = scene[dimension]
            if value == "" or value == [] or value == {} or value is None:
                errors.append(f"{scene_name}.{dimension}: value must not be empty")

        for field, allowed in MATRIX_ALLOWED_VALUES.items():
            value = scene.get(field)
            values = value if isinstance(value, list) else [value]
            if not values or any(
                not isinstance(item, str) or item not in allowed for item in values
            ):
                errors.append(f"{scene_name}.{field}: value is not allowed")
            if (
                isinstance(value, list)
                and all(isinstance(item, str) for item in value)
                and len(value) != len(set(value))
            ):
                errors.append(f"{scene_name}.{field}: values must be unique")
        if type(scene.get("interior")) is not bool:
            errors.append(f"{scene_name}.interior: value must be boolean")
        if type(scene.get("release_blocking")) is not bool:
            errors.append(f"{scene_name}.release_blocking: value must be boolean")

        expected_host = "BATTLE_ART_VOXEL_FORK" if scene_index < len(scene_classes) else "NO_HOST"
        if scene.get("host") != expected_host:
            errors.append(f"{scene_name}.host: host does not match checkpoint class")
        expected_games = ["RED", "BLUE", "YELLOW"] if scene_index < len(scene_classes) else ["SYNTHETIC"]
        if scene.get("game") != expected_games:
            errors.append(f"{scene_name}.game: game coverage does not match checkpoint class")
        expected_evidence = (
            [
                "SYNTHETIC_CONTRACT",
                "NATIVE_REDACTED_SUMMARY",
                "PRIVATE_REDACTED_SUMMARY",
            ]
            if scene_index < len(scene_classes)
            else ["SYNTHETIC_CONTRACT"]
        )
        if scene.get("required_evidence") != expected_evidence:
            errors.append(f"{scene_name}.required_evidence: evidence coverage is incomplete")
        if scene.get("qualities") != ["LOW", "BALANCED", "HIGH"]:
            errors.append(f"{scene_name}.qualities: quality coverage is incomplete")

        cases = scene.get("quality_case_ids", {})
        if not isinstance(cases, dict):
            errors.append(f"{scene_name}: quality case IDs must be an object")
            cases = {}
        else:
            _closed_fields(
                cases,
                QUALITY_CASE_FIELDS,
                f"{scene_name}.quality_case_ids",
                errors,
            )
        if list(cases) != ["LOW", "BALANCED", "HIGH"]:
            errors.append(f"{scene_name}: quality case IDs incomplete")
        case_base = scene.get("authored_case_id")
        if case_base is None:
            checkpoint = scene.get("checkpoint_id", "")
            if isinstance(checkpoint, str):
                case_base = re.sub(r"^advisory\.|\.v1$", "", checkpoint).replace("-", "_")
            else:
                case_base = "<invalid>"
        if not isinstance(case_base, str) or re.fullmatch(r"[a-z0-9]+(?:_[a-z0-9]+)*", case_base) is None:
            errors.append(f"{scene_name}: authored case ID is malformed")
            case_base = "<invalid>"
        expected_cases = {
            quality: f"{case_base}.{quality.lower()}.v1"
            for quality in ("LOW", "BALANCED", "HIGH")
        }
        if cases != expected_cases:
            errors.append(
                f"{scene_name}: quality case IDs are not deterministic"
            )
        quality_ids.extend(value for value in cases.values() if isinstance(value, str))
    for duplicate in _duplicates(quality_ids):
        errors.append(f"duplicate quality case ID: {duplicate}")

    checkpoints = route.get("checkpoints", [])
    if not isinstance(checkpoints, list):
        errors.append("smoke route checkpoints must be an array")
        checkpoints = []
    route_ids = [
        item.get("checkpoint_id")
        for item in checkpoints
        if isinstance(item, dict)
    ]
    expected_route = [
        "control.no-host-fail-closed.v1",
        *MATRIX_SCENE_IDS,
        "advisory.dense-outdoor-64x64.v1",
    ]
    if route_ids != expected_route:
        errors.append("smoke route does not match the visual matrix checkpoint order")

    rows_by_id = {
        row.get("scene_class_id"): row
        for row in scene_classes
        if isinstance(row, dict) and isinstance(row.get("scene_class_id"), str)
    }
    if isinstance(advisory.get("checkpoint_id"), str):
        rows_by_id[advisory["checkpoint_id"]] = advisory
    for checkpoint_index, checkpoint in enumerate(checkpoints):
        if not isinstance(checkpoint, dict):
            errors.append("smoke route checkpoint must be an object")
            continue
        _closed_fields(
            checkpoint,
            ROUTE_CHECKPOINT_FIELDS,
            f"smoke route checkpoints[{checkpoint_index}]",
            errors,
        )
        checkpoint_id = checkpoint.get("checkpoint_id")
        if not isinstance(checkpoint_id, str):
            errors.append(
                f"smoke route checkpoints[{checkpoint_index}].checkpoint_id: expected a string"
            )
            continue
        if type(checkpoint.get("order")) is not int or not json_equal(
            checkpoint.get("order"), checkpoint_index + 1
        ):
            errors.append(f"{checkpoint_id}: route order cross-link is broken")
        if checkpoint_id == "control.no-host-fail-closed.v1":
            if checkpoint.get("scene_class") != "No compatible host fail-closed control":
                errors.append(f"{checkpoint_id}: scene class cross-link is broken")
            if checkpoint.get("fixture_class") != "control":
                errors.append(f"{checkpoint_id}: fixture cross-link is broken")
            if checkpoint.get("qualities") != ["LOW", "BALANCED", "HIGH"]:
                errors.append(f"{checkpoint_id}: quality cross-link is broken")
            if checkpoint.get("host_scope") != ["NO_HOST"]:
                errors.append(f"{checkpoint_id}: host cross-link is broken")
            if checkpoint.get("release_role") != "REQUIRED":
                errors.append(f"{checkpoint_id}: release-role cross-link is broken")
            continue
        row = rows_by_id.get(checkpoint_id)
        if row is None:
            errors.append(f"smoke route checkpoint {checkpoint_id!r} has no matrix row")
            continue
        if checkpoint.get("scene_class") != row.get("scene_class"):
            errors.append(f"{checkpoint_id}: scene class cross-link is broken")
        if checkpoint.get("qualities") != row.get("qualities"):
            errors.append(f"{checkpoint_id}: quality cross-link is broken")
        expected_scope = (
            ["NO_HOST"]
            if checkpoint_id == "advisory.dense-outdoor-64x64.v1"
            else ["BATTLE_ART_VOXEL_FORK", "DRAMALESS_SHAPE"]
        )
        if checkpoint.get("host_scope") != expected_scope:
            errors.append(f"{checkpoint_id}: host cross-link is broken")
        expected_fixture = row.get("fixture_kind", matrix.get("fixture_kind"))
        if checkpoint.get("fixture_class") != expected_fixture:
            errors.append(f"{checkpoint_id}: fixture cross-link is broken")
        expected_role = "REQUIRED" if row.get("release_blocking") is True else "ADVISORY"
        if checkpoint.get("release_role") != expected_role:
            errors.append(f"{checkpoint_id}: release-role cross-link is broken")
    return errors


def meta_validate_schemas(schemas):
    try:
        import jsonschema
    except ImportError:
        return None, []
    errors = []
    for name, schema in schemas.items():
        try:
            validator = jsonschema.validators.validator_for(schema)
            validator.check_schema(schema)
        except Exception as error:  # jsonschema reports several schema error types.
            errors.append(f"{name}: {error}")
    return importlib.metadata.version("jsonschema"), errors


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate KFP QA contracts and records")
    parser.add_argument("--runtime-result", type=pathlib.Path)
    parser.add_argument("--defect-ledger", type=pathlib.Path)
    args = parser.parse_args(argv)

    try:
        runtime_schema = load_json(
            QA / "runtime-result.schema.json", "runtime result schema"
        )
        defect_schema = load_json(
            QA / "defect-ledger.schema.json", "defect ledger schema"
        )
        gate_map = load_json(QA / "release-gate-map-v1.json", "release gate map")
        matrix = load_json(
            QA / "visual-scene-matrix-v1.json", "visual scene matrix"
        )
        route = load_json(QA / "smoke-route-v1.json", "smoke route")
        parent_ledger = load_json(
            ROOT / "docs" / "prerelease-gates.json", "parent prerelease ledger"
        )
        runtime_result = (
            load_json(args.runtime_result, "runtime result")
            if args.runtime_result
            else None
        )
        defect_ledger = (
            load_json(args.defect_ledger, "defect ledger")
            if args.defect_ledger
            else None
        )
    except QaContractLoadError as error:
        print(f"qa-contract: {error}", file=sys.stderr)
        return 1

    errors = validate_gate_map(gate_map, runtime_schema)
    errors.extend(validate_parent_release_ledger(parent_ledger, gate_map))
    errors.extend(validate_matrix(matrix, route))
    dependency_version, meta_errors = meta_validate_schemas(
        {"runtime-result.schema.json": runtime_schema, "defect-ledger.schema.json": defect_schema}
    )
    errors.extend(meta_errors)
    if args.runtime_result:
        errors.extend(validate_runtime_result(runtime_result, runtime_schema, gate_map))
    if args.defect_ledger:
        errors.extend(validate_defect_ledger(defect_ledger, defect_schema))

    if errors:
        for error in errors:
            print(f"qa-contract: {error}", file=sys.stderr)
        return 1
    meta = dependency_version or "unavailable"
    print(f"qa-contract: validation passed (Draft 2020-12 meta-validator: {meta})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
