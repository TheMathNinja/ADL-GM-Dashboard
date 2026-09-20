source('scripts/postseason_draft.R')
regular <- data.frame(franchise_id=sprintf('%04d',1:32), conference=rep(c('00','01'),each=16),
                     seed=rep(1:16,2), ap_wins_total=rep(seq(300,75,length.out=16),2),
                     points_for=rep(seq(3000,1500,length.out=16),2),
                     potential_points=rep(seq(4000,2500,length.out=16),2))
scores <- matrix(rep(regular$points_for/12,17),32,17)
scores[,13:17] <- rep(seq(250,100,length.out=16),2)
r12 <- adl_postseason_replay(regular,scores,12)
r14 <- adl_postseason_replay(regular,scores,14)
r15 <- adl_postseason_replay(regular,scores,15)
r16 <- adl_postseason_replay(regular,scores,16)
stopifnot(all(r14$currentPick[c(7,6,5)]==10:12),
          all(r15$currentPick[c(4,3)]==13:14),
          r16$currentPick[2]==15, r16$currentPick[1]==16)
stopifnot(all(table(r14$status)[c('Wild Card exit','Still alive')]==c(6,8)),
          all(r14$apThrough[r14$status=='Wild Card exit']==14))
# Placement results must not change a Wild Card loser's frozen ordering/AP.
altered <- scores; altered[c(5,6,7),15:17] <- 10000
later <- adl_postseason_replay(regular,altered,17)
stopifnot(identical(r14$currentPick[c(5,6,7)], later$currentPick[c(5,6,7)]),
          identical(r14$apPct[c(5,6,7)],later$apPct[c(5,6,7)]),
          identical(r12$currentPick[regular$seed>7],later$currentPick[regular$seed>7]))
# A first-leg deficit is carried forward; Week 13 alone never eliminates.
upset <- scores; upset[7,13] <- 1000; upset[7,14] <- 0
u13 <- adl_postseason_replay(regular,upset,13)
u14 <- adl_postseason_replay(regular,upset,14)
stopifnot(all(u13$status[regular$seed<=7]=='Still alive'),u14$status[2]=='Wild Card exit',u14$status[7]=='Still alive')
# Exact Wild Card totals favor the higher original seed.
tie <- scores; tie[7,13:14] <- tie[2,13:14]
stopifnot(adl_postseason_replay(regular,tie,14)$status[7]=='Wild Card exit')
# All generated boards are permutations 1:16; expected picks conserve totals.
set.seed(2026)
mc <- adl_postseason_draft(regular,scores,14,rep(200,32),40,100)
stopifnot(all(tapply(mc$expectedPick,regular$conference,sum)==136),
          all(mc$expectedPick>=1 & mc$expectedPick<=16),
          identical(mc$expectedPick[regular$seed>7],r12$currentPick[regular$seed>7]))
final <- adl_postseason_draft(regular,scores,17,rep(200,32),40,100)
stopifnot(identical(final$currentPick,final$expectedPick))
bad <- scores; bad[1,13] <- NA
stopifnot(inherits(try(adl_postseason_replay(regular,bad,13),silent=TRUE),'try-error'))
cat('Postseason draft rules passed.\n')
