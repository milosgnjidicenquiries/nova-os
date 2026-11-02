#!/usr/bin/env bash
set -euo pipefail
[[ $EUID != 0 ]] || exit 1
STATE=${XDG_STATE_HOME:-"$HOME/.local/state"}/nova
[[ ! -e "$STATE/welcome-seen" ]] || exit 0
mkdir -p -- "$STATE"

# A browser session costs several hundred MB, so on the 1 GB target it must not be the
# first-boot screen that pushes the session into swap. The page stays one menu click away.
low_memory() {
    local source=${NOVA_MEMINFO:-/proc/meminfo}
    [[ -r $source ]] || return 1
    (( $(awk '/^MemTotal:/{print $2}' "$source") < ${NOVA_LOW_MEMORY_KB:-1600000} ))
}

if low_memory; then
    nova-notify 'Nova OS je spreman' \
        'Dobrodošli. Zbog male količine RAM-a pregledač ne startuje sam — otvorite "Nova OS — dobrodošlica" iz menija.' || true
else
    xdg-open /usr/share/nova/welcome.html
fi
: >"$STATE/welcome-seen"
