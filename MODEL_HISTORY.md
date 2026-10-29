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
