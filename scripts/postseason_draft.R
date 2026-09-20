# Qualification and potential points are frozen at Week 12. Scores after
# elimination must never change a team's draft tiebreaker.
adl_postseason_replay <- function(regular, scores, through_week) {
  n <- nrow(regular)
  stopifnot(n == 32L, nrow(scores) == n, ncol(scores) >= 17L,
            through_week >= 12L, through_week <= 17L)
  if (any(!is.finite(scores[, seq_len(through_week)]))) stop("Incomplete postseason scores.")
  ap <- regular$ap_wins_total
  pf <- regular$points_for
  frozen_ap <- ap; frozen_week <- rep(12L, n)
  stage <- ifelse(regular$seed > 7L, 0L, 4L)
  status <- ifelse(stage == 0L, "Consolation", "Still alive")
  # Reverse seed is only a provisional ordering for teams still alive.
  rank_group <- function(ids) ids[order(-ap[ids], -pf[ids], -regular$potential_points[ids])]
  alive <- lapply(split(seq_len(n), regular$conference), function(ids) rank_group(ids[regular$seed[ids] <= 7L]))
  wc <- lapply(alive, function(ids) list(c(ids[2], ids[7]), c(ids[3], ids[6]), c(ids[4], ids[5])))
  if (through_week > 12L) for (w in 13:through_week) {
    # Pairings and home-field ties use seeds ENTERING the round.
    pairs <- if (w == 14L) wc else if (w %in% c(15L, 16L)) lapply(alive, function(ids) {
      ids <- rank_group(ids)
      if (length(ids) == 4L) list(ids[c(1,4)], ids[c(2,3)]) else list(ids)
    }) else NULL
    losers <- integer()
    if (!is.null(pairs)) for (conf in names(pairs)) {
      winners <- integer()
      for (pair in pairs[[conf]]) {
        value <- if (w == 14L) rowSums(scores[, 13:14, drop=FALSE]) else scores[,w]
        # Opponents remain fixed across Wild Card legs, but the displayed
        # home-field seed updates weekly from cumulative All-Play.
        winner <- if (abs(value[pair[1]] - value[pair[2]]) < 1e-8) rank_group(pair)[1] else pair[which.max(value[pair])]
        winners <- c(winners, winner); losers <- c(losers, setdiff(pair, winner))
      }
      alive[[conf]] <- if (w == 14L) c(alive[[conf]][1], winners) else winners
    }
    ap <- ap + rank(scores[,w], ties.method="average") - 1
    pf <- pf + scores[,w]
    if (length(losers)) {
      stage[losers] <- w - 13L
      status[losers] <- c("Wild Card exit", "Divisional exit", "Conference runner-up")[w-13L]
      frozen_ap[losers] <- ap[losers]; frozen_week[losers] <- w
    }
    if (w == 16L) {
      champs <- unlist(alive, use.names=FALSE)
      status[champs] <- "Conference champion"
      frozen_ap[champs] <- ap[champs]; frozen_week[champs] <- 16L
    }
  }
  active <- which(status == "Still alive")
  frozen_ap[active] <- ap[active]; frozen_week[active] <- through_week
  pick <- numeric(n)
  for (ids in split(seq_len(n), regular$conference)) {
    non <- ids[stage[ids] == 0L]
    non <- non[order(regular$potential_points[non])]
    playoff <- ids[stage[ids] > 0L]
    # Same-round ties follow the seed hierarchy: AP, actual points, potential.
    # Actual points must also be frozen at the elimination week.
    frozen_pf <- vapply(playoff, function(i) sum(scores[i,seq_len(frozen_week[i])]), numeric(1))
    playoff <- playoff[order(stage[playoff], frozen_ap[playoff], frozen_pf, regular$potential_points[playoff])]
    pick[c(non, playoff)] <- seq_along(ids)
  }
  data.frame(franchise_id=regular$franchise_id, currentPick=pick, status=status,
             apPct=frozen_ap / (31 * frozen_week), apThrough=frozen_week,
             potentialPPG=regular$potential_points / 12)
}

adl_postseason_draft <- function(regular, scores, through_week, mean_points, sd_points, n_sims=3000L) {
  current <- adl_postseason_replay(regular, scores, through_week)
  stopifnot(length(mean_points)==32L, all(is.finite(mean_points)), is.finite(sd_points), sd_points>0)
  # Conference-specific draft boards become final after Week 16. The Super
  # Bowl and Bragging Rights do not re-order teams within either conference.
  if (through_week >= 16L) {
    current$expectedPick <- current$currentPick
    return(current)
  }
  sums <- numeric(32)
  for (trial in seq_len(n_sims)) {
    simulated <- scores
    for (w in (through_week+1L):16L) simulated[,w] <- pmax(0, rnorm(32, mean_points, sd_points))
    result <- adl_postseason_replay(regular, simulated, 16L)
    sums <- sums + result$currentPick
  }
  current$expectedPick <- sums/n_sims
  current
}

adl_build_postseason_draft <- function(regular, season, through_week, history, n_sims) {
  starters <- adl_fetch("starters", adl_connection(season), week=seq_len(through_week))
  weekly <- starters %>% dplyr::filter(starter_status == "starter") %>%
    dplyr::group_by(franchise_id, week) %>%
    dplyr::summarise(points=round(sum(player_score), 6), .groups="drop")
  scores <- matrix(NA_real_, 32, 17)
  scores[cbind(match(weekly$franchise_id, regular$franchise_id), weekly$week)] <- weekly$points
  # Retain the regular forecast's potential-only scoring model. Its final
  # available historical fit uses Weeks 1-11 to predict Week 12; apply that
  # same fit to the full regular-season potential PPG for remaining games.
  past <- history[history$season < season,]
  early <- past[past$week == 11L, c("season","franchise_id","potential_points")]
  last <- past[past$week == 12L, c("season","franchise_id","points_for_week")]
  training <- merge(early, last, by=c("season","franchise_id"))
  training$avg_pot <- training$potential_points/11
  model <- lm(points_for_week ~ avg_pot, training)
  mu <- pmax(0, predict(model, data.frame(avg_pot=regular$potential_points/12)))
  sigma <- mean(vapply(split(past$points_for_week, interaction(past$season,past$franchise_id,drop=TRUE)), sd, numeric(1)), na.rm=TRUE)
  adl_postseason_draft(regular, scores, through_week, mu, sigma, n_sims)
}
