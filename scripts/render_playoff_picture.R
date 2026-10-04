# Render the GM suite from the same raw snapshot used by the forecasting model.
render_adl_playoff_page <- function(snapshot, season, week, dropdown, full_file, updated_at) {
  teams <- snapshot[order(snapshot$conference, snapshot$seed), ]
  postseason <- NULL
  if (week >= 12L) {
    source("scripts/postseason_draft.R", local=TRUE)
    postseason <- adl_build_postseason_draft(teams, season, week, ADL_weekly_history, getOption("adl.n_sims",3000L))
  }
  rosters <- read.csv("data/current_rosters.csv", stringsAsFactors = FALSE)
  abbr <- rosters$franchise[match(teams$franchise_name, rosters$franchise_name)]
  # Match prepare_ext_data.R::espn_team_logo_from_adl exactly.
  slug <- dplyr::recode(abbr, GBP="gb", JAC="jax", KCC="kc", LAR="lar",
                        LVR="lv", NEP="ne", NOS="no", SFO="sf", TBB="tb", WAS="wsh",
                        .default=tolower(abbr))
  stopifnot(!anyNA(slug), nrow(teams) == 32L)
  logo <- paste0("https://a.espncdn.com/i/teamlogos/nfl/500/", slug, ".png")
  off <- teams$offst_points / teams$through_week
  defense <- teams$defense_points / teams$through_week
  potential <- teams$pot_ppg
  rank_of <- function(values, i) {
    values <- round(values, 6)
    list(rank=as.integer(rank(-values, ties.method="min")[i]), tied=sum(values==values[i])>1L)
  }
  escape <- function(x) as.character(htmltools::htmlEscape(x, attribute=TRUE))
  pct <- function(x) paste0(round(x*100), "%")
  record_text <- function(w, l, t) if (t == 0) sprintf("%d-%d", w, l) else sprintf("%d-%d-%d", w, l, t)
  cutoff <- min(as.integer(teams$through_week), 12L)
  history <- ADL_weekly_history[ADL_weekly_history$season == season & ADL_weekly_history$week <= cutoff, ]
  allplay_records <- function(column) vapply(teams$franchise_id, function(id) {
    own <- history[history$franchise_id == id, ]
    totals <- c(0L, 0L, 0L)
    for (j in seq_len(nrow(own))) {
      other <- history[[column]][history$week == own$week[j] & history$franchise_id != id]
      score <- own[[column]][j]
      totals <- totals + c(sum(score > other), sum(score < other), sum(score == other))
    }
    stopifnot(sum(totals) == 31L * cutoff)
    record_text(totals[1], totals[2], totals[3])
  }, character(1))
  ap_records <- allplay_records("points_for_week")
  potential_ap_records <- allplay_records("potential_points_week")
  source("scripts/sos_model.R", local=TRUE)
  future_allplay <- adl_predict_remaining_allplay(ADL_weekly_history, season, cutoff, potential)
  schedule <- adl_fetch("schedule", adl_connection(season))
  remaining_sos <- vapply(teams$franchise_id, function(id) {
    opponents <- schedule$opponent_id[schedule$franchise_id == id & schedule$week > cutoff & schedule$week <= 12L]
    if (!length(opponents)) return(NA_real_)
    values <- future_allplay[match(opponents, teams$franchise_id)]
    stopifnot(!anyNA(values))
    mean(values) * 100
  }, numeric(1))
  bonus_specs <- list(
    list(label="Q1 Bonus Game", start_week=1L, end_week=3L, column="pred_q1_bonus_wins"),
    list(label="Q2 Bonus Game", start_week=4L, end_week=6L, column="pred_q2_bonus_wins"),
    list(label="Q3 Bonus Game", start_week=7L, end_week=9L, column="pred_q3_bonus_wins"),
    list(label="Q4 Bonus Game", start_week=10L, end_week=12L, column="pred_q4_bonus_wins"),
    list(label="Regular Season Bonus Game", start_week=1L, end_week=12L, column="pred_rs_bonus_wins")
  )
  weekly_actual <- history %>%
    dplyr::group_by(week) %>%
    dplyr::group_modify(~ {
      scores <- .x$points_for_week
      tibble::tibble(
        franchise_id=.x$franchise_id,
        ap_wins=vapply(seq_along(scores), function(j) sum(scores[j] > scores[-j]), numeric(1)),
        ap_losses=vapply(seq_along(scores), function(j) sum(scores[j] < scores[-j]), numeric(1)),
        ap_ties=vapply(seq_along(scores), function(j) sum(scores[j] == scores[-j]), numeric(1)),
        points=.x$points_for_week,
        potential=.x$potential_points_week
      )
    }) %>% dplyr::ungroup()
  completed_bonus <- dplyr::bind_rows(lapply(Filter(function(spec) spec$end_week <= cutoff, bonus_specs), function(spec) {
    weekly_actual %>%
      dplyr::filter(week >= spec$start_week, week <= spec$end_week) %>%
      dplyr::group_by(franchise_id) %>%
      dplyr::summarise(ap=sum(ap_wins + .5*ap_ties), points=sum(points), potential=sum(potential), .groups="drop") %>%
      dplyr::arrange(dplyr::desc(ap), dplyr::desc(points), dplyr::desc(potential)) %>%
      dplyr::mutate(rank=dplyr::row_number(), credit=dplyr::case_when(rank<=15L~1, rank<=17L~.5, TRUE~0),
                    label=spec$label, week=spec$end_week)
  }))
  if (!nrow(completed_bonus)) completed_bonus <- tibble::tibble(
    franchise_id=character(), ap=numeric(), points=numeric(), potential=numeric(),
    rank=integer(), credit=numeric(), label=character(), week=integer())
  win_details <- lapply(seq_len(nrow(teams)), function(i) {
    future <- schedule[schedule$franchise_id == teams$franchise_id[i] &
                         schedule$week > cutoff & schedule$week <= 12L, ]
    future <- future[order(future$week), ]
    matchups <- lapply(seq_len(nrow(future)), function(j) {
      opponent_i <- match(future$opponent_id[j], teams$franchise_id)
      probability_column <- paste0("pred_w", future$week[j], "_wins")
      stopifnot(!is.na(opponent_i), probability_column %in% names(teams))
      list(
        week=as.integer(future$week[j]),
        opponent=escape(teams$franchise_name[opponent_i]),
        opponentLogo=logo[opponent_i],
        opponentAbbr=abbr[opponent_i],
        site=if (isTRUE(future$is_home[j])) "v." else "@",
        probability=as.numeric(teams[[probability_column]][i])
      )
    })
    bonus_games <- lapply(Filter(function(spec) spec$end_week > cutoff, bonus_specs), function(spec) {
      stopifnot(spec$column %in% names(teams))
      list(label=spec$label, week=spec$end_week,
           probability=as.numeric(teams[[spec$column]][i]))
    })
    list(currentWins=as.numeric(teams$total_wins[i]), matchups=matchups,
         bonusGames=bonus_games)
  })
  actual_details <- lapply(seq_len(nrow(teams)), function(i) {
    played <- weekly_actual[weekly_actual$franchise_id == teams$franchise_id[i], ]
    played <- played[order(played$week), ]
    conference_ids <- teams$franchise_id[teams$conference == teams$conference[i]]
    weeks <- lapply(seq_len(nrow(played)), function(j) {
      conference_scores <- weekly_actual$points[
        weekly_actual$week == played$week[j] &
          weekly_actual$franchise_id %in% conference_ids
      ]
      list(
        week=as.integer(played$week[j]), points=as.numeric(played$points[j]),
        weeklyMoney=isTRUE(round(as.numeric(played$points[j]), 6) == max(round(conference_scores, 6))),
        allPlayRecord=record_text(played$ap_wins[j], played$ap_losses[j], played$ap_ties[j]),
        allPlayPct=as.numeric((played$ap_wins[j]+.5*played$ap_ties[j])/31)
      )
    })
    games <- schedule[schedule$franchise_id == teams$franchise_id[i] & schedule$week <= cutoff, ]
    games <- games[order(games$week), ]
    matchups <- lapply(seq_len(nrow(games)), function(j) {
      opponent_i <- match(games$opponent_id[j], teams$franchise_id)
      credit <- if (games$franchise_score[j] > games$opponent_score[j]) 1 else if (games$franchise_score[j] < games$opponent_score[j]) 0 else .5
      list(week=as.integer(games$week[j]), opponent=escape(teams$franchise_name[opponent_i]),
           opponentLogo=logo[opponent_i], opponentAbbr=abbr[opponent_i],
           site=if(isTRUE(games$is_home[j])) "v." else "@",
           teamScore=as.numeric(games$franchise_score[j]), opponentScore=as.numeric(games$opponent_score[j]),
           result=if(credit==1) "W" else if(credit==.5) "T" else "L")
    })
    bonuses <- completed_bonus[completed_bonus$franchise_id == teams$franchise_id[i], ]
    bonus_games <- lapply(seq_len(nrow(bonuses)), function(j) list(
      label=bonuses$label[j], week=as.integer(bonuses$week[j]),
      allPlayWins=as.numeric(bonuses$ap[j]), rank=as.integer(bonuses$rank[j]),
      result=if(bonuses$credit[j]==1) "W" else if(bonuses$credit[j]==.5) "T" else "L"
    ))
    list(weeks=weeks, matchups=matchups, bonusGames=bonus_games)
  })
  data <- draft <- list(NFC=list(), AFC=list())
  for (conf in c("NFC", "AFC")) {
    ix <- which(teams$conference == if (conf == "NFC") "00" else "01")
    stopifnot(length(ix) == 16L)
    data[[conf]] <- lapply(ix, function(i) list(
      franchise_id=teams$franchise_id[i], name=escape(teams$franchise_name[i]), logo=logo[i], seed=teams$seed[i],
      clinch=teams$clinch[i], qual=teams$qual[i], projectedQual=if (isTRUE(teams$pred_is_division_winner[i])) "y" else if (isTRUE(teams$pred_is_wild_card[i])) "x" else "", record=teams$record[i],
      h2hRecord=record_text(teams$h2h_wins_raw[i], teams$h2h_losses_raw[i], teams$h2h_ties_raw[i]),
      bonusRecord=record_text(teams$bonus_wins_raw[i], teams$bonus_losses_raw[i], teams$bonus_ties_raw[i]),
      apRecord=ap_records[i], potentialApRecord=potential_ap_records[i], remainingSos=remaining_sos[i],
      pointsTotal=teams$points_for[i], apPct=teams$ap_win_pct[i], ppg=sprintf("%.1f", teams$ppg[i]),
      pot=potential[i], off=off[i], deff=defense[i], wins=teams$pred_total_wins[i],
      predPct=teams$pred_ap_win_pct[i]*100, finish=teams$pred_finish[i],
      playoffSeed=if (is.na(teams$pred_playoff_seed[i])) "NA" else as.character(teams$pred_playoff_seed[i]),
      odds=pct(teams$playoff_pct[i]), div=pct(teams$divwin_pct[i]), bye=pct(teams$bye_pct[i]),
      winDetails=win_details[[i]], actualDetails=actual_details[[i]],
      ranks=list(off=rank_of(off,i), deff=rank_of(defense,i), pot=rank_of(potential,i))))
    current <- build_conf_draft(teams[ix,], "seed", "potential_points", playoff_order="seed")
    projected <- build_conf_draft(teams[ix,], "pred_finish", "pred_potential_points", playoff_order="seed")
    draft[[conf]] <- lapply(ix, function(i) list(
      franchise_id=teams$franchise_id[i], name=escape(teams$franchise_name[i]), logo=logo[i],
      currentPick=current$Pick[match(teams$franchise_name[i], current$Team)],
      pick=projected$Pick[match(teams$franchise_name[i], projected$Team)],
      playoffSeed=if (is.na(teams$pred_playoff_seed[i])) "NA" else as.character(teams$pred_playoff_seed[i]),
      currentPlayoffSeed=if (teams$seed[i] <= 7L) as.character(teams$seed[i]) else "NA",
      currentAdjWins=teams$total_wins[i], projectedAdjWins=teams$pred_total_wins[i],
      currentApPct=teams$ap_win_pct[i], projectedApPct=teams$pred_ap_win_pct[i],
      currentDivisionRank=teams$division_rank[i], projectedDivisionRank=teams$pred_division_rank[i],
      division=c("East", "North", "South", "West")[as.integer(teams$division[i]) %% 4L + 1L],
      currentPoints=teams$points_for[i], projectedPoints=teams$pred_points_for[i],
      currentPotentialPPG=teams$potential_points[i] / teams$through_week[i],
      projectedPotentialPPG=teams$pred_potential_points[i] / adl_max_week,
      currentPotential=teams$potential_points[i],
      potential=teams$pred_potential_points[i]))
  }
  if (!is.null(postseason)) for (conf in names(draft)) for (j in seq_along(draft[[conf]])) {
    row <- match(draft[[conf]][[j]]$name, escape(teams$franchise_name))
    value <- postseason[match(teams$franchise_id[row], postseason$franchise_id),]
    draft[[conf]][[j]]$postseason <- as.list(value[1,])
  }
  source("scripts/gm_profiles.R", local=TRUE)
  gm_profiles <- adl_gm_profiles(season, week)
  template <- paste(readLines("scripts/templates/playoff_picture.html", warn=FALSE, encoding="UTF-8"), collapse="\n")
  json <- function(x) as.character(jsonlite::toJSON(x, auto_unbox=TRUE, digits=8, na="null"))
  status <- getOption("adl.score_status", "")
  status <- if (status == "official") "official" else if (status == "unofficial") "unofficial" else "reported"
  substitutions <- list(
    "__DATA__"=json(data), "__DRAFT__"=json(draft), "__GM_PROFILES__"=json(gm_profiles),
    "__SHIELD__"=paste0("data:image/png;base64,", jsonlite::base64_enc(readBin("www/adl-shield.png", "raw", file.info("www/adl-shield.png")$size))),
    "__SEASON__"=season, "__OUTLOOK__"=week+1L, "__WEEK__"=week,
    "__POSTSEASON__"=json(week >= 12L),
    "__HEADING__"=if(week >= 17L) "Final" else if(week >= 12L) "Postseason" else paste("Week",week+1L,"Outlook"), "__STATUS__"=status,
    "__SIMS__"=format(getOption("adl.n_sims",3000L), big.mark=",", scientific=FALSE),
    "__TRAINING__"=paste0(2021L, "–", season-1L), "__UPDATED__"=escape(updated_at),
    "__DROPDOWN__"=if(is.null(dropdown)) "" else as.character(dropdown), "__FULL_FILE__"=full_file)
  for (key in names(substitutions)) template <- gsub(key, substitutions[[key]], template, fixed=TRUE)
  stopifnot(!grepl("__[A-Z_]+__", template))
  paste0('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
         '<title>ADL ',season,' Playoff Picture</title><style>:root{color-scheme:light dark}body{margin:0;padding:12px;background:light-dark(#f5f7fa,#151c25)}#adl-playoff-design{max-width:1100px;margin:auto}a{color:light-dark(#235789,#89bce8)}</style></head><body>',
         template, '</body></html>')
}
