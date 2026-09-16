source("R/score_calendar.R")
dates <- as.Date(c("2026-09-14", "2026-09-15", "2026-09-17", "2026-09-22", "2026-09-24",
                   "2026-11-03", "2026-11-05", "2026-12-01", "2026-12-03"))
stopifnot(identical(vapply(dates, completed_score_week, integer(1), season = 2026L),
                    c(0L, 1L, 1L, 2L, 2L, 8L, 8L, 12L, 12L)))
cat("PASS: completed-week selection across Tuesdays, Thursdays, and DST.\n")
