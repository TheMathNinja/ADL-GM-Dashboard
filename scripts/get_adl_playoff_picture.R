## This function gets ADL Playoff picture and Projected Draft Order 
## given season and (completed) week inputs

library(gt)
library(glue)
library(ffscrapr)
library(dplyr)
library(tidyr)
library(purrr)
library(ggplot2)
library(stringr)
library(tibble)

# Public ADL data needs no local credential file. Connections are created on demand.
mfl_conns <- list()
adl_fetch_cache <- new.env(parent = emptyenv())
adl_output_dir <- function() getOption("adl.output_dir", file.path("docs", "playoff-picture"))
adl_connection <- function(season) {
  key <- paste0("ADL", substr(as.character(season), 3, 4))
  if (is.null(mfl_conns[[key]])) {
    mfl_conns[[key]] <<- ffscrapr::mfl_connect(
      season = season, league_id = "60206", user_agent = "adl-playoff-picture",
      rate_limit_number = 3, rate_limit_seconds = 6
    )
  }
  mfl_conns[[key]]
}
# Read only the schedule fields this report uses. ffscrapr 1.4.8's schedule
# parser errors on R 4.5 when MFL includes spreads for unplayed games.
adl_schedule <- function(conn) {
  weeks <- ffscrapr::mfl_getendpoint(conn, "schedule")$content$schedule$weeklySchedule
  purrr::map_dfr(weeks, function(w) {
    games <- w$matchup
    if (!is.null(games$franchise)) games <- list(games)
    purrr::map_dfr(games, function(game) {
      teams <- game$franchise
      if (length(teams) != 2L) stop("Expected two teams per ADL matchup.")
      purrr::map_dfr(1:2, function(i) {
        team <- teams[[i]]
        opponent <- teams[[3L - i]]
        tibble::tibble(
          week = as.integer(w$week), franchise_id = team$id,
          opponent_id = opponent$id,
          franchise_score = as.numeric(team$score %||% NA_character_),
          opponent_score = as.numeric(opponent$score %||% NA_character_),
          result = team$result %||% NA_character_
        )
      })
    })
  })
}
adl_fetch <- function(kind, conn, week = seq_len(adl_max_week)) {
  key <- paste(conn$season, kind, paste(week, collapse = ","), sep = "_")
  if (!exists(key, envir = adl_fetch_cache, inherits = FALSE)) {
    shared <- getOption("adl.shared_starters")
    if (kind == "starters" && !is.null(shared) && conn$season == shared$season) {
      value <- readRDS(shared$path)
      required <- c("season", "week", "franchise_id", "starter_status", "player_score", "should_start", "pos")
      if (!all(required %in% names(value)) || anyNA(value$season) ||
          any(value$season != conn$season) || !all(week %in% value$week)) {
        stop("Shared starter cache is incomplete or belongs to another season.")
      }
      message("Reusing the score job's starter cache for ", conn$season, ".")
      value <- dplyr::filter(value, .data$week %in% .env$week)
      assign(key, value, envir = adl_fetch_cache)
      return(value)
    }
    value <- switch(kind,
      schedule = adl_schedule(conn),
      starters = ffscrapr::ff_starters(conn, week = week),
      franchises = ffscrapr::ff_franchises(conn))
    assign(key, value, envir = adl_fetch_cache)
  }
  get(key, envir = adl_fetch_cache, inherits = FALSE)
}

# Global constant: ADL regular season ends after 12 weeks
adl_max_week <- 12L

###############################################
## HELPER: Fast all-play from weekly scores  ##
###############################################
allplay_from_scores <- function(scores) {
  # scores: numeric vector of length n (points for all teams in a week)
  n <- length(scores)
  if (n <= 1L) return(rep(0, n))
  
  # Sort ascending
  o <- order(scores)
  s <- scores[o]
  
  # Run-length encode to find ties
  r <- rle(s)
  m <- r$lengths          # lengths of equal-score runs
  k <- length(m)
  
  # starting index of each run in the sorted vector
  starts    <- cumsum(c(1L, head(m, -1L)))
  # number of elements strictly less than the run
  less_than <- cumsum(c(0L, head(m, -1L)))
  
  ap_sorted <- numeric(n)
  for (j in seq_len(k)) {
    idx <- starts[j]:(starts[j] + m[j] - 1L)
    L   <- less_than[j]
    T   <- m[j]
    # AP wins formula: lower scores + 0.5 * (ties - 1)
    ap_sorted[idx] <- L + 0.5 * (T - 1L)
  }
  
  # unsort back to original order
  ap <- numeric(n)
  ap[o] <- ap_sorted
  ap
}

########################################################
## HELPER: Bonus wins from segment AP + points        ##
########################################################
bonus_from_segment <- function(ap_seg, pts_seg) {
  # ap_seg : numeric vector of segment AP wins
  # pts_seg: numeric vector of segment total points (tie-breaker)
  n <- length(ap_seg)
  if (length(pts_seg) != n) {
    stop("ap_seg and pts_seg must have the same length")
  }
  
  # Rank primarily by segment AP, secondarily by segment points
  ord <- order(ap_seg, pts_seg, decreasing = TRUE)
  ranks <- integer(n)
  ranks[ord] <- seq_len(n)
  
  res <- numeric(n)
  # Top 15: bonus win (1)
  res[ranks <= 15L] <- 1
  # 16–17: bonus tie (0.5)
  res[ranks > 15L & ranks <= 17L] <- 0.5
  # 18–32: bonus loss (0)
  res
}



# ============================================================
# FUNCTION: get_adl_paths()
#
# Purpose in workflow:
#   Centralizes all file paths used in the ADL playoff / modeling
#   pipeline (history caches, rating history, model comparison
#   outputs, etc.) so you have one place to change directories
#   and one object to pass around.
# ============================================================

get_adl_paths <- function(
    base_dir = adl_output_dir()
) {
  if (!dir.exists(base_dir)) dir.create(base_dir, recursive = TRUE)
  
  list(
    base_dir              = base_dir,
    history_completed     = file.path(base_dir, "ADL_weekly_history_completed.rds"),
    rating_hist_completed = file.path(base_dir, "rating_hist_completed.rds"),
    ap_model_comparison   = file.path(base_dir, "ap_model_comparison.rds"),
    h2h_model_comparison  = file.path(base_dir, "h2h_model_comparison.rds"),
    # current-season history cache, one file per season:
    history_current = function(season) {
      file.path(base_dir, paste0("ADL_weekly_history_", season, ".rds"))
    }
  )
}


# ============================================================
# FUNCTION: build_adl_weekly_primitives()
#
# Purpose in workflow:
#   For a given season, builds the *weekly primitives* that all
#   downstream modeling uses:
#     - weekly points for
#     - weekly potential points
#     - weekly H2H W/L/T counts
#     - weekly all-play wins (APW)
#     - NEW: weekly offense / defense / special teams / bench splits:
#         * offense_points_week        (QB, RB, WR, TE)
#         * defense_points_week        (DT, DE, LB, CB, S)
#         * specialteams_points_week   (PK, PN)
#         * bench_points_week          (starter_status == "nonstarter")
#         * offst_points_week = offense + special teams
#
#   Output: one row per (season, week, team) with only the
#   minimal fields needed to later derive:
#     - cumulative standings
#     - APW prediction models
#     - Monte Carlo simulations, etc.
# ============================================================

build_adl_weekly_primitives <- function(season, max_week = adl_max_week) {
  
  # Derive connection name for this season (e.g., "ADL25")
  season_suffix <- substr(as.character(season), 3, 4)  # 2025 -> "25"
  conn_name     <- paste0("ADL", season_suffix)        # "ADL25"
  
  mfl_conn <- adl_connection(season)
  if (is.null(mfl_conn)) {
    stop("No MFL connection named ", conn_name, " found in load_mfl_conns().")
  }
  
  max_week <- min(max_week, adl_max_week)
  
  # 1. Franchises (metadata only) --------------------------------------
  franchises <- adl_fetch("franchises", mfl_conn) %>%
    dplyr::select(
      franchise_id,
      dplyr::any_of(c("franchise_name", "name", "division", "conference"))
    )
  
  # 2. Schedule (weekly H2H + points_for_week) -------------------------
  sched <- adl_fetch("schedule", mfl_conn) %>%
    dplyr::filter(week <= max_week) %>%
    dplyr::select(
      week, franchise_id, opponent_id,
      franchise_score, opponent_score, result
    )
  
  h2h_weekly <- sched %>%
    dplyr::group_by(franchise_id, week) %>%
    dplyr::summarise(
      h2h_wins_week_raw   = sum(franchise_score > opponent_score, na.rm = TRUE),
      h2h_ties_week_raw   = sum(franchise_score == opponent_score, na.rm = TRUE),
      h2h_losses_week_raw = sum(franchise_score < opponent_score, na.rm = TRUE),
      points_for_week     = sum(franchise_score, na.rm = TRUE),
      .groups = "drop"
    )
  
  # 3. Starters -> potential_points_week + O/D/ST/bench splits ---------
  starters <- adl_fetch("starters", mfl_conn, week = seq_len(max_week)) %>%
    dplyr::filter(week <= max_week)
  
  weekly_pts_cats <- starters %>%
    dplyr::group_by(franchise_id, week) %>%
    dplyr::summarise(
      actual_from_starters  = sum(
        player_score[starter_status == "starter"],
        na.rm = TRUE
      ),
      potential_points_week = sum(
        player_score[should_start == 1],
        na.rm = TRUE
      ),
      
      offense_points_week = sum(
        player_score[
          starter_status == "starter" &
            pos %in% c("QB", "RB", "WR", "TE")
        ],
        na.rm = TRUE
      ),
      
      defense_points_week = sum(
        player_score[
          starter_status == "starter" &
            pos %in% c("DT", "DE", "LB", "CB", "S")
        ],
        na.rm = TRUE
      ),
      
      specialteams_points_week = sum(
        player_score[
          starter_status == "starter" &
            pos %in% c("PK", "PN")
        ],
        na.rm = TRUE
      ),
      
      bench_points_week = sum(
        player_score[starter_status == "nonstarter"],
        na.rm = TRUE
      ),
      
      offst_points_week = offense_points_week + specialteams_points_week,
      
      .groups = "drop"
    )
  
  weekly_scores <- h2h_weekly %>%
    dplyr::left_join(weekly_pts_cats, by = c("franchise_id", "week"))
  
  # Optional sanity check: starter totals vs schedule totals -----------
  mismatch <- weekly_scores %>%
    dplyr::filter(
      !is.na(actual_from_starters),
      abs(points_for_week - actual_from_starters) > 0.01
    ) %>%
    dplyr::left_join(franchises, by = "franchise_id")
  
  if (nrow(mismatch) > 0) {
    team_labels <- if ("franchise_name" %in% names(mismatch)) {
      paste0(
        "week ", mismatch$week,
        " – franchise_id ", mismatch$franchise_id,
        " (", mismatch$franchise_name, ")"
      )
    } else {
      paste0("week ", mismatch$week, " – franchise_id ", mismatch$franchise_id)
    }
    
    warning(
      "Starter-based points differ from ff_schedule points for ",
      nrow(mismatch), " team-week rows: ",
      paste(team_labels, collapse = "; ")
    )
  }
  
  # 4. Weekly all-play wins (fast, rank-based) -------------------------
  n_teams <- weekly_scores %>%
    dplyr::summarise(n_teams = dplyr::n_distinct(franchise_id)) %>%
    dplyr::pull(n_teams)
  
  if (n_teams != 32L) {
    warning("Expected 32 teams, found ", n_teams,
            ". All-play logic assumes 32-team ADL.")
  }
  
  allplay_weekly <- weekly_scores %>%
    dplyr::group_by(week) %>%
    dplyr::group_modify(~ {
      tibble::tibble(
        franchise_id = .x$franchise_id,
        ap_wins_week = allplay_from_scores(.x$points_for_week)
      )
    }) %>%
    dplyr::ungroup()
  
  weekly_scores %>%
    dplyr::left_join(allplay_weekly, by = c("franchise_id", "week")) %>%
    dplyr::left_join(franchises,      by = "franchise_id") %>%
    dplyr::mutate(season = !!season, .before = 1L) %>%
    dplyr::select(
      season,
      week,
      franchise_id,
      franchise_name,
      division,
      conference,
      
      # Weekly primitives
      points_for_week,
      potential_points_week,
      offense_points_week,
      defense_points_week,
      specialteams_points_week,
      bench_points_week,
      offst_points_week,
      h2h_wins_week_raw,
      h2h_ties_week_raw,
      h2h_losses_week_raw,
      ap_wins_week,
      
      # Raw starter-based check column if you ever want it
      actual_from_starters
    )
}



# ============================================================
# FUNCTION: build_adl_weekly_history()
#
# Purpose in workflow:
#   Uses build_adl_weekly_primitives() across one or more seasons
#   and adds all *cumulative* fields needed for:
#     - APW regression models
#     - H2H logistic models
#     - Monte Carlo modeling of bonus games, etc.
#
#   Output: one row per (season, week, team) with:
#     - weekly primitives (points_for_week, ap_wins_week, etc.)
#     - cumulative totals (points_for, ap_wins_total, h2h_wins, etc.)
#     - derived rates (win_pct, ap_win_pct)
# ============================================================

