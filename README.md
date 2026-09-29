# ADL GM Dashboard

Player-facing tools for ADL general managers.

The first module is a Contract Extension explorer. It imports current roster data from MFL/ffscrapr, derives salary-rank curves from cached league roster scrapes, calculates the extension salary, and shows the per-year smoothing math that drives the result.

Repo: https://github.com/TheMathNinja/ADL-GM-Dashboard

GM Dashboard landing page: https://themathninja.github.io/ADL-GM-Dashboard/

Note: the landing page is hosted by GitHub Pages. The Contract Extension Calculator itself is a Shiny app, so it needs a Shiny-capable host such as shinyapps.io, Posit Connect, or a league-controlled R server for the live interactive app.

## Shiny Deployment

The repeatable shinyapps.io deployment entrypoint is:

```r
Rscript scripts/deploy_shinyapps.R
```

Before running it, set these environment variables locally or in a secure deployment environment:

- `SHINYAPPS_ACCOUNT`
- `SHINYAPPS_TOKEN`
- `SHINYAPPS_SECRET`
- `SHINYAPPS_APP_NAME`, optional; defaults to `adl-ext-calculator`

## Local Setup

1. Put the current Contract Admin export at `data/source/contract_admin_2026.xlsx` for EXT tab fallback fields.
2. Make sure the local raw league scrape cache is available at `C:/Users/Michael/Documents/R/FFAucAndDraft/RawLeagueData` or set `ADL_RAW_LEAGUE_DATA_DIR`.
3. Build the local data extracts:

```r
Rscript scripts/prepare_ext_data.R
```

4. Run the app:

```r
shiny::runApp()
```

## Intended Architecture

- `scripts/prepare_ext_data.R` imports MFL-facing data into small app-ready CSVs.
- `R/salary_snapshots.R` derives EXT salary curves from `ff_rosters_ADL##_YYYY_raw.rds` caches instead of workbook salary tabs.
- `R/ext_engine.R` owns the rule math and returns both a final price and explainable intermediate steps.
- `app.R` is only the interactive GM experience.

## Current-Season Scores

- `scripts/cache_current_scores.R` scrapes `ffscrapr::ff_playerscores()` and `ffscrapr::ff_starters()` for the current ADL season, writes raw caches to `C:/Users/Michael/Documents/R/FFAucAndDraft/RawLeagueData`, and rebuilds the app data.
- During the NFL season, the shared worker runs when Monday-night/Tuesday readiness checks confirm preliminary scores.
- Thursday correction checks begin at 3:45 AM Eastern and dispatch official-score refreshes only when player scores change (or a baseline needs establishing).
- Set `ADL_SCORE_WEEK` to force a specific week while testing.

The same workflow then runs `scripts/refresh_playoff_picture.R`, reusing the starter RDS named in `data/score_metadata.csv`. It reads the extra MFL schedule/franchise metadata once, builds 3,000-simulation playoff forecasts, commits `docs/playoff-picture/`, and requests a GitHub Pages build. `data/playoff_picture_metadata.csv` records the score status, completed week, and refresh timestamps. Existing historical reports are preserved; missing weeks are filled in. Completed 2021–2025 training data lives in `data/playoff_history/` so cloud runs do not repeatedly scrape those seasons.

Both days follow America/New_York time across daylight saving changes. Lightweight polling workflows enforce the Eastern-time windows; GitHub can delay scheduled starts. Thursday uses the same completed scoring week as Tuesday, not the upcoming week's games.

The shared weekly worker also synchronizes the Elo and Bonus Games Google Sheets from its validated score source. The daily roster refresh remains a separate workflow; it refreshes rosters without running another weekly score scrape.

## Historical Playoff Model Evaluation

The default historical test trains on **all other completed seasons**, excluding the season being evaluated. The Potential-PPG model is evaluated across **2021–2025**, after Weeks 1–11. Run `Rscript scripts/evaluate_playoff_model.R` or the **Evaluate Historical Playoff Model** GitHub workflow. [Methods and saved results](data/model_evaluation/README.md) include a separately labeled past-only comparison and an explicit list of each fold's training years. This testing convention does not change the live forecast or enable the experimental scoring corrections.

## Commissioner Alerts

Commissioner Alerts have moved to the `ADL-Commissioner-Dashboard` repository, where the public Commissioner Dashboard, alert workflows, report history, salary-cap accounting, and inactivity monitor now live together.

## Salary Snapshots

- End salary curves come from the prior-season `ffscrapr::ff_rosters()` raw cache and exclude future-year contract records.
- ADL25 has a small amendment layer for two mistakenly entered `2026 5YO` records in the 2025 scrape: Breece Hall AFC is corrected to `$11.66m`, and Drake London AFC is corrected to `$9.82m`. The rebuilt amended cache is written to `data/salary_snapshots/ff_rosters_ADL25_2025_amended.rds` and `.csv`.
- Before July 1, iEXT pricing uses the End salary curve plus 10% as an estimate.
- On July 1, run `Rscript scripts/cache_july1_raw_salary_readout.R` to scrape and cache a raw July 1 salary readout. The script writes a review prompt so league-office manual work can be checked before the curve is promoted to final EXT pricing.
- `scripts/validate_adl25_salary_scrape_vs_workbook.R` compares the ADL25 scrape-derived End salary curve against the workbook `End25 Sal` tab and writes `data/salary_curve_validation_adl25_vs_workbook.csv`.

