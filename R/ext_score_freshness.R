assert_ext_score_cache_current <- function(metadata_path = "data/score_metadata.csv") {
  if (!file.exists(metadata_path)) return(invisible(NULL))
  metadata <- read.csv(metadata_path, stringsAsFactors = FALSE)
  if (nrow(metadata) != 1L || is.na(metadata$week[[1]])) stop("Invalid EXT source metadata.")
  if (metadata$week[[1]] < 1L) return(invisible(NULL))
  path <- metadata$scores_path[[1]]
  if (!"scores_md5" %in% names(metadata) || is.na(metadata$scores_md5[[1]])) {
    stop("Score source has no confirmed scrape fingerprint.")
  }
  matches <- function(p) file.exists(p) && identical(unname(tools::md5sum(p)), metadata$scores_md5[[1]])
  if (!matches(path)) {
    archive <- if ("scores_archive_path" %in% names(metadata)) metadata$scores_archive_path[[1]] else NA_character_
    if (is.na(archive) || !matches(archive)) stop("Neither cached nor durable scores match the confirmed scrape.")
    dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
    if (!file.copy(archive, path, overwrite = TRUE) || !matches(path)) stop("Cannot restore verified score source.")
    message("Restored confirmed score source from durable publication, not a guessed cache.")
  }
  scores <- readRDS(path)
  weeks <- unique(as.integer(scores$week[scores$season == metadata$season[[1]]]))
  missing <- setdiff(seq_len(metadata$week[[1]]), weeks)
  if (length(missing)) stop("EXT source is missing published score weeks: ", paste(missing, collapse = ", "))
  invisible(NULL)
}

assert_ext_frame_matches <- function(actual, expected, keys, values, label) {
  columns <- c(keys, values)
  if (!all(columns %in% names(actual))) stop(label, " is missing required columns.")
  actual <- as.data.frame(actual[columns])
  expected <- as.data.frame(expected[columns])
  for (key in keys) {
    actual[[key]] <- as.character(actual[[key]])
    expected[[key]] <- as.character(expected[[key]])
  }
  if (anyDuplicated(actual[keys]) || anyDuplicated(expected[keys])) stop(label, " has duplicate player keys.")
  actual <- actual[do.call(order, actual[keys]), , drop = FALSE]
  expected <- expected[do.call(order, expected[keys]), , drop = FALSE]
  rownames(actual) <- rownames(expected) <- NULL
  if (!isTRUE(all.equal(actual, expected, tolerance = 1e-8, check.attributes = FALSE))) {
    stop(label, " disagrees with the confirmed player score source.")
  }
  invisible(NULL)
}

assert_ext_complete_build <- function(metadata) {
  assert_ext_score_cache_current()
  source("R/pr_history.R")
  scores <- readRDS(metadata$scores_path[[1]])
  scores <- scores[scores$season == metadata$season[[1]] & scores$week <= metadata$week[[1]] &
                     scores$pos %in% c("QB", "RB", "WR", "TE", "PK", "PN", "DT", "DE", "LB", "CB", "S"), ]
  if ("is_available" %in% names(scores)) scores <- scores[
    is.na(scores$is_available) | as.character(scores$is_available) %in% c("1", "TRUE", "true"), ]
  expected <- dplyr::bind_rows(lapply(seq_len(metadata$week[[1]]), function(w) {
    frame <- summarise_player_pr_scores(scores[scores$week <= w, ])
    frame <- dplyr::group_by(frame, .data$season, .data$pos)
    frame <- dplyr::mutate(frame,
      pr_total = round_rank_half(rank(-.data$total_points, na.last = "keep")),
      pr_avg = round_rank_half(rank(-.data$ppg, na.last = "keep")),
      pr_final = pmin(.data$pr_total, .data$pr_avg, na.rm = TRUE),
      robust_pr = .data$gp >= 8 & !is.na(.data$pr_final), snapshot_week = w)
    frame <- dplyr::ungroup(frame)
    if (w >= 17L) frame <- apply_completed_season_ppg_ranks(frame)
    frame
  }))
  snapshots <- readr::read_csv("data/pr_weekly_snapshots.csv", show_col_types = FALSE,
                              col_types = readr::cols(player_id = readr::col_character()))
  values <- c("gp", "total_points", "ppg", "pr_total", "pr_avg", "pr_final", "robust_pr")
  assert_ext_frame_matches(snapshots, expected, c("season", "snapshot_week", "player_id", "pos"), values, "Weekly EXT snapshots")
  latest <- expected[expected$snapshot_week == metadata$week[[1]], ]
  history <- readr::read_csv("data/pr_history.csv", show_col_types = FALSE,
                            col_types = readr::cols(player_id = readr::col_character()))
  assert_ext_frame_matches(history[history$season == metadata$season[[1]], ], latest,
                          c("season", "player_id", "pos"), values, "Current-season PR history")
  assert_ext_frame_matches(history, apply_completed_season_ppg_ranks(history),
                          c("season", "player_id", "pos"), c("pr_avg", "pr_final"), "Completed-season PPG ranks")
  summary <- readr::read_csv("data/ext_pr_summary.csv", show_col_types = FALSE,
                            col_types = readr::cols(player_id = readr::col_character()))
  summary <- summary[!is.na(summary$pr_current_season) & summary$pr_current_season == metadata$season[[1]], ]
  names(summary) <- sub("^pr_current_", "", names(summary))
  names(summary)[names(summary) == "total"] <- "pr_total"
  names(summary)[names(summary) == "avg"] <- "pr_avg"
  names(summary)[names(summary) == "final"] <- "pr_final"
  names(summary)[names(summary) == "robust"] <- "robust_pr"
  assert_ext_frame_matches(summary, latest, c("season", "player_id", "pos"),
                          c("gp", "pr_total", "pr_avg", "pr_final", "robust_pr"), "EXT player summary")
  candidates <- readr::read_csv("data/ext_candidates.csv", show_col_types = FALSE,
                               col_types = readr::cols(player_id = readr::col_character()))
  mapping <- c(pr_current_gp_local = "gp", pr_current_total = "pr_total",
               pr_current_avg = "pr_avg", pr_current_final = "pr_final")
  if (!all(c("player_id", "pr_current_pos", names(mapping)) %in% names(candidates))) stop("Incomplete EXT candidate rank fields.")
  index <- match(paste(candidates$player_id, candidates$pr_current_pos), paste(latest$player_id, latest$pos))
  for (field in names(mapping)) {
    actual <- as.numeric(candidates[[field]][!is.na(index)])
    target <- as.numeric(latest[[mapping[[field]]]][index[!is.na(index)]])
    if (any(is.na(actual) != is.na(target)) || any(abs(actual - target) > 1e-8, na.rm = TRUE)) {
      stop("EXT candidate ranks disagree with the confirmed scores: ", field)
    }
  }
  invisible(NULL)
}

assert_ext_rank_week <- function(metadata, path = "data/pr_weekly_snapshots.csv") {
  ranks <- read.csv(path)
  weeks <- unique(as.integer(ranks$snapshot_week[ranks$season == metadata$season[[1]]]))
  missing <- setdiff(seq_len(metadata$week[[1]]), weeks)
  if (length(missing)) stop("EXT ranks do not cover published score weeks: ", paste(missing, collapse = ", "))
  invisible(NULL)
}