build_adl_weekly_history <- function(seasons, max_week = adl_max_week) {
  seasons  <- as.integer(seasons)
  max_week <- min(max_week, adl_max_week)
  
  weekly_raw <- purrr::map_dfr(seasons, function(season) {
    message("Building weekly primitives for ADL season ", season, " ...")
    build_adl_weekly_primitives(season = season, max_week = max_week)
  })
  
  # Optional diagnostic (not used, but handy if you want to inspect)
  teams_per_season <- weekly_raw %>%
    dplyr::group_by(season) %>%
    dplyr::summarise(
      n_teams = dplyr::n_distinct(franchise_id),
      .groups = "drop"
    )
  
  # Cumulative fields per season/team -------------------------------
  history_with_cums <- weekly_raw %>%
    dplyr::arrange(season, franchise_id, week) %>%
    dplyr::group_by(season, franchise_id) %>%
    dplyr::mutate(
      points_for       = cumsum(points_for_week),
      potential_points = cumsum(potential_points_week),
      ap_wins_total    = cumsum(ap_wins_week),
      
      h2h_wins_raw_total   = cumsum(h2h_wins_week_raw),
      h2h_ties_raw_total   = cumsum(h2h_ties_week_raw),
      h2h_losses_raw_total = cumsum(h2h_losses_week_raw),
      
      h2h_wins  = h2h_wins_raw_total + 0.5 * h2h_ties_raw_total,
      h2h_games = h2h_wins_raw_total + h2h_ties_raw_total + h2h_losses_raw_total,
      win_pct   = dplyr::if_else(h2h_games > 0, h2h_wins / h2h_games, 0)
    ) %>%
    dplyr::ungroup()
  
  # All-play games per team by season-week: (n_teams - 1) * week -----
  history_with_cums %>%
    dplyr::group_by(season, week) %>%
    dplyr::mutate(
      n_teams_season = dplyr::n_distinct(franchise_id),
      ap_games       = (n_teams_season - 1L) * week,
      ap_win_pct     = dplyr::if_else(ap_games > 0, ap_wins_total / ap_games, 0)
    ) %>%
    dplyr::ungroup() %>%
    dplyr::select(
      season,
      week,
      franchise_id,
      franchise_name,
      division,
      conference,
      
      # Weekly primitives
      points_for_week,
      potential_points_week,
      offense_points_week,
      defense_points_week,
      specialteams_points_week,
      bench_points_week,
      offst_points_week,
      h2h_wins_week_raw,
      h2h_ties_week_raw,
      h2h_losses_week_raw,
      ap_wins_week,
      
      # Cumulative standings-like fields
      points_for,
      potential_points,
      ap_wins_total,
      h2h_wins_raw_total,
      h2h_ties_raw_total,
      h2h_losses_raw_total,
      h2h_wins,
      h2h_games,
      win_pct,
      ap_games,
      ap_win_pct
    )
}



# ============================================================
# FUNCTION: build_adl_weekly_results()
#
# Purpose in workflow:
#   For a *single* season and snapshot week, builds the full
#   ADL standings table needed for:
#     - Playoff picture
#     - Bonus game tallies (W3 / W6 / W9 / W12 / Season)
#     - Total wins and win% (H2H + Bonus)
#
#   This is the "live standings" function used by your
#   playoff-picture wrapper, whereas build_adl_weekly_history()
#   is the historical modeling dataset builder.
# ============================================================

build_adl_weekly_results <- function(season, week) {
  
  # Derive connection name for this season (e.g., "ADL25")
  season_suffix <- substr(as.character(season), 3, 4)
  conn_name     <- paste0("ADL", season_suffix)
  
  mfl_conn <- adl_connection(season)
  if (is.null(mfl_conn)) {
    stop("No MFL connection named ", conn_name, " found in load_mfl_conns().")
  }
  
  # Snapshot cannot go beyond the ADL regular season
  week_max <- min(as.integer(week), adl_max_week)
  
  # 1. Franchises: id -> name, division, conference --------------------
  franchises <- adl_fetch("franchises", mfl_conn) %>%
    dplyr::select(
      franchise_id,
      dplyr::any_of(c("franchise_name", "name", "division", "conference"))
    )
  
  # 2. Schedule (through given week, reg season only) ------------------
  sched <- adl_fetch("schedule", mfl_conn) %>%
    dplyr::filter(week <= week_max) %>%
    dplyr::select(
      week, franchise_id, opponent_id,
      franchise_score, opponent_score, result
    )
  
  h2h_weekly <- sched %>%
    dplyr::group_by(franchise_id, week) %>%
    dplyr::summarise(
      h2h_wins_raw   = sum(franchise_score > opponent_score, na.rm = TRUE),
      h2h_ties_raw   = sum(franchise_score == opponent_score, na.rm = TRUE),
      h2h_losses_raw = sum(franchise_score < opponent_score, na.rm = TRUE),
      points_for     = sum(franchise_score, na.rm = TRUE),
      .groups = "drop"
    )
  
  # 3. Starters -> potential_points + O/D/ST/bench splits --------------
  starters <- adl_fetch("starters", mfl_conn, week = seq_len(week_max)) %>%
    dplyr::filter(week <= week_max)
  
  weekly_pts_cats <- starters %>%
    dplyr::group_by(franchise_id, week) %>%
    dplyr::summarise(
      actual_from_starters = sum(
        player_score[starter_status == "starter"],
        na.rm = TRUE
      ),
      potential_points = sum(
        player_score[should_start == 1],
        na.rm = TRUE
      ),
      
      # Offense = starters only at offensive positions
      offense_points_week = sum(
        player_score[
          starter_status == "starter" &
            pos %in% c("QB", "RB", "WR", "TE")
        ],
        na.rm = TRUE
      ),
      
      # Defense = starters only at IDP positions
      defense_points_week = sum(
        player_score[
          starter_status == "starter" &
            pos %in% c("DT", "DE", "LB", "CB", "S")
        ],
        na.rm = TRUE
      ),
      
      # Special teams = starters only at PK/PN
      specialteams_points_week = sum(
        player_score[
          starter_status == "starter" &
            pos %in% c("PK", "PN")
        ],
        na.rm = TRUE
      ),
      
      # Bench = all nonstarters, regardless of position
      bench_points_week = sum(
        player_score[starter_status == "nonstarter"],
        na.rm = TRUE
      ),
      
      # Offense + special teams for starters only
      offst_points_week = sum(
        player_score[
          starter_status == "starter" &
            pos %in% c("QB", "RB", "WR", "TE", "PK", "PN")
        ],
        na.rm = TRUE
      ),
      
      .groups = "drop"
    )
  
  
  weekly_scores <- h2h_weekly %>%
    dplyr::left_join(weekly_pts_cats, by = c("franchise_id", "week"))
  
  # Sanity check: starter totals vs schedule totals --------------------
  mismatch <- weekly_scores %>%
    dplyr::filter(
      !is.na(actual_from_starters),
      abs(points_for - actual_from_starters) > 0.01
    ) %>%
    dplyr::left_join(franchises, by = "franchise_id")
  
  if (nrow(mismatch) > 0) {
    team_labels <- if ("franchise_name" %in% names(mismatch)) {
      paste0(
        "week ", mismatch$week,
        " – franchise_id ", mismatch$franchise_id,
        " (", mismatch$franchise_name, ")"
      )
    } else {
      paste0(
        "week ", mismatch$week,
        " – franchise_id ", mismatch$franchise_id
      )
    }
    
    warning(
      "Starter-based points differ from ff_schedule points for ",
      nrow(mismatch), " team-week rows: ",
      paste(team_labels, collapse = "; ")
    )
  }
  
  # 4. Weekly all-play wins (fast, rank-based) -------------------------
  n_teams <- weekly_scores %>%
    dplyr::summarise(n_teams = dplyr::n_distinct(franchise_id)) %>%
    dplyr::pull(n_teams)
  
  if (n_teams != 32L) {
    warning("Expected 32 teams, found ", n_teams,
            ". All-play logic assumes 32-team ADL.")
  }
  
  allplay_weekly <- weekly_scores %>%
    dplyr::group_by(week) %>%
    dplyr::group_modify(~ {
      tibble::tibble(
        franchise_id = .x$franchise_id,
        ap_wins_week = allplay_from_scores(.x$points_for)
      )
    }) %>%
    dplyr::ungroup()
  
  weekly_scores <- weekly_scores %>%
    dplyr::left_join(allplay_weekly, by = c("franchise_id", "week"))
  
  # 5. Bonus Games (W3 / W6 / W9 / W12 / Season) -----------------------
  calc_bonus_event <- function(weeks_vec, label) {
    weekly_scores %>%
      dplyr::filter(week %in% weeks_vec) %>%
      dplyr::group_by(franchise_id) %>%
      dplyr::summarise(
        ap_wins_seg    = sum(ap_wins_week,     na.rm = TRUE),
        points_seg     = sum(points_for,       na.rm = TRUE),
        pot_points_seg = sum(potential_points, na.rm = TRUE),
        .groups = "drop"
      ) %>%
      dplyr::arrange(
        dplyr::desc(ap_wins_seg),
        dplyr::desc(points_seg),
        dplyr::desc(pot_points_seg)
      ) %>%
      dplyr::mutate(
        seg_rank = dplyr::row_number(),
        bonus_result = dplyr::case_when(
          seg_rank <= 15L ~ 1,    # Bonus Win
          seg_rank <= 17L ~ 0.5,  # Bonus Tie
          TRUE            ~ 0     # Bonus Loss
        ),
        bonus_label = label
      ) %>%
      dplyr::select(franchise_id, bonus_label, bonus_result)
  }
  
  bonus_events <- list()
  if (week_max >= 3)  bonus_events[["W3"]]     <- calc_bonus_event(1:3,   "W3")
  if (week_max >= 6)  bonus_events[["W6"]]     <- calc_bonus_event(4:6,   "W6")
  if (week_max >= 9)  bonus_events[["W9"]]     <- calc_bonus_event(7:9,   "W9")
  if (week_max >= 12) {
    bonus_events[["W12"]]    <- calc_bonus_event(10:12, "W12")
    bonus_events[["SEASON"]] <- calc_bonus_event(1:12,  "SEASON")
  }
  
  if (length(bonus_events) == 0L) {
    # No bonus games awarded yet (week < 3)
    bonus_tbl <- franchises %>%
      dplyr::distinct(franchise_id) %>%
      dplyr::mutate(
        bonus_wins_raw   = 0,
        bonus_ties_raw   = 0,
        bonus_losses_raw = 0,
        bonus_wins       = 0
      )
  } else {
    bonus_tbl <- dplyr::bind_rows(bonus_events) %>%
      dplyr::group_by(franchise_id) %>%
      dplyr::summarise(
        bonus_wins_raw   = sum(bonus_result == 1,   na.rm = TRUE),
        bonus_ties_raw   = sum(bonus_result == 0.5, na.rm = TRUE),
        bonus_losses_raw = sum(bonus_result == 0,   na.rm = TRUE),
        bonus_wins       = sum(bonus_result,        na.rm = TRUE),
        .groups = "drop"
      )
  }
  
  # 6. Aggregate season-to-date standings -------------------------------
  h2h_season <- weekly_scores %>%
    dplyr::group_by(franchise_id) %>%
    dplyr::summarise(
      h2h_wins_raw     = sum(h2h_wins_raw,   na.rm = TRUE),
      h2h_ties_raw     = sum(h2h_ties_raw,   na.rm = TRUE),
      h2h_losses_raw   = sum(h2h_losses_raw, na.rm = TRUE),
      points_for       = sum(points_for,     na.rm = TRUE),
      potential_points = sum(potential_points, na.rm = TRUE),
      offense_points   = sum(offense_points_week,       na.rm = TRUE),
      defense_points   = sum(defense_points_week,       na.rm = TRUE),
      specialteams_points = sum(specialteams_points_week, na.rm = TRUE),
      bench_points     = sum(bench_points_week,         na.rm = TRUE),
      offst_points     = sum(offst_points_week,         na.rm = TRUE),
      ap_wins_total    = sum(ap_wins_week,   na.rm = TRUE),
      .groups = "drop"
    ) %>%
    dplyr::mutate(
      h2h_wins  = h2h_wins_raw + 0.5 * h2h_ties_raw,
      h2h_games = h2h_wins_raw + h2h_ties_raw + h2h_losses_raw
    )
  
  n_weeks_played    <- min(week_max, max(weekly_scores$week, na.rm = TRUE))
  ap_games_per_team <- (n_teams - 1L) * n_weeks_played
  
  standings <- h2h_season %>%
    dplyr::left_join(bonus_tbl, by = "franchise_id") %>%
    dplyr::mutate(
      bonus_wins_raw   = tidyr::replace_na(bonus_wins_raw,   0),
      bonus_ties_raw   = tidyr::replace_na(bonus_ties_raw,   0),
      bonus_losses_raw = tidyr::replace_na(bonus_losses_raw, 0),
      bonus_wins       = tidyr::replace_na(bonus_wins,       0),
      total_wins       = h2h_wins + bonus_wins,
      total_games      = h2h_games + (bonus_wins_raw + bonus_ties_raw + bonus_losses_raw),
      win_pct = dplyr::if_else(
        total_games > 0,
        total_wins / total_games,
        0
      ),
      ap_win_pct = if (ap_games_per_team > 0) {
        ap_wins_total / ap_games_per_team
      } else {
        0
      }
    ) %>%
    dplyr::left_join(franchises, by = "franchise_id") %>%
    dplyr::mutate(
      season       = season,
      through_week = week_max
    ) %>%
    dplyr::select(
      franchise_name,
      total_wins,
      ap_wins_total,
      points_for,
      potential_points,
      offense_points,
      defense_points,
      specialteams_points,
      bench_points,
      offst_points,
      
      h2h_wins_raw,
      h2h_losses_raw,
      h2h_ties_raw,
      h2h_wins,
      
      bonus_wins_raw,
      bonus_losses_raw,
      bonus_ties_raw,
      bonus_wins,
      
      dplyr::everything()
    )
  
  standings
}




###################################################################################################
## PLAYOFF SNAPSHOT: Add conference seeds, qual flags, and mini-league tiebreakers
##
## Input:
##   - standings: output from build_adl_weekly_results(), *single season*,
##                with columns like:
##                  season, through_week, conference, division,
##                  win_pct, ap_win_pct, points_for, etc.
##
## Output:
##   - standings with:
##       * qual flag ("y" division winner, "x" wild card, "" otherwise)
##       * playoff_seed (1–7 by conference)
##       * consol_seed  (8–16 by conference)
##       * seed         (playoff_seed or consol_seed)
##       * mini-league H2H tiebreak diagnostics for division leaders
###################################################################################################

