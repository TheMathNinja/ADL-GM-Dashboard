library(dplyr)
library(readr)
library(tibble)

source("R/roster_source.R")

`%||%` <- function(x, y) {
  if (is.null(x) || length(x) == 0 || (length(x) == 1 && is.na(x))) y else x
}

commissioner_alert_dir <- function() {
  Sys.getenv("ADL_ALERT_DIR", unset = file.path("data", "commissioner_alerts"))
}

commissioner_alert_path <- function(name, season = get_current_season(), week = NULL, ext = "csv") {
  dir.create(commissioner_alert_dir(), recursive = TRUE, showWarnings = FALSE)
  week_part <- if (is.null(week) || is.na(week)) "" else paste0("_week", sprintf("%02d", as.integer(week)))
  file.path(commissioner_alert_dir(), paste0(name, "_", season, week_part, ".", ext))
}

commissioner_alert_report_dir <- function() {
  Sys.getenv("ADL_ALERT_REPORT_DIR", unset = file.path("data", "commissioner_alert_reports"))
}

commissioner_alert_report_path <- function(season = get_current_season(), week = NULL, checked_date = Sys.Date()) {
  dir.create(commissioner_alert_report_dir(), recursive = TRUE, showWarnings = FALSE)
  week_part <- if (is.null(week) || is.na(week)) "" else paste0("_week", sprintf("%02d", as.integer(week)))
  file.path(
    commissioner_alert_report_dir(),
    paste0("commissioner_alert_report_", checked_date, "_", season, week_part, ".csv")
  )
}

commissioner_salary_cap <- function(season = get_current_season()) {
  env_value <- suppressWarnings(as.numeric(Sys.getenv(paste0("ADL_SALARY_CAP_", season), unset = NA_character_)))
  if (!is.na(env_value)) return(env_value)

  caps <- c(
    `2025` = 226.20,
    `2026` = 244.00
  )
  value <- caps[[as.character(season)]]
  if (is.null(value) || is.na(value)) {
    stop("Missing ADL salary cap for ", season, ". Set ADL_SALARY_CAP_", season, ".", call. = FALSE)
  }
  value
}

fetch_mfl_salary_cap_adjustments <- function(season = get_current_season()) {
  conn <- connect_adl_mfl(season)
  franchise_tbl <- tibble::as_tibble(ffscrapr::ff_franchises(conn))
  franchises <- franchise_tbl |>
    transmute(
      franchise_id = as.character(.data$franchise_id),
      franchise_name = as.character(coalesce_col(franchise_tbl, c("franchise_name", "name"))),
      franchise = as.character(coalesce_col(franchise_tbl, c("franchise", "franchise_abbrev", "abbrev"), NA_character_))
    )

  raw <- ffscrapr::mfl_getendpoint(conn, "salaryAdjustments")[["content"]][["salaryAdjustments"]][["salaryAdjustment"]]
  if (is.null(raw) || length(raw) == 0) {
    return(franchises |> mutate(salary_cap_adjustments = 0, adjustment_count = 0L))
  }

  adjustments <- bind_rows(lapply(raw, tibble::as_tibble)) |>
    transmute(
      franchise_id = as.character(.data$franchise_id),
      amount = suppressWarnings(as.numeric(.data$amount))
    ) |>
    group_by(.data$franchise_id) |>
    summarize(
      salary_cap_adjustments = round(sum(.data$amount, na.rm = TRUE), 2),
      adjustment_count = n(),
      .groups = "drop"
    )

  franchises |>
    left_join(adjustments, by = "franchise_id") |>
    mutate(
      salary_cap_adjustments = coalesce(.data$salary_cap_adjustments, 0),
      adjustment_count = coalesce(.data$adjustment_count, 0L)
    )
}

normalize_alert_status <- function(x) {
  x <- toupper(trimws(as.character(x %||% "")))
  dplyr::case_when(
    x %in% c("ROSTER", "ACTIVE", "ACTIVE_ROSTER") ~ "Active",
    x %in% c("TAXI", "TAXI_SQUAD") ~ "Taxi",
    TRUE ~ trimws(as.character(x))
  )
}

active_roster_rows <- function(rosters) {
  rosters |>
    mutate(roster_status = normalize_alert_status(.data$roster_status)) |>
    filter(.data$roster_status == "Active")
}

