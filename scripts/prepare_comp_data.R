# Builds a portable snapshot; run after EXT data preparation.
source("R/roster_source.R")
library(dplyr)
library(tidyr)
library(purrr)
season <- get_current_season()
cache_dir <- Sys.getenv("ADL_COMP_CACHE_DIR", "data/comp_raw")
dir.create(cache_dir, recursive = TRUE, showWarnings = FALSE)
read_comp_source <- function(kind, year) {
  path <- file.path(cache_dir, paste0(kind, "_", year, ".rds"))
  if (Sys.getenv("ADL_COMP_OFFLINE") == "TRUE") {
    if (!file.exists(path)) stop("Missing compensatory source: ", path)
    return(readRDS(path))
  }
  conn <- connect_adl_mfl(year)
  value <- switch(kind, rosters = ffscrapr::ff_rosters(conn),
    transactions = ffscrapr::ff_transactions(conn), franchises = ffscrapr::ff_franchises(conn))
  if (!is.data.frame(value) || (kind != "transactions" && !nrow(value))) stop("Empty MFL response: ", kind)
  saveRDS(value, path)
  value
}
comp_inputs <- list(rosters = read_comp_source("rosters", season),
  prior_rosters = read_comp_source("rosters", season - 1L),
  transactions = read_comp_source("transactions", season))
franchises <- read_comp_source("franchises", season)
if (!"bid_amount" %in% names(comp_inputs$transactions)) {
  if (any(comp_inputs$transactions$type == "AUCTION_WON")) stop("Auction bids missing from MFL transactions")
  comp_inputs$transactions$bid_amount <- NA_real_
}
rules <- new.env(parent = environment())
sys.source("R/comp_rules.R", envir = rules)
rules$comp_inputs <- comp_inputs
rules$get_adl_conn <- function(year) year
rules$adl_conference_from_franchise <- function(id) {
  n <- suppressWarnings(as.integer(id))
  ifelse(n >= 1 & n <= 16, "NFC", ifelse(n >= 17 & n <= 32, "AFC", NA_character_))
}
rules$adl_txn_date_et <- function(x) as.Date(format(as.POSIXct(x), tz = "America/New_York", format = "%Y-%m-%d"))
rules$adl_comp_round_from_salary <- function(salary, p90, p80, cutoff) {
  case_when(salary >= p90 ~ 3L, salary >= p80 ~ 4L, salary >= cutoff ~ 5L, TRUE ~ NA_integer_)
}
thresholds <- rules$build_salary_thresholds(season, FALSE)
events <- rules$build_cfa_events(season)
below_threshold_events <- rules$build_cfa_events(season,
  minimum_salary_m = thresholds$meta$sd_plus_100k_m) %>%
  filter(win_bid < thresholds$meta$cfa_cutoff_m, cfa_event %in% c("LOST", "GAINED", "RE-SIGNED")) %>%
  mutate(comp_round = NA_integer_)
cancel <- rules$cancel_cfa_events(events)
conferences <- setNames(lapply(c("AFC", "NFC"), function(conf) rules$build_comp_pick_table(cancel, conf)), c("AFC", "NFC"))
teams <- franchises %>% mutate(franchise_id = as.character(franchise_id),
  conference = rules$adl_conference_from_franchise(franchise_id)) %>%
  filter(!is.na(conference)) %>% select(franchise_id, franchise_name, conference)
photos <- readr::read_csv("data/ext_candidates.csv", show_col_types = FALSE,
  col_types = cols(player_id = col_character())) %>%
  select(player_id, player_headshot, player_pos, player_team) %>% distinct(player_id, .keep_all = TRUE)
source_paths <- list.files(cache_dir, pattern = "rds$", full.names = TRUE)
transaction_labels <- comp_inputs$transactions %>%
  mutate(date = rules$adl_txn_date_et(timestamp),
    conference = rules$adl_conference_from_franchise(franchise_id)) %>%
  filter((type == "AUCTION_WON" & date >= as.Date(sprintf("%d-06-01", season)) &
    date < as.Date(sprintf("%d-07-01", season))) |
    stringr::str_detect(tolower(type_desc), "traded_for")) %>%
  transmute(franchise_id = as.character(franchise_id), player_id = as.character(player_id),
    conference, date, acquired = if_else(type == "AUCTION_WON", "auction", "trade"),
    win_bid = bid_amount, trade_partner = as.character(trade_partner)) %>% distinct()
snapshot <- list(season = season, award_year = season + 1L, built_at = format(Sys.time(), tz = "UTC", usetz = TRUE),
  source_at = format(min(file.info(source_paths)$mtime), tz = "UTC", usetz = TRUE),
  teams = teams, thresholds = thresholds, events = events, below_threshold_events = below_threshold_events,
  cancel = cancel, conferences = conferences, photos = photos, transaction_labels = transaction_labels)
saveRDS(snapshot, "data/comp_picks.rds")
message("Compensatory snapshot saved for ", nrow(teams), " teams; ", nrow(events), " events.")
