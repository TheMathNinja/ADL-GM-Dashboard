Sys.setenv(ADL_GM_FORCE_LIVE_ROSTERS = "TRUE")

source("scripts/prepare_ext_data.R", local = new.env(parent = globalenv()))

message("Refreshed live rosters and rebuilt extension calculator data.")
