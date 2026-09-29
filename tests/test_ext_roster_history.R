source("R/roster_source.R")
path <- tempfile(fileext = ".csv")
old <- read_csv("data/ext_roster_weekly_snapshots_2026.csv", show_col_types = FALSE,
                col_types = cols(player_id = col_character(), contract = col_character(),
                                 ext_marker = col_character()))
old <- old[old$week == 1L, ]
old$player_id[1] <- "00123"
write_csv(old, path)
calls <- integer()
fetch_live_rosters <- function(season, week) {
  calls <<- c(calls, week)
  old |> select(-season, -week)
}
result <- refresh_ext_roster_history(2026L, 2L, TRUE, path)
stopifnot(is.character(result$player_id), identical(calls, 2L),
          nrow(result) == 2L * nrow(old),
          sum(result$player_id == "00123") == 2L)
again <- refresh_ext_roster_history(2026L, 2L, TRUE, path)
stopifnot(nrow(again) == nrow(result), identical(calls, 2L))
unlink(path)
cat("PASS: cached and live roster IDs combine without coercion or duplicate weeks.\n")
