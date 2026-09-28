# Run from the repository root. Uses committed caches; no scrape or live changes.
source("R/historical_evaluation.R")

run_historical_evaluation <- function() {
  files <- list.files("data/playoff_history", "^ADL_weekly_history_[0-9]{4}\\.rds$", full.names = TRUE)
  if (!length(files)) stop("Missing historical caches")
  history <- do.call(rbind, lapply(files, function(path) as.data.frame(readRDS(path))))
  results <- lapply(c("all_other_seasons", "past_only"), function(method)
    adl_evaluate_ppg(history, method))
  predictions <- do.call(rbind, lapply(results, `[[`, "predictions"))
  folds <- do.call(rbind, lapply(results, `[[`, "folds"))
  skipped <- do.call(rbind, lapply(results, `[[`, "skipped"))
  metrics <- function(d, scope) {
    data.frame(method = d$method[1], scope,
      evaluation_seasons = paste(sort(unique(d$season)), collapse = ";"),
      forecasts = nrow(d), mae = mean(abs(d$error)), rmse = sqrt(mean(d$error^2)),
      bias = mean(d$error))
  }
  summary <- do.call(rbind, lapply(split(predictions, predictions$method), metrics, scope = "all_eligible_seasons"))
  common <- Reduce(intersect, lapply(results, function(r) unique(r$predictions$season)))
  summary <- rbind(summary, do.call(rbind, lapply(
    split(predictions[predictions$season %in% common, ],
          predictions$method[predictions$season %in% common]), metrics, scope = "common_seasons_only")))
  by_year <- do.call(rbind, lapply(split(predictions,
    interaction(predictions$method, predictions$season, drop = TRUE)), metrics, scope = "single_season"))
  out <- "data/model_evaluation"
  dir.create(out, recursive = TRUE, showWarnings = FALSE)
  for (name in c("predictions", "folds", "skipped", "summary", "by_year"))
    write.csv(get(name), file.path(out, paste0(name, ".csv")), row.names = FALSE)
  print(summary, row.names = FALSE)
}
if (sys.nframe() == 0L) run_historical_evaluation()