taxi_roster_rows <- function(rosters) {
  rosters |>
    mutate(roster_status = normalize_alert_status(.data$roster_status)) |>
    filter(.data$roster_status == "Taxi")
}

evaluate_roster_cap_alerts <- function(rosters, min_active = 40L, max_active_taxi = 75L) {
  roster_counts <- rosters |>
    mutate(roster_status = normalize_alert_status(.data$roster_status)) |>
    group_by(.data$conference, .data$franchise, .data$franchise_name) |>
    summarize(
      active_players = sum(.data$roster_status == "Active", na.rm = TRUE),
      taxi_players = sum(.data$roster_status == "Taxi", na.rm = TRUE),
      active_plus_taxi = sum(.data$roster_status %in% c("Active", "Taxi"), na.rm = TRUE),
      .groups = "drop"
    )

  bind_rows(
    roster_counts |>
      filter(.data$active_players < .env$min_active) |>
      transmute(
        alert_type = "Roster Cap Violation",
        severity = "violation",
        conference,
        franchise,
        franchise_name,
        rule = paste0("At least ", .env$min_active, " players on Active Roster"),
        observed = paste0(.data$active_players, " active players"),
        details = paste0(.env$min_active - .data$active_players, " below minimum")
      ),
    roster_counts |>
      filter(.data$active_plus_taxi > .env$max_active_taxi) |>
      transmute(
        alert_type = "Roster Cap Violation",
        severity = "violation",
        conference,
        franchise,
        franchise_name,
        rule = paste0("Maximum ", .env$max_active_taxi, " players on Active Roster + Taxi Squad"),
        observed = paste0(.data$active_plus_taxi, " active/taxi players"),
        details = paste0(.data$active_plus_taxi - .env$max_active_taxi, " above maximum")
      )
  )
}

format_signed_millions <- function(x) {
  paste0(ifelse(x >= 0, "+$", "-$"), sprintf("%.2f", abs(x)), "m")
}

evaluate_salary_cap_alerts <- function(
  rosters,
  season = get_current_season(),
  top_n = 43L,
  cap = commissioner_salary_cap(season),
  salary_cap_adjustments = NULL
) {
  roster_tbl <- active_roster_rows(rosters)
  if (!"franchise_salary_cap" %in% names(roster_tbl)) {
    roster_tbl$franchise_salary_cap <- NA_real_
  }

  salary_summary <- roster_tbl |>
    mutate(prev_salary = suppressWarnings(as.numeric(.data$prev_salary))) |>
    filter(!is.na(.data$prev_salary)) |>
    group_by(.data$conference, .data$franchise, .data$franchise_name) |>
    arrange(desc(.data$prev_salary), .data$player_name, .by_group = TRUE) |>
    slice_head(n = top_n) |>
    summarize(
      top_salary_count = n(),
      top_salary_total = round(sum(.data$prev_salary, na.rm = TRUE), 2),
      franchise_salary_cap = coalesce(
        suppressWarnings(max(as.numeric(.data$franchise_salary_cap), na.rm = TRUE)),
        .env$cap
      ),
      top_salary_players = paste(head(paste0(.data$player_name, " $", sprintf("%.2f", .data$prev_salary), "m"), 8), collapse = "; "),
      .groups = "drop"
    )

  if (!is.null(salary_cap_adjustments)) {
    adjustment_tbl <- tibble::as_tibble(salary_cap_adjustments) |>
      transmute(
        franchise = as.character(.data$franchise),
        salary_cap_adjustments = suppressWarnings(as.numeric(.data$salary_cap_adjustments))
      )

    salary_summary <- salary_summary |>
      left_join(adjustment_tbl, by = "franchise")
  } else {
    salary_summary$salary_cap_adjustments <- 0
  }

  salary_summary |>
    mutate(
      franchise_salary_cap = if_else(is.infinite(.data$franchise_salary_cap), .env$cap, .data$franchise_salary_cap),
      salary_cap_adjustments = coalesce(.data$salary_cap_adjustments, 0),
      final_expenditure = round(.data$top_salary_total + .data$salary_cap_adjustments, 2),
      overage = round(.data$final_expenditure - .data$franchise_salary_cap, 2)
    ) |>
    filter(.data$overage > 0) |>
    transmute(
      alert_type = "Salary Cap Violation",
      severity = "violation",
      conference,
      franchise,
      franchise_name,
      rule = paste0("Top ", .env$top_n, " Active Roster salaries plus cap adjustments at or below franchise cap of $", sprintf("%.2f", .data$franchise_salary_cap), "m"),
      observed = paste0("$", sprintf("%.2f", .data$final_expenditure), "m"),
      details = paste0(
        "$", sprintf("%.2f", .data$overage), "m over; top ", .env$top_n, " salaries $",
        sprintf("%.2f", .data$top_salary_total), "m; cap adjustments ",
        format_signed_millions(.data$salary_cap_adjustments), "; leaders: ", .data$top_salary_players
      )
    )
}

