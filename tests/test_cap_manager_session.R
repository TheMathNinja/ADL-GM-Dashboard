library(shiny)
# app.R supplies the same global data and helpers as production.
app <- source("app.R")$value
near <- function(a,b) stopifnot(isTRUE(all.equal(a,b,tolerance=1e-8,check.attributes=FALSE)))
testServer(cap_manager_server,args=list(players_data=reactive(players),
  snapshots_data=reactive(pr_weekly_snapshots),history_data=reactive(pr_history),
  season=2026,active=reactive(FALSE)), {
  session$setInputs(team="CHI",forward=250,action="Drop")
  session$flushReact()
  stopifnot(nrow(roster())>0,baseline()$weeks>=6)
  # Rendering all visible outputs catches initialization/reactive errors.
  stopifnot(nzchar(output$current$html),nzchar(output$projection$html))
  # The picker must not send itself another choices update when the browser
  # reports a selection. On mobile that feedback loop repeatedly closes it.
  picker_updates <- 0L
  root_session <- session$rootScope()
  original_send <- root_session$sendInputMessage
  root_session$sendInputMessage <- function(inputId, message) {
    if (grepl("(^|-)player$", inputId)) picker_updates <<- picker_updates + 1L
    original_send(inputId, message)
  }
  session$setInputs(player=roster()$player_id[1])
  session$flushReact()
  session$setInputs(player=roster()$player_id[2],forward=251)
  session$flushReact()
  stopifnot(picker_updates==0L)
  row <- roster()[which(cap_paid(roster()))[1],]
  session$setInputs(player=row$player_id,guarantee="SD",claimed=FALSE,accelerate=FALSE)
  session$flushReact()
  stopifnot(!is.null(preview()))
  guarantee <- cap_guarantee(selected(),2026)
  expected <- cap_drop_penalty(selected()$prev_salary,selected()$prev_years,guarantee,selected()$injury)
  near(preview()$penalty,expected$current)
  stopifnot(grepl("Contract guarantee at signing",output$move_controls$html),
            !grepl("<select",output$move_controls$html),
            grepl("Last Updated",output$freshness$html))
  delta <- preview()$delta
  session$setInputs(add=1)
  session$flushReact()
  stopifnot(length(moves())==1)
  stopifnot(picker_updates>0L)
  near(scenario()$delta,delta+vacancy_delta(moves()))
  # A second dropped player cannot be added twice; undo restores baseline.
  session$setInputs(player=row$player_id)
  stopifnot(is.null(preview()))
  session$setInputs(remove_move="1",remove=1)
  near(scenario()$delta,0)
  session$setInputs(team="BUF")
  stopifnot(length(moves())==0)
  session$setInputs(forward=current()$spending)
  near(scenario()$projected_rollover,baseline()$projected_rollover)
  # Check each roster's eligibility and allowed terms against the shared EXT context.
  found <- FALSE
  for(code in data()$teams$franchise) {
    session$setInputs(team=code,action="Extend")
    for(id in roster()$player_id) {
      session$setInputs(player=id)
      p <- context()
      if(!is.null(p) && length(cap_extension_years(p,extension_week_current))) {
        years <- cap_extension_years(p,extension_week_current)
        session$setInputs(years=as.character(years[1]))
        stopifnot(!is.null(preview()))
        result <- extension_breakdown(p,years[1],extension_week_default,salary_curves,
          fifth_year_option=if(has_exercised_fifth_year_option(p)) fifth_year_display_salary(p) else NA_real_)
        near(preview()$delta,if(cap_paid(selected())) round_salary(result$new_salary-selected()$prev_salary) else 0)
        session$setInputs(years="6")
        if(!6 %in% years) stopifnot(is.null(preview()))
        found <- TRUE
        break
      }
    }
    if(found) break
  }
  stopifnot(found)
})
message("Salary Cap Manager session: selection, drop, undo, team reset and shared EXT pricing passed.")

