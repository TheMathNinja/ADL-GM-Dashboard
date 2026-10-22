completed_pr_seasons <- function(seasons, active_season, metadata_path = "data/score_metadata.csv") {
  complete <- as.integer(seasons) < as.integer(active_season)
  if (file.exists(metadata_path)) {
    metadata <- tryCatch(read.csv(metadata_path), error = function(e) data.frame())
    if (nrow(metadata) == 1L && all(c("season", "week", "official_week") %in% names(metadata)) &&
        isTRUE(metadata$season[[1]] == active_season && metadata$week[[1]] >= 17L && metadata$official_week[[1]] >= 17L)) {
      complete <- complete | as.integer(seasons) == as.integer(active_season)
    }
  }
  !is.na(complete) & complete
}

apply_completed_season_ppg_ranks <- function(history, active_season = get_current_season(),
                                            metadata_path = "data/score_metadata.csv") {
  if (!nrow(history)) return(history)
  history |>
    dplyr::mutate(
      .completed_pr_season = completed_pr_seasons(.data$season, active_season, metadata_path),
      .ppg_pool = dplyr::if_else(.data$gp >= 8L, as.numeric(.data$ppg), NA_real_)
    ) |>
    dplyr::group_by(.data$season, .data$pos) |>
    dplyr::mutate(
      pr_avg = dplyr::if_else(.data$.completed_pr_season,
        round(rank(-.data$.ppg_pool, na.last = "keep") * 2) / 2, as.numeric(.data$pr_avg)),
      pr_final = dplyr::if_else(.data$.completed_pr_season,
        pmin(.data$pr_total, .data$pr_avg, na.rm = TRUE), as.numeric(.data$pr_final))
    ) |>
    dplyr::ungroup() |>
    dplyr::select(-dplyr::all_of(c(".completed_pr_season", ".ppg_pool")))
}
