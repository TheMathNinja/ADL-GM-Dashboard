# Use the same MFL player IDs as the roster scrape; availability is conference-specific.
build_free_agent_rosters <- function(catalog, rosters, season, availability) {
  catalog <- tibble::as_tibble(catalog)
  column <- function(options) {
    hit <- intersect(options, names(catalog))
    if (!length(hit)) stop("Missing MFL player catalog column: ", options[[1]])
    as.character(catalog[[hit[[1]]]])
  }
  players <- tibble::tibble(
    player_id = column(c("player_id", "id")),
    player_name = column(c("player_name", "name")),
    player_team = column(c("team", "player_team")),
    player_pos = column(c("pos", "position"))
  ) |>
    dplyr::filter(player_pos %in% c("QB", "RB", "WR", "TE", "PK", "PN", "DT", "DE", "LB", "CB", "S")) |>
    dplyr::distinct(player_id, .keep_all = TRUE)
  dplyr::bind_rows(lapply(c("AFC", "NFC"), function(conf) {
    players |>
      dplyr::semi_join(dplyr::filter(availability, conference == conf), by = "player_id") |>
      dplyr::anti_join(dplyr::filter(rosters, conference == conf), by = "player_id") |>
      dplyr::mutate(
        conference = conf, franchise = "Free Agents", franchise_name = "Free Agents",
        player = paste(player_name, player_team, player_pos),
        roster_status = "Free Agent", prev_salary = NA_real_, prev_years = 1,
        contract = paste(season, "UFA")
      )
  }))
}

fetch_free_agent_rosters <- function(rosters, season) {
  conn <- connect_adl_mfl(season)
  catalog <- ffscrapr::mfl_players(conn)
  league <- ffscrapr::mfl_getendpoint(conn, "league")$content$league
  conferences <- league$conferences$conference
  units <- ffscrapr::mfl_getendpoint(conn, "freeAgents")$content$freeAgents$leagueUnit
  if (!length(conferences) || !length(units)) stop("MFL returned no conference free-agent pools.")
  availability <- dplyr::bind_rows(lapply(conferences, function(conf) {
    unit <- Filter(function(x) identical(x$unit, paste0("CONFERENCE", conf$id)), units)
    if (length(unit) != 1L) stop("Missing MFL free-agent pool for ", conf$name)
    tibble::tibble(
      conference = conf$name,
      player_id = vapply(unit[[1]]$player, function(x) as.character(x$id), character(1))
    )
  }))
  build_free_agent_rosters(catalog, rosters, season, availability)
}

apply_free_agent_terms <- function(row, salary, years) {
  salary <- suppressWarnings(as.numeric(salary))
  years <- suppressWarnings(as.numeric(years))
  if (length(salary) != 1L || is.na(salary) || !is.finite(salary) || salary <= 0 ||
      length(years) != 1L || is.na(years) || !years %in% 1:6) {
    return(NULL)
  }
  row$prev_salary <- salary
  row$prev_years <- years
  row
}
