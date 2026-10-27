from pathlib import Path


workflow = Path(".github/workflows/refresh_extension_calculator.yml").read_text(encoding="utf-8")
playoff_refresh = Path("scripts/refresh_playoff_picture.R").read_text(encoding="utf-8")
playoff_model = Path("scripts/get_adl_playoff_picture.R").read_text(encoding="utf-8")

required = {
    "dispatch requires explicit authorization": "id: cap_dispatch\n        if: steps.schedule.outputs.should_run == 'true' && inputs.ready_week != '' && inputs.score_revision == '' && inputs.capture_cap_snapshot == true && inputs.authorize_official_writes == true\n        continue-on-error: true",
    "manual rebuild defaults cap off": "capture_cap_snapshot:\n        description: \"Authorize the readiness-poll run to capture the official weekly cap snapshot\"\n        required: true\n        default: false",
    "manual rebuild defaults official writes off": "authorize_official_writes:\n        description: \"Authorize readiness-poll writes to Google Sheets and MFL\"\n        required: true\n        default: false",
    "google writes require authorization": "id: elo\n        if: steps.schedule.outputs.should_run == 'true' && inputs.authorize_official_writes == true\n        continue-on-error: true\n        timeout-minutes: 8",
    "mfl dispatch requires authorization": "inputs.authorize_official_writes == true && steps.schedule.outputs.score_status == 'official'",
    "reuse completed snapshot": "Official Week ${READY_WEEK} cap snapshot is already complete; no new run will be dispatched.",
    "reuse is successful": "Reusing the completed official Week ${READY_WEEK} cap snapshot.",
    "bounded cap wait": "id: cap_snapshot\n        if: steps.cap_dispatch.outcome == 'success'\n        continue-on-error: true\n        timeout-minutes: 20",
    "dispatch participates in completion gate": "(inputs.score_revision != '' || inputs.capture_cap_snapshot != true) && 'success' || steps.cap_dispatch.outcome",
    "snapshot participates in completion gate": "(inputs.score_revision != '' || inputs.capture_cap_snapshot != true) && 'success' || steps.cap_snapshot.outcome",
    "final cap requirement": "Require official cap snapshot for preliminary weekly publication",
}

missing = [name for name, marker in required.items() if marker not in workflow]
if missing:
    raise SystemExit("Weekly workflow safety checks failed: " + ", ".join(missing))

correction_markers = {
    "corrections disable matchup swing": 'Sys.getenv("REFRESH_PROCESS", "preliminary") != "corrections"',
    "corrections preserve Tuesday swing output": 'preserving Tuesday Game of the Week swing data',
    "playoff model honors swing control": 'getOption("adl.build_playoff_swing", TRUE)',
}
missing = [
    name for name, marker in correction_markers.items()
    if marker not in (playoff_model if name == "playoff model honors swing control" else playoff_refresh)
]
if missing:
    raise SystemExit("Correction workflow isolation checks failed: " + ", ".join(missing))

ordered_steps = [
    "Validate the shared MFL snapshot",
    "Publish official workbook Elo",
    "Synchronize and collect official Bonus Games verification",
    "Synchronize and verify Payouts",
    "Build playoff forecast and Tuesday Game of the Week swing data",
    "Build selected Bonus Games dashboard",
    "Build playoff bracket from official workbook Elo",
    "Synchronize and verify postseason Payouts",
    "Require synchronized quarterly forecasts before publication",
    "Commit generated data",
    "Publish updated reports on GitHub Pages",
    "Dispatch independent calculator deployment",
    "Confirm official weekly cap snapshot and Cap Rollover update",
    "Confirm weekly publication and record processed scores",
]
positions = [workflow.find(f"- name: {name}") for name in ordered_steps]
if any(position < 0 for position in positions) or positions != sorted(positions):
    raise SystemExit(
        "Weekly workflow fast-publication order is invalid: "
        + " -> ".join(ordered_steps)
    )

print("Weekly workflow failure-isolation checks passed.")

# Retired Bonus Games sheets must not become weekly publication dependencies.
google_sync = Path("scripts/sync_google_weekly_system.R").read_text(encoding="utf-8")
legacy_bonus_ids = ("1S3NrGPEGdA3zR3-VNLLS1dAbMYFzH5rt1Z4ROoCzekU", "1X5DJD6K2mAL93DpPtHshVnOo4f_mJRc1CE2phcTFnTE")
if any(sheet_id in google_sync for sheet_id in legacy_bonus_ids):
    raise SystemExit("Weekly Google synchronization must not access retired Bonus Games sheets.")
if "python scripts/bonus_module.py --league ADL --root . --out docs/bonus-games" not in workflow or "python scripts/verify_quarterly_sync.py --league ADL --root ." not in workflow:
    raise SystemExit("Weekly updates must build Bonus Games and verify shared quarterly forecasts.")
print("Bonus Games module publication and legacy-sheet retirement checks passed.")

bonus_module = Path("scripts/bonus_module.py").read_text(encoding="utf-8")
bridge_client = Path("scripts/apps_script_bridge.py").read_text(encoding="utf-8")
bridge_worker = Path("scripts/PayoutsGithubBridge.gs").read_text(encoding="utf-8")
bonus_workflow = Path(".github/workflows/verify_bonus_mfl.yml").read_text(encoding="utf-8")
maintenance = Path(".github/workflows/rebuild_playoff_model.yml").read_text(encoding="utf-8")
if "w<last and previous" not in bonus_module or "snapshot',w,'preserved" not in bonus_module:
    raise SystemExit("Weekly Bonus Games must preserve historical snapshots instead of re-simulating them.")
if "'Bridge queue is busy' in error" not in bridge_client:
    raise SystemExit("Apps Script lock contention must continue to authoritative Sheet acknowledgement.")
bonus_position = bridge_worker.find("refreshGithubBonusMfl(league, ref);")
logo_position = bridge_worker.find("const raw = ref.getRange('Z10').getValue();")
if bonus_position < 0 or logo_position < 0 or bonus_position > logo_position:
    raise SystemExit("Apps Script must acknowledge Bonus Games before processing payout logos.")
if "group: gm-dashboard-bonus-mfl" not in bonus_workflow or "mode=official" not in workflow:
    raise SystemExit("Bonus Games must run independently from the weekly publication queue.")
if maintenance.count("if: github.event_name == 'workflow_dispatch'") < 6 or "gm-dashboard-validation-" not in maintenance:
    raise SystemExit("Push validation must not rebuild/publish or block the weekly data-write queue.")
print("Historical snapshot preservation and serialized Apps Script checks passed.")

