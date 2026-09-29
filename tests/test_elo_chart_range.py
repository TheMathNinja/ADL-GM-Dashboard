import copy
import importlib.util
from pathlib import Path
import unittest
from io import BytesIO
from types import SimpleNamespace
from zipfile import ZipFile

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


if __name__=='__main__':unittest.main()
