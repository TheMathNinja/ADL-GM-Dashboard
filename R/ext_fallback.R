# Published fallback rows must identify players, not just matching surnames.
deduplicate_ext_fallback <- function(rows) {
  rows <- dplyr::distinct(rows)
  if (anyDuplicated(rows[c("conference", "player_id")])) {
    stop("Conflicting published EXT fallback inputs for the same player/conference.")
  }
  rows
}

download_ext_contract_admin <- function(path) {
  response <- httr::RETRY("GET", paste0("https://docs.google.com/spreadsheets/d/",
    "1Pyw8qVfiBlXNuX0lW0LdjRnBiijfbo2BXHfZMWwLLaw/export?format=xlsx"),
    httr::timeout(20), times = 2, terminate_on = c(401L, 403L, 404L), quiet = TRUE)
  httr::stop_for_status(response)
  writeBin(httr::content(response, as = "raw"), path)
}

read_ext_workbook_season <- function(path) {
  readxl::read_excel(path, sheet = "FT5YO $", range = "L2", col_names = FALSE,
                     .name_repair = "minimal")[[1]]
}

ext_workbook_name_key <- function(name, roster = FALSE) {
  name <- trimws(tolower(as.character(name)))
  pattern <- if (roster) "^([^,]+),\\s*([a-z]).*$" else "^([a-z])(?:[.][a-z])*[.]\\s*(.+)$"
  key <- sub(pattern, if (roster) "\\2|\\1" else "\\1|\\2", name, perl = TRUE)
  key[is.na(name) | !grepl(pattern, name, perl = TRUE)] <- NA_character_
  key
}

ext_workbook_join_keys <- c("conference", "franchise", "workbook_name_key", "prev_salary", "prev_years")

overlay_ext_workbook <- function(candidates, workbook) {
  if (is.null(workbook)) return(candidates)
  values <- setdiff(names(workbook), ext_workbook_join_keys)
  stopifnot(all(values %in% names(candidates)))
  candidates$workbook_name_key <- ext_workbook_name_key(candidates$player_name, roster = TRUE)
  found <- dplyr::rename_with(workbook, function(cols) paste0(cols, "_workbook"),
                              dplyr::all_of(values))
  joined <- dplyr::left_join(candidates, found, by = ext_workbook_join_keys,
                            relationship = "one-to-one", na_matches = "never")
  for (field in values) {
    source <- paste0(field, "_workbook")
    joined[[field]] <- dplyr::coalesce(joined[[source]], joined[[field]])
    joined[[source]] <- NULL
  }
  joined$workbook_name_key <- NULL
  joined
}

load_ext_workbook <- function(local_path, season, live, read_block,
                              download = download_ext_contract_admin, read_season = read_ext_workbook_season) {
  read_workbook <- function(path) {
    year <- read_season(path)
    if (length(year) != 1L || is.na(year) || as.character(year) != as.character(season)) {
      stop("Contract Admin workbook is for another season.")
    }
    nfc <- read_block(path, 1:25, "NFC")
    afc <- read_block(path, 27:51, "AFC")
    if (!nrow(nfc) || !nrow(afc)) stop("Contract Admin EXT requires both conference blocks.")
    dplyr::bind_rows(nfc, afc)
  }
  if (file.exists(local_path)) return(read_workbook(local_path))
  if (!live) return(NULL)

  path <- tempfile("contract-admin-ext-", fileext = ".xlsx")
  on.exit(unlink(path), add = TRUE)
  tryCatch({
    download(path)
    result <- read_workbook(path)
    message("Read verified live Contract Admin EXT inputs for ", season, ".")
    result
  }, error = function(e) NULL)
}
