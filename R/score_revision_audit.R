score_revision_rows <- function(scores) {
  required <- c("season", "week", "player_id", "points")
  if (!all(required %in% names(scores))) stop("Score audit input is missing required columns.")
  rows <- as.data.frame(scores[, required], stringsAsFactors = FALSE)
  rows$player_id <- as.character(rows$player_id)
  rows$player_name <- if ("player_name" %in% names(scores)) as.character(scores$player_name) else rows$player_id
  rows <- unique(rows)
  key <- paste(rows$season, rows$week, rows$player_id, sep = ":")
  if (anyDuplicated(key)) stop("Conflicting duplicate player scores in score audit input.")
  rows
}

find_official_score_revisions <- function(before, after, season, official_week, scrape_week) {
  old <- score_revision_rows(before)
  new <- score_revision_rows(after)
  old <- old[old$season == season & old$week <= official_week, ]
  new <- new[new$season == season & new$week <= official_week, ]
  joined <- merge(old, new, by = c("season", "week", "player_id"), all = TRUE,
                  suffixes = c("_old", "_new"))
  a <- joined$points_old
  b <- joined$points_new
  changed <- xor(is.na(a), is.na(b)) | (!is.na(a) & !is.na(b) & abs(a - b) > 1e-8)
  result <- joined[changed, , drop = FALSE]
  result$scrape_week <- rep(as.integer(scrape_week), nrow(result))
  result
}

audit_official_score_revisions <- function(scores, season, scrape_week,
                                         metadata_path = "data/score_metadata.csv",
                                         baseline_path = "data/player_score_audit_baseline.csv",
                                         report_path = "data/official_score_revisions.csv") {
  metadata <- if (file.exists(metadata_path)) read.csv(metadata_path) else data.frame()
  official_week <- 0L
  if (nrow(metadata) == 1L && metadata$season[[1]] == season) {
    official_week <- if ("official_week" %in% names(metadata)) metadata$official_week[[1]] else 0L
  }
  if (is.na(official_week)) official_week <- 0L
  before <- NULL
  if (file.exists(baseline_path)) {
    before <- read.csv(baseline_path, colClasses = c(player_id = "character"))
  } else if (nrow(metadata) == 1L && "scores_path" %in% names(metadata) && file.exists(metadata$scores_path[[1]])) {
    before <- readRDS(metadata$scores_path[[1]])
  }
  if (!is.null(before)) {
    revisions <- find_official_score_revisions(before, scores, season, official_week, scrape_week)
    if (nrow(revisions)) {
      revisions$detected_at <- format(Sys.time(), tz = "UTC", usetz = TRUE)
      for (i in seq_len(nrow(revisions))) {
        row <- revisions[i, ]
        name <- if (!is.na(row$player_name_new)) row$player_name_new else row$player_name_old
        note <- sprintf("Week %s official score for %s (MFL %s) was changed in Week %s scrape: %s -> %s points",
                        row$week, name, row$player_id, scrape_week, row$points_old, row$points_new)
        warning(note, call. = FALSE, immediate. = TRUE)
        if (nzchar(Sys.getenv("GITHUB_ACTIONS"))) cat("::warning::", note, "\n", sep = "")
        summary <- Sys.getenv("GITHUB_STEP_SUMMARY")
        if (nzchar(summary)) cat("- ", note, "\n", file = summary, append = TRUE, sep = "")
      }
      history <- if (file.exists(report_path)) read.csv(report_path, colClasses = c(player_id = "character")) else revisions[0, ]
      write.csv(rbind(history, revisions), report_path, row.names = FALSE, na = "")
    }
  } else {
    message("Initializing player-score audit baseline; prior official scores cannot be compared on this first run.")
  }
  write.csv(score_revision_rows(scores), baseline_path, row.names = FALSE, na = "")
}
