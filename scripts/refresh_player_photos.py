"""Ownership-independent official NFL headshot catalog, keyed by MFL player ID.
Reads all 32 official NFL rosters, then checks official profiles for remaining
current players. Public source data only; never reads league rosters or EXT.
"""
import csv,io,argparse,concurrent.futures,datetime,html,json,pathlib,re,time,unicodedata,urllib.request
ROOT=pathlib.Path(__file__).resolve().parents[1]
TEAMS={'ARI':'arizona-cardinals','ATL':'atlanta-falcons','BAL':'baltimore-ravens','BUF':'buffalo-bills','CAR':'carolina-panthers','CHI':'chicago-bears','CIN':'cincinnati-bengals','CLE':'cleveland-browns','DAL':'dallas-cowboys','DEN':'denver-broncos','DET':'detroit-lions','GB':'green-bay-packers','HOU':'houston-texans','IND':'indianapolis-colts','JAX':'jacksonville-jaguars','KC':'kansas-city-chiefs','LAC':'los-angeles-chargers','LAR':'los-angeles-rams','LV':'las-vegas-raiders','MIA':'miami-dolphins','MIN':'minnesota-vikings','NE':'new-england-patriots','NO':'new-orleans-saints','NYG':'new-york-giants','NYJ':'new-york-jets','PHI':'philadelphia-eagles','PIT':'pittsburgh-steelers','SEA':'seattle-seahawks','SF':'san-francisco-49ers','TB':'tampa-bay-buccaneers','TEN':'tennessee-titans','WAS':'washington-commanders'}
ALIASES={'GBP':'GB','KCC':'KC','JAC':'JAX','LVR':'LV','NEP':'NE','NOS':'NO','SFO':'SF','TBB':'TB'}
def fullname(n):
 n=html.unescape(n)
 return ' '.join(reversed(n.split(', ',1))) if ', 'in n else n

def key(n):
 n=unicodedata.normalize('NFKD',fullname(n));n=re.sub(r'\b(jr|sr|ii|iii|iv)\b\.?','',n,flags=re.I)
 return re.sub('[^a-z0-9]','',n.lower())

def get(url):
 req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; CHI player photo directory)'})
 with urllib.request.urlopen(req,timeout=25)as r:return r.read().decode('utf-8')

def asset(url):
 url=html.unescape(url)
 m=re.search(r'https://static\.www\.nfl\.com/image/(upload|private)/([^"<> ]*?)/league/([A-Za-z0-9_-]+)',url)
 if not m or m[3]=='nvfr7ogywskqrfaiu38m':return None
 return ('https://static.www.nfl.com/image/upload/f_auto,q_auto/league/'+m[3]) if m[1]=='upload' else m[0]

