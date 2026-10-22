library(dplyr)
source("R/pr_partial_robust.R")
source("R/pr_rank_popovers.R")
source("R/pr_completed_seasons.R")

# Independently insert each player into the eligible comparison list.
set.seed(26)
for (minimum in 1:8) {
  ppg <- sample(c(NA_real_, 0:20), 200, replace = TRUE)
  gp <- sample(1:17, 200, replace = TRUE)
  expected <- vapply(seq_along(ppg), function(i) {
    pool <- which(gp >= minimum & !is.na(ppg))
    pool <- union(pool, i)
    rank(-ppg[pool], na.last = "keep")[match(i, pool)]
  }, numeric(1))
  stopifnot(identical(personalized_ppg_ranks(ppg, gp, minimum), expected))
}
stopifnot(identical(personalized_ppg_ranks(c(20, 20, 30, 10), c(3, 1, 1, 3), 3L), c(1, 1.5, 1, 2)))
stopifnot(identical(personalized_ppg_ranks(c(NA_real_, 10), c(1, 1), 3L), c(NA_real_, 1)))
stopifnot(length(personalized_ppg_ranks(numeric(), integer(), 3L)) == 0L)
expected <- c(1,1,2,2,3,3,4,4,5,5,6,6,7,7,7,8,8)
stopifnot(identical(vapply(1:17, function(w) partial_robust_min_games(2026L, w), integer(1)), as.integer(expected)))
stopifnot(partial_robust_min_games(2026L, 0L) == 0L)
stopifnot(inherits(try(partial_robust_min_games(2026L, 6L, "missing"), silent = TRUE), "try-error"))

rows <- tibble(season=2026L, pos=c("QB", "QB", "QB", "WR"), player_id=c("a", "b", "c", "d"),
  player_name=c("Selected", "Qualified", "Short", "Other Position"), gp=c(2L, 6L, 1L, 8L),
  ppg=c(20, 10, 30, 50), total_points=c(40, 60, 30, 400), pr_total=c(2,1,3,1),
  pr_avg=c(2,3,1,1), pr_final=c(2,1,1,1), robust_pr=c(FALSE,FALSE,FALSE,TRUE), snapshot_week=6L)
updated <- apply_partial_robust_ppg_ranks(rows, 2026L, 6L)
stopifnot(identical(updated$pr_avg, c(1,1,1,1)), identical(updated$robust_pr, rows$robust_pr),
  identical(updated$pr_total, rows$pr_total), identical(updated$gp, rows$gp))
popup <- pr_rank_list(tibble(), updated, 2026L, "QB", 6L, 2026L, "avg", "a")
stopifnot(!popup$excluded[popup$player_id=="a"], popup$display_rank[popup$player_id=="a"]==1,
  popup$excluded[popup$player_id=="c"], is.na(popup$display_rank[popup$player_id=="c"]),
  !popup$excluded[popup$player_id=="b"])
markup <- as.character(pr_rank_popover("QB1", popup, 2026L, "QB", "avg", "a", 2026L))
stopifnot(grepl("3+ Active games", markup, fixed=TRUE))
historical <- mutate(updated, season=2025L)
historical <- apply_completed_season_ppg_ranks(historical, 2026L, "missing")
stopifnot(all(is.na(historical$pr_avg[historical$gp<8])), historical$pr_avg[historical$gp>=8]==1)
cat("PASS: personalized insertion/ties; schedule-aware bye thresholds; position isolation; full robust unchanged; popup selected exception; completed seasons unchanged.\n")

app_text <- paste(readLines("app.R",warn=FALSE),collapse="\n")
start <- regexpr("format_next_kickoff_label <- function",app_text,fixed=TRUE)[[1]]
end <- regexpr("position_order <-",app_text,fixed=TRUE)[[1]]
stopifnot(start>0,end>start)
`%||%` <- function(x,y) if(is.null(x)||!length(x)||is.na(x)) y else x
eval(parse(text=substr(app_text,start,end-1L)))
schedule <- data.frame(mfl_team="JAC",week=c(1L,7L,8L),is_bye=c(FALSE,TRUE,FALSE),
  kickoff_label=c("Sun Sep 13 1:00p ET",NA_character_,"Sun Nov 1 1:00p ET"))
stopifnot(identical(format_next_kickoff_label("JAC",7L,schedule),"JAC Week 7: Bye"),
  identical(format_next_kickoff_label("JAC",8L,schedule),"JAC Week 8 begins at Sun Nov 1 1:00p ET"),
  is.null(format_next_kickoff_label("FA",7L,schedule)))
cat("PASS: kickoff label selects the requested week, including byes, not the first schedule row.\n")
