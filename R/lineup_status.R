# Production-only availability predictor. Official potential points never change.
prepare_lineup_status <- function(metadata) {
  season <- as.integer(metadata$season); week <- min(as.integer(metadata$week), 12L)
  if (season < 2026L) return(invisible(NULL))
  source("R/roster_source.R")
  conn <- connect_adl_mfl(season)
  cache <- file.path(dirname(metadata$starters_path), "lineup_status", season)
  dir.create(cache, recursive = TRUE, showWarnings = FALSE)
  endpoint <- function(type, filename, ..., refresh = FALSE) {
    path <- file.path(cache, filename)
    if (!file.exists(path) || refresh) {
      if (type %in% c("injuries", "nflSchedule")) {
        # These global feeds reject requests to a league's numbered MFL server.
        response <- httr::RETRY("GET", sprintf("https://api.myfantasyleague.com/%d/export", season),
          query = c(list(TYPE = type, JSON = 1), list(...)), httr::timeout(60),
          httr::user_agent("ADL-GM-Dashboard"), times = 3, pause_min = 5)
        httr::stop_for_status(response)
        content <- jsonlite::fromJSON(httr::content(response, "text", encoding = "UTF-8"), simplifyVector = FALSE)
        Sys.sleep(2)
      } else content <- ffscrapr::mfl_getendpoint(conn, type, ...)$content
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
    projections = setNames(lapply(seq_len(week), function(w)
      endpoint("projectedScores", sprintf("projections_%02d.json", w), W = w)), as.character(seq_len(week))),
    scores = readRDS(metadata$scores_path), starters = readRDS(metadata$starters_path),
    rosters = dplyr::bind_rows(rosters))
  path <- file.path(cache, "inputs.json")
  jsonlite::write_json(inputs, path, dataframe = "rows", auto_unbox = TRUE, null = "null", na = "null", digits = NA)
  python <- Sys.getenv("ADL_PYTHON", "python3")
  dest <- file.path("data", sprintf("lineup_status_credits_%d.csv", season))
  result <- system2(python, c("scripts/lineup_status.py", "--input", shQuote(path), "--output", shQuote(dest)))
  if (result != 0L) stop("Availability lineup calculation failed")
  result <- system2(python, c("scripts/adjusted_actual.py", "--input", shQuote(path),
                            "--output", "data/adjusted_actual_weekly.csv"))
  if (result != 0L) stop("Adjusted actual lineup calculation failed")
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
  adjusted <- read.csv("data/adjusted_actual_weekly.csv", colClasses=c(franchise_id="character"))
  adjusted <- aggregate(adjusted_pf ~ franchise_id, adjusted[adjusted$season==season & adjusted$week<=week,], mean)
  teams$rem_mean_hat <- adl_eb_scoring_mean(teams$adjusted_potential_ppg, teams$avg_pf, week, season,
                                         adjusted_ppg=adjusted$adjusted_pf[match(ids,adjusted$franchise_id)])
  teams$mu_pts <- pmax(0, teams$rem_mean_hat)
  teams$rem_potential_hat <- params$potential_intercept +
    params$potential_slope * teams$adjusted_potential_ppg
  teams$potential_mu_pts <- pmax(teams$mu_pts, teams$rem_potential_hat, 0)
  stopifnot(all(is.finite(teams$mu_pts)), all(is.finite(teams$potential_mu_pts)),
            all(teams$lineup_credit_ppg >= 0))
  message("Using ", model$version, "; taper k=", model$k)
  teams
}

# Keep relative team scoring advantages, anchor the league to observed YTD PF.
adl_observed_league_level <- function(mu, observed_ppg) {
  stopifnot(length(mu) == length(observed_ppg), length(mu) > 0L,
            all(is.finite(mu)), all(is.finite(observed_ppg)))
  mu - mean(mu) + mean(observed_ppg)
}

# Compatibility mean accessor uses the same unified model as the Python simulation.
adl_eb_scoring_mean <- function(adjusted_potential, observed_ppg, week, season,
                                model = jsonlite::read_json("data/adl_scoring_model.json", simplifyVector = TRUE)[[as.character(season)]],
                                adjusted_ppg = NULL) {
  stopifnot(length(adjusted_potential)==length(observed_ppg), all(is.finite(adjusted_potential)),
            all(is.finite(observed_ppg)), week>=1L, week<12L,
            as.integer(season)==as.integer(model$forecast_season),max(model$training_years)<season)
  stopifnot(length(adjusted_ppg)==length(observed_ppg),all(is.finite(adjusted_ppg)))
  d <- model$input_latent + model$input_measurement/week
  x <- .85*adjusted_potential + .15*adjusted_ppg
  mean(observed_ppg) + model$cross/d*(x-mean(x))
}
