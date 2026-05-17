library(shiny)
library(bslib)
library(dplyr)
library(readr)
library(ggplot2)
library(scales)
library(jsonlite)

source("R/ext_engine.R")

players <- read_csv("data/ext_candidates.csv", show_col_types = FALSE)
salary_curves <- read_csv("data/salary_curves.csv", show_col_types = FALSE)
pr_history <- if (file.exists("data/pr_history.csv")) {
  read_csv("data/pr_history.csv", show_col_types = FALSE)
} else {
  tibble()
}
default_fifth_year_option <- function(row) {
  source_value <- suppressWarnings(as.numeric(row$fifth_year_option[[1]] %||% NA_real_))
  if (!is.na(source_value) && source_value > 0) return(source_value)

  NA_real_
}

has_exercised_fifth_year_option <- function(row) {
  isTRUE(row$has_exercised_5yo[[1]]) || grepl("\\+$", trimws(row$contract[[1]] %||% ""))
}

has_available_fifth_year_option <- function(row) {
  isTRUE(row$fifth_year_option_available[[1]])
}

has_ineligible_fifth_year_option <- function(row) {
  isTRUE(row$fifth_year_option_ineligible[[1]])
}

fifth_year_display_salary <- function(row) {
  exercised_value <- default_fifth_year_option(row)
  if (!is.na(exercised_value)) return(exercised_value)

  available_value <- suppressWarnings(as.numeric(row$fifth_year_option_salary[[1]] %||% NA_real_))
  if (!is.na(available_value) && available_value > 0) available_value else NA_real_
}

money <- function(x) dollar(x, prefix = "$", suffix = "m", accuracy = 0.01)
rank_label <- function(position, rank) {
  if (is.na(position) || is.na(rank)) return("--")
  paste0(position, format(as.numeric(rank), trim = TRUE, scientific = FALSE))
}
has_url <- function(x) {
  !is.null(x) && length(x) > 0 && !is.na(x[[1]]) && nzchar(x[[1]])
}
player_initials <- function(name) {
  name <- trimws(as.character(name %||% ""))
  if (!nzchar(name)) return("--")
  if (grepl(",", name)) {
    parts <- trimws(strsplit(name, ",\\s*")[[1]])
    first <- if (length(parts) >= 2) substr(parts[[2]], 1, 1) else ""
    last <- substr(parts[[1]], 1, 1)
  } else {
    parts <- trimws(strsplit(name, "\\s+")[[1]])
    first <- substr(parts[[1]], 1, 1)
    last <- if (length(parts) >= 2) substr(parts[[length(parts)]], 1, 1) else ""
  }
  toupper(paste0(first, last))
}
player_display_name <- function(name) {
  name <- trimws(as.character(name %||% ""))
  if (!nzchar(name)) return("--")
  if (!grepl(",", name)) return(name)
  parts <- trimws(strsplit(name, ",\\s*")[[1]])
  if (length(parts) < 2) return(name)
  trimws(paste(parts[[2]], parts[[1]]))
}
player_age <- function(birth_date, today = Sys.Date()) {
  birth_date <- suppressWarnings(as.Date(birth_date[[1]] %||% NA))
  if (is.na(birth_date)) return(NA_real_)
  round(as.numeric(difftime(today, birth_date, units = "days")) / 365.25, 1)
}
draft_label <- function(year, round, round_pick, pick, rookie_season = NA_integer_) {
  year <- suppressWarnings(as.integer(year[[1]] %||% NA_integer_))
  round <- suppressWarnings(as.integer(round[[1]] %||% NA_integer_))
  round_pick <- suppressWarnings(as.integer(round_pick[[1]] %||% NA_integer_))
  pick <- suppressWarnings(as.integer(pick[[1]] %||% NA_integer_))
  rookie_season <- suppressWarnings(as.integer(rookie_season[[1]] %||% NA_integer_))
  if (is.na(year) || is.na(round) || is.na(round_pick) || is.na(pick)) {
    if (!is.na(rookie_season)) return(paste0(rookie_season, " Undrafted"))
    return("--")
  }
  paste0(year, " ", round, ".", sprintf("%02d", round_pick), " (#", pick, " ovr)")
}
position_order <- c("QB", "RB", "WR", "TE", "PK", "PN", "DT", "DE", "LB", "CB", "S")
current_season <- as.integer(format(Sys.Date(), "%Y"))
options(adl.pr_starter_floor_season = current_season)
ensure_pr_starter_floors_configured(current_season)
salary_dispute_minimum <- 2.01
current_ext_window <- if (format(Sys.Date(), "%m-%d") < "03-01") "oEXT" else "iEXT"
current_nfl_week <- function(today = Sys.Date(), season = current_season) {
  env_week <- suppressWarnings(as.integer(Sys.getenv("ADL_CURRENT_WEEK", unset = NA_character_)))
  if (!is.na(env_week)) return(max(0, min(17, env_week)))

  score_metadata_path <- file.path("data", "score_metadata.csv")
  if (file.exists(score_metadata_path)) {
    score_metadata <- tryCatch(readr::read_csv(score_metadata_path, show_col_types = FALSE), error = function(e) NULL)
    if (!is.null(score_metadata) && nrow(score_metadata)) {
      cached_season <- suppressWarnings(as.integer(score_metadata$season[[1]] %||% NA_integer_))
      cached_week <- suppressWarnings(as.integer(score_metadata$week[[1]] %||% NA_integer_))
      if (identical(cached_season, as.integer(season)) && !is.na(cached_week)) {
        return(max(0, min(17, cached_week)))
      }
    }
  }

  if (format(today, "%m-%d") < "03-01") return(0)

  week_one_start <- as.Date(paste0(season, "-09-10"))
  if (today < week_one_start) return(1)
  max(1, min(17, floor(as.numeric(today - week_one_start) / 7) + 1))
}
extension_week_current <- current_nfl_week()
extension_week_max <- 16
extension_week_default <- min(extension_week_current, extension_week_max)
current_stats_finalized <- function(now = Sys.time()) {
  override <- Sys.getenv("ADL_STATS_FINALIZED", unset = "")
  if (nzchar(override)) {
    return(tolower(override) %in% c("1", "true", "yes", "official", "finalized"))
  }

  eastern <- as.POSIXlt(now, tz = "America/New_York")
  day <- eastern$wday
  hour <- eastern$hour + eastern$min / 60 + eastern$sec / 3600
  day > 4 || (day == 4 && hour >= 5)
}

nfl_bye_weeks_2026 <- c(
  CAR = 5, KCC = 5,
  CIN = 6, DET = 6, MIA = 6, MIN = 6,
  BUF = 7, JAC = 7, LAC = 7, WAS = 7,
  HOU = 8, NOS = 8, NYG = 8, SFO = 8,
  PIT = 9, TEN = 9,
  CHI = 10, DEN = 10, PHI = 10, TBB = 10,
  ATL = 11, CLE = 11, GBP = 11, LAR = 11, NEP = 11, SEA = 11,
  BAL = 13, IND = 13, LVR = 13, NYJ = 13,
  ARI = 14, DAL = 14
)

