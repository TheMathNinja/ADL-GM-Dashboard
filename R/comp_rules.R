## This function gets the compensatory draft picks for the next season
## What this function DOESN'T DO: It doesn't see draft order so therefore it can't:
## (1) Order ties in comp pick order due to identical salaries, or 
## (2) Name teams who get picks based on draft order

library(ffscrapr)
library(dplyr)
library(glue)

# ----------------------------
# SALARY THRESHOLDS
# ----------------------------

build_salary_thresholds <- function(season, verbose = TRUE) {
  
  # ---- SD minimum bid base inputs (in $M) ----
  sd_min_base_m <- c(
    `2020` = 1.32,
    `2021` = 1.22,
    `2022` = 1.39,
    `2023` = 1.50,
    `2024` = 1.70,
    `2025` = 1.86,
    `2026` = 2.01
  )
  
  # ---- Resolve connection from global mfl_conns (season 2025 -> "ADL25") ----
  conn_name <- paste0("ADL", substr(season, 3, 4))
  # ---- Pull salaries from rosters (ADL-wide) ----
  rosters <- comp_inputs$rosters
  
  rosters_na_salary <- rosters %>% dplyr::filter(is.na(salary))
  
  salaries <- rosters %>% dplyr::pull(salary)
  
  n_players_total <- length(salaries)
  n_salary_na     <- sum(is.na(salaries))
  n_salary_non_na <- sum(!is.na(salaries))
  
  salaries_non_na <- salaries[!is.na(salaries)]
  
  if (length(salaries_non_na) == 0) {
    stop("All salaries are NA; cannot compute thresholds.")
  }
  
  # ---- SD min bid rounding rule + $100k (0.1M) above ----
  if (!as.character(season) %in% names(sd_min_base_m)) {
    stop(sprintf("No SD min base found for season %s in sd_min_base_m.", season))
  }
  
  sd_base_m       <- unname(sd_min_base_m[as.character(season)])
  sd_min_bid_m    <- ceiling(sd_base_m * 10) / 10     # round UP to nearest tenth
  sd_plus_100k_m  <- sd_min_bid_m + 0.1
  
  # ---- Percentile table definition ----
  pct_vec <- c(95, 90, 85, 80, 75, 70, 65, 60, 50, 0)
  
  # Excel-like: ROUNDDOWN(((100-p)/100)*COUNT(...),0)
  players_above <- floor(((100 - pct_vec) / 100) * n_salary_non_na)
  
  # Excel-like: LARGE(range, k) where k = Players Above
  salaries_sorted_desc <- sort(salaries_non_na, decreasing = TRUE)
  
  kth_salary <- purrr::map_dbl(players_above, function(k) {
    k_safe <- max(1, min(k, length(salaries_sorted_desc)))
    salaries_sorted_desc[[k_safe]]
  })
  
  note <- dplyr::case_when(
    pct_vec == 90 ~ "3rd Round Cutoff",
    pct_vec == 80 ~ "4th Round Cutoff",
    pct_vec == 65 ~ "5th Round Cutoff",
    TRUE ~ ""
  )
  
  thresholds_tbl <- tibble::tibble(
    `ADL Percentile` = pct_vec,
    `Players Above`  = players_above,
    Salary           = sprintf("$%.2f", kth_salary),
    Note             = note
  )
  
  p65_salary_m <- kth_salary[pct_vec == 65]
  cfa_cutoff_m <- max(p65_salary_m, sd_plus_100k_m)
  
  if (isTRUE(verbose)) {
    cat(
      sprintf("\nSeason: %s  (conn: %s)\n", season, conn_name),
      sprintf("Players total: %d | Salary non-NA: %d | Salary NA: %d\n", n_players_total, n_salary_non_na, n_salary_na),
      sprintf("65th-percentile salary (rank-based): $%.2fM\n", p65_salary_m),
      sprintf("SD min bid base: $%.2fM  -> rounded up to $%.1fM\n", sd_base_m, sd_min_bid_m),
      sprintf("SD + $100k: $%.1fM\n", sd_plus_100k_m),
      sprintf("CFA cutoff (max of 65th and SD+100k): $%.2fM\n\n", cfa_cutoff_m),
      sep = ""
    )
    print(thresholds_tbl)
  }
  
  meta <- list(
    season = season,
    conn_name = conn_name,
    n_players_total = n_players_total,
    n_salary_non_na = n_salary_non_na,
    n_salary_na = n_salary_na,
    p65_salary_m = p65_salary_m,
    sd_base_m = sd_base_m,              # <--- NEW
    sd_min_bid_m = sd_min_bid_m,
    sd_plus_100k_m = sd_plus_100k_m,
    cfa_cutoff_m = cfa_cutoff_m
  )
  
  invisible(list(
    thresholds = thresholds_tbl,
    meta = meta,
    rosters_na_salary = rosters_na_salary
  ))
}



