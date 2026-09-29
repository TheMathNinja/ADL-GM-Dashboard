import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('elo_chart_range', Path(__file__).resolve().parents[1]/'scripts/elo_chart_range.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class RangeTests(unittest.TestCase):
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


if __name__=='__main__':unittest.main()
