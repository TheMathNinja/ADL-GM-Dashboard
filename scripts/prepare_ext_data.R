library(readxl)
library(dplyr)
library(readr)
library(tidyr)

source("R/roster_source.R")
source("R/pr_history.R")
source("R/salary_snapshots.R")

source_path <- file.path("data", "source", "contract_admin_2026.xlsx")
if (!file.exists(source_path)) {
  stop("Missing ", source_path, ". Export the Contract Admin Google Sheet as xlsx first.")
}

dir.create("data", showWarnings = FALSE, recursive = TRUE)

read_ext_block <- function(path, cols, conference) {
  valid_franchises <- c(
    "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE",
    "DAL", "DEN", "DET", "GBP", "HOU", "IND", "JAX", "KCC",
    "LAC", "LAR", "LVR", "MIA", "MIN", "NEP", "NOS", "NYG",
    "NYJ", "PHI", "PIT", "SEA", "SFO", "TBB", "TEN", "WAS"
  )

  raw <- read_excel(path, sheet = "EXT", col_names = FALSE, range = cell_cols(cols))
  names(raw) <- c(
    "player", "gm", "prev_salary", "prev_years", "ext_years", "fifth_year_option", "week",
    "pr_current_pos", "pr_current_total", "pr_current_avg", "pr_current_final",
    "pr_recent_pos", "pr_recent_total", "pr_recent_avg", "pr_recent_final",
    "pr_previous_pos", "pr_previous_total", "pr_previous_avg", "pr_previous_final",
    "epv_current", "epv_recent", "epv_previous", "eys", "new_salary", "new_years"
  )

  raw |>
    slice(-(1:2)) |>
    mutate(conference = conference, .before = 1) |>
    filter(!is.na(player), gm %in% valid_franchises) |>
    mutate(
      across(c(
        prev_salary, prev_years, ext_years, week,
        pr_current_total, pr_current_avg, pr_current_final,
        pr_recent_total, pr_recent_avg, pr_recent_final,
        pr_previous_total, pr_previous_avg, pr_previous_final,
        starts_with("epv_"), eys, new_salary, new_years
      ), as.numeric),
      franchise = gm
    )
}

normalize_name_key <- function(x) {
  x <- as.character(x)
  x <- ifelse(
    grepl(",", x),
    trimws(sub("^([^,]+),\\s*(.*)$", "\\2 \\1", x)),
    x
  )
  tolower(gsub("[^a-z0-9]", "", x))
}

nfl_team_abbr_from_adl <- function(x) {
  recode(
    as.character(x),
    GBP = "GB",
    JAC = "JAX",
    KCC = "KC",
    LAR = "LA",
    LVR = "LV",
    NEP = "NE",
    NOS = "NO",
    SFO = "SF",
    TBB = "TB",
    .default = as.character(x)
  )
}

espn_team_logo_from_adl <- function(x) {
  slug <- recode(
    as.character(x),
    GBP = "gb",
    JAC = "jax",
    KCC = "kc",
    LAR = "lar",
    LVR = "lv",
    NEP = "ne",
    NOS = "no",
    SFO = "sf",
    TBB = "tb",
    WAS = "wsh",
    .default = tolower(as.character(x))
  )
  ifelse(
    is.na(slug) | !nzchar(slug) | slug %in% c("fa", "na"),
    NA_character_,
    paste0("https://a.espncdn.com/i/teamlogos/nfl/500/", slug, ".png")
  )
}

