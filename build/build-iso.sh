#!/usr/bin/env bash
set -Eeuo pipefail
export LC_ALL=C
ORIGINAL_ARGS=("$@")
PROJECT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
usage() {
    printf '%s\n' 'Usage: sudo bash build/build-iso.sh --iso FILE --checksums FILE --signature FILE --key FILE --output-dir DIR [--package-lock FILE] [--keep-work]'
}
ISO= CHECKSUMS= SIGNATURE= KEY= OUTPUT= LOCK= KEEP=0
while (($#)); do
    case "$1" in
        --iso|--checksums|--signature|--key|--output-dir|--package-lock)
            (($# >= 2)) || { usage; exit 2; }
            case "$1" in
                --iso) ISO=$2;; --checksums) CHECKSUMS=$2;; --signature) SIGNATURE=$2;;
                --key) KEY=$2;; --output-dir) OUTPUT=$2;; --package-lock) LOCK=$2;;
            esac
            shift 2;;
        --keep-work) KEEP=1; shift;;
        --help) usage; exit 0;;
        *) usage; exit 2;;
    esac
done
[[ -n "$ISO" && -n "$CHECKSUMS" && -n "$SIGNATURE" && -n "$KEY" && -n "$OUTPUT" ]] || { usage; exit 2; }
[[ $(uname -s) == Linux && $(uname -m) == x86_64 && $EUID == 0 ]] || { printf '%s\n' 'Requires root in a dedicated x86-64 Linux build VM. Windows Git Bash is not a Linux build host.' >&2; exit 1; }
for tool in python3 gpg xorriso unsquashfs mksquashfs dpkg-deb mount mountpoint umount chroot rsync flock sha256sum systemctl tee realpath install du dpkg unshare; do
    command -v "$tool" >/dev/null || { printf 'Missing build dependency: %s\n' "$tool" >&2; exit 1; }
done
for source in "$ISO" "$CHECKSUMS" "$SIGNATURE" "$KEY"; do
    [[ -f "$source" ]] || { printf 'Missing source: %s\n' "$source" >&2; exit 1; }
done
if [[ ${NOVA_BUILD_MOUNT_NS:-0} != 1 ]]; then
    exec unshare --mount --propagation private env NOVA_BUILD_MOUNT_NS=1 bash "$PROJECT/build/build-iso.sh" "${ORIGINAL_ARGS[@]}"
