import copy
from contextlib import redirect_stderr
import importlib.util
from io import StringIO
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
GENERATOR_PATH = ROOT / "tools" / "generate_alpha_quality_status.py"
FIXTURES = ROOT / "tests" / "fixtures" / "alpha_quality"
OUTPUT = ROOT / "website" / "public" / "alpha-quality-status.json"

SPEC = importlib.util.spec_from_file_location("alpha_quality_status", GENERATOR_PATH)
GENERATOR = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(GENERATOR)


class AlphaQualityStatusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures = GENERATOR.load_fixtures(FIXTURES)

    def fixture(self):
        return copy.deepcopy(self.fixtures[0])

    def assert_invalid(self, fixture):
        with self.assertRaises(GENERATOR.ValidationError):
            GENERATOR.validate_fixture(fixture)

    def catalog_fixtures(self):
        return copy.deepcopy(self.fixtures)

    def gate_status(self, status, gate_id):
        return next(gate["status"] for gate in status["gates"] if gate["gate_id"] == gate_id)

    def test_checked_in_status_is_canonical_public_data(self):
        first = GENERATOR.generate(FIXTURES)
        second = GENERATOR.generate(FIXTURES)
        self.assertEqual(first, second)
        self.assertEqual(first, OUTPUT.read_bytes())
        self.assertTrue(first.endswith(b"\n"))
        self.assertNotIn(b"\r", first)

        status = json.loads(first)
        self.assertEqual(status["readiness_status"], "NOT READY")
        self.assertEqual(status["release_status"], "NOT RELEASED")
        self.assertEqual(status["qualities"], ["Low", "Balanced", "High"])
        self.assertEqual(status["summary"]["required_gates_passed"], 3)
        self.assertEqual(status["summary"]["required_gates"], 4)
        self.assertEqual(
            {GENERATOR.cohort_key(fixture) for fixture in self.fixtures},
            {
                (
                    "alpha-quality-synthetic-v1",
                    "e540c3b3de25caa5fa855dd6c3c702449ed9e72c",
                    "cdc415907e244cbce7ff9e46f1dffdbdee07d713",
                    "f31044dfcc4dcdd3a68536424293058aec70b0390f99ed243e1af18189b5e620",
                    "gen1recomp",
                    "Gen1Recomp",
                    "0.2.19",
                )
            },
        )
        self.assertEqual(
            [gate["status"] for gate in status["gates"]],
            ["PASS", "PASS", "PASS", "BLOCKED"],
        )
        self.assertEqual(
            {host["id"]: host["eligibility"] for host in status["hosts"]},
            {
                "battle-art": "ELIGIBLE",
                "dramaless": "INELIGIBLE",
                "kfp-no-host": "CONTROL",
            },
        )
        self.assertTrue(
            all(
                item["reference"].startswith("public-evidence://")
                for item in status["evidence_references"]
            )
        )

    def test_cli_check_mode_accepts_only_current_bytes(self):
        completed = subprocess.run(
            [sys.executable, str(GENERATOR_PATH), "--check"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

        missing = ROOT / "tests" / "fixtures" / "alpha_quality" / "missing-status.json"
        self.assertFalse(missing.exists())
        rejected = subprocess.run(
            [
                sys.executable,
                str(GENERATOR_PATH),
                "--output",
                str(missing),
                "--check",
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(rejected.returncode, 0)

        stale = mock.Mock()
        stale.is_file.return_value = True
        stale.read_bytes.return_value = b"{}\n"
        arguments = SimpleNamespace(fixtures=FIXTURES, output=stale, check=True)
        stderr = StringIO()
        with mock.patch.object(GENERATOR, "parse_args", return_value=arguments), redirect_stderr(
            stderr
        ):
            self.assertEqual(GENERATOR.main([]), 1)
        self.assertIn("missing or stale", stderr.getvalue())
        stale.read_bytes.assert_called_once_with()
        self.assertFalse(stale.write_bytes.called)

    def test_rejects_unknown_and_forbidden_fields(self):
        for field in (
            "unknown_field",
            "rom_path",
            "save_path",
            "cache_path",
            "raw_image",
            "raw_video",
            "raw_log",
            "secret_token",
        ):
            with self.subTest(field=field):
                fixture = self.fixture()
                fixture[field] = "not-public"
                self.assert_invalid(fixture)

    def test_rejects_absolute_private_and_raw_media_references(self):
        references = (
            "C:\\Users\\person\\evidence.json",
            "C:private\\evidence.json",
            "\\Users\\person\\evidence.json",
            "/home/person/evidence.json",
            "public-evidence://synthetic/../private/result.json",
            "public-evidence://synthetic/./alpha/result.json",
            "public-evidence://synthetic//alpha/result.json",
            "public-evidence://synthetic/.hidden/result.json",
            "public-evidence://synthetic/_hidden/result.json",
            "public-evidence://synthetic/-hidden/result.json",
            "private-evidence://alpha/result.json",
            "public-evidence://synthetic/alpha/frame.png",
            "public-evidence://synthetic/alpha/runtime.log",
            "public-evidence://synthetic/alpha/mix.aif",
            "public-evidence://synthetic/alpha/mix.aiff",
            "public-evidence://synthetic/alpha/mix.ac3",
            "public-evidence://synthetic/alpha/mix.amr",
            "public-evidence://synthetic/alpha/mix.ape",
            "public-evidence://synthetic/alpha/mix.mka",
            "public-evidence://synthetic/alpha/mix.mp3",
            "public-evidence://synthetic/alpha/mix.ra",
            "public-evidence://synthetic/alpha/mix.snd",
            "public-evidence://synthetic/alpha/mix.wav",
            "public-evidence://synthetic/alpha/mix.weba",
            "public-evidence://synthetic/alpha/mix.wma",
            "public-evidence://synthetic/alpha/mix.mp3/assertion",
            "public-evidence://synthetic/alpha/frame.png/assertion",
            "public-evidence://synthetic/alpha/runtime.log/assertion",
        )
        for reference in references:
            with self.subTest(reference=reference):
                fixture = self.fixture()
                fixture["evidence"][0]["reference"] = reference
                self.assert_invalid(fixture)

    def test_rejects_embedded_private_paths_and_file_uris(self):
        unsafe_strings = (
            "public prefix C:\\Users\\person\\evidence.json suffix",
            "public prefix /home/person/evidence.json suffix",
            "public prefix /workspace/evidence.json suffix",
            "public prefix /usr/local/bin/tool suffix",
            "public prefix //server/share/evidence.json suffix",
            "public prefix \\\\server\\share\\evidence.json suffix",
            "public prefix file:///home/person/evidence.json suffix",
            "public prefix FILE://C:/Users/person/evidence.json suffix",
            "public prefix ../evidence suffix",
            "public prefix ./evidence suffix",
            "public prefix ..\\evidence suffix",
            "public prefix .\\evidence suffix",
            "public prefix %2e%2e%2fevidence suffix",
            "public prefix %252e%252e%252fprivate suffix",
            "public prefix %25252e%25252e%25252fprivate suffix",
        )
        for value in unsafe_strings:
            with self.subTest(value=value):
                fixture = self.fixture()
                fixture["engine"]["label"] = value
                self.assert_invalid(fixture)

    def test_accepts_safe_colon_percentage_and_public_reference_prose(self):
        fixture = self.fixture()
        fixture["summary"] = "Phase A: public evidence is 25% complete"
        fixture["engine"]["label"] = "Input/output public check with %20 marker"
        fixture["evidence"][0]["reference"] = (
            "public-evidence://synthetic/alpha/safe-assertion"
        )
        GENERATOR.validate_fixture(fixture)

    def test_rejects_secrets_in_public_text(self):
        possible_secrets = (
            "public prefix " + "ghp_" + ("A" * 24) + " suffix",
            "public prefix Bearer " + ("a" * 24) + " suffix",
            "public prefix Bearer\t" + ("c" * 24) + " suffix",
            "public prefix Bearer:" + ("b" * 24) + " suffix",
            "public prefix Bearer=" + ("d" * 24) + " suffix",
            "public prefix " + "xoxb-" + ("1" * 12) + "-" + ("A" * 24) + " suffix",
            "public prefix -----BEGIN " + "RSA PRIVATE KEY----- suffix",
            "public prefix " + "glpat-" + ("A" * 24) + " suffix",
            "public prefix " + "AIza" + ("A" * 35) + " suffix",
            "public prefix " + "npm_" + ("A" * 36) + " suffix",
            "public prefix " + "sk_live_" + ("A" * 24) + " suffix",
            "public prefix " + "eyJ" + ("A" * 12) + "." + ("B" * 12) + "." + ("C" * 12),
        )
        for value in possible_secrets:
            with self.subTest(value=value):
                fixture = self.fixture()
                fixture["host"]["label"] = value
                self.assert_invalid(fixture)

    def test_accepts_benign_and_non_credential_bearer_text(self):
        safe_values = (
            "Bearer authentication is supported",
            "Bearer:",
            "Bearer short",
        )
        for value in safe_values:
            with self.subTest(value=value):
                fixture = self.fixture()
                fixture["host"]["label"] = value
                GENERATOR.validate_fixture(fixture)

    def test_rejects_mixed_readiness_cohorts(self):
        mutations = (
            lambda fixture: fixture["source"].__setitem__("commit_sha", "0" * 40),
            lambda fixture: fixture["source"].__setitem__("tree_sha", "0" * 40),
            lambda fixture: fixture["package"].__setitem__("sha256", "0" * 64),
            lambda fixture: fixture["engine"].__setitem__("id", "different-engine"),
            lambda fixture: fixture["engine"].__setitem__("label", "Different Engine"),
            lambda fixture: fixture["engine"].__setitem__("version", "0.2.20"),
            lambda fixture: fixture.__setitem__("suite_id", "different-suite"),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                fixtures = self.catalog_fixtures()
                mutate(fixtures[-1])
                with self.assertRaisesRegex(
                    GENERATOR.ValidationError,
                    "approved source/package/engine cohort",
                ):
                    GENERATOR.build_status(fixtures)

    def test_rejects_same_commit_with_different_source_tree(self):
        fixtures = self.catalog_fixtures()
        fixtures[-1]["source"]["tree_sha"] = "0" * 40
        self.assertEqual(
            len({fixture["source"]["commit_sha"] for fixture in fixtures}),
            1,
        )
        self.assertEqual(
            len({fixture["source"]["tree_sha"] for fixture in fixtures}),
            2,
        )
        with self.assertRaisesRegex(
            GENERATOR.ValidationError,
            "approved source/package/engine cohort",
        ):
            GENERATOR.build_status(fixtures)

    def test_rejects_a_complete_alternate_cohort(self):
        fixtures = self.catalog_fixtures()
        for fixture in fixtures:
            fixture["suite_id"] = "alternate-suite"
            fixture["source"]["commit_sha"] = "0" * 40
            fixture["source"]["tree_sha"] = "1" * 40
            fixture["package"]["sha256"] = "2" * 64
            fixture["engine"] = {
                "id": "alternate-engine",
                "label": "Alternate Engine",
                "version": "9.9.9",
            }
        with self.assertRaisesRegex(
            GENERATOR.ValidationError,
            "approved source/package/engine cohort",
        ):
            GENERATOR.build_status(fixtures)

    def test_result_catalog_blocks_missing_or_rewritten_release_blocker(self):
        missing = [
            fixture
            for fixture in self.catalog_fixtures()
            if fixture["result_id"] != "companion-dramaless-ineligible"
        ]
        with self.assertRaisesRegex(GENERATOR.ValidationError, "result catalog"):
            GENERATOR.build_status(missing)

        rewritten = self.catalog_fixtures()
        dramaless = next(
            fixture
            for fixture in rewritten
            if fixture["result_id"] == "companion-dramaless-ineligible"
        )
        dramaless["host"]["release"] = "2.0.0"
        dramaless["host"]["eligibility"] = "ELIGIBLE"
        dramaless["status"] = "PASS"
        dramaless["cleanup"] = "PASS"
        with self.assertRaisesRegex(GENERATOR.ValidationError, "approved identity"):
            GENERATOR.build_status(rewritten)

    def test_required_gate_fail_and_not_run_transitions(self):
        failed = self.catalog_fixtures()
        camera = next(item for item in failed if item["gate_id"] == "camera")
        camera["status"] = "FAIL"
        failed_status = GENERATOR.build_status(failed)
        self.assertEqual(self.gate_status(failed_status, "camera"), "FAIL")
        self.assertEqual(failed_status["readiness_status"], "NOT READY")

        incomplete = [
            fixture
            for fixture in self.catalog_fixtures()
            if fixture["gate_id"] != "camera"
        ]
        with self.assertRaisesRegex(GENERATOR.ValidationError, "result catalog"):
            GENERATOR.build_status(incomplete)

    def test_rejects_invalid_hashes(self):
        mutations = (
            ("source", "commit_sha"),
            ("source", "tree_sha"),
            ("package", "sha256"),
            ("evidence", 0, "sha256"),
        )
        for path in mutations:
            with self.subTest(path=path):
                fixture = self.fixture()
                target = fixture
                for part in path[:-1]:
                    target = target[part]
                target[path[-1]] = "not-a-hash"
                self.assert_invalid(fixture)

    def test_rejects_pass_with_cleanup_failure(self):
        fixture = self.fixture()
        fixture["status"] = "PASS"
        fixture["cleanup"] = "FAIL"
        self.assert_invalid(fixture)

        fixtures = self.catalog_fixtures()
        camera = next(item for item in fixtures if item["gate_id"] == "camera")
        camera["status"] = "FAIL"
        camera["cleanup"] = "FAIL"
        GENERATOR.validate_fixture(camera)
        status = GENERATOR.build_status(fixtures)
        self.assertEqual(self.gate_status(status, "camera"), "FAIL")
        self.assertEqual(status["readiness_status"], "NOT READY")

    def test_rejects_duplicate_json_keys_and_result_ids(self):
        with self.assertRaises(GENERATOR.ValidationError):
            json.loads('{"schema":1,"schema":1}', object_pairs_hook=GENERATOR.strict_object)

        fixture = self.fixture()
        with self.assertRaises(GENERATOR.ValidationError):
            GENERATOR.build_status([fixture, copy.deepcopy(fixture)])

        fixture = self.fixture()
        fixture["evidence"].append(copy.deepcopy(fixture["evidence"][0]))
        self.assert_invalid(fixture)

        fixtures = self.catalog_fixtures()
        fixtures[1]["evidence"][0] = copy.deepcopy(fixtures[0]["evidence"][0])
        with self.assertRaisesRegex(GENERATOR.ValidationError, "duplicate evidence id"):
            GENERATOR.build_status(fixtures)

    def test_malformed_status_fields_fail_with_controlled_validation_errors(self):
        for path in (
            ("host", "eligibility"),
            ("status",),
            ("cleanup",),
        ):
            for invalid in ([], {}):
                with self.subTest(path=path, invalid=type(invalid).__name__):
                    fixture = self.fixture()
                    target = fixture
                    for part in path[:-1]:
                        target = target[part]
                    target[path[-1]] = invalid
                    self.assert_invalid(fixture)

    def test_duplicate_and_unknown_keys_do_not_echo_untrusted_text(self):
        unsafe_key = "C:\\Users\\person\\" + "ghp_" + ("A" * 24)
        with self.assertRaises(GENERATOR.ValidationError) as duplicate:
            GENERATOR.strict_object([(unsafe_key, 1), (unsafe_key, 2)])
        self.assertNotIn(unsafe_key, str(duplicate.exception))

        fixture = self.fixture()
        fixture["source"][unsafe_key] = "safe"
        with self.assertRaises(GENERATOR.ValidationError) as unknown:
            GENERATOR.validate_fixture(fixture)
        self.assertNotIn(unsafe_key, str(unknown.exception))

    def test_main_controls_type_errors_without_echoing_values(self):
        arguments = SimpleNamespace(fixtures=FIXTURES, output=OUTPUT, check=True)
        stderr = StringIO()
        with mock.patch.object(GENERATOR, "parse_args", return_value=arguments), mock.patch.object(
            GENERATOR,
            "generate",
            side_effect=TypeError("C:\\Users\\person\\private-value"),
        ), redirect_stderr(stderr):
            self.assertEqual(GENERATOR.main([]), 1)
        self.assertEqual(
            stderr.getvalue(),
            "alpha quality status failed: invalid value type\n",
        )


if __name__ == "__main__":
    unittest.main()
