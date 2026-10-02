"""Keep each league's two Readout charts on the smallest 1500 +/- 50k scale.

Uses the latest 32 unrounded workbook ratings, not the shadow model or historical
trajectory. The existing Apps Script bridge applies bounds while preserving
native imported styles; no Elo cells, formulas, or chart positions are written.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from io import BytesIO
import math
import os
from pathlib import Path
import posixpath
import time
import uuid
from apps_script_bridge import request_bridge
import xml.etree.ElementTree as ET
from zipfile import ZipFile

BOOKS = {
    'ADL': ('1iu7oJUQ8IEhHDTp5RiArK7oTD4-DmjTbI1xtOwuwRBI', 'Data', '26'),
    'FAFL': ('1yWEzFx8hKhhlTQ47gacHSQXmZtPsX9k7hB2s6D6-g3k', '2026', ''),
}
PAYOUTS = {'ADL': '1oh7P9TRUj356U7xjC26X5a6lunYI73zpSPjT11t1Vok',
           'FAFL': '1E-N1YK-udh88c7LFbB57itbMIEAzt6z1N4M5s_J1XBA'}
NS = {'c':'http://schemas.openxmlformats.org/drawingml/2006/chart',
      'a':'http://schemas.openxmlformats.org/drawingml/2006/main'}
REL='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
SHEET='http://schemas.openxmlformats.org/spreadsheetml/2006/main'


def readout_chart_paths(archive):
    def related(source):
        path=posixpath.join(posixpath.dirname(source),'_rels',posixpath.basename(source)+'.rels')
        return {r.get('Id'):posixpath.normpath(posixpath.join(posixpath.dirname(source),r.get('Target'))).lstrip('/')
                for r in ET.fromstring(archive.read(path))}
    workbook=ET.fromstring(archive.read('xl/workbook.xml'))
    sheets=[s for s in workbook.findall(f'.//{{{SHEET}}}sheet') if s.get('name')=='Readout']
    if len(sheets)!=1:
        raise ValueError('Missing exported Readout sheet')
    sheet_path=related('xl/workbook.xml')[sheets[0].get(f'{{{REL}}}id')]
    sheet=ET.fromstring(archive.read(sheet_path))
    sheet_links=related(sheet_path)
    paths=[]
    for drawing in sheet.findall(f'{{{SHEET}}}drawing'):
        drawing_path=sheet_links[drawing.get(f'{{{REL}}}id')]
        drawing_links=related(drawing_path)
        root=ET.fromstring(archive.read(drawing_path))
        paths.extend(drawing_links[c.get(f'{{{REL}}}id')] for c in root.findall('.//c:chart',NS))
    return paths


def exported_styles(book, league):
    # Imported Excel styling is not fully exposed by chart metadata. Preserve
    # the native rendered styles from an authenticated XLSX export instead.
    response = book.client.request('get', f'https://docs.google.com/spreadsheets/d/{book.id}/export?format=xlsx')
    result = {}
    theme_fonts = {}
    def text_style(root, path):
        node = root.find(path, NS)
        if node is None:
            raise ValueError('Missing exported chart text style: '+path)
        color = node.find('a:solidFill/a:srgbClr', NS)
        font = node.find('a:latin', NS)
        if color is None or font is None:
            raise ValueError('Unsupported chart theme text style')
        face=font.get('typeface')
        face=theme_fonts.get(face,face)
        return dict(fontName=face, fontSize=int(node.get('sz'))/100,
                    color='#'+color.get('val'), bold=node.get('b','0')=='1', italic=node.get('i','0')=='1')
    with ZipFile(BytesIO(response.content)) as archive:
        theme=ET.fromstring(archive.read('xl/theme/theme1.xml'))
        for token,kind in [('+mn-lt','minorFont'),('+mj-lt','majorFont')]:
            face=theme.find('.//a:'+kind+'/a:latin',NS)
            if face is not None:
                theme_fonts[token]=face.get('typeface')
        for name in readout_chart_paths(archive):
            root = ET.fromstring(archive.read(name))
            title = ''.join(t.text or '' for t in root.findall('./c:chart/c:title//a:t', NS))
            if title not in {f'{league} NFC Elo Ratings', f'{league} AFC Elo Ratings'}:
                continue
            colors = [s.find('c:spPr/a:ln/a:solidFill/a:srgbClr', NS) for s in root.findall('.//c:ser', NS)]
            if len(colors) != 16 or any(c is None for c in colors):
                raise ValueError('Expected 16 explicit exported series colors')
            base='./c:chart/'
            area=root.find(base+'c:plotArea/c:spPr/a:solidFill/a:srgbClr', NS)
            result[title] = dict(colors=['#'+c.get('val') for c in colors],
                title=text_style(root,base+'c:title//a:defRPr'),
                hAxis=text_style(root,base+'c:plotArea/c:catAx/c:txPr//a:defRPr'),
                vAxis=text_style(root,base+'c:plotArea/c:valAx/c:txPr//a:defRPr'),
                legend=text_style(root,base+'c:legend/c:txPr//a:defRPr'),
                background='#'+area.get('val') if area is not None else None)
    if len(result)!=2:
        raise ValueError('Missing conference charts in native export')
    return result


def bounds(ratings):
    if len(ratings) != 32 or any(type(v) not in (int, float) or not math.isfinite(v) for v in ratings):
        raise ValueError('Range check requires exactly 32 finite numeric Elo ratings')
    # A zero-width axis cannot render; use the smallest positive window if tied.
    x = max(50, 50 * math.ceil(max(abs(v - 1500) for v in ratings) / 50))
    return 1500 - x, 1500 + x


def column(n):
    s = ''
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def scalar_column(rows):
    return [r[0] if len(r) == 1 else None for r in rows]


def read_current(book, league, expected_week=None):
    _, tab, prefix = BOOKS[league]
    data = book.worksheet(tab)
    headers = data.row_values(36)
    start = headers.index(prefix + 'W1OPF') + 1
    if headers[start-1:start+16] != [f'{prefix}W{w}OPF' for w in range(1, 18)]:
        raise ValueError('Unexpected current-season OPF headers')
    scores = data.get(f'{column(start)}37:{column(start+16)}68', value_render_option='UNFORMATTED_VALUE')
    if len(scores) != 32:
        raise ValueError('Incomplete current-season score inputs')
    week = 0
    gap = False
    for w in range(17):
        values = [r[w] if w < len(r) else '' for r in scores]
        if all(v == '' for v in values):
            gap = True
            continue
        if gap or any(type(v) not in (int, float) or not math.isfinite(v) for v in values):
            raise ValueError('Incomplete or noncontiguous scoring week')
        week = w + 1
    if expected_week is not None and week != expected_week:
        raise ValueError(f'Workbook week {week} differs from expected week {expected_week}')
    names = scalar_column(data.get('A2:A33'))
    if len(names) != 32 or len(set(names)) != 32 or not all(isinstance(n, str) and n for n in names):
        raise ValueError('Expected 32 unique workbook team names')
    elo_col = data.row_values(1).index(f'{prefix}W{week}Elo') + 1
    ratings = scalar_column(data.get(f'{column(elo_col)}2:{column(elo_col)}33', value_render_option='UNFORMATTED_VALUE'))
    bounds(ratings)
    expected = dict(zip(names, ratings))
    output = book.worksheet('Readout').get('C2:E33', value_render_option='UNFORMATTED_VALUE')
    if len(output) != 32 or {r[0] for r in output if r} != set(names):
        raise ValueError('Readout team mapping differs from source')
    if any(len(r) != 3 or type(r[2]) not in (int, float) or not math.isfinite(r[2]) or abs(r[2]-expected[r[0]]) > 0.001 for r in output):
        raise ValueError('Readout does not match latest unrounded workbook Elo')
    return week, expected


def read_charts(book, league):
    metadata = book.fetch_sheet_metadata(params={'fields': 'sheets(properties(title),charts)'})
    sheets = [s for s in metadata['sheets'] if s['properties']['title'] == 'Readout']
    if len(sheets) != 1:
        raise ValueError('Missing Readout sheet')
    titles = {f'{league} {conf} Elo Ratings' for conf in ('NFC', 'AFC')}
    charts = [c for c in sheets[0].get('charts', []) if c['spec'].get('title') in titles]
    if len(charts) != 2 or {c['spec']['title'] for c in charts} != titles:
        raise ValueError('Expected one NFC and one AFC Elo chart')
    return charts


def plan(charts, lower, upper):
    desired = deepcopy(charts)
    requests = []
    for chart in desired:
        basic = chart['spec'].get('basicChart', {})
        if basic.get('chartType') != 'LINE' or len(basic.get('series', [])) != 16:
            raise ValueError('Unexpected conference chart type or series count')
        axes = [a for a in basic.get('axis', []) if a.get('position') == 'LEFT_AXIS']
        if len(axes) != 1 or any(s.get('targetAxis', 'LEFT_AXIS') != 'LEFT_AXIS' for s in basic['series']):
            raise ValueError('Unexpected Elo axis assignment')
        window = {'viewWindowMin': lower, 'viewWindowMax': upper, 'viewWindowMode': 'EXPLICIT'}
        current = axes[0].get('viewWindowOptions', {})
        if current.get('viewWindowMin') == lower and current.get('viewWindowMax') == upper:
            continue
        axes[0]['viewWindowOptions'] = window
        requests.append({'updateChartSpec': {'chartId': chart['chartId'], 'spec': chart['spec']}})
    return desired, requests


def sync_ranges(book, league, expected_week=None, apply=False, output_dir=None, bridge_book=None):
    week, teams = read_current(book, league, expected_week)
    lower, upper = bounds(list(teams.values()))
    before = read_charts(book, league)
    desired, requests = plan(before, lower, upper)
    report = dict(league=league, week=week, minimum_rating=min(teams.values()),
                  maximum_rating=max(teams.values()), axis_min=lower, axis_max=upper,
                  x=upper-1500, changed_charts=len(requests), applied=False,
                  checked_at=datetime.now(timezone.utc).isoformat(), before=before, desired=desired)
    path = Path(output_dir or 'artifacts/elo-range')
    path.mkdir(parents=True, exist_ok=True)
    backup = path / f'{league.lower()}-range-check.json'
    backup.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    if apply:
        if requests:
            # Don't overwrite a chart someone changed while the range was read.
            if read_charts(book, league) != before:
                raise ValueError('Charts changed during range check; retry')
            styles = exported_styles(book, league)
            report['preserved_styles'] = styles
            backup.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
            if bridge_book is None:
                raise ValueError('Native chart bridge is required to preserve imported styling')
            ref = bridge_book.worksheet('Reference')
            pending = ref.acell('Z14').value
            ack = ref.acell('Z15').value
            if pending and (not ack or json.loads(pending)['request_id'] != json.loads(ack).get('request_id')):
                raise ValueError('An earlier Elo chart range request is still pending')
            request = dict(version=1,request_id=uuid.uuid4().hex,league=league,season=2026,
                           week=week,lower=lower,upper=upper,teams=teams,
                           charts=[dict(chart_id=c['chartId'],title=c['spec']['title'],style=styles[c['spec']['title']])
                                   for c in before if c['chartId'] in {r['updateChartSpec']['chartId'] for r in requests}])
            ref.update_acell('Z14',json.dumps(request))
            request_bridge()
            for attempt in range(40):
                raw = ref.acell('Z15').value
                ack = json.loads(raw) if raw else {}
                if ack.get('request_id') == request['request_id']:
                    if ack.get('status') != 'success':
                        raise ValueError('Native range update failed: '+ack.get('error','unknown'))
                    break
                time.sleep(15)
            else:
                raise TimeoutError('Native chart bridge did not acknowledge within 10 minutes')
            if exported_styles(book, league) != styles:
                raise ValueError('Rendered chart styles changed unexpectedly; inspect range-check backup')
        actual = read_charts(book, league)
        if plan(actual,lower,upper)[1]:
            raise ValueError('Saved chart axis bounds differ from requested range')
        old_by_id = {c['chartId']:c for c in before}
        for c in actual:
            old = old_by_id[c['chartId']]
            if c.get('position')!=old.get('position') or c['spec']['basicChart']['domains']!=old['spec']['basicChart']['domains']:
                raise ValueError('Chart position or horizontal data range changed')
            if [s['series'] for s in c['spec']['basicChart']['series']] != [s['series'] for s in old['spec']['basicChart']['series']]:
                raise ValueError('Chart team data ranges changed')
        check_week, check_teams = read_current(book, league, week)
        if check_teams != teams:
            raise ValueError('Elo ratings changed during range check; retry')
        report.update(applied=True, verified=True, after=actual)
        backup.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(f'{league} Week {week}: {min(teams.values()):.6f}–{max(teams.values()):.6f}; '
          f'both charts {lower}–{upper} (1500 +/- {upper-1500}); '
          f'{len(requests)} chart changes; {"verified" if apply else "preview only"}')
    return report


def main():
    import gspread
    parser = argparse.ArgumentParser()
    parser.add_argument('--league', choices=BOOKS, required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--expected-week', type=int)
    args = parser.parse_args()
    client = gspread.service_account_from_dict(json.loads(os.environ['GOOGLE_SERVICE_ACCOUNT_JSON']),
                                               http_client=gspread.BackOffHTTPClient)
    book = client.open_by_key(BOOKS[args.league][0])
    # Readout may lag formula recalculation briefly after a weekly write.
    for attempt in range(6):
        try:
            read_current(book, args.league, args.expected_week)
            break
        except ValueError:
            if attempt == 5:
                raise
            time.sleep(5)
    sync_ranges(book, args.league, args.expected_week, args.apply,
                bridge_book=client.open_by_key(PAYOUTS[args.league]) if args.apply else None)


if __name__ == '__main__':
    main()
