if (!requireNamespace("rsconnect", quietly = TRUE)) {
  stop("Install rsconnect first: install.packages('rsconnect')", call. = FALSE)
}

options(repos = c(
  ffverse = "https://ffverse.r-universe.dev",
  CRAN = "https://cloud.r-project.org"
))

account <- Sys.getenv("SHINYAPPS_ACCOUNT", unset = "")
token <- Sys.getenv("SHINYAPPS_TOKEN", unset = "")
secret <- Sys.getenv("SHINYAPPS_SECRET", unset = "")
app_name <- Sys.getenv("SHINYAPPS_APP_NAME", unset = "adl-gm-dashboard")

if (!nzchar(account) || !nzchar(token) || !nzchar(secret)) {
  stop(
    "Missing shinyapps.io credentials. Set SHINYAPPS_ACCOUNT, SHINYAPPS_TOKEN, ",
    "and SHINYAPPS_SECRET before deploying.",
    call. = FALSE
  )
}

rsconnect::setAccountInfo(
  name = account,
  token = token,
  secret = secret
)

rsconnect::deployApp(
  appDir = ".",
  appName = app_name,
  appTitle = "ADL Extension Calculator",
  appFiles = c(
    "app.R",
    "DESCRIPTION",
    "R",
    "data/current_rosters.csv",
    "data/ext_candidates.csv",
    "data/ext_pr_summary.csv",
    "data/pr_history.csv",
    "data/roster_metadata.csv",
    "data/salary_curves.csv",
    "data/salary_snapshots/ff_rosters_ADL25_2025_amended.csv",
    "data/salary_snapshots/ff_rosters_ADL25_2025_amended.rds",
    "www"
  )
)
