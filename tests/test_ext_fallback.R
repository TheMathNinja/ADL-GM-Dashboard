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
cat("PASS: EXT fallback uses player IDs and repeated refreshes preserve row counts.\n")
