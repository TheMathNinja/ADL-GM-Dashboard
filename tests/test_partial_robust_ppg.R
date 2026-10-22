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
stopifnot(grepl("PPG comparison pool: 3+ Active games (maximum NFL games played at start of week = 6)",markup,fixed=TRUE),
  !grepl("Gray players are outside the pool",markup,fixed=TRUE))
stopifnot(partial_robust_max_games(2026L, 5L)==5L,
  partial_robust_min_games(2026L, 5L)==3L,
  partial_robust_max_games(2026L, 15L)==14L,
  partial_robust_min_games(2026L, 15L)==7L)
stopifnot(grepl('(1)',markup,fixed=TRUE), !grepl('(QB1)',markup,fixed=TRUE),
  grepl('class="rank-excluded rank-selected"',markup,fixed=TRUE))
qualified_popup <- pr_rank_list(tibble(), updated, 2026L, "QB", 6L, 2026L, "avg", "b")
qualified_markup <- as.character(pr_rank_popover("QB1", qualified_popup, 2026L, "QB", "avg", "b", 2026L))
stopifnot(!grepl('(1)',qualified_markup,fixed=TRUE),
  !grepl('class="rank-excluded rank-selected"',qualified_markup,fixed=TRUE))
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
stopifnot(!grepl("PPG ranked against players with",app_text,fixed=TRUE),
  identical(pr_rank_player_label("Nacua, Puka","LAR","WR"),"Puka Nacua LAR WR"),
  identical(pr_rank_player_label("Mitchell, Adonai","NYJ","WR"),"Adonai Mitchell NYJ WR"),
  identical(pr_rank_player_label("Thomas Jr., Brian",NA_character_,"WR"),"Brian Thomas Jr. WR"))
cat("PASS: first-last team/position labels; numeric-only evaluation ranks; duplicate current-rank helper removed.\n")

source("R/pr_history.R")
identity_cache <- tempfile("pr-identity-")
dir.create(identity_cache)
saveRDS(data.frame(id="0001",team="SEA"),file.path(identity_cache,"mfl_players_ADL25_2025_raw.rds"))
saveRDS(data.frame(id="0001",team="PIT"),file.path(identity_cache,"mfl_players_ADL26_2026_raw.rds"))
identity_rows <- data.frame(season=c(2025L,2026L,2026L),player_id="0001",player_team=c(NA,NA,"DAL"),pr_avg=c(1,2,3))
enriched <- add_pr_player_teams(identity_rows,identity_cache)
stopifnot(identical(enriched$player_team,c("SEA","PIT","DAL")),identical(enriched$pr_avg,identity_rows$pr_avg))
trade_scores <- data.frame(season=2026L,week=c(1L,2L),player_id="0001",pos="WR",
  player_name="Trade, Test",team=c("SEA","PIT"),points=c(10,20))
stopifnot(summarise_player_pr_scores(trade_scores[1,])$player_team=="SEA",
  summarise_player_pr_scores(trade_scores)$player_team=="PIT")
cat("PASS: cached season-specific identity fallback; raw as-of-week teams preserved across trades; ranks untouched.\n")
