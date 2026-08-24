from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
import uuid


ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".githooks" / "windows"
ARTIFACTS = ROOT / "tests" / ".artifacts"
PYTHON = Path("C:/Windows/py.exe")
sys.path.insert(0, str(HOOKS))

from hooklib import (  # noqa: E402
    HookFailure,
    SUPPORTED_PYTHON,
    ZERO_SHA1,
    parse_push_lines,
    require_supported_python,
    validate_commit_subject,
)


class WindowsGitHookUnitTests(unittest.TestCase):
    def test_declares_and_runs_supported_python(self):
        self.assertEqual(SUPPORTED_PYTHON, (3, 14))
        if sys.version_info[:2] == SUPPORTED_PYTHON:
            require_supported_python()
        else:
            with self.assertRaisesRegex(HookFailure, "Python 3.14"):
                require_supported_python()
        self.assertEqual((ROOT / ".python-version").read_text(encoding="utf-8").strip(), "3.14")
        for name in ("pre-commit", "commit-msg", "pre-push"):
            first = (HOOKS / name).read_text(encoding="utf-8").splitlines()[0]
            self.assertEqual(first, "#!C:/Windows/py.exe -3.14")

    def test_accepts_repository_style_subject(self):
        validate_commit_subject("fix(hooks): add native Windows launchers")

    def test_rejects_vague_subject(self):
        with self.assertRaisesRegex(HookFailure, "too short|too vague"):
            validate_commit_subject("fix")

    def test_rejects_long_subject(self):
        with self.assertRaisesRegex(HookFailure, "longer than 72"):
            validate_commit_subject("fix(hooks): " + "x" * 70)

    def test_rejects_leading_and_trailing_subject_whitespace(self):
        for subject in (
            " fix(hooks): reject leading whitespace",
            "fix(hooks): reject trailing whitespace ",
        ):
            with self.subTest(subject=subject):
                with self.assertRaisesRegex(HookFailure, "repository style"):
                    validate_commit_subject(subject)

    def test_parses_pre_push_protocol(self):
        rows = parse_push_lines([
            f"refs/heads/topic {'1' * 40} refs/heads/topic {ZERO_SHA1}\n"
        ])
        self.assertEqual(rows[0][0], "refs/heads/topic")
        self.assertEqual(rows[0][3], ZERO_SHA1)

    def test_rejects_malformed_pre_push_protocol(self):
        with self.assertRaisesRegex(HookFailure, "four fields"):
            parse_push_lines(["refs/heads/topic only-two\n"])


