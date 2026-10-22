library(dplyr)
source("R/pr_completed_seasons.R")
source("R/pr_rank_popovers.R")
history <- tibble(season = 2025L, pos = "QB", player_id = c("a", "b", "c"),
  player_name = c("Short", "Robust One", "Robust Two"), gp = c(2, 8, 12),
  total_points = c(80, 240, 240), ppg = c(40, 30, 20), pr_total = c(3, 1.5, 1.5),
  pr_avg = 1:3, pr_final = c(1, 1.5, 1.5))
history <- apply_completed_season_ppg_ranks(history, 2026L, "missing")
avg <- pr_rank_list(history, tibble(), 2025L, "QB", 6L, 2026L, "avg")
stopifnot(nrow(avg) == 3, is.na(avg$display_rank[1]), avg$excluded[1], identical(avg$display_rank[-1], c(1, 2)))
tot <- pr_rank_list(history, tibble(), 2025L, "QB", 6L, 2026L, "total")
stopifnot(identical(tot$display_rank, c(1.5, 1.5, 3)), !any(tot$excluded))
snapshots <- bind_rows(mutate(history, season = 2026L, snapshot_week = 2L),
                       mutate(history, season = 2026L, snapshot_week = 6L, total_points = total_points + 100))
past <- pr_rank_list(history, snapshots, 2026L, "QB", 2L, 2026L, "total")
stopifnot(max(past$total_points) == 240, all(past$snapshot_week == 2L))
stopifnot(nrow(pr_rank_list(history, snapshots, 2026L, "QB", 0L, 2026L, "avg")) == 0)
html <- as.character(pr_rank_popover("Avg: QB1", avg, 2025L, "QB", "avg", "b", 2026L))
stopifnot(grepl("rank-excluded", html), grepl("rank-selected", html), grepl("<template", html), grepl("aria-haspopup", html))
cat("PASS: total/robust-only PPG lists, excluded rows, ties, selected-week isolation and accessible markup.\n")


# Exercise the real summary renderer without starting the Shiny application.
app_text <- paste(readLines("app.R", warn = FALSE), collapse = "\n")
start <- regexpr("  pr_summary_section <- function", app_text, fixed = TRUE)[[1]]
end <- regexpr("  build_pr_summary <- function", app_text, fixed = TRUE)[[1]]
stopifnot(start > 0, end > start)
renderer <- substr(app_text, start, end - 1L)
env <- new.env(parent = globalenv())
env$tags <- htmltools::tags
env$tagList <- htmltools::tagList
env$`%||%` <- function(x,y) if (is.null(x) || length(x)==0 || is.na(x)) y else x
env$money <- function(x) paste0("$",formatC(x,format="f",digits=2),"m")
env$true_rank_label <- function(position, rank) if (is.na(position)||is.na(rank)) "--" else paste0(position,rank)
env$pr_history_data <- function() history
env$pr_weekly_snapshots_data <- function() snapshots
env$input <- list(week=2L)
env$extension_week_current <- 6L
env$current_season <- 2026L
env$selected_player <- function() list(player_id="b")
eval(parse(text=renderer),envir=env)
render_section <- function(year=2025L,total=1.5,average=2,final=1.5,note="QB1.5") {
  as.character(env$pr_summary_section("Test",year,"QB",total,average,final,5,4,5,
    epv_note=note,overall_used=TRUE))
}
markup <- render_section()
stopifnot(length(gregexpr('class="rank-popover-trigger"',markup,fixed=TRUE)[[1]])==3L,
  grepl("Show 2025 QB Total points ranks",markup,fixed=TRUE),
  grepl("Show 2025 QB PPG ranks",markup,fixed=TRUE),
  !grepl('class="robust-season-rank rank-popover-host"',markup,fixed=TRUE))
stopifnot(grepl("EPV evaluation: QB16 (Starter Floor)",
  render_section(total=25,average=30,final=25,note="QB16 (Starter Floor)"),fixed=TRUE))
stopifnot(!grepl("rank-popover-trigger",render_section(year=NA_integer_),fixed=TRUE))
stopifnot(!grepl("rank-popover-trigger",render_section(total=NA_real_,average=NA_real_,final=NA_real_,note="--"),fixed=TRUE))
current_markup <- render_section(year=2026L)
stopifnot(grepl("Show 2026 QB PPG ranks",current_markup,fixed=TRUE),
  grepl("242.00",current_markup,fixed=TRUE)==FALSE,
  grepl("240.00",current_markup,fixed=TRUE))
cat("PASS: summary Tot/Avg/EPV links; matching season/week; starter-floor context; missing-season/rank safety; compact layout.\n")
