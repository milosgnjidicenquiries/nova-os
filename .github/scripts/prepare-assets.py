#!/usr/bin/env python3
"""Split an oversized image into ordered parts and write per-asset checksums."""
import argparse
import hashlib
import subprocess
from pathlib import Path


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(16 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", type=Path, default=Path("."))
    parser.add_argument("--limit", type=int, required=True)
    args = parser.parse_args()
    iso = args.dir / "nova-os-0.1.0-amd64.iso"
    size = iso.stat().st_size
    if size > args.limit:
        subprocess.run(["split", "-b", str(args.limit), "-d", "--additional-suffix=.part",
                        str(iso), str(iso) + "."], check=True)
        print(f"Splitted {size} bytes into {args.limit}-byte parts")
    else:
        print(f"Image fits one asset: {size} bytes")
    assets = [path.name for path in sorted(args.dir.iterdir())
              if path.is_file() and path.name not in {"ASSET_SHA256SUMS"}]
    (args.dir / "ASSET_SHA256SUMS").write_text("".join(sha256(args.dir / name) + "  " + name + "\n" for name in assets))


if __name__ == "__main__":
    main()
