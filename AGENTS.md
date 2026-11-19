# Coordinated League Changes

## NFL Team Identity

Use MFL three-letter NFL team codes internally, including JAC (the live ADL franchise also uses JAC). Normalize legacy/provider aliases using config/nfl_teams.json and R/nfl_teams.R or scripts/nfl_teams.py; convert to external codes only at named API/asset boundaries. FA is a non-team sentinel. Never add ad hoc maps or rewrite historical raw sources/franchise IDs. Run Commissioner's scripts/check_nfl_team_codes.py across all four checkouts and the full publication gate. Shared mapping changes require synchronized copies and all-32-team/provider round-trip tests.

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
