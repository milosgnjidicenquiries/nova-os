#!/usr/bin/env python3
import argparse
import hashlib
import subprocess
from pathlib import Path


def desktop_manifest(current, original, original_desktop):
    excluded = {line.split()[0] for line in original.splitlines() if line.strip()} - {line.split()[0] for line in original_desktop.splitlines() if line.strip()}
    return "".join(line + "\n" for line in current.splitlines() if line.strip() and line.split()[0] not in excluded)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("tree", type=Path)
    parser.add_argument("root", type=Path)
    parser.add_argument("--epoch", required=True, type=int)
    parser.add_argument("--comp", required=True, choices=("gzip", "lz4", "lzo", "xz", "zstd"))
    args = parser.parse_args()
    casper = args.tree / "casper"
    manifest = casper / "filesystem.manifest"
    installed_manifest = casper / "filesystem.manifest-desktop"
    if not installed_manifest.exists():
        raise SystemExit("Missing Mint installer manifest; refusing to guess installer package exclusions")
    inventory = subprocess.check_output(["chroot", str(args.root), "dpkg-query", "-W", "-f=${Package}\t${Version}\t${db:Status-Status}\\n"], text=True)
    current = "".join(package + " " + version + "\n" for package, version, status in (line.split("\t") for line in inventory.splitlines()) if status == "installed")
    original = manifest.read_text()
    original_desktop = installed_manifest.read_text()
    manifest.write_text(current)
    installed_manifest.write_text(desktop_manifest(current, original, original_desktop))
    (casper / "filesystem.size").write_text(subprocess.check_output(["du", "-sx", "--block-size=1", str(args.root)], text=True).split()[0] + "\n")
    squashfs = casper / "filesystem.squashfs"
    squashfs.unlink()
    subprocess.run(["mksquashfs", str(args.root), str(squashfs), "-noappend", "-comp", args.comp, "-b", "1048576", "-processors", "2", "-mkfs-time", str(args.epoch), "-all-time", str(args.epoch)], check=True)
    entries = []
    for path in sorted(args.tree.rglob("*")):
        relative = path.relative_to(args.tree).as_posix()
        if not path.is_file() or path.is_symlink() or relative == "md5sum.txt" or relative.startswith("isolinux/"):
            continue
        digest = hashlib.md5()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                digest.update(chunk)
        entries.append(f"{digest.hexdigest()}  ./{relative}\n")
    (args.tree / "md5sum.txt").write_text("".join(entries))


if __name__ == "__main__":
    main()
