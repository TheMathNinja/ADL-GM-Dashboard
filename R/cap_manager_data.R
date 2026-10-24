cap_read_sheet <- function(path, season) {
  sheet <- as.data.frame(readxl::read_excel(path, sheet="Cap Rollover", col_names=FALSE,
                                         col_types="text", .name_repair="minimal"))
  numeric_cell <- function(row, col) suppressWarnings(as.numeric(gsub("[$,]", "", sheet[row,col])))
  headers <- as.character(sheet[1,])
  columns <- match(c("AVG", "FRAN CAP", "EFF SPACE", "FRAN ROLL"), headers)
  if (anyNA(columns) || nrow(sheet)<34) stop("Contract Admin Cap Rollover format is not recognized.")
  pricing <- readxl::read_excel(path, sheet="FT5YO $", range="L2:L4", col_names=FALSE)
  if (as.integer(pricing[[1]][1])!=season) stop("Contract Admin workbook is for another season.")
  league_cap <- as.numeric(pricing[[1]][3])
  if (!is.finite(league_cap) || league_cap<=0) stop("Missing ADL salary cap.")
  teams <- data.frame(franchise=as.character(sheet[3:34,1]), franchise_cap=NA_real_)
  finals <- matrix(NA_real_, nrow=32, ncol=17)
  for (i in seq_len(32)) {
    teams$franchise_cap[i] <- numeric_cell(i+2, columns[2])
    for (w in seq_len(17)) finals[i,w] <- numeric_cell(i+2, 1+12*w)
    cap_projection(finals[i,], teams$franchise_cap[i], league_cap, 0)
  }
  fields <- c("A","IR","S","TE","Yrs","Ill?","Paid","Vac$","RostSal","Adj","Corr","Final")
  ledger <- dplyr::bind_rows(lapply(seq_len(32),function(i) {
    dplyr::bind_rows(lapply(seq_len(17),function(w) {
      if(!is.finite(finals[i,w])) return(NULL)
      cols <- 2+(w-1)*12+0:11
      if(!identical(as.character(sheet[2,cols]),fields)) stop("Cap Rollover weekly columns changed.")
      row <- data.frame(franchise=teams$franchise[i],week=w)
      for(j in seq_along(fields)) row[[fields[j]]] <- if(fields[j]=="Ill?") {
        value <- as.character(sheet[i+2,cols[j]])
        if(is.na(value)) "" else value
      } else numeric_cell(i+2,cols[j])
      required <- setdiff(fields,c("Ill?","Corr"))
      if(anyNA(row[required])) stop("A recorded Cap Rollover week has missing ledger values.")
      total <- sum(as.numeric(row[1,c("Vac$","RostSal","Adj","Corr")]),na.rm=TRUE)
      if(abs(total-row$Final)>.011) stop("Weekly ledger components do not reconcile to Final.")
      row
    }))
  }))
  if (anyDuplicated(teams$franchise) || anyNA(teams$franchise_cap)) stop("Incomplete franchise caps.")
  list(teams=teams, finals=finals, league_cap=league_cap, ledger=ledger)
}

cap_mfl <- function(endpoint, season) {
  query <- list(TYPE=endpoint, L="60206", JSON="1")
  if (identical(endpoint,"injuries")) {
    query$W <- cap_injury_week(season)
    query$L <- NULL # League routing redirects this NFL-wide endpoint to an invalid host.
  }
  response <- httr::GET(paste0("https://api.myfantasyleague.com/",season,"/export"),
    query=query, httr::timeout(25),
    httr::user_agent("ADL-GM-Dashboard Salary Cap Manager"))
  httr::stop_for_status(response)
  value <- jsonlite::fromJSON(httr::content(response, as="text", encoding="UTF-8"), simplifyVector=FALSE)
  if (!is.null(value$error)) stop("MFL returned an error for ",endpoint)
  value
}

cap_injury_week <- function(season, now=Sys.time()) {
  path <- file.path("data",paste0("nfl_schedule_",season,".csv"))
  if (!file.exists(path)) stop("NFL schedule is needed to request the current injury report.")
  schedule <- utils::read.csv(path,stringsAsFactors=FALSE)
  kickoff <- as.POSIXct(schedule$kickoff_et,format="%Y-%m-%dT%H:%M:%SZ",tz="UTC")
  started <- schedule$week[!is.na(kickoff) & kickoff<=now]
  if (!length(started)) return(1L)
  as.integer(min(18,max(started)))
}

