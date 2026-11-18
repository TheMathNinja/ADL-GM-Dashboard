"""Enrich frozen seasonlong player timelines from original MFL reports/status exports."""
import argparse,json
from pathlib import Path
from seasonlong_player_weeks import SeasonPlayerReport,StatusArchive,complete_player_weeks
ROOT=Path(__file__).resolve().parents[1]
def enrich(league,cache):
    path=ROOT/'data/trophy_room/seasonlong_performances_history.json';data=json.loads(path.read_bytes());reports={};archive=StatusArchive(cache)
    for key,d in data['details'].items():
        if d['kind']!='season-player':continue
        year=d['year'];pid=key.split(':')[-1];d['playerId']=pid;d['leagueId']=60206 if league=='ADL' else {2014:37677,2015:27312}.get(year,22686)
        if year not in reports:
            report=SeasonPlayerReport(16 if year<2021 else 17);report.feed((Path(cache)/f'{league}-{year}-player-report.html').read_text(encoding='utf8'));reports[year]=report
        d['weeks']=complete_player_weeks(d,reports[year].weekly_labels[pid],archive);d['average']=d['score']/d['games']
    for mode in data['modes'].values():
        for positions in mode['positions'].values():
            for rows in positions.values():
                for row in rows:row['average']=row['score']/row['games']
    data['meta']['playerStatusSources']=[archive.sources[k] for k in sorted(archive.sources)]
    data['meta']['playerAverageMethod']='Points divided by games played in the selected range; zero-point games count, byes and other absences do not. Cumulative average uses played games through that week.'
    data['meta']['playerTimelineMethod']='Every week in the selected range is shown. Bye comes from the MFL player report; absence reasons come from that week’s MFL injury export. An unrecorded reason is shown as Did not play, never inferred as Out or Suspended.'
    path.write_text(json.dumps(data,separators=(',',':'))+'\n',encoding='utf8')
    from collections import Counter
    print(league,'timeline enrichment',Counter(w['status'] for d in data['details'].values() if d['kind']=='season-player' for w in d['weeks']),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--league',choices=['ADL','FAFL'],required=True);p.add_argument('--cache',type=Path,required=True);a=p.parse_args();enrich(a.league,a.cache)
