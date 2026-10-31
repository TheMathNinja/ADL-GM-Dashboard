# Official NFL headshots. This identity map is independent of fantasy ownership.
gm_player_photo_urls <- local({
  file <- "data/nfl-player-photo-urls.json"
  urls <- if (file.exists(file)) tryCatch(jsonlite::fromJSON(file, simplifyVector = TRUE), error = function(e) list()) else list()
  urls
})
gm_player_photo <- function(id, fallback = NA_character_) {
  key <- as.character(id)
  photo <- if (key %in% names(gm_player_photo_urls)) gm_player_photo_urls[[key]] else NULL
  if (!is.null(photo) && length(photo) == 1L && !is.na(photo) && nzchar(photo)) return(sub("/f_auto,q_auto/", "/f_auto,q_auto,w_160,h_160,c_fill/", photo, fixed = TRUE))
  fallback
}
