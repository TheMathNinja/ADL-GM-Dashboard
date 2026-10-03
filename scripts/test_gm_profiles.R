source('scripts/gm_profiles.R')
b<-jsonlite::fromJSON('data/gm_career_profiles.json',simplifyVector=FALSE)
s<-expand.grid(franchise_id=sprintf('%04d',1:32),week=1:2,stringsAsFactors=FALSE)
s$season<-2026L
s$franchise_score<-ifelse(s$week==1,100,as.integer(s$franchise_id))
g<-adl_gm_profiles(2026,2,s)
for(n in names(g)) {
 id<-as.integer(g[[n]]$franchise_id)
 stopifnot(g[[n]]$wins-b$profiles[[n]]$wins==id-1L,
           g[[n]]$losses-b$profiles[[n]]$losses==32L-id,
           g[[n]]$ties-b$profiles[[n]]$ties==31L,
           identical(g[[n]]$bestYears,b$profiles[[n]]$bestYears),
           identical(g[[n]]$experience,b$profiles[[n]]$experience))
}
stopifnot(inherits(try(adl_gm_profiles(2026,2,s[-1,]),silent=TRUE),'try-error'))
stopifnot(inherits(try(adl_gm_profiles(2027,2,s),silent=TRUE),'try-error'))

# Completed seasons receive equal weight; the current season receives week/17.
rows <- jsonlite::fromJSON('data/gm_career_seasons.json')
mataya <- rows[trimws(rows$gm) == 'Russell Mataya', ]
season_pcts <- (mataya$wins + .5 * mataya$ties) /
  (mataya$wins + mataya$losses + mataya$ties)
current_pct <- (15.5 + 1) / 62 # Week 1: 31 ties; Week 2: one win for franchise 0002.
expected <- (sum(season_pcts) + (2/17) * current_pct) /
  (length(season_pcts) + 2/17)
stopifnot(abs(g[['New York Giants']]$careerApPct - expected) < 1e-12)
pooled <- (sum(mataya$wins + .5 * mataya$ties) + 16.5) /
  (sum(mataya$wins + mataya$losses + mataya$ties) + 62)
stopifnot(abs(g[['New York Giants']]$careerApPct - pooled) > 1e-8)

# A current ownership change must move the GM's career with the GM. It must not
# leave the completed-season profile attached to the old franchise.
owner_path <- 'data/current_gms_2026.json'
owner_text <- paste(readLines(owner_path, warn=FALSE), collapse='\n')
on.exit(writeLines(owner_text, owner_path), add=TRUE)
owners <- jsonlite::fromJSON(owner_path, simplifyVector=FALSE)
owners$profiles[['Dallas Cowboys']]$gm <- 'Russell Mataya'
owners$profiles[['New York Giants']]$gm <- 'Seth Coven'
jsonlite::write_json(owners, owner_path, auto_unbox=TRUE, pretty=TRUE)
swapped <- adl_gm_profiles(2026, 2, s)
stopifnot(swapped[['Dallas Cowboys']]$gm == 'Russell Mataya',
          swapped[['Dallas Cowboys']]$experience == b$profiles[['New York Giants']]$experience,
          swapped[['New York Giants']]$gm == 'Seth Coven',
          swapped[['New York Giants']]$experience == b$profiles[['Dallas Cowboys']]$experience)
writeLines(owner_text, owner_path)
cat('GM career tests passed: equal-season weighting, partial current-year weighting, ties, current games, ownership changes and stale baselines.\n')