# One qualification/seeding engine for actual and projected standings.
# games has one row per team/opponent/game, with credit 1, 0.5 or 0
# (expected credit is also supported for the point-estimate forecast).
adl_rank_playoffs <- function(teams, games) {
  stopifnot(!anyDuplicated(teams$franchise_id))
  teams$is_division_winner <- FALSE
  teams$is_wild_card <- FALSE
  teams$playoff_seed <- NA_integer_
  teams$consol_seed <- NA_integer_
  teams$h2h_mini_pct <- NA_real_
  rank_rows <- function(ix, division = FALSE) {
    if (division) {
      tied <- ix[round(teams$win_pct[ix], 10) == max(round(teams$win_pct[ix], 10))]
      ids <- teams$franchise_id[tied]
      for (i in tied) {
        g <- games[games$franchise_id == teams$franchise_id[i] & games$opponent_id %in% ids, ]
        teams$h2h_mini_pct[i] <<- if (nrow(g)) mean(g$credit) else NA_real_
      }
      mini <- teams$h2h_mini_pct[ix]
      mini[is.na(mini)] <- -Inf
      return(ix[order(-round(teams$win_pct[ix],10), -mini,
                      -teams$ap_win_pct[ix], -teams$points_for[ix], -teams$potential_points[ix])])
    }
    ix[order(-round(teams$win_pct[ix],10), -teams$ap_win_pct[ix],
             -teams$points_for[ix], -teams$potential_points[ix])]
  }
  for (ix in split(seq_len(nrow(teams)), interaction(teams$conference, teams$division, drop=TRUE))) {
    winner <- rank_rows(ix, TRUE)[1]
    teams$is_division_winner[winner] <- TRUE
  }
  for (ix in split(seq_len(nrow(teams)), teams$conference)) {
    candidates <- ix[!teams$is_division_winner[ix]]
    teams$is_wild_card[head(rank_rows(candidates),3)] <- TRUE
    qualified <- teams$is_division_winner[ix] | teams$is_wild_card[ix]
    # Qualification status and overall win percentage have no role in seeding.
    seed_order <- function(z) z[order(-teams$ap_win_pct[z], -teams$points_for[z], -teams$potential_points[z])]
    field <- seed_order(ix[qualified]); rest <- seed_order(ix[!qualified])
    teams$playoff_seed[field] <- seq_along(field)
    teams$consol_seed[rest] <- length(field) + seq_along(rest)
  }
  teams$is_playoff_team <- teams$is_division_winner | teams$is_wild_card
  teams$qual <- ifelse(teams$is_division_winner, "y", ifelse(teams$is_wild_card,"x",""))
  teams$seed <- ifelse(teams$is_playoff_team, teams$playoff_seed, teams$consol_seed)
  teams
}

add_adl_playoff_snapshot <- function(standings) {
  
  #-------------------------------
  # 0. Derive season, through_week, and MFL connection
  #-------------------------------
  season_vals <- unique(standings$season)
  if (length(season_vals) != 1L) {
    stop("standings must contain exactly one season; found: ",
         paste(season_vals, collapse = ", "))
  }
  season <- season_vals[[1]]
  
  week_vals    <- unique(standings$through_week)
  through_week <- max(week_vals, na.rm = TRUE)
  
  season_suffix <- substr(as.character(season), 3, 4)   # 2025 -> "25"
  conn_name     <- paste0("ADL", season_suffix)         # "ADL25"
  
  mfl_conn <- adl_connection(season)
  if (is.null(mfl_conn)) {
    stop("No MFL connection named ", conn_name, " found in load_mfl_conns().")
  }
  
  sched <- adl_fetch("schedule", mfl_conn) %>%
    dplyr::filter(week <= through_week, week <= adl_max_week) %>%   # reg season weeks 1–12
    dplyr::select(
      week,
      franchise_id,
      opponent_id,
      franchise_score,
      opponent_score
    )
  
  #-------------------------------
  # 1. Helper: mini-league H2H for a tied group (division title)
  #-------------------------------
  compute_mini_h2h <- function(sched_tbl, team_ids) {
    if (length(team_ids) <= 1L) {
      return(
        tibble::tibble(
          franchise_id        = team_ids,
          h2h_mini_wins       = 0,
          h2h_mini_ties_raw   = 0,
          h2h_mini_losses_raw = 0,
          h2h_mini_pct        = NA_real_
        )
      )
    }
    
    sched_tbl %>%
      dplyr::filter(
        franchise_id %in% team_ids,
        opponent_id  %in% team_ids
      ) %>%
      dplyr::group_by(franchise_id) %>%
      dplyr::summarise(
        h2h_mini_wins_raw   = sum(franchise_score > opponent_score, na.rm = TRUE),
        h2h_mini_ties_raw   = sum(franchise_score == opponent_score, na.rm = TRUE),
        h2h_mini_losses_raw = sum(franchise_score < opponent_score, na.rm = TRUE),
        .groups = "drop"
      ) %>%
      dplyr::mutate(
        h2h_mini_wins  = h2h_mini_wins_raw + 0.5 * h2h_mini_ties_raw,
        h2h_mini_games = h2h_mini_wins_raw + h2h_mini_ties_raw + h2h_mini_losses_raw,
        h2h_mini_pct   = dplyr::if_else(
          h2h_mini_games > 0,
          h2h_mini_wins / h2h_mini_games,
          NA_real_
        )
      ) %>%
      dplyr::select(
        franchise_id,
        h2h_mini_wins,
        h2h_mini_losses_raw,
        h2h_mini_ties_raw,
        h2h_mini_pct
      )
  }
  
  #-------------------------------
  # 2. Attach mini-league H2H to division leaders' tie groups
  #-------------------------------
  standings_with_mini <- standings %>%
    dplyr::group_by(conference, division) %>%
    dplyr::group_modify(~ {
      div_tbl <- .x
      max_wp  <- max(div_tbl$win_pct, na.rm = TRUE)
      tied_ids <- div_tbl$franchise_id[div_tbl$win_pct == max_wp]
      
      mini_tbl <- compute_mini_h2h(sched_tbl = sched, team_ids = tied_ids)
      
      div_tbl %>%
        dplyr::left_join(mini_tbl, by = "franchise_id")
    }) %>%
    dplyr::ungroup()
  
  games <- sched %>% dplyr::mutate(credit = as.numeric(franchise_score > opponent_score) +
                                    0.5 * as.numeric(franchise_score == opponent_score))
  combined <- adl_rank_playoffs(standings_with_mini, games)

  #-------------------------------
  # 6. Final column ordering
  #-------------------------------
  combined %>%
    dplyr::arrange(conference, seed) %>%
    dplyr::select(
      # First two columns:
      qual,        # "y", "x", or ""
      seed,          # 1–16 conference seed
      
      # Main stats:
      franchise_name,
      total_wins,
      ap_wins_total,
      points_for,
      potential_points,
      offense_points,
      defense_points,
      specialteams_points,
      bench_points,
      offst_points,
      
      # Raw + adjusted H2H:
      h2h_wins_raw,
      h2h_losses_raw,
      h2h_ties_raw,
      h2h_wins,
      
      # Raw + adjusted Bonus:
      bonus_wins_raw,
      bonus_losses_raw,
      bonus_ties_raw,
      bonus_wins,
      
      # Mini-league diagnostics:
      h2h_mini_wins,
      h2h_mini_losses_raw,
      h2h_mini_ties_raw,
      h2h_mini_pct,
      
      # Playoff vs consolation seeds:
      playoff_seed,
      consol_seed,
      
      # Everything else (conference, division, win_pct, ids, etc.)
      dplyr::everything()
    )
}



###############################################################################################
## POINTS-BASED MONTE CARLO ENGINE
##
## Goal:
##   Use historical weekly data to build a *points model* for each team at a snapshot week:
##     - Choose how to model the **mean** weekly points going forward
##     - Choose how to model the **standard deviation** (volatility)
##   Then simulate the remaining schedule many times, to get:
##     - Expected remaining points
##     - Expected remaining H2H wins
##     - Distribution quantiles for remaining points
##
## This replaces the previous “many linear models for AP/H2H” section.
###############################################################################################

###################################################################################################
## build_points_params_from_history()
##
## Purpose (DIAGNOSTICS ONLY, NO CHOOSING):
##   Using ADL weekly history, this function:
##
##   1) For each snapshot week w (1..max_week-1), builds 5 models to predict
##      EACH TEAM’S *remaining mean weekly points_for* over weeks (w+1..max_week),
##      using predictors available at week w:
##
##        Target:
##          rem_mean_pts = (season_points_for_total - points_for_to_date) /
##                         (max_week - w)
##
##        Candidate models:
##          M1: rem_mean_pts ~ ap_win_pct            # AP-only (renamed)
##          M2: rem_mean_pts ~ avg_pf                # PF-only (renamed)
##          M3: rem_mean_pts ~ avg_pot               # Pot-only (renamed)
##          M4: rem_mean_pts ~ avg_pf + avg_pot      # PF + Pot
##          M5: rem_mean_pts ~ avg_pf + avg_pot + ap_win_pct   # PF + Pot + AP
##
##        where:
##          avg_pf  = points_for       / w
##          avg_pot = potential_points / w
##
##      It returns a tibble of adjusted R² for all 5 models by week,
##      AND a ggplot of adj. R² vs week (5 lines).
##
##   2) For standard deviation of points:
##        - For each SEASON:
##             * compute each team’s SD of points_for_week across the full season
##             * average those SDs across teams -> avg_sd_pts_per_season
##        - Then compute an overall average SD across all season-team combos.
##
## Inputs:
##   - history_df: output from build_adl_weekly_history()
##                 must contain:
##                   season, week, franchise_id,
##                   points_for_week, potential_points_week,
##                   points_for, potential_points, ap_win_pct
##   - max_week:   final regular-season week (ADL: 12 / adl_max_week)
##   - min_rows_per_week: if fewer rows than this, we skip that week (NA adj.R²)
##
## Output:
##   A list with:
##     $mean_model_comparison : tibble(week, m1_ap_adjR2, m2_pf_adjR2, m3_pot_adjR2,
##                                           m4_pf_pot_adjR2, m5_pf_pot_ap_adjR2)
##     $mean_model_plot       : ggplot object (adj.R² vs week for 5 models, labeled M1–M5)
##     $coefficients_m4       : tibble(week, pf_coef, pot_coef)  # NEW per your request
##     $sd_by_season          : tibble(season, avg_sd_pts)
##     $overall_sd_avg        : single numeric, overall mean SD
##
##   This function DOES NOT choose a model or SD – it just reports diagnostics.
###################################################################################################


