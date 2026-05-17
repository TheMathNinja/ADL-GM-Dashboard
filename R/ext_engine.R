round_salary <- function(x, digits = 2) {
  round(as.numeric(x), digits)
}

round_rank_half <- function(x) {
  round(as.numeric(x) * 2) / 2
}

pr_starter_floors_by_season <- list(
  `2026` = c(
    QB = 16, RB = 28, WR = 50, TE = 18, PK = 16, PN = 16,
    DT = 38, DE = 40, LB = 38, CB = 38, S = 38
  )
)

default_pr_starter_floor_season <- function() {
  as.integer(getOption("adl.pr_starter_floor_season", Sys.getenv("ADL_PR_STARTER_FLOOR_SEASON", "2026")))
}

ensure_pr_starter_floors_configured <- function(season) {
  if (is.null(pr_starter_floors_by_season[[as.character(season)]])) {
    stop(
      "PR Starter Floors for ", season,
      " are not configured yet. Ask Michael for the updated season floors before using the EXT calculator.",
      call. = FALSE
    )
  }
  invisible(TRUE)
}

starter_floor <- function(position, season = default_pr_starter_floor_season()) {
  ensure_pr_starter_floors_configured(season)
  floors <- pr_starter_floors_by_season[[as.character(season)]]
  if (is.null(position) || length(position) == 0 || is.na(position) || !position %in% names(floors)) {
    return(NA_real_)
  }
  unname(floors[[position]] %||% NA_real_)
}

`%||%` <- function(x, y) {
  if (is.null(x) || length(x) == 0 || is.na(x)) y else x
}

salary_lookup <- function(position, rank, salary_curves, salary_source = NULL) {
  if (is.na(position) || is.na(rank)) return(NA_real_)
  rows <- salary_curves[salary_curves$position == position, , drop = FALSE]
  if (!is.null(salary_source) && "salary_source" %in% names(rows)) {
    rows <- rows[rows$salary_source == salary_source, , drop = FALSE]
  }
  if (!nrow(rows)) return(NA_real_)

  exact <- rows[rows$rank == rank, "salary", drop = TRUE]
  if (length(exact) && !is.na(exact[1])) return(as.numeric(exact[1]))

  stats::approx(rows$rank, rows$salary, xout = rank, rule = 2, ties = "ordered")$y
}

salary_component_lookup <- function(position, rank, salary_curves, salary_source = NULL, source_multiplier = 1) {
  rows <- salary_curves[salary_curves$position == position, , drop = FALSE]
  if (!is.null(salary_source) && "salary_source" %in% names(rows)) {
    rows <- rows[rows$salary_source == salary_source, , drop = FALSE]
  }

  exact <- rows[rows$rank == rank, , drop = FALSE]
  if (nrow(exact)) {
    exact <- exact[1, , drop = FALSE]
    base_salary <- as.numeric(exact$salary[[1]])
    player <- if ("player" %in% names(exact)) exact$player[[1]] else paste0(position, rank)
    conference <- if ("conference" %in% names(exact)) exact$conference[[1]] else NA_character_
  } else {
    base_salary <- salary_lookup(position, rank, salary_curves, salary_source)
    player <- paste0("Interpolated ", position, rank)
    conference <- NA_character_
  }

  data.frame(
    position = position,
    rank = as.numeric(rank),
    player = player %||% paste0(position, rank),
    conference = conference %||% NA_character_,
    base_salary_raw = as.numeric(base_salary),
    adjusted_salary_raw = source_multiplier * as.numeric(base_salary),
    base_salary = round_salary(base_salary),
    adjusted_salary = round_salary(source_multiplier * base_salary),
    stringsAsFactors = FALSE
  )
}

