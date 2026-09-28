# GM career profiles

The popup follows the current GM's ADL history, including other franchises.
Names use the existing leaderboard aliases. Current ADL co-managers have identical
historical membership; shared seasons and games are counted once.

`gm_career_seasons.json` contains audited 2016–2025 team-season records/finishes.
`gm_career_profiles.json` contains completed-season totals for the 2026 roster.
`gm_career_sources.json` lists archived playoff and payout sheet URLs.
`scripts/gm_profiles.R` adds this season's completed games from the existing score
snapshot. It includes postseason games even when the qualifying picture freezes.

Experience counts completed seasons. All-play rank uses cumulative adjusted win
percentage, (wins + 0.5 * ties) / games, among the 32 current teams. Ties share the
best occupied rank. Best/worst finishes include every matching completed year.

MFL weeklyResults with W=YTD&MISSING_AS_BYE=1 includes bye teams. Count weeks 1–16
through 2020 and 1–17 thereafter. Every season has 32 teams, wins equal losses,
and 31 all-play comparisons per team-week. All 320 ADL adjusted-win totals match
the saved historical standings.

Finish order: playoff teams 1–12 through 2019, 1–14 from 2020. Final Super Bowl
and Bragging Rights winners/losers determine places. Payout sheets verify
conference finishes and ladder champions for 2018–2025. Original league-page
Week 16 matchup tables and MFL results supply 2016–2017. Consecutive ladder
championship rematches use series W-L, then cumulative points. The two ladder
champions come next by full-season all-play. Other teams follow by full-season
all-play, with total points breaking equal all-play records.

League pages: https://api.myfantasyleague.com/{year}/home/60206
Schedules: https://api.myfantasyleague.com/{year}/export?TYPE=schedule&L=60206&JSON=1
Scores use the same export endpoint with TYPE=weeklyResults and the parameters
above. Public GM names and league results only; no private contact details.

For a new season or ownership change, rebuild the roster's baseline from audited
season rows. The renderer rejects the wrong season to avoid silently misattributing
careers or double-counting a completed season. Weekly updates need no new scrape.
