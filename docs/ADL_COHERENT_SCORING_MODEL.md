# Unified ADL scoring model

Selected: **PPG-normalized EB + 2018+ innovations / NIG**, version `adl-coherent-ppg-eb-nig-v1`.

Adjusted Potential input reliability/covariance trains on 2022 through the prior season. Weekly actual scoring innovations, unconditional latent actual strength, and NIG shape train on normalized 2018+ completed seasons. The scale is league PPG, not league score SD. The mean is observed YTD league PPG plus the matched EB team contrast; the persistent SD is its covariance-consistent posterior, decreasing with observed weeks. No inherited blended-mean uncertainty, horizon taper, independent H Normal trajectory, or separate deterministic Potential forecast remains in the active simulation.

`data/adl_scoring_model.json` freezes prior-only fit parameters for each forecast season. `scripts/fit_adl_scoring.py` fits missing future seasons from canonical history and historical availability credits. Current-season outcomes never fit this artifact. Weekly updates change observed inputs/league PPG and posterior reliability, not historical parameters.

One PF/Potential trajectory yields all H2H, All-Play, quarterly/Reg Season Bonus, qualification, playoff swing and draft outputs. Potential uses the existing conditional random nonnegative gap, with team gap and NFL byes; no new Potential engine. Official Elo and actual standings are separate recorded quantities.

On a model-version change earlier outlooks are regenerated using only their completed-week inputs and the selected model. Within a version saved published outlooks remain frozen. Future version changes must also rebuild Playoffs archives before publishing Bonus pages.

Research verification uses common 2023–2025 plus official 2026 Weeks 1–4 tests. Quarterly Bonus Brier excludes Reg Season. The candidate has a small PF/CRPS/Brier tradeoff against the retired Live B and was selected by the user for coherence and near-target coverage.
