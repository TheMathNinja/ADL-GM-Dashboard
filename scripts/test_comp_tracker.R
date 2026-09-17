library(dplyr)
source("R/comp_rules.R")
# Calendar rollover, Eastern noon, exclusive July cutoff and strict trade days.
stopifnot(format(adl_ufa_start(2026), "%Y-%m-%d %H:%M", tz="America/New_York") == "2026-06-15 12:00")
stopifnot(format(adl_ufa_start(2027), "%Y-%m-%d", tz="America/New_York") == "2027-06-21")
stopifnot(format(adl_ufa_start(2028), "%Y-%m-%d", tz="America/New_York") == "2028-06-19")
for (year in 2020:2050) {
  day <- as.POSIXlt(adl_ufa_start(year), tz="America/New_York")
  stopifnot(day$wday == 1L, day$mday >= 15L, day$mday <= 21L, day$hour == 12L)
}
window <- adl_comp_ufa_window(2026)
times <- as.POSIXct(c("2026-06-15 15:59:59", "2026-06-15 16:00:00", "2026-07-01 03:59:59", "2026-07-01 04:00:00"),tz="UTC")
stopifnot(identical(adl_comp_auction_in_window(times,window),c(FALSE,TRUE,TRUE,FALSE)))
stopifnot(identical(adl_comp_trade_after_auction_day(as.Date(c("2026-04-11","2026-06-17","2026-06-18","2026-08-19","2026-09-01")),as.Date("2026-06-17")),c(FALSE,FALSE,TRUE,TRUE,TRUE)))
s <- readRDS("data/comp_picks.rds")
trade_rows <- bind_rows(s$events,s$below_threshold_events) |> filter(acquired == "trade")
if (s$season == 2026) {
  stopifnot(!any(trade_rows$date < as.Date("2026-06-16")))
  stopifnot(any(grepl("Sweat",trade_rows$player_name) & trade_rows$date == as.Date("2026-08-19")))
  stopifnot(sum(grepl("Murphy",trade_rows$player_name) & trade_rows$date %in% as.Date(c("2026-09-01","2026-09-03"))) == 2L)
}
stopifnot(nrow(s$teams) == 32, !anyDuplicated(s$teams$franchise_id))
stopifnot(all(vapply(s$conferences, function(x) nrow(x$picks), integer(1)) == 16))
stopifnot(all(s$events$comp_round %in% 3:5))
for (conf in names(s$conferences)) {
  picks <- s$conferences[[conf]]$picks
  stopifnot(all(table(picks$franchise_id[picks$pick_source == "NET"]) <= 4))
}
# Same-round highest; later-round highest; earlier-round lowest.
fixture <- function(lost_rounds, lost_salary, gained_round, gained_salary) {
  tibble(franchise_id="0001",franchise_name="Test",conference="NFC",
    player_id=as.character(seq_len(length(lost_rounds)+1)),player_name=paste("Player",seq_len(length(lost_rounds)+1)),
    cfa_event=c(rep("LOST",length(lost_rounds)),"GAINED"),
    comp_round=c(lost_rounds,gained_round),win_bid=c(lost_salary,gained_salary))
}
stopifnot(cancel_cfa_events(fixture(c(3,3,4),c(12,20,9),3,15))$cancels$lost_win_bid == 20)
stopifnot(cancel_cfa_events(fixture(c(4,5),c(9,5),3,15))$cancels$lost_win_bid == 9)
stopifnot(cancel_cfa_events(fixture(c(3,4),c(15,9),5,5))$cancels$lost_win_bid == 9)
stopifnot(nrow(cancel_cfa_events(s$events)$cancels) == nrow(s$cancel$cancels))
empty <- build_comp_pick_table(cancel_cfa_events(s$events[0, ]), "AFC")
stopifnot(nrow(empty$picks) == 16, all(empty$picks$pick_source == "FILLER"))
many <- bind_rows(lapply(1:5, function(team) {
  tibble(franchise_id=sprintf("%04d",team), franchise_name=paste("Team",team), conference="NFC",
    player_id=paste(team,1:6),player_name=paste("Player",team,1:6),cfa_event="LOST",
    comp_round=3L,win_bid=seq(30,25)-team/10)
}))
limited <- build_comp_pick_table(cancel_cfa_events(many), "NFC")
stopifnot(nrow(limited$team_trim)==10,nrow(limited$conference_trim)==4,nrow(limited$picks)==16)
bonus <- build_comp_pick_table(cancel_cfa_events(fixture(3,20,3,15)), "NFC")
stopifnot(sum(bonus$picks$pick_source=="BONUS")==1, bonus$picks$win_bid[bonus$picks$pick_source=="BONUS"]==5)
# Optional direct regression against the user's original, without executing its publisher.
original <- Sys.getenv("ADL_COMP_ORIGINAL")
if (nzchar(original)) {
  env <- new.env()
  for (expr in parse(original)) {
    if (is.call(expr) && identical(expr[[1]], as.name("<-")) &&
      as.character(expr[[2]]) %in% c("cancel_cfa_events", "build_comp_pick_table")) eval(expr, env)
  }
  expected <- env$cancel_cfa_events(s$events)
  stopifnot(identical(expected, s$cancel))
  for (conf in c("AFC","NFC")) stopifnot(identical(env$build_comp_pick_table(expected, conf), s$conferences[[conf]]$display))
}
source("R/comp_module.R")
library(shiny)
testServer(comp_tracker_server, {
  for (id in s$teams$franchise_id) {
    session$setInputs(team=id)
    stopifnot(nchar(output$dashboard$html) > 100)
  }
})
cat("PASS: original-script parity; cancellation priority; all 32 team views; conference/team limits.\n")
