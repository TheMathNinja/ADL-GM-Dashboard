partial_robust_min_games <- function(season, week, schedule_path = file.path("data", paste0("nfl_schedule_", season, ".csv"))) {
  stopifnot(length(week) == 1L, !is.na(week), week >= 0L, week <= 17L)
  if (week == 0L) return(0L)
  if (!file.exists(schedule_path)) stop("Missing cached NFL schedule for partial-robust PPG ranks.")
  schedule <- read.csv(schedule_path, stringsAsFactors = FALSE)
  required <- c("season", "week", "mfl_team", "is_bye")
  if (!all(required %in% names(schedule))) stop("Invalid cached NFL schedule.")
  schedule <- schedule[schedule$season == season & schedule$week %in% seq_len(week), required]
  if (anyNA(schedule) || anyDuplicated(schedule[c("week", "mfl_team")]) ||
      nrow(schedule) != 32L * week || length(unique(schedule$mfl_team)) != 32L ||
      any(table(schedule$week) != 32L)) stop("Incomplete cached NFL schedule for selected EXT week.")
  games <- table(schedule$mfl_team[!as.logical(schedule$is_bye)])
  as.integer(ceiling(max(games) / 2))
}

personalized_ppg_ranks <- function(ppg, gp, minimum) {
  qualified <- !is.na(gp) & gp >= minimum & is.finite(ppg)
  pool <- ppg[qualified]
  vapply(seq_along(ppg), function(i) {
    if (!is.finite(ppg[[i]])) return(NA_real_)
    # Insert only this player if unqualified; do not rank other short performances.
    1 + sum(pool > ppg[[i]]) + (sum(pool == ppg[[i]]) - as.integer(qualified[[i]])) / 2
  }, numeric(1))
}

apply_partial_robust_ppg_ranks <- function(rows, season, week) {
  if (!nrow(rows)) return(rows)
  minimum <- partial_robust_min_games(season, week)
  rows |>
    dplyr::group_by(.data$season, .data$pos) |>
    dplyr::mutate(
      partial_robust_min_games = minimum,
      partial_robust = !is.na(.data$gp) & .data$gp >= minimum,
      pr_avg = personalized_ppg_ranks(.data$ppg, .data$gp, minimum),
      pr_final = pmin(.data$pr_total, .data$pr_avg, na.rm = TRUE)
    ) |>
    dplyr::ungroup()
}
