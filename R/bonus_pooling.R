# Pool Monte Carlo estimates for interchangeable, completely unplayed quarterly
# Bonus Games. This is a reporting transformation only: averaging a team's
# probabilities across the pooled quarters preserves its total expected wins.
pool_unstarted_quarter_bonus <- function(probabilities, through_week,
                                         league_total = 16) {
  probabilities <- as.matrix(probabilities)
  if (ncol(probabilities) != 4L || any(!is.finite(probabilities))) {
    stop("Quarterly Bonus Game probabilities must be a finite four-column matrix.")
  }
  through_week <- as.integer(through_week)
  quarter_starts <- c(1L, 4L, 7L, 10L)
  pooled <- which(quarter_starts > through_week)
  before <- probabilities

  if (length(pooled) > 1L) {
    shared <- rowMeans(probabilities[, pooled, drop = FALSE])
    probabilities[, pooled] <- shared
  }

  # Each event awards 15 wins plus two half-wins. Pooling must preserve both
  # every team's combined expectation and the league total in every event.
  if (length(pooled) > 0L) {
    stopifnot(isTRUE(all.equal(rowSums(probabilities[, pooled, drop = FALSE]),
                              rowSums(before[, pooled, drop = FALSE]),
                              tolerance = 1e-12)))
  }
  stopifnot(all(abs(colSums(probabilities) - league_total) < 1e-9))
  probabilities
}
