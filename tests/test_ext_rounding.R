source("R/ext_engine.R")

stopifnot(identical(round_salary(20.765), 20.77))
stopifnot(identical(round_salary(-20.765), -20.77))

salary_curves <- data.frame(
  salary_source = "Jul1 Sal",
  position = c(rep("RB", 2), rep("TE", 4)),
  rank = c(7, 8, 1, 2, 3, 4),
  salary = c(21.20, 20.33, 22.66, 20.00, 18.50, 18.05),
  player = c("RB7", "RB8", "TE1", "TE2", "TE3", "TE4"),
  conference = NA_character_,
  stringsAsFactors = FALSE
)

# De'Von Achane's 2025 RB5 EPV: average RB7 and RB8 before the years
# adjustment, then smooth a one-year contract plus two extension years.
achane_epv <- performance_salary("RB", 5, salary_curves, week = 1)
stopifnot(identical(achane_epv, 20.77))

achane <- data.frame(
  player = "Achane, De'Von MIA RB",
  franchise = "LAR",
  conference = "NFC",
  prev_salary = 5.81,
  prev_years = 1,
  epv_current = 5.81,
  epv_recent = achane_epv,
  epv_previous = 15.40,
  pr_current_pos = "RB",
  pr_current_final = 28,
  pr_recent_pos = "RB",
  pr_recent_final = 5,
  pr_previous_pos = "RB",
  pr_previous_final = 9,
  stringsAsFactors = FALSE
)
achane_ext <- extension_breakdown(achane, 2, week = 1, salary_curves = salary_curves)
stopifnot(identical(achane_ext$extended_years_salary, 21.81))
stopifnot(identical(achane_ext$new_salary, 17.18))

# Tucker Kraft's TE1 elite extrapolation:
# 2 * avg(TE1, TE2) - avg(TE3, TE4) = 24.385 -> 24.39.
kraft_epv <- performance_salary("TE", 1, salary_curves, week = 2)
stopifnot(identical(kraft_epv, 24.39))

cat("EXT monetary rounding regression tests passed.\n")