normalize_lineups <- function(starters, franchises = NULL) {
  starters_tbl <- tibble::as_tibble(starters)
  if (!nrow(starters_tbl)) {
    return(tibble(
      franchise_id = character(), franchise = character(), franchise_name = character(),
      player_id = character(), player_name = character(), player_team = character(),
      player_pos = character(), lineup_slot = character()
    ))
  }

  lineups <- starters_tbl |>
    transmute(
      franchise_id = as.character(coalesce_col(starters_tbl, c("franchise_id", "franchiseId"))),
      player_id = as.character(coalesce_col(starters_tbl, c("player_id", "playerId", "id"))),
      player_name = as.character(coalesce_col(starters_tbl, c("player_name", "player", "name"))),
      player_team = as.character(coalesce_col(starters_tbl, c("team", "player_team"))),
      player_pos = as.character(coalesce_col(starters_tbl, c("pos", "position", "player_pos"))),
      lineup_slot = as.character(coalesce_col(starters_tbl, c("lineup_slot", "slot", "starter_position", "starter_position")))
    )

  if (!is.null(franchises)) {
    franchise_tbl <- tibble::as_tibble(franchises)
    fr <- franchise_tbl |>
      transmute(
        franchise_id = as.character(.data$franchise_id),
        franchise_name = as.character(coalesce_col(franchise_tbl, c("franchise_name", "name"))),
        franchise = as.character(coalesce_col(franchise_tbl, c("franchise", "franchise_abbrev", "abbrev"), NA_character_))
      )
  } else {
    fr <- tibble(franchise_id = character(), franchise_name = character(), franchise = character())
  }

  lineups |>
    left_join(fr, by = "franchise_id") |>
    mutate(
      franchise = coalesce(.data$franchise, franchise_code_from_name(.data$franchise_name)),
      conference = case_when(
        suppressWarnings(as.integer(.data$franchise_id)) <= 16L ~ "NFC",
        suppressWarnings(as.integer(.data$franchise_id)) >= 17L ~ "AFC",
        TRUE ~ NA_character_
      )
    ) |>
    select(conference, franchise, franchise_name, franchise_id, player_id, player_name, player_team, player_pos, lineup_slot)
}

fetch_live_lineups <- function(season = get_current_season(), week) {
  conn <- connect_adl_mfl(season)
  starters <- ffscrapr::ff_starters(conn, season = season, week = week)
  franchises <- ffscrapr::ff_franchises(conn)
  normalize_lineups(starters, franchises)
}

cache_lineups_snapshot <- function(season = get_current_season(), week, force_live = TRUE) {
  lineups <- if (force_live) {
    fetch_live_lineups(season = season, week = week)
  } else {
    path <- commissioner_alert_path("lineups_snapshot", season, week)
    if (!file.exists(path)) stop("Missing lineup snapshot: ", path)
    read_csv(path, show_col_types = FALSE)
  }

  write_csv(lineups, commissioner_alert_path("lineups_snapshot", season, week), na = "")
  lineups
}