salary_curve_context <- function(week = 1, as_of = Sys.Date(), salary_curves = NULL) {
  week <- as.numeric(week)
  july_first <- as.Date(paste0(format(as_of, "%Y"), "-07-01"))

  if (!is.na(week) && week == 0) {
    return(list(
      salary_source = "End25 Sal",
      source_multiplier = 1.1,
      estimated = FALSE,
      label = "oEXT curve"
    ))
  }

  if (as_of < july_first) {
    return(list(
      salary_source = "End25 Sal",
      source_multiplier = 1.1,
      estimated = TRUE,
      label = "Using 110% End25 Sal as iEXT estimate"
    ))
  }

  has_final_july1 <- is.null(salary_curves) ||
    any(salary_curves$salary_source == "Jul1 Sal", na.rm = TRUE)

  if (!has_final_july1) {
    return(list(
      salary_source = "End25 Sal",
      source_multiplier = 1.1,
      estimated = TRUE,
      label = "July 1 raw pending review: End25 Sal + 10%"
    ))
  }

  list(
    salary_source = "Jul1 Sal",
    source_multiplier = 1,
    estimated = FALSE,
    label = "July 1 salary curve"
  )
}

epv_salary_components <- function(position, pr, salary_curves, week = 1, floor_to_starter = TRUE) {
  if (is.na(position) || is.na(pr)) return(NULL)

  floor_rank <- starter_floor(position)
  eval_pr <- max(round_rank_half(pr), 1)
  if (isTRUE(floor_to_starter) && !is.na(floor_rank)) {
    eval_pr <- min(eval_pr, floor_rank, na.rm = TRUE)
  }

  curve_context <- salary_curve_context(week, salary_curves = salary_curves)
  salary_source <- curve_context$salary_source
  source_multiplier <- curve_context$source_multiplier

  if (eval_pr <= 1) {
    components <- do.call(
      rbind,
      lapply(
        c(1, 2, 3, 4),
        function(rank) {
          salary_component_lookup(position, rank, salary_curves, salary_source, source_multiplier)
        }
      )
    )
    top_avg <- mean(components$adjusted_salary[components$rank %in% c(1, 2)], na.rm = TRUE)
    next_avg <- mean(components$adjusted_salary[components$rank %in% c(3, 4)], na.rm = TRUE)

    return(list(
      eval_pr = eval_pr,
      formula_type = "elite_extrapolation",
      components = components,
      result = round_salary(2 * top_avg - next_avg),
      salary_source = salary_source,
      source_multiplier = source_multiplier,
      estimated = curve_context$estimated,
      label = curve_context$label
    ))
  }

  component_ranks <- c(2 * eval_pr - 3, 2 * eval_pr - 2)
  components <- do.call(
    rbind,
    lapply(
      component_ranks,
      function(rank) {
        salary_component_lookup(position, rank, salary_curves, salary_source, source_multiplier)
      }
    )
  )

  list(
    eval_pr = eval_pr,
    formula_type = "average",
    components = components,
    result = round_salary(mean(components$adjusted_salary, na.rm = TRUE)),
    salary_source = salary_source,
    source_multiplier = source_multiplier,
    estimated = curve_context$estimated,
    label = curve_context$label
  )
}

performance_salary <- function(position, pr, salary_curves, week = 1) {
  if (is.na(position) || is.na(pr)) return(NA_real_)

  floor_rank <- starter_floor(position)
  eval_pr <- min(max(round_rank_half(pr), 1), floor_rank, na.rm = TRUE)
  curve_context <- salary_curve_context(week, salary_curves = salary_curves)
  salary_source <- curve_context$salary_source
  source_multiplier <- curve_context$source_multiplier

  if (eval_pr <= 1) {
    sal_1 <- round_salary(source_multiplier * salary_lookup(position, 1, salary_curves, salary_source))
    sal_2 <- round_salary(source_multiplier * salary_lookup(position, 2, salary_curves, salary_source))
    sal_3 <- round_salary(source_multiplier * salary_lookup(position, 3, salary_curves, salary_source))
    sal_4 <- round_salary(source_multiplier * salary_lookup(position, 4, salary_curves, salary_source))
    return(round_salary(2 * mean(c(sal_1, sal_2), na.rm = TRUE) - mean(c(sal_3, sal_4), na.rm = TRUE)))
  }

  rank_a <- 2 * eval_pr - 3
  rank_b <- 2 * eval_pr - 2
  round_salary(mean(c(
    round_salary(source_multiplier * salary_lookup(position, rank_a, salary_curves, salary_source)),
    round_salary(source_multiplier * salary_lookup(position, rank_b, salary_curves, salary_source))
  ), na.rm = TRUE))
}

