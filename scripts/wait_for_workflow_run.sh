#!/usr/bin/env bash

set -euo pipefail

repo="${1:?repository is required}"
run_id="${2:?run ID is required}"
max_polls="${3:-240}"
poll_seconds="${4:-5}"

for ((poll = 1; poll <= max_polls; poll++)); do
  response=""
  if response=$(gh api "repos/${repo}/actions/runs/${run_id}" \
    --jq '[.status, (.conclusion // ""), .html_url] | @tsv' 2>&1); then
    IFS=$'\t' read -r status conclusion run_url <<< "${response}"
    echo "Child workflow ${run_id}: ${status}/${conclusion:-pending}"

    if [ "${status}" = "completed" ]; then
      echo "${run_url}"
      if [ "${conclusion}" = "success" ]; then
        exit 0
      fi
      echo "Child workflow ${run_id} completed with conclusion: ${conclusion}."
      exit 1
    fi
  else
    echo "GitHub status query ${poll} failed; retrying: ${response}"
  fi

  sleep "${poll_seconds}"
done

# A child can complete between the final sleep and the timeout decision. Query
# once more so a success at that boundary is not reported as a parent failure.
if response=$(gh api "repos/${repo}/actions/runs/${run_id}" \
  --jq '[.status, (.conclusion // ""), .html_url] | @tsv' 2>&1); then
  IFS=$'\t' read -r status conclusion run_url <<< "${response}"
  echo "Child workflow ${run_id} final check: ${status}/${conclusion:-pending}"
  if [ "${status}" = "completed" ]; then
    echo "${run_url}"
    if [ "${conclusion}" = "success" ]; then
      exit 0
    fi
    echo "Child workflow ${run_id} completed with conclusion: ${conclusion}."
    exit 1
  fi
fi

echo "Timed out waiting for child workflow ${run_id} after $((max_polls * poll_seconds)) seconds."
echo "Child workflow remains active: https://github.com/${repo}/actions/runs/${run_id}"
exit 1
