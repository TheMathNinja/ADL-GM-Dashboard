"""Use NFL kickoff times and scoreboard states to gate live collections."""
import datetime as dt
import json
import time
import urllib.request

SCOREBOARD = 'https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard'
FRESH_SECONDS = 45
_cached = {}
_recently_live = {}


def games(season):
    checked, events = _cached.get(season, (0, ()))
    now = time.monotonic()
    if now - checked < FRESH_SECONDS:
        return events
    try:
        with urllib.request.urlopen(f'{SCOREBOARD}?dates={season}&seasontype=2&limit=1000', timeout=8) as response:
            events = json.load(response)['events']
        if not events:
            raise ValueError('NFL schedule is empty')
    except (OSError, ValueError, KeyError):
        if now - checked < 600:
            return events
        raise
    _cached[season] = (now, events)
    return events


def coverage_due(events, now, lead_minutes=5):
    for game in events:
        kickoff = dt.datetime.fromisoformat(game['date'].replace('Z', '+00:00'))
        status = game['status']['type']
        state = status['state']
        game_id = game['id']
        if state == 'in' and not status.get('completed'):
            _recently_live[game_id] = now
            return True
        if state == 'post' and now - _recently_live.get(game_id, kickoff) <= dt.timedelta(minutes=2):
            return True
        if state == 'pre' and status['name'] not in {'STATUS_POSTPONED', 'STATUS_CANCELED', 'STATUS_CANCELLED'}:
            if -dt.timedelta(minutes=75) <= kickoff - now <= dt.timedelta(minutes=lead_minutes):
                return True
    return False


def active(now, season, lead_minutes=5):
    return coverage_due(games(season), now, lead_minutes)
