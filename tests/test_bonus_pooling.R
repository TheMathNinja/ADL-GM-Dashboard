source("R/bonus_pooling.R")

# Every synthetic quarter awards the required 16 adjusted wins, while each
# team's raw Monte Carlo estimate differs slightly across future quarters.
x <- cbind(
  Q1 = c(rep(1, 15), 0.5, 0.5, rep(0, 15)),
  Q2 = c(rep(1, 14), 0.8, 0.7, 0.5, rep(0, 15)),
  Q3 = c(rep(1, 14), 0.7, 0.8, 0.5, rep(0, 15)),
  Q4 = c(rep(1, 14), 0.75, 0.75, 0.5, rep(0, 15))
)
stopifnot(all(abs(colSums(x) - 16) < 1e-12))

# Through Week 3, Q2-Q4 are unplayed and become identical. Q1 is untouched.
y <- pool_unstarted_quarter_bonus(x, 3)
stopifnot(identical(y[, 1], x[, 1]),
          isTRUE(all.equal(y[, 2], y[, 3])),
          isTRUE(all.equal(y[, 3], y[, 4])),
          isTRUE(all.equal(rowSums(y), rowSums(x), tolerance = 1e-12)),
          all(abs(colSums(y) - 16) < 1e-12))

# A quarter already in progress remains distinct; only Q3-Q4 are pooled.
z <- pool_unstarted_quarter_bonus(x, 4)
stopifnot(identical(z[, 1], x[, 1]), identical(z[, 2], x[, 2]),
          isTRUE(all.equal(z[, 3], z[, 4])),
          isTRUE(all.equal(rowSums(z), rowSums(x), tolerance = 1e-12)))

# Once only one future quarter remains, there is nothing to pool.
stopifnot(isTRUE(all.equal(pool_unstarted_quarter_bonus(x, 7), x)))
cat("Bonus Game pooling tests passed.\n")
