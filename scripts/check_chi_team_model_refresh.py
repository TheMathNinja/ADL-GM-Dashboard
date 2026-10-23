"""Cheaply decide whether the private CHI team model needs rebuilding."""
from pathlib import Path
import hashlib
import json
import os
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SITE = "https://chi-team-tools.dreamytang7.chatgpt.site"


def snapshot_key(payload: dict) -> str | None:
    return payload.get("snapshotKey") or (payload.get("metadata") or {}).get("snapshotKey")


def signature(root: Path) -> str:
    digest = hashlib.sha256()
    names = [
        "data/weekly_team_metrics.csv",
        "data/adl_scoring_model.json",
        "data/lineup_status_credits_2026.csv",
    ]
    names += [
        str(path.relative_to(root)).replace("\\", "/")
        for path in sorted((root / "data/player_strength").glob("*"))
        if path.suffix in [".json", ".csv"]
    ]
    names += [
        "scripts/sync_chi_team_model.py",
        "scripts/export_full_team_model.py",
        "scripts/player_team_strength.py",
        "scripts/player_blend_scoring.py",
        "scripts/bonus_predictor.py",
        "scripts/quarterly_bonus.py",
        "scripts/weekly_pairs.py",
    ]
    for name in names:
        path = root / name
        if path.exists():
            digest.update(name.encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def main() -> None:
    token = os.environ["CHI_SITE_SERVICE_TOKEN"]
    headers = {"OAI-Sites-Authorization": "Bearer " + token, "User-Agent": "CHI-Team-Tools/2.0"}
    changed = True
    try:
        request = urllib.request.Request(SITE + "/api/team-projections", headers=headers)
        with urllib.request.urlopen(request, timeout=30) as response:
            changed = snapshot_key(json.load(response)) != signature(ROOT)
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as handle:
            handle.write("changed=" + str(changed).lower() + "\n")
    print("Private team model rebuild " + ("required." if changed else "not required."))


if __name__ == "__main__":
    main()
