# Historical model evaluation

The standard historical evaluation is **all other completed seasons** (leave-one-season-out). The target season is excluded from regression fitting. For a 2023 test, train on 2021, 2022, 2024 and 2025. The default evaluation covers **all five seasons, 2021–2025**, after every Week 1–11.

Run from the repository root:

```sh
Rscript scripts/evaluate_playoff_model.R
Rscript tests/test_historical_evaluation.R
```

The runner reads committed historical caches; no network or scrape is required. Outputs record every training fold, team prediction, excluded evaluation year, MAE, RMSE and bias. These metrics measure **remaining actual PPG**, not potential PPG, wins, all-play or playoff probabilities. The model is the deployed raw Potential-PPG regression, without the experimental 90% correction or season-factor models.

`summary.csv` leads with all-other-seasons performance over all eligible years. The separate `past_only` comparison requires at least two earlier complete training seasons and therefore evaluates 2023–2025. `common_seasons_only` rows restrict both methods to the same evaluation years for a fair comparison. Do not compare different year sets as if training method were the only difference.

All-other-seasons measures retrospective cross-season generalization. Past-only measures chronological forecasting performance. Later seasons are legitimate training data for the former, but those results must not be described as forecasts available at the time. Live production forecasts still use completed prior seasons only; for 2026, that is 2021–2025.

Future model comparisons should use this all-other-seasons convention and evaluate every year with the required inputs. A preseason-input model may need a narrower range if predecessor-season data or archived preseason estimates are missing; it does not automatically require a 2023 cutoff. Document excluded years and reasons, fit preprocessing only on the training fold, and avoid using the held-out season's later outcomes in any inputs. Lagged features in later training seasons require a separate leakage audit before extending this evaluator to those models.

Weekly checkpoints overlap and are not independent samples. Model or hyperparameter selection using these results is exploratory unless evaluated in an additional independent or nested validation procedure.