### Preliminary score readiness

The Tuesday 1 a.m. refresh is replaced by `.github/workflows/poll_preliminary_scores.yml`. It checks every 15 minutes from Monday 11:30 p.m. through Tuesday 11:59 p.m. America/New_York, including DST, for scoring weeks 1–17. GitHub may delay scheduled starts. Thursday's fixed 5 a.m. run is replaced by the score-correction poll below.

The lightweight standard-library checker requires 32 unique franchises, expected/balanced head-to-head records through Week 12 (MFL excludes our separate bonus awards), expected/balanced all-play totals through the target week, finished NFL games, and matching-week weekly/player score feeds with lineups and potential points. During Weeks 13–17 it uses advancing all-play totals instead of regular-season H2H records. Missing/ambiguous data waits rather than publishing incomplete results.

A successful check dispatches the existing shared weekly worker with an explicit `ready_week` and unofficial status. In-progress or successful runs with the same league/season/week key suppress duplicate dispatch. Failed runs retry on subsequent checks without an attempt limit. These are complete worker retries, not component-only retries. Outputs are regenerated by the existing replace/update operations.

Only after required components and deployment succeed does the worker commit `data/preliminary_refresh_complete.json`. The Game of the Week chat automation independently watches MFL standings and emits one shortlist per league/week without waiting for GitHub; stale Elo is labeled rather than blocking it. It does not publish to MFL or send email. Its local automation still requires the Codex automation environment to be available.

Manual test: dispatch the polling workflow with `dry_run=true` and a target `week` to inspect readiness without triggering updates. With `dry_run=false`, a ready week dispatches the worker unless already completed. A failed worker can also be rerun manually after resolving its underlying error. Manual refreshes remain available independently.

### Thursday score corrections

`poll_score_corrections.yml` checks every 15 minutes from Thursday 3:45 a.m. through 11:59 p.m. America/New_York (DST-aware), for the same completed scoring week as Tuesday. Scheduled Actions starts may be delayed. It compares every player ID and score, including bench players, with `data/processed_player_scores.json`; response ordering, availability flags, and numeric formatting do not count as corrections. Standings do not need to change.

Unchanged scores do nothing. Changed scores dispatch the shared worker with official status after the player and team feeds reconcile. A running worker suppresses overlapping dispatches. Each new correction or reversion can trigger another refresh; failed workers retry on later checks without a retry cap. A missing baseline causes one full refresh to establish it. The worker captures scores before scraping and only records that baseline after all required components succeed and the scores still match at completion. A mid-run correction leaves the baseline unacknowledged for retry. This replaces the fixed Thursday 5 a.m. run, and does not resend Game of the Week shortlists.

Manual test: dispatch `poll_score_corrections.yml` with `dry_run=true` and `week` set to the completed scoring week. It reports changes without publishing.

### Private weekly completion emails

`email_weekly_completion.yml` requests one combined ADL/FAFL report per completed preliminary-score refresh pair or correction pair. Delivery runs in ADL-Commissioner-Dashboard using its current SMTP secrets and the single recipient in `WEEKLY_REPORT_EMAIL_TO`, with no CC/BCC. The Commissioner workflow checks out this repository's reporting script and tests. Checkers pass their exact dispatch time to the worker. Completion receipts retain that time and the process; the reporter obtains actual job start/end times from GitHub and displays Eastern time, duration, and links. Manually dispatched runs are explicitly labeled and do not invent an MFL trigger time.

Email waits for successful worker completion in both leagues, no active worker, matching run markers on both live GitHub Pages sites, and processed player scores matching MFL. ADL worker success includes the Shiny calculator deployment. If only one league has a Thursday correction, the other's unchanged published scores can satisfy the check. If neither has a correction, there is no new report. An ADL workflow-completion event requests the reporter; a 15-minute catch-up schedule in the Commissioner repository handles FAFL finishing later, delayed site publication, or mail retries. Durable sent-pair records in that repository suppress repeated reports; a later correction receives a new report. Manual `dry_run=true` verifies readiness and previews without sending.

### Payouts in the weekly refresh

Both preliminary and correction runs publish the same validated team-week scores
to the Payouts workbook, replacing its delayed IMPORTRANGE input. Existing award
formulas, prize amounts, manual corrections and layout are preserved. Completed
bracket results fill playoff participants and postseason prizes; projected
results never earn payouts. The script independently reconciles all weekly,
quarterly and season winners, shared prizes, and all 32 payout balances.

Google Sheets API cannot update over-cell logo images. `PayoutsGithubBridge.gs`
is installed in the existing 2026 Elo/Payouts Apps Script project alongside its
approved logo renderer. A five-minute trigger checks Reference!Z10 for a new
authenticated workflow request and acknowledges verified logos in Z11. It does
not scrape MFL or run Elo. GitHub waits for this exact run/source acknowledgement;
a missing bridge or stale result fails the refresh. Install the bridge once with
`installPayoutGithubBridge`; do not re-enable the retired Elo scrape schedules.

Payouts success is recorded in `data/payouts_sync_metadata.json` and required
before completion receipts and owner emails. Failed runs preserve other
successful components but cannot report complete. The original import anchor
and postseason inputs are backed up once in `data/payouts_source_backup.json`.
