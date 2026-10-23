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
  if (anyDuplicated(teams$franchise) || anyNA(teams$franchise_cap)) stop("Incomplete franchise caps.")
  list(teams=teams, finals=finals, league_cap=league_cap)
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
  sheet$teams$net_cash_received <- vapply(sheet$teams$franchise, function(code) {
    id <- names(franchise_names)[franchise_names==code]
    entries <- Filter(function(x) x$franchise_id %in% id &&
      cap_is_cash_adjustment(x$description %||% ""), adjustments)
    -round_salary(sum(vapply(entries, function(x) as.numeric(x$amount), numeric(1))))
  }, numeric(1))
  for (code in sheet$teams$franchise) cap_spending(roster[roster$franchise==code,],
    sheet$teams$adjustment[sheet$teams$franchise==code], cap_vet_min(season))
  list(season=season, refreshed_at=format(Sys.time(), "%Y-%m-%d %H:%M:%S", tz="UTC"),
       teams=sheet$teams, finals=sheet$finals, league_cap=sheet$league_cap, roster=roster)
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
  franchises <- cap_mfl("league",season)$league$franchises$franchise
  adjustments <- cap_mfl("salaryAdjustments",season)$salaryAdjustments$salaryAdjustment
  ids <- setNames(vapply(franchises,function(f)f$id,""),vapply(franchises,function(f)f$abbrev,""))
  net <- vapply(data$teams$franchise,function(code) {
    if (!code %in% names(ids)) stop("Cash ledger franchise mismatch.")
    entries <- Filter(function(a)a$franchise_id==ids[[code]] && cap_is_cash_adjustment(a$description %||% ""),adjustments)
    -round_salary(sum(vapply(entries,function(a)as.numeric(a$amount),numeric(1))))
  },numeric(1))
  if (anyNA(net) || abs(sum(net))>.001) stop("The cash ledger does not reconcile across all teams.")
  data$teams$net_cash_received <- net
  data$cash_refreshed_at <- format(Sys.time(),"%Y-%m-%d %H:%M:%S",tz="UTC")
  data
}
