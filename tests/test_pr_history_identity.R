library(dplyr)
source("R/pr_history.R")

scores <- tibble::tribble(
  ~season, ~week, ~player_id, ~player_name, ~pos, ~points,
  2026L, 1L, "17059", "Gordon, Ollie", "RB", 2.5,
  2026L, 1L, "17059", "Gordon II, Ollie", "RB", 2.5,
  2026L, 2L, "17059", "Gordon II, Ollie", "RB", 7.3
)

result <- summarise_player_pr_scores(scores)
stopifnot(
  nrow(result) == 1L,
  result$player_id[[1]] == "17059",
  result$player_name[[1]] == "Gordon II, Ollie",
  result$gp[[1]] == 2L,
  abs(result$total_points[[1]] - 9.8) < 0.000001
)

cat("PASS: MFL display-name changes do not duplicate player PR history.\n")
