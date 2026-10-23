Sys.setenv(ADL_GM_FORCE_LIVE_ROSTERS = "TRUE")

source("scripts/prepare_ext_data.R", local = new.env(parent = globalenv()))
source("scripts/prepare_cap_manager.R", local = new.env(parent = globalenv()))

message("Refreshed live rosters and rebuilt EXT and Salary Cap Manager data.")
