import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
SETUP_ACTION = ROOT / ".github" / "actions" / "setup-luajit" / "action.yml"

CURRENT_COMMIT = "1ee778a4e37122d8ca7d5733c590a47dafd6b15c"
CURRENT_VERSION = "LuaJIT 2.1.1787165859"
ENGINE_COMMIT = "43d0a19158ceabaa51b0462c1ebc97612b420a2e"
ENGINE_VERSION = "LuaJIT 2.1.1700008891"
CACHE_ACTION = "actions/cache@0057852bfaa89a56745cba8c7296529d2fc39830"


class CiWorkflowPolicyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.setup_action = SETUP_ACTION.read_text(encoding="utf-8")

    def test_main_jobs_use_the_exact_current_runtime(self):
        self.assertIn(f"LUAJIT_CURRENT_COMMIT: {CURRENT_COMMIT}", self.workflow)
        self.assertIn(f"LUAJIT_CURRENT_VERSION: {CURRENT_VERSION}", self.workflow)
        self.assertEqual(
            self.workflow.count("uses: ./.github/actions/setup-luajit"), 3
        )
        self.assertEqual(
            self.workflow.count("commit: ${{ env.LUAJIT_CURRENT_COMMIT }}"), 2
        )
        self.assertNotIn("luaVersion: luajit-2.1", self.workflow)
        self.assertNotIn("leafo/gh-actions-lua", self.workflow)

    def test_cache_key_is_exact_and_has_no_fallback(self):
        self.assertIn(CACHE_ACTION, self.setup_action)
        self.assertIn(
            "key: kfp-luajit-v1-${{ runner.os }}-${{ runner.arch }}-"
            "${{ inputs.commit }}",
            self.setup_action,
        )
        self.assertNotIn("restore-keys:", self.setup_action)
        self.assertIn('fetch --depth 1 origin "$LUAJIT_COMMIT"', self.setup_action)
        self.assertIn('rev-parse HEAD)" = "$LUAJIT_COMMIT"', self.setup_action)
        self.assertIn("KFP_LUAJIT_COMMIT", self.setup_action)
        self.assertIn('test "$actual_version" = "$LUAJIT_RUNTIME_VERSION"', self.setup_action)

    def test_engine_and_current_hash_compatibility_rows_are_bounded(self):
        self.assertIn(f"commit: {ENGINE_COMMIT}", self.workflow)
        self.assertIn(f"runtime_version: {ENGINE_VERSION}", self.workflow)
        self.assertIn(f"commit: {CURRENT_COMMIT}", self.workflow)
        self.assertIn(f"runtime_version: {CURRENT_VERSION}", self.workflow)
        self.assertEqual(self.workflow.count("runtime: gen1recomp-embedded"), 1)
        self.assertEqual(self.workflow.count("runtime: current-ci"), 1)
        self.assertIn(
            "lua tools/run_tests.lua packet_hash full_scene_benchmark\n"
            "          synthetic_scene_golden",
            self.workflow,
        )


if __name__ == "__main__":
    unittest.main()