build_player_visual_data <- function(rosters) {
  empty <- tibble(
    player_id = character(),
    player_headshot = character(),
    player_birth_date = as.Date(character()),
    player_jersey = character(),
    player_rookie_season = integer(),
    player_draft_year = integer(),
    player_draft_round = integer(),
    player_draft_round_pick = integer(),
    player_draft_pick = integer(),
    team_logo_espn = character(),
    team_logo_wikipedia = character(),
    team_logo_squared = character(),
    team_wordmark = character(),
    team_color = character(),
    team_color2 = character()
  )

  if (!requireNamespace("nflreadr", quietly = TRUE)) return(empty)

  ff_ids <- tryCatch(
    nflreadr::load_ff_playerids() |>
      as_tibble() |>
      transmute(
        player_id = as.character(.data$mfl_id),
        gsis_id = as.character(.data$gsis_id)
      ) |>
      filter(!is.na(.data$player_id), nzchar(.data$player_id)) |>
      distinct(.data$player_id, .keep_all = TRUE),
    error = function(e) tibble(player_id = character(), gsis_id = character())
  )

  nfl_players <- tryCatch(
    {
      draft_round_picks <- nflreadr::load_draft_picks(TRUE) |>
        as_tibble() |>
        arrange(.data$season, .data$round, .data$pick) |>
        group_by(.data$season, .data$round) |>
        mutate(player_draft_round_pick = row_number()) |>
        ungroup() |>
        transmute(
          gsis_id = as.character(.data$gsis_id),
          player_draft_round_pick = as.integer(.data$player_draft_round_pick)
        ) |>
        filter(!is.na(.data$gsis_id), nzchar(.data$gsis_id)) |>
        distinct(.data$gsis_id, .keep_all = TRUE)

      nflreadr::load_players() |>
      as_tibble() |>
      transmute(
        gsis_id = as.character(.data$gsis_id),
        player_headshot = as.character(.data$headshot),
        player_birth_date = as.Date(.data$birth_date),
        player_jersey = as.character(.data$jersey_number),
        player_rookie_season = suppressWarnings(as.integer(.data$rookie_season)),
        player_draft_year = suppressWarnings(as.integer(.data$draft_year)),
        player_draft_round = suppressWarnings(as.integer(.data$draft_round)),
        player_draft_pick = suppressWarnings(as.integer(.data$draft_pick))
      ) |>
        left_join(draft_round_picks, by = "gsis_id") |>
      filter(!is.na(.data$gsis_id), nzchar(.data$gsis_id)) |>
      distinct(.data$gsis_id, .keep_all = TRUE)
    },
    error = function(e) tibble(
      gsis_id = character(),
      player_headshot = character(),
      player_birth_date = as.Date(character()),
      player_jersey = character(),
      player_rookie_season = integer(),
      player_draft_year = integer(),
      player_draft_round = integer(),
      player_draft_round_pick = integer(),
      player_draft_pick = integer()
    )
  )

  nfl_teams <- tryCatch(
    nflreadr::load_teams() |>
      as_tibble() |>
      transmute(
        nfl_team_abbr = as.character(.data$team_abbr),
        team_logo_espn = as.character(.data$team_logo_espn),
        team_logo_wikipedia = as.character(.data$team_logo_wikipedia),
        team_logo_squared = as.character(.data$team_logo_squared),
        team_wordmark = as.character(.data$team_wordmark),
        team_color = as.character(.data$team_color),
        team_color2 = as.character(.data$team_color2)
      ) |>
      distinct(.data$nfl_team_abbr, .keep_all = TRUE),
    error = function(e) tibble(
      nfl_team_abbr = character(),
      team_logo_espn = character(),
      team_logo_wikipedia = character(),
      team_logo_squared = character(),
      team_wordmark = character(),
      team_color = character(),
      team_color2 = character()
    )
  )

  rosters |>
    transmute(
      player_id = as.character(.data$player_id),
      nfl_team_abbr = nfl_team_abbr_from_adl(.data$player_team),
      team_logo_espn_direct = espn_team_logo_from_adl(.data$player_team)
    ) |>
    left_join(ff_ids, by = "player_id") |>
    left_join(nfl_players, by = "gsis_id") |>
    left_join(nfl_teams, by = "nfl_team_abbr") |>
    mutate(team_logo_espn = coalesce(.data$team_logo_espn_direct, .data$team_logo_espn)) |>
    select(-any_of(c("gsis_id", "nfl_team_abbr"))) |>
    distinct(.data$player_id, .keep_all = TRUE)
}

pr_starter_floors_by_season <- list(
  `2026` = c(
    QB = 16, RB = 28, WR = 50, TE = 18, PK = 16, PN = 16,
    DT = 38, DE = 40, LB = 38, CB = 38, S = 38
  )
)