cap_fetch_data <- function(season, players, workbook=NULL) {
  if (is.null(workbook)) {
    workbook <- tempfile(fileext=".xlsx")
    on.exit(unlink(workbook), add=TRUE)
    response <- httr::GET(paste0("https://docs.google.com/spreadsheets/d/",
      "1Pyw8qVfiBlXNuX0lW0LdjRnBiijfbo2BXHfZMWwLLaw/export?format=xlsx"), httr::timeout(30))
    httr::stop_for_status(response)
    writeBin(httr::content(response, as="raw"), workbook)
  }
  sheet <- cap_read_sheet(workbook, season)
  franchises <- cap_mfl("league", season)$league$franchises$franchise
  roster_data <- cap_mfl("rosters", season)$rosters$franchise
  injuries <- cap_mfl("injuries", season)$injuries$injury
  adjustments <- cap_mfl("salaryAdjustments", season)$salaryAdjustments$salaryAdjustment
  # MFL franchise id, not player id alone, identifies each conference's copy.
  franchise_names <- setNames(vapply(franchises, function(x) x$abbrev, ""),
                              vapply(franchises, function(x) x$id, ""))
  injury_names <- setNames(vapply(injuries, function(x) x$status %||% "", ""),
                           vapply(injuries, function(x) x$id, ""))
  rows <- lapply(roster_data, function(fr) {
    code <- unname(franchise_names[fr$id])
    conference <- if (as.integer(fr$id)<=16) "NFC" else "AFC"
    dplyr::bind_rows(lapply(fr$player, function(p) {
      match_row <- players[players$conference==conference & players$player_id==p$id,,drop=FALSE]
      data.frame(franchise=code, conference=conference, player_id=p$id,
        player=if(nrow(match_row)) match_row$player[[1]] else paste("MFL player",p$id),
        prev_salary=as.numeric(p$salary), prev_years=as.numeric(p$contractYear),
        contract=p$contractInfo %||% "", roster_status=p$status,
        injury=if (p$id %in% names(injury_names)) unname(injury_names[p$id]) else "")
    }))
  })
  roster <- dplyr::bind_rows(rows)
  if (anyNA(roster$franchise) || !setequal(unique(roster$franchise), sheet$teams$franchise) ||
      anyDuplicated(roster[c("conference","player_id")])) stop("MFL roster coverage does not match Contract Admin.")
  sheet$teams$adjustment <- vapply(sheet$teams$franchise, function(code) {
    id <- names(franchise_names)[franchise_names==code]
    amounts <- vapply(Filter(function(x) x$franchise_id %in% id, adjustments),
                      function(x) as.numeric(x$amount), numeric(1))
    if (anyNA(amounts)) stop("Invalid salary adjustment.")
    sum(amounts)
  }, numeric(1))
  cash <- cap_cash_ledger(season,sheet$teams$franchise)
  sheet$teams$net_cash_received <- cash$net
  for (code in sheet$teams$franchise) cap_spending(roster[roster$franchise==code,],
    sheet$teams$adjustment[sheet$teams$franchise==code], cap_vet_min(season))
  free_agents <- tryCatch(cap_fetch_free_agents(season,roster),error=identity)
  future <- tryCatch(cap_future_inputs(workbook,season,roster,players,franchise_names),error=identity)
  list(free_agents=if(inherits(free_agents,"error")) NULL else free_agents,
       free_agents_error=if(inherits(free_agents,"error")) conditionMessage(free_agents) else NULL,
       next_season=if(inherits(future,"error")) NULL else future,
       next_season_error=if(inherits(future,"error")) conditionMessage(future) else NULL,
       season=season, refreshed_at=format(Sys.time(), "%Y-%m-%d %H:%M:%S", tz="UTC"),
       cash_source="SalAdj Curator Cash Trade rows",cash_trades=cash$trades,
       teams=sheet$teams, finals=sheet$finals, league_cap=sheet$league_cap, ledger=sheet$ledger, roster=roster)
}

cap_load_cache <- function(path="data/cap_manager.json", season) {
  if (!file.exists(path)) return(NULL)
  data <- jsonlite::fromJSON(path)
  if (!identical(as.integer(data$season), as.integer(season))) return(NULL)
  data$roster$player_id <- as.character(data$roster$player_id)
  if (!"net_cash_received" %in% names(data$teams)) data$teams$net_cash_received <- NA_real_
  data
}

