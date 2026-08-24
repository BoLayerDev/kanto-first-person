# Native Windows Git hooks

Git for Windows shell hooks can fail inside a restricted Codex execution
container before hook logic starts. The MSYS2 runtime reports that it cannot
create its signal pipe.

The files in `.githooks/windows` preserve the repository commit safeguards and
start through the native Windows Python launcher. They do not use `env.exe`,
`sh.exe`, `bash.exe`, or `--no-verify`.

Enable them for one local clone only:

```powershell
git config --local core.hooksPath .githooks/windows
```

Requirements:

- `C:\Windows\py.exe` must exist.
- Python 3.14 must be registered with the Windows Python launcher. The hook
  shebang and `.python-version` both declare 3.14. Other versions fail closed.
- `guard.prePushCommand` must be absent. Any configured value is unsupported
  because the original hook executes it as Bash shell text. The native
  pre-push hook does not interpret or execute it and fails closed instead.

Run the focused tests:

```powershell
py -3.14 tests/tools/test_windows_git_hooks.py
```

The Python hook preserves the original protected-branch, staged whitespace,
forbidden-file, file-size, conflict-marker, secret-pattern, commit-message,
upstream-remote, protected-push, and pushed-diff checks. The only unsupported
original behavior is arbitrary Bash `guard.prePushCommand` execution.
