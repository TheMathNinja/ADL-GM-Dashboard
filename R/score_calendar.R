# The Tuesday after kickoff starts each completed scoring week. Thursday's
# corrections still belong to that same week, even though the next game is due.
first_score_tuesday <- function(season) {
  september <- as.Date(sprintf("%d-09-01", season))
  first_monday <- september + (1L - as.POSIXlt(september)$wday + 7L) %% 7L
  first_monday + 8L
}

completed_score_week <- function(today, season) {
  max(0L, min(17L, as.integer(floor(as.numeric(as.Date(today) - first_score_tuesday(season)) / 7)) + 1L))
}
