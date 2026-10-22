"""Fetch signed-index APT packages concurrently with curl, then let APT verify/install."""
import concurrent.futures,os,shlex,subprocess,sys
from pathlib import Path
from urllib.parse import urlsplit
PACKAGES=['r-base','r-base-dev','libcurl4-openssl-dev','libfontconfig1-dev','libfreetype6-dev','libfribidi-dev','libharfbuzz-dev','libjpeg-dev','libpng-dev','libssl-dev','libtiff5-dev','libxml2-dev','libuv1-dev','libnode-dev','pkg-config']

def parse_plan(text):
    entries=[]
    for line in text.splitlines():
        if not line.startswith("'"):continue
        fields=shlex.split(line)
        if len(fields)<3:raise ValueError('Incomplete APT download plan')
        url,name,size=fields[:3]
        # GitHub's Ubuntu image uses a signed-index mirror-list URI. Resolve
        # only its known Ubuntu pool to the measured HTTPS mirror.
        for prefix in ('mirror+file:/etc/apt/apt-mirrors.txt/','mirror+file:/etc/apt/apt-mirrors-security.txt/'):
            if url.startswith(prefix) and url[len(prefix):].startswith('pool/'):
                url='https://archive.ubuntu.com/ubuntu/'+url[len(prefix):]
                break
        if not url.startswith(('http://','https://')) or Path(name).name!=name or not name.endswith('.deb') or int(size)<0:raise ValueError('Unsafe APT download target: '+repr(fields[:3]))
        entries.append((url,name,int(size)))
    return entries

def download_urls(url):
    parsed=urlsplit(url)
    if parsed.hostname in ('azure.archive.ubuntu.com','archive.ubuntu.com','security.ubuntu.com') and parsed.path.startswith('/ubuntu/'):
        suffix=parsed.path[len('/ubuntu/'):]
        return ['https://mirror.math.princeton.edu/pub/ubuntu/'+suffix,'https://archive.ubuntu.com/ubuntu/'+suffix]
    return [url]

def main():
    if sys.platform!='linux':raise RuntimeError('This installer is only for the Ubuntu CI runner')
    subprocess.run(['sudo','apt-get','-o','Acquire::Retries=3','-o','DPkg::Lock::Timeout=120','update'],check=True)
    args=['apt-get','-o','DPkg::Lock::Timeout=120','--no-install-recommends']
    plan=subprocess.run(['sudo',*args,'--print-uris','--download-only','--yes','install',*PACKAGES],check=True,capture_output=True,text=True).stdout
    entries=parse_plan(plan);cache=Path('/var/cache/apt/archives');subprocess.run(['sudo','mkdir','-p',str(cache)],check=True)
    staging=Path(os.environ.get('RUNNER_TEMP','/tmp'))/'adl-apt-downloads';staging.mkdir(exist_ok=True)
    def fetch(entry):
        url,name,size=entry;target=staging/name
        for address in download_urls(url):
            result=subprocess.run(['curl','--fail','--location','--silent','--show-error','--retry','1','--connect-timeout','15','--max-time','90','--output',str(target),address])
            if result.returncode==0:break
        else:raise RuntimeError('All mirrors failed for '+name)
        if target.stat().st_size!=size:raise ValueError('Incomplete package download: '+name)
        subprocess.run(['sudo','install','-m','644',str(target),str(cache/name)],check=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:list(ex.map(fetch,entries))
    print('Downloaded',len(entries),'packages through curl; APT will verify their signed-index hashes.',flush=True)
    subprocess.run(['sudo',*args,'--no-download','--yes','install',*PACKAGES],check=True)
if __name__=='__main__':main()
