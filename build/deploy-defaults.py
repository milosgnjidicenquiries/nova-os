#!/usr/bin/env python3
import argparse
import shutil
from pathlib import Path


def deploy(root):
    root = Path(root).resolve()
    if root == Path("/") or not (root / "etc/linuxmint/info").is_file():
        raise ValueError("Expected extracted Mint rootfs, not host root")
    backup = root / "var/lib/nova/backups"
    backup.mkdir(parents=True, exist_ok=True)
    backup.chmod(0o700)
    mappings = [(root / "usr/share/nova/performance/zramswap", root / "etc/default/zramswap", backup / "zramswap"),
                (root / "usr/share/nova/performance/nova-journald.conf", root / "etc/systemd/journald.conf.d/nova-performance.conf", backup / "nova-performance.conf")]
    for source in (root / "usr/share/nova/skel").rglob("*"):
        if source.is_file():
            relative = source.relative_to(root / "usr/share/nova/skel")
            mappings.append((source, root / "etc/skel" / relative, backup / "skel" / relative))
    for source, target, saved in mappings:
        if not target.resolve().is_relative_to(root):
            raise ValueError(f"Target escapes extracted rootfs: {target}")
        saved.parent.mkdir(parents=True, exist_ok=True)
        absent = saved.with_name(saved.name + ".absent")
        if not saved.exists() and not absent.exists():
            if target.is_file():
                shutil.copy2(target, saved)
            else:
                absent.touch(mode=0o600)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        target.chmod(0o644)
    print("Nova defaults deployed; original skel/performance files backed up without package ownership collisions")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    deploy(args.root)


if __name__ == "__main__":
    main()
