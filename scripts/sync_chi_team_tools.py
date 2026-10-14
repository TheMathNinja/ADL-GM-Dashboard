"""Read MFL using existing Actions secrets; publish only CHI trade snapshots.

No local snapshots, workflow artifacts, credentials or raw responses are logged.
"""
import datetime
import http.cookiejar
import json
import os
import sys
import urllib.parse
import urllib.request

SITE='https://chi-team-tools.dreamytang7.chatgpt.site'
def many(x):
    return [] if not x else x if isinstance(x,list) else [x]
def number(x):
    if x is None or x=='':return None
    return float(x)
def run():
    username=os.environ['MFL_USERNAME'];password=os.environ['MFL_PASSWORD']
    token=os.environ['CHI_SITE_SERVICE_TOKEN']
    if not username or not password or not token:raise RuntimeError('Required GitHub secret is missing')
    jar=http.cookiejar.CookieJar()
    opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    opener.addheaders=[('User-Agent',os.environ.get('MFL_USER_AGENT') or 'CHI-Team-Tools/1.0')]
    login=urllib.request.Request('https://api.myfantasyleague.com/2026/login',data=urllib.parse.urlencode({'USERNAME':username,'PASSWORD':password,'XML':'1'}).encode())
    with opener.open(login,timeout=30) as response:response.read()
    if not any(c.name=='MFL_USER_ID' for c in jar):raise RuntimeError('MFL did not create an authenticated session')
    def get(kind,league):
        params={'TYPE':kind,'L':league,'JSON':'1'}
        if kind=='pendingTrades':params['FRANCHISE_ID']='0005'
        url='https://api.myfantasyleague.com/2026/export?'+urllib.parse.urlencode(params)
        with opener.open(url,timeout=30) as response:result=json.load(response)
        if result.get('error'):raise RuntimeError('MFL rejected '+kind+' access')
        if kind=='pendingTrades' and 'pendingTrades' not in result:raise RuntimeError('Unexpected MFL pending-trade response')
        return result
    for league,lid in [('ADL','60206'),('FAFL','22686')]:
        pending=get('pendingTrades',lid);raw=get('rosters',lid)
        node=pending['pendingTrades'] or {}
        trades=[t for t in many(node.get('trade')) if '0005' in [t.get('franchise'),t.get('franchise2')]]
        roster=[]
        for f in many(raw['rosters'].get('franchise')):
            for p in many(f.get('player')):
                roster.append(dict(id=p['id'],franchise=f['id'],salary=number(p.get('salary')),years=number(p.get('contractYear')),contract=p.get('contractInfo',''),status=p.get('status','')))
        snapshot=dict(league=league,trades=trades,roster=roster,syncedAt=datetime.datetime.now(datetime.timezone.utc).isoformat())
        # A separate opener prevents MFL cookies from accompanying the Site upload.
        req=urllib.request.Request(SITE+'/api/trade-sync',data=json.dumps(snapshot,allow_nan=False).encode(),headers={'Content-Type':'application/json','OAI-Sites-Authorization':'Bearer '+token},method='POST')
        with urllib.request.urlopen(req,timeout=45) as response:result=json.load(response)
        if not result.get('ok'):raise RuntimeError('Private Site rejected snapshot')
        print(league+': private CHI trade snapshot updated.')

if __name__=='__main__':
    try:run()
    except Exception as exc:
        # Network errors can include URLs. Do not print exception contents.
        print('CHI trade synchronization failed ('+type(exc).__name__+'). No private payload was logged.',file=sys.stderr)
        sys.exit(1)
