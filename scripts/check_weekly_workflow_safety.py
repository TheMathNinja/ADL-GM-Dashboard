from pathlib import Path


workflow = Path(".github/workflows/refresh_extension_calculator.yml").read_text(encoding="utf-8")
playoff_refresh = Path("scripts/refresh_playoff_picture.R").read_text(encoding="utf-8")
playoff_model = Path("scripts/get_adl_playoff_picture.R").read_text(encoding="utf-8")

required = {
    "dispatch requires explicit authorization": "id: cap_dispatch\n        if: steps.schedule.outputs.should_run == 'true' && inputs.ready_week != '' && inputs.score_revision == '' && inputs.capture_cap_snapshot == true && inputs.authorize_official_writes == true\n        continue-on-error: true",
    "manual rebuild defaults cap off": "capture_cap_snapshot:\n        description: \"Authorize the readiness-poll run to capture the official weekly cap snapshot\"\n        required: true\n        default: false",
    "manual rebuild defaults official writes off": "authorize_official_writes:\n        description: \"Authorize readiness-poll writes to Google Sheets and MFL\"\n        required: true\n        default: false",
    "google writes require authorization": "if: steps.schedule.outputs.should_run == 'true' && inputs.authorize_official_writes == true\n        continue-on-error: true\n        env:\n          LEAGUE: ADL",
    "mfl writes require authorization": "inputs.authorize_official_writes == true && steps.schedule.outputs.score_status == 'official'",
    "reuse completed snapshot": "Official Week ${READY_WEEK} cap snapshot is already complete; no new run will be dispatched.",
    "reuse is successful": "Reusing the completed official Week ${READY_WEEK} cap snapshot.",
    "bounded cap wait": "id: cap_snapshot\n        if: steps.cap_dispatch.outcome == 'success'\n        continue-on-error: true\n        timeout-minutes: 30",
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
    "Enter and verify official Bonus Games in MFL",
    "Build playoff forecast and Tuesday Game of the Week swing data",
    "Build selected Bonus Games dashboard",
    "Require synchronized quarterly forecasts before publication",
    "Confirm weekly publication and record processed scores",
    "Deploy calculator to shinyapps.io",
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
