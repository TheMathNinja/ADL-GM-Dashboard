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
