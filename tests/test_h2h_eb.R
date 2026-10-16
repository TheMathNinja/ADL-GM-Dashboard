source("R/lineup_status.R")
m <- jsonlite::read_json("data/adl_scoring_model.json", simplifyVector=TRUE)[["2026"]]
f <- read.csv("tests/fixtures/h2h_eb_expected_means.csv")
for (w in unique(f$week)) {
  q <- f[f$week == w, ]
  mu <- adl_eb_scoring_mean(q$adjusted_potential,q$observed_ppg,w,2026,m,adjusted_ppg=q$adjusted_ppg)
  outlook <- read.csv("data/player_team_outlooks_2026.csv",colClasses=c(franchise_id="character"))
  expected <- outlook$forecast_mean[outlook$week==w]
  expected <- expected-mean(expected)+mean(q$observed_ppg)
  stopifnot(max(abs(mu-expected)) < 1e-9,
            abs(mean(mu)-mean(q$observed_ppg)) < 1e-10)
  stopifnot(max(abs(adl_eb_scoring_mean(q$adjusted_potential+50,q$observed_ppg,w,2026,m,adjusted_ppg=q$adjusted_ppg)-mu)) < 1e-9)
}
stopifnot(inherits(try(adl_eb_scoring_mean(1:2,1:2,4,2025,m),silent=TRUE),"try-error"),
          inherits(try(adl_eb_scoring_mean(c(1,NA),1:2,4,2026,m),silent=TRUE),"try-error"))
cat("H2H EB: exact research means, observed league level, centering and season guards verified.\n")
