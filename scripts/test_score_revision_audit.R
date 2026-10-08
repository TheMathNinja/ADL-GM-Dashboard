source("R/score_revision_audit.R")
old <- data.frame(season = 2026L, week = c(2L, 4L), player_id = c("001", "002"),
                  player_name = c("Test Player", "Current Player"), points = c(12, 15))
new <- old
new$points <- c(13, 20)
changes <- find_official_score_revisions(old, new, 2026L, 2L, 5L)
stopifnot(nrow(changes) == 1L, changes$week == 2L, changes$points_old == 12,
          changes$points_new == 13, changes$scrape_week == 5L)
stopifnot(nrow(find_official_score_revisions(old, old, 2026L, 4L, 5L)) == 0L,
          nrow(find_official_score_revisions(old, new, 2027L, 4L, 5L)) == 0L)
removed <- find_official_score_revisions(old, new[-1, ], 2026L, 2L, 5L)
stopifnot(nrow(removed) == 1L, is.na(removed$points_new))
directory <- tempfile("score-audit-")
dir.create(directory)
metadata <- file.path(directory, "metadata.csv")
baseline <- file.path(directory, "baseline.csv")
report <- file.path(directory, "revisions.csv")
write.csv(data.frame(season = 2026L, official_week = 2L), metadata, row.names = FALSE)
audit_official_score_revisions(old, 2026L, 4L, metadata, baseline, report)
messages <- character()
withCallingHandlers(
  audit_official_score_revisions(new, 2026L, 5L, metadata, baseline, report),
  warning = function(w) {
    messages <<- c(messages, conditionMessage(w))
    invokeRestart("muffleWarning")
  }
)
stopifnot(length(messages) == 1L, grepl("Week 2 official score", messages),
          grepl("Week 5 scrape", messages), nrow(read.csv(report)) == 1L)
audit_official_score_revisions(new, 2026L, 5L, metadata, baseline, report)
stopifnot(nrow(read.csv(report)) == 1L)
cat("Score revision tests passed: historical corrections, unchanged scores, season isolation, and removed rows.\n")
