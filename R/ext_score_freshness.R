assert_ext_score_cache_current <- function(metadata_path = "data/score_metadata.csv") {
  if (!file.exists(metadata_path)) return(invisible(NULL))
  metadata <- read.csv(metadata_path, stringsAsFactors = FALSE)
  if (nrow(metadata) != 1L || is.na(metadata$week[[1]])) stop("Invalid EXT source metadata.")
  if (metadata$week[[1]] < 1L) return(invisible(NULL))
  path <- metadata$scores_path[[1]]
  if (!file.exists(path)) stop("Published score source is missing; refusing to rebuild EXT ranks from an older cache: ", path)
  scores <- readRDS(path)
  weeks <- unique(as.integer(scores$week[scores$season == metadata$season[[1]]]))
  missing <- setdiff(seq_len(metadata$week[[1]]), weeks)
  if (length(missing)) stop("EXT source is missing published score weeks: ", paste(missing, collapse = ", "))
  invisible(NULL)
}

assert_ext_rank_week <- function(metadata, path = "data/pr_weekly_snapshots.csv") {
  ranks <- read.csv(path)
  weeks <- unique(as.integer(ranks$snapshot_week[ranks$season == metadata$season[[1]]]))
  missing <- setdiff(seq_len(metadata$week[[1]]), weeks)
  if (length(missing)) stop("EXT ranks do not cover published score weeks: ", paste(missing, collapse = ", "))
  invisible(NULL)
}
