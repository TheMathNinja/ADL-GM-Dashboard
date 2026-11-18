"""Build completed-season division standings using MFL final standings and canonical all-play."""
import argparse,hashlib,json
from pathlib import Path
from import_trophy_results import arr,export,codes_for
ROOT=Path(__file__).resolve().parents[1]
def build(league,cache):
    history=json.loads((ROOT/'data/gm_career_seasons.json').read_bytes());seasons={}
    for year in sorted({r['season'] for r in history}):
        lid=60206 if league=='ADL' else {2014:37677,2015:27312}.get(year,22686)
        raw,source=export(year,'leagueStandings',dict(L=lid),cache)
        config_path=cache/f'{league}-{year}-league.json'
        if config_path.exists():
            body=config_path.read_bytes();config=json.loads(body)['league'];config_source=dict(url=f'https://api.myfantasyleague.com/{year}/export?TYPE=league&L={lid}&JSON=1',sha256=hashlib.sha256(body).hexdigest())
        else:config,config_source=export(year,'league',dict(L=lid),cache)
        conferences={c['id']:c['name'] for c in arr(config['conferences']['conference'])}
        franchises={f['id']:f for f in arr(config['franchises']['franchise'])};canonical={r['franchise_id']:r for r in history if r['season']==year}
        codes=codes_for(league,year);divisions=[];seen=set()
        for division in arr(config['divisions']['division']):
            rows=[]
            for team in arr(raw['franchise']):
                fid=team['id']
                if franchises[fid]['division']!=division['id']:continue
                row=canonical[fid];record={k:row['record_'+k] for k in ['wins','losses','ties']}
                assert [record[k] for k in ['wins','losses','ties']]==[int(team[k]) for k in ['h2hw','h2hl','h2ht']],(league,year,fid,'Canonical and published records differ')
                rows.append(dict(franchiseId=fid,franchise=row['name'],abbreviation=codes[int(fid)-1],gm=row['gm'],record=record,percentage=team['h2hpct'],streak=team.get('strk',''),averagePointsFor=float(team['avgpf']),averagePointsAgainst=float(team['avgpa']),allPlayRecord={k:row[k] for k in ['wins','losses','ties']},publishedMflAllPlay=team.get('all_play_wlt')))
                assert fid not in seen;seen.add(fid)
            assert len(rows)==4,(league,year,division['id'],len(rows))
            divisions.append(dict(id=division['id'],conference=conferences[division['conference']],name=division['name'],rows=rows))
        assert len(seen)==32 and len(divisions)==8
        seasons[str(year)]=dict(year=year,divisions=divisions,source=source,divisionSource=config_source)
        print(league,year,'final standings captured',flush=True)
    result=dict(meta=dict(league=league,firstSeason=min(int(y) for y in seasons),completedThrough=max(int(y) for y in seasons),method='Division layout, ordering, record, percentage, streak and averages follow MFL final standings. All-play uses the same audited once-per-week comparisons as the shared GM history, including playoffs; MFL duplicate-game comparison totals are retained for provenance but not substituted for canonical all-play.'),seasons=seasons)
    for folder in ['data/trophy_room','docs/trophy-room']:
        path=ROOT/folder/'season-standings.json';path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(result,separators=(',',':'))+'\n',encoding='utf8')
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--league',choices=['ADL','FAFL'],required=True);p.add_argument('--cache',type=Path,required=True);a=p.parse_args();build(a.league,a.cache)