cap_refresh_cash <- function(data, season) {
  # Cash accounting can refresh even when the unrelated MFL injury feed fails.
  if (is.null(data)) stop("No saved cap snapshot is available.")
  cash <- cap_cash_ledger(season,data$teams$franchise)
  net <- cash$net
  data$cash_trades <- cash$trades
  data$cash_source <- "SalAdj Curator Cash Trade rows"
  data$teams$net_cash_received <- net
  data$cash_refreshed_at <- format(Sys.time(),"%Y-%m-%d %H:%M:%S",tz="UTC")
  data
}


cap_future_inputs <- function(workbook, season, roster, players, franchise_names) {
  rules <- jsonlite::fromJSON("data/cap_projection_rules.json")
  if(rules$rookieGrowth$baseYear!=season) stop("Next-season projection rules need annual rollover.")
  # Published summary totals include penalties already recorded for next season.
  adjustments <- dplyr::bind_rows(lapply(c("NFC Sal Adj","AFC Sal Adj"),function(sheet) {
    x <- as.data.frame(readxl::read_excel(workbook,sheet=sheet,col_names=FALSE,
      col_types="text",.name_repair="minimal"))
    h <- as.character(x[1,]); amount <- match(paste(season+1,"ADJ"),h)
    if(is.na(amount) || h[amount-2]!="FRAN") stop("Next-year adjustment summary format changed.")
    data.frame(franchise=as.character(x[2:17,amount-2]),
      adjustment=suppressWarnings(as.numeric(x[2:17,amount])))
  }))
  if(nrow(adjustments)!=32 || anyNA(adjustments) || anyDuplicated(adjustments$franchise) ||
     !setequal(adjustments$franchise,unique(roster$franchise))) stop("Incomplete next-year salary adjustments.")
  # Reuse the dashboard's accrued-season and salary tests with current contracts.
  env <- new.env(parent=environment())
  sys.source("R/tag_eligibility.R",envir=env)
  tags <- env$build_next_season_tag_eligibility(roster,season,force_live=FALSE)
  roster <- dplyr::left_join(roster,tags[,c("conference","player_id","next_erfa_eligible","projected_accrued_seasons")],
    by=c("conference","player_id"))
  fifth <- players[,intersect(c("conference","player_id","fifth_year_option_salary","fifth_year_option","has_exercised_5yo"),names(players)),drop=FALSE]
  fifth$player_id <- as.character(fifth$player_id)
  roster <- dplyr::left_join(roster,fifth,by=c("conference","player_id"))
  if(!"fifth_year_option_salary" %in% names(roster)) roster$fifth_year_option_salary <- NA_real_
  if("fifth_year_option" %in% names(roster)) {
    actual <- suppressWarnings(as.numeric(roster$fifth_year_option))
    use <- is.finite(actual) & actual>0
    roster$fifth_year_option_salary[use] <- actual[use]
  }
  picks_raw <- cap_mfl("futureDraftPicks",season)$futureDraftPicks$franchise
  picks <- dplyr::bind_rows(lapply(picks_raw,function(f) dplyr::bind_rows(lapply(f$futureDraftPick,function(p) {
    data.frame(franchise=unname(franchise_names[f$id]),original=unname(franchise_names[p$originalPickFor]),
      original_id=p$originalPickFor,year=as.integer(p$year),round=as.integer(p$round))
  }))))
  picks <- picks[picks$year==season+1,,drop=FALSE]
  if(anyNA(picks) || anyDuplicated(picks[c("original_id","year","round")])) stop("Invalid future draft-pick ownership.")
  response <- httr::GET("https://themathninja.github.io/ADL-GM-Dashboard/playoff-picture/",httr::timeout(30))
  httr::stop_for_status(response)
  html <- httr::content(response,as="text",encoding="UTF-8")
  start <- regexpr("const draft=",html,fixed=TRUE)
  if(start<1) stop("Projected draft board unavailable.")
  tail <- substring(html,start+attr(start,"match.length"))
  end <- regexpr("};",tail,fixed=TRUE)
  if(end<1) stop("Projected draft board is not recognized.")
  board <- dplyr::bind_rows(jsonlite::fromJSON(substr(tail,1,end)))
  picks$slot <- as.numeric(board$pick[match(picks$original_id,board$franchise_id)])
  if(anyNA(picks$slot) || any(picks$slot<1 | picks$slot>16 | picks$round<1 | picks$round>6)) stop("Invalid projected draft slots.")
  list(year=season+1,roster=roster,adjustments=adjustments,picks=picks,
    rules=rules,tag_through_week=env$completed_week_from_metadata(),
    draft_source="Public Playoff Picture projected draft order; provisional slots, not a finalized draft order.",
    refreshed_at=format(Sys.time(),"%Y-%m-%d %H:%M:%S",tz="UTC"))
}

