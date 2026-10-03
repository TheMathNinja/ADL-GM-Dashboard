# Trophy Room sources and audit

The module's two views are Champions and All-Time. The legacy MFL record widgets are intentionally excluded.

## Authoritative data

- `data/gm_career_seasons.json` is the single audited team-season history, 2016–2025. Existing all-play counts, identities, points and finishes are unchanged. Added regular-season all-play counts and actual scheduled-game H2H counts come from the archived MFL exports used by the September 2026 GM-profile audit. The displayed `record_wins`, `record_losses`, and `record_ties` come from finalized league standings, including bonus games. `league_records.json` preserves the 320 public team-season record rows and the hash of their audited scheduler source.
- `data/gm_name_aliases.json` centralizes historical individual-name aliases. Both the Playoff Picture career popup and Trophy Room use `R/gm_history.R`. Identity follows individuals across teams. Comma-separated co-managers are normalized and shared team-seasons are counted once. Ambiguous same-person/multiple-team seasons fail rather than double-count.
- `data/gm_career_profiles.json` supplies the established 2026 GM membership and serves as a regression check. Every stored career field is checked against the canonical season rows before either view builds. Neither view can silently accept a conflicting baseline.
- `champions.csv` is a snapshot of the Champions tab of [ADL Trophy Room](https://docs.google.com/spreadsheets/d/1wIpnnSlCFM0IcqpxgD8na1fn-Bv0TOFrDQ_Kb6ICKao/edit), retrieved 2026-10-02. Published final scores and all 80 conference awards are retained. Winner and runner-up identities are validated against audited finishes. Season records use the same canonical finalized league totals (including bonus games) as the All-Time leaderboard, rather than the spreadsheet's inconsistent records. The original CSV retains the original records for audit.

## Errors avoided from the legacy leaderboard

`LeagueFeatures/Leaderboard/ADL_AllTimeLeaderboard.R` was hard-coded to the 2025 league year, so it stopped at 2024 and used a 2025 active-owner list. Its six inline aliases and strict comma-space splitting could fragment identity. It averaged MFL `allplay_winpct` instead of the corrected full-season score comparisons and used an unweighted mean across seasons of different lengths. The shared historical helper was later fixed to request `MISSING_AS_BYE=1` and stop at Week 16 before 2021 / Week 17 thereafter; the old CSV was never regenerated with those fixes.

The old `H2H Record` label was misleading because MFL standings include bonus results. The column is now called `Record` and deliberately includes those bonus games, as requested. For example, Kansas City's 2024 Record is 18–4–0 (13–4 in actual scheduled games plus five bonus wins). Historical bonus formats differ, especially before 2019; finalized league totals are used directly rather than subtracting schedule records or applying the current bonus algorithm retroactively. Champions and individual GM histories use these same totals.

Spreadsheet rendering also turned some W-L-T records into dates (e.g. `11-5-2000`) or `########`; the module renders explicit W-L-T text. No public output includes owner emails or usernames.

## Rebuild and validation

Run from the repository root:

```
Rscript scripts/build_trophy_room.R
Rscript scripts/test_trophy_room.R
Rscript scripts/test_gm_profiles.R
```

The ordinary weekly refresh rebuilds Trophy Room and stages its generated data. Trophy Room deliberately reports completed seasons through 2025; Playoff Picture adds the current year's completed weeks to the exact same baseline. Ranks use the selected individual-GM pool in Trophy Room, versus the 32 current team/GM groups in Playoff Picture. Those scope differences are intentional and labeled.

To reproduce the historical enrichment, set `ADL_GM_HISTORY_CACHE` to the directory containing `ADL-{year}-weeklyResults.json` and `ADL-{year}-schedule.json` and run `node scripts/enrich_gm_history.cjs`. It validates every original full-season all-play count before writing. Canonical identities and finishes remain unchanged. Provenance hashes are in `history_provenance.json`.

For future seasons, extend the audited season history and current GM membership together. The shared helper rejects incomplete histories and mismatched baselines. Update the Champions CSV after official league awards are recorded. Do not run the retired independent CSV aggregation.

## Yearly payouts

`payouts.json` preserves published earnings, adjustments, final payouts, prize recipients and available period awards. The builder joins these to canonical season finishes, GM names and records rather than maintaining another history table. All 320 team balances and ten published season totals reconcile.

2018–2025 use public workbook exports listed in `gm_career_sources.json`. The local 2018 workbook is a blank template and must not replace the completed Google Sheet. 2016–2017 use the ADL tabs in the user's `2016 AFLADL Payouts.xlsx` and `2017 AFLADL Payouts.xlsx`. The 2016 list includes only paid teams; its entries sum exactly to the stated $3,060, and the remaining canonical teams receive zero. Preserve its explanations. The 2017 source explicitly allocates $7.50 tie adjustments to NYG and SEA. Normalize NOR to NOS and OAK to LVR only for identity matching.

Reimport with `python scripts/import_trophy_payouts.py WORKBOOK_CACHE LOCAL_LEAGUE_DIRECTORY`, then rebuild and run the tests above. Cache files are named `ADL-{year}-payouts.xlsx`; the local directory contains the year-specific Leagues folders. SHA-256 hashes record the imported files. The raw XLSX files are not needed during ordinary dashboard rebuilds. No workbooks are modified.

Some older Display sheets have blank or broken references. These become null, never fabricated winners. The Money sheet totals remain authoritative for payouts. Manual adjustments are separate from prize earnings and are not inferred from current prize rules. A payout-total reconciliation does not verify each award calculation. Source spreadsheet corrections remain unchanged.

The Finishes & Earnings table ranks totalEarnings derived from earnedBreakdown, not final cash payouts or canonical playoff finish. Shared weekly prizes are divided among the named winners. The 2017 NYG/SEA $7.50 awards are genuine earnings despite being stored as corrections; deposit and other payment adjustments are excluded. All 320 earned breakdown totals are validated. The original accounting amounts remain in the source snapshot for audit only.