performance_salary_unfloored <- function(position, pr, salary_curves, week = 1) {
  if (is.na(position) || is.na(pr)) return(NA_real_)

  eval_pr <- max(round_rank_half(pr), 1)
  curve_context <- salary_curve_context(week, salary_curves = salary_curves)
  salary_source <- curve_context$salary_source
  source_multiplier <- curve_context$source_multiplier

  if (eval_pr <= 1) {
    sal_1 <- round_salary(source_multiplier * salary_lookup(position, 1, salary_curves, salary_source))
    sal_2 <- round_salary(source_multiplier * salary_lookup(position, 2, salary_curves, salary_source))
    sal_3 <- round_salary(source_multiplier * salary_lookup(position, 3, salary_curves, salary_source))
    sal_4 <- round_salary(source_multiplier * salary_lookup(position, 4, salary_curves, salary_source))
    return(round_salary(2 * mean(c(sal_1, sal_2), na.rm = TRUE) - mean(c(sal_3, sal_4), na.rm = TRUE)))
  }

  rank_a <- 2 * eval_pr - 3
  rank_b <- 2 * eval_pr - 2
  round_salary(mean(c(
    round_salary(source_multiplier * salary_lookup(position, rank_a, salary_curves, salary_source)),
    round_salary(source_multiplier * salary_lookup(position, rank_b, salary_curves, salary_source))
  ), na.rm = TRUE))
}

discount_multiplier <- function(ext_years) {
  1.15 - 0.05 * as.numeric(ext_years)
}

annuity_factor <- function(years) {
  years <- as.numeric(years)
  if (is.na(years) || years <= 0) return(0)
  sum(1.1^(seq_len(floor(years)) - 1), na.rm = TRUE)
}

has_fifth_year_option <- function(fifth_year_option) {
  fifth_year_option <- suppressWarnings(as.numeric(fifth_year_option[[1]] %||% NA_real_))
  !is.na(fifth_year_option) && fifth_year_option > 0
}

smooth_contract_salary <- function(prev_salary, current_years, ext_years, extended_years_salary, week = 0, fifth_year_option = NA_real_) {
  current_years <- as.numeric(current_years)
  ext_years <- as.numeric(ext_years)
  week <- max(0, min(17, as.numeric(week)))
  total_years <- current_years + ext_years
  has_5yo <- has_fifth_year_option(fifth_year_option)
  fifth_year_option <- suppressWarnings(as.numeric(fifth_year_option[[1]] %||% NA_real_))

  if (!is.na(ext_years) && ext_years <= 0) return(round_salary(prev_salary))
  if (is.na(total_years) || total_years <= 0) return(NA_real_)
  if (is.na(extended_years_salary)) return(NA_real_)

  week_fraction <- week / 17
  denominator <- annuity_factor(total_years) - week_fraction
  if (denominator <= 0) return(NA_real_)

  numerator <- prev_salary * annuity_factor(current_years) - prev_salary * week_fraction

  if (has_5yo) {
    numerator <- numerator +
      fifth_year_option +
      (extended_years_salary * 1.1^(current_years + 1)) * annuity_factor(ext_years - 1)
  } else {
    numerator <- numerator +
      (extended_years_salary * 1.1^current_years) * annuity_factor(ext_years)
  }

  round_salary(numerator / denominator)
}

