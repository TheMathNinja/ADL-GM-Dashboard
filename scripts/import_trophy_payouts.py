"""Import cached public payout workbooks; never recalculate or change league adjustments.

Usage: python scripts/import_trophy_payouts.py /path/to/workbooks
Files: ADL-{year}-payouts.xlsx, exported from gm_career_sources.json.
"""
import hashlib
import json
import math
import re
from pathlib import Path
import sys
import openpyxl

ROOT = Path(__file__).resolve().parents[1]

def number(value):
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'Missing or invalid payout amount: {value!r}')
    return value

def add_earned_breakdowns(seasons):
    normalize = lambda code: {'NOR':'NOS','OAK':'LVR'}.get(code,code)
    labels = {'Conference Champ Runner-Up':'Conference Championship Runner-Up',
              'Third Place Winner':'3rd Place Finish', 'Third Place Runner-Up':'4th Place Finish',
              'Fifth Place Winner':'5th Place Finish', 'Fifth Place Runner-Up':'6th Place Finish',
              'Consolation Ladder Champ':'Consolation Ladder Champion'}
    for year, season in seasons.items():
        for team in season['teams']:
            items, weekly = [], {}
            if not season['prizes']:
                for amount,label in re.findall(r'\$(\d+(?:\.\d+)?)\s*([^$]+)',team.get('explanation') or ''):
                    items.append(dict(label=label.strip(' +'), amount=float(amount)))
            else:
                for prize in season['prizes']:
                    for conf in ('nfc','afc'):
                        winners = [normalize(x.strip()) for x in (prize[conf] or '').split('/')]
                        if normalize(team['team']) not in winners or prize['amount']==0:continue
                        amount=prize['amount']/len(winners)
                        label=prize['prize']
                        week=re.fullmatch(r'Week (\d+) High Score',label)
                        if week:
                            key=(conf,len(winners)>1)
                            entry=weekly.setdefault(key,dict(weeks=[],amount=0))
                            entry['weeks'].append(int(week[1]));entry['amount']+=amount
                        else:
                            label=labels.get(label,label)
                            if label.startswith('Playoff Participant'):label='Playoff Participant'
                            elif not label.startswith('Super Bowl'):label=conf.upper()+' '+label
                            items.append(dict(label=label,amount=amount))
                for (conf,shared),entry in weekly.items():
                    weeks=sorted(entry['weeks'])
                    label=f"{conf.upper()} Top Score {'Week' if len(weeks)==1 else 'Weeks'} "+', '.join(map(str,weeks))
                    if shared:label+=' (shared)'
                    items.append(dict(label=label,amount=entry['amount']))
            total=sum(item['amount'] for item in items)
            # 2017's two half-prizes were stored as corrections, but are earned prizes.
            expected=team['earnings']+(7.5 if year=='2017' and team['team'] in ('NYG','SEA') else 0)
            assert abs(total-expected)<.001,(year,team['team'],total,expected)
            team['earnedBreakdown']=items
            team['totalEarnings']=total
        season['totalPrizeEarnings']=sum(t['totalEarnings'] for t in season['teams'])

def main(directory, local=None):
    sources = json.loads((ROOT/'data/gm_career_sources.json').read_text())
    seasons = {}
    for source in sources:
        if source['kind'] != 'payouts':
            continue
        year = source['year']
        path = directory/f'ADL-{year}-payouts.xlsx'
        book = openpyxl.load_workbook(path, data_only=True, read_only=True)
        money = list(book['Money'].values)
        assert money[0][:4] == ('Prize', 'NFC', 'AFC', 'Payout')
        assert money[0][5:9] == ('Team', 'Raw', 'Correction', 'Final')
        teams, prizes = [], []
        for row in money[1:]:
            if row[0]:
                prizes.append(dict(prize=row[0], nfc=row[1], afc=row[2], amount=number(row[3])))
            if row[5] and row[5] not in ('Sum', 'Pay-In:'):
                earned, adjustment, final = number(row[6]), number(row[7] or 0), number(row[8])
                assert abs(earned+adjustment-final) < .001, (year,row[5])
                teams.append(dict(team=row[5], earnings=earned, adjustment=adjustment, payout=final))
        assert len(teams) == 32 and len({t['team'] for t in teams}) == 32
        published_total = next(number(r[8]) for r in money if r[5] == 'Sum')
        assert abs(sum(t['payout'] for t in teams)-published_total) < .001
        periods = [dict(period=r[0], winners=list(r[1:9]))
                   for r in list(book['Display'].values)[2:] if r[0]]
        missing = 0
        for period in periods:
            assert len(period['winners']) == 8
            for i, value in enumerate(period['winners']):
                if value is None or str(value).startswith('#'):
                    period['winners'][i] = None
                    missing += 1
        seasons[str(year)] = dict(source=source['url'], sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                                  teams=teams, prizes=prizes, periods=periods, missingAwardCells=missing,
                                  totalEarnings=sum(t['earnings'] for t in teams),
                                  totalAdjustments=sum(t['adjustment'] for t in teams), totalPayout=published_total)
        print(f'{year}: 32 teams; published payout ${published_total:,.2f}; balances reconcile')
    if local:
        history=json.loads((ROOT/'data/gm_career_seasons.json').read_text())
        for year in (2016,2017):
            path=local/f'{year} Leagues/{year} AFLADL Payouts.xlsx'
            rows=list(openpyxl.load_workbook(path,data_only=True,read_only=True)['ADL'].values)
            teams,prizes=[],[]
            if year==2016:
                listed={r[0]:r for r in rows if isinstance(r[1],(float,int)) and r[0]!='Total'}
                total=next(r[1] for r in rows if r[0]=='Total')
                assert sum(r[1] for r in listed.values())==total
                for h in history:
                    if h['season']!=year:continue
                    r=listed.pop(h['name'],None)
                    teams.append(dict(team=h['name'],earnings=r[1] if r else 0,adjustment=0,
                                      payout=r[1] if r else 0,explanation=r[2] if r else None))
                assert not listed
            else:
                for r in rows[2:]:
                    if r[0]:prizes.append(dict(prize=r[0],nfc=r[1],afc=r[2],amount=number(r[3])))
                    if r[5] and r[5]!='Sum':
                        earned,adjustment,final=number(r[6]),number(r[7] or 0),number(r[8])
                        assert abs(earned+adjustment-final)<.001
                        teams.append(dict(team=r[5],earnings=earned,adjustment=adjustment,payout=final,explanation=r[9]))
                total=next(r[8] for r in rows if r[5]=='Sum')
            assert len(teams)==32 and abs(sum(t['payout'] for t in teams)-total)<.001
            seasons[str(year)]=dict(source=None,sourceLabel=f'{path.name} · ADL',sha256=hashlib.sha256(path.read_bytes()).hexdigest(),teams=teams,prizes=prizes,periods=[],missingAwardCells=0,totalEarnings=sum(t['earnings'] for t in teams),totalAdjustments=sum(t['adjustment'] for t in teams),totalPayout=total)
            print(f'{year}: local ADL sheet, 32 teams; payout ${total:,.2f}; balances reconcile')
    add_earned_breakdowns(seasons)
    (ROOT/'data/trophy_room/payouts.json').write_text(json.dumps(seasons,indent=2)+'\n')

if __name__ == '__main__':
    main(Path(sys.argv[1]),Path(sys.argv[2]) if len(sys.argv)>2 else None)
