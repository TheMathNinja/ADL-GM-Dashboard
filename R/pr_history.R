source("R/pr_completed_seasons.R")
source("R/pr_partial_robust.R")
adl_score_cache_dir <- Sys.getenv(
  "ADL_RAW_LEAGUE_DATA_DIR",
  unset = "C:/Users/Michael/Documents/R/FFAucAndDraft/RawLeagueData"
)

round_rank_half <- function(x) {
  round(as.numeric(x) * 2) / 2
}

add_pr_player_teams <- function(rows, cache_dir = adl_score_cache_dir, identity_path = "data/pr_player_identity.csv") {
  if (!"player_team" %in% names(rows)) rows$player_team <- rep(NA_character_, nrow(rows))
  # Preserve raw as-of-week teams; backfill older seasons whose raw caches are not hosted.
  if (file.exists(identity_path)) {
    identities <- read.csv(identity_path, colClasses = c("integer", "character", "character"))
    if (!all(c("season", "player_id", "player_team") %in% names(identities)) ||
        anyDuplicated(identities[c("season", "player_id")])) stop("Invalid cached PR player identities.")
    index <- which(is.na(rows$player_team) | !nzchar(rows$player_team))
    teams <- identities$player_team[match(paste(rows$season[index], rows$player_id[index]),
      paste(identities$season, identities$player_id))]
    found <- !is.na(teams) & nzchar(teams)
    rows$player_team[index[found]] <- teams[found]
  }
  for (season in unique(rows$season[!is.na(rows$season)])) {
    path <- file.path(cache_dir, sprintf("mfl_players_ADL%02d_%d_raw.rds", season %% 100L, season))
    if (!file.exists(path)) next
    players <- readRDS(path)
    id_column <- intersect(c("player_id", "id"), names(players))
    if (!length(id_column) || !"team" %in% names(players)) stop("Invalid cached MFL player identity data: ", path)
    index <- which(rows$season == season & (is.na(rows$player_team) | !nzchar(rows$player_team)))
    if (!length(index)) next
    teams <- trimws(as.character(players$team[match(as.character(rows$player_id[index]), as.character(players[[id_column[[1]]]]))]))
    found <- !is.na(teams) & nzchar(teams)
    rows$player_team[index[found]] <- teams[found]
  }
  rows
}

collapse_player_score_rows <- function(score_rows) {
  if (!"player_team" %in% names(score_rows)) {
    score_rows$player_team <- if ("team" %in% names(score_rows)) as.character(score_rows$team) else rep(NA_character_, nrow(score_rows))
  }
  score_rows |>
    dplyr::arrange(.data$season, .data$week, .data$player_id, .data$pos) |>
    dplyr::group_by(.data$season, .data$week, .data$player_id, .data$pos) |>
    dplyr::summarise(
      player_name = dplyr::last(.data$player_name),
      player_team = dplyr::last(.data$player_team),
      points = max(.data$points, na.rm = TRUE),
      .groups = "drop"
    ) |>
    dplyr::mutate(points = dplyr::if_else(is.infinite(.data$points), NA_real_, .data$points))
}

summarise_player_pr_scores <- function(score_rows) {
  collapse_player_score_rows(score_rows) |>
    dplyr::arrange(.data$season, .data$player_id, .data$pos, .data$week) |>
    dplyr::group_by(.data$season, .data$player_id, .data$pos) |>
    dplyr::summarise(
      player_name = dplyr::last(.data$player_name),
      player_team = dplyr::last(.data$player_team),
      gp = dplyr::n_distinct(.data$week),
      total_points = sum(.data$points, na.rm = TRUE),
      ppg = dplyr::if_else(.data$gp > 0, .data$total_points / .data$gp, NA_real_),
      .groups = "drop"
    )
}

