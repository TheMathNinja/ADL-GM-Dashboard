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
  data <- draft <- list(NFC=list(), AFC=list())
  for (conf in c("NFC", "AFC")) {
    ix <- which(teams$conference == if (conf == "NFC") "00" else "01")
    stopifnot(length(ix) == 16L)
    data[[conf]] <- lapply(ix, function(i) list(
      name=escape(teams$franchise_name[i]), logo=logo[i], seed=teams$seed[i],
      clinch=teams$clinch[i], qual=teams$qual[i], record=teams$record[i],
      h2hRecord=record_text(teams$h2h_wins_raw[i], teams$h2h_losses_raw[i], teams$h2h_ties_raw[i]),
      bonusRecord=record_text(teams$bonus_wins_raw[i], teams$bonus_losses_raw[i], teams$bonus_ties_raw[i]),
      apRecord=ap_records[i], potentialApRecord=potential_ap_records[i], remainingSos=remaining_sos[i],
      pointsTotal=teams$points_for[i], apPct=teams$ap_win_pct[i], ppg=sprintf("%.1f", teams$ppg[i]),
      pot=potential[i], off=off[i], deff=defense[i], wins=teams$pred_total_wins[i],
      predPct=teams$pred_ap_win_pct[i]*100, finish=teams$pred_finish[i],
      playoffSeed=if (is.na(teams$pred_playoff_seed[i])) "NA" else as.character(teams$pred_playoff_seed[i]),
      odds=pct(teams$playoff_pct[i]), div=pct(teams$divwin_pct[i]), bye=pct(teams$bye_pct[i]),
      ranks=list(off=rank_of(off,i), deff=rank_of(defense,i), pot=rank_of(potential,i))))
    current <- build_conf_draft(teams[ix,], "seed", "potential_points", playoff_order="seed")
    projected <- build_conf_draft(teams[ix,], "pred_finish", "pred_potential_points", playoff_order="seed")
    draft[[conf]] <- lapply(ix, function(i) list(
      name=escape(teams$franchise_name[i]), logo=logo[i],
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
  template <- paste(readLines("scripts/templates/playoff_picture.html", warn=FALSE, encoding="UTF-8"), collapse="\n")
  json <- function(x) as.character(jsonlite::toJSON(x, auto_unbox=TRUE, digits=8, na="null"))
  status <- getOption("adl.score_status", "")
  status <- if (status == "official") "Official" else if (status == "unofficial") "Unofficial" else "Reported"
  substitutions <- list(
    "__DATA__"=json(data), "__DRAFT__"=json(draft),
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
