player_display_name <- function(name) {
  name <- trimws(as.character(name))
  if (!length(name) || is.na(name[[1]]) || !nzchar(name[[1]])) return("--")
  name <- name[[1]]
  if (!grepl(",", name)) return(name)
  parts <- trimws(strsplit(name, ",\\s*")[[1]])
  if (length(parts) < 2) return(name)
  trimws(paste(parts[[2]], parts[[1]]))
}

pr_rank_player_label <- function(name, team = NA_character_, position = NA_character_) {
  parts <- c(player_display_name(name), as.character(team), as.character(position))
  paste(parts[!is.na(parts) & nzchar(trimws(parts))], collapse = " ")
}
