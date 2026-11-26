#!/usr/bin/env bash
set -euo pipefail

if [[ -f /etc/apt/apt-mirrors.txt ]]; then
  sudo sed -i 's|http://azure.archive.ubuntu.com/ubuntu|https://archive.ubuntu.com/ubuntu|g' /etc/apt/apt-mirrors.txt
fi

apt=(sudo apt-get -o Acquire::Retries=1 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30)
packages=(
  r-base r-base-dev libcurl4-openssl-dev libfontconfig1-dev libfreetype6-dev
  libfribidi-dev libharfbuzz-dev libjpeg-dev libpng-dev libssl-dev
  libtiff5-dev libxml2-dev libuv1-dev pkg-config
)

for attempt in 1 2; do
  # A mirror can remove a version after update. Refresh the indexes before the
  # next download instead of asking apt to retry the same retired package URL.
  if "${apt[@]}" -o APT::Update::Error-Mode=any update &&
     "${apt[@]}" install -y --download-only "${packages[@]}"; then
    "${apt[@]}" install -y --no-download "${packages[@]}"
    exit 0
  fi
  if [[ "$attempt" == 1 ]]; then
    echo 'Ubuntu dependency download failed; refreshing package lists and retrying once.' >&2
    sleep 5
  fi
done
echo 'Ubuntu dependency downloads failed after two package-list refresh attempts.' >&2
exit 1
