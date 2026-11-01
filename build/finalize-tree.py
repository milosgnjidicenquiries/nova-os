#!/usr/bin/env python3
import argparse
import hashlib
import subprocess
from pathlib import Path


def desktop_manifest(current, original, original_desktop):
    excluded = {line.split()[0] for line in original.splitlines() if line.strip()} - {line.split()[0] for line in original_desktop.splitlines() if line.strip()}
    return "".join(line + "\n" for line in current.splitlines() if line.strip() and line.split()[0] not in excluded)


def prune_remove_list(original_remove, installed):
    return "".join(line + "\n" for line in original_remove.splitlines() if line.strip() and line.split()[0] in installed)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("tree", type=Path)
    parser.add_argument("root", type=Path)
    parser.add_argument("--epoch", required=True, type=int)
    parser.add_argument("--comp", required=True, choices=("gzip", "lz4", "lzo", "xz", "zstd"))
    args = parser.parse_args()
    casper = args.tree / "casper"
    manifest = casper / "filesystem.manifest"
    desktop_manifest_path = casper / "filesystem.manifest-desktop"
    remove_manifest = casper / "filesystem.manifest-remove"
    if not (desktop_manifest_path.is_file() or remove_manifest.is_file()):
        raise SystemExit("Missing Mint installer manifests (neither filesystem.manifest-desktop nor filesystem.manifest-remove); refusing to guess installer package handling")
    inventory = subprocess.check_output(["chroot", str(args.root), "dpkg-query", "-W", "-f=${Package}\t${Version}\t${db:Status-Status}\\n"], text=True)
    installed = [(package, version) for package, version, status in (line.split("\t") for line in inventory.splitlines()) if status == "installed"]
    # Mint 22.1 separates name and version with a tab; keep whatever the base image used.
    separator = "\t" if "\t" in manifest.read_text() else " "
    current = "".join(package + separator + version + "\n" for package, version in installed)
    original = manifest.read_text()
    manifest.write_text(current)
    if desktop_manifest_path.is_file():
        desktop_manifest_path.write_text(desktop_manifest(current, original, desktop_manifest_path.read_text()))
    if remove_manifest.is_file():
        remove_manifest.write_text(prune_remove_list(remove_manifest.read_text(), {package for package, _ in installed}))
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