build_points_params_from_history <- function(history_df, max_week = 12L) {
  max_week <- as.integer(max_week)
  
  # ----------------------------------------------------------
  # 0) Add cumulative OFF / DEF / ST / BENCH / OFF+ST splits
  #    so we can define per-week PPG components.
  # ----------------------------------------------------------
  history_with_splits <- history_df %>%
    dplyr::arrange(season, franchise_id, week) %>%
    dplyr::group_by(season, franchise_id) %>%
    dplyr::mutate(
      off_points_to_date   = cumsum(offense_points_week),
      def_points_to_date   = cumsum(defense_points_week),
      st_points_to_date    = cumsum(specialteams_points_week),
      bench_points_to_date = cumsum(bench_points_week),
      offst_points_to_date = cumsum(offst_points_week)
    ) %>%
    dplyr::ungroup()
  
  # ----------------------------------------------------------
  # 1) Season totals for final points_for (used for remainder)
  # ----------------------------------------------------------
  season_totals <- history_with_splits %>%
    dplyr::filter(week == max_week) %>%
    dplyr::select(
      season,
      franchise_id,
      season_points_for = points_for
    )
  
  weeks_to_test <- 1:(max_week - 1L)
  
  mean_rows  <- list()
  m4_rows    <- list()
  week6_points_models <- NULL
  
  # ----------------------------------------------------------
  # 2) Loop over weeks to build remaining-mean-points models
  # ----------------------------------------------------------
  for (wk in weeks_to_test) {
    
    wk_df <- history_with_splits %>%
      dplyr::filter(week == wk) %>%
      dplyr::left_join(season_totals,
                       by = c("season", "franchise_id")) %>%
      dplyr::mutate(
        rem_weeks    = max_week - wk,
        rem_mean_pts = (season_points_for - points_for) / rem_weeks,
        
        weeks_played = wk,
        ppg          = points_for       / weeks_played,
        pot_ppg      = potential_points / weeks_played,
        
        off_ppg      = off_points_to_date   / weeks_played,
        def_ppg      = def_points_to_date   / weeks_played,
        st_ppg       = st_points_to_date    / weeks_played,
        bench_ppg    = bench_points_to_date / weeks_played,
        offst_ppg    = offst_points_to_date / weeks_played
      ) %>%
      dplyr::filter(
        !is.na(rem_mean_pts),
        !is.na(ppg),
        !is.na(pot_ppg)
      )
    
    if (nrow(wk_df) < 10L) {
      # Not enough data to fit; fill NA row
      mean_rows[[length(mean_rows) + 1L]] <- tibble::tibble(
        week                    = wk,
        M1_PF_adjR2             = NA_real_,
        M2_OffDefSTBench_adjR2  = NA_real_,
        M3_Pot_adjR2            = NA_real_,
        M4_PF_Pot_adjR2         = NA_real_,
        M5_OffDefST_Pot_adjR2   = NA_real_
      )
      
      m4_rows[[length(m4_rows) + 1L]] <- tibble::tibble(
        week            = wk,
        m4_intercept    = NA_real_,
        m4_pf_coef      = NA_real_,
        m4_pot_coef     = NA_real_,
        m4_pf_pval      = NA_real_,
        m4_pot_pval     = NA_real_
      )
      
      next
    }
    
    # ----------------------
    # Points models (M1–M5)
    # ----------------------
    
    # M1: Points For only
    m1 <- stats::lm(rem_mean_pts ~ ppg, data = wk_df)
    s1 <- summary(m1)
    a1 <- s1$adj.r.squared
    
    # M2: Off + Def + ST + Bench
    m2 <- stats::lm(
      rem_mean_pts ~ off_ppg + def_ppg + st_ppg + bench_ppg,
      data = wk_df
    )
    s2 <- summary(m2)
    a2 <- s2$adj.r.squared
    
    # M3: Potential only
    m3 <- stats::lm(rem_mean_pts ~ pot_ppg, data = wk_df)
    s3 <- summary(m3)
    a3 <- s3$adj.r.squared
    
    # M4: PF + Pot
    m4 <- stats::lm(rem_mean_pts ~ ppg + pot_ppg, data = wk_df)
    s4 <- summary(m4)
    a4 <- s4$adj.r.squared
    
    c4 <- stats::coef(s4)
    m4_intercept <- c4["(Intercept)", "Estimate"]
    m4_pf_coef   <- c4["ppg",         "Estimate"]
    m4_pot_coef  <- c4["pot_ppg",     "Estimate"]
    
    # M5: Off + Def + ST + Pot
    m5 <- stats::lm(
      rem_mean_pts ~ off_ppg + def_ppg + st_ppg + pot_ppg,
      data = wk_df
    )
    s5 <- summary(m5)
    a5 <- s5$adj.r.squared
    
    # Store row of adj.R² for this week
    mean_rows[[length(mean_rows) + 1L]] <- tibble::tibble(
      week                    = wk,
      M1_PF_adjR2             = a1,
      M2_OffDefSTBench_adjR2  = a2,
      M3_Pot_adjR2            = a3,
      M4_PF_Pot_adjR2         = a4,
      M5_OffDefST_Pot_adjR2   = a5
    )
    
    # Store M4 coefficients
    m4_rows[[length(m4_rows) + 1L]] <- tibble::tibble(
      week         = wk,
      m4_intercept = m4_intercept,
      m4_pf_coef   = m4_pf_coef,
      m4_pot_coef  = m4_pot_coef
    )
    
    # Keep the actual model objects for Week 6 so you can inspect
    if (wk == 6L) {
      week6_points_models <- list(
        M1_PF                = m1,
        M2_Off_Def_ST_Bench  = m2,
        M3_Pot               = m3,
        M4_PF_Pot            = m4,
        M5_Off_Def_ST_Pot    = m5
      )
    }
  }
  
  mean_model_comparison <- dplyr::bind_rows(mean_rows)
  m4_coefs_by_week      <- dplyr::bind_rows(m4_rows)
  
  # ----------------------------------------------------------
  # 3) Plot: adj.R² vs week for all 5 points models (M1–M5)
  # ----------------------------------------------------------
  mean_model_plot <- mean_model_comparison %>%
    tidyr::pivot_longer(
      cols = dplyr::starts_with("M"),
      names_to = "model",
      values_to = "adjR2"
    ) %>%
    dplyr::mutate(
      model = factor(
        model,
        levels = c(
          "M1_PF_adjR2",
          "M2_OffDefSTBench_adjR2",
          "M3_Pot_adjR2",
          "M4_PF_Pot_adjR2",
          "M5_OffDefST_Pot_adjR2"
        ),
        labels = c(
          "M1: Points For",
          "M2: Off + Def + ST + Bench",
          "M3: Potential Points",
          "M4: PF + Pot",
          "M5: Off + Def + ST + Pot"
        )
      )
    ) %>%
    ggplot2::ggplot(ggplot2::aes(x = week, y = adjR2, color = model)) +
    ggplot2::geom_line(linewidth = 1) +
    ggplot2::geom_point(size = 2) +
    ggplot2::labs(
      title = "Adjusted R² by Week for Points-Mean Models",
      x     = "Week (snapshot)",
      y     = "Adjusted R²",
      color = "Model"
    ) +
    ggplot2::theme_minimal(base_size = 13) +
    ggplot2::theme(
      legend.position = "right",
      legend.title    = ggplot2::element_text(size = 12, face = "bold"),
      legend.text     = ggplot2::element_text(size = 11)
    )
  
  # ----------------------------------------------------------
  # 4) SD models (S1–S4): predict future SD of points_for_week
  #     S1: rem_sd ~ sd_so_far
  #     S2: rem_sd ~ sd_so_far + ppg_so_far
  #     S3: rem_sd ~ sd_so_far + off_ppg_so_far
  #     S4: rem_sd ~ sd_so_far + pot_ppg_so_far
  # ----------------------------------------------------------
  sd_rows <- list()
  week6_sd_models <- NULL
  
  for (wk in weeks_to_test) {
    
    # "Past" segment: weeks 1..wk
    past <- history_df %>%
      dplyr::filter(week <= wk) %>%
      dplyr::group_by(season, franchise_id) %>%
      dplyr::summarise(
        sd_so_far        = stats::sd(points_for_week, na.rm = TRUE),
        ppg_so_far       = mean(points_for_week, na.rm = TRUE),
        off_ppg_so_far   = mean(offense_points_week, na.rm = TRUE),
        pot_ppg_so_far   = mean(potential_points_week, na.rm = TRUE),
        .groups          = "drop"
      )
    
    # "Future" segment: weeks (wk+1)..max_week
    future <- history_df %>%
      dplyr::filter(week > wk, week <= max_week) %>%
      dplyr::group_by(season, franchise_id) %>%
      dplyr::summarise(
        rem_sd = stats::sd(points_for_week, na.rm = TRUE),
        .groups = "drop"
      )
    
    sd_df <- dplyr::inner_join(
      past,
      future,
      by = c("season", "franchise_id")
    ) %>%
      dplyr::filter(
        !is.na(rem_sd),
        !is.na(sd_so_far)
      )
    
    if (nrow(sd_df) < 10L) {
      sd_rows[[length(sd_rows) + 1L]] <- tibble::tibble(
        week       = wk,
        S1_sd_adjR2 = NA_real_,
        S2_sd_ppg_adjR2 = NA_real_,
        S3_sd_off_adjR2 = NA_real_,
        S4_sd_pot_adjR2 = NA_real_
      )
      next
    }
    
    s1 <- stats::lm(rem_sd ~ sd_so_far, data = sd_df)
    s2 <- stats::lm(rem_sd ~ sd_so_far + ppg_so_far, data = sd_df)
    s3 <- stats::lm(rem_sd ~ sd_so_far + off_ppg_so_far, data = sd_df)
    s4 <- stats::lm(rem_sd ~ sd_so_far + pot_ppg_so_far, data = sd_df)
    
    sd_rows[[length(sd_rows) + 1L]] <- tibble::tibble(
      week             = wk,
      S1_sd_adjR2      = summary(s1)$adj.r.squared,
      S2_sd_ppg_adjR2  = summary(s2)$adj.r.squared,
      S3_sd_off_adjR2  = summary(s3)$adj.r.squared,
      S4_sd_pot_adjR2  = summary(s4)$adj.r.squared
    )
    
    if (wk == 6L) {
      week6_sd_models <- list(
        S1_sd_only       = s1,
        S2_sd_plus_ppg   = s2,
        S3_sd_plus_off   = s3,
        S4_sd_plus_pot   = s4
      )
    }
  }
  
  sd_model_comparison <- dplyr::bind_rows(sd_rows)
  
  # ----------------------------------------------------------
  # 5) SD diagnostics: per-season avg SD and overall
  # ----------------------------------------------------------
  sd_by_season <- history_df %>%
    dplyr::filter(week <= max_week) %>%
    dplyr::group_by(season, franchise_id) %>%
    dplyr::summarise(
      points_sd = stats::sd(points_for_week, na.rm = TRUE),
      .groups   = "drop"
    ) %>%
    dplyr::group_by(season) %>%
    dplyr::summarise(
      avg_points_sd = mean(points_sd, na.rm = TRUE),
      n_teams       = dplyr::n(),
      .groups       = "drop"
    )
  
  overall_sd_avg <- mean(sd_by_season$avg_points_sd, na.rm = TRUE)
  
  # ----------------------------------------------------------
  # 6) Return everything
  # ----------------------------------------------------------
  list(
    mean_model_comparison = mean_model_comparison,
    mean_model_plot       = mean_model_plot,
    week6_points_models   = week6_points_models,
    m4_coefs_by_week      = m4_coefs_by_week,
    sd_model_comparison   = sd_model_comparison,
    week6_sd_models       = week6_sd_models,
    sd_by_season          = sd_by_season,
    overall_sd_avg        = overall_sd_avg
  )
}




###################################################################################################
## run_adl_monte_carlo()
##
## Purpose:
##   For a given ADL season + snapshot week, simulate the REMAINDER of the regular season
##   using:
##     - Mean model:   M3 (avg_pot only) from historical seasons
##     - SD of points: sd_points (e.g. points_diag$overall_sd_avg)
##     - n_sims:       number of Monte Carlo runs (e.g. 3000)
##
##   For each sim, it:
##     1) Simulates weekly points_for for each team for weeks (through_week+1 .. max_week)
##     2) Derives weekly all-play wins and H2H wins from those simulated scores
##     3) Recomputes all 5 bonus events (Q1, Q2, Q3, Q4, RS) using:
##          - actual scores for past weeks
##          - simulated scores for future weeks
##
##   It then aggregates across sims to produce EXPECTED values:
##     - Expected remaining AP wins + final AP wins
##     - Expected remaining H2H wins + final H2H wins
##     - Expected Q1, Q2, Q3, Q4, RS bonus wins
##     - Expected weekly H2H wins: pred_w1_wins ... pred_w12_wins
##
## Inputs:
##   - standings_df : output from build_adl_weekly_results(season, week)
##                    must include:
##                      season, through_week, franchise_id,
##                      ap_wins_total, h2h_wins, total_wins,
##                      points_for, potential_points,
##                      franchise_name, conference, division
##   - history_df   : output from build_adl_weekly_history() for MULTIPLE seasons
##                    (used as training data for M3 mean model)
##   - sched_df     : ff_schedule() for the CURRENT season, with:
##                      week, franchise_id, opponent_id
##   - sd_points    : scalar SD for weekly points_for (e.g. points_diag$overall_sd_avg)
##   - max_week     : final regular-season week (ADL: 12)
##   - n_sims       : number of Monte Carlo simulations
##
## Output:
##   A list:
##     $team_summary : one row per team with:
##                      franchise_id, franchise_name, conference, division,
##                      actual_* columns (through snapshot week),
##                      predicted_* columns (expected future + final)
##     $weekly_h2h   : tibble(franchise_id, week, pred_weekly_h2h for each week)
##     $bonus_expect : tibble(franchise_id, pred_Q1_bonus, ..., pred_RS_bonus)
##     $mean_model_m3: the fitted M3 mean model (rem_mean_pts ~ avg_pot)
##
## Notes:
##   - Uses progressr for a text progress bar if available:
##       install.packages("progressr")
###################################################################################################



###################################################################################################
## FAST, STREAMING MONTE CARLO ENGINE
##
## Same interface as before:
##   run_adl_monte_carlo(standings_df, history_df, sched_df, sd_points, max_week = 12L, n_sims = 3000L)
##
## Returns:
##   $team_summary : tibble with actual + expected future wins and bonus
##   $weekly_h2h   : tibble(franchise_id, pred_w1, ..., pred_w12)
##   $bonus_expect : tibble(franchise_id, pred_Q1_bonus, ..., pred_RS_bonus)
##   $mean_model_m3: fitted M3 mean model (rem_mean_pts ~ avg_pot)
##
## Changes vs old version:
##   - Uses allplay_from_scores() (no Cartesian product).
##   - Uses base matrices for simulated points & bonus segments.
##   - Aggregates expectations inside the loop (no giant bind_rows).
##   - Adds exp_rem_bonus_wins to team_summary.
###################################################################################################

