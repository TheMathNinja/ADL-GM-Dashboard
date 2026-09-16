"""Select the Eastern-time cron slot, independently of Actions start delays."""
import os
from datetime import datetime, date
from zoneinfo import ZoneInfo


def schedule_decision(now, season, event, cron="", status="manual", force=False):
    if event == "workflow_dispatch":
        return dict(should_run="true", score_status=status, force_refresh=str(force).upper())
    local = now.astimezone(ZoneInfo("America/New_York"))
    if not date(season, 9, 15) <= local.date() <= date(season + 1, 1, 7):
        return dict(should_run="false")
    utc_offset = int(local.utcoffset().total_seconds() / 3600)
    slots = {f"0 {1 - utc_offset} * * 2": "unofficial", f"0 {5 - utc_offset} * * 4": "official"}
    if cron not in slots:
        return dict(should_run="false")
    return dict(should_run="true", score_status=slots[cron], force_refresh="FALSE")


if __name__ == "__main__":
    result = schedule_decision(datetime.now(ZoneInfo("UTC")), int(os.environ["CURRENT_SEASON"]),
                               os.environ["EVENT_NAME"], os.getenv("SCHEDULE", ""),
                               os.getenv("SCORE_STATUS", "manual"), os.getenv("FORCE", "false") == "true")
    with open(os.environ["GITHUB_OUTPUT"], "a") as output:
        for key, value in result.items():
            print(f"{key}={value}", file=output)
    print(result)
