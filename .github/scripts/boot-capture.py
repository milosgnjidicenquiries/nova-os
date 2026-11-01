#!/usr/bin/env python3
"""Boot an image headless under QEMU and capture the screen over time.

Hosted runners have no /dev/kvm, so this is pure TCG emulation: it answers
"does the image reach a desktop", it says nothing about real speed.
"""
import argparse
import hashlib
import os
import shlex
import socket
import subprocess
import sys
import time
from pathlib import Path


def monitor(sock_path, command, wait=10.0):
    """Send one human-monitor command and drain the reply.

    Reading a fixed byte count blocks forever (the greeting is far shorter than
    the read), so the socket is drained with recv until it goes quiet.
    """
    received = []
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(wait)
        connection.connect(str(sock_path))
        try:
            connection.recv(65536)
        except (socket.timeout, BlockingIOError):
            pass
        connection.sendall((command + "\n").encode())
        deadline = time.time() + wait
        while time.time() < deadline:
            try:
                chunk = connection.recv(65536)
            except (socket.timeout, BlockingIOError):
                break
            if not chunk:
                break
            received.append(chunk)
            if b"(qemu)" in chunk:
                break
    return b"".join(received).decode("utf-8", "replace")


def screendump(sock_path, ppm, retries=3):
    """Dump the screen, reporting why a failed attempt failed.

    Without the monitor reply a missing file is undiagnosable, and this loop
    runs on a hosted runner where a retry costs the whole job.
    """
    last = ""
    for attempt in range(retries):
        try:
            last = monitor(sock_path, f"screendump {ppm}", wait=5.0)
        except OSError as error:
            last = str(error)
        for _ in range(20):
            if ppm.is_file() and ppm.stat().st_size:
                return True
            time.sleep(0.5)
        print(f"screendump attempt {attempt + 1}: no file; monitor said {last.strip()[:300]!r}", flush=True)
    return False


def parse_times(value):
    """Comma-separated seconds, deduplicated and ordered; empty means nothing."""
    return sorted({int(part) for part in value.split(",") if part.strip()})


def wait_with_keys(sock_path, seconds, pending, elapsed):
    """Sleep in short ticks, firing any scheduled Enter keypress that came due.

    A single long sleep would let a scheduled keystroke land minutes late, and
    the point of the keystroke is to dismiss a boot menu that never times out.
    """
    target = elapsed + seconds
    while elapsed < target:
        step = min(15, target - elapsed)
        time.sleep(step)
        elapsed += step
        while pending and pending[0] <= elapsed:
            pending.pop(0)
            reply = monitor(sock_path, "sendkey ret", wait=5.0)
            print(f"sent Enter at {elapsed}s: {reply.strip()[:200]!r}", flush=True)
    return elapsed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--iso", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--memory", default="2048")
    parser.add_argument("--cpus", default="2")
    parser.add_argument("--mode", choices=("bios", "uefi"), default="bios")
    parser.add_argument("--interval", type=int, default=60, help="seconds between screenshots")
    parser.add_argument("--count", type=int, default=30, help="how many screenshots to take")
    parser.add_argument("--enter-at", default="", help="comma-separated seconds at which to press Enter")
    args = parser.parse_args()
    args.out = args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=True)
    iso = args.iso.resolve()
    monitor_socket = args.out / "monitor.sock"
    if monitor_socket.exists():
        monitor_socket.unlink()
    command = [
        "qemu-system-x86_64", "-machine", "pc", "-cpu", "qemu64", "-smp", args.cpus, "-m", args.memory,
        "-cdrom", str(iso), "-boot", "d", "-vga", "std", "-display", "none", "-no-reboot",
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
    pending = parse_times(args.enter_at)
    elapsed = 0
    try:
        for attempt in range(1, args.count + 1):
            # The first frame is taken early so the boot loader / early console is
            # captured even when the desktop itself needs minutes under emulation.
            elapsed = wait_with_keys(monitor_socket, args.interval if attempt > 1 else min(args.interval, 25),
                                     pending, elapsed)
            if guest.poll() is not None:
                print(f"QEMU exited early with code {guest.returncode}: {guest.stderr.read()[:2000]}", flush=True)
                break
            frame = args.out / f"screen-{attempt:03d}.png"
            ppm = (args.out / f"screen-{attempt:03d}.ppm").resolve()
            if not screendump(monitor_socket, ppm):
                print(f"screendump produced no file at frame {attempt}", flush=True)
                continue
            subprocess.run(["convert", str(ppm), str(frame)], check=True)
            # Hash the PPM, not the PNG: ImageMagick stamps a varying chunk into every
            # PNG, so identical screens looked like they kept changing.
            digest = hashlib.sha256(ppm.read_bytes()).hexdigest()[:12]
            changed = "changed" if not frames or frames[-1][1] != digest else "same"
            frames.append((frame.name, digest))
            ppm.unlink()
            print(f"frame {attempt:03d}: {frame.name} {frame.stat().st_size} bytes {digest} {changed}", flush=True)
    finally:
        if guest.poll() is None:
            try:
                monitor(monitor_socket, "quit", wait=5.0)
            except OSError as error:
                print(f"monitor quit failed: {error}", flush=True)
            try:
                guest.wait(timeout=20)
            except subprocess.TimeoutExpired:
                guest.kill()
    if not frames:
        raise SystemExit("No screenshot captured; the boot test produced no evidence")
    distinct = len({digest for _, digest in frames})
    print(f"Captured {len(frames)} frames ({distinct} distinct screens) under TCG emulation. "
          f"Performance is not measurable this way.")


if __name__ == "__main__":
    sys.exit(main())
