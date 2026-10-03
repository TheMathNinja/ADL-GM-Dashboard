# Rebuild from the same audited history used by the Playoff Picture GM profiles.
# Run from repository root: Rscript scripts/build_trophy_room.R
source('R/gm_history.R')
adl_majority_franchise <- function(s, active) {
  if (!nrow(s)) return(active)
  counts <- table(s$franchise_id)
  tied <- names(counts)[counts == max(counts)]
  latest <- s[s$franchise_id %in% tied, , drop=FALSE]
  latest$name[which.max(latest$season)]
}
adl_trophy_owner_groups <- function(people, h, current) {
  # Group only identical ownership stints, including the current roster.
  keys <- vapply(people,function(person) {
    s <- h[vapply(h$gm,function(x)person %in% adl_gm_people(x),logical(1)),,drop=FALSE]
    stints <- sort(paste(s$season,s$franchise_id,sep=':'))
    active <- sort(names(current)[vapply(current,function(p)person %in% adl_gm_people(p$gm),logical(1))])
    if(!length(stints) && !length(active))return(paste('unknown',person))
    paste(paste(stints,collapse=';'),paste(active,collapse=';'),sep='|')
  },character(1))
  lapply(unique(keys),function(key)people[keys==key])
}
build_trophy_room <- function() {
  h <- adl_gm_history()
  baseline <- adl_gm_baseline()
  required <- c('rs_wins','rs_losses','rs_ties','record_wins','record_losses','record_ties')
  stopifnot(all(required %in% names(h)), !anyNA(h[required]),
            all(h$rs_wins+h$rs_losses+h$rs_ties==372))
  roster <- jsonlite::fromJSON('data/current_gms_2026.json',simplifyVector=FALSE)
  current <- roster$profiles
  payouts <- jsonlite::fromJSON('data/trophy_room/payouts.json',simplifyVector=FALSE)
  codes <- strsplit('DAL NYG PHI WAS CHI DET GBP MIN ATL CAR NOS TBB ARI LAR SFO SEA BUF MIA NEP NYJ BAL CIN CLE PIT HOU IND JAC TEN DEN KCC LVR LAC',' ')[[1]]
  payout_seasons <- lapply(sort(unique(h$season)),function(year) {
    s <- h[h$season==year,,drop=FALSE]
    p <- payouts[[as.character(year)]]
    stopifnot(!is.null(p),length(p$teams)==32L)
    p$teams <- lapply(p$teams,function(t) {
      code <- switch(t$team,OAK='LVR',NOR='NOS',t$team)
      ix <- if(code %in% codes)which(s$franchise_id==sprintf('%04d',match(code,codes))) else which(s$name==code)
      stopifnot(length(ix)==1L)
      t$franchise <- s$name[ix];t$finish <- s$finish[ix]
      t$gm <- paste(adl_gm_people(s$gm[ix]),collapse=' / ')
      t$record <- paste(s$record_wins[ix],s$record_losses[ix],s$record_ties[ix],sep='-')
      t
    })
    stopifnot(!anyDuplicated(vapply(p$teams,`[[`,character(1),'franchise')))
    p$teams <- p$teams[order(vapply(p$teams,`[[`,numeric(1),'finish'))]
    p$year <- year;p
  })
  people <- sort(unique(c(unlist(lapply(h$gm,adl_gm_people)),unlist(lapply(current,function(p)adl_gm_people(p$gm))))))
  owners <- lapply(adl_trophy_owner_groups(people,h,current),function(members) {
    person <- members[1]
    s <- h[vapply(h$gm,function(x)person %in% adl_gm_people(x),logical(1)),,drop=FALSE]
    s <- s[order(s$season),,drop=FALSE]
    career <- adl_gm_career(person,h)
    active <- names(current)[vapply(current,function(p)person %in% adl_gm_people(p$gm),logical(1))]
    stopifnot(length(active)<=1)
    franchise <- if(length(active)) active else adl_majority_franchise(s, active)
    total <- career$wins+career$losses+career$ties
    rs <- sum(s$rs_wins+s$rs_losses+s$rs_ties)
    list(owner=paste(members,collapse=' / '),members=as.list(members),franchise=franchise,active=length(active)>0,
         years=as.list(s$season),seasons=career$experience,
         record=paste(sum(s$record_wins),sum(s$record_losses),sum(s$record_ties),sep='-'),
         rs=if(rs>0)(sum(s$rs_wins)+.5*sum(s$rs_ties))/rs else NULL,
         all=if(total>0)(career$wins+.5*career$ties)/total else NULL,
         allTimeAllPlay=adl_gm_allplay_average(s),
         wins=career$wins,losses=career$losses,ties=career$ties,
         best=career$best,bestYears=career$bestYears,
         history=lapply(seq_len(nrow(s)),function(i)list(year=s$season[i],franchise=s$name[i],
           record=paste(s$record_wins[i],s$record_losses[i],s$record_ties[i],sep='-'),
           rs=(s$rs_wins[i]+.5*s$rs_ties[i])/372,
           all=(s$wins[i]+.5*s$ties[i])/(s$wins[i]+s$losses[i]+s$ties[i]),finish=s$finish[i])))
  })
  c <- read.csv('data/trophy_room/champions.csv',skip=1,check.names=FALSE,stringsAsFactors=FALSE)
  c <- c[!is.na(suppressWarnings(as.integer(c[[1]]))),,drop=FALSE]
  record <- function(s) paste(s$record_wins,s$record_losses,s$record_ties,sep='-')
  champions <- lapply(seq_len(nrow(c)),function(i) {
    year <- as.integer(c[i,1]); s <- h[h$season==year,]
    name <- sub(' \\(.*$','',c[i,3]); runner <- sub(' \\(.*$','',c[i,5])
    # Preserve source spelling in the snapshot, normalize the known display typo.
    name <- sub('Bucaneers','Buccaneers',name,fixed=TRUE)
    stopifnot(nrow(s)==32L, name==s$name[s$finish==1], runner==s$name[s$finish==2])
    list(year=year,champion=name,championRecord=record(s[s$finish==1,]),
      runner=runner,runnerRecord=record(s[s$finish==2,]),score=c[i,6],
      gm=paste(adl_gm_people(s$gm[s$finish==1]),collapse=', '),
      awards=as.list(setNames(as.character(c[i,8:15]),trimws(names(c)[8:15]))))
  })
  stopifnot(length(champions)==length(unique(h$season)),!anyDuplicated(vapply(champions,`[[`,integer(1),'year')))
  payload <- list(completedThrough=baseline$completedThrough,rosterSeason=baseline$season,
    champions=champions,owners=owners,payouts=payout_seasons)
  dir.create('docs/trophy-room',recursive=TRUE,showWarnings=FALSE)
  jsonlite::write_json(payload,'docs/trophy-room/data.json',auto_unbox=TRUE,pretty=TRUE,null='null',digits=12)
  message('Trophy Room: ',length(champions),' champions; ',length(owners),' ownership rows covering ',length(people),' GMs; canonical completed-season history.')
  invisible(payload)
}
if(sys.nframe()==0L)build_trophy_room()
