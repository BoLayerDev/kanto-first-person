# Contributing

Use the `v2-rewrite` branch or a focused feature branch. Read `AGENTS.md`, `PROJECT_STATUS.md`, the companion API specification, and the relevant parity row before changing code.

Every change must include:

- A clear behavior or defect target.
- LuaJIT-compatible source.
- Unit or contract tests.
- Resource-lifetime review for graphics or audio work.
- Updated compatibility, parity, or architecture text when the contract changes.
- Confirmation that no ROM, save, extracted cache, credential, or private evidence entered the change.

Run all repository checks before requesting review. Do not update golden images without an independent visual review. Sign commits or use a signed-off contribution record when requested by the maintainer.
