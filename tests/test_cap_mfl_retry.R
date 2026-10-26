source("R/cap_manager_data.R")

response <- function(status) structure(list(status_code=status, url="https://example.test", headers=list()), class="response")
exercise <- function(sequence) {
  calls <- 0L
  get <- function(...) {
    calls <<- calls+1L
    result <- sequence[[calls]]
    if (inherits(result,"error")) stop(result)
    response(result)
  }
  result <- tryCatch(cap_http_get("https://example.test", get=get, sleep=function(...) NULL), error=identity)
  list(calls=calls,result=result)
}
recovered <- exercise(list(simpleError("Connection timed out"),200L))
stopifnot(recovered$calls==2L,httr::status_code(recovered$result)==200L)
recovered <- exercise(list(503L,429L,200L))
stopifnot(recovered$calls==3L,httr::status_code(recovered$result)==200L)
failed <- exercise(rep(list(simpleError("Connection timed out")),3))
stopifnot(failed$calls==3L,inherits(failed$result,"error"))
failed <- exercise(list(503L,503L,503L))
stopifnot(failed$calls==3L,inherits(failed$result,"error"))
for (status in c(400L,401L,403L,404L)) {
  failed <- exercise(list(status))
  stopifnot(failed$calls==1L,inherits(failed$result,"error"))
}
cat("PASS: MFL connection/service retries recover, remain bounded, and preserve permanent failures.\n")
