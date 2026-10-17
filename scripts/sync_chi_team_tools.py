"""Read MFL using existing Actions secrets; publish CHI trade snapshots and temporary refresh sessions to the owner-private Site.

No local snapshots, workflow artifacts, credentials or raw responses are logged.
"""
import datetime
import http.cookiejar
import json
import os
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

SITE='https://chi-team-tools.dreamytang7.chatgpt.site'
def many(x):
    return [] if not x else x if isinstance(x,list) else [x]
def number(x):
    if x is None or x=='':return None
    return float(x)
def normalize_trades(node):
    if not isinstance(node,dict):raise RuntimeError('Unexpected MFL pending-trade container')
    if node and not any(k in node for k in ['pendingTrade','trade']):raise RuntimeError('Unrecognized MFL pending-trade schema')
    trades=[]
    for t in many(node.get('pendingTrade',node.get('trade'))):
        offering=t.get('offeringteam',t.get('franchise'))
        receiving=t.get('offeredto',t.get('franchise2'))
        if not offering or not receiving:raise RuntimeError('MFL trade is missing franchise identifiers')
        if '0005' not in [offering,receiving]:continue
        trades.append(dict(id=t.get('trade_id',t.get('id','')),franchise=offering,franchise2=receiving,
                           franchise1_gave_up=t.get('will_give_up',t.get('franchise1_gave_up','')),
                           franchise2_gave_up=t.get('will_receive',t.get('franchise2_gave_up','')),
                           timestamp=t.get('timestamp',''),comments=t.get('comments','')))
    return trades

def run():
    username=os.environ['MFL_USERNAME'].strip();password=os.environ['MFL_PASSWORD']
    token=os.environ['CHI_SITE_SERVICE_TOKEN']
    if not username or not password or not token:raise RuntimeError('Required GitHub secret is missing')
    jar=http.cookiejar.CookieJar()
    opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    opener.addheaders=[('User-Agent',os.environ.get('MFL_USER_AGENT') or 'CHI-Team-Tools/1.0')]
    login=urllib.request.Request('https://api.myfantasyleague.com/2026/login',data=urllib.parse.urlencode({'USERNAME':username,'PASSWORD':password,'XML':'1'}).encode())
    with opener.open(login,timeout=30) as response:login_body=response.read()
    cookie=next((c.value for c in jar if c.name=='MFL_USER_ID'),None)
    sequence=next((c.value for c in jar if c.name=='MFL_PW_SEQ'),None)
    try:
        status=ET.fromstring(login_body)
        sequence=next((node.attrib.get('MFL_PW_SEQ') for node in status.iter() if node.attrib.get('MFL_PW_SEQ')),None) or sequence
        cookie=next((node.attrib.get('MFL_USER_ID') for node in status.iter() if node.attrib.get('MFL_USER_ID')),None) or cookie
    except ET.ParseError:pass
    if not cookie:
        # Only preset categories are logged; never emit raw response text or attributes.
        lower=login_body.decode('utf-8',errors='replace').lower()
        if any(word in lower for word in ['captcha','two-factor','two factor','verification code']):
            raise RuntimeError('MFL requires interactive login verification')
        if any(word in lower for word in ['invalid password','incorrect password','invalid username','invalid user','incorrect user','credentials']):
            raise RuntimeError('MFL rejected the saved GitHub login credentials')
        if '<error' in lower:raise RuntimeError('MFL login returned an XML error response')
        if '<html' in lower or '<!doctype' in lower:raise RuntimeError('MFL returned an HTML login page instead of an API session')
        raise RuntimeError('MFL login response did not include a usable session token')
    cookie_header='MFL_USER_ID='+urllib.parse.quote(urllib.parse.unquote(cookie),safe='')
    def get(kind,league):
        params={'TYPE':kind,'L':league,'JSON':'1'}
        if kind=='pendingTrades':params['FRANCHISE_ID']='0005'
        variants=[cookie_header,'MFL_USER_ID='+urllib.parse.unquote(cookie)]
        requests=[params]
        if kind=='pendingTrades':requests.append({k:v for k,v in params.items() if k!='FRANCHISE_ID'})
        for request_params in requests:
            url='https://api.myfantasyleague.com/2026/export?'+urllib.parse.urlencode(request_params)
            for header in dict.fromkeys(variants):
                if '\r' in header or '\n' in header:raise RuntimeError('Invalid MFL session header')
                request=urllib.request.Request(url,headers={'Cookie':header})
                with opener.open(request,timeout=30) as response:result=json.load(response)
                if not result.get('error'):break
            if not result.get('error'):break
        if result.get('error'):
            message=str(result['error']).lower()
            if 'logged in user in league' in message:raise RuntimeError('MFL did not accept this session as an owner in the requested league')
            if 'api.myfantasyleague.com' in message:raise RuntimeError('MFL rejected the requested API route')
            flags=[word for word in ['franchise','commissioner','cookie','permission','invalid','expired','user agent','access'] if word in message]
            raise RuntimeError('MFL rejected '+kind+' owner access; diagnostic categories: '+','.join(flags))
        if kind=='pendingTrades' and 'pendingTrades' not in result:raise RuntimeError('Unexpected MFL pending-trade response')
        return result
    for league,lid in [('ADL','60206'),('FAFL','22686')]:
        pending=get('pendingTrades',lid);raw=get('rosters',lid)
        node=pending['pendingTrades'] or {}
        trades=normalize_trades(node)
        roster=[]
        for f in many(raw['rosters'].get('franchise')):
            for p in many(f.get('player')):
                roster.append(dict(id=p['id'],franchise=f['id'],salary=number(p.get('salary')),years=number(p.get('contractYear')),contract=p.get('contractInfo',''),status=p.get('status','')))
        now=datetime.datetime.now(datetime.timezone.utc)
        # Session goes only to separate server-side storage; never to a browser or workflow log.
        session=dict(uid=cookie,seq=sequence or '',createdAt=now.isoformat(),expiresAt=(now+datetime.timedelta(hours=6)).isoformat())
        snapshot=dict(league=league,trades=trades,roster=roster,syncedAt=now.isoformat(),session=session)
        # A separate opener prevents MFL cookies from accompanying the Site upload.
        req=urllib.request.Request(SITE+'/api/trade-sync',data=json.dumps(snapshot,allow_nan=False).encode(),headers={'Content-Type':'application/json','OAI-Sites-Authorization':'Bearer '+token},method='POST')
        with urllib.request.urlopen(req,timeout=45) as response:result=json.load(response)
        if not result.get('ok'):raise RuntimeError('Private Site rejected snapshot')
        print(league+': private CHI trade snapshot updated.')

if __name__=='__main__':
    try:run()
    except Exception as exc:
        # Network errors can include URLs. Do not print exception contents.
        reason=str(exc) if type(exc) is RuntimeError else type(exc).__name__
        print('CHI trade synchronization failed: '+reason+'. No private payload was logged.',file=sys.stderr)
        sys.exit(1)