ensure_pr_starter_floors_configured <- function(season) {
  if (is.null(pr_starter_floors_by_season[[as.character(season)]])) {
    stop(
      "PR Starter Floors for ", season,
      " are not configured yet. Ask Michael for the updated season floors before rebuilding EXT data.",
      call. = FALSE
    )
  }
  invisible(TRUE)
}

starter_floor <- function(position, season = get_current_season()) {
  ensure_pr_starter_floors_configured(season)
  floors <- pr_starter_floors_by_season[[as.character(season)]]
  if (is.null(position) || length(position) == 0 || is.na(position) || !position %in% names(floors)) {
    return(NA_real_)
  }
  unname(floors[[position]])
}

find_adl_draft_cache_file <- function(cache_dir = adl_score_cache_dir, season) {
  files <- list.files(
    cache_dir,
    pattern = paste0("^ff_draft_ADL[0-9]{2}_", season, "_raw[.]rds$"),
    full.names = TRUE
  )
  if (!length(files)) return(NA_character_)
  files[which.max(file.info(files)$mtime)]
}

build_fifth_year_draft_eligibility <- function(season, cache_dir = adl_score_cache_dir) {
  draft_file <- find_adl_draft_cache_file(cache_dir, season)
  if (is.na(draft_file) || !file.exists(draft_file)) {
    warning("No ADL draft cache found for ", season, call. = FALSE)
    return(tibble(
      conference = character(),
      player_id = character(),
      fifth_year_draft_year = integer(),
      fifth_year_draft_round = integer(),
      fifth_year_draft_pick = integer(),
      fifth_year_draft_overall = integer()
    ))
  }

  readRDS(draft_file) |>
    as_tibble() |>
    mutate(
      franchise_num = suppressWarnings(as.integer(.data$franchise_id)),
      conference = if_else(.data$franchise_num <= 16L, "NFC", "AFC"),
      player_id = as.character(.data$player_id),
      fifth_year_draft_year = .env$season,
      fifth_year_draft_round = suppressWarnings(as.integer(.data$round)),
      fifth_year_draft_pick = suppressWarnings(as.integer(.data$pick)),
      fifth_year_draft_overall = suppressWarnings(as.integer(.data$overall))
    ) |>
    filter(
      .data$fifth_year_draft_round == 1L,
      .data$fifth_year_draft_overall >= 1L,
      .data$fifth_year_draft_overall <= 16L,
      !is.na(.data$player_id),
      !is.na(.data$conference)
    ) |>
    distinct(.data$conference, .data$player_id, .keep_all = TRUE) |>
    select(
      conference,
      player_id,
      fifth_year_draft_year,
      fifth_year_draft_round,
      fifth_year_draft_pick,
      fifth_year_draft_overall
    )
}

fifth_year_tag_level <- function(position, tsp_rank) {
  floor_rank <- starter_floor(position)
  tsp_rank <- suppressWarnings(as.numeric(tsp_rank))
  if (is.na(floor_rank)) return(NA_character_)
  if (is.na(tsp_rank)) return("5YO-")

  if (tsp_rank <= floor(0.125 * floor_rank)) {
    "NEFT"
  } else if (tsp_rank <= floor(0.25 * floor_rank)) {
    "TT"
  } else if (tsp_rank <= floor(0.75 * floor_rank)) {
    "5YO+"
  } else {
    "5YO-"
  }
}

adl_salary_cap <- function(season) {
  env_value <- suppressWarnings(as.numeric(Sys.getenv(paste0("ADL_SALARY_CAP_", season), unset = NA_character_)))
  if (!is.na(env_value)) return(env_value)

  caps <- c(
    `2025` = 226.20,
    `2026` = 244.00
  )
  value <- caps[[as.character(season)]]
  if (is.null(value) || is.na(value)) {
    stop(
      "Missing ADL salary cap for ", season,
      ". Set ADL_SALARY_CAP_", season, " to calculate FT/5YO salaries.",
      call. = FALSE
    )
  }
  value
}

