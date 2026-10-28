"""Archive the email's combined playoff swing, plus confirmed published GoTW."""
import csv,html,json,re,urllib.request
from pathlib import Path

def add_rows(data,rows,season):
    rows=[r for r in rows if int(r['season'])==season]
    if not rows:return
    weeks={int(r['target_week']) for r in rows}
    if len(rows)!=16 or len(weeks)!=1:raise ValueError('Incomplete weekly playoff stakes')
    values=[round(float(r['combined_swing']),6) for r in rows]
    data.setdefault('weeks',{})[str(next(iter(weeks)))]=[
        dict(teamIds=sorted([str(r['team_a_id']).zfill(4),str(r['team_b_id']).zfill(4)]),combinedSwing=float(r['combined_swing']),teamSwings={str(r['team_a_id']).zfill(4):float(r['team_a_swing']),str(r['team_b_id']).zfill(4):float(r['team_b_swing'])},rank=1+sum(v>round(float(r['combined_swing']),6) for v in values)) for r in rows]

def build(root,league,season):
    path=root/'docs/bonus-games/matchups/stakes.json'
    data=json.loads(path.read_text()) if path.exists() else dict(league=league,season=season,weeks={},gamesOfTheWeek=[])
    if data.get('season')!=season:data=dict(league=league,season=season,weeks={},gamesOfTheWeek=[])
    source=root/'data/playoff_swing.csv'
    if source.exists():
        with source.open(encoding='utf-8-sig') as f:add_rows(data,list(csv.DictReader(f)),season)
    # The actual editorial selection can differ from the top-ranked candidate.
    # Only mark the officially published matchup, never infer a winner by rank.
    lid={'ADL':'60206','FAFL':'22686'}[league]
    try:
        req=urllib.request.Request(f'https://www46.myfantasyleague.com/{season}/home/{lid}',headers={'User-Agent':'GM-Dashboard-Weekly-Matchups'})
        with urllib.request.urlopen(req,timeout=15) as response:page=response.read().decode('utf8',errors='replace')
        match=re.search(rf'{league} Game of the Week, Week (\d+):\s*([^<"]+?)\s+(?:at|vs\.?)\s+(.+?)(?:\s+[\u2014-]|&mdash;|["<])',page,re.I)
        if match:
            row=dict(week=int(match[1]),team_a=html.unescape(match[2].strip()),team_b=html.unescape(match[3].strip(' .')))
            data['gamesOfTheWeek']=[r for r in data.get('gamesOfTheWeek',[]) if r['week']!=row['week']]+[row]
    except (OSError,ValueError) as error:print('Retaining archived Game of the Week selections:',type(error).__name__,flush=True)
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(data,indent=2),encoding='utf8')
    return data
