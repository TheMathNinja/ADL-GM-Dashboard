"""Request the serialized, incident-deduplicating reporter with bounded retries."""
import json
import os
import time
import urllib.error
import urllib.request

URL = ('https://api.github.com/repos/TheMathNinja/ADL-Commissioner-Dashboard/'
       'actions/workflows/email_workflow_failures.yml/dispatches')
DELAYS = (5, 15, 30, 60)
RETRYABLE = {408, 429, 500, 502, 503, 504}


def dispatch(token, opener=urllib.request.urlopen, sleep=time.sleep):
    if not token:
        raise RuntimeError('Report dispatch credential is missing')
    request = urllib.request.Request(URL, method='POST', headers={
        'Authorization': 'Bearer ' + token,
        'Accept': 'application/vnd.github+json',
        'Content-Type': 'application/json',
        'X-GitHub-Api-Version': '2022-11-28',
    }, data=json.dumps({'ref': 'main', 'inputs': {'dry_run': 'false'}}).encode())
    for attempt in range(len(DELAYS) + 1):
        try:
            with opener(request, timeout=20) as response:
                if response.status not in (200, 204):
                    raise RuntimeError('Unexpected dispatch response: HTTP ' + str(response.status))
            print('Commissioner reporter dispatch accepted; delivery is verified by the reporter.')
            return
        except urllib.error.HTTPError as error:
            reason = 'HTTP ' + str(error.code)
            if error.code not in RETRYABLE:
                raise RuntimeError('Reporter dispatch rejected: ' + reason) from None
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            reason = 'transport error; dispatch acceptance unconfirmed'
        if attempt == len(DELAYS):
            raise RuntimeError('Reporter dispatch still unconfirmed after 5 attempts: ' + reason)
        # Duplicate accepted requests are serialized and deduplicated by the reporter.
        print(f'Reporter dispatch {reason}; retrying in {DELAYS[attempt]} seconds.')
        sleep(DELAYS[attempt])


if __name__ == '__main__':
    dispatch(os.environ.get('GH_TOKEN', ''))
