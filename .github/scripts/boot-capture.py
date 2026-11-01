#!/usr/bin/env python3
"""Boot an image headless under QEMU and capture the screen over time.

Hosted runners have no /dev/kvm, so this is pure TCG emulation: it answers
"does the image reach a desktop", it says nothing about real speed.
"""
import argparse
import os
import shlex
import socket
import subprocess
import sys
import time
from pathlib import Path


def monitor(sock_path, command, settle=0.5):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(30)
        connection.connect(str(sock_path))
        stream = connection.makefile("rw", encoding="utf-8", errors="replace")
        stream.read(4096)
        stream.write(command + "\n")
        stream.flush()
        time.sleep(settle)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--iso", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--memory", default="2048")
    parser.add_argument("--cpus", default="2")
    parser.add_argument("--mode", choices=("bios", "uefi"), default="bios")
    parser.add_argument("--interval", type=int, default=60, help="seconds between screenshots")
    parser.add_argument("--count", type=int, default=30, help="how many screenshots to take")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    iso = args.iso.resolve()
    monitor_socket = args.out / "monitor.sock"
    if monitor_socket.exists():
        monitor_socket.unlink()
    command = [
        "qemu-system-x86_64", "-machine", "pc", "-cpu", "qemu64", "-smp", args.cpus, "-m", args.memory,
        "-cdrom", str(iso), "-boot", "d", "-vga", "std", "-display", "none",
        "-rtc", "base=utc", "-monitor", f"unix:{monitor_socket},server,nowait",
        "-serial", f"file:{args.out / 'serial.log'}",
    ]
    if args.mode == "uefi":
        code = Path("/usr/share/OVMF/OVMF_CODE_4M.fd")
        vars_template = Path("/usr/share/OVMF/OVMF_VARS_4M.fd")
        if not code.is_file():
            raise SystemExit(f"UEFI mode needs {code}; install the ovmf package")
        vars_file = args.out / "OVMF_VARS.fd"
        vars_file.write_bytes(vars_template.read_bytes())
        command[1:1] = ["-drive", f"if=pflash,format=raw,readonly=on,file={code}", "-drive", f"if=pflash,format=raw,file={vars_file}"]
    print("QEMU:", " ".join(shlex.quote(part) for part in command), flush=True)
    guest = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    frames = []
    try:
        for attempt in range(1, args.count + 1):
            time.sleep(args.interval)
            if guest.poll() is not None:
                print(f"QEMU exited early with code {guest.returncode}: {guest.stderr.read()[:2000]}", flush=True)
                break
            frame = args.out / f"screen-{attempt:03d}.png"
            ppm = frame.with_suffix(".ppm")
            monitor(monitor_socket, f"screendump {ppm}")
            if not ppm.is_file():
                print(f"screendump produced no file at frame {attempt}", flush=True)
                continue
            subprocess.run(["convert", str(ppm), str(frame)], check=True)
            ppm.unlink()
            # A blank screen hashes the same as the next blank screen; report change, not content.
            digest = __import__("hashlib").sha256(frame.read_bytes()).hexdigest()[:12]
            changed = "changed" if not frames or frames[-1][1] != digest else "same"
            frames.append((frame.name, digest))
            print(f"frame {attempt:03d}: {frame.name} {frame.stat().st_size} bytes {digest} {changed}", flush=True)
    finally:
        if guest.poll() is None:
            monitor(monitor_socket, "quit")
            try:
                guest.wait(timeout=20)
            except subprocess.TimeoutExpired:
                guest.kill()
    if not frames:
        raise SystemExit("No screenshot captured; the boot test produced no evidence")
    print(f"Captured {len(frames)} frames under TCG emulation. Performance is not measurable this way.")


if __name__ == "__main__":
    sys.exit(main())
