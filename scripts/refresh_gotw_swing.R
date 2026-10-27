# Calculation-only refresh: no Sheets, MFL writes, cap snapshot, or live report publication.
source("scripts/get_adl_playoff_picture.R")
metadata <- read.csv("data/score_metadata.csv")
stopifnot(nrow(metadata) == 1L, metadata$week >= 1L, metadata$week < 12L)
options(adl.score_status=metadata$status, adl.build_playoff_swing=TRUE)
scratch <- tempfile("gotw-forecast-")
dir.create(scratch)
snapshot <- run_adl_playoff_picture(as.numeric(metadata$season), as.numeric(metadata$week),
  out_dir=scratch, cache_dir=file.path(scratch,"history"), rebuild_archive=FALSE, n_sims=12000L)
swing <- attr(snapshot,"playoff_swing")
stopifnot(nrow(swing)==16L, all(is.finite(swing$combined_seed_swing)))
readr::write_csv(swing,"data/playoff_swing.csv")
message("Updated Game of the Week swing data only.")