cache_designation_snapshot <- function(season = get_current_season(), week = NULL, force_live = TRUE) {
  rosters <- load_current_rosters(
    force_live = force_live,
    source = if (force_live) "live" else "auto",
    season = season,
    week = week,
    cache_path = commissioner_alert_path("designation_rosters_cache", season, week)
  )

  snapshot <- rosters |>
    transmute(
      captured_at = format(Sys.time(), "%Y-%m-%d %H:%M:%S %Z"),
      season = .env$season,
      week = .env$week %||% NA_integer_,
      conference,
      franchise,
      franchise_name,
      player_id,
      player_name,
      player_team,
      player_pos,
      roster_status = normalize_alert_status(.data$roster_status)
    )

  write_csv(snapshot, commissioner_alert_path("designation_snapshot", season, week), na = "")
  snapshot
}

read_designation_snapshot <- function(season = get_current_season(), week = NULL) {
  path <- commissioner_alert_path("designation_snapshot", season, week)
  if (!file.exists(path)) return(NULL)
  read_csv(path, show_col_types = FALSE)
}

inactive_designation <- function(x) {
  x <- toupper(trimws(as.character(x %||% "")))
  grepl("\\(I\\)|\\(S\\)|(^|[^A-Z])I([^A-Z]|$)", x)
}

read_bye_weeks <- function(season = get_current_season()) {
  path <- Sys.getenv("ADL_BYE_WEEKS_CSV", unset = file.path("data", paste0("nfl_bye_weeks_", season, ".csv")))
  if (file.exists(path)) {
    byes <- read_csv(path, show_col_types = FALSE)
    return(setNames(as.integer(byes$week), as.character(byes$team)))
  }

  if (season == 2026L) {
    return(c(
      CAR = 5, KCC = 5,
      CIN = 6, DET = 6, MIA = 6, MIN = 6,
      BUF = 7, JAC = 7, LAC = 7, WAS = 7,
      HOU = 8, NOS = 8, NYG = 8, SFO = 8,
      PIT = 9, TEN = 9,
      CHI = 10, DEN = 10, PHI = 10, TBB = 10,
      ATL = 11, CLE = 11, GBP = 11, LAR = 11, NEP = 11, SEA = 11,
      BAL = 13, IND = 13, LVR = 13, NYJ = 13,
      ARI = 14, DAL = 14
    ))
  }

  integer()
}

evaluate_illegal_lineup_alerts <- function(lineups, rosters, season = get_current_season(), week, expected_starters = 21L, designation_snapshot = NULL) {
  franchise_index <- rosters |>
    distinct(.data$conference, .data$franchise, .data$franchise_name, .data$franchise_id)

  lineup_counts <- franchise_index |>
    left_join(
      lineups |> count(.data$franchise_id, name = "starter_count"),
      by = "franchise_id"
    ) |>
    mutate(starter_count = coalesce(.data$starter_count, 0L))

  count_alerts <- lineup_counts |>
    filter(.data$starter_count != .env$expected_starters) |>
    transmute(
      alert_type = "Illegal Lineup",
      severity = "violation",
      conference,
      franchise,
      franchise_name,
      rule = paste0("Exactly ", .env$expected_starters, " starters submitted"),
      observed = paste0(.data$starter_count, " starters"),
      details = if_else(.data$starter_count < .env$expected_starters, "below required starter count", "above required starter count")
    )

  status_source <- rosters |>
    transmute(
      player_id,
      current_roster_status = normalize_alert_status(.data$roster_status)
    )

  if (!is.null(designation_snapshot)) {
    status_source <- designation_snapshot |>
      transmute(
        player_id,
        designation_72h = normalize_alert_status(.data$roster_status)
      ) |>
      right_join(status_source, by = "player_id")
  } else {
    status_source <- status_source |>
      mutate(designation_72h = NA_character_)
  }

  player_checks <- lineups |>
    left_join(status_source, by = "player_id") |>
    mutate(
      status_for_rule = coalesce(.data$designation_72h, .data$current_roster_status),
      missing_72h_snapshot = is.na(.data$designation_72h),
      bye_week = unname(read_bye_weeks(season)[.data$player_team]),
      on_bye = !is.na(.data$bye_week) & .data$bye_week == .env$week,
      bad_designation = inactive_designation(.data$status_for_rule)
    )

  designation_alerts <- player_checks |>
    filter(.data$bad_designation) |>
    transmute(
      alert_type = "Illegal Lineup",
      severity = "violation",
      conference,
      franchise,
      franchise_name,
      rule = "No starters with (I), (S), or I designation 72 hours before kickoff",
      observed = paste0(.data$player_name, " ", .data$player_team, " ", .data$player_pos),
      details = if_else(
        .data$missing_72h_snapshot,
        paste0("designation evidence missing; current status is ", .data$current_roster_status),
        paste0("72-hour designation was ", .data$designation_72h)
      )
    )

  bye_alerts <- player_checks |>
    filter(.data$on_bye) |>
    transmute(
      alert_type = "Illegal Lineup",
      severity = "violation",
      conference,
      franchise,
      franchise_name,
      rule = "No starters on bye",
      observed = paste0(.data$player_name, " ", .data$player_team, " ", .data$player_pos),
      details = paste0(.data$player_team, " bye in Week ", .env$week)
    )

  bind_rows(count_alerts, designation_alerts, bye_alerts)
}

