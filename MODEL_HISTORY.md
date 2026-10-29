# ADL model history



## Current: full recalibration, 2026-10-28



Deployed at the owner's explicit request despite slightly weaker chronological held-out results. The fitted blend is 35% adjusted Potential PPG, 5% adjusted actual PPG, 50% legal lineup strength and 10% roster depth. All upstream player/FS/fallback/availability calibration and downstream covariance/NIG parameters were refitted.



## Permanent benchmark: pre-full-recalibration calibration



Keep **35/0/55/10** as the named benchmark for future improvements. Do not replace or redefine it when the current live model changes. Its original source/data commit is `1698d78e231109cf207e87c6b8fd709282a88464`. Exact calibration artifacts, original scoring code and checksums are in `data/model_benchmarks/pre-full-recalibration-2026-10-28/`. Full raw input snapshots and published pages remain recoverable at that commit.



The same-input chronological 2023–2025 replay benchmark has weekly score RMSE 38.259616, weekly MAE 29.940740, remaining-average PPG RMSE 21.451115, All-Play RMSE 15.670429 percentage points, and adjusted-wins RMSE 1.998430. Preserve these definitions; comparisons of training-grid fit are not the same as held-out old-versus-new comparisons.



The full retraining report, per-year scores, grid results, player coefficient comparison, data limitations, and validation checks are in `docs/model-research/full-recalibration-2026-10-28/`.



## 2026-10-28: Status-aware player availability

Replace the stationary appearance rate with a regularized position/state/horizon
logistic model using completed-week MFL history. Latest active/inactive state,
IR/return-designated/suspension status, absence duration, recent return and season
appearance rate determine horizon-specific availability. Byes and known upcoming
absences still yield zero expected points. Active-game ability, 35/5/50/10 blend
and team score uncertainty are unchanged.

Status training excludes empty 2021 reports. Nested season-held-out tests on
2022-2025 use no target-week report. Availability Brier: 0.1252 to 0.1058 across
remaining horizons; next game 0.1044 to 0.0698. Recovered-player next-game
prediction: 70.3% to 90.1%, actual 91.4%. Team remaining-mean PPG RMSE: 21.170
to 21.156 without future reports; All-Play RMSE: 15.809 to 15.771 percentage
points. Individual weekly RMSE essentially unchanged (37.675 vs 37.675).
Team response coefficients held fixed to isolate availability.
Results: data/model_validation/availability_recovery_2026/.
Previous v5 and original pre-recalibration benchmark remain comparison
baselines. This fixes availability without a large team-accuracy gain claim.


## 2026-10-28: Smooth asymmetric player uncertainty

Active-game predictive error now uses a mean-preserving Johnson SU curve.
Let x = log(1 + active_mean / sqrt(position_Ra)) - log(2). Predictive scale
is old_sd * exp(position_intercept + slope*x). Shape a = 2*tanh((c+d*x)/2),
and b = exp(tail_parameter). Standardize the Johnson SU variable to mean zero
and variance one before applying scale and adding the unchanged active mean.
No star flag, rank threshold, or strength bucket is used by the model.

Held-out 2021-2025, using the same established-star cohort as the audit:
90% coverage changes from 83.91% to 91.91%; overall 91.45% to 90.63%.
Upper/lower misses change from 6.88%/1.67% to 5.06%/4.31% overall.
The asymmetric fit improves log score in each held-out season.

Availability-weighted variance is summed over the expected legal lineup.
The weekly team SD is adjusted by exp(gamma * centered_log_portfolio_sd),
with gamma learned from historical training seasons. Existing NIG team
asymmetry and persistent strength uncertainty remain. Extra team-level skew
response was tested and rejected on held-out performance. Expected player
points, player weights, team means and the availability fix remain unchanged.
Team-level gains are small: All-Play RMSE 15.9999 to 15.9945 percentage points,
adjusted-wins RMSE 1.97096 to 1.96978, playoff Brier 0.120016 to 0.119900.
These are exploratory model comparisons, not statistically established gains.

Training outcomes never include the outer test season. Player distributions
are fitted using cross-fitted player forecasts; team variance response uses
training-season residuals and is evaluated on the excluded season. Repeated
weekly outlooks overlap; 2024 qualification uses replayed current rules.
All historical team comparisons omit upcoming-week archived injury reports.
The prior availability-v6 release at e6200400b621fe6008d8137ddc05e3d6e48edc47
and original pre-recalibration benchmark remain available for comparison.
Detailed results: data/model_validation/player_uncertainty_2026/.
