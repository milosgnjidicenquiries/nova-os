#!/usr/bin/env python3
import argparse
import shutil
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Rebuild live initramfs from installed stock kernel and casper hooks")
    parser.add_argument("root", type=Path)
    parser.add_argument("tree", type=Path)
    args = parser.parse_args()
    versions = [path.name.removeprefix("vmlinuz-") for path in (args.root / "boot").glob("vmlinuz-*") if (args.root / "lib/modules" / path.name.removeprefix("vmlinuz-")).is_dir()]
    if not versions:
        raise SystemExit("No installed kernel image/modules found")
    selected = versions[0]
    for version in versions[1:]:
        if subprocess.run(["dpkg", "--compare-versions", version, "gt", selected]).returncode == 0:
            selected = version
    if not selected.startswith("6.8."):
        raise SystemExit("Expected pinned Ubuntu GA 6.8 kernel track; refusing an implicit HWE/custom kernel switch")
    initrd = args.root / "boot" / ("initrd.img-" + selected)
    mode = "-u" if initrd.exists() else "-c"
    subprocess.run(["chroot", str(args.root), "update-initramfs", mode, "-k", selected], check=True)
    casper = args.tree / "casper"
    targets = [casper / name for name in ("initrd", "initrd.lz", "initrd.gz") if (casper / name).is_file()]
    if len(targets) != 1:
        raise SystemExit("Unknown live initrd layout; refusing to guess bootloader path")
    shutil.copyfile(args.root / "boot" / ("vmlinuz-" + selected), casper / "vmlinuz")
    shutil.copyfile(initrd, targets[0])
    print("Live kernel/initramfs synchronized:", selected)


if __name__ == "__main__":
    main()