latest_score_cache_file <- function(cache_dir = adl_score_cache_dir, season = get_current_season()) {
  metadata_path <- "data/score_metadata.csv"
  if (file.exists(metadata_path) && identical(normalizePath(cache_dir, mustWork = FALSE), normalizePath(adl_score_cache_dir, mustWork = FALSE))) {
    metadata <- read.csv(metadata_path)
    if (nrow(metadata) == 1L && metadata$season[[1]] == season) {
      source("R/ext_score_freshness.R")
      assert_ext_score_cache_current(metadata_path)
      return(metadata$scores_path[[1]])
    }
  }
  files <- list.files(
    cache_dir,
    pattern = paste0("^ff_playerscores_ADL[0-9]{2}_", season, "_W1-[0-9]+_raw[.]rds$"),
    full.names = TRUE
  )
  if (!length(files)) return(NA_character_)

  end_week <- suppressWarnings(as.integer(sub("^.*_W1-([0-9]+)_raw[.]rds$", "\\1", files)))
  files[[which.max(end_week)]]
}

build_weekly_pr_snapshots <- function(
  cache_dir = adl_score_cache_dir,
  season = get_current_season(),
  output_path = file.path("data", "pr_weekly_snapshots.csv")
) {
  source_file <- latest_score_cache_file(cache_dir, season)
  if (is.na(source_file) || !file.exists(source_file)) {
    warning("No current-season ADL player score cache found in ", cache_dir, call. = FALSE)
    return(tibble::tibble())
  }

  score_rows <- readRDS(source_file) |>
    dplyr::mutate(
      season = as.integer(.data$season),
      week = as.integer(.data$week),
      player_id = as.character(.data$player_id),
      player_name = as.character(.data$player_name),
      pos = as.character(.data$pos),
      points = as.numeric(.data$points)
    ) |>
    dplyr::filter(
      .data$season == .env$season,
      !is.na(.data$player_id),
      !is.na(.data$week),
      .data$pos %in% c("QB", "RB", "WR", "TE", "PK", "PN", "DT", "DE", "LB", "CB", "S")
    )

  if ("is_available" %in% names(score_rows)) {
    score_rows <- score_rows |>
      dplyr::filter(is.na(.data$is_available) | as.character(.data$is_available) %in% c("1", "TRUE", "true"))
  }

  latest_week <- suppressWarnings(max(score_rows$week, na.rm = TRUE))
  if (!is.finite(latest_week)) return(tibble::tibble())

  snapshots <- dplyr::bind_rows(lapply(seq_len(latest_week), function(snapshot_week) {
    score_rows |>
      dplyr::filter(.data$week <= .env$snapshot_week) |>
      summarise_player_pr_scores() |>
      dplyr::group_by(.data$season, .data$pos) |>
      dplyr::mutate(
        pr_total = round_rank_half(rank(-.data$total_points, na.last = "keep")),
        pr_avg = round_rank_half(rank(-.data$ppg, na.last = "keep")),
        pr_final = pmin(.data$pr_total, .data$pr_avg, na.rm = TRUE),
        robust_pr = .data$gp >= 8 & !is.na(.data$pr_final),
        snapshot_week = .env$snapshot_week
      ) |>
      dplyr::ungroup() |>
      dplyr::mutate(pr_final = dplyr::if_else(is.infinite(.data$pr_final), NA_real_, .data$pr_final)) |>
      apply_partial_robust_ppg_ranks(season, snapshot_week)
  })) |>
    dplyr::arrange(.data$snapshot_week, .data$pos, .data$pr_final, .data$player_name)

  dir.create(dirname(output_path), showWarnings = FALSE, recursive = TRUE)
  final_rows <- snapshots$snapshot_week >= 17L
  if (any(final_rows)) snapshots[final_rows, ] <- apply_completed_season_ppg_ranks(snapshots[final_rows, ])
  snapshots <- add_pr_player_teams(snapshots, cache_dir)
  readr::write_csv(snapshots, output_path)
  snapshots
}