build_commissioner_alerts <- function(
  season = get_current_season(),
  week = NULL,
  include_offseason = TRUE,
  include_inseason = !is.null(week),
  force_live = FALSE
) {
  rosters <- load_current_rosters(force_live = force_live, source = "auto", season = season, week = week)
  alerts <- list()

  if (include_offseason) {
    alerts$roster_cap <- evaluate_roster_cap_alerts(rosters)
    salary_cap_adjustments <- if (isTRUE(force_live)) {
      tryCatch(fetch_mfl_salary_cap_adjustments(season = season), error = function(e) {
        warning("MFL salary cap adjustments unavailable; using zero adjustments: ", conditionMessage(e), call. = FALSE)
        NULL
      })
    } else {
      NULL
    }
    alerts$salary_cap <- evaluate_salary_cap_alerts(rosters, season = season, salary_cap_adjustments = salary_cap_adjustments)
  }

  if (include_inseason) {
    if (is.null(week) || is.na(week)) stop("week is required for in-season lineup alerts.", call. = FALSE)
    lineups <- cache_lineups_snapshot(season = season, week = week, force_live = force_live)
    alerts$illegal_lineup <- evaluate_illegal_lineup_alerts(
      lineups = lineups,
      rosters = rosters,
      season = season,
      week = week,
      designation_snapshot = read_designation_snapshot(season, week)
    )
  }

  result <- bind_rows(alerts) |>
    mutate(
      season = .env$season,
      week = .env$week %||% NA_integer_,
      checked_at = format(Sys.time(), "%Y-%m-%d %H:%M:%S %Z"),
      .before = 1
    ) |>
    arrange(.data$alert_type, .data$conference, .data$franchise, .data$rule)

  write_csv(result, commissioner_alert_path("alerts", season, week), na = "")
  write_csv(result, commissioner_alert_report_path(season, week), na = "")
  result
}

read_commissioner_alert_reports <- function(max_reports = 10L) {
  report_files <- list.files(
    commissioner_alert_report_dir(),
    pattern = "^commissioner_alert_report_.*[.]csv$",
    full.names = TRUE
  )

  legacy_files <- if (length(report_files)) {
    character()
  } else {
    list.files(
      commissioner_alert_dir(),
      pattern = "^alerts_.*[.]csv$",
      full.names = TRUE
    )
  }

  files <- unique(c(report_files, legacy_files))
  if (!length(files)) return(tibble())

  files <- files[order(file.info(files)$mtime, decreasing = TRUE)]
  files <- head(files, max_reports)

  bind_rows(lapply(files, function(path) {
    report <- tryCatch(read_csv(path, show_col_types = FALSE), error = function(e) tibble())
    if (!nrow(report)) return(tibble())
    report |>
      mutate(
        report_file = basename(path),
        report_mtime = format(file.info(path)$mtime, "%Y-%m-%d %H:%M:%S %Z"),
        .before = 1
      )
  }))
}

