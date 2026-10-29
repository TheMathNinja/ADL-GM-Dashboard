"""Wire capabilities are independent of statistical model names and fitted weights."""
import json
import math

FULL_MODEL_SCHEMA = 'adl-eb-counterfactual/1'
PATH_SCHEMA = 'team-season-paths/1'


def model_requirements(root):
    model = json.loads((root / 'data/adl_scoring_model.json').read_text())['2026']
    weights = model['cases']['forecast']['weights']
    if (not isinstance(weights, list) or len(weights) != 4 or
            any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 for v in weights) or
            not math.isclose(sum(weights), 1, abs_tol=1e-9, rel_tol=0)):
        raise ValueError('ADL forecast weights must contain four finite nonnegative values summing to one')
    schema = model.get('counterfactual_schema', FULL_MODEL_SCHEMA)
    if schema != FULL_MODEL_SCHEMA:
        raise ValueError('ADL exporter does not implement counterfactual schema ' + str(schema))
    return model, schema, weights
