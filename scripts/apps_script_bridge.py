"""Call the native Google Apps Script bridge with bounded, idempotent retries."""
import json
import os
import time
import urllib.request


def request_bridge(action='refreshGithubPayoutLogos', attempts=3, timeout_seconds=30):
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
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                raw = response.read()
            try:
                acknowledgement = json.loads(raw)
            except (json.JSONDecodeError, UnicodeDecodeError):
                # Apps Script occasionally accepts the request but its web front
                # end returns an empty/HTML response. The sheet acknowledgement
                # is authoritative, so callers must continue to poll it.
                print('Apps Script dispatch response was not JSON; '
                      'continuing with sheet acknowledgement verification.', flush=True)
                return {'status': 'uncertain', 'queued': False}
            if acknowledgement.get('status') != 'success':
                raise RuntimeError(acknowledgement.get('error', 'unknown bridge response'))
            return acknowledgement
        except Exception as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep((5, 10, 20, 30, 45)[min(attempt, 4)])
    raise RuntimeError(f'Apps Script bridge failed after {attempts} attempts: {last_error}')

