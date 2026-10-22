library(dplyr)
source("R/pr_completed_seasons.R")
source("R/pr_rank_popovers.R")
history <- tibble(season = 2025L, pos = "QB", player_id = c("a", "b", "c"),
  player_name = c("Short", "Robust One", "Robust Two"), gp = c(2, 8, 12),
  total_points = c(80, 240, 240), ppg = c(40, 30, 20), pr_total = c(3, 1.5, 1.5),
  pr_avg = 1:3, pr_final = c(1, 1.5, 1.5))
history <- apply_completed_season_ppg_ranks(history, 2026L, "missing")
avg <- pr_rank_list(history, tibble(), 2025L, "QB", 6L, 2026L, "avg")
stopifnot(nrow(avg) == 3, is.na(avg$display_rank[1]), avg$excluded[1], identical(avg$display_rank[-1], c(1, 2)))
tot <- pr_rank_list(history, tibble(), 2025L, "QB", 6L, 2026L, "total")
stopifnot(identical(tot$display_rank, c(1.5, 1.5, 3)), !any(tot$excluded))
snapshots <- bind_rows(mutate(history, season = 2026L, snapshot_week = 2L),
                       mutate(history, season = 2026L, snapshot_week = 6L, total_points = total_points + 100))
past <- pr_rank_list(history, snapshots, 2026L, "QB", 2L, 2026L, "total")
stopifnot(max(past$total_points) == 240, all(past$snapshot_week == 2L))
stopifnot(nrow(pr_rank_list(history, snapshots, 2026L, "QB", 0L, 2026L, "avg")) == 0)
html <- as.character(pr_rank_popover("Avg: QB1", avg, 2025L, "QB", "avg", "b", 2026L))
stopifnot(grepl("rank-excluded", html), grepl("rank-selected", html), grepl("<template", html), grepl("aria-haspopup", html))
cat("PASS: total/robust-only PPG lists, excluded rows, ties, selected-week isolation and accessible markup.\n")
