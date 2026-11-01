#!/usr/bin/env python3
import argparse
import re
import shutil
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Configure target-root firewall files without invoking host firewall")
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    if root == Path("/") or not (root / "etc/linuxmint/info").is_file():
        parser.error("Expected extracted Mint filesystem, never host root")
    backup = root / "var/lib/nova/backups/security"
    backup.mkdir(parents=True, exist_ok=True)
    for relative, values in {
        "etc/ufw/ufw.conf": {"ENABLED": "yes"},
        "etc/default/ufw": {"DEFAULT_INPUT_POLICY": '"DROP"', "DEFAULT_OUTPUT_POLICY": '"ACCEPT"', "DEFAULT_FORWARD_POLICY": '"DROP"'},
    }.items():
        path = root / relative
        saved = backup / relative.replace("/", "_")
        if not saved.exists():
            shutil.copyfile(path, saved)
        text = path.read_text()
        for key, value in values.items():
            text, count = re.subn(r"^" + re.escape(key) + r"=.*$", key + "=" + value, text, flags=re.MULTILINE)
            if count != 1:
                raise SystemExit(f"Unexpected firewall config: {relative}/{key}")
        path.write_text(text)
    print("UFW enabled for target boot only; no host firewall commands executed")


if __name__ == "__main__":
    main()
