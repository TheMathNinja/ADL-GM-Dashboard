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
train <- history %>% filter(season<2025,week==1) %>%
  select(season,franchise_id,potential_points) %>%
  inner_join(history %>% filter(season<2025,week==12) %>%
    select(season,franchise_id,final=potential_points),by=c('season','franchise_id')) %>%
  mutate(avg_pot=potential_points, target=(final-potential_points)/11)
reference <- lm(target~avg_pot,train)
stopifnot(isTRUE(all.equal(unname(coef(reference)),unname(coef(model$potential_mean_model)))))
# Later current-season results must never leak into either fitted mean model.
changed <- history
changed$potential_points[changed$season==2025 & changed$week>1] <- 1e7
changed$points_for[changed$season==2025 & changed$week>1] <- 1e6
set.seed(1)
again <- run_adl_monte_carlo(standings, changed, schedule, sd_points=35, n_sims=2)
stopifnot(identical(coef(model$potential_mean_model),coef(again$potential_mean_model)),
          identical(coef(model$mean_model_m3),coef(again$mean_model_m3)))
cat('PASS: direct potential target matches independent historical fit; current-season future data cannot affect either mean model.\n')
