# Per-scrape live probability collection

Every successfully collected snapshot is saved to the `live-bonus-watch` branch under `archive/<season>/week-<week>/<UTC date>/<UTC timestamp>-<content hash>.json.gz`. Unchanged scores still produce a separate timestamped observation. Data is gzip-compressed JSON, retained in Git rather than expiring workflow artifacts. Failed requests do not invent observations; a successful score scrape with unavailable probabilities is retained as explicitly missing odds.

Each file includes the full snapshot: per-opponent win/tie/loss probabilities, current/projected scores, starter identities, positions, injury flags, NFL-game grouping, remaining seconds, FS/YTD projections, prior completed-week results, and source timestamps. Probability metadata contains the exact fitted parameters, seed, simulation count, NumPy version, and model ID. The archive envelope records the collector source commit. These allow replay and later joins to corrected official matchup outcomes.

The archive file and latest `live.json` are published atomically in a single commit. An archive failure cannot silently update the dashboard while losing that scrape's evidence. Hash-qualified filenames prevent distinct observations from replacing one another, including multiple scrapes in one minute.

For calibration, use official finalized matchup outcomes as truth and count each matchup once in a calibration time bucket. Repeated minute-level observations from one game are correlated: do not treat them as thousands of independent games. Report probability calibration/Brier by remaining-time bucket and overall, with uncertainty clustered by matchup (and week where appropriate). Final outcomes are not yet known for ongoing games; the archive does not label provisional live scores as official results.

Collection begins with this deployment. Earlier `live.json` revisions also exist in the data branch's Git history, but are not relabeled as newly collected archive files.
