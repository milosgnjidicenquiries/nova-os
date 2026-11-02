#!/usr/bin/env python3
import argparse
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def stage_payload(project, stage):
    def copy(source, destination, executable=False):
        source = project / source
        destination = stage / destination
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        destination.chmod(0o755 if executable else 0o644)

    for source, target in (
        ("desktop/themes", "usr/share/themes"),
        ("desktop/icons", "usr/share/icons"),
        ("desktop/xfce-config", "usr/share/nova/skel/.config"),
        ("applications", "usr/share/applications"),
    ):
        shutil.copytree(project / source, stage / target, dirs_exist_ok=True)
    for source, target in (
        ("scripts/nova-hardware.py", "usr/local/bin/nova-hardware"),
        ("scripts/nova-notify.py", "usr/local/bin/nova-notify"),
        ("desktop/nova-theme.sh", "usr/local/bin/nova-theme"),
        ("compatibility/nova-compat.py", "usr/local/bin/nova-compat"),
        ("compatibility/install-component.sh", "usr/local/libexec/nova-install-component"),
        ("system/performance/nova-performance.sh", "usr/local/bin/nova-performance"),
        ("tests/performance/benchmark.py", "usr/local/bin/nova-benchmark"),
        ("installer/nova-firstboot.sh", "usr/local/bin/nova-firstboot"),
    ):
        copy(source, target, True)
    for source, target in (
        ("desktop/wallpapers/nova.svg", "usr/share/backgrounds/nova.svg"),
        ("system/performance/zramswap", "usr/share/nova/performance/zramswap"),
        ("system/performance/zramswap-low-memory", "usr/share/nova/performance/zramswap-low-memory"),
        ("system/performance/nova-low-memory.conf", "usr/share/nova/performance/nova-low-memory.conf"),
        ("system/browser/nova.js", "usr/share/nova/browser/nova.js"),
        ("system/performance/nova-journald.conf", "usr/share/nova/performance/nova-journald.conf"),
        ("installer/nova-firstboot.desktop", "usr/share/nova/skel/.config/autostart/nova-firstboot.desktop"),
        ("installer/welcome.html", "usr/share/nova/welcome.html"),
        ("LICENSES/NOVA-MIT.txt", "usr/share/doc/nova-defaults/copyright"),
        ("build/base.json", "usr/share/nova/base.json"),
    ):
        copy(source, target)
    autostart = stage / "usr/share/nova/skel/.config/autostart/mintwelcome.desktop"
    autostart.write_text("[Desktop Entry]\nType=Application\nName=Mint Welcome\nHidden=true\n")
    release = stage / "etc/nova-release"
    release.parent.mkdir(parents=True, exist_ok=True)
    release.write_text('NAME="Nova OS"\nVERSION="0.1.0-development"\nBASE="Linux Mint 22.1 Xfce"\n')
    for path in stage.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"Unexpected payload symlink: {path}")
        path.chmod(0o755 if path.is_dir() or path.parts[-3:-1] == ("local", "bin") or path.parent.name == "libexec" else 0o644)
    control = stage / "DEBIAN"
    control.mkdir(mode=0o755)
    (control / "control").write_text("Package: nova-defaults\nVersion: 0.1.0\nSection: metapackages\nPriority: optional\nArchitecture: all\nMaintainer: Project Nova OS contributors <nova@example.invalid>\nDepends: python3, python3-gi, gir1.2-gtk-3.0, xfce4, xfconf, xfce4-whiskermenu-plugin, xfce4-pulseaudio-plugin, xfce4-power-manager, zram-tools, pkexec, xdg-utils\nDescription: Nova desktop profiles and explicitly optional compatibility tools\n Original lightweight XFCE assets, Linux diagnostics and per-user utilities.\n")
    (control / "conffiles").write_text("/etc/nova-release\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists() or not args.output.parent.is_dir():
        parser.error("Output must be a new file in an existing directory")
    with tempfile.TemporaryDirectory(prefix="nova-deb-") as directory:
        stage = Path(directory) / "nova-defaults"
        stage.mkdir()
        stage_payload(args.project.resolve(), stage)
        subprocess.run(["dpkg-deb", "--build", "--root-owner-group", str(stage), str(args.output.resolve())], check=True)


if __name__ == "__main__":
    main()
