library(shiny)
# app.R supplies the same global data and helpers as production.
app <- source("app.R")$value
near <- function(a,b) stopifnot(isTRUE(all.equal(a,b,tolerance=1e-8,check.attributes=FALSE)))
signing_test_data <- function(d) {
  labels <- c("Test signing","Future test","First","Second","Third")
  d$free_agents <- data.frame(conference="NFC",player_id=labels,player=labels,stringsAsFactors=FALSE)
  d
}

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
  stopifnot(!grepl("Contract guarantee at signing",output$move_controls$html),
            grepl(paste0("(",guarantee,")"),names(cap_player_choice_labels(selected(),2026)),fixed=TRUE),
            !grepl("<select",output$move_controls$html),
            grepl("Last Updated",output$freshness$html))
  delta <- preview()$delta
  session$setInputs(add=1)
  session$flushReact()
  stopifnot(length(moves())==1)
  stopifnot(picker_updates>0L)
  near(scenario()$delta,delta+vacancy_delta(moves()))
  near(scenario()$components$adjustment_delta,expected$current)
  near(scenario()$components$salary_delta,-row$prev_salary)
  stopifnot(grepl(paste0("Weeks 1-",scenario()$weeks,": "),output$projection$html,fixed=TRUE),
    grepl(paste0("Weeks ",scenario()$weeks+1,"-17: "),output$projection$html,fixed=TRUE),
    !grepl("recorded weeks +",output$projection$html,fixed=TRUE))
  near(scenario()$forward,round_salary(current()$spending+scenario()$delta))
  # A second dropped player cannot be added twice; undo restores baseline.
  session$setInputs(player=row$player_id)
  stopifnot(is.null(preview()))
  session$setInputs(remove_move="1",remove=1)
  near(scenario()$delta,0)
  session$setInputs(team="BUF")
  stopifnot(length(moves())==0)
  near(scenario()$forward,current()$spending)
  session$setInputs(forward=9999) # Removed input must never override the roster baseline.
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
  d <- signing_test_data(data())
  kept <- which(d$roster$franchise=="CHI" & cap_paid(d$roster))[seq_len(43)]
  d$roster <- d$roster[d$roster$franchise!="CHI" | seq_len(nrow(d$roster)) %in% kept,]
  d$teams$net_cash_received <- 0
  data(d)
  session$setInputs(team="CHI",forward=250,action="Sign Player",sign_player="Test signing",sign_salary=3)
  session$flushReact()
  stopifnot(current()$empty==2,preview()$paid_delta==1)
  session$setInputs(add=1)
  near(vacancy_delta(moves()),-1.1)
  near(scenario()$delta,1.9)
  # A $3 signing fills a $1.10 reserve: current weekly spending rises $1.90.
  projection_doc <- xml2::read_html(output$projection$html)
  current_metric <- xml2::xml_find_first(projection_doc,"//div[contains(@class,'cap-metric')][span[normalize-space(.)='Current Expenditures (scenario)']]")
  comparison <- xml2::xml_find_first(current_metric,"small[contains(@class,'cap-change')]")
  stopifnot(xml2::xml_text(comparison)=="+$1.90m vs current",grepl("unfavorable",xml2::xml_attr(comparison,"class")),
    grepl("Projected Seasonlong Expenditures",output$projection$html,fixed=TRUE))
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
  near(scenario()$components$adjustment_delta,-1)
  near(scenario()$components$salary_delta,3-row$prev_salary+incoming$prev_salary)
  near(scenario()$forward,scenario()$components$roster+scenario()$components$vacancy+scenario()$components$adjustment)
  near(scenario()$delta,3-row$prev_salary+incoming$prev_salary-2.1)
  stopifnot(length(moves())==4,nzchar(output$moves$html),grepl("Net Cash Charge via Trades",output$current$html))
  html <- output$projection$html
  stopifnot(grepl("Projected Seasonlong Expenditures",html),grepl("(scenario)",html,fixed=TRUE),grepl("Maximum rollover",html),grepl("cap-change",html))
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
          !cap_cash_status(0,c(13,-13),244)$valid)