render_commissioner_alert_email <- function(alerts, season = get_current_season(), week = NULL) {
  title <- paste0("ADL Commissioner Alerts - ", season, if (!is.null(week) && !is.na(week)) paste0(" Week ", week) else "")

  if (!nrow(alerts)) {
    return(paste(c(title, "", "No commissioner alert violations were found."), collapse = "\n"))
  }

  groups <- split(alerts, alerts$alert_type)
  lines <- c(title, "", paste0(nrow(alerts), " violation(s) found."), "")
  for (alert_type in names(groups)) {
    rows <- groups[[alert_type]]
    lines <- c(lines, alert_type, strrep("-", nchar(alert_type)))
    for (i in seq_len(nrow(rows))) {
      row <- rows[i, ]
      lines <- c(
        lines,
        paste0(row$conference, " ", row$franchise, ": ", row$rule),
        paste0("Observed: ", row$observed),
        paste0("Details: ", row$details),
        ""
      )
    }
  }

  paste(lines, collapse = "\n")
}

render_commissioner_gm_alert_email <- function(alerts, season = get_current_season(), week = NULL) {
  if (!nrow(alerts)) return("")

  franchise_label <- paste(unique(paste(alerts$conference, alerts$franchise)), collapse = ", ")
  title <- paste0("ADL Commissioner Alert - ", franchise_label, " - ", season, if (!is.null(week) && !is.na(week)) paste0(" Week ", week) else "")

  lines <- c(
    title,
    "",
    "This is a private commissioner alert for your franchise.",
    "",
    paste0(nrow(alerts), " violation(s) found."),
    ""
  )

  for (i in seq_len(nrow(alerts))) {
    row <- alerts[i, ]
    lines <- c(
      lines,
      paste0(row$alert_type, ": ", row$rule),
      paste0("Observed: ", row$observed),
      paste0("Details: ", row$details),
      ""
    )
  }

  paste(lines, collapse = "\n")
}

safe_file_slug <- function(x) {
  x <- tolower(gsub("[^A-Za-z0-9]+", "_", x))
  gsub("^_+|_+$", "", x)
}

write_commissioner_alert_outbox <- function(body, season = get_current_season(), week = NULL, name = "email_outbox") {
  path <- commissioner_alert_path(name, season, week, ext = "txt")
  writeLines(body, path)
  path
}

write_commissioner_alert_recipients <- function(recipients, season = get_current_season(), week = NULL) {
  path <- commissioner_alert_path("email_recipients", season, week)
  write_csv(recipients, path, na = "")
  path
}

split_env_list <- function(value) {
  values <- trimws(strsplit(value %||% "", "[,;]")[[1]])
  unique(values[nzchar(values)])
}

commissioner_alert_default_digest_franchises <- function() {
  configured <- Sys.getenv("ADL_ALERT_DIGEST_FRANCHISES", unset = Sys.getenv("ADL_ALERT_RECIPIENT_FRANCHISES", unset = ""))
  if (nzchar(configured)) {
    return(split_env_list(configured))
  }
  c("CHI", "KCC", "IND", "SEA")
}

extract_email_addresses <- function(x) {
  x <- paste(as.character(x), collapse = " ")
  matches <- gregexpr("[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,}", x, ignore.case = TRUE, perl = TRUE)
  found <- regmatches(x, matches)[[1]]
  unique(tolower(found[found != "-1"]))
}

normalize_mfl_franchise_email_rows <- function(franchise_tbl, franchises = NULL) {
  franchise_tbl <- tibble::as_tibble(franchise_tbl)
  if (!nrow(franchise_tbl)) {
    return(tibble(franchise = character(), franchise_name = character(), email = character(), source = character()))
  }

  franchise_tbl <- franchise_tbl |>
    mutate(
      franchise_id = as.character(coalesce_col(franchise_tbl, c("franchise_id", "franchiseId", "id"))),
      franchise_name = as.character(coalesce_col(franchise_tbl, c("franchise_name", "name"))),
      franchise = coalesce(
        as.character(coalesce_col(franchise_tbl, c("franchise", "franchise_abbrev", "abbrev", "franchise_code", "code"), NA_character_)),
        franchise_code_from_name(.data$franchise_name)
      )
    )

  if (!is.null(franchises)) {
    franchise_tbl <- franchise_tbl |>
      filter(toupper(.data$franchise) %in% toupper(.env$franchises))
  }

  if (!nrow(franchise_tbl)) {
    return(tibble(franchise = character(), franchise_name = character(), email = character(), source = character()))
  }

  bind_rows(lapply(seq_len(nrow(franchise_tbl)), function(i) {
    row <- franchise_tbl[i, , drop = FALSE]
    emails <- extract_email_addresses(row)
    if (!length(emails)) {
      return(tibble(franchise = character(), franchise_name = character(), email = character(), source = character()))
    }
    tibble(
      franchise = row$franchise[[1]],
      franchise_name = row$franchise_name[[1]],
      email = emails,
      source = "ffscrapr::ff_franchises()"
    )
  })) |>
    distinct(.data$email, .keep_all = TRUE)
}

