# ADL UFA calendar

UFA opens on the **third Monday in June at noon America/New_York**, every league year. Use `adl_ufa_start(season)` from `R/adl_calendar.R`; do not hardcode June 15 or infer this from an old season's CSV. Examples: June 15, 2026; June 21, 2027; June 19, 2028.

The portable calendar helper is also imported by the commissioner dashboard's UFA bid-adjustment and inactivity checks, the GM dashboard's legacy inactivity checks, and `LeagueFeatures/CompensatoryPicks/get_compensatory_picks.R`. Keep these helper copies identical when changing league calendar rules. Loaded inactivity configuration derives its UFA opening and legacy three-day window from this rule; other event dates remain configured independently.

CFA auction eligibility runs from that instant (inclusive) to July 1 at midnight Eastern (exclusive). Trade acquisitions count only on an Eastern calendar date strictly after that player's qualifying UFA auction win. Trades have no July 1 cutoff. This rule applies to the greyed-out SD-floor display as well as qualifying CFAs.