stopifnot(cap_injury_week(2026,as.POSIXct("2026-10-23 20:00:00",tz="UTC"))==7L)
message("PASS: mixed signing/trade/cash queue, vacancy offsets, partner limits, comparisons and cash classification.")

# Future UI must resolve in the same module session as the current-year queue.
if(!is.null(cap_load_cache(season=2026)$next_season)) {
  shiny::testServer(cap_manager_server,args=list(players_data=reactive(players),
    snapshots_data=reactive(pr_weekly_snapshots),history_data=reactive(pr_history),season=2026,active=shiny::reactive(FALSE),
    as_of=function()as.POSIXct("2026-06-01",tz="UTC")), {
    data(signing_test_data(data()))
    session$setInputs(team="CHI",forward=230,action="Sign Player",sign_player="Future test",sign_salary=3,sign_years=2)
    session$flushReact()
    before <- next_outlook()
    stopifnot(!inherits(before,"error"),grepl("2027 projected ADL league cap",output$next_season$html))
    session$setInputs(add=1);session$flushReact()
    after <- next_outlook()
    stopifnot(any(after$roster$player=="Future test"),after$paid==before$paid+1)
    stopifnot(grepl("Future test",output$next_roster$html))
  })
}

testServer(cap_manager_server,args=list(players_data=reactive(players),
  snapshots_data=reactive(pr_weekly_snapshots),history_data=reactive(pr_history),
  season=2026,active=reactive(FALSE)), {
  session$setInputs(team="CHI",action="Extend")
  allowed <- available_players()
  if(nrow(allowed)) stopifnot(all(vapply(seq_len(nrow(allowed)),function(i)
    length(cap_extension_years(player_context(allowed[i,,drop=FALSE]),extension_week_current))>0,logical(1))))
  session$setInputs(action="Drop")
  stopifnot(nrow(available_players())==nrow(roster()))
  d <- data(); d$teams$net_cash_received[d$teams$franchise=="CHI"] <- 6
  d$teams$net_cash_received[d$teams$franchise=="DAL"] <- -10; data(d)
  session$setInputs(action="Cash Trade",cash_partner="DAL",cash_direction="receive",cash_qualifies=TRUE,cash_amount=2.2)
  near(cash_range()$receive,2.2);near(cash_range()$send,18.2)
  stopifnot(!is.null(preview()),grepl("Send up to",output$cash_range$html),grepl("Receive up to",output$cash_range$html))
  session$setInputs(cash_amount=2.21);stopifnot(is.null(preview()))
  session$setInputs(cash_amount=2,add=1)
  near(cash_range()$receive,.2);near(cash_range()$send,20.2)
})
message("PASS: eligible-only EXT picker, contract labels and both-team cash ranges including queued moves.")

testServer(cap_manager_server,args=list(players_data=reactive(players),
  snapshots_data=reactive(pr_weekly_snapshots),history_data=reactive(pr_history),
  season=2026,active=reactive(FALSE)), {
  data(signing_test_data(data()))
  session$setInputs(team="CHI",forward=250,action="Sign Player",sign_player="First",sign_salary=2,sign_years=2,add=1)
  session$setInputs(sign_player="Second",add=2)
  stopifnot(length(moves())==2,grepl("cap-move-remove",output$moves$html))
  key <- moves()[[1]]$queue_id
  session$setInputs(remove_move=key)
  stopifnot(length(moves())==1,moves()[[1]]$player=="Second")
  session$setInputs(remove_move=key)
  stopifnot(length(moves())==1)
  session$setInputs(sign_player="Third",add=3)
  stopifnot(length(unique(vapply(moves(),function(m)m$player_id,character(1))))==2)
  session$setInputs(reset=1);stopifnot(length(moves())==0)
})
message("PASS: per-move removal uses stable IDs, repeat clicks do not remove neighbors, and Clear Scenario empties the queue.")

