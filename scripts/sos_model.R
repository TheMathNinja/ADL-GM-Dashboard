# Predict future all-play from Potential PPG relative to the season league mean.
# Fit each checkpoint on completed prior regular seasons; no current-year outcomes.
adl_predict_remaining_allplay <- function(history, season, cutoff, potential_ppg) {
  if (cutoff >= 12L) return(rep(NA_real_, length(potential_ppg)))
  stopifnot(cutoff >= 1L, length(potential_ppg) == 32L, all(is.finite(potential_ppg)))
  prior <- history[history$season >= 2021L & history$season < season & history$week >= 1L & history$week <= 12L, ]
  stopifnot(!anyDuplicated(prior[c("season", "week", "franchise_id")]))
  counts <- aggregate(week ~ season + franchise_id, prior, length)
  stopifnot(nrow(counts) >= 32L, all(counts$week == 12L))
  input <- aggregate(potential_points_week ~ season + franchise_id, prior[prior$week <= cutoff, ], mean)
  target <- aggregate(ap_wins_week ~ season + franchise_id, prior[prior$week > cutoff, ], mean)
  train <- merge(input, target, by=c("season", "franchise_id"))
  train$future_allplay <- train$ap_wins_week / 31
  stopifnot(all(table(train$season) == 32L))
  # Use only Potential PPG observed through this checkpoint in every season.
  train$relative_potential <- train$potential_points_week -
    ave(train$potential_points_week, train$season, FUN=mean)
  fit <- lm(future_allplay ~ relative_potential, train)
  predicted <- as.numeric(predict(fit, data.frame(
    relative_potential=potential_ppg - mean(potential_ppg))))
  stopifnot(all(is.finite(predicted)))
  # Percentage bounds protect against extrapolation beyond historical inputs.
  pmin(1, pmax(0, predicted))
}