extension_breakdown <- function(player_row, ext_years, week = 1, salary_curves, sd_minimum = 2.01, fifth_year_option = NA_real_) {
  prev_salary <- as.numeric(player_row$prev_salary)
  current_years <- as.numeric(player_row$prev_years)
  ext_years <- as.numeric(ext_years)
  has_5yo <- has_fifth_year_option(fifth_year_option)
  fifth_year_option <- suppressWarnings(as.numeric(fifth_year_option[[1]] %||% NA_real_))

  epv_current <- as.numeric(player_row$epv_current %||% NA_real_)
  epv_recent <- as.numeric(player_row$epv_recent %||% NA_real_)
  epv_previous <- as.numeric(player_row$epv_previous %||% NA_real_)

  current_pos <- player_row$pr_current_pos %||% player_row$player_pos
  current_pr <- player_row$pr_current_final %||% starter_floor(current_pos)

  if (is.na(epv_current)) epv_current <- performance_salary(current_pos, current_pr, salary_curves, week)
  if (is.na(epv_recent)) epv_recent <- performance_salary(player_row$pr_recent_pos, player_row$pr_recent_final, salary_curves, week)
  if (is.na(epv_previous)) epv_previous <- performance_salary(player_row$pr_previous_pos, player_row$pr_previous_final, salary_curves, week)

  prior_floor <- 0.75 * prev_salary
  base_epv <- max(c(epv_current, epv_recent, epv_previous, prior_floor), na.rm = TRUE)
  has_extension_years <- !is.na(ext_years) && ext_years > 0
  discount_years <- if (has_extension_years) max(ext_years - as.integer(has_5yo), 0) else NA_real_
  eys_raw <- if (has_extension_years) base_epv * discount_multiplier(discount_years) else NA_real_
  eys <- if (has_extension_years) max(round_salary(eys_raw), sd_minimum, na.rm = TRUE) else NA_real_
  smoothed <- max(
    smooth_contract_salary(prev_salary, current_years, ext_years, eys, week = week, fifth_year_option = fifth_year_option),
    sd_minimum,
    na.rm = TRUE
  )

  total_years <- current_years + ext_years
  hit_year_cap <- total_years > 6
  final_years <- min(total_years, 6)

  data.frame(
    player = player_row$player,
    franchise = player_row$franchise,
    conference = player_row$conference,
    week = week,
    prev_salary = round_salary(prev_salary),
    current_years = current_years,
    requested_ext_years = ext_years,
    fifth_year_option = if (has_5yo) round_salary(fifth_year_option) else NA_real_,
    final_years = final_years,
    epv_current = round_salary(epv_current),
    epv_recent = round_salary(epv_recent),
    epv_previous = round_salary(epv_previous),
    prior_salary_floor = round_salary(prior_floor),
    base_epv = round_salary(base_epv),
    discount_years = discount_years,
    discount_multiplier = if (has_extension_years) round_salary(discount_multiplier(discount_years), 3) else NA_real_,
    extended_years_salary = round_salary(eys),
    new_salary = round_salary(smoothed),
    hit_year_cap = hit_year_cap,
    hit_sd_minimum = smoothed <= sd_minimum || (has_extension_years && eys <= sd_minimum),
    stringsAsFactors = FALSE
  )
}

