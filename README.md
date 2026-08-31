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

Commissioner Alerts have moved to the `ADL-Commissioner-Dashboard` repository, where the public Commissioner Dashboard, alert workflows, report history, salary-cap accounting, and inactivity monitor now live together.

## Salary Snapshots

- End salary curves come from the prior-season `ffscrapr::ff_rosters()` raw cache and exclude future-year contract records.
- ADL25 has a small amendment layer for two mistakenly entered `2026 5YO` records in the 2025 scrape: Breece Hall AFC is corrected to `$11.66m`, and Drake London AFC is corrected to `$9.82m`. The rebuilt amended cache is written to `data/salary_snapshots/ff_rosters_ADL25_2025_amended.rds` and `.csv`.
- Before July 1, iEXT pricing uses the End salary curve plus 10% as an estimate.
- On July 1, run `Rscript scripts/cache_july1_raw_salary_readout.R` to scrape and cache a raw July 1 salary readout. The script writes a review prompt so league-office manual work can be checked before the curve is promoted to final EXT pricing.
- `scripts/validate_adl25_salary_scrape_vs_workbook.R` compares the ADL25 scrape-derived End salary curve against the workbook `End25 Sal` tab and writes `data/salary_curve_validation_adl25_vs_workbook.csv`.
