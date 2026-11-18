# Trophy Room sources and audit









The module has Hall of Fame, Yearly Results and All-Time GM Stats views.









## Authoritative data









- `data/gm_career_seasons.json` is the single audited team-season history, 2016–2025. Existing all-play counts, identities, points and finishes are unchanged. Added regular-season all-play counts and actual scheduled-game H2H counts come from the archived MFL exports used by the September 2026 GM-profile audit. The displayed `record_wins`, `record_losses`, and `record_ties` come from finalized league standings, including bonus games. `league_records.json` preserves the 320 public team-season record rows and the hash of their audited scheduler source.




- `data/gm_name_aliases.json` centralizes historical individual-name aliases. Both the Playoff Picture career popup and Trophy Room use `R/gm_history.R`. Identity follows individuals across teams. Comma-separated co-managers are normalized and shared team-seasons are counted once. Ambiguous same-person/multiple-team seasons fail rather than double-count.




- `data/gm_career_profiles.json` supplies the established 2026 GM membership and serves as a regression check. Every stored career field is checked against the canonical season rows before either view builds. Neither view can silently accept a conflicting baseline.









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









For future seasons, extend the audited season history and current GM membership together. The shared helper rejects incomplete histories and mismatched baselines. Refresh MFL results and published payout awards with the importer below. Do not run the retired independent CSV aggregation.









## Yearly payouts









`payouts.json` preserves published earnings, adjustments, final payouts, prize recipients and available period awards. The builder joins these to canonical season finishes, GM names and records rather than maintaining another history table. All 320 team balances and ten published season totals reconcile.









2018–2025 use public workbook exports listed in `gm_career_sources.json`. The local 2018 workbook is a blank template and must not replace the completed Google Sheet. 2016–2017 use the ADL tabs in the user's `2016 AFLADL Payouts.xlsx` and `2017 AFLADL Payouts.xlsx`. The 2016 list includes only paid teams; its entries sum exactly to the stated $3,060, and the remaining canonical teams receive zero. Preserve its explanations. The 2017 source explicitly allocates $7.50 tie adjustments to NYG and SEA. Normalize NOR to NOS and OAK to LVR only for identity matching.









Reimport with `python scripts/import_trophy_payouts.py WORKBOOK_CACHE LOCAL_LEAGUE_DIRECTORY`, then rebuild and run the tests above. Cache files are named `ADL-{year}-payouts.xlsx`; the local directory contains the year-specific Leagues folders. SHA-256 hashes record the imported files. The raw XLSX files are not needed during ordinary dashboard rebuilds. No workbooks are modified.









Some older Display sheets have blank or broken references. These become null, never fabricated winners. The Money sheet totals remain authoritative for payouts. Manual adjustments are separate from prize earnings and are not inferred from current prize rules. A payout-total reconciliation does not verify each award calculation. Source spreadsheet corrections remain unchanged.









The Finishes & Earnings table ranks totalEarnings derived from earnedBreakdown, not final cash payouts or canonical playoff finish. Shared weekly prizes are divided among the named winners. The 2017 NYG/SEA $7.50 awards are genuine earnings despite being stored as corrections; deposit and other payment adjustments are excluded. All 320 earned breakdown totals are validated. The original accounting amounts remain in the source snapshot for audit only.









## Results source policy









Trophy Room does not read the retired Trophy Room workbook or CSV. Both leagues use season-specific MFL weekly results (the same results published on the MFL league pages). `scripts/import_trophy_results.py` imports Super Bowl finals, starting lineups and regular-season award metrics together. `champions.json` and `super_bowl_lineups.json` are validated against each other at build time; the importer also reconciles full-season and regular-season all-play against every canonical team-season row used by GM profiles. Any disagreement stops the import.









Official results use MFL's stored franchise score, not an independently substituted player sum. In ADL 2022, MFL retains 208.0-198.6 while current starter points sum to 221.0-204.4 after documented Bills/Bengals replacement imports. Both values are explicitly distinguished in the hover; no synthetic adjustment is added to players. ADL 2025 is 248.9-207.2 in both MFL matchup results and starter sums.









