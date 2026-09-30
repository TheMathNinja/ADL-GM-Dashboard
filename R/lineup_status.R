# Production-only availability predictor. Official potential points never change.
prepare_lineup_status <- function(metadata) {
  season <- as.integer(metadata$season); week <- min(as.integer(metadata$week), 11L)
  if (season < 2026L || as.integer(metadata$week) >= 12L) return(invisible(NULL))
  source("R/roster_source.R")
  conn <- connect_adl_mfl(season)
  cache <- file.path(dirname(metadata$starters_path), "lineup_status", season)
  dir.create(cache, recursive = TRUE, showWarnings = FALSE)
  endpoint <- function(type, filename, ..., refresh = FALSE) {
    path <- file.path(cache, filename)
    if (!file.exists(path) || refresh) {
      content <- ffscrapr::mfl_getendpoint(conn, type, ...)$content
      if (type == "injuries" && !length(content$injuries$injury)) stop("Empty MFL injury report: ", filename)
      jsonlite::write_json(content, path, auto_unbox = TRUE, null = "null", digits = NA)
    }
    jsonlite::read_json(path, simplifyVector = FALSE)
  }
  injuries <- setNames(lapply(seq_len(week), function(w)
    endpoint("injuries", sprintf("injuries_%02d.json", w), W = w, refresh = w == week)), as.character(seq_len(week)))
  rosters <- lapply(seq_len(week), function(w) {
    path <- file.path(cache, sprintf("rosters_%02d.rds", w))
    if (!file.exists(path)) saveRDS(ffscrapr::ff_rosters(conn, week = w), path)
    x <- readRDS(path); x$week <- w; x
  })
  inputs <- list(season = season, week = week, injuries = injuries,
    rules = endpoint("league", "league.json"), schedule = endpoint("nflSchedule", "schedule.json", W = "ALL"),
    scores = readRDS(metadata$scores_path), starters = readRDS(metadata$starters_path),
    rosters = dplyr::bind_rows(rosters))
  path <- file.path(cache, "inputs.json")
  jsonlite::write_json(inputs, path, dataframe = "rows", auto_unbox = TRUE, null = "null", na = "null", digits = NA)
  python <- Sys.getenv("ADL_PYTHON", "python3")
  dest <- file.path("data", sprintf("lineup_status_credits_%d.csv", season))
  result <- system2(python, c("scripts/lineup_status.py", "--input", shQuote(path), "--output", shQuote(dest)))
  if (result != 0L) stop("Availability lineup calculation failed")
  invisible(dest)
}

apply_lineup_status <- function(teams, season, week) {
  if (season < 2026L || week >= 12L) return(teams)
  model <- jsonlite::read_json("data/lineup_status_model.json", simplifyVector = TRUE)
  params <- model$weeks[[as.character(week)]]
  if (is.null(params)) stop("Missing fitted lineup regression for week ", week)
  credits <- read.csv(sprintf("data/lineup_status_credits_%d.csv", season), colClasses = c(franchise_id = "character"))
  credits <- credits[credits$week == week & credits$season == season, ]
  ids <- sprintf("%04d", as.integer(teams$franchise_id))
  stopifnot(nrow(credits) == 32L, !anyDuplicated(credits$franchise_id), all(credits$model_version == model$version))
  ix <- match(ids, credits$franchise_id)
  if (anyNA(ix)) stop("Missing team in lineup credits")
  teams$lineup_credit_ppg <- credits$lineup_credit_ppg[ix]
  teams$adjusted_potential_ppg <- teams$avg_pot + teams$lineup_credit_ppg
  teams$rem_mean_hat <- params$intercept + params$slope * teams$adjusted_potential_ppg
  teams$mu_pts <- pmax(0, teams$rem_mean_hat)
  stopifnot(all(is.finite(teams$mu_pts)), all(teams$lineup_credit_ppg >= 0))
  message("Using ", model$version, "; taper k=", model$k)
  teams
}
