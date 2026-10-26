library(shiny)
library(dplyr)
source("R/ext_engine.R")
source("R/ext_player_context.R")
source("R/cap_manager_engine.R")
source("R/cap_manager_data.R")
source("R/cap_manager_module.R")
near <- function(a,b) stopifnot(isTRUE(all.equal(a,b,tolerance=1e-8,check.attributes=FALSE)))
f <- c(rep(230,6),rep(NA_real_,11))
p <- cap_projection(f,250,244,240)
near(p$effective,20.91); near(p$projected_average,236.47); near(p$projected_rollover,13.53)
near(cap_projection(f,300,244,200)$projected_rollover,24.4)
near(cap_projection(f,210,244,240)$projected_rollover,-26.47)
near(cap_projection(rep(230,17),250,244,999)$projected_rollover,20)
stopifnot(is.na(cap_projection(rep(NA_real_,17),250,244,240)$average))
near(cap_drop_penalty(7.5,4,"SD",as_of=as.Date("2026-10-23"))$current,4.5)
near(cap_drop_penalty(7.5,4,"SD",as_of=as.Date("2026-10-23"))$next_year,6.75)
near(cap_drop_penalty(6.6,3,"FG",as_of=as.Date("2026-10-23"))$current,6.6)
near(cap_drop_penalty(6.6,3,"FG",as_of=as.Date("2026-10-23"))$next_year,15.25)
near(cap_drop_penalty(7.5,4,"SD",as_of=as.Date("2026-06-23"))$current,11.25)
near(cap_drop_penalty(7.5,4,"SD",as_of=as.Date("2026-06-23"),july_tender=TRUE)$next_year,6.75)
near(cap_drop_penalty(7.5,4,"SD",as_of=as.Date("2026-10-23"),accelerate=TRUE)$current,11.25)
near(cap_drop_penalty(7.5,4,"SD",claimed=TRUE)$total,0)
near(cap_drop_penalty(7.5,4,"SD",status="SUSPENDED",as_of=as.Date("2026-10-23"))$current,2.25)
near(cap_drop_penalty(7.5,4,"SD",status="RETIRED")$total,0)
near(cap_drop_penalty(7.5,4,"NG")$total,0)
near(cap_drop_penalty(10,1,"FG",fifth_year=20,as_of=as.Date("2026-10-23"))$current,10)
roster <- data.frame(prev_salary=rep(1.1,45),roster_status="ROSTER",injury="")
near(cap_spending(roster,0,1.1)$spending,49.5)
near(cap_spending(roster[-1,],0,1.1)$spending,49.5)
roster$roster_status[1] <- "TAXI_SQUAD"; roster$injury[1] <- "Suspended"
near(cap_spending(roster,0,1.1)$vacancy,1.1)
cache <- cap_load_cache(season=2026)
stopifnot(nrow(cache$teams)==32,ncol(cache$finals)==17)
for(i in seq_len(32)) {
  t <- cache$teams[i,]
  p <- cap_projection(cache$finals[i,],t$franchise_cap,cache$league_cap,0)
  stopifnot(p$weeks>=6,p$weeks<=17)
  cap_spending(cache$roster[cache$roster$franchise==t$franchise,],t$adjustment,1.1)
}
# Compare every team to the actual Google Sheets cached calculations, not our implementation.
workbook <- Sys.getenv("CAP_TEST_WORKBOOK")
if(nzchar(workbook)) {
  sheet <- readxl::read_excel(workbook,sheet="Cap Rollover",col_names=FALSE,col_types="text",.name_repair="minimal")
  for(i in seq_len(32)) {
    p <- cap_projection(cache$finals[i,],cache$teams$franchise_cap[i],cache$league_cap,0)
    near(p$average,as.numeric(sheet[[206]][i+2]))
    # The sheet's effective figure assumes future spending stays at the
    # historical average; the dashboard instead uses current expenditures.
    sheet_basis <- cap_projection(cache$finals[i,],cache$teams$franchise_cap[i],cache$league_cap,p$average)
    near(sheet_basis$effective,as.numeric(sheet[[209]][i+2]))
    near(p$expected_rollover,as.numeric(sheet[[211]][i+2]))
  }
}
message("Cap engine: accounting, penalties and 32-team sheet reconciliation passed.")

fixture <- list(teams=data.frame(franchise=c("A","B","C"),franchise_cap=c(250,260,270)),
  roster=data.frame(franchise=c("A","B","C"),conference=c("X","X","Y")),
  finals=rbind(c(200,220,NA),c(240,250,NA),c(260,270,NA)))
h <- cap_history_series(fixture,"A")
near(h$value[h$series=="Conference - Weekly"][1:2],c(220,235))
near(h$value[h$series=="Franchise - Cumulative avg."][1:2],c(200,210))
near(cap_history_series(fixture,"A","space")$value[1:2],c(50,30))
stopifnot(all(is.na(h$value[h$week==3])))
invisible(ggplot2::ggplot_build(cap_history_plot(h,character(),250,244)))
cat("Cap history checks passed.\n")

