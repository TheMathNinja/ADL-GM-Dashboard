library(dplyr)

source("R/commissioner_alerts.R")

arg_value <- function(name, default = NULL) {
  args <- commandArgs(trailingOnly = TRUE)
  prefix <- paste0("--", name, "=")
  matched <- args[startsWith(args, prefix)]
  if (!length(matched)) return(default)
  sub(prefix, "", matched[[1]], fixed = TRUE)
}

arg_flag <- function(name) {
  paste0("--", name) %in% commandArgs(trailingOnly = TRUE)
}

season <- suppressWarnings(as.integer(arg_value("season", Sys.getenv("CURRENT_SEASON", unset = get_current_season()))))
week <- suppressWarnings(as.integer(arg_value("week", Sys.getenv("ADL_ALERT_WEEK", unset = NA_character_))))
mode <- arg_value("mode", Sys.getenv("ADL_ALERT_MODE", unset = "check"))
force_live <- arg_flag("force-live") || tolower(Sys.getenv("ADL_ALERT_FORCE_LIVE", unset = "false")) %in% c("1", "true", "yes")
send_email <- arg_flag("send-email") || tolower(Sys.getenv("ADL_ALERT_SEND_EMAIL", unset = "false")) %in% c("1", "true", "yes")
send_empty <- arg_flag("send-empty") || tolower(Sys.getenv("ADL_ALERT_SEND_EMPTY", unset = "false")) %in% c("1", "true", "yes")
auto_week <- !arg_flag("no-auto-week") && tolower(Sys.getenv("ADL_ALERT_AUTO_WEEK", unset = "true")) %in% c("1", "true", "yes")

if (is.na(season)) stop("Provide a valid --season or CURRENT_SEASON.", call. = FALSE)

current_commissioner_alert_week <- function(today = Sys.Date(), season = get_current_season()) {
  week_one_start <- as.Date(Sys.getenv("ADL_WEEK_ONE_START", unset = paste0(season, "-09-10")))
  if (is.na(week_one_start) || today < week_one_start) return(NA_integer_)
  max(1L, min(17L, floor(as.numeric(today - week_one_start) / 7) + 1L))
}

if (identical(mode, "snapshot")) {
  if (is.na(week)) stop("--week is required for designation snapshots.", call. = FALSE)
  snapshot <- cache_designation_snapshot(season = season, week = week, force_live = TRUE)
  message("Wrote 72-hour designation snapshot with ", nrow(snapshot), " rows.")
  message(commissioner_alert_path("designation_snapshot", season, week))
  quit(save = "no")
}

if (!mode %in% c("check", "offseason", "inseason")) {
  stop("--mode must be one of: snapshot, check, offseason, inseason.", call. = FALSE)
}

if (is.na(week) && mode %in% c("check", "inseason") && auto_week) {
  week <- current_commissioner_alert_week(season = season)
  if (!is.na(week)) message("Auto-selected Week ", week, " for in-season alerts.")
}

include_offseason <- mode %in% c("check", "offseason")
include_inseason <- mode %in% c("check", "inseason") && !is.na(week)

alerts <- build_commissioner_alerts(
  season = season,
  week = if (is.na(week)) NULL else week,
  include_offseason = include_offseason,
  include_inseason = include_inseason,
  force_live = force_live
)

alerts_path <- commissioner_alert_path("alerts", season, if (is.na(week)) NULL else week)
message("Wrote ", nrow(alerts), " commissioner alert row(s).")
message(alerts_path)

if (send_email) {
  email_status <- send_commissioner_alert_email(
    alerts,
    season = season,
    week = if (is.na(week)) NULL else week,
    send_empty = send_empty
  )
  message("Email status: ", email_status$reason[[1]])
  message("Outbox: ", email_status$outbox_path[[1]])
  if (!isTRUE(email_status$sent[[1]]) && !identical(email_status$reason[[1]], "no_alerts")) {
    stop("Commissioner alert email was requested but not sent: ", email_status$reason[[1]], call. = FALSE)
  }
}
