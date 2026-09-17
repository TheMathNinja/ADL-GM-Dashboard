# ADL calendar rule: UFA opens on the third Monday in June at noon Eastern.
# Keep this portable helper identical in the GM/Commissioner dashboards and
# LeagueFeatures/CompensatoryPicks; never substitute a fixed June date.
adl_ufa_start <- function(season) {
  stopifnot(length(season) == 1L, !is.na(season), season == as.integer(season))
  first <- as.Date(sprintf("%04d-06-01", as.integer(season)))
  third_monday <- first + ((1L - as.POSIXlt(first)$wday) %% 7L) + 14L
  as.POSIXct(paste(third_monday, "12:00:00"), tz = "America/New_York")
}

adl_apply_ufa_calendar <- function(config, season) {
  ufa <- config$event_type %in% c("ufa_auction", "ufa_auction_first_three_days")
  config$start_at[ufa] <- format(adl_ufa_start(season), "%Y-%m-%d %H:%M:%S", tz = "America/New_York")
  first_three <- config$event_type == "ufa_auction_first_three_days"
  config$end_at[first_three] <- format(adl_ufa_start(season) + 3 * 86400,
    "%Y-%m-%d %H:%M:%S", tz = "America/New_York")
  config
}
