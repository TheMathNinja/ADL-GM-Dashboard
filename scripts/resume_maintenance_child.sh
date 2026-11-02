# Sourced by a single maintenance component. An already-dispatched child
# belongs to this parent run (including retries), not to another day's package.
resume_maintenance_child() {
  local workflow=$1 title=$2 repo=TheMathNinja/ADL-Commissioner-Dashboard record id status conclusion
  record=$(gh run list --repo "$repo" --workflow "$workflow" --event workflow_dispatch --limit 100 \
    --json databaseId,displayTitle,status,conclusion \
    --jq "[.[] | select(.displayTitle==\"$title\")] | first // empty | [.databaseId,.status,.conclusion] | @tsv") || exit 1
  [[ -n "$record" ]] || return 0
  IFS=$'\t' read -r id status conclusion <<< "$record"
  if [[ "$conclusion" == success ]]; then echo "Reusing verified child run $id"; exit 0; fi
  if [[ "$status" != completed ]]; then
    bash scripts/wait_for_workflow_run.sh "$repo" "$id" 480 5
    exit $?
  fi
}
