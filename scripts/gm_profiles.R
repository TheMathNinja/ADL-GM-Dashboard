# Current ownership is season-specific. Career history is an audited
# completed-season baseline and is joined by GM, never by last year's team.
adl_gm_profiles <- function(season, week, scores=NULL) {
  baseline <- jsonlite::fromJSON('data/gm_career_profiles.json', simplifyVector=FALSE)
  current <- jsonlite::fromJSON(sprintf('data/current_gms_%d.json', season), simplifyVector=FALSE)
  seasons <- jsonlite::fromJSON('data/gm_career_seasons.json', simplifyVector=TRUE)
  stopifnot(baseline$season == season, baseline$completedThrough < season,
            length(baseline$profiles) == 32L,
            current$season == season, length(current$profiles) == 32L)
  if (is.null(scores)) {
    if (week <= 12L) {
      scores <- ADL_weekly_history[ADL_weekly_history$season == season & ADL_weekly_history$week <= week, ]
      scores$franchise_score <- scores$points_for_week
    } else {
      source("R/weekly_system.R", local=TRUE)
      scores <- build_adl_team_week_data(season, week)
    }
  }
  scores <- scores[scores$season == season & scores$week <= week, ]
  scores$franchise_id <- sprintf('%04d', as.integer(scores$franchise_id))
  stopifnot(nrow(scores) == 32L * week, !anyNA(scores$franchise_score),
            !anyDuplicated(paste(scores$week, scores$franchise_id)))
  history_by_gm <- setNames(unname(baseline$profiles),
                            vapply(baseline$profiles, `[[`, character(1), 'gm'))
  stopifnot(length(history_by_gm) == 32L)
  profiles <- lapply(current$profiles, function(owner) {
    g <- history_by_gm[[owner$gm]]
    if (is.null(g)) g <- list(experience=0L, wins=0L, losses=0L, ties=0L,
                              best=NULL, bestYears=list(), worst=NULL, worstYears=list())
    g$franchise_id <- owner$franchise_id
    g$gm <- owner$gm
    aliases <- list(
      'Chase Marak'=c('Chase'),
      "Joe O'Mara"=c('Joe'),
      'Zachary Hall'=c('ZH'),
      'Thomas Cool'=c('Thomas')
    )
    normalize <- function(x) gsub('[^a-z0-9]', '', tolower(x))
    accepted <- normalize(c(owner$gm, aliases[[owner$gm]]))
    if (grepl(',', owner$gm, fixed=TRUE)) {
      keep <- normalize(seasons$gm) %in% accepted
    } else {
      keep <- vapply(strsplit(seasons$gm, ',', fixed=TRUE), function(parts)
        any(normalize(trimws(parts)) %in% accepted), logical(1))
    }
    career <- seasons[keep, , drop=FALSE]
    stopifnot(nrow(career) == g$experience,
              sum(career$wins) == g$wins,
              sum(career$losses) == g$losses,
              sum(career$ties) == g$ties)
    g$completedSeasonApPcts <- (career$wins + .5 * career$ties) /
      (career$wins + career$losses + career$ties)
    g
  })
  stopifnot(length(unique(vapply(profiles, `[[`, character(1), 'franchise_id'))) == 32L)
  for (name in names(profiles)) {
    g <- profiles[[name]]
    own <- scores[scores$franchise_id == g$franchise_id, ]
    stopifnot(nrow(own) == week)
    for (i in seq_len(nrow(own))) {
      other <- scores$franchise_score[scores$week == own$week[i] & scores$franchise_id != g$franchise_id]
      g$wins <- g$wins + sum(own$franchise_score[i] > other)
      g$losses <- g$losses + sum(own$franchise_score[i] < other)
      g$ties <- g$ties + sum(own$franchise_score[i] == other)
    }
    current_games <- 31L * week
    current_adjusted_wins <- 0
    if (week > 0L) for (i in seq_len(nrow(own))) {
      other <- scores$franchise_score[scores$week == own$week[i] & scores$franchise_id != g$franchise_id]
      current_adjusted_wins <- current_adjusted_wins + sum(own$franchise_score[i] > other) +
        .5 * sum(own$franchise_score[i] == other)
    }
    current_pct <- if (current_games) current_adjusted_wins / current_games else 0
    current_weight <- min(week, 17L) / 17
    completed <- unlist(g$completedSeasonApPcts, use.names=FALSE)
    g$completedSeasonApPcts <- NULL
    g$careerApPct <- (sum(completed) + current_weight * current_pct) /
      (length(completed) + current_weight)
    profiles[[name]] <- g
  }
  profiles
}
