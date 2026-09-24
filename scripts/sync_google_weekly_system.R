#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(googlesheets4)
  library(readr)
})

`%||%` <- function(x, y) if (is.null(x) || !length(x) || is.na(x) || !nzchar(x)) y else x
league <- toupper(Sys.getenv("LEAGUE", unset = commandArgs(trailingOnly = TRUE)[1] %||% "ADL"))

configs <- list(
  ADL = list(
    elo_id = "1iu7oJUQ8IEhHDTp5RiArK7oTD4-DmjTbI1xtOwuwRBI",
    elo_sheet = "Data", prefix = "26",
    source = "data/weekly_team_metrics.csv",
    score_cols = c(OPF = "offense_points", DPF = "defense_points", PPF = "potential_points", TPF = "total_points"),
    blocks = list(OPF = c(36L, 37L, 1L), DPF = c(70L, 71L, 1L), PPF = c(104L, 105L, 1L)),
    bonus_id = "1S3NrGPEGdA3zR3-VNLLS1dAbMYFzH5rt1Z4ROoCzekU"
  ),
  FAFL = list(
    elo_id = "1yWEzFx8hKhhlTQ47gacHSQXmZtPsX9k7hB2s6D6-g3k",
    elo_sheet = "2026", prefix = "",
    source = "data/current_weekly.csv",
    score_cols = c(OPF = "off", DPF = "deff", PPF = "potential", TPF = "points"),
    blocks = list(OPF = c(36L, 37L, 1L), DPF = c(36L, 37L, 20L), PPF = c(36L, 37L, 39L)),
    bonus_id = "1X5DJD6K2mAL93DpPtHshVnOo4f_mJRc1CE2phcTFnTE"
  )
)

if (!league %in% names(configs)) stop("LEAGUE must be ADL or FAFL.")
cfg <- configs[[league]]

credential_json <- Sys.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", unset = "")
if (!nzchar(credential_json)) stop("GOOGLE_SERVICE_ACCOUNT_JSON is not configured.")
credential_path <- tempfile(fileext = ".json")
writeLines(credential_json, credential_path, useBytes = TRUE)
on.exit(unlink(credential_path), add = TRUE)
gs4_auth(path = credential_path)

col_name <- function(index) {
  output <- character()
  while (index > 0) {
    output <- c(intToUtf8(65L + (index - 1L) %% 26L), output)
    index <- (index - 1L) %/% 26L
  }
  paste0(output, collapse = "")
}

read_row <- function(ss, sheet, row, last_col = "ZZ") {
  values <- read_sheet(ss, sheet = sheet, range = paste0("A", row, ":", last_col, row),
                       col_names = FALSE, .name_repair = "minimal")
  as.character(unlist(values[1, ], use.names = FALSE))
}

read_col <- function(ss, sheet, col, first_row, rows) {
  values <- read_sheet(ss, sheet = sheet,
                       range = paste0(col_name(col), first_row, ":", col_name(col), first_row + rows - 1L),
                       col_names = FALSE, .name_repair = "minimal")
  as.character(unlist(values[[1]], use.names = FALSE))
}

write_matrix <- function(ss, sheet, first_row, first_col, values) {
  range_write(ss, as.data.frame(values, check.names = FALSE), sheet = sheet,
              range = paste0(col_name(first_col), first_row), col_names = FALSE, reformat = FALSE)
}

scores <- read_csv(cfg$source, show_col_types = FALSE, col_types = cols(.default = col_character()))
scores$week <- as.integer(scores$week)
scores$season <- as.integer(scores$season)
through_week <- max(scores$week, na.rm = TRUE)
if (!is.finite(through_week) || through_week < 1L || through_week > 17L) stop("Invalid completed week.")
if (nrow(scores) != 32L * through_week) stop("Validated score snapshot must contain exactly 32 rows per completed week.")
if (anyDuplicated(scores[c("week", "franchise_name")])) stop("Duplicate team/week rows in score snapshot.")

