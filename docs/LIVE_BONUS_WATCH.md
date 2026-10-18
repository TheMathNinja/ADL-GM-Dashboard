# Live Bonus Game Watch

Public provisional live standings, separate from official weekly results and model forecasts. The current quarter appears on the left and Regular Season on the right, with responsive stacking on narrow screens. Both panels use the same snapshot and rank APW, then cumulative PF, then live eligible-roster Potential Points. Exact ties remain tied; a boundary tie is not assigned by franchise ID. All-play record precedes Points For.

`collect_live_bonus.py` reads public MFL `liveScoring&DETAILS=1` for the current week, rather than substituting completed team scores. It adds completed `weeklyResults` for carry-forward; those contain MFL’s recorded `opt_pts`. Live Potential is optimized using public player positions, current eligible roster statuses and the actual league lineup limits. All live results and tiebreakers remain provisional.

Snapshots contain only public franchise IDs, live totals, player counts and prior weekly team totals. They are written to an isolated orphan `live-bonus-watch` branch, not main. No credentials, personal projections, pending trades or model parameters are published. No official Bonus Game outcomes or league settings are modified.

The scheduled workflow starts/continues a collector hourly at :50 on Sunday/Monday/Tuesday UTC. The worker itself enforces America/New_York time: Sunday 13:00–23:45 and Monday 20:00–23:45, including daylight-saving changes. It may warm up for up to 20 minutes before the window without scraping. Within a window it checks MFL once per minute and stops after 345 minutes or the window’s end, whichever is first. The latest queued bootstrap continues a long Sunday window. Only one collector can run per league. An owner can dispatch `once=true` for a single refresh.

GitHub scheduled starts and MFL’s own feed updates can be delayed. Long-running collectors bridge hourly scheduler delays; the browser shows the actual check timestamp and marks snapshots delayed after 150 seconds during live hours. A failed scrape never replaces the last valid snapshot. The visible Live tab reads the shared public snapshot every minute, stops automatic requests outside the ET windows or while hidden, and resumes when visible. Every read has a minute cache key and disables browser cache. The Refresh control re-reads the latest shared snapshot.

Neither the browser nor the data worker reruns the scoring model. Existing completed-quarter results, historical outlooks, projected PPG, Bonus probabilities, playoff odds and regular weekly updates retain their current behavior. Future Bonus module builds retain the new tab via the template.

Checks cover Eastern/DST windows, full 32-team feed validation, legal and partial lineups, current-quarter and season carry-forward, APW conservation, PF/Potential tiebreakers, unresolved ties, both side-by-side panels, filters/sorts, minute polling, failed-refresh retention, outside-window pausing and tab state.
