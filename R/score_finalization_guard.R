latest_finalizable_score_week <- function(now = Sys.time(), season) {
  local_date <- as.Date(format(now, tz = "America/New_York", format = "%Y-%m-%d"))
  first_thursday <- first_score_tuesday(season) + 2L
  eligible <- as.integer(floor(as.numeric(local_date - first_thursday) / 7L)) + 1L
  if (as.POSIXlt(local_date)$wday == 4L &&
      as.integer(format(now, tz = "America/New_York", format = "%H")) < 5L) eligible <- eligible - 1L
  max(0L, min(17L, eligible))
}

confirmed_score_status <- function(status, week, now = Sys.time(), season) {
  if (identical(status, "official") && week > latest_finalizable_score_week(now, season)) {
    message("Official administrative run: current player scores remain preliminary until the Thursday scrape.")
    return("unofficial")
  }
  status
}