fi
ISO=$(realpath -- "$ISO")
CHECKSUMS=$(realpath -- "$CHECKSUMS")
SIGNATURE=$(realpath -- "$SIGNATURE")
KEY=$(realpath -- "$KEY")
[[ -z "$LOCK" ]] || LOCK=$(realpath -- "$LOCK")
[[ ! -e "$OUTPUT" ]] || { printf '%s\n' 'Output directory must be NEW, to avoid overwriting previous builds.' >&2; exit 1; }
[[ -d $(dirname -- "$OUTPUT") ]] || { printf '%s\n' 'Output parent directory does not exist.' >&2; exit 1; }
mkdir -- "$OUTPUT"
OUTPUT=$(realpath -- "$OUTPUT")
exec 9>"$OUTPUT/build.lock"
flock -n 9 || exit 1
python3 "$PROJECT/build/verify-source.py" --iso "$ISO" --checksums "$CHECKSUMS" --signature "$SIGNATURE" --key "$KEY" >"$OUTPUT/source-verification.json"
WORK=$(mktemp -d "$OUTPUT/.nova-work.XXXXXX")
ROOT=$WORK/rootfs
TREE=$WORK/iso
MOUNTS=()
cleanup() {
    local result=$? failed=0 index
    trap - EXIT INT TERM
    for ((index=${#MOUNTS[@]}-1; index>=0; index--)); do
        if mountpoint -q "${MOUNTS[index]}"; then
            umount -- "${MOUNTS[index]}" || failed=1
        fi
    done
    if ((failed)); then
        printf 'Unmount failed; workspace preserved: %s\n' "$WORK" >&2
        exit 1
    fi
    if ((result == 0 && KEEP == 0)); then
        rm -rf -- "$WORK"
    else
        printf 'Workspace preserved for inspection: %s\n' "$WORK" >&2
    fi
    exit "$result"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
exec > >(tee "$OUTPUT/build.log") 2>&1
mkdir -- "$TREE"
xorriso -osirrox on -indev "$ISO" -extract / "$TREE"
[[ -f "$TREE/casper/filesystem.squashfs" && -f "$TREE/casper/filesystem.manifest-desktop" ]] || { printf '%s\n' 'Unsupported Mint ISO layout.'; exit 1; }
ISO_TMP_SQUASH=$TREE/casper/filesystem.squashfs
unsquashfs -d "$ROOT" "$TREE/casper/filesystem.squashfs"
# Reuse the source image's own compression so the remaster matches upstream behavior.
COMP=$(unsquashfs -s "$ISO_TMP_SQUASH" | python3 -c 'import re,sys; m=re.search(r"Compression\s+([a-z0-9]+)", sys.stdin.read()); print(m.group(1) if m else "")')
case "$COMP" in gzip|lz4|lzo|xz|zstd) ;; *) printf 'Unknown source squashfs compression: %s\n' "$COMP" >&2; exit 1;; esac
printf 'Source squashfs compression: %s\n' "$COMP"
python3 - "$ROOT" "$PROJECT/build/base.json" <<'PY'
import json, shlex, sys
from pathlib import Path
root = Path(sys.argv[1])
expected = json.loads(Path(sys.argv[2]).read_text())
release = dict(line.split('=', 1) for line in (root / 'etc/os-release').read_text().splitlines() if '=' in line)
release = {k: shlex.split(v)[0] if v else '' for k, v in release.items()}
if release.get('ID') != 'linuxmint' or release.get('VERSION_ID') != expected['version_id'] or release.get('UBUNTU_CODENAME') != expected['ubuntu_suite']:
    raise SystemExit('Source release does not match pinned base; no cross-release package mixing allowed')
PY
chroot "$ROOT" dpkg --print-architecture | python3 -c 'import sys; assert sys.stdin.read().strip() == "amd64", "Expected amd64"'
if [[ -e "$ROOT/etc/resolv.conf" ]]; then
    cp -a "$ROOT/etc/resolv.conf" "$WORK/resolv.conf.original"
fi
rm -f -- "$ROOT/etc/resolv.conf"
# A loopback stub resolver is unreachable from the chroot, so keep only routable nameservers.
cp -L /etc/resolv.conf "$ROOT/etc/resolv.conf"
python3 - "$ROOT/etc/resolv.conf" <<'PY'
import re, sys
from pathlib import Path
target = Path(sys.argv[1])
servers = []
if target.is_file():
    for line in target.read_text(errors='replace').splitlines():
        match = re.fullmatch(r'\s*nameserver\s+(\S+)', line)
        if match and not (match[1].startswith('127.') or match[1] in ('::1', '0.0.0.0')):
            servers.append(match[1])
if not servers:
    servers = ['1.1.1.1', '9.9.9.9']
target.write_text(''.join('nameserver %s\n' % s for s in servers))
PY
if [[ -e "$ROOT/usr/sbin/policy-rc.d" ]]; then
    cp -a "$ROOT/usr/sbin/policy-rc.d" "$WORK/policy-rc.d.original"
fi
python3 - "$ROOT/usr/sbin/policy-rc.d" <<'PY'
import os, sys
from pathlib import Path
path = Path(sys.argv[1]); path.write_text('#!/bin/sh\nexit 101\n'); os.chmod(path, 0o755)
PY
mount -t proc proc "$ROOT/proc"; MOUNTS+=("$ROOT/proc")
mount --bind /sys "$ROOT/sys"; MOUNTS+=("$ROOT/sys")
mount -o remount,bind,ro "$ROOT/sys"
mount --bind /dev "$ROOT/dev"; MOUNTS+=("$ROOT/dev")
mount --bind /dev/pts "$ROOT/dev/pts"; MOUNTS+=("$ROOT/dev/pts")
CONFIGURE=(python3 "$PROJECT/build/configure-rootfs.py" "$ROOT" --packages "$PROJECT/build/packages.txt" --remove "$PROJECT/build/remove-packages.txt")
[[ -z "$LOCK" ]] || CONFIGURE+=(--lock "$LOCK")
"${CONFIGURE[@]}"
python3 "$PROJECT/build/create-defaults.py" --project "$PROJECT" --output "$WORK/nova-defaults.deb"
install -m 0644 "$WORK/nova-defaults.deb" "$ROOT/tmp/nova-defaults.deb"
chroot "$ROOT" dpkg -i /tmp/nova-defaults.deb
rm -f -- "$ROOT/tmp/nova-defaults.deb"
python3 "$PROJECT/build/deploy-defaults.py" "$ROOT"
python3 "$PROJECT/build/configure-security.py" "$ROOT"
systemctl --root="$ROOT" enable zramswap.service ufw.service
if [[ -d "$ROOT/home/mint" ]]; then
    rsync -a "$ROOT/etc/skel/.config/" "$ROOT/home/mint/.config/"
    chroot "$ROOT" chown -R mint:mint /home/mint/.config
fi
chroot "$ROOT" apt-get check
python3 "$PROJECT/build/prepare-kernel.py" "$ROOT" "$TREE"
chroot "$ROOT" dpkg-query -W '-f=${binary:Package}\t${Version}\t${db:Status-Status}\n' | python3 -c 'import sys; print("".join(p+"="+v+"\n" for p,v,s in (line.rstrip("\n").split("\t") for line in sys.stdin) if s == "installed"), end="")' >"$OUTPUT/packages.lock"
if [[ -n "$LOCK" ]]; then
    python3 "$PROJECT/build/check-lock.py" "$LOCK" "$OUTPUT/packages.lock"
fi
python3 "$PROJECT/build/export-licenses.py" "$ROOT" "$OUTPUT/packages.lock" "$OUTPUT/licenses"
mkdir -p "$OUTPUT/repositories"
cp -a "$ROOT/etc/apt/sources.list.d" "$OUTPUT/repositories/"
[[ ! -f "$ROOT/etc/apt/sources.list" ]] || cp -a "$ROOT/etc/apt/sources.list" "$OUTPUT/repositories/"
cp "$PROJECT/build/base.json" "$OUTPUT/base.json"
if [[ -e "$WORK/resolv.conf.original" || -L "$WORK/resolv.conf.original" ]]; then
    rm -f -- "$ROOT/etc/resolv.conf"
    cp -a "$WORK/resolv.conf.original" "$ROOT/etc/resolv.conf"
else
    rm -f -- "$ROOT/etc/resolv.conf"
fi
if [[ -e "$WORK/policy-rc.d.original" ]]; then
    cp -a "$WORK/policy-rc.d.original" "$ROOT/usr/sbin/policy-rc.d"
else
    rm -f -- "$ROOT/usr/sbin/policy-rc.d"
fi
for ((i=${#MOUNTS[@]}-1; i>=0; i--)); do umount -- "${MOUNTS[i]}"; done
MOUNTS=()
EPOCH=${SOURCE_DATE_EPOCH:-$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["source_date_epoch"])' "$PROJECT/build/base.json")}
[[ "$EPOCH" =~ ^[0-9]+$ ]] || { printf '%s\n' 'Invalid SOURCE_DATE_EPOCH'; exit 1; }
python3 "$PROJECT/build/finalize-tree.py" "$TREE" "$ROOT" --epoch "$EPOCH" --comp "$COMP"
ISO_OUTPUT=$OUTPUT/nova-os-0.1.0-amd64.iso
# Replay original system area and El Torito entries instead of inventing bootloader flags.
xorriso -indev "$ISO" -outdev "$ISO_OUTPUT" -map "$TREE" / -boot_image any replay -volid NOVA_OS_0_1 -commit -end
( cd "$OUTPUT" && sha256sum -- "$(basename -- "$ISO_OUTPUT")" >SHA256SUMS )
bash "$PROJECT/build/verify-iso.sh" "$ISO_OUTPUT" "$OUTPUT/SHA256SUMS" | tee "$OUTPUT/verification.log"
printf 'Built and structurally verified: %s\n' "$ISO_OUTPUT"
printf '%s\n' 'Boot, installation, Secure Boot, desktop performance and hardware remain untested until VM/physical QA.'
