source('scripts/get_adl_playoff_picture.R')
base <- data.frame(franchise_id=sprintf('%02d',1:16), conference='NFC',
 division=rep(LETTERS[1:4],each=4), win_pct=rep(c(.8,.7,.6,.5),4),
 ap_win_pct=seq(.9,.15,length.out=16), points_for=2000, potential_points=2500)
empty <- data.frame(franchise_id=character(),opponent_id=character(),credit=numeric())
ranked <- function(d,g=empty) adl_rank_playoffs(d,g)
# Potential points decides a division when every preceding criterion ties.
d <- base; d[2,c('win_pct','ap_win_pct','points_for')] <- d[1,c('win_pct','ap_win_pct','points_for')]
d$potential_points[2] <- 3000
r <- ranked(d); stopifnot(r$is_division_winner[2],r$playoff_seed[2] < r$playoff_seed[1])
# Head-to-head beats all-play, scoring and potential for division qualification.
g <- data.frame(franchise_id=c('01','02'),opponent_id=c('02','01'),credit=c(1,0))
r <- ranked(d,g); stopifnot(r$is_division_winner[1])
# Three-way mini league aggregates ALL games among tied teams.
d <- base; d$win_pct[1:3] <- .8
g <- data.frame(franchise_id=c('01','02','02','03','01','03'),
 opponent_id=c('02','01','03','02','03','01'), credit=c(0,1,1,0,.5,.5))
r <- ranked(d,g); stopifnot(r$is_division_winner[2],r$h2h_mini_pct[2]==1)
# All four teams from one division can receive seeds 1-4; other winners 5-7.
d <- base; d$win_pct <- c(.95,.94,.93,.92,.8,.2,.1,.05,.8,.2,.1,.05,.8,.2,.1,.05)
r <- ranked(d); stopifnot(all(r$playoff_seed[1:4]==1:4),all(r$playoff_seed[c(5,9,13)]==5:7))
# Wild cards use potential only after win%, all-play, and actual points.
d <- base; d$win_pct[c(2,6,10,14)] <- .7; d$ap_win_pct[c(2,6,10,14)] <- .5
d$potential_points[c(2,6,10,14)] <- c(2600,2700,2800,2900)
r <- ranked(d); stopifnot(!r$is_wild_card[2],all(r$is_wild_card[c(6,10,14)]))
# Row order cannot override a resolved potential-points tie.
rr <- ranked(d[16:1,]); stopifnot(setequal(r$franchise_id[r$is_playoff_team],rr$franchise_id[rr$is_playoff_team]))
# Seven qualifiers and exactly one bye in each conference.
both <- rbind(base,transform(base,franchise_id=paste0('A',franchise_id),conference='AFC'))
r <- ranked(both); stopifnot(all(table(r$conference[r$is_playoff_team])==7),sum(r$playoff_seed==1,na.rm=TRUE)==2)
# Completed-season shortcut uses the same head-to-head/potential rules.
d <- base; d[2,c('win_pct','ap_win_pct')] <- d[1,c('win_pct','ap_win_pct')]
d$potential_points[2] <- 3000
d$season <- 2026; d$through_week <- 12; d$franchise_name <- d$franchise_id
d$total_wins <- d$win_pct*17; d$h2h_wins <- 5; d$bonus_wins <- d$total_wins-5
d$ap_wins_total <- d$ap_win_pct*31*12
hist <- data.frame(season=2026,week=1,franchise_id=d$franchise_id,
 points_for_week=c(210,200,rep(190,14)),h2h_wins_week_raw=0,h2h_ties_week_raw=0)
sched <- data.frame(week=1,franchise_id=c('01','02'),opponent_id=c('02','01'))
mc <- run_adl_monte_carlo(d,hist,sched,sd_points=1)
stopifnot(mc$team_summary$divwin_pct[1]==1, mc$team_summary$divwin_pct[2]==0)
# Projected qualification separates groups before potential/seed sorting.
draft <- data.frame(franchise_name=LETTERS[1:16], seed=1:16,
                    pred_seed=16:1, potential_points=1:16,
                    pred_potential_points=16:1)
today <- build_conf_draft(draft, "seed", "potential_points")
forecast <- build_conf_draft(draft, "pred_seed", "pred_potential_points", playoff_order="seed")
stopifnot(identical(today$Team, LETTERS[c(8:16,1:7)]),
          identical(forecast$Team, LETTERS[c(9:1,10:16)]),
          identical(forecast$Pick, 1:16))
cat('PASS: playoff qualification, seeding, potential, and projected draft rules\n')

# Division ranks also resolve tied teams below the division leader via mini-league H2H.
d <- base; d$win_pct[2:3] <- .6
g <- data.frame(franchise_id=c('02','03'),opponent_id=c('03','02'),credit=c(0,1))
r <- ranked(d,g)
stopifnot(identical(r$division_rank[1:4], c(1L,3L,2L,4L)),
          all(r$division_rank[r$is_division_winner] == 1L))
cat('PASS: full division ranks and lower-place head-to-head tiebreaks\n')
