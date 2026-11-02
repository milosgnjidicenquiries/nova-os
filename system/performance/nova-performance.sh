#!/bin/bash
# Runs unattended from nova-performance-auto.service at boot; `rollback` writes the marker
# that unit's ConditionPathExists checks, so a deliberate rollback is not undone next boot.
set -euo pipefail
export PATH=/usr/sbin:/usr/bin:/sbin:/bin

fail() { printf 'nova-performance: %s\n' "$*" >&2; exit 1; }
[[ $# == 1 && ( $1 == apply || $1 == rollback || $1 == status ) ]] ||
    fail 'Usage: nova-performance.sh apply|rollback|status'
[[ $(uname -s) == Linux ]] || fail 'Requires Linux; no host configuration was changed.'
if [[ $1 != status ]]; then
    # status only reads /proc and the installed configs, so it needs neither root nor a
    # live systemd, and it cannot change anything.
    [[ $EUID == 0 ]] || fail 'Requires root on the installed target OS.'
    [[ -d /run/systemd/system && -e /proc/1/root ]] || fail 'Requires an already running systemd system, not a build chroot.'
    [[ $(stat -Lc '%d:%i' /) == "$(stat -Lc '%d:%i' /proc/1/root/.)" ]] || fail 'Refusing to operate in a chroot.'
    state=$(timeout --foreground 15 systemctl show --property=SystemState --value)
    [[ $state == running || $state == degraded ]] || fail 'systemd is not in a running state.'
fi

profile=/usr/share/nova/performance
backups=/var/lib/nova/backups
zram=/etc/default/zramswap
journal=/etc/systemd/journald.conf.d/nova-performance.conf
low_memory=/etc/sysctl.d/99-nova-low-memory.conf
low_memory_source=$profile/nova-low-memory.conf
live_values=$backups/low-memory-sysctl.live
auto_disabled=/var/lib/nova/performance-auto.disabled
# 1.5 GB in kB. Above this the shipped pool already leaves a browser more room than it
# can use, so the larger pool and the tunables stay off the machine.
low_memory_gate_kb=1572864
# Every key the gated drop-in writes, so recording and reporting cannot drift from it.
low_memory_keys=(vm.swappiness vm.page-cluster vm.vfs_cache_pressure vm.dirty_background_bytes vm.dirty_bytes)
total_kb=0

# Fixed destinations only; do not follow config or backup symlinks.
if [[ $1 != status ]]; then
    for path in /var/lib/nova "$backups" /etc/default /etc/systemd/journald.conf.d /etc/sysctl.d \
        "$zram" "$journal" "$low_memory"; do
        [[ ! -L $path ]] || fail "Refusing symlink: $path"
    done
    for target in "$zram" "$journal" "$low_memory"; do
        [[ ! -e $target || -f $target ]] || fail "Not a regular config: $target"
    done
    install -d -m 0700 "$backups"
    [[ $(stat -c '%u' "$backups") == 0 ]] || fail 'Backup directory must be owned by root.'
    [[ ! -L $backups/.performance.lock ]] || fail 'Refusing symlink lock.'
    exec 9>"$backups/.performance.lock"
    flock -w 10 9 || fail 'Another performance operation is running.'
fi

check_backup() {
    local name=$1
    [[ ! -L $backups/$name && ! -L $backups/$name.absent ]] || fail "Unsafe backup: $name"
    [[ ! ( -e $backups/$name && -e $backups/$name.absent ) ]] || fail "Conflicting backup markers: $name"
    [[ ! -e $backups/$name || -f $backups/$name ]] || fail "Backup is not a file: $name"
    [[ ! -e $backups/$name.absent || -f $backups/$name.absent ]] || fail "Invalid absence marker: $name"
}

backup_once() {
    local target=$1 name=$2
    check_backup "$name"
    if [[ -e $backups/$name || -e $backups/$name.absent ]]; then
        return
    fi
    if [[ -e $target ]]; then
        [[ -f $target ]] || fail "Not a regular config: $target"
        cp -a -- "$target" "$backups/$name"
    else
        # Record absence so rollback removes only the drop-in/config we installed.
        install -m 0600 /dev/null "$backups/$name.absent"
    fi
}

restore() {
    local target=$1 name=$2
    if [[ -f $backups/$name ]]; then
        cp -a -- "$backups/$name" "$target"
    else
        [[ ! -e $target || -f $target ]] || fail "Not a regular config: $target"
        rm -f -- "$target"
    fi
}

memory_total_kb() {
    local total
    total=$(awk '/^MemTotal:/{print $2; exit}' /proc/meminfo)
    [[ $total =~ ^[0-9]+$ ]] || fail 'Cannot read a numeric MemTotal from /proc/meminfo.'
    (( total > 0 )) || fail 'MemTotal is zero.'
    printf '%s\n' "$total"
}

sysctl_path() {
    printf '/proc/sys/%s/%s\n' "${1%.*}" "${1##*.}"
}

installed_percent() {
    local value
    [[ -f $zram && ! -L $zram ]] || return 1
    value=$(awk -F= '/^PERCENT=/{print $2; exit}' "$zram")
    [[ $value =~ ^[0-9]+$ ]] || return 1
    printf '%s\n' "$value"
}

record_sysctl() {
    local key=$1 file value
    file=$(sysctl_path "$key")
    [[ -f $file && ! -L $file ]] || fail "Missing kernel tunable: $key"
    value=$(<"$file")
    [[ $value =~ ^[0-9]+$ ]] || fail "Unexpected value for $key"
    printf '%s=%s\n' "$key" "$value"
}

restore_sysctl() {
    local line key
    [[ ! -L $1 ]] || fail 'Refusing symlink live-value record.'
    while IFS= read -r line; do
        [[ $line =~ ^[a-z0-9_.-]+=[0-9]+$ ]] || fail "Corrupt live-value record: $line"
        key=${line%%=*}
        [[ -f $(sysctl_path "$key") ]] || fail "Missing kernel tunable: $key"
        sysctl -w "$line" >/dev/null || fail "Cannot restore $key"
    done <"$1"
}

total_kb=$(memory_total_kb)
zram_profile=zramswap
low_memory_eligible=false
if (( total_kb <= low_memory_gate_kb )); then
    zram_profile=zramswap-low-memory
    low_memory_eligible=true
fi

if [[ $1 == status ]]; then
    # Read-only report: what this machine is, what the profiles would do, and what is live.
    printf 'MemTotal=%s MB\n' "$(( total_kb / 1024 ))"
    printf 'low_memory_gate=%s MB\n' "$(( low_memory_gate_kb / 1024 ))"
    printf 'low_memory_profile=%s\n' "$low_memory_eligible"
    printf 'packaged_zram_profile=%s/%s\n' "$profile" "$zram_profile"
    if installed=$(installed_percent); then
        printf 'installed_zram_percent=%s\n' "$installed"
    else
        printf 'installed_zram_percent=none\n'
    fi
    printf 'zram_devices=%s\n' "$(awk '/^\/dev\/zram[0-9]/{printf "%s ", $1}' /proc/swaps)"
    # status reports a missing tunable instead of stopping: an older kernel may not have it.
    show_sysctl() {
        local file=$1 path
        path=$(sysctl_path "$file")
        if [[ -f $path && ! -L $path ]]; then
            printf '%s=%s\n' "$file" "$(<"$path")"
        else
            printf '%s=missing\n' "$file"
        fi
    }

    for key in "${low_memory_keys[@]}"; do
        show_sysctl "$key"
    done
    printf 'low_memory_dropin=%s\n' "$([[ -f $low_memory ]] && echo present || echo absent)"
    printf 'recorded_original_values=%s\n' "$([[ -f $live_values ]] && echo present || echo absent)"
    printf 'auto_apply=%s\n' "$([[ -f $auto_disabled ]] && echo disabled || echo enabled)"
    exit 0
fi

if [[ $1 == apply ]]; then
    for source in "$profile/$zram_profile" "$profile/nova-journald.conf"; do
        [[ -f $source && ! -L $source ]] || fail "Install the packaged profile first: $source"
        [[ $(stat -c '%u' "$source") == 0 ]] || fail "Profile must be owned by root: $source"
        mode=$(stat -c '%a' "$source")
        (( (8#$mode & 8#022) == 0 )) || fail "Profile must not be group/world writable: $source"
    done
    backup_once "$zram" zramswap
    backup_once "$journal" nova-performance.conf
    install -d -m 0755 /etc/default /etc/systemd/journald.conf.d
    install -m 0644 "$profile/$zram_profile" "$zram"
    install -m 0644 "$profile/nova-journald.conf" "$journal"
    # Report the pool from the installed profile instead of restating a hardcoded number.
    installed=$(installed_percent) || fail "No numeric PERCENT in $zram"
    printf 'Nova sees %s MB of RAM; the zram pool is %s%% of it.\n' "$(( total_kb / 1024 ))" "$installed"
    # An explicit apply is consent for the boot unit, so drop the rollback opt-out marker.
    [[ ! -L $auto_disabled ]] || fail 'Refusing symlink auto-apply marker.'
    rm -f -- "$auto_disabled"
else
    for name in zramswap nova-performance.conf; do
        check_backup "$name"
        [[ -f $backups/$name || -f $backups/$name.absent ]] || fail "No original backup for $name; nothing restored."
    done
    install -d -m 0755 /etc/default /etc/systemd/journald.conf.d
    restore "$zram" zramswap
    restore "$journal" nova-performance.conf
    # The tunables were only ever written on a low-memory machine, so their absence is a
    # valid state and must not block the rest of the rollback.
    if [[ -f $backups/99-nova-low-memory.conf || -f $backups/99-nova-low-memory.conf.absent ]]; then
        check_backup 99-nova-low-memory.conf
        restore "$low_memory" 99-nova-low-memory.conf
    fi
    if [[ -f $live_values ]]; then
        restore_sysctl "$live_values"
        rm -f -- "$live_values"
        printf 'Nova restored the kernel values that were live before apply.\n'
    fi
    # Rollback is a deliberate choice, so it also opts the machine out of the boot unit.
    [[ ! -L $auto_disabled ]] || fail 'Refusing symlink auto-apply marker.'
    install -d -m 0755 /var/lib/nova
    install -m 0644 /dev/null "$auto_disabled"
    printf 'Nova will not re-apply the profile at boot; run nova-performance apply to opt back in.\n'
fi

# Restart only the two services this script configures, and only when they already run.
# Nothing is enabled, started, masked or disabled beyond that.
for service in zramswap.service systemd-journald.service; do
    if timeout --foreground 15 systemctl is-active --quiet "$service"; then
        timeout --foreground 120 systemctl restart "$service"
    else
        status=$?
        [[ $status == 3 || $status == 4 ]] || fail "Cannot determine service state for $service (exit $status)."
    fi
done

# The pool has to exist before raising swappiness: without a compressed device the same
# tunable would push idle pages onto a slow hard disk and make the desktop worse.
if [[ $1 == apply && $low_memory_eligible == true ]]; then
    if ! grep -q '^/dev/zram' /proc/swaps; then
        printf 'Nova found no active zram device; the low-memory kernel tunables were not applied.\n'
    else
        [[ ! -L $live_values ]] || fail 'Refusing symlink live-value record.'
        if [[ ! -e $live_values ]]; then
            values=$(for key in "${low_memory_keys[@]}"; do record_sysctl "$key"; done)
            (umask 077 && printf '%s\n' "$values" >"$live_values")
        fi
        [[ -f $low_memory_source && ! -L $low_memory_source ]] ||
            fail "Install the packaged profile first: $low_memory_source"
        [[ $(stat -c '%u' "$low_memory_source") == 0 ]] || fail "Profile must be owned by root: $low_memory_source"
        backup_once "$low_memory" 99-nova-low-memory.conf
        install -d -m 0755 /etc/sysctl.d
        install -m 0644 "$low_memory_source" "$low_memory"
        # Load exactly this file; sysctl --system would reapply unrelated administrator drop-ins.
        sysctl -p "$low_memory" >/dev/null || fail 'Cannot apply the low-memory tunables.'
        printf 'Nova applied the low-memory profile and recorded the previous values in %s.\n' "$live_values"
    fi
fi
printf 'Nova performance %s complete; original backups retained in %s.\n' "$1" "$backups"
