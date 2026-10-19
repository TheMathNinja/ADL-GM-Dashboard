# Live H2H win probability

This is the chance of winning the current week's head-to-head matchup, not a Bonus Game win probability. The same joint simulation supplies both teams' reciprocal win/loss odds; a tie is a separate outcome.

## Inputs and model

- Points already scored are fixed. Remaining mean points for every submitted starter are `game seconds remaining / 3600 × pregame Fantasy Sharks projection`, using YTD PPG when FS is unavailable. The existing displayed live projected score is preserved.
- Position-specific full-game error variance is fitted as a nonnegative baseline plus a nonnegative term proportional to squared projected points. Scores/projections are scaled within league and season before fitting; the current submitted starters supply the live scoring scale.
- Two NFL-game factors allow dependence: a common production factor and an opposite-signed NFL-team advantage factor. One pair of coefficients is fitted per league, with no position-pair correlation table. Different NFL games are independent. All players from the same NFL team share the same sign on the advantage factor.
- Remaining variance is proportional to the fraction of game time remaining. Shared factors are Brownian increments, so overlapping remaining time has covariance proportional to the overlap. Idiosyncratic increments use Normal variation, selected against centered, variance-matched NIG. Negative remaining fantasy points are allowed.
- 20,000 joint draws produce final scores, rounded to league 0.1-point precision, and win/tie/loss probabilities. The same score/clock/lineup inputs produce the same random seed. Finished matchups have exact outcomes. An unfinished 0/100 Monte Carlo estimate is displayed as <0.1%/>99.9%, rather than certainty.

## Historical checks and limits

Every 2023, 2024, and 2025 test season was fitted using only earlier seasons beginning in 2021. Checks use submitted starters, the target-week archived FS export, and preceding-week-only YTD fallback. Only complete 21-player lineups whose summed actual points match the official matchup score are scored. This is conditional on those submitted lineups, not a forecast of which players a manager would start. Archived FS exports have unverified pre-kickoff vintage; they are not proven immutable pregame snapshots.

Normal with NFL-game effects has lower combined held-out H2H Brier and PF CRPS than NIG with the same mean/variance in both leagues. Small differences from the independent Normal control are not evidence of a large improvement.

league,model,teamWeeks,matchups,pfRMSE,pfMAE,pfBias,pfCRPS,coverage95,width95,h2hBrier,winCreditMAE

ADL,NIG NFL-game effects,959,401,45.14216652838575,35.348311014961176,-21.82117716341126,25.711098451433195,0.91866527632951,148.26962859317416,0.4790436009975061,0.4624445137157107

ADL,Normal NFL-game effects,959,401,45.14216652838575,35.348311014961176,-21.82117716341126,25.426784336063605,0.8988529718456726,148.12202520686495,0.4774315163480188,0.4621907730673317

ADL,Normal independent,959,401,45.14216652838575,35.348311014961176,-21.82117716341126,25.4276325145482,0.9009384775808134,148.11685725115635,0.4779213392906623,0.4624588528678304

FAFL,NIG NFL-game effects,906,353,44.08665702976833,35.016944794842146,-19.245434931146853,25.19598163022784,0.9249448123620309,149.72314135714288,0.4939089442870632,0.478854343720491

FAFL,Normal NFL-game effects,906,353,44.08665702976833,35.016944794842146,-19.245434931146853,24.89011912254851,0.9183222958057397,149.68941276857362,0.4919514792256846,0.4783297922568461

FAFL,Normal independent,906,353,44.08665702976833,35.016944794842146,-19.245434931146853,24.89423907829448,0.9172185430463576,149.5922977754943,0.4921405020459553,0.4784305949008498


The full-game holdout does **not** validate intragame odds. We do not have historical minute-by-minute player score/clock snapshots to test that directly. Stationary remaining increments, lack of a score-pace update, and future injury/benching behavior are initial assumptions. Overtime uses the remaining OT clock, consistent with the live points projection. The raw Sharks-based live mean has historical scoring bias; this feature does not silently alter that user-selected mean. These limitations should be tested using collected live snapshots before claiming live calibration.

Separate fits are used for ADL and FAFL. Final production parameters use 2021–2025 history. Existing official Playoffs and Bonus Game models are unchanged. Probability computation failures preserve the valid live-score update and display unavailable odds rather than inventing a fallback probability.

Source research: local player scoring/roster archive and MFL target-week projections. NIG simulation follows the Normal/inverse-Gaussian mixture documented at https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.norminvgauss.html .
