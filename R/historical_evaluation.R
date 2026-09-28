# Historical evaluation only. Production forecasts continue to train on prior years.
adl_evaluation_years <- function(available, target,
                               method = c("all_other_seasons", "past_only")) {
  method <- match.arg(method)
  available <- sort(unique(as.integer(available)))
  if (method == "all_other_seasons") available[available != target] else available[available < target]
}

adl_evaluate_ppg <- function(history, method = c("all_other_seasons", "past_only"),
                             min_training_seasons = 2L) {
  method <- match.arg(method)
  required <- c("season", "week", "franchise_id", "points_for_week", "potential_points_week")
  stopifnot(all(required %in% names(history)))
  d <- as.data.frame(history[history$season >= 2021 & history$week %in% 1:12, required])
  stopifnot(!anyDuplicated(d[c("season", "week", "franchise_id")]),
            all(is.finite(d$points_for_week)), all(is.finite(d$potential_points_week)))
  available <- sort(unique(d$season))
  for (year in available) {
    counts <- table(d$franchise_id[d$season == year])
    stopifnot(length(counts) == 32L, all(counts == 12L))
  }
  rows <- list(); folds <- list(); skips <- list()
  for (year in available) {
    training <- adl_evaluation_years(available, year, method)
    if (length(training) < min_training_seasons) {
      skips[[length(skips) + 1L]] <- data.frame(method, season = year,
        reason = "Fewer than two complete training seasons")
      next
    }
    stopifnot(!year %in% training)
    folds[[length(folds) + 1L]] <- data.frame(method, season = year,
      training_seasons = paste(training, collapse = ";"))
    for (cutoff in 1:11) {
      seen <- aggregate(potential_points_week ~ season + franchise_id,
                        d[d$week <= cutoff, ], mean)
      remaining <- aggregate(points_for_week ~ season + franchise_id,
                             d[d$week > cutoff, ], mean)
      snapshot <- merge(seen, remaining, by = c("season", "franchise_id"))
      train <- snapshot[snapshot$season %in% training, ]
      test <- snapshot[snapshot$season == year, ]
      # Mirrors the deployed raw Potential-PPG mean regression; no correction.
      fit <- lm(points_for_week ~ potential_points_week, data = train)
      pred <- pmax(0, as.numeric(predict(fit, test)))
      rows[[length(rows) + 1L]] <- data.frame(method, season = year, cutoff,
        franchise_id = test$franchise_id, predicted_remaining_ppg = pred,
        actual_remaining_ppg = test$points_for_week,
        error = pred - test$points_for_week)
    }
  }
  if (!length(rows)) stop("No eligible evaluation folds")
  list(predictions = do.call(rbind, rows), folds = do.call(rbind, folds),
       skipped = if (length(skips)) do.call(rbind, skips) else
         data.frame(method = character(), season = integer(), reason = character()))
}
