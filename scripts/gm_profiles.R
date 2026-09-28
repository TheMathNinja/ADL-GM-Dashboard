# GM career history is an audited completed-season baseline. Add current games
# from the existing weekly scrape, without another MFL request.
adl_gm_profiles <- function(season, week, scores=NULL) {
  baseline <- jsonlite::fromJSON('data/gm_career_profiles.json', simplifyVector=FALSE)
  stopifnot(baseline$season == season, length(baseline$profiles) == 32L)
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
  profiles <- baseline$profiles
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
    profiles[[name]] <- g
  }
  profiles
}
