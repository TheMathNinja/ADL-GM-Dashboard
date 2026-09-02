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
app_name <- Sys.getenv("SHINYAPPS_APP_NAME", unset = "adl-ext-calculator")

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

github_workflow_token <- Sys.getenv("ADL_GITHUB_WORKFLOW_TOKEN", unset = "")
if (nzchar(github_workflow_token)) {
  dir.create("secrets", showWarnings = FALSE, recursive = TRUE)
  writeLines(github_workflow_token, file.path("secrets", "github_workflow_token.txt"))
}

app_files <- c(
  "app.R",
  "DESCRIPTION",
  list.files("R", full.names = TRUE, recursive = TRUE),
  list.files("scripts", full.names = TRUE, recursive = TRUE),
  "data/current_rosters.csv",
  "data/ext_candidates.csv",
  "data/ext_pr_summary.csv",
  "data/pr_history.csv",
  "data/roster_metadata.csv",
  "data/salary_curves.csv",
  "data/salary_snapshots/ff_rosters_ADL25_2025_amended.csv",
  "data/salary_snapshots/ff_rosters_ADL25_2025_amended.rds",
  list.files("www", full.names = TRUE, recursive = TRUE)
)

if (file.exists(file.path("secrets", "github_workflow_token.txt"))) {
  app_files <- c(app_files, file.path("secrets", "github_workflow_token.txt"))
}

rsconnect::deployApp(
  appDir = ".",
  appName = app_name,
  appTitle = "ADL Extension Calculator",
  forceUpdate = TRUE,
  appFiles = app_files
)
