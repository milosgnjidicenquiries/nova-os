#!/usr/bin/env python3
import sys
from pathlib import Path


def entries(path):
    result = {}
    for line in Path(path).read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            package, version = line.split("=", 1)
            result[package] = version
    return result


def main():
    if len(sys.argv) != 3:
        raise SystemExit("Usage: check-lock.py EXPECTED ACTUAL")
    expected, actual = map(entries, sys.argv[1:])
    if expected != actual:
        changes = [name for name in sorted(expected.keys() | actual.keys()) if expected.get(name) != actual.get(name)]
        raise SystemExit("Package lock mismatch: " + ", ".join(changes))
    print("Exact installed package lock: OK")


if __name__ == "__main__":
    main()