@unittest.skipUnless(os.name == "nt", "native Windows Git hook integration")
class WindowsGitHookIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(PYTHON.is_file(), "C:/Windows/py.exe is required")
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        self.root = (ARTIFACTS / f"windows-hooks-{uuid.uuid4().hex}").resolve()
        self.repo = self.root
        self.run_command("git", "init", "--quiet", "--initial-branch=feature/hook-test", str(self.repo), cwd=ROOT)
        self.run_command("git", "config", "--local", "user.name", "Hook Test", cwd=self.repo)
        self.run_command("git", "config", "--local", "user.email", "hook-test@example.invalid", cwd=self.repo)
        self.run_command("git", "config", "--local", "commit.gpgsign", "false", cwd=self.repo)
        target = self.repo / ".githooks" / "windows"
        shutil.copytree(HOOKS, target)
        self.run_command("git", "config", "--local", "core.hooksPath", ".githooks/windows", cwd=self.repo)
        (self.repo / "seed.txt").write_text("seed\n", encoding="utf-8", newline="\n")
        self.run_command("git", "add", "seed.txt", cwd=self.repo)
        self.run_command("git", "commit", "--quiet", "-m", "test(hooks): create baseline commit", cwd=self.repo)
        self.baseline = self.git_output("rev-parse", "HEAD")

    def tearDown(self):
        resolved = self.root.resolve()
        self.assertTrue(resolved.is_relative_to(ARTIFACTS.resolve()))
        self.assertTrue((resolved / ".git").is_dir())

    def run_command(self, *args, cwd=None, input_text=None, check=True, env=None):
        return subprocess.run(
            args,
            cwd=cwd,
            input=input_text,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=check,
            env=env,
        )

    def git_output(self, *args):
        return self.run_command("git", *args, cwd=self.repo).stdout.strip()

    def stage(self, name: str, content: str):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        self.run_command("git", "add", "--", name, cwd=self.repo)

    def commit(self, message: str, *, cleanup: str | None = None):
        args = ["git", "commit"]
        if cleanup is not None:
            args.append(f"--cleanup={cleanup}")
        args.extend(["-m", message])
        return self.run_command(*args, cwd=self.repo, check=False)

    def invoke_pre_push(self, remote: str, lines: str):
        return self.run_command(
            str(PYTHON),
            "-3.14",
            str(self.repo / ".githooks" / "windows" / "pre-push"),
            remote,
            "unused-url",
            cwd=self.repo,
            input_text=lines,
            check=False,
        )

    def assert_commit_rejected(self, result, pattern: str):
        self.assertNotEqual(result.returncode, 0)
        self.assertRegex(result.stdout + result.stderr, pattern)
        self.assertEqual(self.git_output("rev-parse", "HEAD"), self.baseline)

    def test_real_normal_hook_positive_commit(self):
        self.stage("valid.txt", "valid\n")
        result = self.commit("test(hooks): accept a normal guarded commit")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        output = result.stdout + result.stderr
        self.assertIn("pre-commit: safeguards passed", output)
        self.assertIn("commit-msg: message passed", output)
        self.assertNotEqual(self.git_output("rev-parse", "HEAD"), self.baseline)

    def test_rejects_protected_branch_commit(self):
        self.run_command("git", "branch", "-m", "main", cwd=self.repo)
        self.stage("protected.txt", "blocked\n")
        self.assert_commit_rejected(self.commit("test(hooks): reject protected branch"), "direct commits")

    def test_rejects_exact_staged_whitespace_error(self):
        self.stage("whitespace.txt", "trailing space \n")
        self.assert_commit_rejected(self.commit("test(hooks): reject staged whitespace"), "whitespace errors")

    def test_rejects_forbidden_file(self):
        self.stage("config/.env", "placeholder=true\n")
        self.assert_commit_rejected(self.commit("test(hooks): reject forbidden file"), "must not be committed")

    def test_rejects_large_file(self):
        self.run_command("git", "config", "--local", "guard.maxFileBytes", "4", cwd=self.repo)
        self.stage("large.txt", "12345")
        self.assert_commit_rejected(self.commit("test(hooks): reject large staged file"), "local limit is 4 bytes")

    def test_rejects_conflict_marker(self):
        self.stage("conflict.txt", "<<<<<<< local\nleft\n=======\nright\n>>>>>>> remote\n")
        self.assert_commit_rejected(self.commit("test(hooks): reject conflict marker"), "conflict")

    def test_rejects_synthetic_secret_pattern(self):
        synthetic = "AK" + "IA" + ("A" * 16)
        self.stage("secret.txt", f"token={synthetic}\n")
        self.assert_commit_rejected(self.commit("test(hooks): reject secret pattern"), "private key or access token")

    def test_rejects_invalid_max_file_config(self):
        self.run_command("git", "config", "--local", "guard.maxFileBytes", "invalid", cwd=self.repo)
        self.stage("config.txt", "value\n")
        self.assert_commit_rejected(self.commit("test(hooks): reject invalid guard config"), "must be an integer")

    def test_rejects_invalid_commit_message(self):
        self.stage("message.txt", "value\n")
        self.assert_commit_rejected(self.commit("fix"), "too short|too vague")

    def test_verbatim_commit_rejects_subject_edge_whitespace_without_moving_head(self):
        self.stage("subject-whitespace.txt", "value\n")
        for message in (
            " test(hooks): reject leading whitespace",
            "test(hooks): reject trailing whitespace ",
        ):
            with self.subTest(message=message):
                result = self.commit(message, cleanup="verbatim")
                self.assert_commit_rejected(result, "repository style")

    def test_pre_push_rejects_upstream_remote(self):
        head = self.git_output("rev-parse", "HEAD")
        result = self.invoke_pre_push(
            "upstream",
            f"refs/heads/feature/hook-test {head} refs/heads/feature/hook-test {ZERO_SHA1}\n",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("pushes to upstream are blocked", result.stderr)

    def test_pre_push_rejects_protected_branch(self):
        head = self.git_output("rev-parse", "HEAD")
        result = self.invoke_pre_push(
            "origin",
            f"refs/heads/main {head} refs/heads/main {ZERO_SHA1}\n",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("direct development pushes", result.stderr)

    def test_pre_push_fails_closed_for_any_shell_command_config(self):
        self.run_command("git", "config", "--local", "guard.prePushCommand", "   ", cwd=self.repo)
        head = self.git_output("rev-parse", "HEAD")
        result = self.invoke_pre_push(
            "origin",
            f"refs/heads/feature/hook-test {head} refs/heads/feature/hook-test {ZERO_SHA1}\n",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("shell commands are not supported", result.stderr)

    def test_pre_push_rejects_pushed_diff_whitespace(self):
        bad = self.repo / "bad-push.txt"
        bad.write_text("bad trailing space \n", encoding="utf-8", newline="\n")
        blob = self.git_output("hash-object", "-w", str(bad))
        index = self.repo / ".git" / "test-pre-push-index"
        env = {**os.environ, "GIT_INDEX_FILE": str(index)}
        self.run_command("git", "read-tree", "HEAD", cwd=self.repo, env=env)
        self.run_command(
            "git", "update-index", "--add", "--cacheinfo", f"100644,{blob},bad-push.txt",
            cwd=self.repo, env=env,
        )
        tree = self.run_command("git", "write-tree", cwd=self.repo, env=env).stdout.strip()
        commit = self.run_command(
            "git", "commit-tree", tree, "-p", self.baseline,
            cwd=self.repo, input_text="test(hooks): synthesize bad pushed diff\n",
        ).stdout.strip()
        result = self.invoke_pre_push(
            "origin",
            f"refs/heads/feature/hook-test {commit} refs/heads/feature/hook-test {self.baseline}\n",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("whitespace", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
