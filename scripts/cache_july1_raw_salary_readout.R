library(readr)

source("R/roster_source.R")
source("R/salary_snapshots.R")

season <- get_current_season()
today <- as.Date(Sys.getenv("ADL_GM_TODAY", unset = as.character(Sys.Date())))

if (format(today, "%m-%d") != "07-01" && !identical(Sys.getenv("ADL_ALLOW_NON_JULY1_SCRAPE", unset = "FALSE"), "TRUE")) {
  stop("This raw salary readout is intended for July 1. Set ADL_ALLOW_NON_JULY1_SCRAPE=TRUE to run it manually.")
}

status <- cache_july1_raw_salary_readout(season = season, force_live = TRUE)
print(status)
