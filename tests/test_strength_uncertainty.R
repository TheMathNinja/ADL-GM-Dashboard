source("R/strength_uncertainty.R")
files <- list.files("data/playoff_history", "^ADL_weekly_history_[0-9]{4}\\.rds$", full.names = TRUE)
h <- do.call(rbind, lapply(files, function(p) as.data.frame(readRDS(p))))
# Match the independently implemented Python historical experiment.
expected <- c(15.14,14.26,12.31,11.33,10.82,11.21,9.58,10.15,9.33,6.99,0)
for (w in 1:11) {
  v <- adl_strength_uncertainty(h, 2021:2024, w)
  stopifnot(abs(v$raw_sd - expected[w]) < .006,
            abs(v$sd - v$raw_sd * (12-w)/11) < 1e-12)
}
# Excluded season scores cannot affect the uncertainty estimate.
changed <- h; changed$points_for_week[changed$season == 2025] <- 9999
stopifnot(identical(adl_strength_uncertainty(h, 2021:2024, 3),
                    adl_strength_uncertainty(changed, 2021:2024, 3)))
# With no weekly noise, each team's offset persists across all future weeks.
set.seed(7); p <- adl_draw_future_points(rep(200,32), 0, 10, 6)
stopifnot(all(p == p[,1]), sd(p[,1]) > 0, all(p >= 0))
stopifnot(adl_strength_uncertainty(h, 2021:2024, 12)$sd == 0)
cat("Linear strength uncertainty tests passed.\n")