def compatible(nfl,mfl):
 groups={'K':{'PK'},'P':{'PN'},'DB':{'CB','S'},'SAF':{'S'},'S':{'S','CB'},'FS':{'S','CB'},'SS':{'S','CB'},'DL':{'DT','DE'},'DE':{'DE','DT','LB'},'DT':{'DT','DE'},'LB':{'LB','DE'},'OLB':{'LB','DE'},'ILB':{'LB'},'FB':{'RB'},'RB':{'RB'},'QB':{'QB'},'WR':{'WR'},'TE':{'TE'},'CB':{'CB','S'}}
 return mfl in groups.get(nfl,{nfl})

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--year',type=int,default=datetime.datetime.now().year);parser.add_argument('--offline',action='store_true');args=parser.parse_args()
 folder=ROOT/'work/player-photos';folder.mkdir(parents=True,exist_ok=True)
 authority=folder/'mfl-players.json'
 if not args.offline:authority.write_text(get(f'https://api.myfantasyleague.com/{args.year}/export?TYPE=players&DETAILS=1&JSON=1'),encoding='utf-8')
 raw=json.loads(authority.read_text(encoding='utf-8'))['players']['player'];current={str(p['id']):p for p in raw if p.get('position')in {'QB','RB','WR','TE','PK','PN','DT','DE','LB','CB','S'}}
 def roster(item):
  team,slug=item;file=folder/(team+'-roster.html');url='https://www.nfl.com/teams/'+slug+'/roster/'
  if not args.offline:file.write_text(get(url),encoding='utf-8')
  s=file.read_text(encoding='utf-8');out=[]
  for row in re.findall(r'<tr\b[^>]*>(.*?)</tr>',s,re.S):
   a=re.search(r'<a[^>]+href="(/players/[^"?#]+/)"[^>]*>(.*?)</a>',row,re.S);cells=re.findall(r'<td[^>]*>(.*?)</td>',row,re.S);photo=asset(row)
   if not a or len(cells)<4 or not photo:continue
   out.append({'name':html.unescape(re.sub('<[^>]+>','',a[2])).strip(),'team':team,'position':re.sub('<[^>]+>','',cells[2]).strip(),'status':re.sub('<[^>]+>','',cells[3]).strip(),'photo':photo,'profile':'https://www.nfl.com'+a[1],'source':url})
  if len(out)<45:raise ValueError('Incomplete NFL roster '+team)
  return out
 with concurrent.futures.ThreadPoolExecutor(max_workers=4)as pool:catalog=[p for rows in pool.map(roster,TEAMS.items())for p in rows]
 print('Official NFL roster records',len(catalog),flush=True)
 byname={}
 for p in catalog:byname.setdefault(key(p['name']),[]).append(p)
 prior=ROOT/'data/player-photos.json';previous=json.loads(prior.read_text(encoding='utf-8')) if prior.exists()else {};photos=dict(previous.get('players',{}));missing=[]
 url_file=ROOT/'docs/assets/nfl-player-photo-urls.json'
 if url_file.exists():
  for pid,url in json.loads(url_file.read_text(encoding='utf-8')).items():
   if pid not in photos and asset(url):photos[pid]={'mflId':pid,'photo':asset(url),'source':'retained official NFL headshot','matchedBy':'existing-verified-player-id'}
 for pid,p in current.items():
  rows=[r for r in byname.get(key(p['name']),[])if compatible(r['position'],p['position'])]
  active=[r for r in rows if r['status']in {'ACT','RES','RSR','DEV','EXE','PUP','NFI'}];matching=[r for r in rows if r['team']==ALIASES.get(p.get('team'),p.get('team'))]
  choices=active or matching or rows
  unique={r['profile']for r in choices}
  if len(unique)==1:
   chosen=(matching or choices)[0];photos[pid]={**chosen,'mflId':pid,'mflName':p['name'],'matchedBy':'normalized-name-and-position'}
  elif pid not in photos:missing.append((pid,p))
 print('Current coverage after rosters',sum(pid in photos for pid in current),'/',len(current),'profile checks',len(missing),flush=True)
 def profile(item):
  pid,p=item;slug=re.sub(r'[^a-z0-9]+','-',fullname(p['name']).lower()).strip('-');url='https://www.nfl.com/players/'+slug+'/';file=folder/(slug+'.html')
  try:
   if not args.offline and not file.exists():file.write_text(get(url),encoding='utf-8')
   s=file.read_text(encoding='utf-8');objects=[json.loads(x)for x in re.findall(r'<script type="application/ld\+json">(.*?)</script>',s,re.S)];person=next(o['member']['member']for o in objects if o.get('@type')=='SportsTeam')
   if key(person['name'])!=key(p['name']):return None
   birthday=p.get('birthdate');dob=person.get('birthDate')
   if birthday and dob and datetime.datetime.fromtimestamp(int(birthday),datetime.timezone.utc).date().isoformat()!=dob:return None
   photo=asset(person.get('image',{}).get('contentUrl',''))
   if not photo:return None
   return pid,{'mflId':pid,'name':person['name'],'mflName':p['name'],'team':p.get('team'),'position':p['position'],'photo':photo,'profile':url,'source':url,'matchedBy':'official-profile-name-and-birthdate' if birthday and dob else 'official-profile-name'}
  except Exception:return None
 with concurrent.futures.ThreadPoolExecutor(max_workers=4)as pool:
  for result in pool.map(profile,missing):
   if result:photos[result[0]]=result[1]
 # Backfill additional official NFL CDN headshots through the nflverse identity
 # crosswalk. Images still come only from NFL; birthdates disambiguate names.
 identity_file=folder/'nflverse-players.csv'
 if not args.offline:identity_file.write_text(get('https://github.com/nflverse/nflverse-data/releases/download/players/players.csv'),encoding='utf-8')
 identities=list(csv.DictReader(io.StringIO(identity_file.read_text(encoding='utf-8-sig'))));named={};by_espn={}
 for person in identities:
  if not asset(person.get('headshot','')):continue
  if person.get('espn_id'):by_espn.setdefault(person['espn_id'],[]).append(person)
  for name in {person.get('display_name',''),person.get('football_name','')+' '+person.get('last_name',''),person.get('first_name','')+' '+person.get('last_name','')}:
   named.setdefault(key(name),{})[person['gsis_id']]=person
 directory=json.loads((ROOT/'data/player-directory.json').read_text(encoding='utf-8')) if (ROOT/'data/player-directory.json').exists() else {}
 for pid,p in {**directory,**current}.items():
  if pid in photos:continue
  direct=by_espn.get(str(p.get('espn_id','')),[])
  candidates=direct or [r for r in named.get(key(p['name']),{}).values()if compatible(r.get('position',''),p.get('position',p.get('pos','')))]
  birthday=p.get('birthdate')
  if birthday:candidates=[r for r in candidates if r.get('birth_date')==datetime.datetime.fromtimestamp(int(birthday),datetime.timezone.utc).date().isoformat()]
  if len(candidates)==1:
   r=candidates[0];photos[pid]={'mflId':pid,'name':r['display_name'],'mflName':p['name'],'team':r.get('latest_team'),'position':p.get('position',p.get('pos')),'photo':asset(r['headshot']),'source':'Official NFL GSIS headshot via nflverse player identity crosswalk','matchedBy':'shared-espn-identity-and-birthdate' if direct and birthday else 'shared-espn-identity' if direct else 'name-position-birthdate' if birthday else 'unique-name-and-position','gsisId':r['gsis_id'],'birthDate':r.get('birth_date')}
 # Preserve established official NFL images for older identities without requiring ownership.
 directory=json.loads((ROOT/'data/player-directory.json').read_text(encoding='utf-8')) if (ROOT/'data/player-directory.json').exists() else {}
 for pid,p in directory.items():
  if pid not in photos and p.get('photo') and asset(p['photo']):photos[pid]={'mflId':pid,'name':p['name'],'photo':asset(p['photo']),'source':'retained official NFL CDN image','matchedBy':'existing-verified-player-id'}
 missing=[{'id':pid,'name':p['name'],'position':p['position'],'team':p.get('team'),'reason':'No verified official NFL headshot found'}for pid,p in current.items()if pid not in photos]
 counts={pos:{'total':sum(p['position']==pos for p in current.values()),'covered':sum(pid in photos and p['position']==pos for pid,p in current.items())}for pos in sorted({p['position']for p in current.values()})}
 registry={'version':1,'season':args.year,'generatedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source':'Official NFL.com player profiles and all 32 NFL roster pages','ownershipIndependent':True,'players':photos,'coverage':{'currentTotal':len(current),'currentCovered':len(current)-len(missing),'byPosition':counts,'missing':missing}}
 (ROOT/'data/player-photos.json').write_text(json.dumps(registry,separators=(',',':')),encoding='utf-8');(ROOT/'data/player-photo-urls.json').write_text(json.dumps({pid:p['photo']for pid,p in photos.items()},separators=(',',':')),encoding='utf-8')
 out=ROOT/'docs/assets';out.mkdir(parents=True,exist_ok=True);(out/'nfl-player-photo-urls.json').write_text(json.dumps({pid:p['photo']for pid,p in photos.items()},separators=(',',':')),encoding='utf-8');(out/'nfl-player-photo-registry.json').write_text(json.dumps(registry,separators=(',',':')),encoding='utf-8');(folder/'nfl-catalog.json').write_text(json.dumps(catalog,separators=(',',':')),encoding='utf-8')
 print(json.dumps({k:v for k,v in registry['coverage'].items()if k!='missing'}),flush=True)
if __name__=='__main__':main()

