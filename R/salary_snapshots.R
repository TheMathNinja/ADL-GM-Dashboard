library(dplyr)
library(readr)
library(tibble)

raw_league_data_dir <- function() {
  Sys.getenv(
    "ADL_RAW_LEAGUE_DATA_DIR",
    unset = "C:/Users/Michael/Documents/R/FFAucAndDraft/RawLeagueData"
  )
}

cached_ff_rosters_path <- function(season) {
  league_code <- paste0("ADL", substr(as.character(season), 3, 4))
  file.path(raw_league_data_dir(), paste0("ff_rosters_", league_code, "_", season, "_raw.rds"))
}

position_curve_order <- function() {
  c("QB", "RB", "WR", "TE", "PK/PN", "PK", "PN", "DT", "DE", "LB", "CB", "S")
}

normalize_salary_snapshot_rosters <- function(rosters, max_contract_year = NULL) {
  normalize_rosters(rosters) |>
    mutate(
      player_pos = if_else(.data$player_pos == "DEF", "DT", .data$player_pos),
      salary = as.numeric(.data$prev_salary),
      contract_year = suppressWarnings(as.integer(sub("^([0-9]{4}).*", "\\1", .data$contract)))
    ) |>
    filter(
      .data$player_pos %in% c("QB", "RB", "WR", "TE", "PK", "PN", "DT", "DE", "LB", "CB", "S"),
      !is.na(.data$salary),
      is.null(.env$max_contract_year) | is.na(.data$contract_year) | .data$contract_year <= .env$max_contract_year
    )
}

add_top_rank_extrapolation <- function(curve) {
  top_four <- curve |>
    filter(.data$rank %in% 1:4) |>
    arrange(.data$rank)

  if (nrow(top_four) < 4) return(curve)

  rank_one <- top_four$salary[top_four$rank == 1][1]
  rank_four <- top_four$salary[top_four$rank == 4][1]
  step <- (rank_one - rank_four) / 3

  bind_rows(
    tibble(
      salary_source = curve$salary_source[1],
      position = curve$position[1],
      rank = c(-1, 0),
      player = NA_character_,
      conference = NA_character_,
      salary = c(rank_one + 2 * step, rank_one + step)
    ),
    curve
  )
}

salary_curve_from_rosters <- function(rosters, salary_source, multiplier = 1, max_contract_year = NULL) {
  normalized <- normalize_salary_snapshot_rosters(rosters, max_contract_year = max_contract_year)

  bind_rows(lapply(position_curve_order(), function(position) {
    position_rows <- if (position == "PK/PN") {
      normalized |> filter(.data$player_pos %in% c("PK", "PN"))
    } else {
      normalized |> filter(.data$player_pos == .env$position)
    }

    curve <- position_rows |>
      arrange(desc(.data$salary), .data$player_name, .data$franchise) |>
      mutate(
        salary_source = .env$salary_source,
        position = .env$position,
        rank = row_number(),
        salary = round(as.numeric(.data$salary) * .env$multiplier, 2)
      ) |>
      transmute(
        salary_source,
        position,
        rank,
        player,
        conference,
        salary
      )

    add_top_rank_extrapolation(curve)
  }))
}

read_cached_ff_rosters <- function(season) {
  path <- cached_ff_rosters_path(season)
  if (!file.exists(path)) stop("Missing cached ff_rosters scrape: ", path)
  readRDS(path)
}

adl_roster_amendments <- function() {
  tibble(
    season = c(2025L, 2025L),
    franchise_id = c("0018", "0031"),
    player_id = c("15708", "15751"),
    player_name = c("Hall, Breece", "London, Drake"),
    original_contractInfo = c("2026 5YO", "2026 5YO"),
    amended_contractInfo = c("2025 5YO amended", "2025 5YO amended"),
    original_salary = c(15.12, 29.83),
    amended_salary = c(11.66, 9.82),
    reason = c(
      "ADL25 cache had 2026 5YO entered before End25 salary readout",
      "ADL25 cache had 2026 5YO entered before End25 salary readout"
    )
  )
}

