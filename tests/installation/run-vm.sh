#!/usr/bin/env bash
set -Eeuo pipefail
usage() { printf '%s\n' 'Usage: bash tests/installation/run-vm.sh --iso FILE [--ram 1024|2048|4096] [--uefi CODE VARS] [--disk NEW_QCOW2]'; }
ISO= RAM=1024 DISK= CODE= VARS=
while (($#)); do
    case "$1" in
        --iso|--ram|--disk) (($# >= 2)) || { usage; exit 2; }; case "$1" in --iso) ISO=$2;; --ram) RAM=$2;; --disk) DISK=$2;; esac; shift 2;;
        --uefi) (($# >= 3)) || { usage; exit 2; }; CODE=$2; VARS=$3; shift 3;;
        --help) usage; exit 0;;
        *) usage; exit 2;;
    esac
done
[[ -f "$ISO" && "$RAM" =~ ^(1024|2048|4096)$ ]] || { usage; exit 2; }
command -v qemu-system-x86_64 >/dev/null || { printf '%s\n' 'Install qemu-system-x86.'; exit 1; }
WORK=$(mktemp -d)
trap 'rm -rf -- "$WORK"' EXIT
ARGS=(-machine pc -accel tcg -cpu core2duo -smp 2 -m "$RAM" -cdrom "$ISO" -boot d -vga std -nic user,model=e1000 -no-reboot)
if [[ -n "$CODE" ]]; then
    [[ -f "$CODE" && -f "$VARS" ]] || exit 1
    cp -- "$VARS" "$WORK/OVMF_VARS.fd"
    ARGS+=(-drive "if=pflash,format=raw,readonly=on,file=$CODE" -drive "if=pflash,format=raw,file=$WORK/OVMF_VARS.fd")
fi
if [[ -n "$DISK" ]]; then
    [[ ! -e "$DISK" && -d $(dirname -- "$DISK") && "$DISK" != /dev/* ]] || { printf '%s\n' 'Disk must be a NEW regular qcow2 file, never a host disk.'; exit 1; }
    command -v qemu-img >/dev/null || exit 1
    qemu-img create -f qcow2 "$DISK" 24G
    ARGS+=(-drive "file=$DISK,format=qcow2,if=ide")
fi
printf '%s\n' 'Interactive QA VM. No host disks passed through. TCG performance is not a physical Celeron benchmark.'
qemu-system-x86_64 "${ARGS[@]}"
