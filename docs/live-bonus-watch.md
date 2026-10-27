# Live Bonus Game Watch

ADL and FAFL use the same collector and browser refresh windows in
America/New_York (DST-aware):

- Thursday: 8:00 p.m. through Friday 12:30 a.m.
- Sunday: 9:00 a.m. through Monday 12:30 a.m., including 9:30 a.m. international games
- Monday: 8:00 p.m. through Tuesday 12:30 a.m.

Workers poll about once a minute. The hourly GitHub bootstrap includes the UTC
Thursday/Friday boundary and starts waiting up to 20 minutes before a window.
GitHub runner queues can still delay startup; this is not an exact-time guarantee.
Browser auto-refresh uses the same tested windows. These are the normal live
windows, not a promise to cover every special Wednesday, Friday, Saturday, or
holiday afternoon game.

After an authorized official correction run successfully publishes, the parent
workflow calls live_bonus_watch.yml for one immediate refresh. The collector
requires that run's successful correction receipt, including verified Bonus
Games and Payouts. Monday preliminary runs and manual previews cannot trigger it.
No separate token or Apps Script trigger is needed. The live step cannot cause
earlier published official results to be overwritten or rolled back.

The corrected week becomes completed history; its following week becomes the
minimum live week. If MFL's default liveScoring feed still returns the old week,
the collector explicitly requests W=next and checks the response's actual week.
It never relabels old scores/lineups as the upcoming week. Projections, injuries,
NFL clocks, scoring details, opponents and history follow the selected week.
An unavailable or wrong-week feed fails visibly while preserving the last valid
live snapshot. The next scheduled live worker also honors the correction receipt.

Live data and its small monotonic watch-state.json marker are committed atomically
to the separate live-bonus-watch branch. A delayed writer cannot move the week
backward or replace a newer same-week snapshot. Regular-season Bonus Games end
after Week 12: later official corrections refresh the completed Week 12 view,
not a fictitious Week 13 Bonus Game race.

The normal quarterly tabs, score status, forecasts, official cap snapshots,
Sheets, MFL entries and email recipients are not changed by this feature.

Validation: test_live_rollover.py, test_live_archive.py, test_live_bonus.py,
test_live_windows.cjs and test_thursday_workflow_contract.py. The shared window
fixture tests Thursday, Sunday international starts, Monday, midnight and DST.
Manual workflow dry_run=true reads a single real snapshot without publication.
Set preview_week=8 with dry_run=true to test the upcoming week before its official
rollover receipt exists. Preview weeks cannot be used for publication. Scheduled
runs outside the watch window skip dependency installation and upstream requests.

Schedule references checked October 27, 2026:
https://www.nfl.com/schedules/2026/prime-time/thursday-night-football
https://operations.nfl.com/journey-to-the-nfl/the-nfl-s-international-impact/nfl-international-games