run_adl_monte_carlo <- function(
    standings_df,
    history_df,
    sched_df,
    sd_points,
    max_week = 12L,
    n_sims   = 3000L
) {
  
  #-------------------------------------------------------
  # 0. Basic checks: one season, one through_week
  #-------------------------------------------------------
  season_vals <- unique(standings_df$season)
  if (length(season_vals) != 1L) {
    stop("standings_df must contain exactly one season.")
  }
  season0 <- season_vals[[1]]
  
  wk_vals <- unique(standings_df$through_week)
  if (length(wk_vals) != 1L) {
    stop("standings_df must contain exactly one through_week.")
  }
  wk0 <- wk_vals[[1]]
  
  #-------------------------------------------------------
  # SPECIAL CASE: season already complete (wk0 >= max_week)
  #   -> no simulation, just echo actuals as projections
  #   (Note: probabilities are handled in get_adl_playoff_picture)
  #-------------------------------------------------------
  #-------------------------------------------------------
  # SPECIAL CASE: season already complete (wk0 >= max_week)
  #   -> no simulation, just echo actuals as projections
  #   -> ALSO compute 0/1 probabilities from actual results
  #-------------------------------------------------------
  if (wk0 >= max_week) {
    message("Snapshot week is at or beyond max_week; using actuals as projections (no simulation).")
    
    curr_teams <- standings_df %>%
      dplyr::select(
        season,
        through_week,
        franchise_id,
        franchise_name,
        conference,
        division,
        ap_wins_total,
        h2h_wins,
        total_wins,
        bonus_wins,
        points_for,
        potential_points
      )
    
    team_ids   <- curr_teams$franchise_id
    n_teams    <- length(team_ids)
    team_index <- seq_len(n_teams)
    names(team_index) <- team_ids
    
    # Build weekly H2H matrix from history (actuals only)
    hist_season <- history_df %>%
      dplyr::filter(season == season0, week <= max_week)
    
    n_weeks <- max_week
    h2h_mat_actual <- matrix(0, nrow = n_teams, ncol = n_weeks)
    
    if (nrow(hist_season) > 0L) {
      for (row_i in seq_len(nrow(hist_season))) {
        w  <- hist_season$week[row_i]
        if (w > n_weeks) next
        
        id  <- hist_season$franchise_id[row_i]
        idx <- team_index[[as.character(id)]]
        
        h2h_val <- hist_season$h2h_wins_week_raw[row_i] +
          0.5 * hist_season$h2h_ties_week_raw[row_i]
        
        h2h_mat_actual[idx, w] <- h2h_val
      }
    }
    
    weekly_h2h_df <- as.data.frame(h2h_mat_actual)
    colnames(weekly_h2h_df) <- paste0("pred_w", seq_len(n_weeks), "_wins")
    
    weekly_h2h <- tibble::tibble(franchise_id = team_ids) %>%
      dplyr::bind_cols(weekly_h2h_df)
    
    bonus_expect <- tibble::tibble(
      franchise_id  = team_ids,
      pred_Q1_bonus = 0,
      pred_Q2_bonus = 0,
      pred_Q3_bonus = 0,
      pred_Q4_bonus = 0,
      pred_RS_bonus = 0
    )
    
    # --- NEW: compute 0/1 probabilities from ACTUAL final standings ---
    final_games    <- 17L       # 12 H2H + 5 bonus events
    ap_games_total <- (n_teams - 1L) * max_week
    
    standings_for_prob <- curr_teams %>%
      dplyr::mutate(
        win_pct = total_wins / final_games,
        ap_win_pct = if (ap_games_total > 0) {
          ap_wins_total / ap_games_total
        } else {
          NA_real_
        }
      )
    
    games <- sched_df %>% dplyr::filter(week <= max_week) %>%
      dplyr::left_join(hist_season %>% dplyr::select(franchise_id, week, own = points_for_week), by=c("franchise_id","week")) %>%
      dplyr::left_join(hist_season %>% dplyr::select(opponent_id=franchise_id, week, opp=points_for_week), by=c("opponent_id","week")) %>%
      dplyr::mutate(credit=as.numeric(own > opp) + 0.5 * as.numeric(own == opp))
    flagged <- adl_rank_playoffs(standings_for_prob, games)

    prob_df <- flagged %>%
      dplyr::transmute(
        franchise_id,
        playoff_pct = as.numeric(is_playoff_team),
        divwin_pct  = as.numeric(is_division_winner),
        bye_pct     = as.numeric(!is.na(playoff_seed) & playoff_seed == 1L)
      )
    
    # --- actuals as projections + probabilities -----------------------
    team_summary <- curr_teams %>%
      dplyr::mutate(
        exp_rem_ap_wins    = 0,
        exp_rem_h2h_wins   = 0,
        pred_ap_wins       = ap_wins_total,
        pred_h2h_wins      = h2h_wins,
        pred_total_bonus   = bonus_wins,
        exp_rem_bonus_wins = 0,
        pred_total_wins    = total_wins
      ) %>%
      dplyr::left_join(prob_df, by = "franchise_id")
    
    return(list(
      team_summary  = team_summary,
      weekly_h2h    = weekly_h2h,
      bonus_expect  = bonus_expect,
      mean_model_m3 = NULL
    ))
  }
  
  
  #-------------------------------------------------------
  # 1. Fit the M3 (avg_pot only) mean model at week wk0
  #    using fully-completed seasons in history_df
  #-------------------------------------------------------
  future_weeks    <- seq.int(wk0 + 1L, max_week)
  n_future_weeks  <- length(future_weeks)
  
  full_seasons <- history_df %>%
    dplyr::filter(week == max_week) %>%
    dplyr::distinct(season) %>%
    dplyr::pull(season)
  
  train_seasons <- full_seasons[full_seasons < season0]
  if (length(train_seasons) == 0L) {
    stop("No fully-completed prior seasons available for training mean model.")
  }
  
  season_totals <- history_df %>%
    dplyr::filter(season %in% train_seasons, week == max_week) %>%
    dplyr::select(season, franchise_id, season_pts = points_for)
  
  snapshot_train <- history_df %>%
    dplyr::filter(season %in% train_seasons, week == wk0) %>%
    dplyr::select(
      season, franchise_id,
      pts_to_date = points_for,
      pot_to_date = potential_points
    )
  
  train_df <- snapshot_train %>%
    dplyr::inner_join(season_totals, by = c("season", "franchise_id")) %>%
    dplyr::mutate(
      rem_weeks    = max_week - wk0,
      rem_mean_pts = (season_pts - pts_to_date) / rem_weeks,
      avg_pot      = pot_to_date / wk0
    ) %>%
    dplyr::filter(rem_weeks > 0)
  
  if (nrow(train_df) < 10L) {
    stop("Not enough training rows to fit M3 mean model at week ", wk0, ".")
  }
  
  mean_mod_m3 <- stats::lm(rem_mean_pts ~ avg_pot, data = train_df)
  a3 <- stats::coef(mean_mod_m3)[["(Intercept)"]]
  b3 <- stats::coef(mean_mod_m3)[["avg_pot"]]
  
  #-------------------------------------------------------
  # 2. Current-season snapshot: compute mu (mean) per team
  #-------------------------------------------------------
  curr_teams <- standings_df %>%
    dplyr::select(
      season,
      through_week,
      franchise_id,
      franchise_name,
      conference,
      division,
      ap_wins_total,
      h2h_wins,
      total_wins,
      bonus_wins,
      points_for,
      potential_points
    ) %>%
    dplyr::mutate(
      avg_pf       = points_for       / through_week,
      avg_pot      = potential_points / through_week,
      rem_weeks    = max_week - through_week,
      rem_mean_hat = a3 + b3 * avg_pot,
      mu_pts       = pmax(rem_mean_hat, 0)
    )
  
  team_ids    <- curr_teams$franchise_id
  n_teams     <- length(team_ids)
  team_index  <- seq_len(n_teams)
  names(team_index) <- team_ids
  
  conferences <- curr_teams$conference
  divisions   <- curr_teams$division
  
  # AP games per team in a full regular season
  ap_games_total <- (n_teams - 1L) * max_week
  
  #-------------------------------------------------------
  # 3. Actual weekly scores and AP/H2H for current season
  #-------------------------------------------------------
  hist_season <- history_df %>%
    dplyr::filter(season == season0, week <= wk0)
  
  pts_mat_actual <- matrix(0, nrow = n_teams, ncol = wk0)
  ap_mat_actual  <- matrix(0, nrow = n_teams, ncol = wk0)
  h2h_mat_actual <- matrix(0, nrow = n_teams, ncol = wk0)
  
  if (wk0 > 0L && nrow(hist_season) > 0L) {
    for (row_i in seq_len(nrow(hist_season))) {
      w  <- hist_season$week[row_i]
      id <- hist_season$franchise_id[row_i]
      idx <- team_index[[as.character(id)]]
      
      pts_mat_actual[idx, w] <- hist_season$points_for_week[row_i]
      ap_mat_actual[idx,  w] <- hist_season$ap_wins_week[row_i]
      
      h2h_val <- hist_season$h2h_wins_week_raw[row_i] +
        0.5 * hist_season$h2h_ties_week_raw[row_i]
      h2h_mat_actual[idx, w] <- h2h_val
    }
  }
  
  #-------------------------------------------------------
  # 4. Remaining schedule in index form for fast H2H calc
  #-------------------------------------------------------
  sched_rem <- sched_df %>%
    dplyr::filter(week > wk0, week <= max_week) %>%
    dplyr::mutate(
      t1 = pmin(franchise_id, opponent_id),
      t2 = pmax(franchise_id, opponent_id)
    ) %>%
    dplyr::distinct(week, t1, t2, .keep_all = TRUE) %>%
    dplyr::transmute(
      week,
      i   = team_index[as.character(t1)],
      j   = team_index[as.character(t2)],
      col = week - wk0
    )
  
  all_games <- sched_df %>% dplyr::filter(week <= max_week)
  own_idx <- cbind(match(all_games$franchise_id, team_ids), all_games$week)
  opp_idx <- cbind(match(all_games$opponent_id, team_ids), all_games$week)
  # Potential points are not independently simulated by the existing model.
  # Preserve each team's observed nonnegative potential-minus-actual gap.
  potential_gap <- pmax((curr_teams$potential_points - curr_teams$points_for) / wk0, 0)
  sched_rem_mat <- as.data.frame(sched_rem)
  
  #-------------------------------------------------------
  # 5. Initialize accumulators for expectations + probs
  #-------------------------------------------------------
  accum_rem_ap   <- numeric(n_teams)
  accum_rem_h2h  <- numeric(n_teams)
  accum_bonus_Q1 <- numeric(n_teams)
  accum_bonus_Q2 <- numeric(n_teams)
  accum_bonus_Q3 <- numeric(n_teams)
  accum_bonus_Q4 <- numeric(n_teams)
  accum_bonus_RS <- numeric(n_teams)
  
  weekly_future_h2h_sum <- matrix(0, nrow = n_teams, ncol = length(future_weeks))
  
  # NEW: playoff/division/bye counts
  playoff_count <- numeric(n_teams)
  divwin_count  <- numeric(n_teams)
  bye_count     <- numeric(n_teams)
  
  pb <- utils::txtProgressBar(min = 0, max = n_sims, style = 3)
  
  #-------------------------------------------------------
  # 6. Run simulations
  #-------------------------------------------------------
  for (sim_id in seq_len(n_sims)) {
    
    # 6a. Simulate future weekly points
    pts_future <- matrix(
      stats::rnorm(
        n_teams * length(future_weeks),
        mean = rep(curr_teams$mu_pts, times = length(future_weeks)),
        sd   = sd_points
      ),
      nrow = n_teams,
      ncol = length(future_weeks),
      byrow = FALSE
    )
    pts_future[pts_future < 0] <- 0
    
    # 6b. All-play for future weeks
    ap_future <- matrix(0, nrow = n_teams, ncol = length(future_weeks))
    if (length(future_weeks) > 0L) {
      for (c in seq_len(length(future_weeks))) {
        ap_future[, c] <- allplay_from_scores(pts_future[, c])
      }
    }
    
    # 6c. H2H for future weeks
    rem_h2h_sim    <- numeric(n_teams)
    weekly_h2h_sim <- matrix(0, nrow = n_teams, ncol = length(future_weeks))
    
    if (nrow(sched_rem_mat) > 0L) {
      for (g in seq_len(nrow(sched_rem_mat))) {
        i   <- sched_rem_mat$i[g]
        j   <- sched_rem_mat$j[g]
        col <- sched_rem_mat$col[g]
        
        pi <- pts_future[i, col]
        pj <- pts_future[j, col]
        
        if (pi > pj) {
          ri <- 1;   rj <- 0
        } else if (pi < pj) {
          ri <- 0;   rj <- 1
        } else {
          ri <- 0.5; rj <- 0.5
        }
        
        rem_h2h_sim[i] <- rem_h2h_sim[i] + ri
        rem_h2h_sim[j] <- rem_h2h_sim[j] + rj
        
        weekly_h2h_sim[i, col] <- weekly_h2h_sim[i, col] + ri
        weekly_h2h_sim[j, col] <- weekly_h2h_sim[j, col] + rj
      }
    }
    
    # 6d. Full-season matrices for bonus segments
    pts_mat_sim <- cbind(pts_mat_actual, pts_future)
    ap_mat_sim  <- cbind(ap_mat_actual,  ap_future)
    
    seg_Q1_ap  <- rowSums(ap_mat_sim[, 1:3,   drop = FALSE])
    seg_Q2_ap  <- rowSums(ap_mat_sim[, 4:6,   drop = FALSE])
    seg_Q3_ap  <- rowSums(ap_mat_sim[, 7:9,   drop = FALSE])
    seg_Q4_ap  <- rowSums(ap_mat_sim[, 10:12, drop = FALSE])
    seg_RS_ap  <- rowSums(ap_mat_sim[, 1:12,  drop = FALSE])
    
    seg_Q1_pts <- rowSums(pts_mat_sim[, 1:3,   drop = FALSE])
    seg_Q2_pts <- rowSums(pts_mat_sim[, 4:6,   drop = FALSE])
    seg_Q3_pts <- rowSums(pts_mat_sim[, 7:9,   drop = FALSE])
    seg_Q4_pts <- rowSums(pts_mat_sim[, 10:12, drop = FALSE])
    seg_RS_pts <- rowSums(pts_mat_sim[, 1:12,  drop = FALSE])
    
    Q1_bonus <- bonus_from_segment(seg_Q1_ap, seg_Q1_pts)
    Q2_bonus <- bonus_from_segment(seg_Q2_ap, seg_Q2_pts)
    Q3_bonus <- bonus_from_segment(seg_Q3_ap, seg_Q3_pts)
    Q4_bonus <- bonus_from_segment(seg_Q4_ap, seg_Q4_pts)
    RS_bonus <- bonus_from_segment(seg_RS_ap, seg_RS_pts)
    
    accum_rem_ap   <- accum_rem_ap   + rowSums(ap_future)
    accum_rem_h2h  <- accum_rem_h2h  + rem_h2h_sim
    accum_bonus_Q1 <- accum_bonus_Q1 + Q1_bonus
    accum_bonus_Q2 <- accum_bonus_Q2 + Q2_bonus
    accum_bonus_Q3 <- accum_bonus_Q3 + Q3_bonus
    accum_bonus_Q4 <- accum_bonus_Q4 + Q4_bonus
    accum_bonus_RS <- accum_bonus_RS + RS_bonus
    
    weekly_future_h2h_sum <- weekly_future_h2h_sum + weekly_h2h_sim
    
    # ---------- NEW: derive playoff/division/bye outcomes for this sim ----------
    pts_total_sim      <- rowSums(pts_mat_sim)
    ap_wins_total_sim  <- rowSums(ap_mat_sim)
    total_h2h_sim      <- curr_teams$h2h_wins + rem_h2h_sim
    total_bonus_sim    <- Q1_bonus + Q2_bonus + Q3_bonus + Q4_bonus + RS_bonus
    total_wins_sim     <- total_h2h_sim + total_bonus_sim
    win_pct_sim        <- total_wins_sim / 17L
    ap_win_pct_sim     <- if (ap_games_total > 0) ap_wins_total_sim / ap_games_total else NA_real_
    
    sim_df <- tibble::tibble(
      franchise_id=team_ids, conference=conferences, division=divisions,
      win_pct=win_pct_sim, ap_win_pct=ap_win_pct_sim, points_for=pts_total_sim,
      potential_points=curr_teams$potential_points + rowSums(pts_future) + potential_gap * n_future_weeks)
    games <- all_games
    games$credit <- as.numeric(pts_mat_sim[own_idx] > pts_mat_sim[opp_idx]) +
      0.5 * as.numeric(pts_mat_sim[own_idx] == pts_mat_sim[opp_idx])
    sim_flagged <- adl_rank_playoffs(sim_df, games) %>%
      dplyr::rename(is_division_winner_sim=is_division_winner,
                    is_playoff_team_sim=is_playoff_team, playoff_seed_sim=playoff_seed)

    # Update counts
    for (row_i in seq_len(nrow(sim_flagged))) {
      fid <- as.character(sim_flagged$franchise_id[row_i])
      idx <- team_index[[fid]]
      
      if (isTRUE(sim_flagged$is_playoff_team_sim[row_i])) {
        playoff_count[idx] <- playoff_count[idx] + 1L
      }
      if (isTRUE(sim_flagged$is_division_winner_sim[row_i])) {
        divwin_count[idx] <- divwin_count[idx] + 1L
      }
      if (!is.na(sim_flagged$playoff_seed_sim[row_i]) &&
          sim_flagged$playoff_seed_sim[row_i] == 1L) {
        bye_count[idx] <- bye_count[idx] + 1L
      }
    }
    
    utils::setTxtProgressBar(pb, sim_id)
  }
  
  close(pb)
  
  #-------------------------------------------------------
  # 7. Convert accumulators to expectations + probabilities
  #-------------------------------------------------------
  exp_rem_ap_wins  <- accum_rem_ap  / n_sims
  exp_rem_h2h_wins <- accum_rem_h2h / n_sims
  
  pred_Q1_bonus <- accum_bonus_Q1 / n_sims
  pred_Q2_bonus <- accum_bonus_Q2 / n_sims
  pred_Q3_bonus <- accum_bonus_Q3 / n_sims
  pred_Q4_bonus <- accum_bonus_Q4 / n_sims
  pred_RS_bonus <- accum_bonus_RS / n_sims
  
  weekly_future_exp <- weekly_future_h2h_sum / n_sims
  
  weekly_h2h_all <- matrix(0, nrow = n_teams, ncol = max_week)
  if (wk0 > 0L) {
    weekly_h2h_all[, 1:wk0] <- h2h_mat_actual
  }
  if (length(future_weeks) > 0L) {
    weekly_h2h_all[, (wk0 + 1L):max_week] <- weekly_future_exp
  }
  
  weekly_h2h_df <- as.data.frame(weekly_h2h_all)
  colnames(weekly_h2h_df) <- paste0("pred_w", seq_len(max_week), "_wins")
  
  weekly_h2h <- tibble::tibble(franchise_id = team_ids) %>%
    dplyr::bind_cols(weekly_h2h_df)
  
  bonus_expect <- tibble::tibble(
    franchise_id  = team_ids,
    pred_Q1_bonus = pred_Q1_bonus,
    pred_Q2_bonus = pred_Q2_bonus,
    pred_Q3_bonus = pred_Q3_bonus,
    pred_Q4_bonus = pred_Q4_bonus,
    pred_RS_bonus = pred_RS_bonus
  )
  
  agg_df <- tibble::tibble(
    franchise_id     = team_ids,
    exp_rem_ap_wins  = exp_rem_ap_wins,
    exp_rem_h2h_wins = exp_rem_h2h_wins
  )
  
  prob_df <- tibble::tibble(
    franchise_id = team_ids,
    playoff_pct  = playoff_count / n_sims,
    divwin_pct   = divwin_count  / n_sims,
    bye_pct      = bye_count     / n_sims
  )
  
  team_summary <- curr_teams %>%
    dplyr::left_join(agg_df,       by = "franchise_id") %>%
    dplyr::left_join(bonus_expect, by = "franchise_id") %>%
    dplyr::left_join(prob_df,      by = "franchise_id") %>%
    dplyr::mutate(
      exp_rem_ap_wins    = dplyr::coalesce(exp_rem_ap_wins,  0),
      exp_rem_h2h_wins   = dplyr::coalesce(exp_rem_h2h_wins, 0),
      pred_ap_wins       = ap_wins_total + exp_rem_ap_wins,
      pred_h2h_wins      = h2h_wins      + exp_rem_h2h_wins,
      pred_total_bonus   = pred_Q1_bonus + pred_Q2_bonus +
        pred_Q3_bonus + pred_Q4_bonus + pred_RS_bonus,
      exp_rem_bonus_wins = pred_total_bonus - bonus_wins,
      pred_total_wins    = pred_h2h_wins + pred_total_bonus
    )
  
  list(
    team_summary  = team_summary,
    weekly_h2h    = weekly_h2h,
    bonus_expect  = bonus_expect,
    mean_model_m3 = mean_mod_m3
  )
}





