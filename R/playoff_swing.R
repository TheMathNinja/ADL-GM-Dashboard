adl_swing_seed_values <- function(qualified, seeds) {
  if (length(qualified) != length(seeds) || anyNA(qualified) ||
      any(!is.finite(seeds[qualified]) | seeds[qualified] < 1 | seeds[qualified] > 7)) {
    stop("Invalid conditional playoff seeds.")
  }
  ifelse(qualified, seeds, 8)
}

adl_conditional_seed_means <- function(totals, counts) {
  if (any(!is.finite(counts) | counts <= 0)) stop("Missing conditional seed samples.")
  list(a_win = totals[, 1L, 1L] / counts[, 1L],
       a_loss = totals[, 2L, 1L] / counts[, 2L],
       b_win = totals[, 2L, 2L] / counts[, 2L],
       b_loss = totals[, 1L, 2L] / counts[, 1L])
}

adl_swing_draft_values <- function(qualified, seeds, potential, conferences) {
  adl_swing_seed_values(qualified, seeds)
  if (any(!is.finite(potential)) || anyNA(conferences)) stop("Invalid projected draft inputs.")
  picks <- numeric(length(qualified))
  for (ids in split(seq_along(qualified), conferences)) {
    non <- ids[!qualified[ids]]
    playoff <- ids[qualified[ids]]
    # Match the existing regular-season projected draft board: non-playoff
    # teams by potential, then playoff teams in provisional reverse-seed order.
    ordered <- c(non[order(potential[non])], playoff[order(-seeds[playoff])])
    picks[ordered] <- seq_along(ids)
  }
  picks
}