fetch_mfl_franchise_recipients <- function(
  season = get_current_season(),
  franchises = NULL
) {
  if (!requireNamespace("ffscrapr", quietly = TRUE)) {
    stop("Package ffscrapr is required to fetch MFL alert recipients.", call. = FALSE)
  }

  conn <- connect_adl_mfl(season)
  franchise_tbl <- tibble::as_tibble(ffscrapr::ff_franchises(conn))
  normalize_mfl_franchise_email_rows(franchise_tbl, franchises = franchises)
}

fetch_mfl_commissioner_alert_recipients <- function(
  season = get_current_season(),
  franchises = commissioner_alert_default_digest_franchises()
) {
  fetch_mfl_franchise_recipients(season = season, franchises = franchises)
}

resolve_commissioner_alert_recipients <- function(season = get_current_season()) {
  mfl_recipients <- tryCatch(
    fetch_mfl_commissioner_alert_recipients(season = season),
    error = function(e) {
      attr(e, "recipient_lookup_failed") <- TRUE
      e
    }
  )

  if (!inherits(mfl_recipients, "error") && nrow(mfl_recipients)) {
    return(mfl_recipients)
  }

  fallback <- split_env_list(Sys.getenv("ADL_ALERT_EMAIL_TO", unset = ""))
  if (!length(fallback)) {
    return(tibble(franchise = NA_character_, franchise_name = NA_character_, email = character(), source = "none"))
  }

  tibble(
    franchise = NA_character_,
    franchise_name = NA_character_,
    email = fallback,
    source = if (inherits(mfl_recipients, "error")) {
      paste0("ADL_ALERT_EMAIL_TO fallback after MFL lookup failed: ", conditionMessage(mfl_recipients))
    } else {
      "ADL_ALERT_EMAIL_TO fallback"
    }
  )
}

conference_cc_email <- function(conference) {
  conference <- toupper(trimws(as.character(conference %||% "")))
  if (identical(conference, "NFC")) {
    configured <- Sys.getenv("ADL_ALERT_NFC_CC", unset = "")
    return(if (nzchar(configured)) configured else "wittecarson@gmail.com")
  }
  if (identical(conference, "AFC")) {
    configured <- Sys.getenv("ADL_ALERT_AFC_CC", unset = "")
    return(if (nzchar(configured)) configured else "andrewrmast@gmail.com")
  }
  ""
}

send_alert_mail <- function(subject, body, to, cc = character()) {
  to <- unique(trimws(to[nzchar(trimws(to))]))
  cc <- unique(trimws(cc[nzchar(trimws(cc))]))
  from <- Sys.getenv("ADL_ALERT_EMAIL_FROM", unset = "")
  smtp_server <- Sys.getenv("ADL_SMTP_SERVER", unset = "")

  if (!length(to) || !nzchar(from) || !nzchar(smtp_server)) {
    return(list(sent = FALSE, reason = "email_not_configured"))
  }
  if (!requireNamespace("curl", quietly = TRUE)) {
    return(list(sent = FALSE, reason = "curl_package_not_installed"))
  }

  message <- paste0(
    "From: ", from, "\r\n",
    "To: ", paste(to, collapse = ", "), "\r\n",
    if (length(cc)) paste0("Cc: ", paste(cc, collapse = ", "), "\r\n") else "",
    "Subject: ", subject, "\r\n",
    "Content-Type: text/plain; charset=UTF-8\r\n\r\n",
    body
  )

  curl::send_mail(
    mail_from = from,
    mail_rcpt = unique(c(to, cc)),
    smtp_server = smtp_server,
    message = charToRaw(message),
    username = Sys.getenv("ADL_SMTP_USERNAME", unset = ""),
    password = Sys.getenv("ADL_SMTP_PASSWORD", unset = ""),
    use_ssl = Sys.getenv("ADL_SMTP_SSL", unset = "try")
  )

  list(sent = TRUE, reason = "sent")
}