Conference award recipients remain those recorded in the published payout workbooks (including the early local workbooks). Metrics are calculated from MFL weeks 1-12: HC is league-wide all-play percentage, OC/DC sum actual offensive/defensive starters, and GM sums MFL optimal starters (`shouldStart=1`), matching the shared weekly dashboard calculation. Decimal values round half up at display precision. Earnings and historical payout corrections use their existing audited sources; no earnings come from the retired Trophy Room.









Refresh after historical scoring corrections or when a completed season is added:









```




python scripts/import_trophy_results.py --league LEAGUE --cache /path/to/mfl-cache




```









Replace LEAGUE with ADL or FAFL, then run the ordinary Trophy Room builder. A fresh cache fetches current MFL exports; an existing cache reproduces its exact responses. `results_provenance.json` records source URLs and SHA-256 hashes. The old `import_super_bowl_lineups.py` entry point delegates to this importer, so it cannot reintroduce a different final from displayed data.








## Ending-roster player statistics







Yearly Results team names and logos open the championship-week MFL roster, including IR and taxi players. `python scripts/import_trophy_rosters.py --league LEAGUE --cache /path/to/mfl-cache` refreshes every completed season. Raw responses can be reproduced with that cache; source URLs and SHA-256 hashes are stored in `rosters_provenance.json`. Both ordinary builders validate season coverage and copy the imported snapshots to the website. The UI fetches only the selected year's roster file when needed.







Player statistics cover weeks 1 through the fantasy championship (Week 16 before 2021, Week 17 thereafter), irrespective of the fantasy franchise holding the player at the time. MFL's Top Performers weekly report supplies points and played-game presence. Numeric zero-point games count toward GP; byes and absent games do not. PPG is total points / GP. Starter points sum the weeks in which the player played and any franchise in the league started him. Starter PPG divides by those games started; duplicate player copies count once per week. No starts displays zero starter points and an unavailable starter average. Negative points remain negative. Older MFL roster exports sometimes duplicate a taxi player as an active player; roster membership is deduplicated by player ID, preserving the reserve designation.







The importer checks every scored starter against the same MFL weekly player report before publishing. Tests cover trades between franchises, duplicate copies, zero-point games, missed games, negative scores, zero starts, reserve duplication and full historical coverage. Run `python -m unittest discover -s tests -p test_trophy_rosters.py` after importing.






## Top Performances





The fourth view is ordered Hall of Fame, Yearly Results, Top Performances, All-Time GM Stats. Native Scoring and Current Scoring cover Total Team Points, Offensive Points (including PK/PN and historical KR), Defensive Points, Potential Points, and individual player games by position. Team lists separate NFC/AFC and Weeks 1-12/playoffs. Higher points rank first; ties at tenth are retained. Individual player games are unique by year/week/MFL player ID, regardless of fantasy copies or whether anyone started the player.





Native results come from season-specific MFL weekly results and the public Top Performers report. Player metadata requests include the league ID to preserve historical league-specific position overrides. Historical franchise/GM identities follow the same canonical career history and alias helpers as the other Trophy Room views. Playoff fields use the published six/seven-team bracket format and audited finishes; scheduled field/placement games count, byes and consolation teams do not. Once the current regular season finishes, qualification comes from the existing published bracket-data snapshot, never projected qualifiers.





