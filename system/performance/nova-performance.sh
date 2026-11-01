#!/bin/bash
# Live-system opt-in only. The ISO remaster installs the profiles separately.
set -euo pipefail
export PATH=/usr/sbin:/usr/bin:/sbin:/bin

fail() { printf 'nova-performance: %s\n' "$*" >&2; exit 1; }
[[ $# == 1 && ( $1 == apply || $1 == rollback ) ]] || fail 'Usage: nova-performance.sh apply|rollback'
[[ $(uname -s) == Linux ]] || fail 'Requires Linux; no host configuration was changed.'
[[ $EUID == 0 ]] || fail 'Requires root on the installed target OS.'
[[ -d /run/systemd/system && -e /proc/1/root ]] || fail 'Requires an already running systemd system, not a build chroot.'
[[ $(stat -Lc '%d:%i' /) == "$(stat -Lc '%d:%i' /proc/1/root/.)" ]] || fail 'Refusing to operate in a chroot.'
state=$(timeout --foreground 15 systemctl show --property=SystemState --value)
[[ $state == running || $state == degraded ]] || fail 'systemd is not in a running state.'

profile=/usr/share/nova/performance
backups=/var/lib/nova/backups
zram=/etc/default/zramswap
journal=/etc/systemd/journald.conf.d/nova-performance.conf

# Fixed destinations only; do not follow config or backup symlinks.
for path in /var/lib/nova "$backups" /etc/default /etc/systemd/journald.conf.d "$zram" "$journal"; do
    [[ ! -L $path ]] || fail "Refusing symlink: $path"
done
for target in "$zram" "$journal"; do
    [[ ! -e $target || -f $target ]] || fail "Not a regular config: $target"
done
install -d -m 0700 "$backups"
[[ $(stat -c '%u' "$backups") == 0 ]] || fail 'Backup directory must be owned by root.'
[[ ! -L $backups/.performance.lock ]] || fail 'Refusing symlink lock.'
exec 9>"$backups/.performance.lock"
flock -w 10 9 || fail 'Another performance operation is running.'

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

if [[ $1 == apply ]]; then
    for source in "$profile/zramswap" "$profile/nova-journald.conf"; do
        [[ -f $source && ! -L $source ]] || fail "Install the packaged profile first: $source"
        [[ $(stat -c '%u' "$source") == 0 ]] || fail "Profile must be owned by root: $source"
        mode=$(stat -c '%a' "$source")
        (( (8#$mode & 8#022) == 0 )) || fail "Profile must not be group/world writable: $source"
    done
    backup_once "$zram" zramswap
    backup_once "$journal" nova-performance.conf
    install -d -m 0755 /etc/default /etc/systemd/journald.conf.d
    install -m 0644 "$profile/zramswap" "$zram"
    install -m 0644 "$profile/nova-journald.conf" "$journal"
else
    for name in zramswap nova-performance.conf; do
        check_backup "$name"
        [[ -f $backups/$name || -f $backups/$name.absent ]] || fail "No original backup for $name; nothing restored."
    done
    install -d -m 0755 /etc/default /etc/systemd/journald.conf.d
    restore "$zram" zramswap
    restore "$journal" nova-performance.conf
fi

# Do not enable/start anything, disable unrelated services, or change sysctls.
for service in zramswap.service systemd-journald.service; do
    if timeout --foreground 15 systemctl is-active --quiet "$service"; then
        timeout --foreground 120 systemctl restart "$service"
    else
        status=$?
        [[ $status == 3 || $status == 4 ]] || fail "Cannot determine service state for $service (exit $status)."
    fi
done
printf 'Nova performance %s complete; original backups retained in %s.\n' "$1" "$backups"
