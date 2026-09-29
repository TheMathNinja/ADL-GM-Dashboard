# Thursday official refresh

The score-correction poll runs every 15 minutes from Thursday 03:45 Eastern.
It dispatches the unified worker once even if player scores are unchanged,
then only for new score revisions. A failed worker is retried by the poll.

The worker refreshes Elo, Bonus Games, playoff views, and Payouts (plus ADL
Extension Calculator). On official runs it also requests MFL Bonus Games
entry through Reference!Z12:Z13 in the existing Payouts book. The same
five-minute Apps Script bridge processes these requests; it uses the existing
BonusMFL commissioner credentials and the GitHub score snapshot, not a new
MFL score scrape. Both Apps Script source files are versioned beside this note.

Only completed bonus periods are eligible: Q1/Q2/Q3/Q4 after Weeks 3/6/9/12,
plus the regular-season bonus after Week 12. The date guard prevents premature
entries. Existing matching MFL entries are left alone; conflicts fail visibly
rather than silently replacing a commissioner's adjustment. After an uncertain
submission, the next workflow reads live MFL before attempting missing entries.

Completion receipts require successful MFL verification and Payouts publication.
The shared completion email waits for both leagues' official receipts and live
site verification. A preview never satisfies the official completion check.

The manual verify_bonus_mfl.yml workflow exercises the authenticated request,
MFL login/form reconciliation and acknowledgement in preview mode. It never
submits a standings adjustment. Preview artifacts contain the planned entries.
