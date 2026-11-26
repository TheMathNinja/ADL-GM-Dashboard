#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
test_dir=$(mktemp -d)
trap 'rm -f -- "$test_dir/sudo" "$test_dir/sleep" "$test_dir/commands"; rmdir -- "$test_dir"' EXIT
export TEST_APT_LOG="$test_dir/commands"
export PATH="$test_dir:$PATH"

cat > "$test_dir/sudo" <<'STUB'
#!/usr/bin/env bash
case " $* " in
  " sed "*) exit 0 ;;
  *' update '*)
    [[ " $* " == *' -o APT::Update::Error-Mode=any '* ]] || exit 41
    operation=update ;;
  *' --download-only '*) operation=download ;;
  *' --no-download '*) operation=install ;;
  *) exit 42 ;;
esac
printf '%s\n' "$operation" >> "$TEST_APT_LOG"
case "$TEST_APT_CASE:$operation" in
  stale:download) [[ $(grep -c '^update$' "$TEST_APT_LOG") == 2 ]] || exit 100 ;;
  update:download|update:update) [[ $(grep -c '^update$' "$TEST_APT_LOG") == 2 ]] || exit 100 ;;
  offline:download|broken:install) exit 100 ;;
esac
STUB
printf '#!/usr/bin/env bash\nexit 0\n' > "$test_dir/sleep"
chmod +x "$test_dir/sudo" "$test_dir/sleep"

check() {
  local status=0
  : > "$TEST_APT_LOG"
  TEST_APT_CASE=$1 bash "$root/scripts/install_dashboard_r_system_deps.sh" || status=$?
  [[ "$status" == "$2" ]]
  [[ $(paste -sd, "$TEST_APT_LOG") == "$3" ]]
}

check normal 0 update,download,install
check stale 0 update,download,update,download,install
check update 0 update,update,download,install
check offline 1 update,download,update,download
check broken 100 update,download,install
echo 'Dashboard R system dependency setup tests passed.'