stopifnot(cap_scenario_move_title(list(action="Extend + 1 years",player="Taylor, Jonathan IND RB"))=="[Extend 1 year] Taylor, Jonathan IND RB",
  cap_scenario_move_title(list(action="Extend + 3 years",player="Test"))=="[Extend 3 years] Test",
  cap_scenario_move_title(list(action="Drop",player="McLaurin, Terry WAS WR"))=="[Drop] McLaurin, Terry WAS WR")
for(action in c("Trade Away","Trade For","Sign Player","Cash Trade"))
  stopifnot(cap_scenario_move_title(list(action=action,player="Test"))==paste0("[",action,"] Test"))

stopifnot(cap_signing_max_years(2026,as.POSIXct("2026-06-01",tz="UTC"))==6L,
  cap_signing_max_years(2026,as.POSIXct("2026-10-24",tz="UTC"))==1L)
testServer(cap_manager_server,args=list(players_data=reactive(players),
  snapshots_data=reactive(pr_weekly_snapshots),history_data=reactive(pr_history),
  season=2026,active=reactive(FALSE),as_of=function()as.POSIXct("2026-10-24",tz="UTC")), {
  data(signing_test_data(data()))
  session$setInputs(team="CHI",forward=250,action="Sign Player",sign_player="First",sign_salary=3,sign_years=6)
  stopifnot(preview()$contract_years==1,is.null(output$sign_years_control))
  session$setInputs(sign_player="a rostered or fabricated player");stopifnot(is.null(preview()))
  session$setInputs(team="DEN",sign_player="First");stopifnot(nrow(signing_candidates())==0,is.null(preview()))
})
message("PASS: conference free-agent signing selection, offseason multi-year terms and mandatory in-season one-year terms.")

scenario_markup <- as.character(cap_manager_ui("test"))
stopifnot(!grepl("Forward spending|Use current spending|Scenario forward spending",scenario_markup))

# A veteran-minimum drop at 45 paid players is offset by an empty-slot reserve.
testServer(cap_manager_server,args=list(players_data=reactive(players),
 snapshots_data=reactive(pr_weekly_snapshots),history_data=reactive(pr_history),
 season=2026,active=reactive(FALSE)), {
 d <- data(); team_rows <- which(d$roster$franchise=="CHI" & cap_paid(d$roster))
 candidate <- team_rows[which(vapply(team_rows,function(i) cap_guarantee(d$roster[i,,drop=FALSE],2026)=="NG" && d$roster$prev_salary[i]==1.1,logical(1)))[1]]
 stopifnot(!is.na(candidate))
 selected_id <- d$roster$player_id[candidate]
 kept <- c(candidate,head(setdiff(team_rows,candidate),44))
 d$roster <- d$roster[d$roster$franchise!="CHI" | seq_len(nrow(d$roster)) %in% kept,]
 data(d); session$setInputs(team="CHI",action="Drop",claimed=FALSE,accelerate=FALSE)
 session$setInputs(player=selected_id); session$flushReact()
 stopifnot(current()$paid==45,!is.null(preview()))
 stopifnot(grepl("2026 penalty",preview()$detail),!grepl("paid salary removed|one fewer paid player",preview()$detail))
 session$setInputs(add=1);session$flushReact()
 near(scenario()$components$salary_delta,-1.1)
 near(scenario()$components$vacancy_delta,1.1)
 near(scenario()$components$adjustment_delta,0)
 near(scenario()$delta,0)
 stopifnot(grepl("Empty Roster Slots:",output$projection$html,fixed=TRUE),grepl("(+$1.10m)",output$projection$html,fixed=TRUE))
})
message("PASS: scenario components expose the offset between a vet-min drop and an empty roster slot.")