build_ft5yo_prices_from_salary_curves <- function(salary_curves, current_season) {
  source_name <- paste0("End", substr(current_season - 1L, 3, 4), " Sal")
  cap_multiplier <- adl_salary_cap(current_season) / adl_salary_cap(current_season - 1L)
  tag_specs <- list(
    NEFT = 1:5,
    TT = 1:10,
    `5YO+` = 3:20,
    `5YO-` = 3:25
  )
  positions <- c("QB", "RB", "WR", "TE", "PK/PN", "DT", "DE", "LB", "CB", "S")

  rows <- bind_rows(lapply(names(tag_specs), function(tag_level) {
    ranks <- tag_specs[[tag_level]]
    bind_rows(lapply(positions, function(position) {
      salaries <- salary_curves |>
        filter(
          .data$salary_source == .env$source_name,
          .data$position == .env$position,
          .data$rank %in% .env$ranks
        ) |>
        arrange(.data$rank) |>
        pull(.data$salary)

      tibble(
        tag_level = tag_level,
        position = position,
        salary = if (length(salaries)) round(mean(salaries, na.rm = TRUE) * cap_multiplier, 2) else NA_real_
      )
    }))
  })) |>
    filter(!is.na(.data$salary))

  bind_rows(
    rows |> filter(.data$position != "PK/PN"),
    rows |>
      filter(.data$position == "PK/PN") |>
      select("tag_level", "salary") |>
      tidyr::crossing(position = c("PK", "PN")) |>
      select("tag_level", "position", "salary")
  )
}

find_adl_starter_cache_file <- function(cache_dir = adl_score_cache_dir, season) {
  files <- list.files(
    cache_dir,
    pattern = paste0("^ff_starters_ADL[0-9]{2}_", season, "_W1-[0-9]+_raw[.]rds$"),
    full.names = TRUE
  )
  if (!length(files)) return(NA_character_)
  files[which.max(file.info(files)$mtime)]
}

build_fifth_year_tsp_ranks <- function(season, cache_dir = adl_score_cache_dir) {
  starter_file <- find_adl_starter_cache_file(cache_dir, season)
  if (is.na(starter_file) || !file.exists(starter_file)) {
    warning("No ADL starter cache found for ", season, call. = FALSE)
    return(tibble(
      player_id = character(),
      fifth_year_tsp_pos = character(),
      fifth_year_starts = integer(),
      fifth_year_tsp_points = numeric(),
      fifth_year_tsp_rank = numeric()
    ))
  }

  readRDS(starter_file) |>
    as_tibble() |>
    mutate(
      season = as.integer(.data$season),
      week = as.integer(.data$week),
      player_id = as.character(.data$player_id),
      player_name = as.character(.data$player_name),
      fifth_year_tsp_pos = as.character(.data$pos),
      player_score = as.numeric(.data$player_score),
      starter_status = as.character(.data$starter_status)
    ) |>
    filter(
      .data$season == .env$season,
      .data$starter_status == "starter",
      !is.na(.data$player_id),
      !is.na(.data$fifth_year_tsp_pos)
    ) |>
    group_by(.data$season, .data$player_id, .data$player_name, .data$fifth_year_tsp_pos) |>
    summarise(
      fifth_year_starts = n(),
      fifth_year_tsp_points = sum(.data$player_score, na.rm = TRUE),
      .groups = "drop"
    ) |>
    group_by(.data$fifth_year_tsp_pos) |>
    mutate(
      fifth_year_tsp_rank = as.numeric(rank(-.data$fifth_year_tsp_points, ties.method = "min", na.last = "keep"))
    ) |>
    ungroup() |>
    select(
      player_id,
      fifth_year_tsp_pos,
      fifth_year_starts,
      fifth_year_tsp_points,
      fifth_year_tsp_rank
    )
}

ext_sheet_candidates <- bind_rows(
  read_ext_block(source_path, 1:25, "NFC"),
  read_ext_block(source_path, 27:51, "AFC")
) |>
  mutate(
    ext_player = player,
    roster_last = tolower(sub("^.*[.]\\s*", "", player))
  ) |>
  select(
    conference, franchise, roster_last, prev_salary, prev_years,
    ext_player, ext_years, week, fifth_year_option,
    starts_with("pr_"), starts_with("epv_"), eys, new_salary, new_years
  )

