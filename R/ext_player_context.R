# Shared by the EXT explorer and Salary Cap Manager. No pricing/eligibility fork.
ext_player_context <- function(row, snapshots, roster_history, history, selected_week,
                               current_season, historical=TRUE) {

    row$historical_roster_found <- TRUE
    if (historical && nrow(roster_history) && selected_week > 0L) {
      historical_roster <- roster_history |>
        filter(
          .data$season == current_season,
          .data$week == .env$selected_week,
          .data$conference == row$conference[[1]],
          .data$player_id == as.character(row$player_id[[1]])
        ) |>
        slice(1)
      if (nrow(historical_roster)) {
        historical_fields <- intersect(
          c(
            "franchise", "franchise_name", "player", "player_name", "player_team", "player_pos",
            "roster_status", "prev_salary", "prev_years", "contract", "roster_last"
          ),
          names(historical_roster)
        )
        for (field in historical_fields) row[[field]] <- historical_roster[[field]][[1]]
      } else if (selected_week <= max(roster_history$week, na.rm = TRUE)) {
        row$historical_roster_found <- FALSE
      }
    }

    row$pr_current_pos <- row$player_pos
    row$pr_current_total <- NA_real_
    row$pr_current_avg <- NA_real_
    row$pr_current_final <- NA_real_
    row$pr_current_gp <- 0L
    row$pr_current_robust <- FALSE
    row$pr_snapshot_week <- 0L

    if (nrow(snapshots) && selected_week > 0L) {
      available_weeks <- snapshots |>
        filter(.data$season == current_season) |>
        pull(snapshot_week)
      latest_available <- if (length(available_weeks)) max(available_weeks, na.rm = TRUE) else 0L
      snapshot_week <- min(selected_week, latest_available)
      current_snapshot <- snapshots |>
        filter(
          .data$season == current_season,
          .data$snapshot_week == .env$snapshot_week,
          .data$player_id == as.character(row$player_id[[1]])
        ) |>
        slice(1)

      row$pr_snapshot_week <- snapshot_week
      if (nrow(current_snapshot)) {
        row$pr_current_pos <- current_snapshot$pos[[1]]
        row$pr_current_total <- current_snapshot$pr_total[[1]]
        row$pr_current_avg <- current_snapshot$pr_avg[[1]]
        row$pr_current_final <- current_snapshot$pr_final[[1]]
        row$pr_current_gp <- current_snapshot$gp[[1]]
        row$pr_current_robust <- isTRUE(current_snapshot$robust_pr[[1]])
      }
    }

    prior_robust <- history |>
      filter(
        .data$player_id == as.character(row$player_id[[1]]),
        .data$season < current_season,
        .data$robust_pr
      ) |>
      arrange(desc(.data$season))

    robust_options <- prior_robust
    if (isTRUE(row$pr_current_robust[[1]])) {
      robust_options <- bind_rows(
        tibble(
          season = current_season,
          pos = row$pr_current_pos[[1]],
          pr_total = row$pr_current_total[[1]],
          pr_avg = row$pr_current_avg[[1]],
          pr_final = row$pr_current_final[[1]],
          gp = row$pr_current_gp[[1]]
        ),
        prior_robust
      )
    }

    set_robust_slot <- function(prefix, robust_row = NULL) {
      values <- if (is.null(robust_row) || !nrow(robust_row)) {
        list(season = NA_integer_, pos = NA_character_, total = NA_real_, avg = NA_real_, final = NA_real_, gp = NA_integer_)
      } else {
        list(
          season = robust_row$season[[1]], pos = robust_row$pos[[1]],
          total = robust_row$pr_total[[1]], avg = robust_row$pr_avg[[1]],
          final = robust_row$pr_final[[1]], gp = robust_row$gp[[1]]
        )
      }
      row[[paste0("pr_", prefix, "_season_local")]] <<- values$season
      row[[paste0("pr_", prefix, "_pos")]] <<- values$pos
      row[[paste0("pr_", prefix, "_total")]] <<- values$total
      row[[paste0("pr_", prefix, "_avg")]] <<- values$avg
      row[[paste0("pr_", prefix, "_final")]] <<- values$final
      row[[paste0("pr_", prefix, "_gp")]] <<- values$gp
    }
    set_robust_slot("recent", if (nrow(robust_options) >= 1L) robust_options[1, ] else NULL)
    set_robust_slot("previous", if (nrow(robust_options) >= 2L) robust_options[2, ] else NULL)
    row$robust_pr_count <- nrow(robust_options)

    contract_text <- trimws(as.character(row$contract[[1]] %||% ""))
    contract_year <- suppressWarnings(as.integer(sub("^([0-9]{4}).*", "\\1", contract_text)))
    contract_tool <- dplyr::case_when(
      grepl("\\boEXT\\b", contract_text) ~ "oEXT",
      grepl("\\biEXT\\b", contract_text) ~ "iEXT",
      grepl("\\bmEXT\\b", contract_text) ~ "mEXT",
      grepl("\\bB/R\\b", contract_text) ~ "B/R",
      TRUE ~ NA_character_
    )
    rookie_type <- dplyr::case_when(
      grepl("^[0-9]{4} UDFA$", contract_text) ~ "UDFA",
      grepl("^[0-9]{4} [0-9]+\\.[0-9]+", contract_text) ~ "Drafted rookie",
      TRUE ~ NA_character_
    )
    rookie_max_remaining <- dplyr::case_when(
      rookie_type == "UDFA" ~ max(0, 3 - (current_season - contract_year)),
      rookie_type == "Drafted rookie" ~ max(0, 4 - (current_season - contract_year)),
      TRUE ~ NA_real_
    )
    cooldown <- isTRUE(
      (contract_tool == "oEXT" && contract_year == current_season) ||
        (contract_tool %in% c("mEXT", "B/R", "iEXT") && contract_year == current_season)
    )
    next_ext_type <- if (identical(contract_tool, "iEXT")) "iEXT" else "oEXT"
    reasons <- c(
      if (!isTRUE(row$historical_roster_found[[1]])) paste0("not rostered in this conference in Week ", selected_week),
      if (as.numeric(row$prev_years[[1]]) >= 2) "2+ current contract years",
      if (!is.na(rookie_max_remaining) && as.numeric(row$prev_years[[1]]) < rookie_max_remaining) {
        "rookie contract signed for less than maximum years"
      },
      if (cooldown) {
        paste0("Signed ", contract_text, "; next eligible EXT is ", contract_year + 1L, " ", next_ext_type)
      }
    )
    if (row$robust_pr_count[[1]] == 0L) reasons <- c(reasons, "no Robust PRs")
    row$eligibility_note <- if (length(reasons)) paste0("Ineligible: ", paste(reasons, collapse = "; ")) else "Likely EXT eligible"

    row$epv_current <- NA_real_
    row$epv_recent <- NA_real_
    row$epv_previous <- NA_real_
    row
}