# Real roster projection: next-year accounting must reconcile for all 32 teams.
cache <- cap_load_cache(season=2026)
if(!is.null(cache$next_season)) {
  rules <- cache$next_season$rules
  fit <- stats::lm(cap~I(year-2022),data=rules$capGrowth$history)
  near(unname(predict(fit,data.frame(year=2027))),264.03)
  near(rules$rookieGrowth$annualMultiplier,186.57/168.08)
  for(code in cache$teams$franchise) {
    n <- cap_next_outlook(cache,code,rollover=20)
    near(n$franchise_cap,284.03)
    near(n$official_adjustments,round_salary(cache$next_season$adjustments$adjustment[
      match(code,cache$next_season$adjustments$franchise)]))
    near(n$spending,round_salary(n$salaries+n$vacancy+n$official_adjustments))
    near(n$vacancy,n$empty*1.1)
    stopifnot(n$paid==sum(n$roster$next_years>0),n$empty==max(0,45-n$paid))
  }
  n <- cap_next_outlook(cache,"CHI",rollover=20)
  # Fixed-value regressions must not depend on production adjustments changing.
  adjustment_fixture <- cache
  chi_adjustment <- match("CHI",adjustment_fixture$next_season$adjustments$franchise)
  adjustment_fixture$next_season$adjustments$adjustment[chi_adjustment] <- 4.94
  near(cap_next_outlook(adjustment_fixture,"CHI",rollover=20)$official_adjustments,4.94)
  adjustment_fixture$next_season$adjustments$adjustment[chi_adjustment] <- 7.23
  changed_adjustment <- cap_next_outlook(adjustment_fixture,"CHI",rollover=20)
  near(changed_adjustment$official_adjustments,7.23)
  near(changed_adjustment$spending-cap_next_outlook(cache,"CHI",rollover=20)$spending,
       round_salary(7.23-n$official_adjustments))
  stopifnot(nrow(n$picks)==5,all(n$picks$salary>0),sum(n$roster$next_status=="ERFA tag assumed")==n$erfas)
  draft_rows <- n$roster[n$roster$origin=="Draft reserve",]
  stopifnot(identical(draft_rows$player,paste0(n$year," ",n$picks$round,".",n$picks$original)),
    identical(draft_rows$contract,sprintf("%d %d.%02d",n$year,n$picks$round,as.integer(n$picks$slot))))
  retained <- n$roster[n$roster$next_status=="Current contract",]
  near(retained$next_salary,round_salary(retained$prev_salary*1.1))
  r <- cache$next_season$roster
  r <- r[r$franchise=="CHI" & r$prev_years>1,][1,]
  drop <- list(player_id=r$player_id,action="Drop",next_year=5)
  after <- cap_next_outlook(cache,"CHI",list(drop),rollover=19)
  stopifnot(!r$player_id %in% after$roster$player_id)
  near(after$scenario_penalties,5);near(after$official_adjustments,n$official_adjustments)
  near(after$franchise_cap,n$franchise_cap-1)
  extend <- list(player_id=r$player_id,action="Extend + 2 years",next_year=0,contract_salary=4,contract_years=3)
  ext <- cap_next_outlook(cache,"CHI",list(extend),rollover=20)
  near(ext$roster$next_salary[ext$roster$player_id==r$player_id],4.4)
  sign <- list(player_id="sign:1",player="Test signing",action="Sign Player",next_year=0,contract_salary=3,contract_years=2)
  signed <- cap_next_outlook(cache,"CHI",list(sign),rollover=20)
  near(signed$roster$next_salary[signed$roster$player_id=="sign:1"],3.3)
  sign$contract_years <- 1
  signed <- cap_next_outlook(cache,"CHI",list(sign),rollover=20)
  near(signed$roster$next_salary[signed$roster$player_id=="sign:1"],0)
  incoming <- cache$next_season$roster[cache$next_season$roster$franchise=="DAL",][1,]
  trade <- cap_next_outlook(cache,"CHI",list(list(player_id=incoming$player_id,action="Trade For",next_year=0)),rollover=20)
  stopifnot(incoming$player_id %in% trade$roster$player_id)
  near(cap_drop_penalty(10,1,"FG",fifth_year=20,as_of=as.Date("2026-10-23"))$next_year,20)
  cat("Next-season cap, roster, ERFA, picks and stacked-move checks passed.\n")
}

# Optional integration regression for the numeric IDs supplied by the hosted EXT loader.
if(identical(Sys.getenv("CAP_TEST_LIVE"),"1")) {
  hosted <- readr::read_csv("data/ext_candidates.csv",show_col_types=FALSE)
  hosted$player_id <- as.numeric(hosted$player_id)
  live <- cap_fetch_data(2026,hosted)
  stopifnot(is.null(live$next_season_error),!is.null(live$next_season))
  stopifnot(cap_next_outlook(live,"CHI",rollover=20)$paid>0)
  cat("Live next-season refresh with hosted numeric IDs passed.\n")
}