force_live <- identical(Sys.getenv("ADL_GM_FORCE_LIVE_ROSTERS", unset = "FALSE"), "TRUE")
current_rosters <- load_current_rosters(force_live = force_live)
current_season <- get_current_season()
ensure_pr_starter_floors_configured(current_season)
salary_curves <- build_salary_curves_from_scrapes(current_season)
ft5yo_prices <- build_ft5yo_prices_from_salary_curves(salary_curves, current_season)
today <- as.Date(Sys.getenv("ADL_GM_TODAY", unset = as.character(Sys.Date())))
current_ext_window <- if (format(today, "%m-%d") < "03-01") "oEXT" else "iEXT"
local_pr_summary <- build_ext_pr_summary(last_season = current_season) |>
  mutate(player_id = as.character(.data$player_id)) |>
  rename_with(\(x) paste0(x, "_local"), starts_with("pr_"))
fifth_year_tsp_ranks <- build_fifth_year_tsp_ranks(season = current_season - 1L)
fifth_year_draft_eligibility <- build_fifth_year_draft_eligibility(season = current_season - 3L)
player_visual_data <- build_player_visual_data(current_rosters)

ext_candidates <- current_rosters |>
  mutate(
    has_exercised_5yo = grepl("\\+$", trimws(.data$contract))
  ) |>
  left_join(
    ext_sheet_candidates,
    by = c("conference", "franchise", "roster_last", "prev_salary", "prev_years")
  ) |>
  left_join(
    fifth_year_draft_eligibility,
    by = c("conference", "player_id")
  ) |>
  left_join(
    local_pr_summary,
    by = "player_id"
  ) |>
  left_join(
    fifth_year_tsp_ranks,
    by = "player_id"
  ) |>
  left_join(
    player_visual_data,
    by = "player_id"
  ) |>
  mutate(
    robust_pr_count = coalesce(as.integer(.data$robust_pr_count), 0L),
    pr_current_pos = coalesce(.data$pr_current_pos_local, .data$pr_current_pos),
    pr_current_total = coalesce(.data$pr_current_total_local, .data$pr_current_total),
    pr_current_avg = coalesce(.data$pr_current_avg_local, .data$pr_current_avg),
    pr_current_final = coalesce(.data$pr_current_final_local, .data$pr_current_final),
    pr_recent_pos = coalesce(.data$pr_recent_pos_local, .data$pr_recent_pos),
    pr_recent_total = coalesce(.data$pr_recent_total_local, .data$pr_recent_total),
    pr_recent_avg = coalesce(.data$pr_recent_avg_local, .data$pr_recent_avg),
    pr_recent_final = coalesce(.data$pr_recent_final_local, .data$pr_recent_final),
    pr_previous_pos = coalesce(.data$pr_previous_pos_local, .data$pr_previous_pos),
    pr_previous_total = coalesce(.data$pr_previous_total_local, .data$pr_previous_total),
    pr_previous_avg = coalesce(.data$pr_previous_avg_local, .data$pr_previous_avg),
    pr_previous_final = coalesce(.data$pr_previous_final_local, .data$pr_previous_final),
    contract_year = suppressWarnings(as.integer(sub("^([0-9]{4}).*", "\\1", .data$contract))),
    is_fourth_year_rookie = !is.na(.data$contract_year) & .data$contract_year == .env$current_season - 3L,
    rookie_contract_type = case_when(
      grepl("^[0-9]{4} UDFA$", .data$contract) ~ "UDFA",
      grepl("^[0-9]{4} [0-9]+\\.[0-9]+", .data$contract) ~ "Drafted rookie",
      TRUE ~ NA_character_
    ),
    fifth_year_draft_qualified = !is.na(.data$fifth_year_draft_overall) &
      .data$fifth_year_draft_round == 1L &
      .data$fifth_year_draft_overall >= 1L &
      .data$fifth_year_draft_overall <= 16L,
    fifth_year_original_rookie_contract = grepl(
      paste0("^", .env$current_season - 3L, " 1[.][0-9]{2}[+]?$"),
      trimws(.data$contract)
    ),
    fifth_year_position_eligible = !.data$player_pos %in% c("PK", "PN"),
    fifth_year_tsp_pos = coalesce(.data$fifth_year_tsp_pos, .data$player_pos),
    fifth_year_tag_level = mapply(fifth_year_tag_level, .data$fifth_year_tsp_pos, .data$fifth_year_tsp_rank),
    fifth_year_option_salary = mapply(
      function(position, tag_level) {
        match <- ft5yo_prices |>
          filter(.data$position == .env$position, .data$tag_level == .env$tag_level) |>
          slice(1)
        if (nrow(match)) match$salary[[1]] else NA_real_
      },
      .data$fifth_year_tsp_pos,
      .data$fifth_year_tag_level
    ),
    fifth_year_option_eligible = .data$fifth_year_draft_qualified &
      .data$fifth_year_original_rookie_contract &
      .data$fifth_year_position_eligible,
    fifth_year_option_available = .data$fifth_year_option_eligible &
      !.data$has_exercised_5yo &
      .env$today < as.Date(paste0(.env$current_season, "-07-01")) &
      !is.na(.data$fifth_year_option_salary),
    fifth_year_option_ineligible = .data$fifth_year_draft_qualified &
      !.data$has_exercised_5yo &
      .env$today < as.Date(paste0(.env$current_season, "-07-01")) &
      !.data$fifth_year_option_eligible,
    fifth_year_option_ineligible_reason = mapply(
      function(original_rookie_contract, position_eligible) {
        reasons <- c(
          if (!isTRUE(original_rookie_contract)) "Rookie Contract Expired",
          if (!isTRUE(position_eligible)) "PK and PN are 5YO ineligible"
        )
        paste(reasons, collapse = "; ")
      },
      .data$fifth_year_original_rookie_contract,
      .data$fifth_year_position_eligible
    ),
    contract_tool = case_when(
      grepl("\\boEXT\\b", .data$contract) ~ "oEXT",
      grepl("\\biEXT\\b", .data$contract) ~ "iEXT",
      grepl("\\bmEXT\\b", .data$contract) ~ "mEXT",
      grepl("\\bB/R\\b", .data$contract) ~ "B/R",
      TRUE ~ NA_character_
    ),
    max_rookie_remaining_years = case_when(
      .data$rookie_contract_type == "UDFA" ~ pmax(0, 3 - (.env$current_season - .data$contract_year)),
      .data$rookie_contract_type == "Drafted rookie" ~ pmax(0, 4 - (.env$current_season - .data$contract_year)),
      TRUE ~ NA_real_
    ),
    rookie_signed_less_than_max = !is.na(.data$rookie_contract_type) &
      .data$prev_years < .data$max_rookie_remaining_years,
    ext_cooldown_ineligible = case_when(
      .env$current_ext_window == "oEXT" &
        .data$contract_tool == "oEXT" &
        .data$contract_year == .env$current_season ~ TRUE,
      .env$current_ext_window == "oEXT" &
        .data$contract_tool == "iEXT" &
        .data$contract_year == .env$current_season - 1L ~ TRUE,
      .env$current_ext_window == "iEXT" &
        .data$contract_tool == "oEXT" &
        .data$contract_year == .env$current_season ~ TRUE,
      .env$current_ext_window == "iEXT" &
        .data$contract_tool %in% c("mEXT", "B/R") &
        .data$contract_year == .env$current_season ~ TRUE,
      .env$current_ext_window == "iEXT" &
        .data$contract_tool == "iEXT" &
        .data$contract_year == .env$current_season ~ TRUE,
      TRUE ~ FALSE
    ),
    next_eligible_ext_year = case_when(
      .env$current_ext_window == "oEXT" &
        .data$contract_tool == "iEXT" &
        .data$contract_year == .env$current_season - 1L ~ .env$current_season,
      .data$contract_tool == "iEXT" ~ .data$contract_year + 1L,
      .data$contract_tool %in% c("oEXT", "mEXT", "B/R") ~ .data$contract_year + 1L,
      TRUE ~ NA_integer_
    ),
    next_eligible_ext_type = case_when(
      .env$current_ext_window == "oEXT" &
        .data$contract_tool == "iEXT" &
        .data$contract_year == .env$current_season - 1L ~ "iEXT",
      .data$contract_tool == "iEXT" ~ "iEXT",
      .data$contract_tool %in% c("oEXT", "mEXT", "B/R") ~ "oEXT",
      TRUE ~ NA_character_
    ),
    ext_cooldown_reason = case_when(
      .data$ext_cooldown_ineligible ~ paste0("Signed ", .data$contract, "; next eligible EXT is ", .data$next_eligible_ext_year, " ", .data$next_eligible_ext_type),
      TRUE ~ NA_character_
    ),
    ineligibility_reason = mapply(
      function(has_too_many_years, under_max_rookie, has_no_robust_prs, ext_cooldown_reason) {
        reasons <- c(
          if (isTRUE(has_too_many_years)) "2+ current contract years",
          if (isTRUE(under_max_rookie)) "rookie contract signed for less than maximum years",
          if (isTRUE(has_no_robust_prs)) "no Robust PRs",
          if (!is.na(ext_cooldown_reason) && nzchar(ext_cooldown_reason)) ext_cooldown_reason
        )
        paste(reasons, collapse = "; ")
      },
      .data$prev_years >= 2,
      .data$rookie_signed_less_than_max,
      .data$robust_pr_count == 0L,
      .data$ext_cooldown_reason
    ),
    ext_years = coalesce(ext_years, pmax(1, pmin(3, 6 - prev_years))),
    fifth_year_option = case_when(
      .data$has_exercised_5yo & !is.na(.data$fifth_year_option_salary) ~ .data$fifth_year_option_salary,
      TRUE ~ suppressWarnings(as.numeric(.data$fifth_year_option))
    ),
    week = coalesce(week, 0),
    eligibility_note = case_when(
      nzchar(.data$ineligibility_reason) ~ paste("Ineligible:", .data$ineligibility_reason),
      !is.na(ext_marker) & is.na(pr_recent_final) & is.na(pr_previous_final) ~ "Needs PR import before final pricing",
      TRUE ~ "Likely EXT eligible"
    )
  ) |>
  mutate(ext_window = .env$current_ext_window) |>
  select(
    conference, franchise, franchise_name, player, prev_salary, prev_years, ext_years, week,
    player_id, player_name, player_team, player_pos, roster_status,
    player_headshot, player_birth_date, player_jersey, player_rookie_season,
    player_draft_year, player_draft_round, player_draft_round_pick, player_draft_pick,
    team_logo_espn, team_logo_wikipedia, team_logo_squared, team_wordmark, team_color, team_color2,
    contract, ext_marker, fifth_year_option, eligibility_note,
    fifth_year_option_available, fifth_year_option_ineligible, fifth_year_option_ineligible_reason,
    fifth_year_draft_qualified, fifth_year_original_rookie_contract, fifth_year_position_eligible,
    has_exercised_5yo,
    fifth_year_option_salary, fifth_year_tag_level, fifth_year_tsp_pos, fifth_year_tsp_rank,
    fifth_year_tsp_points, fifth_year_starts,
    fifth_year_draft_year, fifth_year_draft_round, fifth_year_draft_pick, fifth_year_draft_overall,
    rookie_contract_type, max_rookie_remaining_years, rookie_signed_less_than_max,
    ext_window, contract_tool, ext_cooldown_ineligible, next_eligible_ext_year, next_eligible_ext_type,
    robust_pr_count,
    starts_with("pr_"), starts_with("epv_"), eys, new_salary, new_years
  ) |>
  arrange(conference, franchise, player)

write_csv(ext_candidates, file.path("data", "ext_candidates.csv"))
write_csv(salary_curves, file.path("data", "salary_curves.csv"))

message("Wrote data/ext_candidates.csv and data/salary_curves.csv")
