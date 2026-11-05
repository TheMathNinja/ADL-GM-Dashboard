library(dplyr)
source("R/ext_free_agents.R")
catalog <- tibble(player_id=c("1","2","3","4"), player_name=c("Zulu, A","Alpha, B","Beta, C","Defense"),
  team=c("NYJ","SEA","BUF","DAL"), pos=c("QB","WR","LB","Def"))
rosters <- tibble(conference=c("AFC","NFC"), player_id=c("1","2"))
fa <- build_free_agent_rosters(catalog, rosters, 2026)
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
cat("PASS: conference availability, ID exclusion, supported positions, blank/invalid salary, all contract lengths.\n")
