library(dplyr)
library(readr)
root <- normalizePath(".")
source("R/ext_score_freshness.R")
source("R/ext_deploy_guard.R")
run_tests <- function() {
  dir <- tempfile("ext-integrity-")
  dir.create(dir)
  dir.create(file.path(dir, "R"))
  dir.create(file.path(dir, "data"))
  file.copy(file.path(root, "R/pr_history.R"), file.path(dir, "R/pr_history.R"))
  file.copy(file.path(root, "R/pr_completed_seasons.R"), file.path(dir, "R/pr_completed_seasons.R"))
  file.copy(file.path(root, "R/pr_partial_robust.R"), file.path(dir, "R/pr_partial_robust.R"))
  file.copy(file.path(root, "R/ext_score_freshness.R"), file.path(dir, "R/ext_score_freshness.R"))
  before <- getwd()
  on.exit(setwd(before))
  setwd(dir)
  Sys.setenv(ADL_RAW_LEAGUE_DATA_DIR = "cache", CURRENT_SEASON = "2026")
  assign("get_current_season", function() 2026L, envir = .GlobalEnv)
  dir.create("cache")
  schedule <- expand.grid(season = 2026L, week = 1:6, mfl_team = sprintf("T%02d", 1:32))
  schedule$is_bye <- FALSE
  write.csv(schedule, "data/nfl_schedule_2026.csv", row.names = FALSE)
  source("R/pr_history.R", local = .GlobalEnv)
  raw_path <- "cache/ff_playerscores_ADL26_2026_W1-6_raw.rds"
  scores <- data.frame(season = 2026L, week = rep(1:6, 2), player_id = rep(c("10700", "002"), each = 6),
    player_name = rep(c("Cousins, Kirk", "Other, Player"), each = 6), pos = "QB",
    team = rep(c("ATL", "BUF"), each = 6), points = c(7.8, 34.8, 33.5, 48, 25.5, 40.1, 1:6), is_available = "1")
  saveRDS(scores, raw_path)
  archive <- "data/confirmed_scores.rds"
  file.copy(raw_path, archive)
  metadata <- data.frame(season = 2026L, week = 6L, official_week = 5L, refreshed_at = "2026-10-20 04:02:16 UTC",
    scores_path = raw_path, scores_archive_path = archive, scores_md5 = unname(tools::md5sum(raw_path)))
  write.csv(metadata, "data/score_metadata.csv", row.names = FALSE)
  assert_ext_score_cache_current()
  # Both evicted caches and same-week stale corrections recover only from verified archive.
  unlink(raw_path)
  assert_ext_score_cache_current()
  stale <- scores; stale$points[6] <- 1
  saveRDS(stale, raw_path)
  assert_ext_score_cache_current()
  stopifnot(identical(readRDS(raw_path), scores))
  build_weekly_pr_snapshots("cache", 2026L)
  build_ext_pr_summary("cache", 2026L)
  summary <- read_csv("data/ext_pr_summary.csv", show_col_types = FALSE, col_types = cols(player_id = col_character()))
  candidates <- summary |>
    transmute(player_id, pr_current_pos, pr_current_gp_local = pr_current_gp,
              pr_current_total, pr_current_avg, pr_current_final)
  write_csv(candidates, "data/ext_candidates.csv")
  assert_ext_complete_build(metadata)
  stopifnot(summary$pr_current_gp[summary$player_id == "10700"] == 6)
  # Newer file timestamps must never legitimize an old current-season summary.
  old_summary <- summary; old_summary$pr_current_gp[1] <- 5
  write_csv(old_summary, "data/ext_pr_summary.csv")
  Sys.setFileTime("data/ext_pr_summary.csv", Sys.time() + 3600)
  rebuilt <- build_ext_pr_summary("cache", 2026L)
  stopifnot(all(rebuilt$pr_current_gp == 6))
  # An unrelated/future-named cache cannot outrank the explicitly confirmed source.
  future <- scores; future$week <- 17L
  saveRDS(future, "cache/ff_playerscores_ADL26_2026_W1-17_raw.rds")
  stopifnot(identical(latest_score_cache_file("cache", 2026L), raw_path))
  # Partial old-season caches cannot rewrite already-published historical seasons.
  history <- read_csv("data/pr_history.csv", show_col_types = FALSE, col_types = cols(player_id = col_character()))
  prior <- history[1, ]; prior$season <- 2025L; prior$gp <- 17; prior$total_points <- 1000; prior$ppg <- 1000 / 17
  write_csv(bind_rows(history, prior), "data/pr_history.csv")
  partial <- scores[1, ]; partial$season <- 2025L
  saveRDS(partial, "cache/ff_playerscores_ADL25_2025_W1-1_raw.rds")
  rebuilt_history <- build_robust_pr_history("cache", 2026L)
  stopifnot(rebuilt_history$gp[rebuilt_history$season == 2025L] == 17)
  assert_ext_complete_build(metadata)
  expect_failure <- function(expr) stopifnot(inherits(try(force(expr), silent = TRUE), "try-error"))
  snapshots <- read_csv("data/pr_weekly_snapshots.csv", show_col_types = FALSE, col_types = cols(player_id = col_character()))
  stopifnot(all(snapshots$player_team[snapshots$player_id == "10700"] == "ATL"),
    all(snapshots$player_team[snapshots$player_id == "002"] == "BUF"))
  write_csv(filter(snapshots, snapshot_week < 6), "data/pr_weekly_snapshots.csv")
  expect_failure(assert_ext_complete_build(metadata))
  write_csv(snapshots[-nrow(snapshots), ], "data/pr_weekly_snapshots.csv")
  expect_failure(assert_ext_complete_build(metadata))
  bad <- snapshots; bad$total_points[nrow(bad)] <- 0
  write_csv(bad, "data/pr_weekly_snapshots.csv")
  expect_failure(assert_ext_complete_build(metadata))
  write_csv(snapshots, "data/pr_weekly_snapshots.csv")
  bad_summary <- summary; bad_summary$pr_current_gp[1] <- 5
  write_csv(bad_summary, "data/ext_pr_summary.csv")
  expect_failure(assert_ext_complete_build(metadata))
  write_csv(summary, "data/ext_pr_summary.csv")
  bad_candidates <- candidates; bad_candidates$pr_current_gp_local[1] <- 5
  write_csv(bad_candidates, "data/ext_candidates.csv")
  expect_failure(assert_ext_complete_build(metadata))
  write_csv(candidates, "data/ext_candidates.csv")
  assert_ext_complete_build(metadata)
  newer <- metadata; newer$scores_md5 <- "later-stat-correction"
  expect_failure(assert_ext_source_identity(metadata, newer))
  newer <- metadata; newer$week <- 7L
  expect_failure(assert_ext_source_identity(metadata, newer))
  saveRDS(stale, archive); saveRDS(stale, raw_path)
  expect_failure(assert_ext_score_cache_current())
  cat("PASS: six-game regression; evicted/stale caches; same-week corrections; missing weeks/players; stale summaries/candidates; timestamp trap; future cache; historical preservation; newer source; corrupt archive.\n")
}
run_tests()
