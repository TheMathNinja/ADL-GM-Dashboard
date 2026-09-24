adl_elo_config <- list(
  `2026` = list(
    expectation_base = 10,
    expectation_scale = 400,
    component_weights = c(offense = 0.3646980016, defense = 0.4081967410, potential = 0.2271052574),
    k = c(2.240249197, 0.5902384748, 1.113998496, 1.465561634,
          1.678966473, 1.788251594, 1.827455582, 1.830617021,
          1.831774493, 1.864966582, 1.964231872, 2.163608946,
          2.497136387, 2.998852778, 3.702796704, 4.643006748,
          1.0)
  )
)

all_play_rank <- function(values) {
  vapply(values, function(value) {
    sum(values < value) + 0.5 * sum(values == value) - 0.5
  }, numeric(1))
}

expected_all_play <- function(ratings, base, scale) {
  vapply(ratings, function(rating) {
    sum((base^(rating / scale)) /
          (base^(rating / scale) + base^(ratings / scale))) - 0.5
  }, numeric(1))
}

build_adl_team_week_data <- function(season, through_week) {
  through_week <- as.integer(through_week)
  conn <- adl_connection(season)
  franchises <- adl_fetch("franchises", conn) |>
    dplyr::select(franchise_id, dplyr::any_of(c("franchise_name", "name", "division", "conference")))
  schedule <- adl_fetch("schedule", conn) |>
    dplyr::filter(.data$week <= through_week) |>
    dplyr::select(.data$week, .data$franchise_id, .data$franchise_score)
  starters <- adl_fetch("starters", conn, week = seq_len(through_week)) |>
    dplyr::filter(.data$week <= through_week)

  components <- starters |>
    dplyr::group_by(.data$franchise_id, .data$week) |>
    dplyr::summarise(
      offense_points = sum(.data$player_score[
        .data$starter_status == "starter" & .data$pos %in% c("QB", "RB", "WR", "TE", "PK", "PN")
      ], na.rm = TRUE),
      defense_points = sum(.data$player_score[
        .data$starter_status == "starter" & .data$pos %in% c("DT", "DE", "LB", "CB", "S")
      ], na.rm = TRUE),
      potential_points = sum(.data$player_score[.data$should_start == 1], na.rm = TRUE),
      .groups = "drop"
    )

  result <- schedule |>
    dplyr::left_join(components, by = c("franchise_id", "week")) |>
    dplyr::left_join(franchises, by = "franchise_id") |>
    dplyr::mutate(
      season = as.integer(season),
      total_points = .data$offense_points + .data$defense_points
    ) |>
    dplyr::arrange(.data$week, .data$franchise_name)

  counts <- result |>
    dplyr::count(.data$week, name = "teams")
  bad_weeks <- counts$week[counts$teams != 32L]
  required <- c("franchise_score", "offense_points", "defense_points", "potential_points", "total_points")
  if (nrow(result) != 32L * through_week || length(bad_weeks) ||
      any(!is.finite(as.matrix(result[required])))) {
    stop("Shared MFL team-week data is incomplete through Week ", through_week,
         if (length(bad_weeks)) paste0("; incomplete weeks: ", paste(bad_weeks, collapse = ", ")) else "")
  }
  mismatch <- abs(result$franchise_score - result$total_points) > 0.011
  if (any(mismatch)) {
    stop("Starter components do not reconcile to MFL totals for: ",
         paste(paste0(result$franchise_name[mismatch], " W", result$week[mismatch]), collapse = ", "))
  }
  result
}

