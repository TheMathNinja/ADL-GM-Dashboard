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
