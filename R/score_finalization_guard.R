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

ext_update_pending_message <- function(metadata, now = Sys.time(), season) {
  date <- as.Date(format(now, tz = "America/New_York", format = "%Y-%m-%d"))
  expected <- completed_score_week(date, season)
  if (expected < 1L) return(NULL)
  if (is.null(metadata)) return("Score publication could not be verified.")
  if (metadata$week < expected) return(paste0("Week ", expected, " rank update pending; showing Week ", metadata$week, "."))
  if (metadata$official_week < latest_finalizable_score_week(now, season)) {
    return(paste0("Official Week ", latest_finalizable_score_week(now, season), " update pending; published status unchanged."))
  }
  NULL
}