calculate_adl_elo <- function(team_weeks, season,
                              seed_path = file.path("data", "elo_seed_2026.csv")) {
  config <- adl_elo_config[[as.character(season)]]
  if (is.null(config)) {
    stop("No reviewed Elo configuration exists for season ", season,
         ". Add the season's Week 0 seed, component weights, and weekly K values before publishing.")
  }
  seed <- readr::read_csv(seed_path, show_col_types = FALSE)
  if (nrow(seed) != 32L || anyDuplicated(seed$franchise_name) || any(!is.finite(seed$elo))) {
    stop("Elo seed must contain 32 distinct teams with finite Week 0 ratings.")
  }
  observed <- sort(unique(team_weeks$franchise_name))
  if (!identical(observed, sort(seed$franchise_name))) {
    stop("MFL franchises do not match the Elo seed. Missing from MFL: ",
         paste(setdiff(seed$franchise_name, observed), collapse = ", "),
         "; missing from seed: ", paste(setdiff(observed, seed$franchise_name), collapse = ", "))
  }

  ratings <- stats::setNames(seed$elo, seed$franchise_name)
  output <- dplyr::transmute(seed, season = as.integer(season), week = 0L,
                            franchise_name = .data$franchise_name, elo = .data$elo,
                            offense_points = NA_real_, defense_points = NA_real_,
                            potential_points = NA_real_, composite = NA_real_,
                            adjusted_all_play = NA_real_, actual_all_play = NA_real_,
                            expected_all_play = NA_real_, k = NA_real_)
  weights <- config$component_weights

  for (week in sort(unique(team_weeks$week))) {
    current <- team_weeks |>
      dplyr::filter(.data$week == week) |>
      dplyr::arrange(match(.data$franchise_name, names(ratings))) |>
      dplyr::mutate(
        composite = weights[["offense"]] * .data$offense_points +
          weights[["defense"]] * .data$defense_points +
          weights[["potential"]] * .data$potential_points,
        adjusted_all_play = all_play_rank(.data$composite),
        actual_all_play = all_play_rank(.data$total_points),
        expected_all_play = expected_all_play(
          unname(ratings[.data$franchise_name]), config$expectation_base, config$expectation_scale
        ),
        k = config$k[[week]],
        elo = unname(ratings[.data$franchise_name]) + .data$k *
          (.data$adjusted_all_play - .data$expected_all_play)
      )
    ratings[current$franchise_name] <- current$elo
    output <- dplyr::bind_rows(output, current |>
      dplyr::transmute(
        season = as.integer(season), week = .data$week,
        franchise_name = .data$franchise_name, elo = .data$elo,
        offense_points = .data$offense_points, defense_points = .data$defense_points,
        potential_points = .data$potential_points, composite = .data$composite,
        adjusted_all_play = .data$adjusted_all_play, actual_all_play = .data$actual_all_play,
        expected_all_play = .data$expected_all_play, k = .data$k
      ))
  }
  output
}

write_weekly_system_outputs <- function(snapshot, season, through_week,
                                        data_dir = "data") {
  dir.create(data_dir, recursive = TRUE, showWarnings = FALSE)
  team_weeks <- build_adl_team_week_data(season, through_week)
  elo <- calculate_adl_elo(team_weeks, season)
  latest <- elo |>
    dplyr::filter(.data$week == through_week)
  if (nrow(latest) != 32L || any(!is.finite(latest$elo))) {
    stop("Elo output is incomplete for Week ", through_week, ".")
  }

  bonus <- snapshot |>
    dplyr::select(dplyr::any_of(c(
      "season", "week", "franchise_id", "franchise_name", "conference", "division",
      "bonus_wins_raw", "bonus_ties_raw", "bonus_losses_raw", "bonus_wins",
      "pred_q1_bonus_wins", "pred_q2_bonus_wins", "pred_q3_bonus_wins",
      "pred_q4_bonus_wins", "pred_rs_bonus_wins", "pred_total_bonus"
    )))
  if (nrow(bonus) != 32L) stop("Bonus Games output does not contain exactly 32 teams.")

  readr::write_csv(team_weeks, file.path(data_dir, "weekly_team_metrics.csv"), na = "")
  readr::write_csv(elo, file.path(data_dir, "elo_ratings.csv"), na = "")
  readr::write_csv(bonus, file.path(data_dir, "bonus_games.csv"), na = "")
  readr::write_csv(
    tibble::tibble(
      season = as.integer(season), through_week = as.integer(through_week),
      teams = 32L, team_week_rows = nrow(team_weeks), elo_rows = nrow(elo),
      refreshed_at = format(Sys.time(), tz = "UTC", usetz = TRUE)
    ),
    file.path(data_dir, "weekly_system_metadata.csv"), na = ""
  )
  invisible(list(team_weeks = team_weeks, elo = elo, bonus = bonus))
}
