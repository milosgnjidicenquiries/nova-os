#!/usr/bin/env python3
import argparse
import re
import subprocess
from pathlib import Path


def read_manifest(path):
    packages = []
    for line in Path(path).read_text().splitlines():
        entry = line.split("#", 1)[0].strip()
        if not entry:
            continue
        if not re.fullmatch(r"[a-z0-9][a-z0-9+.-]*(?::[a-z0-9]+)?(?:=[A-Za-z0-9.+:~_-]+)?", entry):
            raise ValueError(f"Invalid package entry: {entry}")
        packages.append(entry)
    if len(packages) != len(set(packages)):
        raise ValueError("Duplicate package entries")
    return packages


def removal_plan(output):
    return [line.split()[1] for line in output.splitlines() if line.startswith("Remv ")]


def unsafe_removals(plan, protected, essential):
    unsafe = []
    for package in plan:
        name = package.split(":", 1)[0]
        if name in protected or name in essential or name.startswith(("linux-", "grub", "shim", "cryptsetup", "casper", "ubiquity")):
            unsafe.append(package)
    return unsafe


def run(root, arguments, capture=False):
    return subprocess.run(["chroot", str(root), "/usr/bin/env", "DEBIAN_FRONTEND=noninteractive", "LC_ALL=C"] + arguments, check=True, text=True, stdout=subprocess.PIPE if capture else None).stdout


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--packages", required=True, type=Path)
    parser.add_argument("--remove", required=True, type=Path)
    parser.add_argument("--lock", type=Path)
    args = parser.parse_args()
    required = read_manifest(args.packages)
    requested = read_manifest(args.lock) if args.lock else required
    requested = [entry for entry in requested if entry.split("=", 1)[0] != "nova-defaults"]
    if args.lock:
        locked_names = {entry.split("=", 1)[0].split(":", 1)[0] for entry in requested}
        if any(entry.split("=", 1)[0] not in locked_names for entry in required):
            parser.error("Package lock must include every required package")
        if any("=" not in entry for entry in requested):
            parser.error("Every lock entry must include an exact version")
    run(args.root, ["apt-get", "update"])
    if not args.lock:
        run(args.root, ["apt-get", "-y", "--with-new-pkgs", "--no-install-recommends", "upgrade"])
    run(args.root, ["apt-get", "-y", "--no-install-recommends", "install"] + requested)
    inventory = run(args.root, ["dpkg-query", "-W", "-f=${binary:Package}\t${db:Status-Status}\t${Essential}\t${Priority}\n"], True)
    rows = [line.split("\t") for line in inventory.splitlines()]
    installed = {row[0]: row for row in rows if len(row) == 4 and row[1] == "installed"}
    essential = {name.split(":", 1)[0] for name, row in installed.items() if row[2] == "yes" or row[3] == "required"}
    optional = [name for name in read_manifest(args.remove) if name in installed]
    protected = {entry.split("=", 1)[0].split(":", 1)[0] for entry in required}
    protected.update({"systemd", "systemd-sysv", "udev", "dbus", "sudo", "apt", "dpkg", "mintsystem", "linuxmint-keyring", "ubuntu-keyring", "ubuntu-minimal", "initramfs-tools", "xserver-xorg", "xserver-xorg-core", "xserver-xorg-video-intel", "linux-firmware", "network-manager", "openssh-client", "apparmor", "unattended-upgrades", "timeshift", "mint-meta-xfce"})
    if optional:
        plan = removal_plan(run(args.root, ["apt-get", "-s", "purge"] + optional, True))
        unsafe = unsafe_removals(plan, protected, essential)
        if unsafe:
            raise SystemExit("Unsafe removal dependencies: " + ", ".join(unsafe) + "; adjust remove-packages.txt, no removal performed")
        run(args.root, ["apt-get", "-y", "purge"] + optional)
    run(args.root, ["apt-get", "clean"])
    run(args.root, ["dpkg", "--audit"])
    run(args.root, ["apt-get", "check"])


if __name__ == "__main__":
    main()