Current Scoring uses the existing ADL26 reconstructed NFL-stat overlay for earlier seasons and recorded MFL scores for 2026. It is explicitly labeled reconstructed, not an original MFL result or a fitted forecasting model. Original starters and historical positional limits are preserved; Potential Points is reoptimized within those limits. Missing player scores and positions absent from 2026 scoring (notably FAFL's historical KR slot) are excluded, never silently assigned zero. The UI displays coverage for the selected metric. MFL stored totals remain distinct from player sums where necessary. Player/team popups show stat lines or the applicable lineup and link to the original public MFL scoring report.





`top_performances_history.json` freezes completed-season top ranks and their detail records. `top-performances.json` merges those with all completed current-season weeks; it is the source for the identical website snapshot. Source URLs/hashes, the scoring-rule fingerprint, overlay hash and statistical-source provenance are retained in these snapshots and `top_performances_sources.json`. Historical football stat lines use the audited season-specific GSIS/MFL maps; 2022 BUF/CIN replacement statistics use Week 18 consistently with the league imports. Current-season supplemental stat lines use nflverse and DynastyProcess ID mappings. Scoring-page links show original MFL points, not the reconstructed counterfactual.





Refresh only the completed current-season weeks:





```


python scripts/import_top_performances.py --league LEAGUE --cache artifacts/top-performance-cache


python -m unittest discover -s tests -p test_top_performances.py


```





Replace LEAGUE with ADL or FAFL. The existing authorized weekly publication workflow runs this after its publication marker. A failed optional records refresh preserves the last successful dated snapshot and does not block core league publication. Ordinary Trophy Room builds copy the saved snapshot. The updater refuses to silently advance the Current Scoring year or accept a changed rule fingerprint: rebuild/audit historical reconstruction when scoring changes.





To rebuild completed-season rankings, supply the original derived scoring CSV and optional stat lines generated from the existing local NFL caches:





```


Rscript scripts/export_performance_stat_lines.R FFAUC_ROOT artifacts/performance-stat-lines.json


python scripts/import_top_performances.py --league LEAGUE --history --overlay PATH_TO_ADL26_OVERLAY_CSV --stats artifacts/performance-stat-lines.json --cache artifacts/historical-performance-cache


python scripts/import_top_performances.py --league LEAGUE --cache artifacts/current-performance-cache


```





The overlay source is `DerivedScoringData/ff_playerscores_FAFL_withADL26scores_2014_2025.csv`, produced by the existing `HelperFunctions/build_ff_playerscores_with_adl26_scores.R` / `add_estimated_fafl_pts.R` pipeline. It is not the retired Trophy Room workbook. Neither importer modifies the original league caches. Rebuild completed history after historical source corrections; rebuild the 2026 reconstruction before deliberately advancing the scoring-year guard. The stat-line exporter requires R's jsonlite package; runtime importers/tests use Python's standard library and the existing shared Trophy Room helpers.




### Player scoring-event popups



Player popups follow CHI Team Tools: Event / Points rows, position-specific event order, per-event rounding, and a Total footer. `scripts/performance_scoring.py` evaluates captured MFL `live_stats_idp_WW.txt` events against that league's season-specific rules for Native Scoring and 2026 rules for recorded current-season games. Labels and ordering use the same MFL event catalog as CHI Team Tools, extended with missing official MFL allRules labels. Historical source availability is recorded honestly: missing native event details show the published total with an explicit reference-only note. If captured events disagree with MFL's stored total, both are shown; the ranking retains the published total without inventing an adjustment.



Historical Current Scoring uses the frozen `top_performances_reconstructed_breakdowns.json` contribution bank from the existing ADL26 overlay engine (`add_estimated_fafl_pts.R`, `keep_details=TRUE`) and original cached NFL statistics. Every retained Current Scoring contribution sum is checked against its ranked estimate. These are labeled reconstructed; they are not represented as original MFL event records. Return yards with no scoring rule never appear as scoring contributions. The bank retains engine/cache file hashes. Rebuild it alongside the historical scoring overlay when historical inputs change: `Rscript scripts/export_performance_scoring_breakdowns.R FFAUC_ROOT`. The exporter loads function definitions only and never initializes league connections or changes source caches. Ordinary refreshes retain saved historical breakdowns and fetch completed current-season event sources; they do not run R or read local NFL caches. The snapshots remain identical between source and docs. `tests/test_performance_scoring.py` covers unscored return yards, per-event rounding/field-goal thresholds, all saved sums, and Taysom Hill's 2022 Week 5 47.8-point result.


Individual Performances retains the top 25 unique NFL player games for every supported position in Native Scoring and Current Scoring, including all ties at rank 25. Team boards remain top 10 including ties at tenth. The expanded historical snapshots and reconstructed contribution bank include the additional games; completed current-season weeks merge with these using the same separate limits. The source metadata records `individualRankingLimit: 25` and `teamRankingLimit: 10`.

### Top Seasonlong Scores

The seasonlong tab ranks team seasons (top 10 including ties) by record winning percentage, all-play percentage, total, offensive, defensive, or potential points, separately for NFC/AFC. Individual NFL player seasons retain the top 25 including ties at each position. Team and individual Regular Season / Playoffs / Combined selectors are independent. Regular season covers Weeks 1–12; team playoffs use actual qualifying teams and scheduled postseason games, including placement games, excluding byes and consolation teams. Partial seasons are excluded from every seasonlong board. H2H uses the MFL schedule; all-play and points count each team-week once. Popups reconcile weekly totals and link to original MFL reports.

Native Scoring preserves MFL scores and audited records. Current Scoring uses the same reconstructed historical overlay and lineup optimizer as Top Weekly Scores; missing required inputs exclude a total rather than silently treating it as zero. Offensive points include special teams. Current-season games use recorded scores and results. Canonical GM membership comes from gm_career_seasons.json and the current roster, with input hashes retained in metadata.

Both leagues use four quarterly bonuses through 2020 and five bonuses from 2021 (four quarters plus the regular season). Bonus rankings use league-wide all-play, points, then potential points; award cutoffs are within conferences through 2024 and league-wide from 2025. See the [2021 schedule proposals](https://www46.myfantasyleague.com/2021/options?L=60206&O=28&THREAD=39) and [2023 ballot discussion](https://www46.myfantasyleague.com/2023/options?L=60206&O=28&THREAD=25), which describes five bonuses. The commissioner corrected FAFL’s duplicated 2023 Q4 result in MFL. A fresh 2014–2025 audit on November 17, 2026 reconciled all 32 corrected 2023 records to the standard five-bonus format; no separate adjustment remains. Native uses the corrected published totals. This importer does not alter canonical GM history or MFL standings.

Build completed history with `python scripts/import_seasonlong_performances.py --league LEAGUE --history --overlay PATH_TO_ADL26_OVERLAY_CSV --cache CACHE`. Ordinary refreshes run the same command without --history/--overlay and retain the frozen seasonlong_performances_history.json until the current season’s final week is official, then merge the completed season. Rebuild history when historical sources change. Builders copy the snapshot to docs; the optional official-write-authorized workflow step refreshes it alongside weekly rankings. Tests verify rank ties, bonus formats, saved total reconciliation, and native canonical records.

Seasonlong record displays omit a zero tie count (15–1); nonzero ties remain visible (15–1–1), including H2H/bonus subtext and popups. Weekly rankings continue to include completed weeks from the ongoing season.

### Individual season averages and complete timelines

Individual totals include PPG subtext (points / games played in the selected range). Player popups show every week in that range and a Cum. Avg. column using played games through each week. Numeric zero scores count as games; bye/absence rows do not add points or games. Bye labels come from MFL player-report weekly cells; Out, IR, Suspended, Holdout and Retired come from the corresponding archived MFL injuries export. Blank report weeks without a confirmed absence status display Did not play. No absence reason is guessed. Player popups use a 240px width with the existing 10px placement gap.

The frozen historical timelines can be rebuilt without recalculating score rankings: `python scripts/enrich_seasonlong_player_weeks.py --league LEAGUE --cache CACHE`, followed by the normal seasonlong importer to publish the merged snapshot. Source URLs, timestamps and hashes are retained in playerStatusSources. New completed-season imports create the same full timelines with scripts/seasonlong_player_weeks.py.

Team season popups insert bonus outcomes immediately after the relevant quarter’s final week (and the full regular-season bonus after Week 12). Every scheduled game retains its MFL home/away flag, opponent, score and result. Historical Current Scoring game scores use the same reconstructed original-starter totals as the rankings; Native uses stored MFL schedule scores and result flags. Multiple games in a week remain separate matchup lines. Bonus rows affect records, not point totals. W/L/T outcomes use the Playoff module’s green/red/neutral presentation. Final Roster appears below the timeline and uses the same archived roster and full-season player statistics as Season Archive; it is fetched once per year and safely cached.
The appended roster statistics retain full-season native MFL values in every phase, consistent with Season Archive. Reconstructed Current Scoring popups label that roster section Native season statistics.
