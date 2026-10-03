from pathlib import Path


workflow = Path(".github/workflows/refresh_extension_calculator.yml").read_text(encoding="utf-8")

required = {
    "dispatch requires explicit authorization": "id: cap_dispatch\n        if: steps.schedule.outputs.should_run == 'true' && inputs.ready_week != '' && inputs.score_revision == '' && inputs.capture_cap_snapshot == true\n        continue-on-error: true",
    "manual rebuild defaults cap off": "capture_cap_snapshot:\n        description: \"Authorize the readiness-poll run to capture the official weekly cap snapshot\"\n        required: true\n        default: false",
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

print("Weekly workflow failure-isolation checks passed.")