apply_roster_amendments <- function(rosters, season) {
  amendments <- adl_roster_amendments() |>
    filter(.data$season == .env$season)

  if (!nrow(amendments)) return(rosters)

  rosters <- tibble::as_tibble(rosters)

  for (i in seq_len(nrow(amendments))) {
    row <- amendments[i, ]
    matched <- rosters$franchise_id == row$franchise_id &
      as.character(rosters$player_id) == row$player_id &
      rosters$contractInfo == row$original_contractInfo &
      abs(as.numeric(rosters$salary) - row$original_salary) < 0.001

    if (!any(matched, na.rm = TRUE)) {
      warning("Roster amendment did not match: ", row$player_name, " ", row$franchise_id)
      next
    }

    rosters$salary[matched] <- row$amended_salary
    rosters$contractInfo[matched] <- row$amended_contractInfo
  }

  rosters
}

read_amended_ff_rosters <- function(season) {
  packaged_path <- amended_ff_rosters_path(season, "rds")
  if (file.exists(packaged_path)) {
    return(readRDS(packaged_path))
  }

  apply_roster_amendments(read_cached_ff_rosters(season), season)
}

final_july1_salary_curve_path <- function(season) {
  file.path("data", "salary_snapshots", paste0("july1_final_salary_curve_", season, ".csv"))
}

raw_july1_salary_curve_path <- function(season) {
  file.path("data", "salary_snapshots", paste0("july1_raw_salary_curve_", season, ".csv"))
}

amended_ff_rosters_path <- function(season, ext = "rds") {
  league_code <- paste0("ADL", substr(as.character(season), 3, 4))
  file.path("data", "salary_snapshots", paste0("ff_rosters_", league_code, "_", season, "_amended.", ext))
}

july1_status_path <- function(season) {
  file.path("data", "salary_snapshots", paste0("july1_status_", season, ".csv"))
}

build_salary_curves_from_scrapes <- function(current_season = get_current_season()) {
  end_season <- current_season - 1L
  amended_end_rosters <- read_amended_ff_rosters(end_season)
  dir.create(file.path("data", "salary_snapshots"), recursive = TRUE, showWarnings = FALSE)
  saveRDS(amended_end_rosters, amended_ff_rosters_path(end_season, "rds"))
  write_csv(amended_end_rosters, amended_ff_rosters_path(end_season, "csv"), na = "")

  end_curve <- salary_curve_from_rosters(
    amended_end_rosters,
    salary_source = paste0("End", substr(end_season, 3, 4), " Sal"),
    max_contract_year = end_season
  ) |>
    mutate(salary_source = "End25 Sal")

  july1_final <- final_july1_salary_curve_path(current_season)
  if (file.exists(july1_final)) {
    july1_curve <- read_csv(july1_final, show_col_types = FALSE) |>
      mutate(salary_source = "Jul1 Sal")
  } else {
    july1_curve <- tibble(
      salary_source = character(),
      position = character(),
      rank = numeric(),
      player = character(),
      conference = character(),
      salary = numeric()
    )
  }

  bind_rows(end_curve, july1_curve)
}

write_july1_review_prompt <- function(season) {
  prompt_path <- file.path("data", "salary_snapshots", paste0("july1_review_prompt_", season, ".md"))
  lines <- c(
    paste0("# July 1 Salary Snapshot Review - ", season),
    "",
    "A raw July 1 salary curve has been scraped and cached.",
    "",
    "Before promoting it to the final July 1 salary curve for EXT pricing, check whether manual league-office work is complete:",
    "",
    "- salary adjustments",
    "- Franchise Tags",
    "- any other contract-admin corrections that should be reflected in July 1 salaries",
    "",
    paste0("If complete, review `", raw_july1_salary_curve_path(season), "` and copy/approve it as `", final_july1_salary_curve_path(season), "`.")
  )
  writeLines(lines, prompt_path)
  prompt_path
}

cache_july1_raw_salary_readout <- function(season = get_current_season(), force_live = TRUE) {
  dir.create(file.path("data", "salary_snapshots"), recursive = TRUE, showWarnings = FALSE)

  rosters <- if (force_live) {
    fetch_live_rosters(season = season)
  } else {
    read_amended_ff_rosters(season)
  }

  curve <- salary_curve_from_rosters(rosters, salary_source = "Jul1 Raw", max_contract_year = season)
  write_csv(curve, raw_july1_salary_curve_path(season), na = "")

  status <- tibble(
    season = season,
    scraped_at = format(Sys.time(), "%Y-%m-%d %H:%M:%S %Z"),
    status = "raw_pending_review",
    raw_curve = raw_july1_salary_curve_path(season),
    final_curve = final_july1_salary_curve_path(season),
    review_prompt = write_july1_review_prompt(season)
  )
  write_csv(status, july1_status_path(season), na = "")
  status
}