########################################################################
#### CREATE PRETTY READOUT GRAPHIC #####################################
########################################################################

build_conf_draft <- function(df_conf,
                             seed_col,
                             pot_col,
                             seed_playoff_max = 7L,
                             seed_consol_min  = 8L,
                             playoff_order = c("potential", "seed")) {
  playoff_order <- match.arg(playoff_order)
  consol <- df_conf %>%
    dplyr::filter(.data[[seed_col]] >= seed_consol_min) %>%
    dplyr::arrange(.data[[pot_col]]) %>%
    dplyr::mutate(Pick = dplyr::row_number()) %>%
    dplyr::select(Pick, Team = franchise_name)
  
  playoff <- df_conf %>%
    dplyr::filter(.data[[seed_col]] <= seed_playoff_max)
  # Projected playoff teams draft in reverse seed order (7 before 1).
  playoff <- if (playoff_order == "seed") {
    dplyr::arrange(playoff, dplyr::desc(.data[[seed_col]]))
  } else {
    dplyr::arrange(playoff, .data[[pot_col]])
  }
  playoff <- playoff %>%
    dplyr::mutate(Pick = dplyr::row_number() + nrow(consol)) %>%
    dplyr::select(Pick, Team = franchise_name)
  
  dplyr::bind_rows(consol, playoff)
}

build_adl_playoff_graphic <- function(adl_picture, season, week) {
  
  # ------------------------------------------------------------------
  # 0. Ensure key columns exist (light safety only)
  # ------------------------------------------------------------------
  safe_add <- function(df, col, default) {
    if (!col %in% names(df)) df[[col]] <- default
    df
  }
  
  adl_picture <- adl_picture %>%
    safe_add("clinch",      "") %>%
    safe_add("entry",       "") %>%
    safe_add("ap_wins",     adl_picture$ap_wins_total %||% NA_real_) %>%
    safe_add("record",      NA_character_) %>%
    safe_add("ap_win_pct",  NA_real_) %>%
    safe_add("ppg",         NA_real_) %>%
    safe_add("pot_ppg",     NA_real_) %>%
    safe_add("playoff_pct", NA_real_) %>%
    safe_add("divwin_pct",  NA_real_) %>%
    safe_add("bye_pct",     NA_real_)
  
  # Convenience coalesces for legacy fields ---------------------------
  adl_picture <- adl_picture %>%
    dplyr::mutate(
      entry     = dplyr::coalesce(.data$entry, .data$qual),
      ap_wins   = dplyr::coalesce(.data$ap_wins, .data$ap_wins_total),
      pred_wins = dplyr::coalesce(.data$pred_wins, .data$pred_total_wins)
    )
  
  playoff_cols <- c(
    "clinch",          # Clinch tag column (b/d/p/e or "")
    "entry",           # Qual (y/x)
    "seed",
    "franchise_name",
    "record",
    "ap_wins",
    "ap_win_pct",
    "ppg",
    "pot_ppg",
    "pred_wins",
    "pred_ap_wins",
    "pred_finish",
    "playoff_pct",
    "divwin_pct",
    "bye_pct"
  )
  
  nfc_df <- adl_picture %>%
    dplyr::filter(conference == "00") %>%
    dplyr::arrange(seed)
  
  afc_df <- adl_picture %>%
    dplyr::filter(conference == "01") %>%
    dplyr::arrange(seed)
  
  if (nrow(nfc_df) == 0 || nrow(afc_df) == 0) {
    warning(
      "Expected NFC (conference == '00') and AFC (conference == '01') rows.\n",
      "Got: ", nrow(nfc_df), " NFC and ", nrow(afc_df), " AFC."
    )
  }
  
  nfc_tbl <- nfc_df %>% dplyr::select(dplyr::all_of(playoff_cols))
  afc_tbl <- afc_df %>% dplyr::select(dplyr::all_of(playoff_cols))
  
  label_cols <- list(
    clinch           = "Clinch",
    entry            = "Qual",
    seed             = "Seed",
    franchise_name   = "Team",
    record           = "Record",
    ap_wins          = "AP Wins",
    ap_win_pct       = "APwin%",
    ppg              = "PPG",
    pot_ppg          = "Pot. PPG",
    pred_wins        = "Pred. Wins",
    pred_ap_wins     = "Pred. AP Wins",
    pred_finish      = "Pred. Finish",
    playoff_pct      = "Playoff%",
    divwin_pct       = "Div%",
    bye_pct          = "Bye%"
  )
  
  format_playoff_table <- function(tbl, conf_label) {
    gt::gt(tbl) %>%
      gt::tab_header(
        title = glue::glue("{conf_label} Playoff Picture (after Week {week})")
      ) %>%
      gt::cols_label(.list = label_cols) %>%
      # Numeric formatting
      gt::fmt_number(columns = "pred_wins",    decimals = 2) %>%
      gt::fmt_number(columns = "pred_ap_wins", decimals = 1) %>%
      gt::fmt_number(columns = "ap_win_pct",   decimals = 3) %>%
      gt::fmt_number(columns = c("ppg", "pot_ppg"), decimals = 1) %>%
      gt::fmt_percent(
        columns  = c("playoff_pct", "divwin_pct", "bye_pct"),
        decimals = 0
      ) %>%
      # Clinch + Qual italic in the body
      gt::tab_style(
        style = list(
          gt::cell_text(align = "right", style = "italic")
        ),
        locations = gt::cells_body(columns = c("clinch", "entry"))
      ) %>%
      # Clinch key (above Qual key), with capitalized words and italic letters
      gt::tab_source_note(
        gt::md(
          "*b* = Clinched Bye &nbsp;&nbsp;&nbsp;&nbsp; *d* = Clinched Division &nbsp;&nbsp;&nbsp;&nbsp; *p* = Clinched Playoffs &nbsp;&nbsp;&nbsp;&nbsp; *e* = Eliminated"
        )
      ) %>%
      gt::tab_source_note(
        gt::md("*y* = Division Winner &nbsp;&nbsp;&nbsp;&nbsp; *x* = Wild Card")
      )
  }
  
  playoff_nfc_gt <- format_playoff_table(nfc_tbl, "NFC")
  playoff_afc_gt <- format_playoff_table(afc_tbl, "AFC")
  
  # Current order uses actual potential; projected order uses forecast inputs.
  nfc_today <- build_conf_draft(nfc_df, seed_col = "seed",      pot_col = "potential_points")
  afc_today <- build_conf_draft(afc_df, seed_col = "seed",      pot_col = "potential_points")
  nfc_pred  <- build_conf_draft(nfc_df %>% dplyr::mutate(pred_seed = pred_finish),
                                seed_col = "pred_seed", pot_col = "pred_potential_points",
                                playoff_order = "seed")
  afc_pred  <- build_conf_draft(afc_df %>% dplyr::mutate(pred_seed = pred_finish),
                                seed_col = "pred_seed", pot_col = "pred_potential_points",
                                playoff_order = "seed")
  
  draft_grid <- nfc_today %>%
    dplyr::rename(
      nfc_today_pick = Pick,
      nfc_today_team = Team
    ) %>%
    dplyr::bind_cols(
      nfc_pred %>%
        dplyr::rename(
          nfc_proj_pick = Pick,
          nfc_proj_team = Team
        ),
      afc_today %>%
        dplyr::rename(
          afc_today_pick = Pick,
          afc_today_team = Team
        ),
      afc_pred %>%
        dplyr::rename(
          afc_proj_pick = Pick,
          afc_proj_team = Team
        )
    )
  
  draft_gt <- draft_grid %>%
    gt::gt() %>%
    gt::tab_header(
      title = glue::glue("Projected {season + 1} ADL Draft Order")
    ) %>%
    gt::cols_label(
      nfc_today_pick = "",
      nfc_today_team = "",
      nfc_proj_pick  = "",
      nfc_proj_team  = "",
      afc_today_pick = "",
      afc_today_team = "",
      afc_proj_pick  = "",
      afc_proj_team  = ""
    ) %>%
    gt::tab_spanner(
      label   = "NFC (As of Today)",
      columns = c(nfc_today_pick, nfc_today_team)
    ) %>%
    gt::tab_spanner(
      label   = "NFC (Projected)",
      columns = c(nfc_proj_pick, nfc_proj_team)
    ) %>%
    gt::tab_spanner(
      label   = "AFC (As of Today)",
      columns = c(afc_today_pick, afc_today_team)
    ) %>%
    gt::tab_spanner(
      label   = "AFC (Projected)",
      columns = c(afc_proj_pick, afc_proj_team)
    )
  
  list(
    playoff_nfc = playoff_nfc_gt,
    playoff_afc = playoff_afc_gt,
    draft_table = draft_gt
  )
}







####################################################
### DEFINE FINAL WRAPPER FUNCTION #################
####################################################

