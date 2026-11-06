library(dplyr)
source("R/ext_free_agents.R")
catalog <- tibble(player_id=c("1","2","3","4"), player_name=c("Zulu, A","Alpha, B","Beta, C","Defense"),
  team=c("NYJ","SEA","BUF","DAL"), pos=c("QB","WR","LB","Def"))
rosters <- tibble(conference=c("AFC","NFC"), player_id=c("1","2"))
availability <- tidyr::crossing(conference=c("AFC","NFC"), player_id=c("1","2","3","4"))
fa <- build_free_agent_rosters(catalog, rosters, 2026, availability)
stopifnot(!any(fa$conference=="AFC" & fa$player_id=="1"),
  any(fa$conference=="NFC" & fa$player_id=="1"),
  any(fa$conference=="AFC" & fa$player_id=="2"),
  !any(fa$conference=="NFC" & fa$player_id=="2"),
  !any(fa$player_id=="4"), !anyDuplicated(fa[c("conference","player_id")]))
row <- filter(fa, conference=="AFC", player_id=="3")
stopifnot(is.null(apply_free_agent_terms(row,"",1)),
  is.null(apply_free_agent_terms(row,"-2",1)),
  is.null(apply_free_agent_terms(row,"Inf",1)),
  is.null(apply_free_agent_terms(row,"3",7)))
for (years in 1:6) {
  result <- apply_free_agent_terms(row,"4.25",years)
  stopifnot(result$prev_salary==4.25, result$prev_years==years)
}
limited <- build_free_agent_rosters(catalog, rosters, 2026,
  filter(availability, !(conference=="AFC" & player_id=="3")))
stopifnot(!any(limited$conference=="AFC" & limited$player_id=="3"))
cat("PASS: conference availability, ID exclusion, supported positions, blank/invalid salary, all contract lengths.\n")

# Exercise the app's pricing gate, including the jsonlite/shiny validate name collision.
app <- paste(readLines("app.R", warn=FALSE), collapse="\n")
start <- regexpr("  result <- reactive({", app, fixed=TRUE)[[1]]
end <- regexpr("  robust_season_rows <- reactive({", app, fixed=TRUE)[[1]]
stopifnot(start>0, end>start)
check_gate <- function(salary) {
  env <- new.env(parent=globalenv())
  env$reactive <- shiny::reactive
  env$req <- shiny::req
  env$validate <- jsonlite::validate
  env$input <- list(ext_years=1,week=8,fa_salary=salary,fa_years=1)
  env$selected_player_base <- function() row
  env$selected_player <- function() row
  env$selected_fifth_year_option <- function() NA_real_
  env$salary_curves <- NULL
  env$extension_breakdown <- function(...) "priced"
  eval(parse(text=substr(app,start,end-1L)), envir=env)
  tryCatch(shiny::isolate(env$result()), shiny.silent.error=function(e) "blocked")
}
stopifnot(identical(check_gate(""),"blocked"), identical(check_gate("bad"),"blocked"),
  identical(check_gate("5"),"priced"))
cat("PASS: real app blocks blank/invalid salary before invoking pricing.\n")

source("R/ext_player_context.R")
start <- regexpr("  selected_player <- reactive({", app, fixed=TRUE)[[1]]
end <- regexpr("  selected_max_ext_years <- reactive({", app, fixed=TRUE)[[1]]
stopifnot(start>0, end>start)
live <- tibble(conference="NFC", franchise="CHI", player_id="14104", player_pos="WR",
  prev_salary=5.70, prev_years=1, contract="2026 UFA")
old <- mutate(live, season=2026L, week=8L, franchise="ATL", prev_salary=36.61, contract="2024 oEXT")
snapshots <- tibble(season=2026L, player_id="14104", snapshot_week=c(7L,8L),
  pos="WR", pr_total=c(20,15), pr_avg=c(19,14), pr_final=c(19,14),
  gp=c(6L,7L), robust_pr=FALSE)
for (week in c(7L,8L,9L)) {
  env <- new.env(parent=globalenv())
  env$reactive <- shiny::reactive
  env$input <- list(week=week)
  env$current_season <- 2026L
  env$extension_week_current <- 8L
  env$`%||%` <- function(x,y) if (is.null(x)) y else x
  env$selected_player_base <- function() live
  env$pr_weekly_snapshots_data <- function() snapshots
  env$pr_history_data <- function() snapshots[0,]
  env$ext_roster_history_data <- function() old
  eval(parse(text=substr(app,start,end-1L)), envir=env)
  chosen <- shiny::isolate(env$selected_player())
  stopifnot(chosen$franchise=="CHI", chosen$prev_salary==5.70, chosen$prev_years==1,
    chosen$contract=="2026 UFA", chosen$pr_current_gp==if (week==7L) 6L else 7L)
}
cat("PASS: EXT week changes scores without replacing the live contract.\n")
