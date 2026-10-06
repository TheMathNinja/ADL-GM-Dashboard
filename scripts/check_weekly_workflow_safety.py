from pathlib import Path


workflow = Path(".github/workflows/refresh_extension_calculator.yml").read_text(encoding="utf-8")

required = {
    "dispatch requires explicit authorization": "id: cap_dispatch\n        if: steps.schedule.outputs.should_run == 'true' && inputs.ready_week != '' && inputs.score_revision == '' && inputs.capture_cap_snapshot == true && inputs.authorize_official_writes == true\n        continue-on-error: true",
    "manual rebuild defaults cap off": "capture_cap_snapshot:\n        description: \"Authorize the readiness-poll run to capture the official weekly cap snapshot\"\n        required: true\n        default: false",
    "manual rebuild defaults official writes off": "authorize_official_writes:\n        description: \"Authorize readiness-poll writes to Google Sheets and MFL\"\n        required: true\n        default: false",
    "google writes require authorization": "if: steps.schedule.outputs.should_run == 'true' && inputs.authorize_official_writes == true\n        continue-on-error: true\n        env:\n          LEAGUE: ADL",
    "mfl writes require authorization": "inputs.authorize_official_writes == true && steps.schedule.outputs.score_status == 'official'",
    "reuse completed snapshot": "Official Week ${READY_WEEK} cap snapshot is already complete; no new run will be dispatched.",
    "reuse is successful": "Reusing the completed official Week ${READY_WEEK} cap snapshot.",
    "bounded cap wait": "id: cap_snapshot\n        if: steps.cap_dispatch.outcome == 'success'\n        continue-on-error: true\n        timeout-minutes: 30",
    "dispatch participates in completion gate": "inputs.score_revision != '' || inputs.capture_cap_snapshot != true && 'success' || steps.cap_dispatch.outcome",
    "snapshot participates in completion gate": "inputs.score_revision != '' || inputs.capture_cap_snapshot != true && 'success' || steps.cap_snapshot.outcome",
    "final cap requirement": "Require official cap snapshot for preliminary weekly publication",
}

missing = [name for name, marker in required.items() if marker not in workflow]
if missing:
    raise SystemExit("Weekly workflow safety checks failed: " + ", ".join(missing))

ordered_steps = [
    "Validate the shared MFL snapshot",
    "Publish workbook Elo and synchronize Bonus Games inputs",
    "Enter and verify official Bonus Games in MFL",
    "Build playoff forecast and Game of the Week swing data",
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
