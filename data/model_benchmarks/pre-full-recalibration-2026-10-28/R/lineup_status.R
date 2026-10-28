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
  # Current ownership is deliberately fetched on every preliminary/correction run.
  current_rosters <- ffscrapr::ff_rosters(conn)
  stopifnot(nrow(current_rosters)>0L,dplyr::n_distinct(current_rosters$franchise_id)==32L)
  current_rosters$week <- week
  nfl_rosters <- nflreadr::load_rosters_weekly(seasons = season)
  forecast_injuries <- tryCatch(endpoint("injuries", sprintf("forecast_injuries_%02d.json", week+1L),
                                           W=week+1L, refresh=TRUE), error=function(e) {
    message("Forecast-week injury report unavailable: ", conditionMessage(e)); NULL
  })
  inputs <- list(season = season, week = week, injuries = injuries,
    current_rosters = current_rosters, nfl_rosters = nfl_rosters,
    current_rosters_fetched_at = format(Sys.time(),tz="UTC",usetz=TRUE),
    forecast_injuries = forecast_injuries,
    rules = endpoint("league", "league.json"), schedule = endpoint("nflSchedule", "schedule.json", W = "ALL"),
    projections = setNames(lapply(seq_len(min(week+1L,17L)), function(w)
      endpoint("projectedScores", sprintf("projections_%02d.json", w), W = w, refresh = w > week)), as.character(seq_len(min(week+1L,17L)))),
    scores = readRDS(metadata$scores_path), starters = readRDS(metadata$starters_path),
    rosters = dplyr::bind_rows(rosters))
  path <- file.path(cache, "inputs.json")
  jsonlite::write_json(inputs, path, dataframe = "rows", auto_unbox = TRUE, null = "null", na = "null", digits = NA)
  python <- Sys.getenv("ADL_PYTHON", Sys.getenv("BONUS_PYTHON", Sys.which("python3")))
  python_root <- Sys.getenv("Python_ROOT_DIR", Sys.getenv("pythonLocation"))
  child_env <- character()
  if (.Platform$OS.type != "windows" && nzchar(python_root)) {
    child_env <- c(paste0("PYTHONHOME=",shQuote(python_root)),
                   paste0("LD_LIBRARY_PATH=",shQuote(file.path(python_root,"lib"))))
  }
  run_python <- function(args) system2(python,args,env=child_env)
  dest <- file.path("data", sprintf("lineup_status_credits_%d.csv", season))
  result <- run_python(c("scripts/lineup_status.py", "--input", shQuote(path), "--output", shQuote(dest)))
  if (result != 0L) stop("Availability lineup calculation failed")
  result <- run_python(c("scripts/adjusted_actual.py", "--input", shQuote(path),
                            "--output", "data/adjusted_actual_weekly.csv"))
  if (result != 0L) stop("Adjusted actual lineup calculation failed")
  result <- run_python(c("scripts/refresh_player_strength_inputs.py", "--input", shQuote(path)))
  if (result != 0L) stop("Fresh player/roster inputs failed; refusing a stale forecast")
  result <- run_python(c("scripts/player_team_strength.py", "--season", season, "--week", week))
  if (result != 0L) stop("Player-based Starter/Roster forecasts failed")
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
                                         adjusted_ppg=adjusted$adjusted_pf[match(ids,adjusted$franchise_id)], team_ids=ids)
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
                                model = jsonlite::read_json("data/adl_scoring_model.json", simplifyVector=TRUE)[[as.character(season)]],
                                adjusted_ppg = NULL, team_ids = NULL) {
  stopifnot(length(adjusted_potential)==length(observed_ppg), all(is.finite(adjusted_potential)),
            all(is.finite(observed_ppg)), week>=1L, week<12L,
            as.integer(season)==as.integer(model$forecast_season),max(model$training_years)<season,
            model$version=="adl-player-blend-35-0-55-10-weekly-sharks-nig-v4")
  x <- read.csv(sprintf("data/player_team_outlooks_%d.csv",season),colClasses=c(franchise_id="character"))
  x <- x[x$week==week,]
  if(is.null(team_ids)) team_ids <- sprintf("%04d",seq_along(observed_ppg))
  ix <- match(sprintf("%04d",as.integer(team_ids)),x$franchise_id)
  stopifnot(nrow(x)==32L,!anyNA(ix),all(is.finite(x$forecast_mean[ix])))
  # Use the shared Python forecast, with the same 35/0/55/10 mean and posterior.
  x$forecast_mean[ix] - mean(x$forecast_mean[ix]) + mean(observed_ppg)
}
