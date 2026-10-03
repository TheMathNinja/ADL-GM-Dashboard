# Shared GM identity and completed-career calculations for every dashboard view.
# Franchise IDs identify a team's season, never a GM's career.
adl_gm_aliases <- local({
  value <- NULL
  function() {
    if (is.null(value)) value <<- unlist(jsonlite::fromJSON('data/gm_name_aliases.json'), use.names=TRUE)
    value
  }
})
adl_gm_people <- function(name) {
  aliases <- adl_gm_aliases()
  people <- trimws(unlist(strsplit(name, ',', fixed=TRUE)))
  people <- people[nzchar(people)]
  ix <- match(tolower(people), tolower(names(aliases)))
  people[!is.na(ix)] <- unname(aliases[ix[!is.na(ix)]])
  unique(people)
}

adl_gm_history <- function() {
  h <- jsonlite::fromJSON('data/gm_career_seasons.json')
  stopifnot(!anyDuplicated(paste(h$season,h$franchise_id)), !anyNA(h[c('wins','losses','ties')]))
  for (year in unique(h$season)) {
    s <- h[h$season==year,]
    stopifnot(nrow(s)==32L, sum(s$wins)==sum(s$losses),
              all(s$wins+s$losses+s$ties==31L*ifelse(year<2021,16L,17L)))
  }
  h
}

adl_gm_allplay_average <- function(seasons) {
  if (!nrow(seasons)) return(NULL)
  if (anyDuplicated(seasons$season)) stop('All-play average requires one team per GM season.')
  comparisons <- seasons$wins+seasons$losses+seasons$ties
  stopifnot(all(comparisons>0))
  # Each completed year has one vote, regardless of its 16/17-week length.
  mean((seasons$wins+.5*seasons$ties)/comparisons)
}

adl_gm_career <- function(members, history=adl_gm_history()) {
  members <- adl_gm_people(members)
  keep <- vapply(history$gm, function(x) any(tolower(adl_gm_people(x)) %in% tolower(members)), logical(1))
  s <- history[keep, , drop=FALSE]
  # Union of shared seasons: never multiply results by number of co-managers.
  if (anyDuplicated(s$season)) stop('Ambiguous GM history: more than one franchise in a season.')
  best <- if(nrow(s)) min(s$finish) else NULL
  worst <- if(nrow(s)) max(s$finish) else NULL
  list(experience=nrow(s), wins=sum(s$wins), losses=sum(s$losses), ties=sum(s$ties),
       best=best, bestYears=as.list(s$season[s$finish %in% best]),
       worst=worst, worstYears=as.list(s$season[s$finish %in% worst]))
}

adl_gm_baseline <- function() {
  b <- jsonlite::fromJSON('data/gm_career_profiles.json', simplifyVector=FALSE)
  h <- adl_gm_history()
  stopifnot(max(h$season)==b$completedThrough, b$completedThrough<b$season)
  for (name in names(b$profiles)) {
    p <- b$profiles[[name]]
    calculated <- adl_gm_career(p$gm,h)
    # Detect stale derived baselines, rather than silently publishing conflicting totals.
    for (field in names(calculated)) {
      if (!isTRUE(all.equal(unlist(p[[field]]),unlist(calculated[[field]]),check.attributes=FALSE)))
        stop('GM baseline differs from canonical history: ',name,' / ',field)
    }
    b$profiles[[name]][names(calculated)] <- calculated
  }
  b
}
