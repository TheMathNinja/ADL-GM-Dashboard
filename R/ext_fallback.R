# Published fallback rows must identify players, not just matching surnames.
deduplicate_ext_fallback <- function(rows) {
  rows <- dplyr::distinct(rows)
  if (anyDuplicated(rows[c("conference", "player_id")])) {
    stop("Conflicting published EXT fallback inputs for the same player/conference.")
  }
  rows
}
