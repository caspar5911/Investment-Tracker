# Windows Symlink Security Test Environment Resolution

Status: `RESOLVED`

Date: 2026-09-13

## Resolution

The earlier Windows `WinError 1314` limitation was an environment-level
symlink-creation restriction. Windows Developer Mode is now enabled, and the
unchanged security regression can create its symlink fixture and reach the
product assertion without administrative elevation.

## Verification evidence

- Base revision: `2d2119e12be7c36abf92ea8106deaf51fb2d4a12`
- Python: `3.13.5`
- Test: `tests/test_validation_security.py::test_manifest_rejects_symlink_artifact`
- Test command: `python -m pytest tests/test_validation_security.py::test_manifest_rejects_symlink_artifact -q`
- Test result: passed, exit code 0
- Full-suite command: `python -m pytest -q`
- Full-suite result: passed, exit code 0
- Count-confirmation command: `python -m pytest -o "addopts=-q"`
- Count-confirmation result: `580 passed, 1 skipped in 50.05s`, exit code 0
- Unchanged test blob: `521bb6c38ada8dbe3d0fa0ede1222821d1bd151e`,
  identical in the worktree and base revision

The `pytest-asyncio` default-loop-scope deprecation warning remains
non-failing and is unrelated to symlink handling.

## Boundary statement

No test was modified, weakened, or skipped to obtain this result. This record
does not alter frozen Phase 2, Phase 3, readiness, or Gate 1 evidence and does
not begin Phase 4 Gate 2.
