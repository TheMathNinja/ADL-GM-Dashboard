# ADL H2H empirical-Bayes estimation update

The scoring mean uses centered YTD availability-adjusted Potential with the matched EB reliability estimator. The league level remains observed YTD actual PPG. The original weekly scoring SD, tapered persistent strength uncertainty, Normal weekly distribution, Bonus Game forecasts, and Potential tiebreaker are unchanged.

The 2026 fit uses completed 2022–2025 seasons. Historical availability-credit snapshots use the existing prior-fitted native status design. `scripts/fit_h2h_eb.py` reproduces the covariance/moment fit from canonical scoring history and those snapshots; the model refuses to forecast a different season without a refreshed fit. Training uses within-season centered inputs/targets and prior full-season PF SD normalization.

Multiplier = latent cross-covariance / (latent Potential variance + weekly Potential variance / observed weeks). The final mean is observed league PPG plus that multiplier times the team’s adjusted Potential advantage. Research tests cover 2023–2025 and official 2026 through Week 4; research comparisons refit using earlier seasons only.

Mean and uncertainty are not yet jointly refitted: matching uncertainty remains a final-model design requirement under study.
