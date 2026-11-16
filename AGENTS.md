# Coordinated League Changes

Shared probability labels and tie-display thresholds are owned by the
Commissioner repository's `contracts/live_display.json`. Follow its
`contracts/README.md`: update the versioned policy and reviewed examples, then
run `scripts/sync_live_display_contract.py` against BOTH GM repositories with
`--write`. Do not edit generated policy blocks or mirrored test fixtures by hand.

Keep presentation changes separate from scoring and Guardian lineup rules.
For other shared behaviors, declare the dependency and add a reviewed contract
to the cross-repository gate. Never weaken tests just to obtain a passing run.

Before a production push, run every validation command in the private Guardian
`.github/workflows/league-audit.yml` contracts job against all four candidate
checkouts, plus focused tests. Repeat after edits or rebases. Publish compatible
consumers before checkers that require their files. Record audited revisions
and distinguish local tests from actual production recovery.
