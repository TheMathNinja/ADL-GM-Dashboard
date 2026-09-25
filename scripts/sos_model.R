# Predict future all-play percentage from current Potential PPG only.
# Fit each checkpoint on completed prior regular seasons; no current-year outcomes.
adl_predict_remaining_allplay <- function(history, season, cutoff, potential_ppg) {
  if (cutoff >= 12L) return(rep(NA_real_, length(potential_ppg)))
  stopifnot(cutoff >= 1L, all(is.finite(potential_ppg)))
  prior <- history[history$season >= 2021L & history$season < season & history$week >= 1L & history$week <= 12L, ]
  stopifnot(!anyDuplicated(prior[c("season", "week", "franchise_id")]))
  counts <- aggregate(week ~ season + franchise_id, prior, length)
  stopifnot(nrow(counts) >= 32L, all(counts$week == 12L))
  input <- aggregate(potential_points_week ~ season + franchise_id, prior[prior$week <= cutoff, ], mean)
  target <- aggregate(ap_wins_week ~ season + franchise_id, prior[prior$week > cutoff, ], mean)
  train <- merge(input, target, by=c("season", "franchise_id"))
  train$future_allplay <- train$ap_wins_week / 31
  fit <- lm(future_allplay ~ potential_points_week, train)
  predicted <- as.numeric(predict(fit, data.frame(potential_points_week=potential_ppg)))
  stopifnot(all(is.finite(predicted)))
  # Percentage bounds protect against extrapolation beyond historical inputs.
  pmin(1, pmax(0, predicted))
}
