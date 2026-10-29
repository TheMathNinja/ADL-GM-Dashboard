"""Export the public R05/L17 player states and the selected ADL EB response.

Counterfactuals change ownership, not already-observed Potential or annual fits.
This export uses the production player updater and verifies its lineup totals.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from player_team_strength import RuntimeStudy, weekly_sharks_prior
from player_strength_core import POSITIONS, mapped
from player_positive_core import prepare, run


def export_full_team_model(root, week, metadata, forecast):
    d = Path(root) / 'data/player_strength'
    study = RuntimeStudy(root, 2026)
    fits = {r['pos']: r for r in json.loads((d/'fits_2026.json').read_text())}
    from availability_recovery import predict as recovery_probability
    recovery_path = d/'availability_recovery_2026.json'
    recovery = json.loads(recovery_path.read_text()) if recovery_path.exists() else None
    predictions = {}
    for pos in POSITIONS:
        rec = fits[pos]
        f = weekly_sharks_prior(root, 2026, pos, rec['prior'])
        c = study.cubes[2026, pos]
        from missing_fs_prior import missing_fs_initial_mean
        membership = pd.read_csv(d/'fantasy_rosters.csv', dtype={'player_id': str, 'franchise_id': str})
        c['initial_mean'] = missing_fs_initial_mean(root, 2026, pos, c['ids'], mapped(f['prior'], c['first_fs']), (~np.isfinite(c['first_fs'])) | (~np.isfinite(c['projection'][0])) | c['known_out'][0] | (c['scheduled_bye'][0] == 1), membership)
        states, _, _ = run(prepare(study, 2026, pos, f), f, 'position', rec['q'])
        past = np.where(np.isfinite(c['active_score'][:week]), 1., np.where(c['inactive'][:week] == 1, 0., np.nan))
        for j in range(week):
            past[j] = np.where([(2026, j+1, str(t)) in study.opp for t in c['team'][j]], past[j], np.nan)
        av = f['availability']
        prob = (av['k']*av['mean'] + np.nansum(past, 0))/(av['k']+np.isfinite(past).sum(0))
        scheduled = np.array([[(2026, j+1, str(t)) in study.opp for t in c['team'][j]] for j in range(17)])
        for target in range(week+1, 13):
            delta, _, play = study.context(2026, pos, f['opponent'], week, c['team'][week], target)
            if target == week+1:
                play &= ~c['known_out'][week]
            target_prob = recovery_probability(recovery, c, pos, week, target, scheduled) if recovery else prob
            expected = np.maximum(0, states[week]['mean']*(1+f['opponent_effect']*delta))*target_prob*play
            for pid, value in zip(c['ids'], expected):
                predictions.setdefault(pid, {'pos': pos, 'weeks': {}})['weeks'][str(target)] = float(value)
    roster = pd.read_csv(d/'fantasy_rosters.csv', dtype={'player_id': str, 'franchise_id': str})
    roster = roster[roster.week == week]
    raw = pd.read_csv(d/'score_archive.csv', dtype={'player_id': str})
    history = {str(pid): g for pid, g in raw.groupby('player_id')}
    for r in roster.itertuples():
        if r.pos not in fits or r.player_id in predictions:
            continue
        f = fits[r.pos]['prior']
        past = history.get(r.player_id, pd.DataFrame(columns=['week', 'active_score', 'team']))
        past = past[past.week <= week]
        a = past.active_score.dropna().to_numpy()
        prior = float(mapped(f['prior'], [0.])[0])
        gain = f['Pa']/(f['Pa']+f['Ra']/len(a)) if len(a) else 0.
        ability = (1-gain)*prior + gain*(a.mean() if len(a) else prior)
        club = str(past.sort_values('week').iloc[-1].team) if len(past) else str(r.team)
        predictions[r.player_id] = {'pos': r.pos, 'weeks': {str(t): float(max(0, ability)*f['availability']['mean']*((2026, t, club) in study.opp)) for t in range(week+1, 13)}}
    saved = json.loads((Path(root)/'data/adl_scoring_model.json').read_text())['2026']
    case = saved['cases']['forecast']
    assert len(case['weights']) == 4 and np.isclose(sum(case['weights']), 1)
    response = case['cross']/(case['input_latent']+case['input_measurement']/week)
    base = pd.read_csv(d/'team_strength_2026.csv', dtype={'franchise_id': str})
    base = base[base.week == week]
    return dict(version=saved['version'], weights=case['weights'], conversion=case['conversion'], reliability=response,
                players=predictions, rosters=[dict(id=r.player_id, franchise=r.franchise_id, status=r.roster_status, pos=r.pos) for r in roster.itertuples()],
                baseline={fid: {str(r.target_week): [r.starter_strength, r.roster_strength] for r in g.itertuples()} for fid,g in base.groupby('franchise_id')},
                mean=np.asarray(forecast['mu']).tolist(),
                receipt=json.loads((d/'refresh_receipt.json').read_text()), playerModel='R05/L17 + calibrated weekly Sharks')