find_adl_score_cache_files <- function(cache_dir = adl_score_cache_dir, last_season = get_current_season() - 1L) {
  files <- list.files(
    cache_dir,
    pattern = "^ff_playerscores_ADL[0-9]{2}_[0-9]{4}_W1-[0-9]+_raw[.]rds$",
    full.names = TRUE
  )

  if (!length(files)) return(character())

  seasons <- suppressWarnings(as.integer(sub("^.*_([0-9]{4})_W1-[0-9]+_raw[.]rds$", "\\1", files)))
  files[!is.na(seasons) & seasons <= last_season]
}

pr_cache_is_fresh <- function(output_path, source_files) {
  if (!file.exists(output_path) || !length(source_files)) return(FALSE)
  max(file.info(source_files)$mtime, na.rm = TRUE) <= file.info(output_path)$mtime
}

build_robust_pr_history <- function(
  cache_dir = adl_score_cache_dir,
  last_season = get_current_season() - 1L,
  output_path = file.path("data", "pr_history.csv")
) {
  source_files <- find_adl_score_cache_files(cache_dir, last_season)
  if (last_season >= get_current_season()) {
    latest <- latest_score_cache_file(cache_dir, last_season)
    source_files <- if (is.na(latest)) character() else latest
  }
  if (!length(source_files)) {
    warning("No ADL player score cache files found in ", cache_dir, call. = FALSE)
    return(tibble::tibble())
  }

  dir.create(dirname(output_path), showWarnings = FALSE, recursive = TRUE)
  if (last_season < get_current_season() && pr_cache_is_fresh(output_path, source_files)) {
    cached <- readr::read_csv(output_path, show_col_types = FALSE)
    if (!anyDuplicated(cached[c("season", "player_id", "pos")])) {
      cached <- apply_completed_season_ppg_ranks(cached)
      cached <- add_pr_player_teams(cached, cache_dir)
      readr::write_csv(cached, output_path)
      return(cached)
    }
  }

  score_rows <- dplyr::bind_rows(lapply(source_files, readRDS)) |>
    dplyr::mutate(
      season = as.integer(.data$season),
      week = as.integer(.data$week),
      player_id = as.character(.data$player_id),
      player_name = as.character(.data$player_name),
      pos = as.character(.data$pos),
      points = as.numeric(.data$points)
    ) |>
    dplyr::filter(!is.na(.data$player_id), !is.na(.data$season), !is.na(.data$week))

  if ("is_available" %in% names(score_rows)) {
    score_rows <- score_rows |>
      dplyr::filter(is.na(.data$is_available) | as.character(.data$is_available) %in% c("1", "TRUE", "true"))
  }

  pr_history <- score_rows |>
    summarise_player_pr_scores() |>
    dplyr::filter(.data$pos %in% c("QB", "RB", "WR", "TE", "PK", "PN", "DT", "DE", "LB", "CB", "S")) |>
    dplyr::group_by(.data$season, .data$pos) |>
    dplyr::mutate(
      pr_total = round_rank_half(rank(-.data$total_points, na.last = "keep")),
      pr_avg = round_rank_half(rank(-.data$ppg, na.last = "keep")),
      pr_final = pmin(.data$pr_total, .data$pr_avg, na.rm = TRUE),
      robust_pr = .data$gp >= 8 & !is.na(.data$pr_final)
    ) |>
    dplyr::ungroup() |>
    dplyr::mutate(
      pr_final = dplyr::if_else(is.infinite(.data$pr_final), NA_real_, .data$pr_final)
    ) |>
    dplyr::arrange(.data$season, .data$pos, .data$pr_final, .data$player_name)

  rebuilt_seasons <- unique(pr_history$season)
  if (file.exists(output_path)) {
    existing_history <- tryCatch(
      readr::read_csv(output_path, show_col_types = FALSE),
      error = function(e) tibble::tibble()
    )

    if (nrow(existing_history) && "season" %in% names(existing_history)) {
      existing_history <- existing_history |>
        dplyr::mutate(
          season = as.integer(.data$season),
          player_id = as.character(.data$player_id),
          player_name = as.character(.data$player_name),
          pos = as.character(.data$pos),
          gp = as.integer(.data$gp),
          total_points = as.numeric(.data$total_points),
          ppg = as.numeric(.data$ppg),
          pr_total = as.numeric(.data$pr_total),
          pr_avg = as.numeric(.data$pr_avg),
          pr_final = as.numeric(.data$pr_final),
          robust_pr = as.logical(.data$robust_pr)
        ) |>
        dplyr::filter(!.data$season %in% .env$rebuilt_seasons)

      pr_history <- dplyr::bind_rows(existing_history, pr_history) |>
        dplyr::arrange(.data$season, .data$pos, .data$pr_final, .data$player_name)
    }
  }

  current_rows <- pr_history$season == get_current_season()
  if (any(current_rows) && any(score_rows$season == get_current_season())) {
    current_week <- max(score_rows$week[score_rows$season == get_current_season()], na.rm = TRUE)
    current <- apply_partial_robust_ppg_ranks(pr_history[current_rows, ], get_current_season(), current_week)
    pr_history <- dplyr::bind_rows(pr_history[!current_rows, ], current)
  }
  pr_history <- apply_completed_season_ppg_ranks(pr_history)
  pr_history <- add_pr_player_teams(pr_history, cache_dir)
  readr::write_csv(pr_history, output_path)
  pr_history
}