# ----------------------------
# CFA EVENTS (GAINED / LOST / RE-SIGNED)
# + trade logic + de-dupe gained + NEW combined summary printout
# ----------------------------

source("R/adl_calendar.R")

adl_comp_ufa_window <- function(season) {
  list(start = adl_ufa_start(season),
       end = as.POSIXct(sprintf("%d-07-01 00:00:00", season), tz = "America/New_York"))
}
adl_comp_auction_in_window <- function(timestamp, window) {
  time <- as.POSIXct(timestamp)
  !is.na(time) & time >= window$start & time < window$end
}

adl_comp_trade_after_auction_day <- function(trade_date, auction_date) {
  !is.na(trade_date) & !is.na(auction_date) & as.Date(trade_date) > as.Date(auction_date)
}

build_cfa_events <- function(season, minimum_salary_m = NULL) {
  
  library(dplyr)
  library(stringr)
  library(tidyr)
  
  # ---- connections ----
  conn      <- get_adl_conn(season)       # your existing helper
  conn_prev <- get_adl_conn(season - 1)
  
  # ---- salary thresholds (ADL-wide) ----
  # We do NOT print here; we print one unified block at the end.
  thr <- build_salary_thresholds(season, verbose = FALSE)
  
  cutoff_m <- thr$meta$cfa_cutoff_m
  ufa_window <- adl_comp_ufa_window(season)
  if (!is.null(minimum_salary_m)) cutoff_m <- minimum_salary_m
  
  thr_tbl <- thr$thresholds
  p90_m <- as.numeric(gsub("[$]", "", thr_tbl$Salary[thr_tbl$`ADL Percentile` == 90]))
  p80_m <- as.numeric(gsub("[$]", "", thr_tbl$Salary[thr_tbl$`ADL Percentile` == 80]))
  
  # ---- prior-year roster owners (per conference) ----
  prior_owner <- comp_inputs$prior_rosters %>%
    dplyr::transmute(
      player_id,
      prior_franchise_id   = franchise_id,
      prior_franchise_name = franchise_name,
      conference           = adl_conference_from_franchise(franchise_id)
    ) %>%
    dplyr::filter(!is.na(conference)) %>%
    dplyr::distinct(player_id, conference, .keep_all = TRUE)
  
  # ============================================================
  # UFA auction wins: third Monday in June at noon until July 1 (exclusive).
  # ============================================================
  early_ufa_all <- comp_inputs$transactions %>%
    dplyr::mutate(
      date_et    = adl_txn_date_et(timestamp),
      conference = adl_conference_from_franchise(franchise_id),
      win_bid    = bid_amount
    ) %>%
    dplyr::filter(
      !is.na(conference),
      type == "AUCTION_WON",
      adl_comp_auction_in_window(timestamp, ufa_window)
    ) %>%
    dplyr::transmute(conference, player_id, date_et, win_bid) %>%
    dplyr::arrange(conference, player_id, date_et, dplyr::desc(win_bid)) %>%
    dplyr::group_by(conference, player_id) %>%
    dplyr::slice(1) %>%
    dplyr::ungroup()
  
  early_counts <- early_ufa_all %>% dplyr::count(conference, name = "n_early_ufas")
  n_early_nfc <- early_counts$n_early_ufas[early_counts$conference == "NFC"]
  n_early_afc <- early_counts$n_early_ufas[early_counts$conference == "AFC"]
  n_early_nfc <- ifelse(length(n_early_nfc) == 0, 0L, n_early_nfc)
  n_early_afc <- ifelse(length(n_early_afc) == 0, 0L, n_early_afc)
  
  # ============================================================
  # UFA AUCTION WINS that qualify as CFA (bid >= cutoff)
  # ============================================================
  tx <- comp_inputs$transactions %>%
    dplyr::mutate(
      date_et    = adl_txn_date_et(timestamp),
      conference = adl_conference_from_franchise(franchise_id),
      win_bid    = bid_amount
    ) %>%
    dplyr::filter(
      !is.na(conference),
      type == "AUCTION_WON",
      adl_comp_auction_in_window(timestamp, ufa_window),
      !is.na(win_bid),
      win_bid >= cutoff_m
    ) %>%
    dplyr::transmute(
      franchise_id,
      franchise_name,
      player_id,
      player_name,
      win_bid,
      date       = date_et,
      acquired   = "auction",
      conference
    ) %>%
    dplyr::arrange(conference, player_id, dplyr::desc(win_bid), date) %>%
    dplyr::group_by(conference, player_id) %>%
    dplyr::slice(1) %>%
    dplyr::ungroup()
  
  # ---- Join prior owner by player_id + conference ----
  tx_w_prior <- tx %>%
    dplyr::left_join(prior_owner, by = c("player_id", "conference"))
  
  # ---- Classify: LOST/GAINED/RE-SIGNED within each conference copy ----
  cfa_base <- tx_w_prior %>%
    dplyr::mutate(
      cfa_event = dplyr::case_when(
        is.na(prior_franchise_id) ~ "NOT_CFA",
        prior_franchise_id == franchise_id ~ "RE-SIGNED",
        TRUE ~ "GAINED"
      ),
      comp_round = adl_comp_round_from_salary(win_bid, p90_m, p80_m, cutoff_m)
    ) %>%
    dplyr::filter(cfa_event != "NOT_CFA") %>%
    dplyr::mutate(
      lost_franchise_id   = prior_franchise_id,
      lost_franchise_name = prior_franchise_name
    )
  
  cfa_gained <- cfa_base %>%
    dplyr::transmute(
      franchise_id,
      franchise_name,
      player_id,
      player_name,
      win_bid,
      date,
      acquired,     # after date
      cfa_event,
      comp_round,
      conference
    )
  
  cfa_lost <- cfa_base %>%
    dplyr::filter(cfa_event == "GAINED") %>%   # RE-SIGNED produces no LOST row
    dplyr::transmute(
      franchise_id   = lost_franchise_id,
      franchise_name = lost_franchise_name,
      player_id,
      player_name,
      win_bid,
      date,
      acquired,      # still "auction"
      cfa_event      = "LOST",
      comp_round,
      conference
    )
  
  # ============================================================
  # TRADE acquisitions (type_desc contains "traded_for")
  # Only add extra GAINED rows, and ONLY for TRUE CFAs (auction GAINED, not RE-SIGNED).
  # ============================================================
  cfa_winbid_lookup <- cfa_gained %>%
    dplyr::filter(as.character(cfa_event) == "GAINED") %>%
    dplyr::select(player_id, conference, win_bid, comp_round, auction_date = date) %>%
    dplyr::distinct(player_id, conference, .keep_all = TRUE)
  
  trades_for <- comp_inputs$transactions %>%
    dplyr::mutate(
      date_et    = adl_txn_date_et(timestamp),
      conference = adl_conference_from_franchise(franchise_id)
    ) %>%
    dplyr::filter(
      !is.na(conference),
      stringr::str_detect(tolower(type_desc), "traded_for")
    ) %>%
    dplyr::transmute(
      franchise_id,
      franchise_name,
      player_id,
      player_name,
      date       = date_et,
      acquired   = "trade",
      conference
    ) %>%
    dplyr::distinct()
  
  trade_gained_rows <- trades_for %>%
    dplyr::inner_join(cfa_winbid_lookup, by = c("player_id", "conference")) %>%
    # Compare Eastern calendar days; trades have no July cutoff.
    dplyr::filter(adl_comp_trade_after_auction_day(date, auction_date)) %>%
    dplyr::mutate(cfa_event = "GAINED") %>%
    dplyr::transmute(
      franchise_id,
      franchise_name,
      player_id,
      player_name,
      win_bid,
      date,
      acquired,     # "trade"
      cfa_event,
      comp_round,
      conference
    )
  
  # ============================================================
  # Combine + de-dupe: same team cannot be GAINED twice for same player
  # Keep earliest date for (conference, franchise_id, player_id) where cfa_event == GAINED
  # ============================================================
  status_levels <- c("LOST", "GAINED", "RE-SIGNED")
  
  cfa_events_all <- dplyr::bind_rows(
    cfa_lost,
    cfa_gained,
    trade_gained_rows
  ) %>%
    dplyr::arrange(conference, franchise_id, player_id, date) %>%
    dplyr::group_by(conference, franchise_id, player_id) %>%
    dplyr::filter(!(as.character(cfa_event) == "GAINED" & dplyr::row_number() > 1)) %>%
    dplyr::ungroup() %>%
    dplyr::mutate(
      cfa_event = factor(cfa_event, levels = status_levels, ordered = TRUE),
      franchise_num = suppressWarnings(as.integer(franchise_id))
    ) %>%
    dplyr::arrange(franchise_num, cfa_event, dplyr::desc(win_bid), player_name) %>%
    dplyr::select(-franchise_num)
  
  # ============================================================
  # Summary counts for printout:
  # - Salary Err = salary NA OR salary == 0
  # - Print culprits (player_name, conference, salary)
  # - CFA counts = LOST only (trade-safe)
  # - Round breakdowns = LOST only, by comp_round
  # ============================================================
  
  # Salary Err: NA + zero (and list culprits)
  rosters_now <- comp_inputs$rosters %>%
    dplyr::mutate(conference = adl_conference_from_franchise(franchise_id))
  
  salary_err_df <- rosters_now %>%
    dplyr::filter(is.na(salary) | salary == 0) %>%
    dplyr::transmute(
      player_name,
      conference,
      salary
    ) %>%
    dplyr::arrange(conference, salary, player_name)
  
  salary_err_total <- nrow(salary_err_df)
  
  # CFA counts (LOST only)
  lost_counts <- cfa_events_all %>%
    dplyr::filter(as.character(cfa_event) == "LOST") %>%
    dplyr::count(conference, name = "n_cfas_lost")
  
  n_cfa_nfc <- lost_counts$n_cfas_lost[lost_counts$conference == "NFC"]
  n_cfa_afc <- lost_counts$n_cfas_lost[lost_counts$conference == "AFC"]
  n_cfa_nfc <- ifelse(length(n_cfa_nfc) == 0, 0L, n_cfa_nfc)
  n_cfa_afc <- ifelse(length(n_cfa_afc) == 0, 0L, n_cfa_afc)
  
  # Round breakdown (LOST only)
  cfa_round_breakdown <- cfa_events_all %>%
    dplyr::filter(as.character(cfa_event) == "LOST") %>%
    dplyr::mutate(comp_round = as.integer(comp_round)) %>%
    dplyr::count(conference, comp_round, name = "n") %>%
    tidyr::pivot_wider(
      names_from   = comp_round,
      values_from  = n,
      names_prefix = "rd_",
      values_fill  = 0
    )
  
  get_rd <- function(df, conf, rd) {
    col <- paste0("rd_", rd)
    if (!col %in% names(df)) return(0L)
    val <- df[[col]][df$conference == conf]
    ifelse(length(val) == 0, 0L, as.integer(val))
  }
  
  nfc_3 <- get_rd(cfa_round_breakdown, "NFC", 3)
  nfc_4 <- get_rd(cfa_round_breakdown, "NFC", 4)
  nfc_5 <- get_rd(cfa_round_breakdown, "NFC", 5)
  
  afc_3 <- get_rd(cfa_round_breakdown, "AFC", 3)
  afc_4 <- get_rd(cfa_round_breakdown, "AFC", 4)
  afc_5 <- get_rd(cfa_round_breakdown, "AFC", 5)
  
  # ============================================================
  # Unified printout (NO blank line before cutoff line)
  # ============================================================
  cat(
    sprintf("\nADL Season: %d\n", season),
    sprintf("Rostered Players: %d | Salary Err: %d\n", thr$meta$n_players_total, salary_err_total),
    sprintf("NFC Early-Window UFA's: %d | NFC CFA's: %d (3rd: %d / 4th: %d / 5th: %d)\n",
            n_early_nfc, n_cfa_nfc, nfc_3, nfc_4, nfc_5),
    sprintf("AFC Early-Window UFA's: %d | AFC CFA's: %d (3rd: %d / 4th: %d / 5th: %d)\n",
            n_early_afc, n_cfa_afc, afc_3, afc_4, afc_5),
    sprintf("65th-percentile salary: $%.2fM \n", thr$meta$p65_salary_m),
    sprintf("SD min: $%.2fM  -> SD min bid: $%.1fM -> + $100k: $%.1fM\n",
            thr$meta$sd_base_m, thr$meta$sd_min_bid_m, thr$meta$sd_plus_100k_m),
    sprintf("CFA cutoff (max of 65th and SD+100k): $%.2fM\n", thr$meta$cfa_cutoff_m),
    sep = ""
  )
  
  # Print salary error culprits (if any)
  if (salary_err_total > 0) {
    cat("\nSalary Err culprits (salary is NA or 0):\n")
    print(salary_err_df)
  }
  
  cat("\n")
  print(thr_tbl)
  
  cfa_events_all
}




