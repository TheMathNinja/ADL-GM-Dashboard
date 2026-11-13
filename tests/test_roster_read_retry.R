source("R/roster_source.R")

exercise <- function(values) {
  calls <- 0L
  delays <- numeric()
  result <- tryCatch(retry_roster_read(function() {
    calls <<- calls + 1L
    value <- values[[calls]]
    if (inherits(value, "error")) stop(value)
    value
  }, sleep = function(seconds) delays <<- c(delays, seconds)), error = identity)
  list(calls = calls, delays = delays, result = result)
}
outage <- simpleError("MFL API request failed with <Server error: (503) Service Unavailable>")
recovered <- exercise(list(outage, outage, data.frame(player_id = "123")))
stopifnot(recovered$calls == 3L, identical(recovered$delays, c(10, 30)),
          recovered$result$player_id == "123")
failed <- exercise(rep(list(outage), 3))
stopifnot(failed$calls == 3L, identical(failed$result, outage))
for (message in c("Unauthorized (401)", "Forbidden (403)", "Not found (404)", "invalid roster schema")) {
  result <- exercise(list(simpleError(message)))
  stopifnot(result$calls == 1L, inherits(result$result, "error"), !length(result$delays))
}
stopifnot(exercise(list(simpleError("Connection timed out"), "ok"))$result == "ok")

# Forced-live failure must not touch a stale snapshot or rewrite existing output.
fetch_live_rosters <- function(...) stop(outage)
read_snapshot_rosters <- function(...) stop("Snapshot fallback must not run")
write_roster_cache <- function(...) stop("Cache write must not run")
path <- tempfile(fileext = ".csv")
writeLines("previous verified cache", path)
failed <- tryCatch(load_current_rosters(source = "auto", force_live = TRUE, cache_path = path), error = identity)
stopifnot(identical(failed, outage), identical(readLines(path), "previous verified cache"))
unlink(path)
cat("PASS: transient roster reads recover; permanent errors fail; forced-live failures preserve prior output.\n")
