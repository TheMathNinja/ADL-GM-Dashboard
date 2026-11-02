#!/usr/bin/env bash
set -eu
source scripts/resume_maintenance_child.sh
gh() { printf '%s' "$record_fixture"; }
record_fixture=$'123\tcompleted\tsuccess'
(resume_maintenance_child child.yml "Daily maintenance 1 - Commissioner alerts"; exit 99)
for record_fixture in '' $'123\tcompleted\tfailure'; do
  (resume_maintenance_child child.yml "Daily maintenance 1 - Commissioner alerts"; exit 0)
done
gh() { return 1; }
if (resume_maintenance_child child.yml "Daily maintenance 1 - Commissioner alerts"; exit 0); then exit 1; fi
