"""Cheaply decide whether the private CHI team model needs rebuilding."""
from pathlib import Path
import ast
import hashlib
import json
import os
import urllib.error
import urllib.request
from team_model_contract import model_requirements, PATH_SCHEMA

ROOT = Path(__file__).resolve().parents[1]
SITE = "https://chi-team-tools.dreamytang7.chatgpt.site"


def snapshot_key(payload: dict) -> str | None:
    if "snapshotKey" in payload:
        return payload["snapshotKey"]
    for value in payload.values():
        if isinstance(value, dict):
            found = snapshot_key(value)
            if found:
                return found
    return None


def source_dependencies(root: Path) -> list[str]:
    pending = [root / 'scripts/sync_chi_team_model.py']
    found = set()
    while pending:
        path = pending.pop()
        if not path.is_file() or path in found:
            continue
        found.add(path)
        tree = ast.parse(path.read_text(encoding='utf-8-sig'))
        modules = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.append(node.module)
                modules.extend(node.module + '.' + alias.name for alias in node.names)
        for module in modules:
            base = root / 'scripts' / module.replace('.', '/')
            pending.extend([base.with_suffix('.py'), base / '__init__.py'])
    return sorted(path.relative_to(root).as_posix() for path in found)


def signature(root: Path) -> str:
    digest = hashlib.sha256()
    names = [
        "data/weekly_team_metrics.csv",
        "data/adl_scoring_model.json",
        "data/lineup_status_credits_2026.csv",
        "data/bonus_history.csv",
        "data/h2h_eb_training_credits.csv",
        "data/nfl_schedule_2026.csv",
        "requirements-weekly.txt",
    ]
    names += [
        str(path.relative_to(root)).replace("\\", "/")
        for path in sorted((root / "data/player_strength").rglob("*"))
        if path.is_file() and path.name != "refresh_receipt.json" and '__pycache__' not in path.parts
    ]
    names += source_dependencies(root)
    for name in sorted(set(names)):
        path = root / name
        if path.exists():
            digest.update(name.encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def ensure_site_model_contract(root: Path, headers: dict) -> dict:
    request = urllib.request.Request(SITE + "/api/team-projection-sync", headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        contract = json.load(response)
    model, schema, weights = model_requirements(root)
    if contract.get("contractVersion") != 1 or contract.get("season") != 2026:
        raise RuntimeError("Private team model upload contract is unavailable or incompatible")
    if 'supportedFullModelSchemas' in contract:
        if schema not in contract['supportedFullModelSchemas'] or PATH_SCHEMA not in contract.get('supportedPathSchemas', []):
            raise RuntimeError('Private Site does not support required model wire schema ' + schema)
        return contract
    if model["version"] not in contract.get("supportedADLModelVersions", []):
        raise RuntimeError("Private Site does not support ADL model " + model["version"])
    expected_weights = contract.get("adlModelWeights", {}).get(model["version"], contract.get("adlWeights"))
    if weights != expected_weights:
        raise RuntimeError("Private Site and ADL forecast model weights disagree")
    return contract


def main() -> None:
    token = os.environ["CHI_SITE_SERVICE_TOKEN"]
    headers = {"OAI-Sites-Authorization": "Bearer " + token, "User-Agent": "CHI-Team-Tools/2.0"}
    contract = ensure_site_model_contract(ROOT, headers)
    changed = snapshot_key(contract) != signature(ROOT)
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as handle:
            handle.write("changed=" + str(changed).lower() + "\n")
    print("Private team model rebuild " + ("required." if changed else "not required."))


if __name__ == "__main__":
    main()
