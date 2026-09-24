source("R/weekly_system.R")

fixture <- readr::read_csv("tests/fixtures/adl_2026_elo_weeks_1_2.csv", show_col_types = FALSE)
team_weeks <- dplyr::bind_rows(lapply(1:2, function(week) {
  tibble::tibble(
    season = 2026L,
    week = week,
    franchise_name = fixture$franchise_name,
    offense_points = fixture[[paste0("w", week, "_offense")]],
    defense_points = fixture[[paste0("w", week, "_defense")]],
    potential_points = fixture[[paste0("w", week, "_potential")]],
    total_points = fixture[[paste0("w", week, "_offense")]] + fixture[[paste0("w", week, "_defense")]]
  )
}))

actual <- calculate_adl_elo(team_weeks, 2026L)
for (week in 1:2) {
  result <- actual[actual$week == week, c("franchise_name", "elo")]
  expected <- fixture[, c("franchise_name", paste0("w", week))]
  names(expected)[[2]] <- "expected"
  comparison <- dplyr::left_join(result, expected, by = "franchise_name")
  error <- max(abs(comparison$elo - comparison$expected))
  if (error > 1e-5) stop("Week ", week, " Elo parity failed; max error = ", error)
}

message("Internal Elo engine exactly reproduces the reviewed Week 1 and Week 2 workbook ratings.")