salary_timeline <- function(player_row, ext_years, salary_curves, week = 1, sd_minimum = 2.01, fifth_year_option = NA_real_) {
  result <- extension_breakdown(
    player_row,
    ext_years,
    week = week,
    salary_curves = salary_curves,
    sd_minimum = sd_minimum,
    fifth_year_option = fifth_year_option
  )
  current_years <- as.numeric(player_row$prev_years)
  ext_years <- as.numeric(ext_years)
  week <- max(0, min(17, as.numeric(week)))
  prev_salary <- as.numeric(player_row$prev_salary)
  has_5yo <- has_fifth_year_option(fifth_year_option)
  fifth_year_option <- suppressWarnings(as.numeric(fifth_year_option[[1]] %||% NA_real_))

  rows <- list()
  add_row <- function(year, year_label, year_type, original_salary, escalated_original,
                      escalated_smoothed, bridge_power, include_total = TRUE,
                      original_formula_factor = NA_character_,
                      smoothed_formula_factor = NA_character_) {
    rows[[length(rows) + 1]] <<- data.frame(
      year = as.numeric(year),
      year_label = as.character(year_label),
      year_type = year_type,
      original_salary = round_salary(original_salary),
      smoothed_salary = round_salary(result$new_salary),
      escalated_original = round_salary(escalated_original),
      escalated_smoothed = round_salary(escalated_smoothed),
      bridge_power = bridge_power,
      include_total = include_total,
      original_formula_factor = original_formula_factor,
      smoothed_formula_factor = smoothed_formula_factor,
      stringsAsFactors = FALSE
    )
  }
  week_span_label <- function(start_week, end_week) {
    if (start_week == end_week) {
      paste0("week ", start_week)
    } else {
      paste0("weeks ", start_week, "-", end_week)
    }
  }

  week_fraction <- week / 17
  if (current_years >= 1) {
    if (week_fraction > 0) {
      add_row(
        1,
        "1a",
        paste0("(pre-EXT) ", week_span_label(1, week)),
        prev_salary * week_fraction,
        prev_salary * week_fraction,
        prev_salary * week_fraction,
        0,
        include_total = FALSE,
        original_formula_factor = paste0(week, "/17")
      )
    }

    post_fraction <- 1 - week_fraction
    if (post_fraction > 0) {
      add_row(
        1,
        if (week_fraction > 0) "1b" else "1",
        if (week_fraction > 0) paste0("(post-EXT) ", week_span_label(week + 1, 17)) else "current contract",
        prev_salary * post_fraction,
        prev_salary * post_fraction,
        result$new_salary * post_fraction,
        0,
        include_total = TRUE,
        original_formula_factor = if (week_fraction > 0) paste0(17 - week, "/17") else NA_character_,
        smoothed_formula_factor = if (week_fraction > 0) paste0(17 - week, "/17") else NA_character_
      )
    }
  }

  if (current_years >= 2) {
    for (year in 2:floor(current_years)) {
      power <- year - 1
      add_row(
        year,
        as.character(year),
        "current contract",
        prev_salary,
        prev_salary * 1.1^power,
        result$new_salary * 1.1^power,
        power,
        include_total = TRUE
      )
    }
  }

  if (ext_years > 0) {
    next_year <- floor(current_years) + 1

    if (has_5yo) {
      power <- floor(current_years)
      add_row(
        next_year,
        as.character(next_year),
        "5th year option",
        fifth_year_option / 1.1^power,
        fifth_year_option,
        result$new_salary * 1.1^power,
        power,
        include_total = TRUE
      )
      next_year <- next_year + 1
    }

    ext_count <- max(ext_years - as.integer(has_5yo), 0)
    if (ext_count > 0) {
      for (offset in seq_len(ext_count)) {
        power <- floor(current_years) + as.integer(has_5yo) + offset - 1
        add_row(
          floor(current_years) + as.integer(has_5yo) + offset,
          as.character(floor(current_years) + as.integer(has_5yo) + offset),
          "extended years",
          result$extended_years_salary,
          result$extended_years_salary * 1.1^power,
          result$new_salary * 1.1^power,
          power,
          include_total = TRUE
        )
      }
    }
  }

  if (!length(rows)) {
    return(data.frame(
      year = numeric(),
      year_label = character(),
      year_type = character(),
      original_salary = numeric(),
      smoothed_salary = numeric(),
      escalated_original = numeric(),
      escalated_smoothed = numeric(),
      bridge_power = numeric(),
      include_total = logical(),
      original_formula_factor = character(),
      smoothed_formula_factor = character(),
      stringsAsFactors = FALSE
    ))
  }

  do.call(rbind, rows)
}
