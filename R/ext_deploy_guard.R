ext_source_fields <- c("season", "week", "official_week", "refreshed_at", "scores_md5")

assert_ext_source_identity <- function(bundled, latest) {
  if (nrow(bundled) != 1L || nrow(latest) != 1L ||
      !all(ext_source_fields %in% names(bundled)) ||
      !all(ext_source_fields %in% names(latest))) stop("Unverified EXT score publication metadata.")
  for (field in ext_source_fields) {
    if (!identical(as.character(bundled[[field]]), as.character(latest[[field]]))) {
      stop("EXT deployment source is stale or mismatched: ", field)
    }
  }
  invisible(NULL)
}

assert_ext_deployable <- function(check_remote = identical(Sys.getenv("GITHUB_ACTIONS"), "true")) {
  source("R/ext_score_publication.R")
  bundled <- read_ext_score_publication()
  if (is.null(bundled)) stop("EXT bundle integrity check failed; deployment blocked.")
  assert_ext_source_identity(bundled, read.csv("data/score_metadata.csv"))
  if (check_remote) {
    token <- Sys.getenv("ADL_GITHUB_WORKFLOW_TOKEN")
    headers <- c(Accept = "application/vnd.github+json", `Cache-Control` = "no-cache")
    if (nzchar(token)) headers <- c(headers, Authorization = paste("Bearer", token))
    response <- httr::GET("https://api.github.com/repos/TheMathNinja/ADL-GM-Dashboard/contents/data/score_metadata.csv?ref=main",
                          httr::add_headers(.headers = headers), httr::timeout(30))
    httr::stop_for_status(response)
    document <- httr::content(response, as = "parsed", encoding = "UTF-8")
    latest <- read.csv(text = rawToChar(jsonlite::base64_dec(document$content)))
    assert_ext_source_identity(bundled, latest)
  }
  message("EXT bundle verified against its confirmed source", if (check_remote) " and current main publication" else "", ".")
  invisible(NULL)
}
