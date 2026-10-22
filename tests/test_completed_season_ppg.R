library(dplyr)
source("R/pr_completed_seasons.R")
fixture <- data.frame(
  season = c(rep(2025L, 5), rep(2026L, 3)),
  player_id = c("one-game-star", "seven-games", "eight-games", "tied-a", "tied-b", "current-short", "current-eight", "current-tie"),
  pos = c(rep("QB", 3), "RB", "RB", rep("QB", 3)),
  gp = c(1, 7, 8, 8, 12, 1, 8, 8), ppg = c(50, 40, 30, 20, 20, 50, 30, 30),
  total_points = c(50, 280, 240, 160, 240, 50, 240, 240),
  pr_total = c(3, 1, 2, 2, 1, 3, 1.5, 1.5),
  pr_avg = c(1, 2, 3, 1.5, 1.5, 1, 2.5, 2.5),
  pr_final = c(1, 1, 2, 1.5, 1, 1, 1.5, 1.5), robust_pr = c(FALSE, FALSE, TRUE, TRUE, TRUE, FALSE, TRUE, TRUE))
absent <- tempfile("no-metadata-")
updated <- apply_completed_season_ppg_ranks(fixture, 2026L, absent)
stopifnot(all(is.na(updated$pr_avg[1:2])), updated$pr_avg[3] == 1,
          identical(updated$pr_avg[4:5], c(1.5, 1.5)),
          identical(updated$pr_total, fixture$pr_total),
          identical(updated$gp, fixture$gp), identical(updated$total_points, fixture$total_points),
          identical(updated$ppg, fixture$ppg), identical(updated$robust_pr, fixture$robust_pr),
          identical(updated[6:8, ], fixture[6:8, ] |> tibble::as_tibble()))
none <- fixture[1:2, ]; none$gp <- c(1, 7)
stopifnot(all(is.na(apply_completed_season_ppg_ranks(none, 2026L, absent)$pr_avg)))
metadata <- tempfile(fileext = ".csv")
write.csv(data.frame(season = 2026L, week = 17L, official_week = 16L), metadata, row.names = FALSE)
stopifnot(identical(apply_completed_season_ppg_ranks(fixture, 2026L, metadata)$pr_avg[6:8], fixture$pr_avg[6:8]))
write.csv(data.frame(season = 2026L, week = 17L, official_week = 17L), metadata, row.names = FALSE)
final <- apply_completed_season_ppg_ranks(fixture, 2026L, metadata)
stopifnot(is.na(final$pr_avg[6]), identical(final$pr_avg[7:8], c(1.5, 1.5)))
cat("PASS: completed-season PPG excludes <8 games; cutoff/ties/positions preserved; total ranks and in-process seasons unchanged.\n")