ui <- page_sidebar(
  title = tags$span(
    class = "app-title",
    tags$img(class = "app-title-shield", src = "adl-shield.png", alt = "ADL"),
    tags$span(class = "app-title-text", "Extension Calculator")
  ),
  theme = bs_theme(
    version = 5,
    bootswatch = "flatly",
    primary = "#235789",
    secondary = "#f2c14e",
    base_font = font_google("Inter"),
    heading_font = font_google("Inter")
  ),
  tags$style(HTML("
    body.bslib-page-sidebar {
      background: #f8fafc;
    }
    .navbar.navbar-static-top {
      background: linear-gradient(90deg, #8b8b8b 0%, #a3a9ae 10%, #c9ced3 28%, #d8dde2 44%, #d8dde2 100%);
      border: 0;
      border-bottom: 2px solid #c83a3f;
      box-shadow: 0 1px 8px rgba(15, 23, 42, 0.06);
      min-height: 6.4rem;
      margin-bottom: 0;
    }
    .navbar.navbar-static-top .container-fluid {
      min-height: 6.4rem;
      display: flex;
      align-items: center;
      padding: 0 1.35rem;
    }
    .bslib-page-title.navbar-brand {
      display: flex;
      align-items: center;
      gap: 0.8rem;
      margin: 0;
      padding: 0;
      color: #1f2937;
      font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      font-size: 2.75rem !important;
      line-height: 1;
      font-weight: 800;
      letter-spacing: 0;
    }
    .app-title {
      display: inline-flex;
      align-items: center;
      gap: 2.1rem;
    }
    .app-title-shield {
      width: 5.15rem;
      height: 6.1rem;
      object-fit: contain;
      display: inline-block;
    }
    .app-title-text {
      display: inline-flex;
      align-items: center;
      color: #1f2937;
      font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      font-size: 2.95rem !important;
      font-weight: 800;
      line-height: 1;
      white-space: nowrap;
    }
    .selectize-dropdown .ext-ineligible-option {
      color: #b42318;
    }
    .selectize-control .ext-ineligible-selected {
      color: #b42318;
    }
    .bslib-sidebar-layout {
      --bslib-sidebar-resize-handle-width: 0px;
    }
    .bslib-sidebar-layout .bslib-sidebar-resize-handle {
      display: none !important;
      pointer-events: none !important;
    }
    .bslib-sidebar-layout > .sidebar {
      overflow-y: auto;
      resize: none;
    }
    .bslib-sidebar-layout > .sidebar > .sidebar-content {
      overflow: visible;
    }
    .eligibility-wrap {
      display: flex;
      align-items: center;
      gap: 1rem;
      flex-wrap: wrap;
      margin: 0 0 1rem 0;
    }
    .eligibility-pill {
      display: inline-flex;
      align-items: center;
      gap: 0.65rem;
      border: 0;
      border-radius: 0.45rem;
      padding: 0.75rem 0.95rem;
      font-weight: 700;
      line-height: 1.2;
      font-size: 1.35rem;
    }
    .eligibility-pill.eligible {
      color: #084c2e;
      background: #d1fae5;
      border: 1px solid #86efac;
    }
    .eligibility-pill.ineligible {
      color: #7f1d1d;
      background: #fee2e2;
      border: 1px solid #fca5a5;
    }
    .eligibility-icon {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 1.35rem;
      height: 1.35rem;
      border-radius: 999px;
      font-size: 1.35rem;
      line-height: 1;
    }
    .eligibility-subtext {
      display: block;
      margin-top: 0.35rem;
      font-weight: 500;
      font-size: 0.9rem;
    }
    .eligibility-subtext-line {
      display: block;
    }
    .robust-season-report {
      display: grid;
      grid-template-rows: repeat(4, 1fr);
      align-self: stretch;
      min-height: 5.35rem;
      padding: 0.12rem 0;
      color: #1f2937;
      font-size: 0.92rem;
      line-height: 1.15;
      min-width: 22rem;
    }
    .robust-season-row {
      display: flex;
      align-items: center;
      gap: 0.12rem;
      white-space: nowrap;
    }
    .robust-season-year {
      font-weight: 700;
      color: #374151;
      min-width: 3.15rem;
    }
    .robust-season-status {
      font-weight: 700;
      display: inline-block;
    }
    .robust-season-state {
      display: inline-flex;
      align-items: center;
      gap: 0.12rem;
      min-width: 5.85rem;
    }
    .robust-season-status.robust,
    .robust-season-icon.robust,
    .robust-season-ranks.robust {
      color: #087443;
    }
    .robust-season-status.not-robust,
    .robust-season-icon.not-robust,
    .robust-season-ranks.not-robust {
      color: #b42318;
    }
    .robust-season-icon {
      font-weight: 800;
      font-size: 1rem;
      line-height: 1;
    }
    .robust-season-gp {
      display: inline-block;
      min-width: 7.5rem;
    }
    .robust-season-ranks {
      display: inline-flex;
      gap: 0.25rem;
      font-weight: 700;
      margin-left: 0.85rem;
    }
    .robust-season-rank {
      display: inline-block;
      min-width: 5.25rem;
    }
    .current-contract-line {
      display: flex;
      align-items: flex-end;
      gap: 1.8rem;
      flex-wrap: wrap;
      margin-bottom: 0.42rem;
      font-size: 1.95rem;
      line-height: 1.15;
      color: #1f2937;
    }
    .player-identity {
      display: inline-flex;
      align-items: center;
      gap: 0.85rem;
      min-width: 0;
    }
    .player-name-stack {
      display: inline-flex;
      flex-direction: column;
      gap: 0.18rem;
      min-width: 0;
    }
    .player-avatar-wrap {
      position: relative;
      width: 5.75rem;
      height: 5.75rem;
      flex: 0 0 auto;
    }
    .player-headshot,
    .player-headshot-fallback {
      width: 5.75rem;
      height: 5.75rem;
      border-radius: 0.4rem;
      object-fit: cover;
      background: transparent;
      border: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      color: #6b7280;
      font-size: 1.18rem;
      font-weight: 900;
      overflow: hidden;
    }
    .player-headshot-fallback {
      background: #f3f4f6;
      border: 1px solid #e5e7eb;
      border-radius: 0.4rem;
    }
    .team-logo-badge,
    .team-logo-fallback {
      width: 3rem;
      height: 3rem;
      border-radius: 999px;
      background: transparent;
      border: 0;
      box-shadow: none;
      display: flex;
      align-items: center;
      justify-content: center;
      object-fit: contain;
      padding: 0.12rem;
    }
    .team-logo-fallback {
      color: #111827;
      background: #f3f4f6;
      border: 1px solid #e5e7eb;
      font-size: 0.84rem;
      font-weight: 900;
      padding: 0;
    }
    .player-name-row {
      display: inline-flex;
      align-items: center;
      gap: 0.55rem;
      min-width: 0;
    }
    .current-contract-line .player-name {
      font-weight: 700;
      margin-right: 0.4rem;
      font-size: 2.28rem;
      line-height: 1.05;
    }
    .player-team-pos {
      font-weight: 800;
      white-space: nowrap;
    }
    .player-bio-line {
      color: #6b7280;
      font-size: 0.98rem;
      line-height: 1.15;
      font-weight: 700;
      white-space: nowrap;
    }
    .current-contract-line .contract-field {
      display: inline-flex;
      flex-direction: column;
      gap: 0.12rem;
      white-space: nowrap;
    }
    .current-contract-line .contract-label {
      font-size: 0.72rem;
      line-height: 1;
      color: #6b7280;
      text-transform: uppercase;
      letter-spacing: 0;
      font-weight: 700;
    }
    .current-contract-line .contract-value {
      font-size: 1.15rem;
      line-height: 1.1;
      color: #1f2937;
      font-weight: 600;
    }
    .fifth-year-stack {
      display: inline-flex;
      flex-direction: column;
      align-items: flex-start;
      align-self: center;
      gap: 0.32rem;
      white-space: nowrap;
    }
    .fifth-year-note {
      display: inline-flex;
      align-items: center;
      color: #174ea6;
      background: #dbeafe;
      border: 1px solid #93c5fd;
      border-radius: 0.42rem;
      padding: 0.42rem 0.58rem;
      font-size: 0.95rem;
      line-height: 1.1;
      font-weight: 800;
      white-space: nowrap;
    }
    .fifth-year-note.ineligible {
      color: #991b1b;
      background: #fee2e2;
      border-color: #fca5a5;
    }
    .fifth-year-detail {
      color: #174ea6;
      font-size: 0.88rem;
      line-height: 1.15;
      font-weight: 700;
      white-space: nowrap;
    }
    .fifth-year-detail.ineligible {
      color: #b42318;
    }
    .fifth-year-sim {
      margin: 0;
      color: #174ea6;
      font-size: 0.95rem;
      font-weight: 700;
      line-height: 1.15;
    }
    .fifth-year-sim .shiny-input-container {
      margin-bottom: 0;
    }
    .fifth-year-sim .form-check {
      margin-bottom: 0;
      min-height: 0;
    }
    .fifth-year-sim .form-check-input {
      border: 2px solid #174ea6;
      box-shadow: none;
    }
    .fifth-year-sim-row {
      margin: 0.65rem 0 -0.45rem 0;
    }
    .pr-summary-row {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 2rem;
      margin: 1.15rem 0 1.35rem 0;
      color: #1f2937;
    }
    .pr-summary-section {
      min-width: 0;
    }
    .pr-summary-title {
      display: flex;
      align-items: baseline;
      gap: 0.55rem;
      margin-bottom: 0.35rem;
    }
    .pr-summary-label {
      font-size: 0.78rem;
      line-height: 1;
      color: #6b7280;
      text-transform: uppercase;
      letter-spacing: 0;
      font-weight: 800;
    }
    .pr-summary-year {
      font-size: 1.05rem;
      line-height: 1;
      color: #1f2937;
      font-weight: 700;
    }
    .pr-summary-year-badge {
      font-size: 0.78rem;
      line-height: 1;
      color: #6b7280;
      text-transform: lowercase;
      letter-spacing: 0;
      font-weight: 800;
    }
    .pr-summary-ranks {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 0.35rem;
      max-width: 20rem;
    }
    .pr-summary-rank-label {
      display: block;
      font-size: 0.72rem;
      line-height: 1;
      color: #6b7280;
      text-transform: uppercase;
      letter-spacing: 0;
      font-weight: 700;
      margin-bottom: 0.18rem;
    }
    .pr-summary-rank-value {
      display: block;
      font-size: 1.25rem;
      line-height: 1.05;
      font-weight: 500;
    }
    .pr-summary-rank-value.used {
      font-weight: 900;
    }
    .pr-summary-epv-value {
      display: block;
      font-size: 1.25rem;
      line-height: 1.05;
      font-weight: 500;
    }
    .pr-summary-epv-value.used {
      font-weight: 900;
    }
    .pr-summary-note {
      display: block;
      color: #6b7280;
      font-size: 0.72rem;
      line-height: 1.05;
      margin-top: 0.18rem;
      white-space: nowrap;
    }
    .pr-summary-note.estimate {
      color: #8a5a00;
      font-weight: 700;
    }
    .pr-summary-helper {
      color: #6b7280;
      font-size: 0.78rem;
      line-height: 1.15;
      margin-top: 0.38rem;
      font-weight: 600;
    }
    .epv-math-row {
      display: block;
      margin: -0.65rem 0 0.45rem 0;
      color: #1f2937;
    }
    .epv-math-title {
      color: #6b7280;
      font-size: 0.78rem;
      line-height: 1;
      text-transform: uppercase;
      letter-spacing: 0;
      font-weight: 800;
      white-space: nowrap;
    }
    .epv-math-subtitle {
      color: #6b7280;
      font-size: 0.82rem;
      line-height: 1.15;
      margin: 0.25rem 0 0.35rem 0;
    }
    .epv-math-items {
      display: flex;
      flex-direction: column;
      gap: 0;
      align-items: flex-start;
    }
    .epv-math-item {
      display: inline-flex;
      gap: 0.35rem;
      align-items: baseline;
      white-space: nowrap;
    }
    .epv-math-player {
      font-weight: 700;
    }
    .epv-math-salary {
      color: #374151;
      font-weight: 600;
    }
    .epv-math-adjustment {
      color: #6b7280;
      font-weight: 500;
    }
    .epv-math-op {
      color: #6b7280;
      font-weight: 800;
      margin-top: 0.2rem;
    }
    .epv-math-average {
      display: inline-flex;
      gap: 0.35rem;
      align-items: baseline;
      margin-top: 0.2rem;
    }
    .epv-math-result {
      color: #1f2937;
      font-size: 1.1rem;
      font-weight: 900;
      white-space: nowrap;
    }
    .pricing-bridge {
      display: grid;
      grid-template-columns: minmax(7.5rem, max-content) auto minmax(6rem, max-content) auto minmax(7rem, max-content) auto minmax(7rem, max-content);
      align-items: start;
      gap: 0.55rem;
      margin: 0.7rem 0 1rem 0;
      color: #1f2937;
      width: fit-content;
    }
    .pricing-step {
      min-width: 0;
    }
    .pricing-label {
      display: block;
      font-size: 0.72rem;
      line-height: 1;
      color: #6b7280;
      text-transform: uppercase;
      letter-spacing: 0;
      font-weight: 800;
      margin-bottom: 0.22rem;
    }
    .pricing-value {
      display: block;
      font-size: 1.45rem;
      line-height: 1.05;
      font-weight: 500;
      white-space: nowrap;
    }
    .pricing-value.new-sal {
      font-weight: 900;
    }
    .pricing-value.discount-good {
      color: #087443;
    }
    .pricing-value.discount-bad {
      color: #b42318;
    }
    .pricing-subtext {
      display: block;
      color: #6b7280;
      font-size: 0.82rem;
      line-height: 1.15;
      margin-top: 0.18rem;
    }
    .pricing-subtext.estimate {
      color: #8a5a00;
      font-weight: 700;
    }
    .pricing-operator {
      color: #6b7280;
      font-size: 1.35rem;
      font-weight: 800;
      line-height: 1;
      padding-top: 0.94rem;
    }
    .smoothing-table-wrap {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(8rem, 9.5rem);
      align-items: start;
      gap: 1.5rem;
      margin: 0.2rem 0 1.35rem 0;
    }
    .smoothing-table-main {
      min-width: 0;
    }
    .smoothing-table-title {
      display: flex;
      align-items: baseline;
      gap: 0.6rem;
      margin-bottom: 0.45rem;
    }
    .smoothing-table-title-main {
      color: #1f2937;
      font-size: 0.78rem;
      line-height: 1;
      text-transform: uppercase;
      letter-spacing: 0;
      font-weight: 800;
    }
    .smoothing-table-title-sub {
      color: #6b7280;
      font-size: 0.86rem;
      line-height: 1;
    }
    .smoothing-table {
      width: auto;
      border-collapse: collapse;
      color: #1f2937;
    }
    .smoothing-table th {
      color: #6b7280;
      font-size: 0.72rem;
      line-height: 1;
      text-transform: uppercase;
      letter-spacing: 0;
      font-weight: 800;
      padding: 0.28rem 0;
      text-align: left;
      white-space: nowrap;
    }
    .smoothing-table td {
      padding: 0.25rem 0;
      font-size: 0.98rem;
      line-height: 1.15;
      white-space: nowrap;
    }
    .smoothing-table .number {
      font-weight: 700;
    }
    .smoothing-table .smoothed-number {
      color: #087443;
      font-weight: 800;
    }
    .smoothing-table .smoothing-calc {
      color: #6b7280;
      font-size: 0.82rem;
      font-weight: 700;
      margin-left: 0.4rem;
    }
    .smoothing-table .sum-row td {
      padding-top: 0.45rem;
    }
    .smoothing-table .sum-row .sum-emphasis {
      font-weight: 900;
    }
    .smoothing-table tr.excluded-row td,
    .smoothing-table tr.excluded-row .number,
    .smoothing-table tr.excluded-row .smoothed-number,
    .smoothing-table tr.excluded-row .year-type {
      color: #9ca3af;
    }
    .smoothing-table .sum-label {
      color: #1f2937;
      text-transform: uppercase;
      font-size: 0.78rem;
      letter-spacing: 0;
      font-weight: 900;
    }
    .smoothing-table .bridge-cell {
      width: auto;
      min-width: 0;
      padding-right: 2.2rem;
    }
    .smoothing-table .spacer-cell {
      width: 2.2rem;
      min-width: 2.2rem;
    }
    .smoothing-table .type-spacer {
      width: 1.25rem;
      min-width: 1.25rem;
    }
    .smoothing-table .bridge-cell {
      color: #6b7280;
      font-size: 0.82rem;
      font-weight: 700;
      text-align: left;
    }
    .smoothing-table .bridge-cell sup {
      margin-left: -0.08rem;
    }
    .smoothing-table .year-type {
      color: #1f2937;
    }
    .starter-floor-reference {
      color: #1f2937;
    }
    .starter-floor-title {
      color: #1f2937;
      font-size: 0.78rem;
      line-height: 1;
      text-transform: uppercase;
      letter-spacing: 0;
      font-weight: 800;
      margin-bottom: 0.45rem;
    }
    .starter-floor-note {
      color: #8a5a00;
      font-size: 0.76rem;
      line-height: 1.1;
      font-weight: 700;
      margin: -0.2rem 0 0.45rem 0;
    }
    .starter-floor-table {
      width: auto;
      border-collapse: collapse;
    }
    .starter-floor-table td {
      padding: 0.15rem 0;
      font-size: 0.92rem;
      line-height: 1.12;
      white-space: nowrap;
    }
    .starter-floor-position {
      color: #6b7280;
      font-weight: 800;
      padding-right: 0.55rem;
    }
    .starter-floor-rank {
      font-weight: 800;
      text-align: right;
    }
    .starter-floor-min td {
      padding-bottom: 0.42rem;
    }
    .irs-min,
    .irs-max {
      display: none;
    }
    .slider-grid {
      position: relative;
      display: block;
      height: 2.05rem;
      margin: -1.35rem 0.65rem 0.45rem 0.65rem;
      padding: 0;
      color: #111827;
      font-size: 0.72rem;
      line-height: 1;
      overflow: visible;
    }
    .slider-grid.years-grid {
      height: 1.25rem;
    }
    .slider-tick {
      position: absolute;
      top: 0;
      transform: translateX(-50%);
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 0.18rem;
      min-width: 0.75rem;
    }
    .slider-tick::before {
      content: '';
      width: 1px;
      height: 0.38rem;
      background: #9ca3af;
      display: block;
    }
    .slider-tick.week-past,
    .slider-tick.year-disabled {
      color: #9ca3af;
    }
    .slider-tick.week-current {
      color: #111827;
      font-weight: 900;
    }
    .slider-marker {
      font-weight: 900;
      line-height: 0.75rem;
    }
    .slider-marker-line {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 0.18rem;
      min-height: 0.75rem;
      line-height: 0.75rem;
      margin-top: 0.02rem;
    }
    .slider-marker.robust {
      color: #235789;
    }
    .slider-marker.bye {
      color: #111827;
    }
    .slider-helper,
    .slider-legend,
    .year-cap-note,
    #roster_status {
      color: #6b7280;
      font-size: 0.875rem;
      line-height: 1.35;
      margin-top: 0.25rem;
      margin-bottom: 0.75rem;
    }
    .current-week-helper {
      color: #111827;
      font-weight: 800;
    }
    @media (max-width: 850px) {
      .pr-summary-row {
        grid-template-columns: 1fr;
        gap: 0.85rem;
      }
      .epv-math-row {
        grid-template-columns: 1fr;
        gap: 0.25rem;
      }
      .pricing-bridge {
        grid-template-columns: 1fr;
        gap: 0.55rem;
      }
      .pricing-operator {
        display: none;
      }
      .smoothing-table-wrap {
        grid-template-columns: 1fr;
      }
    }
  ")),
  sidebar = sidebar(
    width = 330,
    selectInput("conference", "Conference", choices = sort(unique(players$conference))),
    uiOutput("franchise_ui"),
    uiOutput("player_ui"),
    tags$div(
      class = "ext-week-slider",
      tags$label(`for` = "week", class = "control-label", "Extension week"),
      tags$div(class = "slider-helper current-week-helper", paste0("Current Week = ", extension_week_current)),
      sliderInput(
        "week",
        NULL,
        min = 0,
        max = extension_week_max,
        value = extension_week_default,
        step = 1,
        ticks = FALSE
      ),
      uiOutput("week_tick_grid")
    ),
    uiOutput("ext_years_ui"),
    actionButton("refresh_rosters", "Refresh rosters"),
    textOutput("roster_status")
  ),
  uiOutput("current_contract_line"),
  uiOutput("eligibility_badge"),
  uiOutput("pr_summary_row"),
  uiOutput("epv_math_row"),
  uiOutput("fifth_year_simulation_control"),
  uiOutput("pricing_bridge"),
  uiOutput("smoothing_table"),
  layout_columns(
    card(
      card_header("Position Rank Inputs"),
      tableOutput("pr_table")
    ),
    card(
      card_header("Caps and Flags"),
      uiOutput("flags")
    )
  )
)

server <- function(input, output, session) {
  players_data <- reactiveVal(players)
  pr_history_data <- reactiveVal(pr_history)
  last_selected_player <- reactiveVal(NULL)

  output$roster_status <- renderText({
    metadata_path <- file.path("data", "roster_metadata.csv")
    if (file.exists(metadata_path)) {
      metadata <- read_csv(metadata_path, show_col_types = FALSE)
      return(paste0("Rosters scraped at ", metadata$refreshed_at[[1]]))
    }
    roster_cache <- file.path("data", "current_rosters.csv")
    if (!file.exists(roster_cache)) return("Roster cache not written yet")
    paste("Roster cache:", format(file.info(roster_cache)$mtime, "%b %d %I:%M %p"))
  })

  observeEvent(input$refresh_rosters, {
    withProgress(message = "Refreshing rosters from MFL", value = 0.2, {
      old_force <- Sys.getenv("ADL_GM_FORCE_LIVE_ROSTERS", unset = NA_character_)
      on.exit({
        if (is.na(old_force)) {
          Sys.unsetenv("ADL_GM_FORCE_LIVE_ROSTERS")
        } else {
          Sys.setenv(ADL_GM_FORCE_LIVE_ROSTERS = old_force)
        }
      }, add = TRUE)

      Sys.setenv(ADL_GM_FORCE_LIVE_ROSTERS = "TRUE")
      source("scripts/prepare_ext_data.R", local = new.env(parent = globalenv()))
      incProgress(0.7)
      refreshed <- read_csv("data/ext_candidates.csv", show_col_types = FALSE)
      players_data(refreshed)
      if (file.exists("data/pr_history.csv")) {
        pr_history_data(read_csv("data/pr_history.csv", show_col_types = FALSE))
      }

      conferences <- sort(unique(refreshed$conference))
      selected_conference <- if (input$conference %in% conferences) input$conference else conferences[[1]]
      updateSelectInput(session, "conference", choices = conferences, selected = selected_conference)
    })
  })

  output$franchise_ui <- renderUI({
    req(input$conference)
    choices <- players_data() |>
      filter(conference == input$conference) |>
      distinct(franchise) |>
      arrange(franchise) |>
      pull(franchise)
    selectInput("franchise", "Franchise", choices = choices)
  })

  output$player_ui <- renderUI({
    req(input$conference, input$franchise)
    player_rows <- players_data() |>
      filter(conference == input$conference, franchise == input$franchise) |>
      mutate(player_pos_order = factor(player_pos, levels = position_order, ordered = TRUE)) |>
      arrange(player_pos_order, player_name, player)

    choices <- player_rows |> pull(player)
    ineligible_players <- player_rows |>
      filter(grepl("^Ineligible", eligibility_note)) |>
      pull(player)
    ineligible_json <- jsonlite::toJSON(ineligible_players, auto_unbox = TRUE)

    selectizeInput(
      "player",
      "Player",
      choices = stats::setNames(choices, choices),
      options = list(
        render = I(sprintf(
          "{
            option: function(item, escape) {
              var ineligible = %s.indexOf(item.value) !== -1;
              return '<div class=\"option ' + (ineligible ? 'ext-ineligible-option' : '') + '\">' + escape(item.label) + '</div>';
            },
            item: function(item, escape) {
              var ineligible = %s.indexOf(item.value) !== -1;
              return '<div class=\"item ' + (ineligible ? 'ext-ineligible-selected' : '') + '\">' + escape(item.label) + '</div>';
            }
          }",
          ineligible_json,
          ineligible_json
        ))
      )
    )
  })

  selected_player <- reactive({
    if (is.null(input$conference) || is.null(input$franchise) || is.null(input$player)) {
      req(last_selected_player())
      return(last_selected_player())
    }

    row <- players_data() |>
      filter(conference == input$conference, franchise == input$franchise, player == input$player) |>
      slice(1)
    if (nrow(row) == 1) {
      last_selected_player(row)
      row
    } else {
      req(last_selected_player())
      last_selected_player()
    }
  })

  selected_max_ext_years <- reactive({
    row <- selected_player()
    max(0, min(6, floor(6 - as.numeric(row$prev_years))))
  })

  current_season_gp <- reactive({
    row <- selected_player()
    history <- pr_history_data()
    if (!nrow(history)) return(0L)

    current <- history |>
      filter(.data$season == current_season, .data$player_id == row$player_id) |>
      slice(1)

    if (!nrow(current) || is.na(current$gp[[1]])) 0L else as.integer(current$gp[[1]])
  })

  earliest_robust_week <- reactive({
    row <- selected_player()
    gp <- current_season_gp()
    if (!is.na(gp) && gp >= 8L) return(extension_week_current)

    bye_week <- unname(nfl_bye_weeks_2026[row$player_team])
    if (extension_week_current > extension_week_max) return(NA_integer_)
    candidate_weeks <- seq(max(1, extension_week_current), extension_week_max)
    if (!is.null(bye_week) && !is.na(bye_week)) {
      candidate_weeks <- candidate_weeks[candidate_weeks != bye_week]
    }

    games_needed <- max(0L, 8L - gp)
    if (games_needed == 0L) return(extension_week_current)
    if (length(candidate_weeks) < games_needed) return(NA_integer_)
    candidate_weeks[[games_needed]]
  })

  output$week_tick_grid <- renderUI({
    robust_week <- earliest_robust_week()
    row <- selected_player()
    bye_week <- unname(nfl_bye_weeks_2026[row$player_team])

    tagList(
      tags$div(
        class = "slider-grid week-grid",
        lapply(0:extension_week_max, function(week) {
          tick_class <- if (week < extension_week_current) {
            "week-past"
          } else if (week == extension_week_current) {
            "week-current"
          } else {
            "week-future"
          }

          tags$span(
            class = paste("slider-tick", tick_class),
            style = paste0("left: ", round(week / extension_week_max * 100, 4), "%;"),
            tags$span(week),
            tags$span(
              class = "slider-marker-line",
              if (!is.na(bye_week) && week == bye_week) {
                tags$span(class = "slider-marker bye", "B")
              },
              if (!is.na(robust_week) && week == robust_week) {
                tags$span(class = "slider-marker robust", "R")
              },
              if ((is.na(bye_week) || week != bye_week) && (is.na(robust_week) || week != robust_week)) {
                HTML("&nbsp;")
              }
            )
          )
        })
      ),
      tags$div(
        class = "slider-legend",
        tags$div("B = bye week"),
        tags$div("R = earliest possible Robust season")
      )
    )
  })

  output$ext_years_ui <- renderUI({
    max_years <- selected_max_ext_years()
    current_value <- if (max_years < 1) 0 else 1
    slider_min <- if (max_years < 1) 0 else 1
    slider_max <- max(slider_min, max_years)
    slider_value <- min(max(current_value, slider_min), slider_max)
    year_ticks <- seq(slider_min, slider_max)

    tags$div(
      class = "ext-years-slider",
      tags$label(`for` = "ext_years", class = "control-label", "Years to add"),
      if (max_years < 6) {
        tags$div(
          class = "slider-helper",
          paste0("Maximum: ", max_years, " (6 contract years max)")
        )
      },
      sliderInput(
        "ext_years",
        NULL,
        min = slider_min,
        max = slider_max,
        value = slider_value,
        step = 1,
        ticks = FALSE
      ),
      tags$div(
        class = "slider-grid years-grid",
        lapply(year_ticks, function(year) {
          tick_pct <- if (slider_max == slider_min) 0 else (year - slider_min) / (slider_max - slider_min) * 100
          tags$span(
            class = "slider-tick year-enabled",
            style = paste0("left: ", round(tick_pct, 4), "%;"),
            tags$span(year)
          )
        })
      )
    )
  })

  selected_fifth_year_option <- reactive({
    row <- selected_player()
    salary <- fifth_year_display_salary(row)
    if (is.na(salary)) return(NA_real_)

    if (has_exercised_fifth_year_option(row) || (has_available_fifth_year_option(row) && isTRUE(input$simulate_5yo))) {
      salary
    } else {
      NA_real_
    }
  })

  observeEvent(input$player, {
    max_years <- selected_max_ext_years()
    slider_min <- if (max_years < 1) 0 else 1
    slider_max <- max(slider_min, max_years)
    reset_years <- if (max_years < 1) 0 else 1

    session$onFlushed(function() {
      updateSliderInput(
        session,
        "ext_years",
        min = slider_min,
        max = slider_max,
        value = reset_years
      )
    }, once = TRUE)
  }, ignoreInit = TRUE)

  observeEvent(input$ext_years, {
    max_years <- selected_max_ext_years()
    if (!is.null(input$ext_years) && input$ext_years > max_years) {
      updateSliderInput(session, "ext_years", value = max_years)
    }
  }, ignoreInit = TRUE)

  result <- reactive({
    req(input$ext_years, input$week)
    extension_breakdown(
      selected_player(),
      input$ext_years,
      input$week,
      salary_curves,
      fifth_year_option = selected_fifth_year_option()
    )
  })

  robust_season_rows <- reactive({
    row <- selected_player()
    history <- pr_history_data()
    seasons <- seq(current_season, current_season - 3L)

    if (!nrow(history)) {
      return(tibble(season = seasons, gp = NA_integer_, robust_pr = NA))
    }

    history |>
      filter(player_id == row$player_id, season %in% seasons) |>
      select(season, pos, gp, robust_pr, pr_total, pr_avg) |>
      right_join(tibble(season = seasons), by = "season") |>
      arrange(desc(season))
  })

  priced_rank_label <- function(position, rank) {
    floor_rank <- starter_floor(position)
    if (is.na(position) || is.na(rank) || is.na(floor_rank)) return("--")

    evaluated_rank <- min(max(round_rank_half(rank), 1), floor_rank, na.rm = TRUE)
    label <- rank_label(position, evaluated_rank)
    if (isTRUE(all.equal(evaluated_rank, floor_rank))) {
      paste0(label, " (Starter Floor)")
    } else {
      label
    }
  }

  true_rank_label <- function(position, rank) {
    if (is.na(position) || is.na(rank)) return("--")
    rank_label(position, rank)
  }

  uses_starter_floor <- function(position, rank) {
    floor_rank <- starter_floor(position)
    if (is.na(position) || is.na(rank) || is.na(floor_rank)) return(FALSE)
    evaluated_rank <- min(max(round_rank_half(rank), 1), floor_rank, na.rm = TRUE)
    isTRUE(all.equal(evaluated_rank, floor_rank))
  }

  pr_summary_section <- function(title, year, position, total_rank, avg_rank, final_rank, total_epv, avg_epv, epv, epv_note = NULL, estimate_note = NULL, overall_used = FALSE, year_badge = NULL, helper_text = NULL) {
    total_used <- overall_used && !is.na(total_rank) && !is.na(final_rank) && isTRUE(all.equal(as.numeric(total_rank), as.numeric(final_rank)))
    avg_used <- overall_used && !is.na(avg_rank) && !is.na(final_rank) && isTRUE(all.equal(as.numeric(avg_rank), as.numeric(final_rank)))

    tags$div(
      class = "pr-summary-section",
      tags$div(
        class = "pr-summary-title",
        tags$span(class = "pr-summary-label", title),
        tags$span(class = "pr-summary-year", ifelse(is.na(year), "--", year)),
        if (!is.null(year_badge) && nzchar(year_badge)) {
          tags$span(class = "pr-summary-year-badge", year_badge)
        }
      ),
      tags$div(
        class = "pr-summary-ranks",
        tags$span(
          tags$span(class = "pr-summary-rank-label", "Tot"),
          tags$span(class = paste("pr-summary-rank-value", if (total_used) "used" else ""), ifelse(is.na(total_epv), "--", money(total_epv))),
          tags$span(class = "pr-summary-note", true_rank_label(position, total_rank))
        ),
        tags$span(
          tags$span(class = "pr-summary-rank-label", "Avg"),
          tags$span(class = paste("pr-summary-rank-value", if (avg_used) "used" else ""), ifelse(is.na(avg_epv), "--", money(avg_epv))),
          tags$span(class = "pr-summary-note", true_rank_label(position, avg_rank))
        ),
        tags$span(
          tags$span(class = "pr-summary-rank-label", "EPV"),
          tags$span(class = paste("pr-summary-epv-value", if (overall_used) "used" else ""), ifelse(is.na(epv), "--", money(epv))),
          tags$span(class = "pr-summary-note", epv_note %||% "--"),
          NULL
        )
      ),
      if (!is.null(helper_text) && nzchar(helper_text)) {
        tags$div(class = "pr-summary-helper", helper_text)
      }
    )
  }

  build_pr_summary <- function(row, week) {
    curve_context <- salary_curve_context(week, salary_curves = salary_curves)
    estimate_note <- if (isTRUE(curve_context$estimated)) curve_context$label else NULL
    stats_finalized <- current_stats_finalized()
    current_year_badge <- paste0("(", if (stats_finalized) "official" else "unofficial", "*)")
    current_helper_text <- paste0(
      "* Week ",
      extension_week_current,
      " stats ",
      if (stats_finalized) "finalized" else "not finalized"
    )
    pr_input <- function(key, title, year, position, total_rank, avg_rank, final_rank) {
      effective_final_rank <- final_rank %||% if (identical(key, "current")) starter_floor(position) else NA_real_
      epv_note <- if (is.na(position) || is.na(effective_final_rank)) {
        NULL
      } else if (uses_starter_floor(position, effective_final_rank)) {
        priced_rank_label(position, effective_final_rank)
      } else {
        true_rank_label(position, effective_final_rank)
      }
      list(
        key = key,
        title = title,
        year = year,
        position = position,
        total_rank = total_rank,
        avg_rank = avg_rank,
        final_rank = final_rank,
        effective_final_rank = effective_final_rank,
        total_epv = performance_salary_unfloored(position, total_rank, salary_curves, week),
        avg_epv = performance_salary_unfloored(position, avg_rank, salary_curves, week),
        epv_note = epv_note,
        epv = performance_salary(position, effective_final_rank, salary_curves, week),
        year_badge = if (identical(key, "current") && identical(as.integer(year), current_season)) current_year_badge else NULL,
        helper_text = if (identical(key, "current") && identical(as.integer(year), current_season)) current_helper_text else NULL
      )
    }

    pr_inputs <- list(
      pr_input(
        "current",
        "Current Pos Rank",
        current_season,
        row$pr_current_pos %||% row$player_pos,
        row$pr_current_total,
        row$pr_current_avg,
        row$pr_current_final
      ),
      pr_input(
        "recent",
        "Recent Robust Pos Rank",
        row$pr_recent_season_local %||% NA_real_,
        row$pr_recent_pos,
        row$pr_recent_total,
        row$pr_recent_avg,
        row$pr_recent_final
      ),
      pr_input(
        "previous",
        "Previous Robust Pos Rank",
        row$pr_previous_season_local %||% NA_real_,
        row$pr_previous_pos,
        row$pr_previous_total,
        row$pr_previous_avg,
        row$pr_previous_final
      )
    )

    epvs <- vapply(pr_inputs, function(x) x$epv %||% NA_real_, numeric(1))
    used_index <- if (all(is.na(epvs))) {
      NA_integer_
    } else {
      max_epv <- max(epvs, na.rm = TRUE)
      tied <- which(!is.na(epvs) & epvs == max_epv)
      current_is_recent_robust <- identical(as.integer(pr_inputs[[2]]$year), current_season) &&
        identical(as.integer(pr_inputs[[1]]$year), current_season) &&
        !is.na(epvs[[1]]) &&
        !is.na(epvs[[2]]) &&
        isTRUE(all.equal(epvs[[1]], epvs[[2]]))

      if (current_is_recent_robust && 2L %in% tied) 2L else tied[[1]]
    }
    list(inputs = pr_inputs, used_index = used_index, estimate_note = estimate_note)
  }

  epv_math_item <- function(component, show_adjustment = FALSE) {
    player_parts <- trimws(strsplit(component$player %||% "", ",\\s*")[[1]])
    display_player <- if (length(player_parts) >= 2) {
      first_and_suffix <- trimws(strsplit(player_parts[[2]], "\\s+")[[1]])
      first_name <- first_and_suffix[[1]]
      suffix <- paste(first_and_suffix[-1], collapse = " ")
      trimws(paste(first_name, player_parts[[1]], suffix))
    } else {
      component$player
    }
    player_label <- paste0(rank_label(component$position, component$rank), ": ", display_player)
    if (!is.na(component$conference)) {
      player_label <- paste0(player_label, " (", component$conference, ")")
    }

    tags$span(
      class = "epv-math-item",
      tags$span(class = "epv-math-player", player_label),
      if (isTRUE(show_adjustment)) {
        tagList(
          tags$span(class = "epv-math-salary", money(component$adjusted_salary)),
          tags$span(class = "epv-math-adjustment", paste0("[", money(component$base_salary), " \u00d7 110%]"))
        )
      } else {
        tags$span(class = "epv-math-salary", money(component$adjusted_salary))
      }
    )
  }

  output$new_salary <- renderText(money(result()$new_salary))
  output$eys <- renderText(money(result()$extended_years_salary))
  output$final_years <- renderText(result()$final_years)
  output$current_contract_line <- renderUI({
    row <- selected_player()
    headshot_url <- row$player_headshot[[1]] %||% NA_character_
    team_logo_url <- row$team_logo_espn[[1]] %||% NA_character_
    team_color <- row$team_color[[1]] %||% "#1f2937"
    if (!has_url(team_color)) team_color <- "#1f2937"
    top_name <- player_display_name(row$player_name)
    team_pos <- trimws(paste(row$player_team %||% "", row$player_pos %||% ""))
    jersey <- row$player_jersey[[1]] %||% NA_character_
    age <- player_age(row$player_birth_date)
    bio_line <- paste0(
      "Jersey: ",
      if (has_url(jersey)) paste0("#", jersey) else "--",
      " | Age: ",
      if (is.na(age)) "--" else sprintf("%.1f", age),
      " | Drafted: ",
      draft_label(
        row$player_draft_year,
        row$player_draft_round,
        row$player_draft_round_pick,
        row$player_draft_pick,
        row$player_rookie_season
      )
    )
    fifth_year_salary <- fifth_year_display_salary(row)
    fifth_year_exercised <- has_exercised_fifth_year_option(row)
    fifth_year_available <- has_available_fifth_year_option(row)
    fifth_year_ineligible <- has_ineligible_fifth_year_option(row)
    fifth_year_simulated <- fifth_year_available && isTRUE(input$simulate_5yo)
    show_fifth_year_note <- (!is.na(fifth_year_salary) && (fifth_year_exercised || fifth_year_available)) || fifth_year_ineligible
    tsp_rank_text <- rank_label(row$fifth_year_tsp_pos, row$fifth_year_tsp_rank)

    tagList(
      tags$div(
        class = "current-contract-line",
        tags$span(
          class = "player-identity",
          tags$span(
            class = "player-avatar-wrap",
            if (has_url(headshot_url)) {
              tags$img(class = "player-headshot", src = headshot_url, alt = "")
            } else {
              tags$span(class = "player-headshot-fallback", player_initials(row$player_name))
            }
          ),
          tags$span(
            class = "player-name-stack",
            tags$span(
              class = "player-name-row",
              tags$span(
                class = "player-name",
                top_name,
                tags$span(class = "player-team-pos", style = paste0("color: ", team_color, ";"), paste0("  ", team_pos))
              ),
              if (has_url(team_logo_url)) {
                tags$img(class = "team-logo-badge", src = team_logo_url, alt = "")
              } else {
                tags$span(class = "team-logo-fallback", row$player_team %||% "FA")
              }
            ),
            tags$span(class = "player-bio-line", bio_line)
          )
        ),
        tags$span(
          class = "contract-field",
          tags$span(class = "contract-label", "Salary"),
          tags$span(class = "contract-value", money(row$prev_salary))
        ),
        tags$span(
          class = "contract-field",
          tags$span(class = "contract-label", "Years"),
          tags$span(class = "contract-value", row$prev_years)
        ),
        tags$span(
          class = "contract-field",
          tags$span(class = "contract-label", "Contract"),
          tags$span(class = "contract-value", row$contract)
        ),
        if (show_fifth_year_note) {
          note_label <- if (fifth_year_ineligible) {
            "Fifth Year Option Ineligible"
          } else if (fifth_year_exercised) {
            "5YO Exercised"
          } else {
            "Fifth Year Option Available"
          }
          detail_text <- if (fifth_year_ineligible) {
            row$fifth_year_option_ineligible_reason %||% "Not eligible for 5YO"
          } else if (!is.na(row$fifth_year_tag_level) && nzchar(row$fifth_year_tag_level %||% "")) {
            paste0(
              current_season + 1L,
              " 5YO Salary = ",
              money(fifth_year_salary),
              " (",
              row$fifth_year_tag_level,
              " Salary | ",
              current_season - 1L,
              " TSP Rank = ",
              tsp_rank_text,
              ")"
            )
          } else {
            paste0(current_season + 1L, " 5YO Salary = ", money(fifth_year_salary))
          }
          tags$span(
            class = "fifth-year-stack",
            tags$span(class = paste("fifth-year-note", if (fifth_year_ineligible) "ineligible" else ""), note_label),
            tags$span(class = paste("fifth-year-detail", if (fifth_year_ineligible) "ineligible" else ""), detail_text)
          )
        }
      )
    )
  })

  output$fifth_year_simulation_control <- renderUI({
    row <- selected_player()
    fifth_year_salary <- fifth_year_display_salary(row)
    if (
      is.na(fifth_year_salary) ||
        !has_available_fifth_year_option(row) ||
        has_exercised_fifth_year_option(row)
    ) {
      return(NULL)
    }

    tags$div(
      class = "fifth-year-sim fifth-year-sim-row",
      checkboxInput("simulate_5yo", "Simulate exercising player's 5YO", value = isTRUE(input$simulate_5yo))
    )
  })

  output$pr_summary_row <- renderUI({
    req(input$week)
    row <- selected_player()
    summary <- build_pr_summary(row, input$week)
    pr_inputs <- summary$inputs
    used_index <- summary$used_index
    estimate_note <- summary$estimate_note

    tags$div(
      class = "pr-summary-row",
      pr_summary_section(
        pr_inputs[[1]]$title,
        pr_inputs[[1]]$year,
        pr_inputs[[1]]$position,
        pr_inputs[[1]]$total_rank,
        pr_inputs[[1]]$avg_rank,
        pr_inputs[[1]]$final_rank,
        pr_inputs[[1]]$total_epv,
        pr_inputs[[1]]$avg_epv,
        pr_inputs[[1]]$epv,
        pr_inputs[[1]]$epv_note,
        NULL,
        identical(1L, used_index),
        pr_inputs[[1]]$year_badge,
        pr_inputs[[1]]$helper_text
      ),
      pr_summary_section(
        pr_inputs[[2]]$title,
        pr_inputs[[2]]$year,
        pr_inputs[[2]]$position,
        pr_inputs[[2]]$total_rank,
        pr_inputs[[2]]$avg_rank,
        pr_inputs[[2]]$final_rank,
        pr_inputs[[2]]$total_epv,
        pr_inputs[[2]]$avg_epv,
        pr_inputs[[2]]$epv,
        pr_inputs[[2]]$epv_note,
        NULL,
        identical(2L, used_index),
        pr_inputs[[2]]$year_badge,
        pr_inputs[[2]]$helper_text
      ),
      pr_summary_section(
        pr_inputs[[3]]$title,
        pr_inputs[[3]]$year,
        pr_inputs[[3]]$position,
        pr_inputs[[3]]$total_rank,
        pr_inputs[[3]]$avg_rank,
        pr_inputs[[3]]$final_rank,
        pr_inputs[[3]]$total_epv,
        pr_inputs[[3]]$avg_epv,
        pr_inputs[[3]]$epv,
        pr_inputs[[3]]$epv_note,
        NULL,
        identical(3L, used_index),
        pr_inputs[[3]]$year_badge,
        pr_inputs[[3]]$helper_text
      )
    )
  })

  output$epv_math_row <- renderUI({
    req(input$week)
    row <- selected_player()
    summary <- build_pr_summary(row, input$week)
    if (is.na(summary$used_index)) return(NULL)

    used <- summary$inputs[[summary$used_index]]
    math <- epv_salary_components(
      used$position,
      used$effective_final_rank,
      salary_curves,
      week = input$week,
      floor_to_starter = TRUE
    )
    if (is.null(math) || !nrow(math$components)) return(NULL)

    show_adjustment <- !is.na(math$source_multiplier) && !isTRUE(all.equal(math$source_multiplier, 1))
    components <- math$components
    result <- money(math$result)
    subtitle <- paste0(
      used$title,
      if (!is.na(used$year)) paste0(" ", used$year) else "",
      ": ",
      priced_rank_label(used$position, used$effective_final_rank)
    )

    formula <- if (identical(math$formula_type, "elite_extrapolation")) {
      tagList(
        tags$span(
          class = "epv-math-average",
          tags$span(class = "epv-math-op", "2 \u00d7 avg(ranks 1, 2) \u2212 avg(ranks 3, 4) ="),
          tags$span(class = "epv-math-result", result)
        )
      )
    } else {
      tagList(
        epv_math_item(components[2, ], show_adjustment),
        tags$span(
          class = "epv-math-average",
          tags$span(class = "epv-math-op", "Average ="),
          tags$span(class = "epv-math-result", result)
        )
      )
    }
    component_tags <- if (identical(math$formula_type, "elite_extrapolation")) {
      lapply(seq_len(nrow(components)), function(i) epv_math_item(components[i, ], show_adjustment))
    } else {
      list(epv_math_item(components[1, ], show_adjustment))
    }

    tags$div(
      class = "epv-math-row",
      tags$div(class = "epv-math-title", "EPV Breakdown"),
      tags$div(
        tags$div(class = "epv-math-subtitle", subtitle),
        if (isTRUE(math$estimated)) tags$div(class = "pr-summary-note estimate", math$label),
        tags$div(
          class = "epv-math-items",
          component_tags,
          formula
        )
      )
    )
  })

  output$pricing_bridge <- renderUI({
    req(input$week, input$ext_years)
    r <- result()
    row <- selected_player()
    curve_context <- salary_curve_context(input$week, salary_curves = salary_curves)
    current_years <- as.numeric(row$prev_years)
    ext_years <- as.numeric(input$ext_years)
    has_extension_years <- !is.na(ext_years) && ext_years > 0
    final_years <- as.numeric(r$final_years)
    base_rate_rank_label <- function(position, rank) {
      floor_rank <- starter_floor(position)
      if (is.na(position) || is.na(rank) || is.na(floor_rank)) return("--")
      rank_label(position, min(max(round_rank_half(rank), 1), floor_rank, na.rm = TRUE))
    }
    source_label <- function(year = NA, position = NA, rank = NA) {
      rank_text <- base_rate_rank_label(position, rank)
      if (is.na(year)) {
        paste0("Position Rank (", rank_text, ")")
      } else {
        paste0(year, " Position Rank (", rank_text, ")")
      }
    }
    current_pricing_pos <- row$pr_current_pos %||% row$player_pos
    current_pricing_rank <- row$pr_current_final %||% starter_floor(current_pricing_pos)

    source_values <- c(
      setNames(r$epv_current, source_label(current_season, current_pricing_pos, current_pricing_rank)),
      setNames(r$epv_recent, source_label(row$pr_recent_season_local %||% NA_real_, row$pr_recent_pos, row$pr_recent_final)),
      setNames(r$epv_previous, source_label(row$pr_previous_season_local %||% NA_real_, row$pr_previous_pos, row$pr_previous_final)),
      setNames(r$prior_salary_floor, "Floor: 75% of current salary")
    )
    selected_source <- names(source_values)[which.max(replace(source_values, is.na(source_values), -Inf))]
    years_adjustment <- if (has_extension_years) round((as.numeric(r$discount_multiplier) - 1) * 100) else NA_real_
    years_adjustment_label <- if (!has_extension_years) {
      "--"
    } else if (years_adjustment >= 0) {
      paste0("+", years_adjustment, "%")
    } else {
      paste0(years_adjustment, "%")
    }
    years_adjustment_class <- if (!has_extension_years) {
      ""
    } else if (years_adjustment < 0) {
      "discount-good"
    } else if (years_adjustment > 0) {
      "discount-bad"
    } else {
      ""
    }

    cap_note <- if (isTRUE(r$hit_year_cap)) {
      paste0("Capped at ", final_years, " total years")
    } else {
      paste0(final_years, " total years")
    }
    floor_note <- if (!has_extension_years) {
      "No extension years"
    } else if (isTRUE(r$hit_sd_minimum)) {
      "SD minimum applied"
    } else {
      ""
    }

    tags$div(
      class = "pricing-bridge",
      tags$div(
        class = "pricing-step",
        tags$span(class = "pricing-label", "Base Rate"),
        tags$span(class = "pricing-value", money(r$base_epv)),
        tags$span(class = "pricing-subtext", selected_source)
      ),
      tags$span(class = "pricing-operator", HTML("&times;")),
      tags$div(
        class = "pricing-step",
        tags$span(class = "pricing-label", "Years Adj."),
        tags$span(class = paste("pricing-value", years_adjustment_class), years_adjustment_label),
          tags$span(
            class = "pricing-subtext",
            if (has_extension_years) paste0(ext_years, " extension year", ifelse(ext_years == 1, "", "s")) else "No extension years"
          )
        ),
      tags$span(class = "pricing-operator", "="),
      tags$div(
        class = "pricing-step",
        tags$span(class = "pricing-label", "EYS"),
        tags$span(class = "pricing-value", if (has_extension_years) money(r$extended_years_salary) else "--"),
        tags$span(class = "pricing-subtext", floor_note)
      ),
      tags$span(class = "pricing-operator", HTML("&rarr;")),
      tags$div(
        class = "pricing-step",
        tags$span(class = "pricing-label", "New Sal"),
        tags$span(class = "pricing-value new-sal", money(r$new_salary)),
        tags$span(class = "pricing-subtext", "Starting EXT salary (after smoothing)")
      )
    )
  })

  output$smoothing_table <- renderUI({
    req(input$week, input$ext_years)
    row <- selected_player()
    tl <- salary_timeline(
      row,
      input$ext_years,
      salary_curves,
      week = input$week,
      fifth_year_option = selected_fifth_year_option()
    )
    starter_floors <- data.frame(
      position = position_order,
      rank = vapply(position_order, starter_floor, numeric(1)),
      stringsAsFactors = FALSE
    )
    starter_floors$salary <- mapply(
      performance_salary,
      starter_floors$position,
      starter_floors$rank,
      MoreArgs = list(salary_curves = salary_curves, week = input$week)
    )
    curve_context <- salary_curve_context(input$week, salary_curves = salary_curves)
    money_or_dash <- function(x) {
      if (is.na(x)) "--" else money(x)
    }
    bridge_label <- function(power) {
      if (is.na(power) || power == 0) {
        ""
      } else if (power == 1) {
        "(x 1.1 =)"
      } else {
        tagList("(x 1.1", tags$sup(power), " =)")
      }
    }
    smoothed_cell <- function(amount, factor) {
      if (is.na(amount)) return("--")
      tagList(
        money(amount),
        if (!is.na(factor) && nzchar(factor)) {
          tags$span(class = "smoothing-calc", paste0("(", factor, ") * ", money(tl$smoothed_salary[[1]])))
        }
      )
    }
    original_bridge_label <- function(power, factor) {
      if (!is.na(factor) && nzchar(factor)) {
        return(paste0("(", factor, ") * ", money(row$prev_salary)))
      }
      bridge_label(power)
    }
    total_rows <- which(tl$include_total %in% TRUE)

    tags$div(
      class = "smoothing-table-wrap",
      tags$div(
        class = "smoothing-table-main",
        tags$div(
          class = "smoothing-table-title",
          tags$span(class = "smoothing-table-title-main", "Smoothing Breakdown")
        ),
        tags$table(
          class = "smoothing-table",
          tags$thead(
            tags$tr(
              tags$th("Year"),
              tags$th(class = "type-spacer", ""),
              tags$th("Type"),
              tags$th(class = "type-spacer", ""),
              tags$th(tags$span("Unsmoothed"), tags$br(), tags$span(paste0(current_season, " $"))),
              tags$th(class = "bridge-cell", ""),
              tags$th(tags$span("Unsmoothed"), tags$br(), tags$span("Future/Actual $")),
              tags$th(class = "spacer-cell", ""),
              tags$th(tags$span("Smoothed"), tags$br(), tags$span("Future/Actual $"))
            )
          ),
          tags$tbody(
            tagList(
              lapply(seq_len(nrow(tl)), function(i) {
                tags$tr(
                  class = if (isTRUE(tl$include_total[[i]])) "" else "excluded-row",
                  tags$td(tl$year_label[[i]]),
                  tags$td(class = "type-spacer", ""),
                  tags$td(class = "year-type", tl$year_type[[i]]),
                  tags$td(class = "type-spacer", ""),
                  tags$td(
                    class = "number",
                    money_or_dash(tl$original_salary[[i]])
                  ),
                  tags$td(
                    class = "bridge-cell",
                    original_bridge_label(tl$bridge_power[[i]], tl$original_formula_factor[[i]])
                  ),
                  tags$td(class = "number", money_or_dash(tl$escalated_original[[i]])),
                  tags$td(class = "spacer-cell", ""),
                  tags$td(
                    class = "smoothed-number",
                    smoothed_cell(tl$escalated_smoothed[[i]], tl$smoothed_formula_factor[[i]])
                  )
                )
              }),
              tags$tr(
                class = "sum-row",
                tags$td(""),
                tags$td(class = "type-spacer", ""),
                tags$td(class = "sum-label", "TOTAL"),
                tags$td(class = "type-spacer", ""),
                tags$td(class = "number", ""),
                tags$td(class = "bridge-cell", ""),
                tags$td(class = "number sum-emphasis", money(sum(round_salary(tl$escalated_original[total_rows]), na.rm = TRUE))),
                tags$td(class = "spacer-cell", ""),
                tags$td(class = "smoothed-number sum-emphasis", money(sum(round_salary(tl$escalated_smoothed[total_rows]), na.rm = TRUE)))
              )
            )
          )
        )
      ),
      tags$div(
        class = "starter-floor-reference",
        tags$div(class = "starter-floor-title", "PR Starter Floors"),
        if (isTRUE(curve_context$estimated)) {
          tags$div(class = "starter-floor-note", curve_context$label)
        },
        tags$table(
          class = "starter-floor-table",
          tags$tbody(
            tags$tr(
              class = "starter-floor-min",
              tags$td(class = "starter-floor-position", "Min SD Sal"),
              tags$td(class = "starter-floor-rank", money(salary_dispute_minimum))
            ),
            lapply(seq_len(nrow(starter_floors)), function(i) {
              label <- paste0(starter_floors$position[[i]], starter_floors$rank[[i]])
              tags$tr(
                tags$td(class = "starter-floor-position", label),
                tags$td(class = "starter-floor-rank", money(starter_floors$salary[[i]]))
              )
            })
          )
        )
      )
    )
  })

  output$eligibility_badge <- renderUI({
    row <- selected_player()
    note <- row$eligibility_note %||% ""
    ineligible <- grepl("^Ineligible", note)
    ineligible_reasons <- strsplit(sub("^Ineligible:\\s*", "", note), ";\\s+(?=(2\\+ current contract years|rookie contract signed|no Robust PRs|Signed ))", perl = TRUE)[[1]]

    tags$div(
      class = "eligibility-wrap",
      tags$span(
        class = paste("eligibility-pill", if (ineligible) "ineligible" else "eligible"),
        tags$span(
          if (ineligible) {
            tagList(
              "Ineligible",
              tags$span(class = "eligibility-icon", HTML("&times;")),
              tags$span(
                class = "eligibility-subtext",
                lapply(ineligible_reasons, function(reason) {
                  tags$span(class = "eligibility-subtext-line", reason)
                })
              )
            )
          } else {
            tagList(
              "Eligible",
              tags$span(class = "eligibility-icon", HTML("&#10003;"))
            )
          }
        )
      ),
      tags$div(
        class = "robust-season-report",
        lapply(seq_len(nrow(robust_season_rows())), function(i) {
          season_row <- robust_season_rows()[i, ]
          if (is.na(season_row$gp)) {
            return(tags$div(
              class = "robust-season-row",
              tags$span(class = "robust-season-year", paste0(season_row$season, ":")),
              tags$span("--")
            ))
          }

          robust <- isTRUE(season_row$robust_pr)
          tags$div(
            class = "robust-season-row",
            tags$span(class = "robust-season-year", paste0(season_row$season, ":")),
            tags$span(class = "robust-season-gp", paste(season_row$gp, "games played")),
            tags$span(
              class = "robust-season-state",
              tags$span(
                class = paste("robust-season-status", if (robust) "robust" else "not-robust"),
                if (robust) "Robust" else "Not Robust"
              ),
              tags$span(
                class = paste("robust-season-icon", if (robust) "robust" else "not-robust"),
                HTML(if (robust) "&#10003;" else "&times;")
              )
            ),
            tags$span(
              class = paste("robust-season-ranks", if (robust) "robust" else "not-robust"),
              tags$span(class = "robust-season-rank", paste0("Tot: ", rank_label(season_row$pos, season_row$pr_total))),
              tags$span(class = "robust-season-rank", paste0("Avg: ", rank_label(season_row$pos, season_row$pr_avg)))
            )
          )
        })
      )
    )
  })

  output$timeline <- renderPlot({
    row <- selected_player()
    tl <- salary_timeline(
      row,
      input$ext_years,
      salary_curves,
      week = input$week,
      fifth_year_option = selected_fifth_year_option()
    )
    tl_long <- tl |>
      tidyr::pivot_longer(c(original_salary, smoothed_salary), names_to = "series", values_to = "salary") |>
      mutate(series = recode(series, original_salary = "before smoothing", smoothed_salary = "smoothed EXT"))

    ggplot(tl_long, aes(year, salary, color = series, group = series)) +
      geom_line(linewidth = 1.2) +
      geom_point(size = 3) +
      scale_y_continuous(labels = money) +
      scale_color_manual(values = c("before smoothing" = "#9b5de5", "smoothed EXT" = "#00a896")) +
      labs(x = "Contract year", y = "Base salary", color = NULL) +
      theme_minimal(base_size = 13) +
      theme(legend.position = "bottom", panel.grid.minor = element_blank())
  })

  output$math_table <- renderTable({
    r <- result()
    data.frame(
      Step = c("EPV current", "EPV recent robust", "EPV previous robust", "Prior salary floor", "Selected base EPV", "Years multiplier", "EYS after SD minimum", "Smoothed salary"),
      Value = c(
        money(r$epv_current), money(r$epv_recent), money(r$epv_previous), money(r$prior_salary_floor),
        money(r$base_epv), paste0(r$discount_multiplier, "x"), money(r$extended_years_salary), money(r$new_salary)
      ),
      check.names = FALSE
    )
  }, striped = TRUE, bordered = FALSE)

  output$pr_table <- renderTable({
    row <- selected_player()
    data.frame(
      Reading = c("Current non-robust", "Recent robust", "Previous robust"),
      Position = c(row$pr_current_pos, row$pr_recent_pos, row$pr_previous_pos),
      Total = c(row$pr_current_total, row$pr_recent_total, row$pr_previous_total),
      PPG = c(row$pr_current_avg, row$pr_recent_avg, row$pr_previous_avg),
      Final = c(row$pr_current_final, row$pr_recent_final, row$pr_previous_final),
      check.names = FALSE
    )
  }, striped = TRUE, bordered = FALSE)

  output$flags <- renderUI({
    r <- result()
    tags$ul(
      tags$li(if (r$hit_year_cap) "Year cap hit: requested years exceed the six-year maximum." else "Year cap clear."),
      tags$li(if (r$hit_sd_minimum) "SD minimum affected the result." else "SD minimum did not bind."),
      tags$li(selected_player()$eligibility_note)
    )
  })
}

shinyApp(ui, server)
