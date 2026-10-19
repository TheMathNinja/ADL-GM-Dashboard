# Live Bonus Game Watch

Public provisional live standings, separate from official weekly results and model forecasts. The current quarter appears on the left and Regular Season on the right, with responsive stacking on narrow screens. Both panels use the same snapshot and rank APW, then cumulative PF, then live eligible-roster Potential Points. Exact ties remain tied; a boundary tie is not assigned by franchise ID. All-play record precedes Points For.

`collect_live_bonus.py` reads public MFL `liveScoring&DETAILS=1` for the current week, rather than substituting completed team scores. It adds completed `weeklyResults` for carry-forward; those contain MFL’s recorded `opt_pts`. Live Potential is optimized using public player positions, current eligible roster statuses and the actual league lineup limits. All live results and tiebreakers remain provisional.

Snapshots contain only public franchise IDs, live totals, player counts and prior weekly team totals. They are written to an isolated orphan `live-bonus-watch` branch, not main. No credentials, personal projections, pending trades or model parameters are published. No official Bonus Game outcomes or league settings are modified.

The scheduled workflow starts/continues a collector hourly at :50 on Sunday/Monday/Tuesday UTC. The worker itself enforces America/New_York time: Sunday 13:00–00:30 next day and Monday 20:00–00:30 next day, including daylight-saving changes. It may warm up for up to 20 minutes before the window without scraping. Within a window it checks MFL once per minute and stops after 345 minutes or the window’s end, whichever is first. The latest queued bootstrap continues a long Sunday window. Only one collector can run per league. An owner can dispatch `once=true` for a single refresh.

GitHub scheduled starts and MFL’s own feed updates can be delayed. Long-running collectors bridge hourly scheduler delays; the browser shows the actual check timestamp and marks snapshots delayed after 150 seconds during live hours. A failed scrape never replaces the last valid snapshot. The visible Live tab reads the shared public snapshot every minute, stops automatic requests outside the ET windows or while hidden, and resumes when visible. Every read has a minute cache key and disables browser cache. The Refresh control re-reads the latest shared snapshot.

Neither the browser nor the data worker reruns the scoring model. Existing completed-quarter results, historical outlooks, projected PPG, Bonus probabilities, playoff odds and regular weekly updates retain their current behavior. Future Bonus module builds retain the new tab via the template.

Checks cover Eastern/DST windows, full 32-team feed validation, legal and partial lineups, current-quarter and season carry-forward, APW conservation, PF/Potential tiebreakers, unresolved ties, both side-by-side panels, filters/sorts, minute polling, failed-refresh retention, outside-window pausing and tab state.

## Current and Projected views

The live toolbar switches between Current and Projected for both side-by-side races. Projected finishes the current week only, retaining completed weeks unchanged. For each submitted starter, Live Proj. = current live points + (MFL game seconds remaining / 3600) × the current-week public Fantasy Sharks projection. No fitting, score normalization, or model blend is applied. Team projected PF is the sum of the starter Live Proj. values; all-play is recomputed across all 32 team totals. Expand Starters to see current points, minutes remaining, Pregame Proj., Live Proj., and team totals.

MFL omits some unprojected players: they are labeled No FS projection and receive zero additional projected points. Completed players retain their actual points. All-play ranking uses unrounded projected totals (six decimal precision), not display-rounded one-decimal values. Projected Potential tiebreakers optimize the eligible roster using the same live player projection formula. The updater caches weekly projections for five minutes and reads current points/game clocks each minute.

## Starter game clocks

The team hover lists starters in MFL position order, then last/first name. Mins Rem displays total remaining minutes:seconds followed by [quarter clock]. Normal regulation time uses MFL player game seconds. An optional public ESPN NFL scoreboard supplies explicit overtime, final and halftime markers, matched by NFL teams, season and scheduled kickoff. In overtime, remaining projection time equals only the OT period clock, with no extra regulation quarters added. If period metadata is unavailable, MFL clocks remain in use. Player scores and Fantasy Sharks projections always come from MFL.

## Overtime buffer

The displayed label is Updated Live · Sundays 1:00–11:59 PM ET · Mondays 8:00–11:59 PM ET. Both browser polling and background collection actually continue through 12:30 a.m. Eastern on the following Monday/Tuesday, including the 12:30 minute. Eastern daylight saving time is handled with America/New_York; no other early-morning windows are active.
