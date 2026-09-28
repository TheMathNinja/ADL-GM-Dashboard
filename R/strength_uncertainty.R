# Persistent team-strength SD, estimated with each training season held out.
# The linear multiplier applies to SD, not variance. Weekly score SD is unchanged.
adl_strength_uncertainty <- function(history, train_seasons, week, max_week = 12L) {
  if (week >= max_week) return(list(raw_sd = 0, multiplier = 0, sd = 0))
  stopifnot(week >= 1L)
  # Earliest archives cannot supply a held-out training-season estimate.
  if (length(train_seasons) < 2L) {
    warning("Fewer than two training seasons: retaining weekly noise only.")
    return(list(raw_sd = 0, multiplier = (max_week-week)/(max_week-1L), sd = 0))
  }
  h <- as.data.frame(history)
  h <- h[h$season %in% train_seasons & h$week <= max_week, ]
  past <- aggregate(potential_points_week ~ season + franchise_id,
                    h[h$week <= week, ], mean)
  future <- aggregate(points_for_week ~ season + franchise_id,
                      h[h$week > week, ], mean)
  d <- merge(past, future, by = c("season", "franchise_id"))
  errors <- noise <- numeric()
  for (year in train_seasons) {
    fit <- lm(points_for_week ~ potential_points_week, d[d$season != year, ])
    test <- d[d$season == year, ]
    e <- test$points_for_week - pmax(0, predict(fit, test))
    errors <- c(errors, e - mean(e))
    n <- nrow(test)
    stopifnot(n == 32L, all(is.finite(e)))
    other <- h[h$season != year, ]
    sds <- aggregate(points_for_week ~ season + franchise_id, other, sd)$points_for_week
    if (week > 1L) {
      observed <- h[h$season == year & h$week <= week, ]
      sds <- c(sds, aggregate(points_for_week ~ franchise_id, observed, sd)$points_for_week)
    }
    noise <- c(noise, mean(sds)^2 / (max_week - week))
  }
  raw <- sqrt(max(0, mean(errors^2) * 32 / 31 - mean(noise)))
  multiplier <- (max_week - week) / (max_week - 1L)
  list(raw_sd = raw, multiplier = multiplier, sd = raw * multiplier)
}

adl_draw_future_points <- function(mu, weekly_sd, strength_sd, remaining_weeks) {
  # One offset per team per simulation, shared by every remaining week.
  offset <- rnorm(length(mu), 0, strength_sd)
  points <- matrix(rnorm(length(mu) * remaining_weeks,
                         rep(mu + offset, remaining_weeks), weekly_sd),
                   nrow = length(mu), ncol = remaining_weeks)
  pmax(points, 0)
}
