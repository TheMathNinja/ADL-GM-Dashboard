source("R/playoff_swing.R")
stopifnot(identical(adl_swing_seed_values(c(TRUE, TRUE, FALSE, FALSE), c(1, 7, 10, 16)), c(1, 7, 8, 8)))
stopifnot(inherits(try(adl_swing_seed_values(TRUE, NA_real_), silent=TRUE), "try-error"))
totals <- array(0, c(1,2,2)); counts <- matrix(c(200,100),1)
totals[1,1,1] <- 200; totals[1,2,1] <- 400
totals[1,2,2] <- 200; totals[1,1,2] <- 1600
means <- adl_conditional_seed_means(totals, counts)
stopifnot(means$a_win == 1, means$a_loss == 4, means$b_win == 2, means$b_loss == 8)
stopifnot(abs(means$a_win-means$a_loss)+abs(means$b_win-means$b_loss)==9)
cat("Conditional seed swing tests passed.\n")
draft <- adl_swing_draft_values(c(FALSE,FALSE,TRUE,TRUE), c(8,8,1,7), c(100,90,80,70), rep("NFC",4))
stopifnot(identical(draft,c(2,1,4,3)))
# Draft slots follow potential, not a reversed conference finish.
draft2 <- adl_swing_draft_values(c(FALSE,FALSE,TRUE,TRUE), c(8,8,1,7), c(85,90,80,70), rep("NFC",4))
stopifnot(identical(draft2,c(1,2,4,3)))
cat("Projected draft board swing tests passed.\n")
