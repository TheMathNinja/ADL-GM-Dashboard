Postseason draft updates
=======================

The shared score workflow accepts completed weeks 1–17. Qualification, the
Playoff Picture table, and regular-season potential points stop at Week 12.
The postseason draft table uses the shared starter cache; it does not scrape
the same scores again.

Each conference has its own 16-pick board. Picks 1–9 use ascending Weeks 1–12
potential points. Wild Card losers occupy 10–12 using All-Play through Week 14;
Divisional losers occupy 13–14 using All-Play through Week 15. The conference
runner-up and champion occupy 15 and 16. Placement games and Week 17 games
cannot change these conference-specific positions. All-Play ties follow the
seed hierarchy (points, then potential); still-alive teams' current positions
are provisional. Wild Card games sum Weeks 13 and 14, followed by reseeded
single-week games in Weeks 15 and 16. Exact game ties favor the higher seed.

The projected table averages final pick numbers across 3,000 simulations of
unplayed games, carrying any actual Week 13 scores into the Wild Card total.
It retains the regular forecast's potential-only mean / normal-score framework,
not the separate bracket mock-up's Elo model. The final available regular-season
historical fit (Weeks 1–11 potential PPG predicting Week 12 scoring) is applied
to current Weeks 1–12 potential PPG. Historical within-team weekly SD supplies
score variation. This is an extrapolation to postseason weeks, not a newly
validated postseason calibration. Completed rounds use actual results only.

Run `Rscript tests/test_postseason_draft.R`. Fixtures cover elimination freezes,
fixed consolation order, first-leg deficits, higher-seed game ties, pick-total
conservation, completed boards, and incomplete scores. Existing qualification
and potential-forecast tests remain in the scheduled workflow.
