#!/usr/bin/env python3
import argparse
import csv
import shutil
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("lock", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir()
    with (args.output / "inventory.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["package", "version", "copyright_file", "redistribution_review"])
        for line in args.lock.read_text().splitlines():
            package, version = line.split("=", 1)
            name = package.split(":", 1)[0]
            source = args.root / "usr/share/doc" / name / "copyright"
            target = package.replace(":", "_") + ".copyright"
            if source.is_file():
                shutil.copyfile(source, args.output / target)
                writer.writerow([package, version, target, "pending"])
            else:
                writer.writerow([package, version, "missing", "pending"])
    print("License inventory exported; redistribution approval still requires review")


if __name__ == "__main__":
    main()
