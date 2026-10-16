source('scripts/get_adl_playoff_picture.R')
history <- dplyr::bind_rows(lapply(2021:2025, function(y)
  readRDS(sprintf('data/playoff_history/ADL_weekly_history_%d.rds', y))))
standings <- history %>% filter(season==2025, week==1) %>%
  mutate(through_week=week, total_wins=h2h_wins, bonus_wins=0)
ids <- standings$franchise_id
# Synthetic schedule keeps this test independent of API access.
schedule <- expand.grid(week=1:12, franchise_id=ids, stringsAsFactors=FALSE)
schedule$opponent_id <- ids[match(schedule$franchise_id,ids) +
  ifelse(match(schedule$franchise_id,ids) %% 2 == 1, 1, -1)]
set.seed(1)
model <- run_adl_monte_carlo(standings, history, schedule, sd_points=35, n_sims=2)
stopifnot(is.null(model$potential_mean_model), is.null(model$mean_model_m3),
          model$scoring_model$version == 'adl-player-blend-35-0-55-10-nig-v3',
          all(model$team_summary$potential_mu_pts >= model$team_summary$mu_pts))
# Later current-season results must never leak into either fitted mean model.
changed <- history
changed$potential_points[changed$season==2025 & changed$week>1] <- 1e7
changed$points_for[changed$season==2025 & changed$week>1] <- 1e6
set.seed(1)
again <- run_adl_monte_carlo(standings, changed, schedule, sd_points=35, n_sims=2)
stopifnot(identical(coef(model$potential_mean_model),coef(again$potential_mean_model)),
          identical(coef(model$mean_model_m3),coef(again$mean_model_m3)))
stopifnot(identical(model$team_summary$mu_pts,again$team_summary$mu_pts),
          identical(model$team_summary$potential_mu_pts,again$team_summary$potential_mu_pts))
cat('PASS: coherent stochastic PF/Potential and no future-score leakage.\n')

model_json <- jsonlite::read_json('data/lineup_status_model.json', simplifyVector=TRUE)
stopifnot(identical(model_json$version, 'adl-lineup-status-v2'))
for (w in 1:11) {
  p <- model_json$weeks[[as.character(w)]]
  stopifnot(is.finite(p$potential_intercept), is.finite(p$potential_slope),
            p$potential_slope >= 0)
}

