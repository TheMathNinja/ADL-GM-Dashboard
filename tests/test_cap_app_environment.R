# Shiny evaluates app.R in its own environment, rather than globalenv().
library(shiny)
app_environment <- new.env(parent=globalenv())
source("app.R", local=app_environment)
stopifnot(identical(environment(app_environment$cap_manager_server),app_environment))
testServer(app_environment$cap_manager_server,args=list(
  players_data=reactive(app_environment$players),
  snapshots_data=reactive(app_environment$pr_weekly_snapshots),
  history_data=reactive(app_environment$pr_history),
  season=2026,active=reactive(FALSE)), {
  session$setInputs(team="ARI",forward=250,action="Extend")
  session$flushReact()
  stopifnot(nzchar(output$current$html),nzchar(output$projection$html),nzchar(output$freshness$html))
  session$setInputs(player=roster()$player_id[1])
  session$flushReact()
  stopifnot(!is.null(context()),!is.null(output$move_controls))
})
message("PASS: hosted app environment resolves cap formatting, EXT week and module helpers.")
