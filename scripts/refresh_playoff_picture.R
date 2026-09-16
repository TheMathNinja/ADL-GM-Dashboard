# Run immediately after cache_current_scores.R in the shared score workflow.
source("scripts/get_adl_playoff_picture.R")

refresh_playoff_from_score_cache <- function(
    metadata_path = "data/score_metadata.csv",
    out_dir = file.path("docs", "playoff-picture"),
    cache_dir = file.path("cache", "playoff-picture"),
    n_sims = 3000L) {
  metadata <- read.csv(metadata_path, stringsAsFactors = FALSE)
  required <- c("season", "week", "starters_path", "refreshed_at", "status")
  if (nrow(metadata) != 1L || !all(required %in% names(metadata))) stop("Missing score-run metadata.")
  season <- as.integer(metadata$season)
  expected_season <- as.integer(Sys.getenv("CURRENT_SEASON", "2026"))
  if (is.na(season) || season != expected_season || is.na(metadata$week) || metadata$week < 1L) {
    stop("Score-run metadata has the wrong season or no completed week.")
  }
  if (!file.exists(metadata$starters_path)) stop("The score job's starter cache is missing.")
  week <- min(as.integer(metadata$week), adl_max_week)
  old_options <- options(adl.shared_starters = list(season = season, path = metadata$starters_path),
                         adl.output_dir = out_dir, adl.n_sims = n_sims,
                         adl.score_status = metadata$status)
  on.exit(options(old_options), add = TRUE)
  snapshot <- run_adl_playoff_picture(season, week, out_dir = out_dir, cache_dir = cache_dir,
                                     rebuild_archive = FALSE, n_sims = n_sims)
  # Fill missed weeks once, preserving already published historical snapshots.
  for (prior in seq_len(week - 1L)) {
    path <- file.path(out_dir, sprintf("ADL_%d_W%02d_playoff_and_draft_forecast.html", season, prior + 1L))
    if (!file.exists(path)) {
      previous <- get_adl_playoff_picture(season, prior)
      write_adl_week_html(previous, season, prior, through_week = week, repo_dir = out_dir)
    }
  }
  readr::write_csv(data.frame(season = season, through_week = week, score_status = metadata$status,
                            scores_refreshed_at = metadata$refreshed_at,
                            report_refreshed_at = format(Sys.time(), tz = "UTC", usetz = TRUE),
                            simulations = n_sims), file.path("data", "playoff_picture_metadata.csv"))
  message("Playoff report refreshed from ", metadata$status, " scores through Week ", week, ".")
  invisible(snapshot)
}

if (sys.nframe() == 0L) refresh_playoff_from_score_cache()