testServer(cap_manager_server,args=list(players_data=reactive(players),
  snapshots_data=reactive(pr_weekly_snapshots),history_data=reactive(pr_history),
  season=2026,active=reactive(FALSE)), {
  # Deliberately use 43 paid players to exercise slot offsets across mixed moves.
  d <- data()
  kept <- which(d$roster$franchise=="CHI" & cap_paid(d$roster))[seq_len(43)]
  d$roster <- d$roster[d$roster$franchise!="CHI" | seq_len(nrow(d$roster)) %in% kept,]
  d$teams$net_cash_received <- 0
  data(d)
  session$setInputs(team="CHI",forward=250,action="Sign Player",sign_name="Test signing",sign_salary=3)
  session$flushReact()
  stopifnot(current()$empty==2,preview()$paid_delta==1)
  session$setInputs(add=1)
  near(vacancy_delta(moves()),-1.1)
  near(scenario()$delta,1.9)
  row <- roster()[1,]
  session$setInputs(action="Trade Away",player=row$player_id)
  stopifnot(preview()$penalty==0,preview()$next_year==0)
  session$setInputs(add=2)
  near(vacancy_delta(moves()),0)
  near(scenario()$delta,3-row$prev_salary)
  incoming <- trade_candidates()[1,]
  session$setInputs(action="Trade For",incoming=incoming$player_id)
  near(preview()$delta,incoming$prev_salary)
  session$setInputs(add=3)
  near(vacancy_delta(moves()),-1.1)
  near(scenario()$delta,3-row$prev_salary+incoming$prev_salary-1.1)
  session$setInputs(action="Cash Trade",cash_partner="DAL",cash_direction="receive",cash_amount=1,cash_qualifies=TRUE)
  near(preview()$delta,-1)
  session$setInputs(add=4)
  near(cash_status()$net,1)
  near(scenario()$delta,3-row$prev_salary+incoming$prev_salary-2.1)
  stopifnot(length(moves())==4,nzchar(output$moves$html),grepl("Net Cash Charge via Trades",output$current$html))
  html <- output$projection$html
  stopifnot(grepl("Projected Expenditures",html),grepl("(scenario)",html,fixed=TRUE),grepl("Maximum rollover",html),grepl("cap-change",html))
  session$setInputs(cash_amount=20)
  stopifnot(is.null(preview()))
  session$setInputs(cash_amount=.015)
  stopifnot(is.null(preview()))
  session$setInputs(cash_amount=1,cash_qualifies=FALSE)
  stopifnot(is.null(preview()))
  # Partner limits are also enforced.
  d <- data(); d$teams$net_cash_received[d$teams$franchise=="DAL"] <- -12.2; data(d)
  session$setInputs(cash_qualifies=TRUE)
  stopifnot(is.null(preview()))
})
stopifnot(cap_cash_status(12.2,0,244)$valid,
          !cap_cash_status(12.2,.01,244)$valid,
          !cap_cash_status(0,c(13,-13),244)$valid,
          cap_is_cash_adjustment("KCC sends $7.2 to IND in a trade 8/13"),
          !cap_is_cash_adjustment("Player dropped at $7.2"))
stopifnot(cap_injury_week(2026,as.POSIXct("2026-10-23 20:00:00",tz="UTC"))==7L)
message("PASS: mixed signing/trade/cash queue, vacancy offsets, partner limits, comparisons and cash classification.")

# Future UI must resolve in the same module session as the current-year queue.
if(!is.null(cap_load_cache(season=2026)$next_season)) {
  shiny::testServer(cap_manager_server,args=list(players_data=reactive(players),
    snapshots_data=reactive(pr_weekly_snapshots),history_data=reactive(pr_history),season=2026,active=shiny::reactive(FALSE)), {
    session$setInputs(team="CHI",forward=230,action="Sign Player",sign_name="Future test",sign_salary=3,sign_years=2)
    session$flushReact()
    before <- next_outlook()
    stopifnot(!inherits(before,"error"),grepl("2027 projected ADL league cap",output$next_season$html))
    session$setInputs(add=1);session$flushReact()
    after <- next_outlook()
    stopifnot(any(after$roster$player=="Future test"),after$paid==before$paid+1)
    stopifnot(grepl("Future test",output$next_roster))
  })
}

