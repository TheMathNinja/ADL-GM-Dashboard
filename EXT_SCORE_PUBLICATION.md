# EXT Score Publication Safeguards

## Source and Rebuild

- The weekly source job scrapes every completed week, not only the newest week.
- `score_metadata.csv` records the score fingerprint and a durable source path under `data/score_sources/`.
- GitHub Actions caches are performance aids, not the authority. Missing or mismatched caches are restored only from the fingerprint-matching durable source.
- Current-season builds use the exact metadata-named source, never the highest filename or a modification-time shortcut.
- Current-season rebuilds preserve published prior-season history rather than rebuilding it from incomplete old caches.

## Validation

Before confirming an EXT build, `assert_ext_complete_build()` compares every weekly player snapshot with the confirmed source, including games played, total points, average points, ranks and robustness. It also verifies the current-season history, summary, and roster-linked candidate ranks. A missing player or stale summary is a failure even if the output contains the expected week number.

The publication receipt fingerprints the output files and records the confirmed source metadata. A failed EXT component restores the previous publication files together. Other dashboard components remain independent.

## Deployment

Weekly and roster jobs commit their outputs and dispatch the same serialized deployment workflow. Roster jobs no longer deploy directly or swallow hosting errors. Deployment checks the bundled receipt, output fingerprints, bundled source metadata and latest source metadata on `main`; missing or mismatched information blocks publication. Deployment checks out current `main` when its job starts.

The app reports only the status of its bundled confirmed publication. Calendar checks can display an update-pending warning but never make scores official. Provider outages or hosting failures can still delay an update; they must be visible rather than silently relabeled as current.

## Regression Tests

Every weekly refresh, roster refresh and deployment runs:

```text
Rscript tests/test_ext_publication_integrity.R
Rscript tests/test_ext_pending_status.R
```

Cases include the Cousins six-game regression, missing weeks/players, stale summaries and candidates, same-week corrections, corrupt/evicted caches, future-named caches, misleading timestamps, historical preservation, source changes before deployment, and pending-status warnings that do not promote finality by the clock.
