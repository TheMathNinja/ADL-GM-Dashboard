source("R/historical_evaluation.R")
stopifnot(identical(adl_evaluation_years(2021:2025, 2023), c(2021L, 2022L, 2024L, 2025L)),
          identical(adl_evaluation_years(2021:2025, 2023, "past_only"), 2021:2022))
files <- list.files("data/playoff_history", "^ADL_weekly_history_[0-9]{4}\\.rds$", full.names = TRUE)
h <- do.call(rbind, lapply(files, function(p) as.data.frame(readRDS(p))))
result <- adl_evaluate_ppg(h)
stopifnot(identical(sort(unique(result$predictions$season)), 2021:2025),
          nrow(result$predictions) == 5 * 11 * 32)
# Changing held-out future outcomes must not change that week's prediction.
altered <- h
ix <- altered$season == 2023 & altered$week > 3
altered$points_for_week[ix] <- altered$points_for_week[ix] + 1000
altered$potential_points_week[ix] <- altered$potential_points_week[ix] + 1000
check <- adl_evaluate_ppg(altered)$predictions
ix <- result$predictions$season == 2023 & result$predictions$cutoff == 3
stopifnot(isTRUE(all.equal(result$predictions$predicted_remaining_ppg[ix],
                          check$predicted_remaining_ppg[ix], tolerance = 1e-10)))
past <- adl_evaluate_ppg(h, "past_only")
stopifnot(identical(sort(unique(past$predictions$season)), 2023:2025),
          identical(sort(past$skipped$season), 2021:2022))
cat("Historical evaluation tests passed.\n")