build_ext_pr_summary <- function(
  cache_dir = adl_score_cache_dir,
  last_season = get_current_season() - 1L,
  history_path = file.path("data", "pr_history.csv"),
  output_path = file.path("data", "ext_pr_summary.csv")
) {
  source_files <- find_adl_score_cache_files(cache_dir, last_season)
  if (last_season >= get_current_season()) {
    latest <- latest_score_cache_file(cache_dir, last_season)
    source_files <- if (is.na(latest)) character() else latest
  }
  pr_history <- build_robust_pr_history(cache_dir, last_season, history_path)
  if (!nrow(pr_history)) return(tibble::tibble())

  robust <- pr_history |>
    dplyr::filter(.data$robust_pr) |>
    dplyr::arrange(.data$player_id, dplyr::desc(.data$season)) |>
    dplyr::group_by(.data$player_id) |>
    dplyr::mutate(robust_pr_order = dplyr::row_number()) |>
    dplyr::ungroup()

  robust_counts <- robust |>
    dplyr::group_by(.data$player_id) |>
    dplyr::summarise(robust_pr_count = dplyr::n(), .groups = "drop")

  current <- pr_history |>
    dplyr::filter(.data$season == .env$last_season) |>
    dplyr::transmute(
      player_id,
      pr_current_season = .data$season,
      pr_current_pos = .data$pos,
      pr_current_total = .data$pr_total,
      pr_current_avg = .data$pr_avg,
      pr_current_final = .data$pr_final,
      pr_current_gp = .data$gp,
      pr_current_robust = .data$robust_pr
    )

  recent <- robust |>
    dplyr::filter(.data$robust_pr_order == 1L) |>
    dplyr::transmute(
      player_id,
      pr_recent_season = .data$season,
      pr_recent_pos = .data$pos,
      pr_recent_total = .data$pr_total,
      pr_recent_avg = .data$pr_avg,
      pr_recent_final = .data$pr_final,
      pr_recent_gp = .data$gp
    )

  previous <- robust |>
    dplyr::filter(.data$robust_pr_order == 2L) |>
    dplyr::transmute(
      player_id,
      pr_previous_season = .data$season,
      pr_previous_pos = .data$pos,
      pr_previous_total = .data$pr_total,
      pr_previous_avg = .data$pr_avg,
      pr_previous_final = .data$pr_final,
      pr_previous_gp = .data$gp
    )

  summary <- robust_counts |>
    dplyr::full_join(current, by = "player_id") |>
    dplyr::left_join(recent, by = "player_id") |>
    dplyr::left_join(previous, by = "player_id")

  readr::write_csv(summary, output_path)
  summary
}
