pr_rank_list <- function(history, snapshots, season, position, week, active_season, metric, selected_player_id = NULL) {
  stopifnot(metric %in% c("total", "avg"))
  rows <- history
  if (season == active_season) {
    if (!nrow(snapshots) || week < 1L) return(tibble::tibble())
    available <- snapshots$snapshot_week[snapshots$season == season]
    if (!length(available)) return(tibble::tibble())
    snapshot <- min(week, max(available, na.rm = TRUE))
    rows <- snapshots[snapshots$season == season & snapshots$snapshot_week == snapshot, ]
  }
  if (!nrow(rows)) return(tibble::tibble())
  rows <- rows[rows$season == season & rows$pos == position, ]
  rows <- rows[!duplicated(rows$player_id), ]
  rows$display_value <- if (metric == "avg") rows$ppg else rows$total_points
  minimum <- if (season == active_season && "partial_robust_min_games" %in% names(rows))
    rows$partial_robust_min_games else 8L
  selected <- as.character(rows$player_id) %in% as.character(selected_player_id)
  rows$excluded <- metric == "avg" & (is.na(rows$gp) | rows$gp < minimum) &
    !(season == active_season & selected)
  rows$display_rank <- if (metric == "avg") rows$pr_avg else rows$pr_total
  rows$display_rank[rows$excluded] <- NA_real_
  rows[order(-rows$display_value, rows$player_name, na.last = TRUE), ]
}

pr_rank_popover <- function(label, rows, season, position, metric, player_id, active_season,
                            host_class = "robust-season-rank rank-popover-host", context_note = NULL) {
  title <- paste(season, position, if (metric == "avg") "PPG ranks" else "Total points ranks")
  rank_text <- function(value) {
    if (is.na(value)) "--" else paste0(position, format(value, trim = TRUE, scientific = FALSE))
  }
  content <- htmltools::tagList(
    htmltools::tags$div(class = "rank-popover-title", title),
    if (!is.null(context_note)) htmltools::tags$div(class = "rank-popover-note", context_note),
    if (metric == "avg") htmltools::tags$div(class = "rank-popover-note",
      if (season < active_season) "Ranked pool: 8+ games. Gray players are excluded."
      else if (nrow(rows) && "partial_robust_min_games" %in% names(rows)) paste0(
        "PPG comparison pool: ", rows$partial_robust_min_games[[1]],
        "+ Active games. The selected player is ranked even below this threshold. Gray players are excluded.")
      else "PPG comparison pool unavailable."),
    if (!nrow(rows)) htmltools::tags$p("No scores available for this week.") else
      htmltools::tags$div(class = "rank-popover-scroll", htmltools::tags$table(
        htmltools::tags$thead(htmltools::tags$tr(lapply(c("Rank", "Player", "GP", if (metric == "avg") "PPG" else "Points"), htmltools::tags$th))),
        htmltools::tags$tbody(lapply(seq_len(nrow(rows)), function(i) {
          row <- rows[i, ]
          htmltools::tags$tr(class = paste(if (row$excluded) "rank-excluded" else "", if (as.character(row$player_id) == as.character(player_id)) "rank-selected" else ""),
            htmltools::tags$td(rank_text(row$display_rank)),
            htmltools::tags$td(row$player_name), htmltools::tags$td(row$gp),
            htmltools::tags$td(if (is.na(row$display_value)) "--" else formatC(row$display_value, format = "f", digits = 2)))
        }))
      ))
  )
  htmltools::tags$span(class = host_class,
    htmltools::tags$button(type = "button", class = "rank-popover-trigger", `aria-label` = paste("Show", title),
      `aria-expanded` = "false", `aria-haspopup` = "dialog", label),
    htmltools::tags$template(class = "rank-popover-template", content))
}
