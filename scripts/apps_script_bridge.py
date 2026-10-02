"""Call the native Google Apps Script bridge with bounded, idempotent retries."""
import json
import os
import time
import urllib.request


def request_bridge(action='refreshGithubPayoutLogos', attempts=6):
    url = os.environ.get('APPS_SCRIPT_BRIDGE_URL', '').strip()
    token = os.environ.get('APPS_SCRIPT_BRIDGE_TOKEN', '').strip()
    if not url or not token:
        raise RuntimeError('Apps Script bridge URL/token are not configured')
    payload = json.dumps({'action': action, 'token': token}).encode()
    last_error = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(
                url, data=payload, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(request, timeout=90) as response:
                acknowledgement = json.loads(response.read() or b'{}')
            if acknowledgement.get('status') != 'success':
                raise RuntimeError(acknowledgement.get('error', 'unknown bridge response'))
            return acknowledgement
        except Exception as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep((5, 10, 20, 30, 45)[min(attempt, 4)])
    raise RuntimeError(f'Apps Script bridge failed after {attempts} attempts: {last_error}')
