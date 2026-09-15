library(dplyr)
library(readr)

season <- suppressWarnings(as.integer(Sys.getenv("CURRENT_SEASON", unset = format(Sys.Date(), "%Y"))))
if (is.na(season)) {
  season <- as.integer(format(Sys.Date(), "%Y"))
}

dir.create("data", recursive = TRUE, showWarnings = FALSE)

mfl_team_map <- c(
  ARI = "ARI", ATL = "ATL", BAL = "BAL", BUF = "BUF", CAR = "CAR",
  CHI = "CHI", CIN = "CIN", CLE = "CLE", DAL = "DAL", DEN = "DEN",
  DET = "DET", GBP = "GB", HOU = "HOU", IND = "IND", JAC = "JAX",
  KCC = "KC", LAC = "LAC", LAR = "LA", LVR = "LV", MIA = "MIA",
  MIN = "MIN", NEP = "NE", NOS = "NO", NYG = "NYG", NYJ = "NYJ",
  PHI = "PHI", PIT = "PIT", SEA = "SEA", SFO = "SF", TBB = "TB",
  TEN = "TEN", WAS = "WAS"
)

format_kickoff_et <- function(kickoff) {
  if (is.na(kickoff)) return(NA_character_)
  format(as.POSIXct(kickoff, tz = "America/New_York"), "%a %b %-d %-I:%M%p ET")
}

schedule <- nflreadr::load_schedules(seasons = season) |>
  filter(.data$season == season, .data$game_type == "REG") |>
  mutate(
    gameday = as.Date(.data$gameday),
    gametime = as.character(.data$gametime),
    kickoff_et = as.POSIXct(
      paste(.data$gameday, ifelse(is.na(.data$gametime) | !nzchar(.data$gametime), "00:00", .data$gametime)),
      tz = "America/New_York"
    )
  )

team_schedule <- bind_rows(
  schedule |>
    transmute(
      season = .data$season,
      week = .data$week,
      nfl_team = .data$away_team,
      opponent = .data$home_team,
      home_away = "away",
      kickoff_et = .data$kickoff_et
    ),
  schedule |>
    transmute(
      season = .data$season,
      week = .data$week,
      nfl_team = .data$home_team,
      opponent = .data$away_team,
      home_away = "home",
      kickoff_et = .data$kickoff_et
    )
) |>
  right_join(
    tidyr::crossing(
      season = season,
      week = 1:18,
      tibble::tibble(mfl_team = names(mfl_team_map), nfl_team = unname(mfl_team_map))
    ),
    by = c("season", "week", "nfl_team")
  ) |>
  mutate(
    kickoff_label = vapply(.data$kickoff_et, format_kickoff_et, character(1)),
    is_bye = is.na(.data$kickoff_et)
  ) |>
  arrange(.data$mfl_team, .data$week) |>
  select(
    .data$season,
    .data$week,
    .data$mfl_team,
    .data$nfl_team,
    .data$opponent,
    .data$home_away,
    .data$kickoff_et,
    .data$kickoff_label,
    .data$is_bye
  )

write_csv(team_schedule, file.path("data", paste0("nfl_schedule_", season, ".csv")), na = "")
write_csv(
  tibble(
    refreshed_at = format(Sys.time(), "%Y-%m-%d %H:%M:%S %Z"),
    season = season,
    source = "nflreadr::load_schedules()"
  ),
  file.path("data", "nfl_schedule_metadata.csv"),
  na = ""
)

message("Cached NFL schedule for ", season, " with ", nrow(team_schedule), " team-week rows.")
