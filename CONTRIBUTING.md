# Contributing

## The one rule that overrides all others

**Frozen artefacts are immutable.** Anything under `models/`, `docs/plans/`, `docs/evidence/`, and
the as-executed phase directories in `scripts/` records what was actually run to produce a sealed
scientific result. Do not edit, reformat, restyle, refactor, "clean up" or delete them — not even
to fix an obvious typo, and not even if a linter complains.

If a frozen component needs a cleaner interface for publication or reuse:

1. add a **new** wrapper alongside it, clearly labelled as a wrapper;
2. leave the frozen original untouched;
3. **prove equivalence** on the fixture suite and record the exact disagreement count (target: zero);
4. document the relationship in the wrapper's docstring.

Superseded scripts, failed attempts and historical receipts are never deleted. Non-canonical
material moves to a documented archival area; it does not disappear.

## Before opening a pull request

```bash
python scripts/release/release_check.py      # secrets, paths, large files, hashes, fixtures
python scripts/p1_13/p113_builder_fixtures.py
```

All fixtures must pass. Any new analysis code must be truth-blind unless it runs strictly after a
recorded truth authorization.

## Commit conventions

* One logical change per commit; explain **why**, not just what.
* Never amend, squash or rebase commits that record evidence.
* Do not add co-authorship trailers.

## Scientific claims

Any change that adds, strengthens or reframes a scientific claim must cite the canonical artefact
that supports it, and must respect
`docs/closure/PLASMIDCALL_LIMITATIONS_AND_NONCLAIMS.md`.