get_adl_playoff_picture <- function(
    season,
    week,
    max_week     = adl_max_week,
    n_bonus_sims = getOption("adl.n_sims", 3000L)
) {
  season <- as.integer(season)
  week   <- as.integer(week)
  
  # -------------------------------------------------
  # 0. Sanity checks / required globals
  # -------------------------------------------------
  if (!exists("ADL_weekly_history")) {
    stop("Object 'ADL_weekly_history' must exist before calling get_adl_playoff_picture().")
  }
  if (!exists("mfl_conns")) {
    stop("Global 'mfl_conns' (from load_mfl_conns()) must exist before calling get_adl_playoff_picture().")
  }
  
  history_df <- ADL_weekly_history %>% dplyr::filter(season <= !!season)
  
  # Clamp to regular-season max
  week_max <- min(week, max_week)
  
  # -------------------------------------------------
  # 1. Current season-to-date standings & live seeds
  # -------------------------------------------------
  standings_raw <- build_adl_weekly_results(season = season, week = week_max)
  snapshot_curr <- add_adl_playoff_snapshot(standings_raw)
  # snapshot_curr should have:
  #   qual, seed, h2h_wins, bonus_wins, total_wins,
  #   ap_wins_total, points_for, potential_points,
  #   conference, division, through_week, and raw W/L/T cols
  
  # -------------------------------------------------
  # 2. Prep inputs for Monte Carlo: sched + sd_points
  # -------------------------------------------------
  # 2a) Connection + schedule for this season
  season_suffix <- substr(as.character(season), 3, 4)  # 2025 -> "25"
  conn_name     <- paste0("ADL", season_suffix)        # "ADL25"
  
  mfl_conn <- adl_connection(season)
  if (is.null(mfl_conn)) {
    stop("No MFL connection named ", conn_name, " found in load_mfl_conns().")
  }
  
  sched_df <- adl_fetch("schedule", mfl_conn) %>%
    dplyr::select(week, franchise_id, opponent_id)
  
  history_df <- ADL_weekly_history %>% dplyr::filter(season <= !!season)
  
  # -------------------------------------------------
  # 3. Always call Monte Carlo helper
  #  - If week_max < max_week  => real simulation
  #  - If week_max >= max_week => special-case branch (actuals + 0/1 probs)
  # -------------------------------------------------
  
  if (week_max < max_week) {
    # SD of weekly points across history (simple overall average)
    sd_points <- history_df %>%
      dplyr::filter(week <= max_week) %>%
      dplyr::group_by(season, franchise_id) %>%
      dplyr::summarise(
        points_sd = sd(points_for_week, na.rm = TRUE),
        .groups   = "drop"
      ) %>%
      dplyr::summarise(
        overall_sd = mean(points_sd, na.rm = TRUE),
        .groups    = "drop"
      ) %>%
      dplyr::pull(overall_sd)
  } else {
    # Value is ignored in the completed-season shortcut
    sd_points <- 1
  }
  
  mc_res <- run_adl_monte_carlo(
    standings_df = snapshot_curr,
    history_df   = history_df,
    sched_df     = sched_df,
    sd_points    = sd_points,
    max_week     = max_week,
    n_sims       = n_bonus_sims
  )
  
  expected_points <- if (week_max < max_week) {
    predict(mc_res$mean_model_m3, newdata=data.frame(avg_pot=snapshot_curr$potential_points/week_max))
  } else rep(0, nrow(snapshot_curr))
  snapshot_curr$pred_points_for <- snapshot_curr$points_for + pmax(expected_points,0) * (max_week-week_max)
  snapshot_curr$pred_potential_points <- snapshot_curr$potential_points +
    (pmax(expected_points,0) + pmax((snapshot_curr$potential_points-snapshot_curr$points_for)/week_max,0)) * (max_week-week_max)
  team_pred <- mc_res$team_summary %>%
    dplyr::select(
      franchise_id,
      pred_ap_wins,
      pred_h2h_wins,
      pred_total_bonus,
      pred_total_wins,
      playoff_pct,
      divwin_pct,
      bye_pct
    )
  
  # Combine live standings with projections + probabilities
  snapshot_pred <- snapshot_curr %>%
    dplyr::left_join(team_pred, by = "franchise_id") %>%
    dplyr::mutate(
      # If MC fields are missing for whatever reason, fall back to actuals
      pred_ap_wins     = dplyr::coalesce(pred_ap_wins,     ap_wins_total),
      pred_h2h_wins    = dplyr::coalesce(pred_h2h_wins,    h2h_wins),
      pred_total_bonus = dplyr::coalesce(pred_total_bonus, bonus_wins),
      pred_total_wins  = dplyr::coalesce(pred_total_wins,  total_wins),
      playoff_pct      = dplyr::coalesce(playoff_pct, 0),
      divwin_pct       = dplyr::coalesce(divwin_pct,  0),
      bye_pct          = dplyr::coalesce(bye_pct,      0)
    )
  
  bonus_expect <- mc_res$bonus_expect
  weekly_h2h   <- mc_res$weekly_h2h
  
  # If bonus_expect uses older names, rename them (unchanged from your version)
  if (all(c("pred_Q1_bonus", "pred_Q2_bonus", "pred_Q3_bonus",
            "pred_Q4_bonus", "pred_RS_bonus") %in% names(bonus_expect))) {
    bonus_expect <- bonus_expect %>%
      dplyr::rename(
        pred_q1_bonus_wins = pred_Q1_bonus,
        pred_q2_bonus_wins = pred_Q2_bonus,
        pred_q3_bonus_wins = pred_Q3_bonus,
        pred_q4_bonus_wins = pred_Q4_bonus,
        pred_rs_bonus_wins = pred_RS_bonus
      )
  }
  
  
  # -------------------------------------------------
  # 4. Win% fields for projections
  # -------------------------------------------------
  n_teams        <- dplyr::n_distinct(snapshot_curr$franchise_id)
  ap_games_total <- (n_teams - 1L) * max_week
  final_games    <- 17L  # 12 H2H + 5 bonus events
  
  snapshot_pred <- snapshot_pred %>%
    dplyr::mutate(
      pred_win_pct = pred_total_wins / final_games,
      pred_ap_win_pct = if (ap_games_total > 0) {
        pred_ap_wins / ap_games_total
      } else {
        NA_real_
      }
    )
  
  # -------------------------------------------------
  # 5. Projected seeding (division winners + wildcards)
  # -------------------------------------------------
  projected_games <- sched_df %>% dplyr::filter(week <= max_week) %>%
    dplyr::left_join(weekly_h2h %>% tidyr::pivot_longer(-franchise_id, names_to="week_label", values_to="credit") %>%
                      dplyr::mutate(week=as.integer(stringr::str_extract(week_label, "[0-9]+"))),
                    by=c("franchise_id","week"))
  forecast_rank <- snapshot_pred %>% dplyr::transmute(
    franchise_id, conference, division, win_pct=pred_win_pct, ap_win_pct=pred_ap_win_pct,
    points_for=pred_points_for, potential_points=pred_potential_points) %>%
    adl_rank_playoffs(projected_games) %>%
    dplyr::transmute(franchise_id, pred_is_division_winner=is_division_winner,
      pred_is_wild_card=is_wild_card, pred_is_playoff_team=is_playoff_team,
      pred_playoff_seed=playoff_seed, pred_consol_seed=consol_seed, pred_finish=seed)
  snapshot_seeded <- dplyr::left_join(snapshot_pred, forecast_rank, by="franchise_id")

  # -------------------------------------------------
  # 6. Attach detailed Monte Carlo outputs (if present)
  # -------------------------------------------------
  if (!"franchise_id" %in% names(bonus_expect)) {
    bonus_expect <- tibble::tibble(franchise_id = snapshot_seeded$franchise_id)
  }
  if (!"franchise_id" %in% names(weekly_h2h)) {
    weekly_h2h <- tibble::tibble(franchise_id = snapshot_seeded$franchise_id)
  }
  
  snapshot_seeded <- snapshot_seeded %>%
    dplyr::left_join(bonus_expect, by = "franchise_id") %>%
    dplyr::left_join(weekly_h2h,   by = "franchise_id")
  
  # -------------------------------------------------
  # 7. Fill probabilities (MC or deterministic) + derived fields
  # -------------------------------------------------
  # If MC supplied playoff/div/bye probs, keep them;
  # otherwise, derive deterministic 1/0 from projected seeds & flags.
  snapshot_seeded <- snapshot_seeded %>%
    dplyr::mutate(
      playoff_pct = dplyr::if_else(
        !is.na(playoff_pct),
        playoff_pct,
        dplyr::if_else(pred_is_playoff_team, 1, 0, 0)
      ),
      divwin_pct = dplyr::if_else(
        !is.na(divwin_pct),
        divwin_pct,
        dplyr::if_else(pred_is_division_winner, 1, 0, 0)
      ),
      bye_pct = dplyr::if_else(
        !is.na(bye_pct),
        bye_pct,
        dplyr::if_else(pred_is_playoff_team & pred_playoff_seed == 1L, 1, 0, 0)
      )
    )
  
  # Record W-L-T from raw components
  snapshot_seeded <- snapshot_seeded %>%
    dplyr::mutate(
      wins_raw = dplyr::coalesce(h2h_wins_raw, 0)   + dplyr::coalesce(bonus_wins_raw, 0),
      loss_raw = dplyr::coalesce(h2h_losses_raw, 0) + dplyr::coalesce(bonus_losses_raw, 0),
      tie_raw  = dplyr::coalesce(h2h_ties_raw, 0)   + dplyr::coalesce(bonus_ties_raw, 0),
      record   = sprintf("%d-%d-%d", wins_raw, loss_raw, tie_raw)
    )
  
  # AP win% to date, PPG, Pot PPG
  snapshot_seeded <- snapshot_seeded %>%
    dplyr::mutate(
      ap_win_pct = dplyr::if_else(
        through_week > 0,
        ap_wins_total / ((n_teams - 1L) * through_week),
        NA_real_
      ),
      ppg      = dplyr::if_else(through_week > 0, points_for       / through_week, NA_real_),
      pot_ppg  = dplyr::if_else(through_week > 0, potential_points / through_week, NA_real_)
    )
  
  # Clinch flags
  snapshot_seeded <- snapshot_seeded %>%
    dplyr::mutate(
      clinch_division   = divwin_pct  >= 1 - 1e-9,
      clinch_bye        = bye_pct     >= 1 - 1e-9,
      clinch_playoffs   = playoff_pct >= 1 - 1e-9,
      eliminated_playoffs = playoff_pct <= 1e-9,
      clinch = dplyr::case_when(
        clinch_bye                      ~ "b",
        clinch_division                 ~ "d",
        clinch_playoffs                 ~ "p",
        eliminated_playoffs             ~ "e",
        TRUE                            ~ ""
      )
    )
  
  # -------------------------------------------------
  # 8. Data for the GRAPHIC helper (raw / machine names)
  # -------------------------------------------------
  snapshot_for_graphic <- snapshot_seeded %>%
    dplyr::mutate(
      entry     = qual,             # y/x flags for legend
      ap_wins   = ap_wins_total,    # convenience alias
      pred_wins = pred_total_wins   # convenience alias
    )
  
  # -------------------------------------------------
  # 9. Pretty, human-facing dataframe returned to you
  # -------------------------------------------------
  snapshot_final <- snapshot_seeded %>%
    dplyr::mutate(
      pred_total_wins = round(pred_total_wins, 2),
      pred_ap_wins    = round(pred_ap_wins,    1),
      APwin_display   = round(ap_win_pct,      3),
      PPG_display     = round(ppg,             1),
      PotPPG_display  = round(pot_ppg,         1)
    ) %>%
    dplyr::rename(
      Clinch         = clinch,
      Qual           = qual,
      Seed           = seed,
      Team           = franchise_name,
      Record         = record,
      `Total Wins`   = total_wins,
      `AP Wins`      = ap_wins_total,
      `Points For`   = points_for,
      `Potential Pts`= potential_points,
      `Pred. Wins`   = pred_total_wins,
      `Pred. AP Wins`= pred_ap_wins,
      `Pred. Finish` = pred_finish,
      `Playoff%`     = playoff_pct,
      `Div%`         = divwin_pct,
      `Bye%`         = bye_pct
    ) %>%
    dplyr::mutate(
      `APwin%`  = APwin_display,
      PPG       = PPG_display,
      `Pot. PPG`= PotPPG_display
    ) %>%
    dplyr::arrange(conference, Seed) %>%
    dplyr::relocate(
      Clinch, Qual, Seed, Team,
      Record,
      `Total Wins`, `AP Wins`, `APwin%`,
      PPG, `Pot. PPG`,
      `Pred. Wins`, `Pred. AP Wins`, `Pred. Finish`
    ) %>%
    # Keep conference & division at the end for grouping
    dplyr::relocate(conference, division, .after = dplyr::last_col())
  
  # -------------------------------------------------
  # 10. Attach attributes + write local HTML for preview
  # -------------------------------------------------
  # Basic attributes used by other helpers
  attr(snapshot_final, "snapshot_for_graphic") <- snapshot_for_graphic
  attr(snapshot_final, "season")               <- season
  attr(snapshot_final, "week")                 <- week_max
  
  # Also write the HTML for this week so you can preview it
  out_dir <- adl_output_dir()
  if (!dir.exists(out_dir)) dir.create(out_dir, recursive = TRUE)
  
  html_paths <- write_adl_week_html(
    snapshot     = snapshot_final,
    season       = season,
    week         = week_max,   # this week’s snapshot
    through_week = week_max,   # at preview time, this is the max completed week
    repo_dir     = out_dir
  )
  
  # Attach HTML paths so you can do:
  #   browseURL(attr(adl_playoff_picture, "html_file"))
  attr(snapshot_final, "html_file")    <- html_paths$week_file
  attr(snapshot_final, "full_df_file") <- html_paths$full_file
  
  snapshot_final
}





########################################################################
########### HTML HELPERS: Week dropdown + per-week pages ###############
########################################################################

