#!/usr/bin/env Rscript

# Build the single validated ADL team-week snapshot and the comparison-only
# Elo result. This stage contains no EXT, playoff, or Bonus Games publishing.
source("scripts/get_adl_playoff_picture.R")
source("R/weekly_system.R")

metadata <- read.csv("data/score_metadata.csv", stringsAsFactors = FALSE)
if (nrow(metadata) != 1L || !all(c("season", "week", "status", "refreshed_at") %in% names(metadata))) {
  stop("Missing or invalid score metadata.")
}
season <- as.integer(metadata$season[[1]])
through_week <- as.integer(metadata$week[[1]])
if (!is.finite(season) || !is.finite(through_week) || through_week < 1L || through_week > 17L) {
  stop("Invalid season or completed week in score metadata.")
}

team_weeks <- build_adl_team_week_data(season, through_week)
shadow <- calculate_adl_elo(team_weeks, season)
if (nrow(shadow) != 32L * (through_week + 1L) || any(!is.finite(shadow$elo))) {
  stop("Internal Elo comparison output is incomplete.")
}

readr::write_csv(team_weeks, "data/weekly_team_metrics.csv", na = "")
readr::write_csv(shadow, "data/elo_shadow_ratings.csv", na = "")
readr::write_csv(
  data.frame(
    season = season,
    through_week = through_week,
    status = metadata$status[[1]],
    source_rows = nrow(team_weeks),
    source_refreshed_at = metadata$refreshed_at[[1]],
    validated_at = format(Sys.time(), tz = "UTC", usetz = TRUE)
  ),
  "data/weekly_source_metadata.csv",
  na = ""
)

message("Validated one ADL MFL snapshot through Week ", through_week, ".")
