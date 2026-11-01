#!/usr/bin/env bash
set -euo pipefail
[[ $EUID != 0 ]] || exit 1
STATE=${XDG_STATE_HOME:-"$HOME/.local/state"}/nova
[[ ! -e "$STATE/welcome-seen" ]] || exit 0
mkdir -p -- "$STATE"
xdg-open /usr/share/nova/welcome.html
: >"$STATE/welcome-seen"
