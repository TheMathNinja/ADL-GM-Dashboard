adl_score_cache_dir <- Sys.getenv(
  "ADL_RAW_LEAGUE_DATA_DIR",
  unset = "C:/Users/Michael/Documents/R/FFAucAndDraft/RawLeagueData"
)

round_rank_half <- function(x) {
  round(as.numeric(x) * 2) / 2
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
  if (!length(source_files)) {
    warning("No ADL player score cache files found in ", cache_dir, call. = FALSE)
    return(tibble::tibble())
  }

  dir.create(dirname(output_path), showWarnings = FALSE, recursive = TRUE)
  if (pr_cache_is_fresh(output_path, source_files)) {
    return(readr::read_csv(output_path, show_col_types = FALSE))
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
    dplyr::group_by(.data$season, .data$player_id, .data$player_name, .data$pos) |>
    dplyr::summarise(
      gp = dplyr::n_distinct(.data$week),
      total_points = sum(.data$points, na.rm = TRUE),
      ppg = dplyr::if_else(.data$gp > 0, .data$total_points / .data$gp, NA_real_),
      .groups = "drop"
    ) |>
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
  if (!length(source_files) && file.exists(output_path)) {
    cached <- readr::read_csv(output_path, show_col_types = FALSE)
    if ("pr_current_pos" %in% names(cached)) {
      return(cached)
    }
  }

  if (pr_cache_is_fresh(output_path, c(source_files, history_path))) {
    cached <- readr::read_csv(output_path, show_col_types = FALSE)
    if ("pr_current_pos" %in% names(cached)) {
      return(cached)
    }
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
