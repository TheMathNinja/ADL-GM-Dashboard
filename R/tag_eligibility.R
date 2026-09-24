library(dplyr)
library(readr)
library(tibble)

adl_vet_min <- c(
  `2020` = 0.8, `2021` = 0.9, `2022` = 0.9, `2023` = 0.9,
  `2024` = 1.0, `2025` = 1.0, `2026` = 1.1, `2027` = 1.1,
  `2028` = 1.2, `2029` = 1.2, `2030` = 1.3
)

compound_vet_min <- function(year_signed, season) {
  year_signed <- suppressWarnings(as.integer(year_signed))
  season <- suppressWarnings(as.integer(season))
  if (is.na(year_signed) || is.na(season) || year_signed > season) return(NA_real_)
  value <- unname(adl_vet_min[as.character(year_signed)])
  if (is.na(value)) return(NA_real_)
  if (season > year_signed) {
    for (i in seq_len(season - year_signed)) value <- round(value * 1.10, 2)
  }
  value
}

completed_week_from_metadata <- function(path = file.path("data", "score_metadata.csv")) {
  if (!file.exists(path)) return(0L)
  metadata <- tryCatch(read_csv(path, show_col_types = FALSE), error = function(e) tibble())
  week_col <- intersect(c("completed_week", "week", "scored_through_week"), names(metadata))
  if (!length(week_col) || !nrow(metadata)) return(0L)
  week <- suppressWarnings(max(as.integer(metadata[[week_col[[1]]]]), na.rm = TRUE))
  if (!is.finite(week)) 0L else max(0L, min(17L, week))
}

refresh_tag_roster_history <- function(season, completed_week, force_live = FALSE) {
  path <- file.path("data", paste0("tag_roster_weeks_", season, ".csv"))
  history <- if (file.exists(path)) {
    read_csv(path, col_types = cols(.default = col_character()), show_col_types = FALSE) |>
      mutate(season = as.integer(.data$season), week = as.integer(.data$week))
  } else {
    tibble(
      season = integer(), week = integer(), conference = character(),
      player_id = character(), roster_status = character()
    )
  }

  if (!isTRUE(force_live) || completed_week < 1L) return(history)
  missing_weeks <- setdiff(seq_len(completed_week), unique(history$week[history$season == season]))
  if (!length(missing_weeks)) return(history)

  additions <- lapply(missing_weeks, function(week) {
    tryCatch(
      fetch_live_rosters(season = season, week = week) |>
        transmute(
          season = .env$season,
          week = .env$week,
          conference = .data$conference,
          player_id = as.character(.data$player_id),
          roster_status = .data$roster_status
        ),
      error = function(e) {
        message("Could not cache tag-eligibility roster for week ", week, ": ", conditionMessage(e))
        tibble()
      }
    )
  })

  history <- bind_rows(history, bind_rows(additions)) |>
    distinct(.data$season, .data$week, .data$conference, .data$player_id, .keep_all = TRUE) |>
    arrange(.data$season, .data$week, .data$conference, .data$player_id)
  write_csv(history, path, na = "")
  history
}

build_next_season_tag_eligibility <- function(rosters, season, force_live = FALSE) {
  baseline_path <- file.path("data", paste0("tag_accrual_baseline_", season, ".csv"))
  baseline <- if (file.exists(baseline_path)) {
    read_csv(baseline_path, col_types = cols(.default = col_character()), show_col_types = FALSE) |>
      transmute(
        conference = .data$conference,
        player_id = as.character(.data$player_id),
        prior_accrued_seasons = as.integer(.data$prior_accrued_seasons)
      )
  } else {
    tibble(conference = character(), player_id = character(), prior_accrued_seasons = integer())
  }

  completed_week <- completed_week_from_metadata()
  project_current_accrual <- completed_week < 17L
  history <- refresh_tag_roster_history(season, completed_week, force_live = force_live)
  current_accrual <- history |>
    filter(
      .data$season == .env$season,
      .data$roster_status %in% c("Active", "ROSTER", "INJURED_RESERVE", "IR")
    ) |>
    distinct(.data$conference, .data$player_id, .data$week) |>
    count(.data$conference, .data$player_id, name = "eligible_roster_weeks") |>
    mutate(current_season_accrued = .data$eligible_roster_weeks >= 6L)

  rosters |>
    select(.data$conference, .data$player_id, .data$prev_salary, .data$prev_years, .data$contract) |>
    left_join(baseline, by = c("conference", "player_id")) |>
    left_join(current_accrual, by = c("conference", "player_id")) |>
    mutate(
      prior_accrued_seasons = coalesce(.data$prior_accrued_seasons, 0L),
      eligible_roster_weeks = coalesce(.data$eligible_roster_weeks, 0L),
      current_season_accrued = coalesce(.data$current_season_accrued, FALSE),
      projected_accrued_seasons = .data$prior_accrued_seasons + as.integer(
        .data$current_season_accrued | .env$project_current_accrual
      ),
      eligibility_projected = !.data$current_season_accrued & .env$project_current_accrual,
      contract_year = suppressWarnings(as.integer(sub("^([0-9]{4}).*", "\\1", .data$contract))),
      projected_salary = round(.data$prev_salary * 1.10, 2),
      projected_vet_min = mapply(compound_vet_min, .data$contract_year, .env$season + 1L),
      expires_after_season = .data$prev_years == 1,
      next_ft_eligible = .data$expires_after_season & !grepl("FT2$", trimws(.data$contract)),
      next_rfa_eligible = .data$expires_after_season & .data$projected_accrued_seasons == 3L,
      next_erfa_eligible = .data$expires_after_season & .data$projected_accrued_seasons <= 2L &
        !is.na(.data$projected_vet_min) & .data$projected_salary <= .data$projected_vet_min,
      next_unrestricted = .data$expires_after_season & !.data$next_rfa_eligible & !.data$next_erfa_eligible
    ) |>
    select(
      .data$conference, .data$player_id, .data$prior_accrued_seasons,
      .data$eligible_roster_weeks, .data$current_season_accrued,
      .data$projected_accrued_seasons, .data$eligibility_projected,
      .data$next_ft_eligible, .data$next_rfa_eligible,
      .data$next_erfa_eligible, .data$next_unrestricted
    )
}
