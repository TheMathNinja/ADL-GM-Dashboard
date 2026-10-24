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
  stopifnot(grepl("Arizona Cardinals",output$team_banner$html),grepl("ari.png",output$team_banner$html))
  if(!is.null(data()$ledger)) {
    ledger_html <- output$weekly_ledger$html
    stopifnot(grepl("<tfoot>",ledger_html),grepl("<strong>Average",ledger_html),grepl("RostSal",ledger_html))
  }

  roster_doc <- xml2::read_html(output$next_roster$html)
  stopifnot(identical(xml2::xml_text(xml2::xml_find_all(roster_doc,"(//table)[1]/thead/tr/th")),c("Player","Salary","Years","Contract")))
  stopifnot(length(xml2::xml_find_all(roster_doc,"(//table)[1]/tbody/tr[td]"))==next_outlook()$paid)
  stopifnot(grepl("CAP ROOM AVAILABLE:",output$next_roster$html))

  session$setInputs(history_view="expenditures",history_lines="Franchise - Weekly")
  chart_doc <- xml2::read_html(output$history_plot$html)
  targets <- xml2::xml_find_all(chart_doc,"//circle[title]")
  stopifnot(length(targets)>0,all(grepl("opacity:0",xml2::xml_attr(targets,"style"))),
    all(nzchar(xml2::xml_text(xml2::xml_find_all(chart_doc,"//circle/title")))))

  stopifnot(grepl(" ET",output$freshness$html),!grepl("UTC|snapshots recorded|Vet minimum",output$freshness$html))
  session$setInputs(team="CHI"); session$flushReact()
  stopifnot(grepl("Chicago Bears",output$team_banner$html),grepl("chi.png",output$team_banner$html))

})
message("PASS: hosted app environment resolves cap formatting, EXT week and module helpers.")

# Deep links must select the right panel and title in the initial HTTP markup.
for(tool in c("cap","comp","ext")) {
  markup <- htmltools::renderTags(app_environment$ui(list(QUERY_STRING=paste0("tool=",tool))))$html
  doc <- xml2::read_html(markup)
  title <- xml2::xml_text(xml2::xml_find_first(doc,"//*[@id='gm_banner_title']"))
  stopifnot(identical(trimws(title),app_environment$gm_tool_title(tool)))
  active <- xml2::xml_find_all(doc,"//div[(@data-value='cap' or @data-value='comp' or @data-value='ext') and contains(concat(' ',normalize-space(@class),' '),' active ')]")
  stopifnot(identical(xml2::xml_attr(active,"data-value"),tool))
}
stopifnot(app_environment$gm_initial_tool("tool=unknown")=="ext",
  app_environment$gm_initial_tool(NULL)=="ext")
message("PASS: initial HTTP titles and selected panels match cap, comp and EXT deep links.")

stopifnot(cap_time_et("2026-10-23 22:55:17")=="2026-10-23 18:55:17 ET",
  cap_time_et("2026-12-23 22:55:17")=="2026-12-23 17:55:17 ET")
brand <- cap_team_brand(app_environment$players,"JAX")
stopifnot(grepl("Jaguars",brand$name),grepl("jac|jax",brand$logo))
message("PASS: team branding follows ADL franchise and timestamps convert to Eastern Time across DST.")