send_commissioner_alert_email <- function(alerts, season = get_current_season(), week = NULL, send_empty = FALSE) {
  body <- render_commissioner_alert_email(alerts, season = season, week = week)
  outbox_path <- write_commissioner_alert_outbox(body, season = season, week = week, name = "email_outbox_digest")

  if (!nrow(alerts) && !send_empty) {
    return(tibble(sent = FALSE, reason = "no_alerts", outbox_path = outbox_path))
  }

  recipients <- resolve_commissioner_alert_recipients(season = season)
  recipients_path <- write_commissioner_alert_recipients(recipients, season = season, week = week)

  subject <- paste0("ADL Commissioner Alerts - ", season, if (!is.null(week) && !is.na(week)) paste0(" Week ", week) else "")
  digest_status <- send_alert_mail(subject = subject, body = body, to = recipients$email)
  if (!isTRUE(digest_status$sent)) {
    return(tibble(sent = FALSE, reason = digest_status$reason, outbox_path = outbox_path, recipients_path = recipients_path, recipients = paste(recipients$email, collapse = ", ")))
  }

  offender_franchises <- unique(alerts$franchise)
  offender_recipients <- tryCatch(
    fetch_mfl_franchise_recipients(season = season, franchises = offender_franchises),
    error = function(e) e
  )
  if (inherits(offender_recipients, "error")) {
    return(tibble(sent = FALSE, reason = paste0("offender_recipient_lookup_failed: ", conditionMessage(offender_recipients)), outbox_path = outbox_path, recipients_path = recipients_path, recipients = paste(recipients$email, collapse = ", ")))
  }

  offender_recipient_path <- commissioner_alert_path("email_recipients_offenders", season, week)
  write_csv(offender_recipients, offender_recipient_path, na = "")

  gm_status <- bind_rows(lapply(offender_franchises, function(franchise) {
    franchise_alerts <- alerts |> filter(.data$franchise == .env$franchise)
    franchise_recipients <- offender_recipients |> filter(toupper(.data$franchise) == toupper(.env$franchise))
    gm_to <- franchise_recipients$email
    gm_cc <- conference_cc_email(franchise_alerts$conference[[1]])
    gm_body <- render_commissioner_gm_alert_email(franchise_alerts, season = season, week = week)
    gm_outbox <- write_commissioner_alert_outbox(
      gm_body,
      season = season,
      week = week,
      name = paste0("email_outbox_gm_", safe_file_slug(franchise))
    )

    if (!length(gm_to)) {
      return(tibble(franchise = franchise, sent = FALSE, reason = "offender_email_not_found", outbox_path = gm_outbox, recipients = "", cc = gm_cc))
    }

    gm_subject <- paste0("ADL Commissioner Alert - ", franchise, " - ", season, if (!is.null(week) && !is.na(week)) paste0(" Week ", week) else "")
    status <- send_alert_mail(subject = gm_subject, body = gm_body, to = gm_to, cc = gm_cc)

    tibble(
      franchise = franchise,
      sent = isTRUE(status$sent),
      reason = status$reason,
      outbox_path = gm_outbox,
      recipients = paste(gm_to, collapse = ", "),
      cc = gm_cc
    )
  }))

  gm_status_path <- commissioner_alert_path("email_gm_status", season, week)
  write_csv(gm_status, gm_status_path, na = "")

  if (any(!gm_status$sent)) {
    return(tibble(
      sent = FALSE,
      reason = paste0("gm_email_failed: ", paste(unique(gm_status$reason[!gm_status$sent]), collapse = ", ")),
      outbox_path = outbox_path,
      recipients_path = recipients_path,
      offender_recipients_path = offender_recipient_path,
      gm_status_path = gm_status_path,
      recipients = paste(recipients$email, collapse = ", ")
    ))
  }

  tibble(
    sent = TRUE,
    reason = "sent",
    outbox_path = outbox_path,
    recipients_path = recipients_path,
    offender_recipients_path = offender_recipient_path,
    gm_status_path = gm_status_path,
    recipients = paste(recipients$email, collapse = ", "),
    gm_emails_sent = nrow(gm_status)
  )
}
