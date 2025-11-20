---
applyTo: '**'
---

# Copilot Instructions

These notes tell future contributors (human or AI) how to keep oRinGD compatible with existing `.orngd` session files while evolving the feature set.

## Mindset
- Treat every change as potentially compatibility-breaking until proven otherwise.
- `.orngd` archives must remain readable unless we explicitly bump both `APP_VERSION` and `SESSION_SCHEMA_VERSION`, document the change, and add migration guidance.
- `SessionVersionError` in `session_store.py` is the guardrail for truly breaking changes; prefer additive, backward-compatible data when possible.

## Workflow for Any Code Change
1. **Read the diff**: Identify whether the change touches `session_store`, `rating`, persistence helpers, or schemas.
2. **Classify impact**:
   - *No schema touch*: proceed, but ensure serialization formats are untouched.
   - *Additive schema change*: bump `SESSION_SCHEMA_VERSION`, add default handling for missing fields, update fixtures/tests.
   - *Breaking schema change*: bump both versions, add migration notes in the PR/README, and generate fixtures exercising the new failure path.
3. **Update metadata**: When versions change, keep `APP_VERSION` aligned and document rationale in release notes.
   - Versioning uses `MAJOR.MINOR.FEATURE`. Any new feature requires bumping the feature slot (`X.X.+1`) *after* confirming with the user that the bump is desired.
4. **Golden files**: For every schema/app change, produce at least one `.orngd` sample in `tests/fixtures/` representing the previous version and one for the new version so compatibility tests stay meaningful.
5. **Document decision**: Summarize compatibility implications in the PR ("Compat: backwards" or "Compat: break") so reviewers can gate merges.
6. **Git guardrail**: Never run `git push`, create tags, or interact with remotes unless a human explicitly orders it for the current task.

## Required Tests & Checks
Run tests from the project virtual environment to ensure the same dependencies as CI:

1. Activate the venv (PowerShell):
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```
   or (cmd.exe):
   ```cmd
   .\.venv\Scripts\activate
   ```
2. Execute the full suite:
   ```cmd
   python -m unittest discover -s tests
   ```
3. When debugging specific modules, you can still target them individually:
   ```cmd
   python -m unittest tests.test_session_store -v
   python -m unittest tests.test_iso23936_unittest -v
   ```

Additional expectations:
- Add/extend unit tests that fail when required fields disappear or types change.
- Verify `SessionVersionError` is raised when loading newer `.orngd` files with an older build and that older files still load.
- If you touch UI flows that rely on session persistence, add scenario tests (even smoke-level) so we detect regressions.

## Compatibility Gating Checklist
- [ ] Change classified (backwards-compatible / additive / breaking) and noted in PR text.
- [ ] Schema/app versions updated when necessary.
- [ ] Golden session fixtures updated and referenced in tests.
- [ ] `tests.test_session_store` includes asserts for both success and failure paths tied to your change.
- [ ] `README.md` or docs mention any user-facing migration/release notes.
- [ ] All tests pass locally with the commands above.

Following this workflow keeps future work honest about compatibility and ensures any deliberate break ships with documentation, fixtures, and automated coverage.
