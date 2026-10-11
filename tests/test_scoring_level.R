source("R/lineup_status.R")
mu <- c(175, 200, 225); observed <- c(180, 190, 215)
z <- adl_observed_league_level(mu, observed)
stopifnot(abs(mean(z) - mean(observed)) < 1e-12,
          all(abs((z - mean(z)) - (mu - mean(mu))) < 1e-12),
          all(abs(outer(z,z,"-") - outer(mu,mu,"-")) < 1e-12))
stopifnot(identical(adl_observed_league_level(mu,mu),mu))
stopifnot(inherits(try(adl_observed_league_level(c(1,NA),c(1,2)),silent=TRUE),"try-error"))
code <- paste(readLines("scripts/get_adl_playoff_picture.R"),collapse="\n")
stopifnot(grepl("curr_teams <- apply_lineup_status",code,fixed=TRUE),
          grepl("adl_observed_league_level(curr_teams$mu_pts, curr_teams$avg_pf)",code,fixed=TRUE))
cat("Observed league scoring level tests passed.\n")
