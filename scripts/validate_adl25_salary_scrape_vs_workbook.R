library(readxl)
library(dplyr)
library(readr)

source("R/roster_source.R")
source("R/salary_snapshots.R")

source_path <- file.path("data", "source", "contract_admin_2026.xlsx")
if (!file.exists(source_path)) {
  stop("Missing ", source_path)
}

read_salary_curve_workbook <- function(path, sheet) {
  raw <- read_excel(path, sheet = sheet, col_names = FALSE)
  position_cols <- data.frame(
    position = c("QB", "RB", "WR", "TE", "PK/PN", "PK", "PN", "DT", "DE", "LB", "CB", "S"),
    player_col = c(2, 6, 10, 14, 18, 22, 26, 30, 34, 38, 42, 46),
    stringsAsFactors = FALSE
  )

  bind_rows(lapply(seq_len(nrow(position_cols)), function(i) {
    pos <- position_cols$position[i]
    start <- position_cols$player_col[i]
    rank_col <- names(raw)[1]
    player_col <- names(raw)[start]
    conf_col <- names(raw)[start + 1]
    salary_col <- names(raw)[start + 2]

    raw |>
      slice(-(1:2)) |>
      transmute(
        position = .env$pos,
        rank = as.numeric(.data[[rank_col]]),
        workbook_player = as.character(.data[[player_col]]),
        workbook_conference = as.character(.data[[conf_col]]),
        workbook_salary = as.numeric(.data[[salary_col]])
      ) |>
      filter(!is.na(.data$rank), !is.na(.data$workbook_salary))
  }))
}

scrape_curve <- salary_curve_from_rosters(
  read_amended_ff_rosters(2025),
  salary_source = "ADL25 ff_rosters scrape amended",
  max_contract_year = 2025
) |>
  transmute(
    position,
    rank,
    scrape_player = player,
    scrape_conference = conference,
    scrape_salary = salary
  )

workbook_curve <- read_salary_curve_workbook(source_path, "End25 Sal")

comparison <- full_join(
  workbook_curve,
  scrape_curve,
  by = c("position", "rank")
) |>
  mutate(
    salary_diff = round(scrape_salary - workbook_salary, 4),
    player_match = coalesce(workbook_player == scrape_player, FALSE),
    conference_match = coalesce(workbook_conference == scrape_conference, FALSE),
    differs = is.na(.data$salary_diff) | abs(.data$salary_diff) > 0.005 | !.data$player_match | !.data$conference_match
  ) |>
  arrange(position, rank)

dir.create("data", showWarnings = FALSE, recursive = TRUE)
write_csv(comparison, file.path("data", "salary_curve_validation_adl25_vs_workbook.csv"), na = "")

summary <- comparison |>
  group_by(position) |>
  summarise(
    rows = n(),
    differences = sum(.data$differs, na.rm = TRUE),
    max_abs_salary_diff = max(abs(.data$salary_diff), na.rm = TRUE),
    .groups = "drop"
  )

print(summary, n = Inf)

salary_summary <- comparison |>
  filter(.data$rank >= 1) |>
  group_by(position) |>
  summarise(
    rows = n(),
    salary_differences = sum(!is.na(.data$salary_diff) & abs(.data$salary_diff) > 0.01),
    max_abs_salary_diff = suppressWarnings(max(abs(.data$salary_diff), na.rm = TRUE)),
    .groups = "drop"
  )

cat("\nRank-level salary differences only (rank >= 1, tolerance > $0.01m):\n")
print(salary_summary, n = Inf)
cat("Wrote data/salary_curve_validation_adl25_vs_workbook.csv\n")
