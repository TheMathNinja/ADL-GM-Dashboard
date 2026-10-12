# ADL shared fixed-15% EB / NIG scoring model

Every ADL forecast uses one score/Potential trajectory: H2H, weekly All-Play, all four quarterlies, Reg Season Bonus, playoff qualification and draft projections.

The team input is 85% availability-adjusted Potential PPG plus 15% adjusted actual PPG. Active submitted starters are preserved; inactive or vacant slots use active eligible replacements from the same weekly roster, ranked by that week’s Fantasy Sharks projection, falling back to earlier-week YTD PPG. Eligibility and lineup group/position constraints apply. Partial rosters count available players without extrapolation. Replacement actual scores are used, not projected scores. Healthy zero scores remain. No future-week projections are used.

Prior 2022+ seasons fit EB input covariance and reliability for this exact blend. Current observed actual league PPG anchors the scoring level. Prior 2018+ normalized actual scoring history supplies the retained NIG innovations and latent actual ability variance. Conditional strength uncertainty is recomputed from the matched blend covariance; a persistent team offset is shared across remaining weeks. Weekly PF/Potential pairing and tiebreak rules are unchanged.

Fixed15% was selected exploratorily by PF RMSE from the 1%-increment fixed-weight 2023–2026 comparison, not independent final validation. Historical injury/roster/projection publication vintages are unverified. Forecast views use only their selected completed-week inputs, with current corrected scores.

The Monday/Thursday pipeline collects weekly projections and rebuilds adjusted actual PF before forecasts. All source inputs and fitted parameters are shared between Bonus Games and Playoffs. No separate Reg Season scoring engine is used.
