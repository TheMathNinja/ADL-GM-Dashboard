library(dplyr)
library(readr)

source("R/roster_source.R")

score_cache_dir <- get_env_or_default(
  "ADL_RAW_LEAGUE_DATA_DIR",
  "C:/Users/Michael/Documents/R/FFAucAndDraft/RawLeagueData"
)

current_nfl_week_for_scores <- function(today = Sys.Date(), season = get_current_season()) {
  override <- suppressWarnings(as.integer(Sys.getenv("ADL_SCORE_WEEK", unset = NA_character_)))
  if (!is.na(override)) return(max(1L, min(17L, override)))

  week_one_start <- as.Date(paste0(season, "-09-10"))
  if (today < week_one_start) return(1L)
  max(1L, min(17L, floor(as.numeric(today - week_one_start) / 7) + 1L))
}

write_score_metadata <- function(season, week, status, scores_path, starters_path) {
  write_csv(
    tibble(
      refreshed_at = format(Sys.time(), "%Y-%m-%d %H:%M:%S %Z"),
      season = season,
      week = week,
      status = status,
      scores_path = scores_path,
      starters_path = starters_path
    ),
    file.path("data", "score_metadata.csv"),
    na = ""
  )
}

season <- get_current_season()
week <- current_nfl_week_for_scores(season = season)
status <- get_env_or_default("ADL_SCORE_STATUS", "manual")
league_tag <- paste0("ADL", substr(as.character(season), 3, 4))

dir.create(score_cache_dir, recursive = TRUE, showWarnings = FALSE)
dir.create("data", recursive = TRUE, showWarnings = FALSE)

conn <- connect_adl_mfl(season)
weeks <- seq_len(week)

scores <- ffscrapr::ff_playerscores(conn, season = season, week = weeks)
starters <- ffscrapr::ff_starters(conn, season = season, week = weeks)

scores_path <- file.path(score_cache_dir, paste0("ff_playerscores_", league_tag, "_", season, "_W1-", week, "_raw.rds"))
starters_path <- file.path(score_cache_dir, paste0("ff_starters_", league_tag, "_", season, "_W1-", week, "_raw.rds"))

saveRDS(scores, scores_path)
saveRDS(starters, starters_path)
write_score_metadata(season, week, status, scores_path, starters_path)

source("scripts/prepare_ext_data.R", local = new.env(parent = globalenv()))

message("Cached ", status, " ADL scores through Week ", week)
message("Scores: ", scores_path)
message("Starters: ", starters_path)
