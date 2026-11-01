#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


def gpg_path(path, executable="gpg"):
    path = Path(path).resolve()
    binary = Path(shutil.which(executable) or executable)
    if os.name == "nt" and (binary.parent / "msys-2.0.dll").is_file():
        return subprocess.check_output([str(binary.parent / "cygpath.exe"), "-u", str(path)], text=True).strip()
    return path.as_posix()


def manifest_digest(text, filename):
    matches = []
    for line in text.splitlines():
        match = re.fullmatch(r"([0-9a-fA-F]{64}) [ *](.+)", line)
        if match and match[2] == filename:
            matches.append(match[1].lower())
    if len(matches) != 1:
        raise ValueError("Expected exactly one SHA256 entry for the configured ISO")
    return matches[0]


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(iso, checksums, signature, key, config, gpg="gpg"):
    iso = Path(iso).resolve()
    if iso.name != config["iso_filename"]:
        raise ValueError("ISO filename does not match selected base")
    fingerprint = config["signing_key_fingerprint"]
    with tempfile.TemporaryDirectory(prefix="nova-gpg-") as home:
        args = [gpg, "--batch", "--no-options", "--homedir", gpg_path(home, gpg)]
        subprocess.run(args + ["--import", gpg_path(key, gpg)], check=True, capture_output=True)
        result = subprocess.run(args + ["--status-fd", "1", "--verify", gpg_path(signature, gpg), gpg_path(checksums, gpg)], check=True, capture_output=True, text=True)
        valid = [line.split()[2:] for line in result.stdout.splitlines() if line.startswith("[GNUPG:] VALIDSIG ")]
        if not any(fields[0] == fingerprint or fields[-1] == fingerprint for fields in valid):
            raise ValueError("Signature not made by pinned Linux Mint ISO signing key")
        if any(f"[GNUPG:] {state} " in result.stdout for state in ("REVKEYSIG", "EXPKEYSIG", "EXPSIG")):
            raise ValueError("Expired or revoked signature/key; verify upstream key rotation")
    expected = manifest_digest(Path(checksums).read_text(encoding="utf-8"), iso.name)
    actual = sha256(iso)
    if actual != expected:
        raise ValueError("ISO SHA256 mismatch")
    return {"iso": iso.name, "sha256": actual, "signer": fingerprint, "base": config["release"], "verified": True}


def main():
    parser = argparse.ArgumentParser(description="Verify official Mint ISO against a pinned signing key")
    for option in ("iso", "checksums", "signature", "key"):
        parser.add_argument("--" + option, required=True, type=Path)
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("base.json"))
    args = parser.parse_args()
    try:
        result = verify(args.iso, args.checksums, args.signature, args.key, json.loads(args.config.read_text()))
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Verification failed: {error}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
