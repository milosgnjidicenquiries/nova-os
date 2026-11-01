#!/usr/bin/env python3
"""Print the release asset filenames in deterministic order."""
import argparse
from pathlib import Path

EXCLUDED = {"build.log", "build.lock", "verification.log", "packages.lock", "base.json", "repositories", "licenses"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", type=Path, default=Path("."))
    args = parser.parse_args()
    for path in sorted(args.dir.iterdir()):
        # GitHub rejects an empty asset with "Bad Content-Length", and the build
        # lock is an open file handle, not a deliverable.
        if path.is_file() and path.name not in EXCLUDED and not path.name.startswith(".") and path.stat().st_size:
            print(path.name)


if __name__ == "__main__":
    main()