######NOW BUILD CFA CANCELLATION FUNCITON###########

cancel_cfa_events <- function(cfa_events) {
  stopifnot(is.data.frame(cfa_events))
  
  # Expecting at least these columns from build_cfa_events():
  # franchise_id, franchise_name, conference, cfa_event (GAINED/LOST/RE-SIGNED),
  # player_id, player_name, win_bid, comp_round
  req <- c(
    "franchise_id","franchise_name","conference","cfa_event",
    "player_id","player_name","win_bid","comp_round"
  )
  missing <- setdiff(req, names(cfa_events))
  if (length(missing) > 0) {
    stop("cfa_events is missing required columns: ", paste(missing, collapse = ", "))
  }
  if (!nrow(cfa_events)) {
    return(list(
      cancels = tibble::tibble(franchise_id=character(), franchise_name=character(), conference=character(),
        gained_player_id=character(), gained_player_name=character(), gained_win_bid=numeric(), gained_round=integer(),
        lost_player_id=character(), lost_player_name=character(), lost_win_bid=numeric(), lost_round=integer()),
      remaining_lost = cfa_events,
      team_net = tibble::tibble(franchise_id=character(), franchise_name=character(), conference=character(),
        net_3rd=integer(), net_4th=integer(), net_5th=integer(), net_cfas_lost=integer(),
        max_comp_picks=integer(), bonus_sal_gained=numeric(), n_lost=integer(), n_gained=integer(),
        salary_lost_total=numeric(), salary_gained_total=numeric())))
  }
  
  library(dplyr)
  library(purrr)
  
  # --- helper: pick which LOST row to cancel given a gained round ---
  pick_cancel_idx <- function(lost_df, gained_round) {
    if (nrow(lost_df) == 0) return(NA_integer_)
    
    # 1) same round: cancel highest salary in that round
    same <- lost_df %>% filter(comp_round == gained_round)
    if (nrow(same) > 0) {
      return(which.max(ifelse(is.na(lost_df$win_bid), -Inf, lost_df$win_bid) * (lost_df$comp_round == gained_round)))
    }
    
    # 2) later rounds (numerically larger): cancel the next highest salary among later rounds
    later <- lost_df %>% filter(comp_round > gained_round)
    if (nrow(later) > 0) {
      idx_sub <- which(lost_df$comp_round > gained_round)
      wb <- lost_df$win_bid[idx_sub]
      wb[is.na(wb)] <- -Inf
      return(idx_sub[which.max(wb)])
    }
    
    # 3) earlier rounds (numerically smaller): cancel from earlier rounds starting at LOWEST salary
    earlier <- lost_df %>% filter(comp_round < gained_round)
    if (nrow(earlier) > 0) {
      idx_sub <- which(lost_df$comp_round < gained_round)
      wb <- lost_df$win_bid[idx_sub]
      wb[is.na(wb)] <- Inf
      return(idx_sub[which.min(wb)])
    }
    
    NA_integer_
  }
  
  # --- run cancellation for ONE team+conference slice ---
  cancel_one_team <- function(df_team) {
    meta <- df_team %>% slice(1) %>% select(franchise_id, franchise_name, conference)
    
    lost <- df_team %>%
      filter(cfa_event == "LOST", !is.na(comp_round)) %>%
      mutate(.lost_row_id = row_number()) %>%
      arrange(comp_round, desc(win_bid), player_id)
    
    gained <- df_team %>%
      filter(cfa_event == "GAINED", !is.na(comp_round)) %>%
      arrange(comp_round, desc(win_bid), player_id)
    
    if (nrow(gained) == 0 || nrow(lost) == 0) {
      cancels <- tibble(
        franchise_id = meta$franchise_id,
        franchise_name = meta$franchise_name,
        conference = meta$conference,
        gained_player_id = character(),
        gained_player_name = character(),
        gained_win_bid = numeric(),
        gained_round = integer(),
        lost_player_id = character(),
        lost_player_name = character(),
        lost_win_bid = numeric(),
        lost_round = integer()
      )
      
      remaining_lost <- lost %>% select(-.lost_row_id)
      return(list(cancels = cancels, remaining_lost = remaining_lost))
    }
    
    cancels_list <- vector("list", nrow(gained))
    
    for (i in seq_len(nrow(gained))) {
      g <- gained[i, ]
      
      if (nrow(lost) == 0) break
      
      j <- pick_cancel_idx(lost, g$comp_round)
      if (is.na(j)) next
      
      l <- lost[j, ]
      
      cancels_list[[i]] <- tibble(
        franchise_id = meta$franchise_id,
        franchise_name = meta$franchise_name,
        conference = meta$conference,
        gained_player_id = as.character(g$player_id),
        gained_player_name = as.character(g$player_name),
        gained_win_bid = as.numeric(g$win_bid),
        gained_round = as.integer(g$comp_round),
        lost_player_id = as.character(l$player_id),
        lost_player_name = as.character(l$player_name),
        lost_win_bid = as.numeric(l$win_bid),
        lost_round = as.integer(l$comp_round)
      )
      
      lost <- lost[-j, , drop = FALSE]
    }
    
    cancels <- bind_rows(cancels_list)
    remaining_lost <- lost %>% select(-.lost_row_id)
    
    list(cancels = cancels, remaining_lost = remaining_lost)
  }
  
  # --- split by team slice (conference included to keep AFC/NFC copies independent) ---
  team_slices <- split(
    cfa_events,
    list(cfa_events$franchise_id, cfa_events$conference),
    drop = TRUE
  )
  
  per_team <- purrr::map(team_slices, cancel_one_team)
  
  cancels_all <- purrr::map_dfr(per_team, "cancels")
  remaining_lost_all <- purrr::map_dfr(per_team, "remaining_lost")
  
  # --- TEAM NET SUMMARY (UPDATED: net_3rd/4th/5th = LOST - GAINED by round; NOT cancellation-based) ---
  team_net <- cfa_events %>%
    filter(cfa_event %in% c("LOST","GAINED")) %>%
    mutate(comp_round = as.integer(comp_round)) %>%
    group_by(franchise_id, franchise_name, conference) %>%
    summarise(
      # requested net-by-round: LOST - GAINED for each round level
      net_3rd = sum(cfa_event == "LOST"  & comp_round == 3L, na.rm = TRUE) -
        sum(cfa_event == "GAINED" & comp_round == 3L, na.rm = TRUE),
      net_4th = sum(cfa_event == "LOST"  & comp_round == 4L, na.rm = TRUE) -
        sum(cfa_event == "GAINED" & comp_round == 4L, na.rm = TRUE),
      net_5th = sum(cfa_event == "LOST"  & comp_round == 5L, na.rm = TRUE) -
        sum(cfa_event == "GAINED" & comp_round == 5L, na.rm = TRUE),
      
      n_lost   = sum(cfa_event == "LOST", na.rm = TRUE),
      n_gained = sum(cfa_event == "GAINED", na.rm = TRUE),
      salary_lost_total   = sum(ifelse(cfa_event == "LOST",   win_bid, 0), na.rm = TRUE),
      salary_gained_total = sum(ifelse(cfa_event == "GAINED", win_bid, 0), na.rm = TRUE),
      .groups = "drop"
    ) %>%
    mutate(
      net_cfas_lost  = n_lost - n_gained,
      max_comp_picks = pmin(pmax(net_cfas_lost, 0), 4),
      bonus_sal_gained = ifelse(net_cfas_lost == 0, salary_lost_total - salary_gained_total, NA_real_)
    ) %>%
    # column order you asked for
    select(
      franchise_id, franchise_name, conference,
      net_3rd, net_4th, net_5th,
      net_cfas_lost, max_comp_picks, bonus_sal_gained,
      n_lost, n_gained, salary_lost_total, salary_gained_total
    ) %>%
    arrange(as.integer(franchise_id), conference)
  
  # Order cancels / remaining lost by franchise_id (conference secondary)
  cancels_all <- cancels_all %>%
    mutate(franchise_id_int = suppressWarnings(as.integer(franchise_id))) %>%
    arrange(franchise_id_int, conference, gained_round, desc(gained_win_bid)) %>%
    select(-franchise_id_int)
  
  remaining_lost_all <- remaining_lost_all %>%
    mutate(franchise_id_int = suppressWarnings(as.integer(franchise_id))) %>%
    arrange(franchise_id_int, conference, comp_round, desc(win_bid)) %>%
    select(-franchise_id_int)
  
  list(
    cancels = cancels_all,
    remaining_lost = remaining_lost_all,
    team_net = team_net
  )
}


