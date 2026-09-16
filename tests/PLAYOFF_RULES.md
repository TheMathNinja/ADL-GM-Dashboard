# ADL playoff rules

`adl_rank_playoffs()` is shared by actual standings, forecast standings, Monte Carlo outcomes, and the completed-season shortcut.

Division qualification: overall win percentage, mini-league head-to-head percentage among teams tied for first on overall percentage, cumulative all-play percentage, total points, potential points.

Wild cards: the next three non-division-winners per conference by overall win percentage, all-play percentage, total points, potential points.

Seed the seven qualifiers solely by all-play percentage, total points, potential points. Division status and overall percentage do not affect seeding. Equal all-play game counts make all-play percentage equivalent to cumulative all-play record here.

The report simulates the regular season only; it does not determine actual postseason matchups. A postseason bracket consumer must re-sort surviving qualifiers by these seeding criteria each round, without re-running qualification.

Actual standings use recorded potential points. The existing score model has no separate potential-points distribution: forecasts use expected actual scoring plus the observed nonnegative potential-minus-actual gap; simulations use each score draw plus that same gap. This is a tiebreaker approximation, not a new validated potential-points model. Projected head-to-head uses expected matchup credits; simulation head-to-head uses the actual score draws.

If every listed criterion is identical, the bylaws supplied do not specify a further tiebreaker; input order remains the display fallback. No alphabetical or franchise-ID rule is claimed as a bylaw.

Run `Rscript tests/test_playoff_rules.R`. The shared refresh workflow also runs these checks before rebuilding reports.
