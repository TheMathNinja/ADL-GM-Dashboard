library(dplyr)
source("R/pr_history.R")

history <- readr::read_csv("data/pr_history.csv", show_col_types = FALSE,
  col_types = readr::cols(player_id = readr::col_character()))
history <- history[history$season < as.integer(Sys.getenv("CURRENT_SEASON", format(Sys.Date(), "%Y"))), ]
identities <- add_pr_player_teams(history, identity_path = tempfile()) |>
  select(season, player_id, player_team) |>
  distinct() |>
  arrange(season, player_id)
stopifnot(!anyDuplicated(identities[c("season", "player_id")]),
  !anyNA(identities$player_team), all(nzchar(identities$player_team)))
readr::write_csv(identities, "data/pr_player_identity.csv")
cat("Cached", nrow(identities), "historical NFL team identities from season-specific MFL player caches.\n")