#############################################
#### FINAL STEP: BUILD COMP PICK TABLE#######
#############################################

build_comp_pick_table <- function(cancel_res, conference = c("AFC","NFC")) {
  conference <- match.arg(conference)
  
  stopifnot(is.list(cancel_res))
  stopifnot(all(c("remaining_lost","team_net") %in% names(cancel_res)))
  stopifnot(is.data.frame(cancel_res$remaining_lost))
  stopifnot(is.data.frame(cancel_res$team_net))
  
  library(dplyr)
  library(tidyr)
  
  remaining_lost <- cancel_res$remaining_lost
  team_net       <- cancel_res$team_net
  
  # ---- sanity checks ----
  req_rl <- c("franchise_id","franchise_name","conference","player_id","player_name","win_bid","comp_round")
  miss_rl <- setdiff(req_rl, names(remaining_lost))
  if (length(miss_rl) > 0) stop("cancel_res$remaining_lost missing: ", paste(miss_rl, collapse=", "))
  
  # NOTE: we now require net_cfas_lost for correct bonus eligibility
  req_tn <- c("franchise_id","franchise_name","conference","max_comp_picks","bonus_sal_gained","net_cfas_lost")
  miss_tn <- setdiff(req_tn, names(team_net))
  if (length(miss_tn) > 0) stop("cancel_res$team_net missing: ", paste(miss_tn, collapse=", "))
  
  # ---- filter to conference ----
  rl_conf <- remaining_lost %>%
    mutate(comp_round = as.integer(comp_round)) %>%
    filter(conference == !!conference, !is.na(comp_round), comp_round %in% c(3L,4L,5L))
  
  tn_conf <- team_net %>%
    filter(conference == !!conference) %>%
    mutate(
      franchise_id_chr = as.character(franchise_id),
      max_comp_picks   = as.integer(max_comp_picks),
      net_cfas_lost    = as.integer(net_cfas_lost)
    ) %>%
    select(franchise_id_chr, franchise_name, conference, max_comp_picks, net_cfas_lost, bonus_sal_gained)
  
  # ---- attach max_comp_picks onto remaining_lost ----
  rl_conf2 <- rl_conf %>%
    mutate(franchise_id_chr = as.character(franchise_id)) %>%
    left_join(tn_conf, by = c("franchise_id_chr","conference"), suffix = c("", "_tn")) %>%
    mutate(
      max_comp_picks = coalesce(max_comp_picks, 0L),
      
      # Tiering for final ordering / pick assignment
      pick_tier = 1L,                 # 1 = NET (real comp picks from net CFAs)
      pick_source = "NET",
      
      # ordering for NET picks: round first (3 before 4 before 5), then salary desc
      order_round  = comp_round,
      order_salary = as.numeric(win_bid)
    )
  
  # ---- TEAM TRIM: keep up to max_comp_picks per team ----
  # (avoid slice_head(n=...) because n must be constant)
  team_split <- rl_conf2 %>%
    arrange(order_round, desc(order_salary), player_name, player_id) %>%
    group_by(franchise_id_chr) %>%
    group_split(.keep = TRUE)
  
  team_kept_list <- vector("list", length(team_split))
  team_trim_list <- vector("list", length(team_split))
  
  for (i in seq_along(team_split)) {
    df_team <- team_split[[i]]
    keep_n  <- df_team$max_comp_picks[1]
    keep_n  <- max(0L, min(keep_n, nrow(df_team)))
    
    team_kept_list[[i]] <- if (keep_n > 0) df_team[seq_len(keep_n), , drop = FALSE] else df_team[0, , drop = FALSE]
    team_trim_list[[i]] <- if (keep_n < nrow(df_team)) df_team[(keep_n + 1L):nrow(df_team), , drop = FALSE] else df_team[0, , drop = FALSE]
  }
  
  team_kept <- bind_rows(rl_conf2[0, ], bind_rows(team_kept_list))
  team_trim <- bind_rows(rl_conf2[0, ], bind_rows(team_trim_list))
  
  # ---- CONFERENCE TRIM (NET picks only): keep top 16 by round then salary ----
  conf_ranked_net <- team_kept %>%
    arrange(order_round, desc(order_salary), franchise_id_chr, player_name, player_id) %>%
    mutate(conf_rank = row_number())
  
  conf_kept_net <- conf_ranked_net %>% filter(conf_rank <= 16)
  conf_trim_net <- conf_ranked_net %>% filter(conf_rank > 16)
  
  # ---- If fewer than 16, add BONUS picks at END of 5th round (AFTER all NET picks) ----
  n_have <- nrow(conf_kept_net)
  n_need <- 16 - n_have
  
  bonus_rows <- tibble()
  if (n_need > 0) {
    bonus_rows <- tn_conf %>%
      # BYLAW: only teams with 0 net CFAs and POSITIVE net salary lost
      filter(net_cfas_lost == 0L, !is.na(bonus_sal_gained), bonus_sal_gained > 0) %>%
      arrange(desc(bonus_sal_gained), franchise_id_chr) %>%
      mutate(
        comp_round   = 5L,
        player_id    = NA_character_,
        player_name  = "BONUS PICK (net salary lost)",
        win_bid      = as.numeric(bonus_sal_gained),
        
        pick_tier    = 2L,          # 2 = BONUS (always after NET in the 5th)
        pick_source  = "BONUS",
        
        order_round  = 5L,
        order_salary = as.numeric(bonus_sal_gained)
      ) %>%
      transmute(
        franchise_id   = franchise_id_chr,
        franchise_name,
        conference,
        player_id,
        player_name,
        win_bid,
        comp_round,
        pick_tier,
        pick_source,
        order_round,
        order_salary
      ) %>%
      slice_head(n = n_need)
  }
  
  conf_all <- bind_rows(
    conf_kept_net %>%
      transmute(
        franchise_id   = franchise_id_chr,
        franchise_name,
        conference,
        player_id,
        player_name,
        win_bid,
        comp_round,
        pick_tier,
        pick_source,
        order_round,
        order_salary
      ),
    bonus_rows
  )
  
  # ---- If STILL fewer than 16, fill with draft-order placeholders at END of 5th ----
  n_have2 <- nrow(conf_all)
  n_need2 <- 16 - n_have2
  
  filler_rows <- tibble()
  if (n_need2 > 0) {
    filler_rows <- tibble(
      franchise_id   = NA_character_,
      franchise_name = paste0("Draft Order ", seq_len(n_need2)),
      conference     = conference,
      player_id      = NA_character_,
      player_name    = "FILLER PICK (draft order)",
      win_bid        = NA_real_,
      comp_round     = 5L,
      
      pick_tier      = 3L,     # 3 = FILLER (always last)
      pick_source    = "FILLER",
      
      order_round    = 5L,
      order_salary   = -Inf
    )
    
    conf_all <- bind_rows(conf_all, filler_rows)
  }
  
  # ---- Assign Pick numbers: start at 17 within each round ----
  # Ordering within each round:
  #   NET first (tier 1) by salary desc
  #   then BONUS (tier 2) by bonus salary desc
  #   then FILLER (tier 3)
  final_tbl <- conf_all %>%
    mutate(comp_round = as.integer(comp_round)) %>%
    group_by(comp_round) %>%
    arrange(
      pick_tier,
      desc(order_salary),
      franchise_name,
      player_name,
      .by_group = TRUE
    ) %>%
    mutate(
      pick_in_round = 16 + row_number(),
      # Tie marking should only compare within the *same tier* in the round
      is_tie = (!is.na(win_bid)) & (
        duplicated(paste0(pick_tier, "::", win_bid)) |
          duplicated(paste0(pick_tier, "::", win_bid), fromLast = TRUE)
      )
    ) %>%
    ungroup() %>%
    mutate(
      Pick = paste0(comp_round, ".", pick_in_round, ifelse(is_tie, "(t)", ""))
    ) %>%
    transmute(
      Pick,
      Team   = franchise_name,
      Player = nflreadr::clean_player_names(player_name),
      Salary = ifelse(
        is.na(win_bid),
        NA_character_,
        paste0("$", formatC(win_bid, format = "f", digits = 1), "m")
      )
    )
  
  # ---- PRINT TRIMS (conference-labeled) ----
  if (nrow(team_trim) > 0) {
    message("\n", conference, " TEAM TRIMS (players removed because a team exceeded its max_comp_picks, capped at 4):")
    print(
      team_trim %>%
        transmute(franchise_name, player_name, win_bid, comp_round) %>%
        arrange(comp_round, desc(win_bid), franchise_name, player_name)
    )
  } else {
    message("\n", conference, " TEAM TRIMS: none")
  }
  
  if (nrow(conf_trim_net) > 0) {
    message("\n", conference, " CONFERENCE TRIMS (players removed because NET picks exceeded 16 total comp picks):")
    print(
      conf_trim_net %>%
        transmute(franchise_name, player_name, win_bid, comp_round) %>%
        arrange(comp_round, desc(win_bid), franchise_name, player_name)
    )
  } else {
    message("\n", conference, " CONFERENCE TRIMS: none")
  }
  
  list(picks = conf_all, display = final_tbl, team_trim = team_trim, conference_trim = conf_trim_net)
}




