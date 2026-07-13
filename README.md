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
- During the NFL season, run it Tuesdays at 5:00 AM Eastern with `ADL_SCORE_STATUS=unofficial`.
- Run it again Thursdays at 5:00 AM Eastern with `ADL_SCORE_STATUS=official`, when weekly stats are treated as finalized.
- Set `ADL_SCORE_WEEK` to force a specific week while testing.

## Commissioner Alerts

- `R/commissioner_alerts.R` checks roster cap, contract years, salary cap, and illegal lineup rules.
- Offseason checks:
  - Active Roster must have at least 40 players.
  - Active Roster + Taxi Squad must have no more than 75 players.
  - Active Roster contract years must not exceed 120.
  - Before July 1, Top 43 Active Roster salaries plus MFL salary cap adjustments must be at or below the franchise salary cap.
  - On and after July 1, Top 43 salaries across all roster statuses plus MFL salary cap adjustments must be at or below the franchise salary cap.
  - Players with MFL `SUSPENDED` roster status are excluded from the salary cap Top 43 pool.
- In-season checks:
  - Each submitted lineup must contain exactly 21 starters.
  - Starters cannot have `(I)`, `(S)`, or `I` designations from the 72-hour pre-kickoff snapshot.
  - Starters cannot be on an NFL bye week.
- Capture the 72-hour designation evidence before games:

```r
Rscript scripts/run_commissioner_alerts.R --mode=snapshot --season=2026 --week=1
```

- Check alerts and write the alert CSV/outbox email body:

```r
Rscript scripts/run_commissioner_alerts.R --mode=check --season=2026 --week=1
```

- Send email by adding `--send-email` and configuring `ADL_ALERT_EMAIL_FROM`, `ADL_SMTP_SERVER`, and optionally `ADL_SMTP_USERNAME`, `ADL_SMTP_PASSWORD`, `ADL_SMTP_SSL`.
- When violations exist, the system sends two kinds of messages:
  - one digest email to the commissioner group, summarizing all violations found that day
  - one private email to each offending GM, limited to that franchise's violations
- By default, digest recipients are the MFL emails found for `CHI`, `KCC`, `IND`, and `SEA`. Override that franchise list with `ADL_ALERT_DIGEST_FRANCHISES`, or use `ADL_ALERT_EMAIL_TO` as a fallback if MFL recipient lookup fails.
- Private GM emails use the offending franchise's MFL email. NFC notices CC Carson Witte via `ADL_ALERT_NFC_CC`, defaulting to `wittecarson@gmail.com`; AFC notices CC Andrew Mast via `ADL_ALERT_AFC_CC`, defaulting to `andrewrmast@gmail.com`.
- For Gmail SMTP, create the sender Gmail account, enable 2-Step Verification, create an app password, then set `ADL_ALERT_EMAIL_FROM` and `ADL_SMTP_USERNAME` to that Gmail address, `ADL_SMTP_PASSWORD` to the app password, `ADL_SMTP_SERVER` to `smtp://smtp.gmail.com:587`, and `ADL_SMTP_SSL` to `try`.
- Alert CSVs, resolved recipient CSVs, and email outbox text files are written under `data/commissioner_alerts/`.
- Public violation summaries are written under `data/commissioner_alert_reports/` and committed by the daily workflow so the dashboard can show past reports.
- `.github/workflows/daily-commissioner-alerts.yml` runs the alert check daily at `11:15 UTC` (`7:15 AM Eastern` during daylight saving time) and can also be run manually from GitHub Actions.
- The daily workflow needs these GitHub secrets to send live alerts: `MFL_USERNAME`, `MFL_PASSWORD`, `ADL_ALERT_EMAIL_FROM`, `ADL_SMTP_SERVER`, and usually `ADL_SMTP_USERNAME`, `ADL_SMTP_PASSWORD`, `ADL_SMTP_SSL`. Optional secrets are `ADL_LEAGUE_ID`, `MFL_USER_AGENT`, fallback `ADL_ALERT_EMAIL_TO`, `ADL_ALERT_DIGEST_FRANCHISES`, `ADL_ALERT_NFC_CC`, and `ADL_ALERT_AFC_CC`.

## Salary Snapshots

- End salary curves come from the prior-season `ffscrapr::ff_rosters()` raw cache and exclude future-year contract records.
- ADL25 has a small amendment layer for two mistakenly entered `2026 5YO` records in the 2025 scrape: Breece Hall AFC is corrected to `$11.66m`, and Drake London AFC is corrected to `$9.82m`. The rebuilt amended cache is written to `data/salary_snapshots/ff_rosters_ADL25_2025_amended.rds` and `.csv`.
- Before July 1, iEXT pricing uses the End salary curve plus 10% as an estimate.
- On July 1, run `Rscript scripts/cache_july1_raw_salary_readout.R` to scrape and cache a raw July 1 salary readout. The script writes a review prompt so league-office manual work can be checked before the curve is promoted to final EXT pricing.
- `scripts/validate_adl25_salary_scrape_vs_workbook.R` compares the ADL25 scrape-derived End salary curve against the workbook `End25 Sal` tab and writes `data/salary_curve_validation_adl25_vs_workbook.csv`.