for (metric in names(cfg$blocks)) {
  block <- cfg$blocks[[metric]]
  headers <- read_row(cfg$elo_id, cfg$elo_sheet, block[[1]])
  labels <- paste0(cfg$prefix, "W", seq_len(17L), metric)
  start <- match(labels[[1]], headers)
  if (is.na(start) || !identical(headers[start + 0:16], labels)) stop("Unexpected ", metric, " headers in ", league, " Elo workbook.")
  workbook_names <- read_col(cfg$elo_id, cfg$elo_sheet, block[[3]], block[[2]], 32L)
  if (length(unique(workbook_names)) != 32L) stop("Workbook team mapping changed for ", metric, ".")
  values <- matrix(NA_real_, nrow = 32L, ncol = through_week)
  for (week in seq_len(through_week)) {
    frame <- scores[scores$week == week, , drop = FALSE]
    values[, week] <- as.numeric(frame[[cfg$score_cols[[metric]]]][match(workbook_names, frame$franchise_name)])
  }
  if (any(!is.finite(values))) stop("Missing ", metric, " values after workbook team mapping.")
  write_matrix(cfg$elo_id, cfg$elo_sheet, block[[2]], start, values)
}

bonus_names <- read_col(cfg$bonus_id, "Alphabetical", 1L, 3L, 32L)
bonus_values <- matrix(NA_real_, nrow = 32L, ncol = through_week)
for (week in seq_len(through_week)) {
  frame <- scores[scores$week == week, , drop = FALSE]
  bonus_values[, week] <- as.numeric(frame[[cfg$score_cols[["TPF"]]]][match(bonus_names, frame$franchise_name)])
}
if (any(!is.finite(bonus_values))) stop("Missing Bonus Games totals after workbook team mapping.")
write_matrix(cfg$bonus_id, "Alphabetical", 3L, 75L, bonus_values)

# Read formula results only after all expected Elo cells are numeric. Google
# recalculation is usually immediate, but bounded polling avoids stale output.
elo_headers <- read_row(cfg$elo_id, cfg$elo_sheet, 1L)
elo_labels <- paste0(cfg$prefix, "W", 0:through_week, "Elo")
elo_cols <- match(elo_labels, elo_headers)
if (anyNA(elo_cols)) stop("Missing official Elo columns: ", paste(elo_labels[is.na(elo_cols)], collapse = ", "))
team_names <- read_col(cfg$elo_id, cfg$elo_sheet, 1L, 2L, 32L)

official <- NULL
for (attempt in 1:12) {
  parts <- lapply(seq_along(elo_cols), function(i) {
    raw <- read_col(cfg$elo_id, cfg$elo_sheet, elo_cols[[i]], 2L, 32L)
    data.frame(season = 2026L, week = i - 1L, franchise_name = team_names,
               elo = suppressWarnings(as.numeric(raw)), stringsAsFactors = FALSE)
  })
  candidate <- do.call(rbind, parts)
  if (all(is.finite(candidate$elo))) { official <- candidate; break }
  Sys.sleep(5)
}
if (is.null(official)) stop("Google Elo formulas did not produce complete numeric output through Week ", through_week, ".")

shadow_path <- "data/elo_shadow_ratings.csv"
shadow <- read_csv(shadow_path, show_col_types = FALSE)
comparison <- merge(
  official,
  shadow[c("season", "week", "franchise_name", "elo")],
  by = c("season", "week", "franchise_name"), all.x = TRUE, suffixes = c("_sheet", "_shadow")
)
comparison$absolute_difference <- abs(comparison$elo_sheet - comparison$elo_shadow)
comparison$within_tolerance <- is.finite(comparison$absolute_difference) & comparison$absolute_difference <= 0.001
write_csv(comparison, "data/elo_shadow_comparison.csv", na = "")
if (any(!comparison$within_tolerance)) {
  warning(sum(!comparison$within_tolerance), " Elo rows differ from the shadow engine; workbook results remain authoritative.")
}

official_output <- merge(
  shadow[setdiff(names(shadow), "elo")], official,
  by = c("season", "week", "franchise_name"), all.y = TRUE, sort = FALSE
)
official_output <- official_output[order(official_output$week, match(official_output$franchise_name, team_names)), ]
write_csv(official_output, "data/elo_ratings.csv", na = "")
write_csv(data.frame(
  league = league, season = 2026L, through_week = through_week,
  source_rows = nrow(scores), official_elo_rows = nrow(official),
  shadow_mismatches = sum(!comparison$within_tolerance),
  synced_at = format(Sys.time(), tz = "UTC", usetz = TRUE)
), "data/google_weekly_sync_metadata.csv", na = "")

message(league, " Google weekly system synchronized through Week ", through_week,
        "; official workbook Elo published; shadow mismatches: ", sum(!comparison$within_tolerance), ".")
