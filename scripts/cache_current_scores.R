library(dplyr)
library(readr)

source("R/roster_source.R")
source("R/score_calendar.R")

first_existing_col <- function(df, candidates, default = NA_character_) {
  hit <- intersect(candidates, names(df))
  if (!length(hit)) return(rep(default, nrow(df)))
  as.character(df[[hit[[1]]]])
}

fetch_mfl_playerscores_raw <- function(conn, season, weeks) {
  players <- tryCatch({
    player_tbl <- tibble::as_tibble(ffscrapr::mfl_players(conn))
    tibble::tibble(
      player_id = first_existing_col(player_tbl, c("player_id", "id")),
      player_name = first_existing_col(player_tbl, c("player_name", "name", "player")),
      pos = first_existing_col(player_tbl, c("pos", "position")),
      team = first_existing_col(player_tbl, c("team", "player_team"))
    ) |>
      distinct(.data$player_id, .keep_all = TRUE)
  }, error = function(e) {
    message("Could not join MFL player metadata; raw score rows will use player IDs only: ", conditionMessage(e))
    tibble::tibble(player_id = character(), player_name = character(), pos = character(), team = character())
  })

  score_rows <- lapply(weeks, function(wk) {
    raw <- ffscrapr::mfl_getendpoint(conn, "playerScores", YEAR = season, W = wk, RULES = 0)
    rows <- purrr::pluck(raw, "content", "playerScores", "playerScore")
    if (is.null(rows)) {
      return(tibble::tibble(
        season = integer(),
        week = integer(),
        player_id = character(),
        points = numeric(),
        is_available = character()
      ))
    }

    raw_tbl <- tibble::tibble(row = rows) |>
      tidyr::unnest_wider(.data$row)

    tibble::tibble(
      season = as.integer(season),
      week = as.integer(wk),
      player_id = first_existing_col(raw_tbl, c("id", "player_id")),
      points = suppressWarnings(as.numeric(first_existing_col(raw_tbl, c("score", "points"), NA_character_))),
      is_available = first_existing_col(raw_tbl, c("isAvailable", "is_available"), NA_character_)
    )
  }) |>
    bind_rows()

  score_rows |>
    left_join(players, by = "player_id") |>
    select(
      season,
      week,
      player_id,
      player_name,
      pos,
      team,
      points,
      is_available
    )
}

fetch_player_scores <- function(conn, season, weeks) {
  tryCatch(
    ffscrapr::ff_playerscores(conn, season = season, week = weeks),
    error = function(e) {
      message("ffscrapr::ff_playerscores() failed; falling back to raw MFL playerScores endpoint: ", conditionMessage(e))
      fetch_mfl_playerscores_raw(conn, season, weeks)
    }
  )
}

score_cache_dir <- get_env_or_default(
  "ADL_RAW_LEAGUE_DATA_DIR",
  "C:/Users/Michael/Documents/R/FFAucAndDraft/RawLeagueData"
)

current_nfl_week_for_scores <- function(today = Sys.Date(), season = get_current_season()) {
  override <- suppressWarnings(as.integer(Sys.getenv("ADL_SCORE_WEEK", unset = NA_character_)))
  if (!is.na(override)) return(max(1L, min(17L, override)))

  max(1L, completed_score_week(today, season))
}

should_refresh_scores <- function(today = Sys.Date(), season = get_current_season()) {
  if (identical(Sys.getenv("ADL_FORCE_SCORE_REFRESH", unset = "FALSE"), "TRUE")) return(TRUE)
  first_unofficial <- as.Date(paste0(season, "-09-15"))
  last_official <- as.Date(paste0(season + 1L, "-01-07"))
  today >= first_unofficial && today <= last_official
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
if (!should_refresh_scores(season = season)) {
  message("Skipping ADL score refresh: today is outside the scheduled NFL scoring refresh window.")
  quit(save = "no", status = 0)
}
week <- current_nfl_week_for_scores(season = season)
status <- get_env_or_default("ADL_SCORE_STATUS", "manual")
league_tag <- paste0("ADL", substr(as.character(season), 3, 4))

dir.create(score_cache_dir, recursive = TRUE, showWarnings = FALSE)
dir.create("data", recursive = TRUE, showWarnings = FALSE)

conn <- connect_adl_mfl(season)
weeks <- seq_len(week)

scores <- fetch_player_scores(conn, season = season, weeks = weeks)
starters <- ffscrapr::ff_starters(conn, season = season, week = weeks)

scores_path <- file.path(score_cache_dir, paste0("ff_playerscores_", league_tag, "_", season, "_W1-", week, "_raw.rds"))
starters_path <- file.path(score_cache_dir, paste0("ff_starters_", league_tag, "_", season, "_W1-", week, "_raw.rds"))

saveRDS(scores, scores_path)
saveRDS(starters, starters_path)
write_score_metadata(season, week, status, scores_path, starters_path)

message("Cached ", status, " ADL scores through Week ", week)
message("Scores: ", scores_path)
message("Starters: ", starters_path)
