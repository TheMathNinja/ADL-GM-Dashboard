source('scripts/build_trophy_room.R')
source('scripts/gm_profiles.R')
d <- build_trophy_room()
h <- adl_gm_history()
b <- adl_gm_baseline()
stopifnot(length(d$payouts)==10L)
for(p in d$payouts) {
  stopifnot(length(p$teams)==32L,
    abs(sum(vapply(p$teams,`[[`,numeric(1),'payout'))-p$totalPayout)<.001)
  for(t in p$teams) {
    s <- h[h$season==p$year & h$name==t$franchise,]
    stopifnot(nrow(s)==1L,t$finish==s$finish,
      abs(t$earnings+t$adjustment-t$payout)<.001,
      abs(sum(vapply(t$earnedBreakdown,`[[`,numeric(1),'amount'))-t$totalEarnings)<.001)
  }
}
official <- jsonlite::fromJSON('data/trophy_room/league_records.json')$records
ix <- match(paste(h$season,h$franchise_id),paste(official$season,official$franchise_id))
stopifnot(!anyNA(ix))
for(k in c('record_wins','record_losses','record_ties'))stopifnot(all(h[[k]]==official[[k]][ix]))
kc <- h[h$season==2024 & h$name=='Kansas City Chiefs',]
stopifnot(kc$record_wins==18L,kc$record_losses==4L,kc$record_ties==0L)
for(o in d$owners) {
  career <- h[vapply(h$gm,function(x)any(unlist(o$members) %in% adl_gm_people(x)),logical(1)),]
  stopifnot(o$record==paste(sum(career$record_wins),sum(career$record_losses),sum(career$record_ties),sep='-'))
  stopifnot(isTRUE(all.equal(o$allTimeAllPlay,mean((career$wins+.5*career$ties)/(career$wins+career$losses+career$ties)))))
  for(person in unlist(o$members)) {
    individual <- adl_gm_career(person,h)
    stopifnot(o$wins==individual$wins,o$losses==individual$losses,
              o$ties==individual$ties,o$seasons==individual$experience)
  }
}
for(c in d$champions) {
  for(side in c('champion','runner')) {
    s <- h[h$season==c$year & h$name==c[[side]],]
    stopifnot(nrow(s)==1L,c[[paste0(side,'Record')]]==paste(s$record_wins,s$record_losses,s$record_ties,sep='-'))
  }
}
members <- unlist(lapply(d$owners,`[[`,'members'))
stopifnot(length(d$champions)==10L, length(members)==71L,!anyDuplicated(members),
          identical(adl_gm_people(' Thomas , Thomas Cool '),'Thomas Cool'),
          identical(adl_gm_people('Joe'),"Joe O'Mara"))
# Every current individual's baseline must agree with the existing GM popup.
for(p in b$profiles) for(person in adl_gm_people(p$gm)) {
  owner <- Filter(function(o)person %in% unlist(o$members),d$owners)[[1]]
  stopifnot(owner$wins==p$wins,owner$losses==p$losses,owner$ties==p$ties,
            owner$seasons==p$experience)
}
# Aliases and franchise changes follow people; shared co-manager years count once.
fixture <- h[1:2,];fixture$season <- c(2024,2025);fixture$gm <- c('Thomas, Joe',"Thomas Cool, Joe O'Mara")
weighted_fixture <- data.frame(season=c(2020,2021),wins=c(496,0),losses=c(0,527),ties=c(0,0))
stopifnot(adl_gm_allplay_average(weighted_fixture)==.5)
weighted_fixture$wins <- c(248,0);weighted_fixture$losses <- c(0,527);weighted_fixture$ties <- c(248,0)
stopifnot(adl_gm_allplay_average(weighted_fixture)==.375,
          is.null(adl_gm_allplay_average(weighted_fixture[FALSE,])))
g <- adl_gm_career("Thomas Cool, Joe O'Mara",fixture)
stopifnot(g$experience==2L,g$wins==sum(fixture$wins))
stopifnot(inherits(try(adl_gm_career('Thomas',rbind(fixture,fixture[1,])),silent=TRUE),'try-error'))
# Identical co-ownership merges; independent stints and current departures do not.
fixture$gm <- c('A, B','A, B')
stopifnot(length(adl_trophy_owner_groups(c('A','B'),fixture,list()))==1L)
fixture$gm[2] <- 'A'
stopifnot(length(adl_trophy_owner_groups(c('A','B'),fixture,list()))==2L)
fixture$gm <- c('A','B')
stopifnot(length(adl_trophy_owner_groups(c('A','B'),fixture,list()))==2L)
fixture$gm <- c('A, B','A, B')
stopifnot(length(adl_trophy_owner_groups(c('A','B'),fixture,list(Team=list(gm='A'))))==2L)
# Explicit full-season boundaries, all-play ties, and 12-week regular seasons.
stopifnot(all(h$rs_wins+h$rs_losses+h$rs_ties==372),
          all(h$wins+h$losses+h$ties==ifelse(h$season<2021,496,527)),
          sum(h$h2h_wins)==sum(h$h2h_losses))
# Actual current weekly snapshot must produce exactly the same popup increments.
s <- read.csv('data/weekly_team_metrics.csv',colClasses=c(franchise_id='character'))
season <- unique(s$season);week <- max(s$week)
live <- adl_gm_profiles(season,week,s)
for(name in names(live)) {
  p <- b$profiles[[name]];o <- live[[name]]
  stopifnot(o$wins+o$losses+o$ties==p$wins+p$losses+p$ties+31*week,
            o$experience==p$experience)
}
cat('Passed: 320 seasons, 71 GMs, 32 current profile baselines; aliases, co-managers, franchise changes, ties, boundaries, and live snapshot additions.\n')
