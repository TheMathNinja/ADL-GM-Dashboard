# ADL model history

## Current: full recalibration, 2026-10-28

Deployed at the owner's explicit request despite slightly weaker chronological held-out results. The fitted blend is 35% adjusted Potential PPG, 5% adjusted actual PPG, 50% legal lineup strength and 10% roster depth. All upstream player/FS/fallback/availability calibration and downstream covariance/NIG parameters were refitted.

## Permanent benchmark: pre-full-recalibration calibration

Keep **35/0/55/10** as the named benchmark for future improvements. Do not replace or redefine it when the current live model changes. Its original source/data commit is `1698d78e231109cf207e87c6b8fd709282a88464`. Exact calibration artifacts, original scoring code and checksums are in `data/model_benchmarks/pre-full-recalibration-2026-10-28/`. Full raw input snapshots and published pages remain recoverable at that commit.

The same-input chronological 2023–2025 replay benchmark has weekly score RMSE 38.259616, weekly MAE 29.940740, remaining-average PPG RMSE 21.451115, All-Play RMSE 15.670429 percentage points, and adjusted-wins RMSE 1.998430. Preserve these definitions; comparisons of training-grid fit are not the same as held-out old-versus-new comparisons.

The full retraining report, per-year scores, grid results, player coefficient comparison, data limitations, and validation checks are in `docs/model-research/full-recalibration-2026-10-28/`.
