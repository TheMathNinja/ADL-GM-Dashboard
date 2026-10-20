import copy
import importlib.util
from pathlib import Path
import unittest
import sys
import json
import tempfile
from unittest.mock import patch
from io import BytesIO
from types import SimpleNamespace
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
spec = importlib.util.spec_from_file_location('elo_chart_range', Path(__file__).resolve().parents[1]/'scripts/elo_chart_range.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class RangeTests(unittest.TestCase):
    def test_export_reads_only_readout_and_resolves_theme_font(self):
        out=BytesIO()
        rel=m.REL; sheet=m.SHEET
        with ZipFile(out,'w') as z:
            z.writestr('xl/workbook.xml',f'<workbook xmlns="{sheet}" xmlns:r="{rel}"><sheets><sheet name="Readout" r:id="r1"/></sheets></workbook>')
            z.writestr('xl/_rels/workbook.xml.rels','<Relationships><Relationship Id="r1" Target="/xl/worksheets/sheet1.xml"/></Relationships>')
            z.writestr('xl/worksheets/sheet1.xml',f'<worksheet xmlns="{sheet}" xmlns:r="{rel}"><drawing r:id="d1"/></worksheet>')
            z.writestr('xl/worksheets/_rels/sheet1.xml.rels','<Relationships><Relationship Id="d1" Target="../drawings/drawing1.xml"/></Relationships>')
            z.writestr('xl/drawings/drawing1.xml',f'<drawing xmlns:c="{m.NS["c"]}" xmlns:r="{rel}"><c:chart r:id="c1"/><c:chart r:id="c2"/></drawing>')
            z.writestr('xl/drawings/_rels/drawing1.xml.rels','<Relationships><Relationship Id="c1" Target="../charts/chart1.xml"/><Relationship Id="c2" Target="../charts/chart2.xml"/></Relationships>')
            z.writestr('xl/theme/theme1.xml',f'<a:theme xmlns:a="{m.NS["a"]}"><a:minorFont><a:latin typeface="Arial"/></a:minorFont></a:theme>')
            style='<a:p><a:pPr><a:defRPr sz="900"><a:solidFill><a:srgbClr val="595959"/></a:solidFill><a:latin typeface="+mn-lt"/></a:defRPr></a:pPr></a:p>'
            series='<c:ser><c:spPr><a:ln><a:solidFill><a:srgbClr val="003594"/></a:solidFill></a:ln></c:spPr></c:ser>'*16
            for i,conf in enumerate(['NFC','AFC'],1):
                xml=f'<c:chartSpace xmlns:c="{m.NS["c"]}" xmlns:a="{m.NS["a"]}"><c:chart><c:title><a:t>ADL {conf} Elo Ratings</a:t>{style}</c:title><c:plotArea>{series}<c:catAx><c:txPr>{style}</c:txPr></c:catAx><c:valAx><c:txPr>{style}</c:txPr></c:valAx></c:plotArea><c:legend><c:txPr>{style}</c:txPr></c:legend></c:chart></c:chartSpace>'
                z.writestr(f'xl/charts/chart{i}.xml',xml)
            z.writestr('xl/charts/chart3.xml','INVALID DUPLICATE CHART ON ANOTHER TAB')
        book=SimpleNamespace(id='test',client=SimpleNamespace(request=lambda *args:SimpleNamespace(content=out.getvalue())))
        styles=m.exported_styles(book,'ADL')
        self.assertEqual(len(styles),2)
        self.assertEqual(styles['ADL NFC Elo Ratings']['colors'],['#003594']*16)
        self.assertEqual(styles['ADL AFC Elo Ratings']['vAxis']['fontName'],'Arial')

    def test_smallest_symmetric_window(self):
        for low, high, expected in [(1344.618326,1641.067709,(1300,1700)),
                                    (1431.95912,1588.901387,(1400,1600)),
                                    (1400,1600,(1400,1600)),
                                    (1399.999999,1500,(1350,1650)),
                                    (1500,1600.000001,(1350,1650)),
                                    (1500,1500,(1450,1550))]:
            with self.subTest(low=low, high=high):
                actual=m.bounds([low,high]+[1500]*30)
                self.assertEqual(actual,expected)
                self.assertLessEqual(actual[0],low)
                self.assertGreaterEqual(actual[1],high)

    def test_invalid_input_fails_closed(self):
        for values in [[1500]*31,[1500]*33,[None]+[1500]*31,['1500']+[1500]*31,
                       [True]+[1500]*31,[float('nan')]+[1500]*31,[float('inf')]+[1500]*31]:
            with self.assertRaises(ValueError):m.bounds(values)

    def charts(self):
        return [dict(chartId=i,position={'overlayPosition':{'widthPixels':299,'heightPixels':338}},
            spec={'title':f'ADL {conf} Elo Ratings','fontName':'Verdana',
                  'basicChart':{'chartType':'LINE','legendPosition':'BOTTOM_LEGEND',
                    'axis':[{'position':'BOTTOM_AXIS','title':'Week'},
                            {'position':'LEFT_AXIS','format':'0','viewWindowOptions':{'viewWindowMin':1300,'viewWindowMax':1700,'viewWindowMode':'EXPLICIT'}}],
                    'series':[{'targetAxis':'LEFT_AXIS','colorStyle':{'rgbColor':{'red':j/16}},
                               'series':{'sourceRange':{'sources':[{'sheetId':5,'startColumnIndex':j}]}}} for j in range(16)]}})
                for i,conf in enumerate(['NFC','AFC'])]

    def test_only_axis_limits_change_and_both_conferences_match(self):
        old=self.charts();backup=copy.deepcopy(old)
        new,req=m.plan(old,1400,1600)
        self.assertEqual(old,backup)
        self.assertEqual(len(req),2)
        for before,after in zip(old,new):
            self.assertEqual(after['spec']['basicChart']['axis'][1]['viewWindowOptions'],
                             {'viewWindowMin':1400,'viewWindowMax':1600,'viewWindowMode':'EXPLICIT'})
            restored=copy.deepcopy(after)
            restored['spec']['basicChart']['axis'][1]['viewWindowOptions']=before['spec']['basicChart']['axis'][1]['viewWindowOptions']
            self.assertEqual(restored,before)
        self.assertEqual(m.plan(new,1400,1600)[1],[])

    def test_unexpected_charts_fail_before_requests(self):
        charts=self.charts();charts[1]['spec']['basicChart']['series'].pop()
        with self.assertRaises(ValueError):m.plan(charts,1400,1600)
        charts=self.charts();charts[0]['spec']['basicChart']['series'][0]['targetAxis']='RIGHT_AXIS'
        with self.assertRaises(ValueError):m.plan(charts,1400,1600)


class PendingRangeTests(unittest.TestCase):
    def setUp(self):
        self.teams = {f'Team {i}': 1395.397 if i == 0 else 1500.0 for i in range(32)}
        self.charts = RangeTests().charts()
        for chart in self.charts:
            chart['spec']['basicChart']['domains'] = [{'domain': {'sourceRange': {'sources': [{'sheetId':5}]}}}]
        self.styles = {c['spec']['title']: {'colors': ['#003594']*16} for c in self.charts}
        self.old = dict(version=1, request_id='a'*32, league='ADL', season=2026,
                        week=6, lower=1350, upper=1650, teams=self.teams,
                        charts=[dict(chart_id=c['chartId'],title=c['spec']['title'],
                                     style=self.styles[c['spec']['title']]) for c in self.charts])
        self.cells = {'Z14': json.dumps(self.old), 'Z15': ''}
        self.writes = []
        self.dispatched = []

        def update(cell, value):
            if cell == 'Z14':
                previous = json.loads(self.cells['Z14'])['request_id']
                self.assertEqual(json.loads(self.cells['Z15'])['request_id'], previous,
                                 'A new request must not overwrite an unacknowledged request')
            self.writes.append((cell, value))
            self.cells[cell] = value
        self.ref = SimpleNamespace(acell=lambda cell: SimpleNamespace(value=self.cells[cell]),
                                   update_acell=update)
        self.bridge = SimpleNamespace(worksheet=lambda name: self.ref)

    def complete(self, **context):
        self.dispatched.append(context['run_id'])
        q = json.loads(self.cells['Z14'])
        stale = q['teams'] != self.teams
        if not stale:
            self.charts = m.plan(self.charts,1350,1650)[0]
        self.cells['Z15'] = json.dumps(dict(request_id=q['request_id'], league='ADL',
                                           status='failure' if stale else 'success',
                                           error='Elo changed after range request' if stale else ''))
        return dict(status='success', league='ADL', operation='elo_chart')

    def sync(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder, \
             patch.object(m, 'read_current', return_value=(6,self.teams)), \
             patch.object(m, 'read_charts', side_effect=lambda *a: copy.deepcopy(self.charts)), \
             patch.object(m, 'exported_styles', return_value=self.styles):
            return m.sync_ranges(object(),'ADL',apply=True,output_dir=folder,bridge_book=self.bridge)

    def test_replays_legacy_pending_request_without_overwriting_it(self):
        with patch.object(m,'request_bridge',side_effect=self.complete):
            report=self.sync()
        self.assertTrue(report['verified'])
        self.assertEqual(self.dispatched,['a'*32])
        self.assertEqual(self.writes,[])
        self.assertEqual(m.plan(self.charts,1350,1650)[1],[])

    def test_stale_ratings_acknowledged_before_fresh_request(self):
        old=copy.deepcopy(self.old);old['teams']['Team 0']=1401
        self.cells['Z14']=json.dumps(old)
        with patch.object(m,'request_bridge',side_effect=self.complete):
            report=self.sync()
        self.assertTrue(report['verified'])
        self.assertEqual(len(self.writes),1)
        self.assertEqual(self.dispatched[0],'a'*32)
        self.assertNotEqual(self.dispatched[1],'a'*32)
        self.assertIn('created_at',json.loads(self.writes[0][1]))

    def test_timeout_retains_request_and_next_run_can_resume(self):
        with patch.object(m,'request_bridge',return_value=dict(status='success',league='ADL',operation='elo_chart')), \
             patch.object(m.time,'sleep'):
            with self.assertRaises(TimeoutError):m.finish_range_request(self.ref,'ADL',self.old)
        self.assertEqual(json.loads(self.cells['Z14'])['request_id'],'a'*32)
        with patch.object(m,'request_bridge',side_effect=self.complete):
            self.assertEqual(m.finish_range_request(self.ref,'ADL',self.old)['status'],'success')

    def test_wrong_deployment_response_fails_immediately(self):
        with patch.object(m,'request_bridge',return_value={'status':'success'}),patch.object(m.time,'sleep') as sleep:
            with self.assertRaisesRegex(RuntimeError,'deployment'):
                m.finish_range_request(self.ref,'ADL',self.old)
            sleep.assert_not_called()

    def test_async_queue_waits_for_matching_completion_receipt(self):
        def queued(**context):
            self.complete(**context)
            return {'status':'success','queued':True}
        with patch.object(m,'request_bridge',side_effect=queued):
            report=self.sync()
        self.assertTrue(report['verified'])

    def test_queue_acceptance_alone_is_not_completion(self):
        with patch.object(m,'request_bridge',return_value={'status':'success','queued':True}) as dispatch, \
             patch.object(m.time,'sleep'):
            with self.assertRaises(TimeoutError):m.finish_range_request(self.ref,'ADL',self.old)
        self.assertEqual(self.cells['Z15'],'')
        dispatch.assert_called_once()

    def test_wrong_league_and_manual_style_changes_fail_closed(self):
        with patch.object(m,'request_bridge') as dispatch:
            with self.assertRaises(ValueError):m.finish_range_request(self.ref,'FAFL',self.old)
            altered=copy.deepcopy(self.old);altered['charts'][0]['style']['colors'][0]='#FFFFFF'
            self.cells['Z14']=json.dumps(altered)
            with self.assertRaisesRegex(ValueError,'manual styling'):self.sync()
            dispatch.assert_not_called()
        self.assertEqual(self.writes,[])

    def test_rollback_failure_does_not_replace_request(self):
        def failed(**context):
            self.cells['Z15']=json.dumps(dict(request_id='a'*32,league='ADL',status='failure',rollback_error='test'))
            return dict(status='success',league='ADL',operation='elo_chart')
        with patch.object(m,'request_bridge',side_effect=failed):
            with self.assertRaisesRegex(ValueError,'rollback'):self.sync()
        self.assertEqual(self.writes,[])


if __name__=='__main__':unittest.main()