# Ledger uses official snapshot components and the same weekly-average cap basis.
ledger_cache <- cap_load_cache(season=2026)
if(!is.null(ledger_cache$ledger)) {
  for(code in ledger_cache$teams$franchise) {
    rows <- ledger_cache$ledger[ledger_cache$ledger$franchise==code,,drop=FALSE]
    stopifnot(identical(as.integer(rows$week),seq_len(nrow(rows))))
    near(rows$Final,rows[["Vac$"]]+rows$RostSal+rows$Adj+ifelse(is.na(rows$Corr),0,rows$Corr))
    i <- match(code,ledger_cache$teams$franchise)
    near(round_salary(cap_ledger_cumulative(rows)[["Final"]]),
      cap_projection(ledger_cache$finals[i,],ledger_cache$teams$franchise_cap[i],ledger_cache$league_cap,0)$average)
  }
  sample <- ledger_cache$ledger[1:2,]
  sample$Corr <- c(NA,2)
  near(cap_ledger_cumulative(sample)[["Corr"]],1)
  cat("Official weekly ledger reconciles for all 32 teams; cumulative averages match Cap Rollover.\n")
}

stopifnot(cap_vet_min(2027)==1.1)

cash_rows <- data.frame(FRAN=c("DEN","DEN","BAL","KCC","DEN"),
  PLAYER=c("Cash Trade"," cash trade ","Cash Trade","Cash Trade","Player dropped"),
  SALARY=c("6.00","$6.20","-6","-6.20","100"))
stopifnot(identical(cap_cash_balances(2026,c("DEN","BAL","KCC"),cash_rows),c(-12.2,6,6.2)))

cash_rows$DATE <- c("8/1/2026 18:18:52","8/1/2026 19:39:15","8/1/2026 18:18:52","8/1/2026 19:39:15","8/1/2026 00:00:00")
ledger <- cap_cash_ledger(2026,c("DEN","BAL","KCC"),cash_rows)
den <- ledger$trades[ledger$trades$franchise=="DEN",]
stopifnot(identical(den$partner,c("BAL","KCC")),all(den$date=="08/01"),sum(den$amount)==12.2)

free_meta <- list(players=list(player=list(
  list(id="one",name="Alpha, Test",team="FA",position="WR"),
  list(id="two",name="Beta, Test",team="FA",position="RB"))))
free_pools <- list(freeAgents=list(leagueUnit=list(
  list(unit="CONFERENCE00",player=list(list(id="one"))),
  list(unit="CONFERENCE01",player=list(list(id="two"))))))
free_rosters <- data.frame(conference=c("AFC","NFC"),player_id=c("one","two"))
free_result <- cap_free_agent_pool(free_pools,free_meta,free_rosters)
stopifnot(identical(free_result$player_id,c("two","one")),identical(free_result$conference,c("AFC","NFC")))

stopifnot(identical(cap_ledger_illegal(c(NA,"","0","NO","FALSE","X","illegal")),c(FALSE,FALSE,FALSE,FALSE,FALSE,TRUE,TRUE)))


# CAR regression: a recent spending increase must consume remaining headroom.
car_history <- c(238.97,241.57,241.57,242.80,245.70,242.97,rep(NA_real_,11))
car <- cap_projection(car_history,262.99,244,271.17)
near(car$effective,3.13)
ceiling <- (17*262.99-sum(car_history,na.rm=TRUE))/11
near(cap_projection(car_history,262.99,244,ceiling)$projected_average,262.99)
stopifnot(cap_projection(car_history,262.99,244,303)$projected_average>262.99)
near(cap_projection(rep(NA_real_,17),250,244,240)$effective,10)
stopifnot(is.na(cap_projection(rep(230,17),250,244,240)$effective))
# A $1 weekly spending increase removes $1 of additional weekly headroom.
for(i in seq_len(nrow(cache$teams))) {
 t <- cache$teams[i,]
 spend <- cap_spending(cache$roster[cache$roster$franchise==t$franchise,],t$adjustment,1.1)$spending
 base <- cap_projection(cache$finals[i,],t$franchise_cap,cache$league_cap,spend)
 higher <- cap_projection(cache$finals[i,],t$franchise_cap,cache$league_cap,spend+1)
 if(base$remaining>0) near(base$effective-higher$effective,1)
}
cat("Effective cap space: CAR spending spike, all-team marginal spending, and season boundaries passed.\n")

status_roster <- data.frame(prev_salary=c(2.38,2,3,4),roster_status=c("TAXI_SQUAD","TAXI_SQUAD","ROSTER","INJURED_RESERVE"),injury=c("Holdout","Suspended","Holdout","Holdout"))
stopifnot(identical(cap_paid(status_roster),c(FALSE,FALSE,TRUE,TRUE)))
stopifnot(identical(cap_taxi_exempt(c("H","(H)","Holdout","S","(S)","Suspended",NA,"Out")),c(rep(TRUE,6),FALSE,FALSE)))
# Holdout taxi does not inherit the suspension-only drop-penalty discount.
near(cap_drop_penalty(10,2,"SD",status="Holdout")$current,6)