cap_cash_ledger <- function(season,franchises,rows=NULL) {
  if(is.null(rows)) {
    response <- httr::GET(paste0("https://raw.githubusercontent.com/TheMathNinja/ADL-Commissioner-Dashboard/main/data/SalAdjCurator_",season,".csv"),
      httr::timeout(30),httr::add_headers(`Cache-Control`="no-cache"))
    httr::stop_for_status(response)
    rows <- utils::read.csv(text=httr::content(response,as="text",encoding="UTF-8"),check.names=FALSE,stringsAsFactors=FALSE)
  }
  if(!all(c("FRAN","PLAYER","SALARY") %in% names(rows))) stop("SalAdj cash ledger columns are unavailable.")
  summary <- cap_summarize_cash_trade_net(rows)
  if(any(!summary$franchise %in% franchises)) stop("SalAdj cash ledger contains an unknown franchise.")
  net <- setNames(rep(0,length(franchises)),franchises)
  # SalAdj positive is cash given (cap charge); Cap Manager stores received cash.
  net[summary$franchise] <- -summary$net_given
  if(anyNA(net) || abs(sum(net))>.001) stop("The SalAdj cash ledger does not reconcile across all teams.")
  amount <- suppressWarnings(as.numeric(gsub("[$,]","",as.character(rows$SALARY))))
  keep <- toupper(trimws(as.character(rows$PLAYER)))=="CASH TRADE" & !is.na(amount) & nzchar(trimws(as.character(rows$FRAN)))
  cash <- rows[keep,,drop=FALSE]
  amounts <- amount[keep]
  dates <- if("DATE" %in% names(cash)) as.character(cash$DATE) else rep(NA_character_,nrow(cash))
  codes <- toupper(trimws(as.character(cash$FRAN)))
  conferences <- if("CONF" %in% names(cash)) as.character(cash$CONF) else rep("",nrow(cash))
  partner <- vapply(seq_len(nrow(cash)),function(i) {
    matches <- which(!is.na(dates) & dates==dates[i] & conferences==conferences[i] &
      codes!=codes[i] & abs(amounts+amounts[i])<.001)
    if(length(matches)==1) codes[matches] else NA_character_
  },character(1))
  stamp <- as.POSIXct(dates,format="%m/%d/%Y %H:%M:%S",tz="America/New_York")
  trades <- data.frame(franchise=codes,date=ifelse(is.na(stamp),NA_character_,format(stamp,"%m/%d")),
    partner=partner,amount=amounts,stringsAsFactors=FALSE)
  trades <- trades[order(stamp,seq_along(stamp),na.last=TRUE),,drop=FALSE]
  list(net=unname(net),trades=trades)
}

cap_cash_balances <- function(season,franchises,rows=NULL) cap_cash_ledger(season,franchises,rows)$net

cap_free_agent_pool <- function(availability,metadata,roster) {
  players <- dplyr::bind_rows(lapply(metadata$players$player,function(p)
    data.frame(player_id=p$id,player=trimws(paste(p$name,p$team,p$position)),position=p$position)))
  positions <- c("QB","RB","WR","TE","PK","PN","DT","DE","LB","CB","S")
  units <- availability$freeAgents$leagueUnit
  if(!setequal(vapply(units,function(u)u$unit,character(1)),c("CONFERENCE00","CONFERENCE01"))) stop("MFL conference free-agent pools unavailable.")
  pool <- dplyr::bind_rows(lapply(units,function(unit) {
    ids <- vapply(unit$player,function(p)p$id,character(1))
    matched <- match(ids,players$player_id)
    if(anyNA(matched)) stop("MFL free-agent player metadata is incomplete.")
    rows <- players[matched,,drop=FALSE]
    rows <- rows[rows$position %in% positions,,drop=FALSE]
    rows$conference <- if(unit$unit=="CONFERENCE00") "NFC" else "AFC"
    rows
  }))
  if(anyDuplicated(pool[c("conference","player_id")])) stop("MFL free-agent pool has duplicate players.")
  if(any(paste(pool$conference,pool$player_id) %in% paste(roster$conference,roster$player_id))) stop("A rostered player appears in MFL's free-agent pool.")
  pool[order(pool$conference,pool$player),c("conference","player_id","player"),drop=FALSE]
}

cap_fetch_free_agents <- function(season,roster) cap_free_agent_pool(cap_mfl("freeAgents",season),cap_mfl("players",season),roster)

