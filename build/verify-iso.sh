#!/usr/bin/env bash
set -Eeuo pipefail
export LC_ALL=C
[[ $# == 2 ]] || { printf '%s\n' 'Usage: bash build/verify-iso.sh ISO SHA256SUMS'; exit 2; }
for tool in python3 xorriso unsquashfs; do
    command -v "$tool" >/dev/null || { printf 'Missing tool: %s\n' "$tool" >&2; exit 1; }
done
ISO=$(realpath -- "$1")
SUMS=$(realpath -- "$2")
[[ -f "$ISO" && -f "$SUMS" ]] || exit 1
python3 - "$ISO" "$SUMS" <<'PY'
import hashlib, sys
from pathlib import Path
iso, sums = map(Path, sys.argv[1:])
expected = []
for line in sums.read_text().splitlines():
    parts = line.split(maxsplit=1)
    if len(parts) == 2 and Path(parts[1].lstrip('*')).name == iso.name:
        expected.append(parts[0])
if len(expected) != 1:
    raise SystemExit('Expected one checksum for ISO')
h = hashlib.sha256()
with iso.open('rb') as stream:
    for data in iter(lambda: stream.read(8 * 1024 * 1024), b''): h.update(data)
if h.hexdigest() != expected[0]: raise SystemExit('ISO checksum mismatch')
print('SHA256: OK (local integrity, not release publisher authentication)')
PY
WORK=$(mktemp -d)
trap 'rm -rf -- "$WORK"' EXIT
xorriso -indev "$ISO" -report_el_torito plain -report_system_area plain >"$WORK/boot.txt" 2>&1
python3 - "$WORK/boot.txt" <<'PY'
import re, sys
from pathlib import Path
report = Path(sys.argv[1]).read_text()
print(report)
for platform in ('BIOS', 'UEFI'):
    if not re.search(r'El Torito boot img\s*:\s*\d+\s+' + platform + r'\s+y\b', report):
        raise SystemExit('Missing bootable ' + platform + ' El Torito entry')
if not re.search(r'System area summary\s*:.*(?:MBR|GPT)', report):
    raise SystemExit('Missing hybrid disk system area')
PY
xorriso -osirrox on -indev "$ISO" -extract /casper "$WORK/casper"
unsquashfs -s "$WORK/casper/filesystem.squashfs"
unsquashfs -d "$WORK/content" "$WORK/casper/filesystem.squashfs" etc/nova-release usr/local/bin/nova-compat usr/local/bin/nova-hardware usr/share/themes/Nova/gtk-3.0/gtk.css
python3 - "$WORK" <<'PY'
import sys
from pathlib import Path
work = Path(sys.argv[1])
for name in ('filesystem.manifest', 'filesystem.manifest-desktop', 'filesystem.size', 'vmlinuz'):
    if not (work / 'casper' / name).is_file(): raise SystemExit('Missing casper/' + name)
if not any((work / 'casper' / name).is_file() for name in ('initrd', 'initrd.lz', 'initrd.gz')):
    raise SystemExit('Missing casper initrd')
for name in ('etc/nova-release', 'usr/local/bin/nova-compat', 'usr/local/bin/nova-hardware', 'usr/share/themes/Nova/gtk-3.0/gtk.css'):
    if not (work / 'content' / name).is_file(): raise SystemExit('Missing Nova payload: ' + name)
manifest = (work / 'casper/filesystem.manifest').read_text()
if 'nova-defaults ' not in manifest or 'ubiquity ' not in manifest or 'casper ' not in manifest:
    raise SystemExit('Missing defaults/live/installer package in manifest')
print('Live payload, installer manifest, Nova package and BIOS/UEFI boot metadata: OK')
print('This is NOT a boot, installation, Secure Boot or runtime test.')
PY
