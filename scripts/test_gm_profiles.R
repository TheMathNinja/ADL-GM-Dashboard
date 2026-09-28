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
cat('GM career tests passed: ties, current-game additions, preserved finishes, incomplete snapshots and stale baselines.\n')
