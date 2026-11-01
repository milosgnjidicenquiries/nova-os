#!/usr/bin/env python3
"""Boot an image headless under QEMU and capture the screen over time.

Hosted runners have no /dev/kvm, so this is pure TCG emulation: it answers
"does the image reach a desktop", it says nothing about real speed.
"""
import argparse
import hashlib
import shlex
import socket
import subprocess
import sys
import time
from pathlib import Path

PROMPT = b"(qemu)"


class Monitor:
    """One long-lived HMP connection.

    Reconnecting per command loses against QEMU's single-client monitor: the
    fresh socket inherits the previous prompt, the command is never parsed, and
    screendump answers "(qemu)" while producing no file. That failure looked
    like a broken guest until the reply was logged.
    """

    def __init__(self, sock_path, timeout=10.0):
        self.connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.connection.settimeout(timeout)
        self.connection.connect(str(sock_path))
        self.buffer = b""

    def wait_for_prompt(self, limit):
        deadline = time.time() + limit
        while PROMPT not in self.buffer:
            if time.time() > deadline:
                return False
            try:
                chunk = self.connection.recv(65536)
            except (socket.timeout, BlockingIOError):
                continue
            if not chunk:
                return False
            self.buffer += chunk
        return True

    def command(self, text, wait=10.0):
        """Send one command and return (saw_prompt, reply_text)."""
        self.buffer = b""
        self.connection.sendall((text + "\n").encode())
        return self.wait_for_prompt(wait), self.buffer.decode("utf-8", "replace").strip()

    def close(self):
        try:
            self.connection.close()
        except OSError:
            pass


def connect_monitor(sock_path, tries=12):
    """Wait for QEMU to create the socket, then prove the monitor answers."""
    deadline = time.time() + 60
    while time.time() < deadline:
        if sock_path.exists():
            connection = None
            try:
                connection = Monitor(sock_path)
                if connection.wait_for_prompt(5.0):
                    ok, reply = connection.command("info status")
                    if ok:
                        print(f"monitor ready: {reply!r}", flush=True)
                        return connection
            except OSError:
                pass
            if connection:
                connection.close()
        time.sleep(2)
    raise SystemExit(f"QEMU monitor at {sock_path} never answered; no boot evidence possible")


def screendump(connection, ppm, retries=3):
    """Dump the screen, reporting why a failed attempt failed."""
    for attempt in range(retries):
        ok, reply = connection.command(f"screendump {ppm}")
        for _ in range(20):
            if ppm.is_file() and ppm.stat().st_size:
                return True
            time.sleep(0.5)
        print(f"screendump attempt {attempt + 1}: no file (prompt seen: {ok}, monitor said {reply[:300]!r})", flush=True)
    return False


def parse_times(value):
    """Comma-separated seconds, deduplicated and ordered; empty means nothing."""
    return sorted({int(part) for part in value.split(",") if part.strip()})


def press(connection, key):
    ok, reply = connection.command(f"sendkey {key}")
    print(f"sent {key}: prompt={ok} reply={reply[:120]!r}", flush=True)


def wait_with_keys(connection, seconds, pending, elapsed):
    """Sleep in short ticks, firing any scheduled keypress that came due.

    A single long sleep would let a scheduled keystroke land minutes late, and
    the point of the keystroke is to dismiss a boot menu that never times out.
    """
    target = elapsed + seconds
    while elapsed < target:
        step = min(15, target - elapsed)
        time.sleep(step)
        elapsed += step
        while pending and pending[0][0] <= elapsed:
            press(connection, pending.pop(0)[1])
    return elapsed


def qemu_command(args, iso, monitor_socket):
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
        command[1:1] = ["-drive", f"if=pflash,format=raw,readonly=on,file={code}",
                        "-drive", f"if=pflash,format=raw,file={vars_file}"]
    return command


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
    # "ret" is what dismisses the GRUB menu; the name stays readable in the log.
    pending = [(second, "ret") for second in parse_times(args.enter_at)]
    command = qemu_command(args, iso, monitor_socket)
    print("QEMU:", " ".join(shlex.quote(part) for part in command), flush=True)
    guest = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    connection = connect_monitor(monitor_socket)
    frames = []
    elapsed = 0
    try:
        for attempt in range(1, args.count + 1):
            # The first frame is taken early so the boot loader / early console is
            # captured even when the desktop itself needs minutes under emulation.
            due = args.interval if attempt > 1 else min(args.interval, 25)
            elapsed = wait_with_keys(connection, due, pending, elapsed)
            if guest.poll() is not None:
                print(f"QEMU exited early with code {guest.returncode}: {guest.stderr.read()[:2000]}", flush=True)
                break
            frame = args.out / f"screen-{attempt:03d}.png"
            ppm = (args.out / f"screen-{attempt:03d}.ppm").resolve()
            if not screendump(connection, ppm):
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
        try:
            connection.command("quit", wait=5.0)
        except OSError as error:
            print(f"monitor quit failed: {error}", flush=True)
        connection.close()
        if guest.poll() is None:
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
