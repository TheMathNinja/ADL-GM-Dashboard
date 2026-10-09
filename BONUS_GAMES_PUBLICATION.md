# Bonus Games publication

The 2026 ADL MFL Bonus Games tab uses Home Page Message 4, embedding `docs/bonus-games/index.html` via the public GitHub Pages URL. The saved replacement markup is `docs/bonus-games/mfl-embed.html`; it uses the same full-module link and 1400px iframe as Playoffs.

The preliminary readiness poll after Monday Night Football and Thursday correction poll dispatch the existing official weekly workflow. That workflow validates one MFL score snapshot, builds Playoffs and Bonus Games with the shared quarterly model, verifies their quarterly forecasts match, and publishes the generated pages. Thursday runs apply official scoring corrections through the same build path.

Google synchronization now updates only the Elo workbook. The old Bonus Games Google workbooks are neither read nor written by this step. They are retained as archives. Official Bonus Games entries in MFL continue through the existing verified standings bridge.

The new dashboard build and quarterly synchronization gate must complete before publication can be marked successful.
