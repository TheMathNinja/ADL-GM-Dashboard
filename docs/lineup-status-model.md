# ADL availability-adjusted scoring predictor

Production version: `adl-lineup-status-v1`, fitted September 29, 2026.

The model fits 2022–2025 weekly MFL injury/status reports and legal lineups.
2021 is excluded because its retrieved weekly MFL injury reports were empty.
Only explicit zero-scoring Out, Suspended, IR-return and Bye player-weeks qualify.
Ordinary IR and taxi players do not receive credits. Fantasy IR alone is not
evidence of an NFL return designation.

Player estimate = `(2 * preseason PPG + games * actual PPG) / (2 + games)`.
If only one estimate exists it is used; neither means zero. Games here means
recorded MFL player-score appearances, excluding explicit unavailable zeros.
Historical preseason estimates use the archived ESPN ADL projection fields.
2026 uses the ESPN-specific ADL-scored preseason estimate divided by ESPN games
from `PreseasonProj/2026/final_projections_2026.csv`, frozen before this deployment.
It does not use composite or current weekly player projections.

Fixed status coefficients: Out 0.71875; Suspended, IR-return and Bye 1.0.
All coefficients are constrained to [0,1]. A credited player must improve the
best legal lineup to increase the predictor; bench credits are not simply summed.
The increase is added to official potential PPG solely as a forecast input.
Official scores, potential points and standings are unchanged.

The taper was selected from k = 1,2,4,8,16 by leave-one-season-out future-PPG
error, fitting the constant lineup coefficients inside each training fold.
Final coefficients and eleven week-specific future-PPG intercepts/slopes were
then fitted on all four seasons. Selection scores are not an independent test
of the final selected production model. Constant coefficients minimize pooled
future-PPG squared error with exact lineup optimization and deterministic bounded
multi-start coordinate search; a global optimum is not claimed.

The separate future-potential-points regression, weekly score noise, and ADL's
linear persistent-strength uncertainty remain unchanged. Every simulated week
produces H2H results, bonus games and all-play from the same score draws. There
is no separate all-play-to-wins conversion. Published expected remaining PPG uses
the same adjusted mean as the simulations.

Weekly refreshes reuse the shared score/starter cache and cache MFL weekly roster,
injury and schedule evidence. Missing required sources fail the forecast build.
The fitted model and player preseason inputs are versioned in `data/`; changes to
the season or retraining require an explicit new fit and preseason input file.

Validation: production calculator matches the research optimizer on all 1,408
historical team/cutoff forecasts (2022–2025, weeks 1–11), within 1e-7 PPG.