# Build the <select> dropdown to jump between weeks
build_adl_week_dropdown <- function(season,
                                    through_week) {
  if (through_week <= 1L) {
    # Not enough weeks to bother with a dropdown
    return(NULL)
  }
  
  # Weeks 1..through_week, shown in DESC order
  week_indices <- rev(seq_len(through_week))
  
  # Build <option> tags like:  <option value="ADL_2025_W03_...">Week 3</option>
  option_tags <- lapply(week_indices, function(wk) {
    display_week <- wk + 1L  # your convention: "after Week {wk+1}"
    
    file_name <- sprintf(
      "ADL_%d_W%02d_playoff_and_draft_forecast.html",
      season, display_week
    )
    
    htmltools::tags$option(
      value = file_name,
      paste0("Week ", display_week)
    )
  })
  
  # Build the full <div> containing label + <select>
  select_tag <- do.call(
    htmltools::tags$select,
    c(
      list(
        id       = "week-select",
        onchange = "if (this.value) window.location.href=this.value;"
      ),
      list(
        # First option: placeholder "Select week..."
        htmltools::tags$option(value = "", "Select week...")
      ),
      option_tags
    )
  )
  
  htmltools::tags$div(
    style = "text-align:center; margin: 0 auto 1rem auto;",
    htmltools::tags$label(
      `for` = "week-select",
      "Jump to week: "
    ),
    select_tag
  )
}





# --------------------------------------------------------------------
# Write both HTML pages for a given week:
#   1) Playoff Picture & Draft Forecast page
#   2) Full Dataframe page
#
# This is what publish_adl_html_to_github() calls.
# --------------------------------------------------------------------
write_adl_week_html <- function(snapshot,
                                season,
                                week,
                                through_week,
                                repo_dir = adl_output_dir()) {
  if (!requireNamespace("htmltools", quietly = TRUE)) {
    stop("Package 'htmltools' is required for HTML output.")
  }
  
  if (!dir.exists(repo_dir)) dir.create(repo_dir, recursive = TRUE)
  
  # If present, this is the trimmed/graphic-ready version
  snapshot_for_graphic <- attr(snapshot, "snapshot_for_graphic")
  if (is.null(snapshot_for_graphic)) {
    # Fallback: use snapshot itself
    snapshot_for_graphic <- snapshot
  }
  
  # Display week = "after Week {week+1}"
  display_week <- week + 1L
  updated_at   <- format(Sys.time(), tz = "America/New_York", usetz = TRUE)
  
  # Dropdown: always includes ALL weeks up to through_week
  dropdown_tag <- build_adl_week_dropdown(
    season       = season,
    through_week = through_week
  )
  
  # Filenames are based on display_week (W02, W03, ..., W13)
  main_file_name <- sprintf(
    "ADL_%d_W%02d_playoff_and_draft_forecast.html",
    season, display_week
  )
  main_file_path <- file.path(repo_dir, main_file_name)
  
  full_df_file_name <- sprintf(
    "ADL_%d_W%02d_full_dataframe.html",
    season, display_week
  )
  full_df_file_path <- file.path(repo_dir, full_df_file_name)
  
  # ---- 1) Main Playoff Picture & Draft Forecast page ----
  source("scripts/render_playoff_picture.R", local = TRUE)
  main_page <- render_adl_playoff_page(snapshot_for_graphic, season, week,
                                       dropdown_tag, full_df_file_name, updated_at)
  writeLines(enc2utf8(main_page), main_file_path, useBytes = TRUE)

  # ---- 2) Full dataframe page ----
  full_df_gt <- gt::gt(snapshot) %>%
    gt::tab_header(
      title = glue::glue(
        "Full ADL Playoff / Forecast Data – Season {season}, Week {display_week}"
      )
    )
  
  full_df_html <- gt::as_raw_html(full_df_gt)
  
  full_df_page <- htmltools::tagList(
    htmltools::tags$head(
      htmltools::tags$meta(charset = "UTF-8"),
      htmltools::tags$meta(
        name    = "viewport",
        content = "width=device-width, initial-scale=1"
      ),
      htmltools::tags$title(
        sprintf(
          "ADL %d Week %d – Full Dataframe",
          season, display_week
        )
      ),
      htmltools::tags$style(htmltools::HTML(
        "body {
           font-family: system-ui, -apple-system, BlinkMacSystemFont,
                        'Segoe UI', sans-serif;
           margin: 0;
           padding: 1rem;
         }
         h2 {
           text-align: center;
           margin-bottom: 0.5rem;
         }
         .content-wrapper {
           max-width: 1200px;
           margin: 0 auto;
         }
         @media (max-width: 768px) {
           body {
             padding: 0.5rem;
           }
         }"
      ))
    ),
    htmltools::tags$body(
      htmltools::tags$div(
        class = "content-wrapper",
        htmltools::tags$h2(
          sprintf(
            "ADL %d Week %d – Full Dataframe",
            season, display_week
          )
        ),
        htmltools::tags$p(
          class = "timestamp",
          sprintf("Last updated: %s", updated_at)
        ),
        htmltools::tags$p(
          htmltools::tags$a(
            href = main_file_name,
            "← Back to playoff picture & draft forecast"
          )
        ),
        
        # Same dropdown on the full-data page
        if (!is.null(dropdown_tag)) dropdown_tag,
        
        htmltools::tags$div(
          style = "max-width: 100%; overflow-x: auto;",
          htmltools::HTML(full_df_html)
        )
      )
    )
  )
  
  htmltools::save_html(full_df_page, file = full_df_file_path)
  
  invisible(list(
    week_file    = main_file_path,
    full_df_file = full_df_file_path
  ))
}




# Build ALL weeks (1..weeks_completed) + set latest as index.html
build_adl_archive_pages <- function(season,
                                    weeks_completed,
                                    out_dir = adl_output_dir()) {
  if (!dir.exists(out_dir)) dir.create(out_dir, recursive = TRUE)
  
  snapshots      <- list()
  last_main_file <- NULL
  
  for (wk in seq_len(weeks_completed)) {
    message("Building ADL HTML for season ", season, ", week ", wk, " ...")
    
    snapshot_df <- get_adl_playoff_picture(season = season, week = wk)
    snapshots[[as.character(wk)]] <- snapshot_df
    
    res <- write_adl_week_html(
      snapshot                     = snapshot_df,
      season                       = season,
      through_week                 = weeks_completed,
      week                         = wk,
      repo_dir                     = out_dir
    )
    
    if (wk == weeks_completed) {
      last_main_file <- res$week_file
    }
  }
  
  if (!is.null(last_main_file) && file.exists(last_main_file)) {
    index_path <- file.path(out_dir, "index.html")
    file.copy(last_main_file, index_path, overwrite = TRUE)
    message("Copied latest week to ", index_path)
  }
  
  invisible(list(
    last_main_file = last_main_file,
    snapshots      = snapshots
  ))
}



########################################################################
########### Function to Publish to GitHub ##############################
########################################################################

publish_adl_html_to_github <- function(
    season,
    through_week,
    repo_dir        = adl_output_dir(),
    rebuild_archive = c("none", "last", "all")  # unified control: "none", "last", "all"
) {
  rebuild_archive <- match.arg(rebuild_archive)
  
  old_wd <- getwd()
  on.exit(setwd(old_wd), add = TRUE)
  setwd(repo_dir)
  
  # ------------------------------------------------------------------
  # 0. Inspect timestamps from last run so you can make decisions
  # ------------------------------------------------------------------
  # Files are named by *display week* = wk + 1, e.g. W02, W03, ... W13
  week_file_name <- function(wk) {
    display_week <- wk + 1L
    sprintf("ADL_%d_W%02d_playoff_and_draft_forecast.html", season, display_week)
  }
  
  last_week      <- through_week - 1L
  this_week_file <- file.path(repo_dir, week_file_name(through_week))
  last_week_file <- if (last_week >= 1L) file.path(repo_dir, week_file_name(last_week)) else NA_character_
  
  this_week_time <- if (file.exists(this_week_file)) file.info(this_week_file)$mtime else NA
  last_week_time <- if (!is.na(last_week_file) && file.exists(last_week_file)) file.info(last_week_file)$mtime else NA
  
  message("Last published files (if any):")
  message("  This week (W", sprintf("%02d", through_week + 1L), "): ",
          if (is.na(this_week_time)) "none" else format(this_week_time))
  if (!is.na(last_week_file)) {
    message("  Last week (W", sprintf("%02d", last_week + 1L), "): ",
            if (is.na(last_week_time)) "none" else format(last_week_time))
  }
  
  # ------------------------------------------------------------------
  # 1. Decide which weeks to rebuild based on "none" / "last" / "all"
  # ------------------------------------------------------------------
  if (rebuild_archive == "all") {
    weeks_to_build <- seq_len(through_week)
    message("Rebuilding FULL ARCHIVE for season ", season, ": weeks ",
            paste(sprintf("W%02d", weeks_to_build), collapse = ", "))
    
  } else if (rebuild_archive == "last" && through_week > 1L) {
    weeks_to_build <- c(through_week - 1L, through_week)
    message("Rebuilding LAST WEEK + CURRENT WEEK for season ", season, ": weeks ",
            paste(sprintf("W%02d", weeks_to_build), collapse = ", "))
    
  } else {
    weeks_to_build <- through_week
    message("Building CURRENT WEEK ONLY for season ", season,
            ": W", sprintf("%02d", through_week))
  }
  
  # ------------------------------------------------------------------
  # 2. Build HTML for the selected weeks
  # ------------------------------------------------------------------
  latest_snapshot <- NULL
  
  for (wk in weeks_to_build) {
    message(sprintf("  - Building archive HTML for week %d ...", wk))
    
    snapshot <- get_adl_playoff_picture(
      season = season,
      week   = wk
    )
    
    # Save full week HTML + full dataframe HTML
    html_files <- write_adl_week_html(
      snapshot     = snapshot,
      season       = season,
      week         = wk,
      through_week = through_week,  # << THIS is the key fix
      repo_dir     = repo_dir
    )
    
    if (wk == through_week) {
      latest_snapshot <- snapshot
      index_file <- file.path(repo_dir, "index.html")
      file.copy(from = html_files$week_file, to = index_file, overwrite = TRUE)
      message("Copied latest week to ", index_file)
    }
  }
  
  
  # ------------------------------------------------------------------
  # 3. Git: add, commit, push
  # ------------------------------------------------------------------
  system("git add -- *.html")
  
  commit_message <- glue::glue(
    "Update ADL playoff picture archive: season {season}, through week {through_week} ({Sys.time()})"
  )
  
  run_git <- function(cmd) {
    res <- system(glue::glue("git {cmd}"), intern = TRUE, ignore.stderr = FALSE)
    attr(res, "status")
  }
  
  status_commit <- run_git(paste("commit --only -m", shQuote(commit_message), "-- *.html"))
  if (!is.null(status_commit) && status_commit != 0) {
    stop("Git command failed (exit code ", status_commit,
         "): git commit -m ", shQuote(commit_message))
  }
  
  status_push <- run_git("push origin main")
  if (!is.null(status_push) && status_push != 0) {
    stop("Git command failed (exit code ", status_push, "): git push origin main")
  }
  
  invisible(
    list(
      latest_snapshot = latest_snapshot,
      this_week_file  = this_week_file,
      last_week_file  = last_week_file,
      this_week_time  = this_week_time,
      last_week_time  = last_week_time,
      weeks_built     = weeks_to_build
    )
  )
}





# Run from the ADL-GM-Dashboard repository root:
# Rscript scripts/get_adl_playoff_picture.R 2026 1
# Arguments: season, completed week (1..12). Sourcing only defines functions.
# The training cache holds completed seasons; current-season data is refreshed each run.
run_adl_playoff_picture <- function(season = 2026L, weeks_completed = 1L,
                                   out_dir = adl_output_dir(),
                                   cache_dir = file.path("cache", "playoff-picture"),
                                   rebuild_archive = TRUE, n_sims = 3000L) {
  valid_integer <- function(x, lo, hi) {
    is.numeric(x) && length(x) == 1L && !is.na(x) && is.finite(x) &&
      x == as.integer(x) && x >= lo && x <= hi
  }
  if (!valid_integer(season, 2022L, 2100L)) stop("season must be an integer from 2022 to 2100.")
  if (!valid_integer(weeks_completed, 1L, adl_max_week)) stop("weeks_completed must be from 1 to 12.")
  if (!valid_integer(n_sims, 1L, 1000000L)) stop("n_sims must be a positive integer.")
  old_options <- options(adl.output_dir = out_dir, adl.n_sims = n_sims)
  on.exit(options(old_options), add = TRUE)
  rm(list = ls(adl_fetch_cache), envir = adl_fetch_cache)
  dir.create(cache_dir, recursive = TRUE, showWarnings = FALSE)
  history <- lapply(seq.int(2021L, season - 1L), function(year) {
    path <- file.path(cache_dir, sprintf("ADL_weekly_history_%d.rds", year))
    if (file.exists(path)) return(readRDS(path))
    seed_path <- file.path("data", "playoff_history", basename(path))
    if (file.exists(seed_path)) {
      value <- readRDS(seed_path)
      saveRDS(value, path)
      return(value)
    }
    value <- build_adl_weekly_history(year, max_week = adl_max_week)
    if (nrow(value) != 32L * adl_max_week || anyNA(value$points_for_week)) {
      stop("Incomplete training history for ", year, "; cache was not saved.")
    }
    saveRDS(value, path)
    value
  })
  current <- build_adl_weekly_history(season, max_week = weeks_completed)
  if (nrow(current) != 32L * weeks_completed || anyNA(current$points_for_week) ||
      any(current %>% dplyr::group_by(week) %>%
          dplyr::summarise(points = sum(points_for_week), .groups = "drop") %>%
          dplyr::pull(points) <= 0)) {
    stop("Current-season scores are incomplete; use the last completed week.")
  }
  ADL_weekly_history <<- dplyr::bind_rows(history, list(current))
  set.seed(2026)
  if (rebuild_archive) {
    result <- build_adl_archive_pages(season, weeks_completed, out_dir)
    return(invisible(result))
  }
  snapshot <- get_adl_playoff_picture(season, weeks_completed)
  file.copy(attr(snapshot, "html_file"), file.path(out_dir, "index.html"), overwrite = TRUE)
  invisible(snapshot)
}

if (sys.nframe() == 0L) {
  args <- commandArgs(trailingOnly = TRUE)
  season <- if (length(args) >= 1L) as.numeric(args[[1]]) else 2026L
  weeks_completed <- if (length(args) >= 2L) as.numeric(args[[2]]) else 1L
  run_adl_playoff_picture(season, weeks_completed)
}
