library(dplyr)
source("R/ext_fallback.R")
# Jalen Davis and Ray Davis share a surname, team, salary and contract length.
# Repeated refreshes must neither cross-match them nor multiply cached rows.
rosters <- tibble(conference = "NFC", franchise = "CAR",
                  player_id = c("14037", "16603"), roster_last = "davis",
                  prev_salary = 1.1, prev_years = 1)
fallback <- rosters |> select(-roster_last) |> mutate(ext_years = c(2, 3))
duplicated <- bind_rows(fallback, fallback, fallback)
keys <- c("conference", "franchise", "player_id", "prev_salary", "prev_years")
result <- left_join(rosters, deduplicate_ext_fallback(duplicated),
                    by = keys, relationship = "many-to-one")
stopifnot(nrow(result) == 2L, identical(result$ext_years, c(2, 3)))
again <- left_join(rosters, deduplicate_ext_fallback(result |> select(-roster_last)),
                   by = keys, relationship = "many-to-one")
stopifnot(identical(result, again))
conflict <- bind_rows(fallback, mutate(fallback[1, ], ext_years = 1))
stopifnot(inherits(try(deduplicate_ext_fallback(conflict), silent = TRUE), "try-error"))
missing <- tempfile()
downloaded <- NULL
fetch <- function(path) {
  downloaded <<- path
  writeLines("test workbook placeholder", path)
}
block <- function(path, columns, conference) {
  stopifnot(file.exists(path))
  tibble(conference = conference)
}
from_live <- load_ext_workbook(missing, 2026L, TRUE, block, fetch, function(...) 2026L)
stopifnot(identical(from_live$conference, c("NFC", "AFC")), !file.exists(downloaded))
stopifnot(is.null(load_ext_workbook(missing, 2026L, FALSE, block, function(...) stop("do not fetch"))))
stopifnot(is.null(load_ext_workbook(missing, 2026L, TRUE, block, fetch, function(...) 2025L)),
          !file.exists(downloaded))
stopifnot(is.null(load_ext_workbook(missing, 2026L, TRUE, function(...) tibble(), fetch, function(...) 2026L)),
          !file.exists(downloaded))
stopifnot(is.null(load_ext_workbook(missing, 2026L, TRUE, block, function(...) stop("HTTP failure"))))
stopifnot(identical(ext_workbook_name_key(c("J. Davis", "R. Davis", "D.J. Moore", "Davis")),
                    c("j|davis", "r|davis", "d|moore", NA_character_)),
          identical(ext_workbook_name_key(c("Davis, Jalen", "Davis, Ray", "Moore, D.J."), roster = TRUE),
                    c("j|davis", "r|davis", "d|moore")))
calculated <- mutate(fallback, player_name = c("Davis, Jalen", "Davis, Ray"))
workbook <- tibble(conference = "NFC", franchise = "CAR", workbook_name_key = "j|davis",
                   prev_salary = 1.1, prev_years = 1, ext_years = 4)
stopifnot(identical(overlay_ext_workbook(calculated, workbook)$ext_years, c(4, 3)),
          identical(overlay_ext_workbook(calculated, mutate(workbook, prev_years = 2)), calculated),
          inherits(try(overlay_ext_workbook(calculated, bind_rows(workbook, workbook)), silent = TRUE), "try-error"))

# Optional read-only smoke test of the existing export and the production parser.
fixture <- Sys.getenv("EXT_VERIFY_WORKBOOK")
if (nzchar(fixture)) {
  library(readxl)
  source("R/nfl_teams.R")
  for (expr in parse("scripts/prepare_ext_data.R")) {
    if (is.call(expr) && identical(expr[[1]], as.name("<-")) &&
        identical(expr[[2]], as.name("read_ext_block"))) eval(expr)
  }
  current <- load_ext_workbook(fixture, 2026L, FALSE, read_ext_block)
  stopifnot(all(c("NFC", "AFC") %in% current$conference))
  keys <- c("conference", "franchise", "workbook_name_key", "prev_salary", "prev_years")
  current <- mutate(current, workbook_name_key = ext_workbook_name_key(player))
  baseline <- readr::read_csv("data/ext_candidates.csv", show_col_types = FALSE) |>
    mutate(workbook_name_key = ext_workbook_name_key(player_name, roster = TRUE))
  matched <- inner_join(current, baseline, by = keys, relationship = "one-to-one", na_matches = "never")
  stopifnot(all(c("NFC", "AFC") %in% current$conference))
  cat("Live export schema validated; EXT rows:", nrow(current),
      "; current-contract matches:", nrow(matched), "\n")
}
cat("PASS: EXT fallback uses player IDs and repeated refreshes preserve row counts.\n")
