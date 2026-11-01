#!/usr/bin/env python3
"""Reassemble a split release image and check it against the build's SHA256SUMS."""
import argparse
import hashlib
import sys
from pathlib import Path


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(16 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", type=Path, required=True)
    parser.add_argument("--name", default="nova-os-0.1.0-amd64.iso")
    args = parser.parse_args()
    iso = args.dir / args.name
    parts = sorted(args.dir.glob(args.name + ".*.part"))
    if parts:
        if iso.exists():
            raise SystemExit(f"{iso} already exists; refusing to overwrite it with {len(parts)} parts")
        with iso.open("wb") as output:
            for part in parts:
                with part.open("rb") as stream:
                    while chunk := stream.read(16 * 1024 * 1024):
                        output.write(chunk)
        print(f"Joined {len(parts)} parts into {iso} ({iso.stat().st_size} bytes)")
    elif not iso.is_file():
        raise SystemExit(f"Neither {iso} nor {args.name}.*.part exists in {args.dir}")
    sums = args.dir / "SHA256SUMS"
    if not sums.is_file():
        raise SystemExit("SHA256SUMS is required to accept an image for boot testing")
    wanted = [line.split()[0] for line in sums.read_text().splitlines() if Path(line.split(maxsplit=1)[1]).name == args.name]
    if len(wanted) != 1:
        raise SystemExit(f"Expected exactly one SHA256SUMS entry for {args.name}")
    actual = sha256(iso)
    if actual != wanted[0]:
        raise SystemExit(f"Checksum mismatch: expected {wanted[0]} got {actual}")
    print(f"SHA256 verified: {actual}")


if __name__ == "__main__":
    sys.exit(main())
