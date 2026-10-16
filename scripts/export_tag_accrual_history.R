library(dplyr)
source_path <- Sys.getenv("ADL_TAG_ROSTER_MASTER", "C:/Users/Michael/Documents/R/LeagueFeatures/TagEligibility/ADL_rosters_master.rds")
history <- readRDS(source_path) |>
  filter(roster_status %in% c("ROSTER", "INJURED_RESERVE")) |>
  distinct(season, conf, player_id, week) |>
  count(season, conf, player_id, name = "eligible_roster_weeks") |>
  filter(eligible_roster_weeks >= 6L) |>
  transmute(conference = conf, player_id = as.character(player_id), season, eligible_roster_weeks) |>
  arrange(conference, player_id, season)
readr::write_csv(history, "data/tag_accrual_history.csv")
baseline <- readr::read_csv("data/tag_accrual_baseline_2026.csv", show_col_types = FALSE,
                          col_types = readr::cols(player_id = readr::col_character()))
counts <- history |> filter(season < 2026) |> count(conference, player_id, name = "verified")
comparison <- full_join(baseline, counts, by = c("conference", "player_id")) |>
  mutate(prior_accrued_seasons = coalesce(prior_accrued_seasons, 0L), verified = coalesce(verified, 0L)) |>
  filter(prior_accrued_seasons != verified)
print(comparison)
message("Exported earned-season history; baseline discrepancies: ", nrow(comparison))
