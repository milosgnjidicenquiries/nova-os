#!/usr/bin/env python3
"""Write the remastered image using the boot commands recovered from the source ISO.

Mint 22.1's BIOS El Torito entry has no ISO9660 path, so "-boot_image any replay"
cannot be used. The source instead tells us exactly how it was built; each report
line is a multi-token command and must become separate argv entries, not one string.
"""
import argparse
import shlex
import subprocess


def boot_flags(report):
    flags = []
    for line in report.splitlines():
        line = line.strip()
        if line.startswith("-boot_image "):
            flags.extend(shlex.split(line))
    return flags


def require(flags):
    if not flags:
        raise ValueError("No boot commands recovered from the source ISO")
    joined = " ".join(flags)
    for needed in ("system_area=", "cat_path=", "bin_path=", "efi_path="):
        if needed not in joined:
            raise ValueError(f"Missing {needed} in source boot report")
    return flags


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--iso", required=True)
    parser.add_argument("--tree", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--volid", default="NOVAOS010")
    args = parser.parse_args()
    report = subprocess.check_output(["xorriso", "-indev", args.iso, "-report_el_torito", "cmd"],
                                     text=True, stderr=subprocess.DEVNULL)
    flags = require(boot_flags(report))
    print("Boot commands recovered from the source image:\n" + report)
    subprocess.run(["xorriso", "-indev", args.iso, "-outdev", args.output, "-map", args.tree, "/",
                    "-volid", args.volid] + flags + ["-commit", "-end"], check=True)


if __name__ == "__main__":
    main()
