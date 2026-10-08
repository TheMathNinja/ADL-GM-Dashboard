ext_score_rank_files <- c("data/ext_candidates.csv", "data/ext_pr_summary.csv",
                          "data/pr_history.csv", "data/pr_weekly_snapshots.csv")

write_ext_score_publication <- function(metadata_path = "data/score_metadata.csv",
                                        receipt_path = "data/ext_score_publication.rds",
                                        rank_files = ext_score_rank_files) {
  if (!file.exists(metadata_path)) return(invisible(NULL))
  metadata <- read.csv(metadata_path, stringsAsFactors = FALSE)
  if (nrow(metadata) != 1L || !all(c("season", "week", "official_week") %in% names(metadata))) {
    stop("EXT publication requires valid score metadata.")
  }
  if (!all(file.exists(rank_files))) stop("EXT publication is missing rank outputs.")
  receipt <- list(metadata = metadata, hashes = tools::md5sum(rank_files),
                  built_at = format(Sys.time(), tz = "UTC", usetz = TRUE))
  saveRDS(receipt, receipt_path)
}

read_ext_score_publication <- function(receipt_path = "data/ext_score_publication.rds") {
  if (!file.exists(receipt_path)) return(NULL)
  tryCatch({
    receipt <- readRDS(receipt_path)
    files <- names(receipt$hashes)
    if (!length(files) || !all(file.exists(files)) ||
        !identical(tools::md5sum(files), receipt$hashes)) return(NULL)
    receipt$metadata
  }, error = function(e) NULL)
}
