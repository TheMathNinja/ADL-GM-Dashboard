"""Archive the email's combined playoff swing, plus confirmed published GoTW."""
import csv,json,re,urllib.request,math
from html.parser import HTMLParser
from pathlib import Path

def conditional_odds(row):
    odds={}
    for side in ['a','b']:
        try:
            win=float(row[f'team_{side}_playoff_if_win']);loss=float(row[f'team_{side}_playoff_if_loss'])
        except (KeyError,TypeError,ValueError):continue
        if math.isfinite(win) and math.isfinite(loss) and 0<=win<=100 and 0<=loss<=100:
            odds[str(row[f'team_{side}_id']).zfill(4)]=dict(ifWin=win,ifLoss=loss)
    return odds

def add_rows(data,rows,season):
    rows=[r for r in rows if int(r['season'])==season]
    if not rows:return
    weeks={int(r['target_week']) for r in rows}
    if len(rows)!=16 or len(weeks)!=1:raise ValueError('Incomplete weekly playoff stakes')
    values=[round(float(r['combined_swing']),6) for r in rows]
    data.setdefault('weeks',{})[str(next(iter(weeks)))]=[
        dict(teamIds=sorted([str(r['team_a_id']).zfill(4),str(r['team_b_id']).zfill(4)]),combinedSwing=float(r['combined_swing']),teamPlayoffOdds=conditional_odds(r),teamSwings={str(r['team_a_id']).zfill(4):float(r['team_a_swing']),str(r['team_b_id']).zfill(4):float(r['team_b_swing'])},rank=1+sum(v>round(float(r['combined_swing']),6) for v in values)) for r in rows]

class GameOfTheWeekBanner(HTMLParser):
    def __init__(self, league):
        super().__init__()
        self.selection = None
        self.pattern = re.compile(
            rf"{league} Game of the Week,\s*Week (\d+):\s*(.+?)\s+"
            r"(?:at|vs\.?)\s+(.+?)\s+(?:—|–|-)\s+(.+)",
            re.I,
        )

    def handle_starttag(self, tag, attrs):
        if tag != 'img' or self.selection:
            return
        alt = dict(attrs).get('alt') or ''
        match = self.pattern.fullmatch(' '.join(alt.split()))
        if match:
            self.selection = dict(
                week=int(match[1]), team_a=match[2], team_b=match[3], blurb=match[4],
            )


def build(root,league,season):
    path=root/'docs/bonus-games/matchups/stakes.json'
    data=json.loads(path.read_text(encoding='utf8')) if path.exists() else dict(league=league,season=season,weeks={},gamesOfTheWeek=[])
    if data.get('season')!=season:data=dict(league=league,season=season,weeks={},gamesOfTheWeek=[])
    source=root/'data/playoff_swing.csv'
    if source.exists():
        with source.open(encoding='utf-8-sig') as f:add_rows(data,list(csv.DictReader(f)),season)
    # The actual editorial selection can differ from the top-ranked candidate.
    # Only mark the officially published matchup, never infer a winner by rank.
    host,lid={'ADL':('www46','60206'),'FAFL':('www43','22686')}[league]
    try:
        req=urllib.request.Request(f'https://{host}.myfantasyleague.com/{season}/home/{lid}',headers={'User-Agent':'GM-Dashboard-Weekly-Matchups'})
        with urllib.request.urlopen(req,timeout=15) as response:page=response.read().decode('utf8',errors='replace')
        banner=GameOfTheWeekBanner(league)
        banner.feed(page)
        if banner.selection:
            row=banner.selection
            data.setdefault('gamesOfTheWeek',[])
            data['gamesOfTheWeek']=[r for r in data.get('gamesOfTheWeek',[]) if r['week']!=row['week']]+[row]
    except (OSError,ValueError) as error:print('Retaining archived Game of the Week selections:',type(error).__name__,flush=True)
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(data,indent=2),encoding='utf8')
    return data
