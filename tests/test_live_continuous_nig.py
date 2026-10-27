import sys,json,unittest,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import numpy as np
from live_continuous_nig import remaining_moments,projected_points,simulate,nig_quantiles
from live_win_probability import add_probabilities
from collect_live_bonus import player_projection
from fs_pregame_calibration import load_calibration

MODELS=json.loads((Path(__file__).resolve().parents[1]/'data/live_win_probability.json').read_text())
LEAGUE=next(k for k,v in MODELS.items() if v.get('shape')=='ContinuousNIG');MODEL=MODELS[LEAGUE]
def player(pid='p',seconds=1200,status='3Q 5:00'):
    return dict(id=pid,position='WR',nflTeam='CHI',nflGame='CHI|GBP',gameSide=1,score=8.,seconds=seconds,projectionSeconds=seconds,gameStatus=status,pregameProjection=12.,calibratedPregameProjection=13.,nflScoreboard=[dict(team='CHI',score=14),dict(team='GBP',score=10)])
def team(tid,p,score=8):return dict(id=tid,score=score,starters=p,opponentIds=['B' if tid=='A' else 'A'])

class ContinuousNIGTests(unittest.TestCase):
    def test_display_is_analytic_mean_not_one_draw(self):
        p=player();mean,sd,_=remaining_moments(p,MODEL);draw=simulate([team('A',[p])],MODEL,65536)['A']
        self.assertEqual(projected_points(p,MODEL),8+mean)
        self.assertAlmostEqual(draw.mean(),8+mean,delta=max(.05,sd*.015))
        self.assertAlmostEqual(draw.var(),sd**2,delta=sd**2*.09)

    def test_shared_nfl_player_cancels_exactly(self):
        p=player();s=simulate([team('A',[p],10),team('B',[copy.deepcopy(p)],7)],MODEL,4096)
        np.testing.assert_allclose(s['A']-s['B'],3,atol=1e-12)

    def test_final_deterministic_but_pending_overtime_random(self):
        p=player(seconds=600,status='Awaiting OT');p['seconds']=0
        mean,sd,fallback=remaining_moments(p,MODEL);self.assertTrue(fallback);self.assertGreater(sd,0);self.assertGreater(mean,0)
        self.assertGreater(simulate([team('A',[p])],MODEL,1024)['A'].var(),0)
        p['gameStatus']='Final';np.testing.assert_array_equal(simulate([team('A',[p])],MODEL,1024)['A'],np.full(1024,8.))

    def test_incomplete_lineup_and_reciprocal_probabilities(self):
        snap=dict(teams=[team('A',[player()]),team('B',[player('q')],10)])
        add_probabilities(snap,MODEL,4096);a=snap['teams'][0]['liveMatchups']['B'];b=snap['teams'][1]['liveMatchups']['A']
        self.assertAlmostEqual(sum(a.values()),1);self.assertEqual(a['win'],b['loss']);self.assertEqual(a['tie'],b['tie'])
        self.assertEqual(snap['liveProbabilityModel']['id'],MODEL['id'])

    def test_collector_projection_matches_simulation_mean(self):
        cal=load_calibration(LEAGUE);g={'CHI':dict(state='in',period=3,clock=300,nflGame='CHI|GBP',gameSide=1,scoreboard=[dict(team='CHI',score=14),dict(team='GBP',score=10)])}
        p=player_projection(dict(id='p',score=8,gameSecondsRemaining=1200,status='starter'),{'p':dict(position='WR',team='CHI')},{'p':12},g,calibration=cal)
        self.assertAlmostEqual(p['liveProjection'],projected_points(p,MODEL),places=5)
        self.assertEqual(p['pregameProjection'],12)
        self.assertEqual(p['liveProjectionModel'],MODEL['id'])

    def test_no_projection_and_no_time_add_nothing(self):
        p=player();p.update(pregameProjection=None,calibratedPregameProjection=None)
        self.assertEqual(projected_points(p,MODEL),8)
        p.update(gameStatus='Bye',seconds=0,projectionSeconds=0);self.assertEqual(remaining_moments(p,MODEL)[:2],(0,0))

    def test_shapes_finite_smooth_and_standardized(self):
        u=(np.arange(65536)+.5)/65536;spec=MODEL['continuousShapes']['WR'];x=nig_quantiles(u,.5,spec)
        self.assertLess(abs(x.mean()),.015);self.assertAlmostEqual(x.var(),1,delta=.04)
        a=nig_quantiles(np.array([.025,.1,.5,.9,.975]),.5-1e-7,spec);b=nig_quantiles(np.array([.025,.1,.5,.9,.975]),.5+1e-7,spec)
        self.assertLess(np.max(abs(a-b)),1e-4)

if __name__=='__main__':unittest.main()
