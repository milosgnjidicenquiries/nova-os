#!/usr/bin/env python3
"""Read-only Linux snapshot: real RAM, a five-second aggregate CPU sample, and process RSS."""

import argparse
from datetime import datetime, timezone
import errno
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time

SAMPLE_SECONDS = 5.0


def read_memory(proc=Path("/proc")):
    values = {}
    for line in (proc / "meminfo").read_text(encoding="ascii").splitlines():
        key, separator, raw = line.partition(":")
        if separator and key in {"MemTotal", "MemAvailable"}:
            fields = raw.split()
            if len(fields) != 2 or fields[1] != "kB" or not fields[0].isdigit():
                raise ValueError(f"Malformed {key} in meminfo")
            values[key] = int(fields[0]) * 1024
    if "MemTotal" not in values or "MemAvailable" not in values:
        raise ValueError("MemTotal and MemAvailable are required; no estimated RAM values are used")
    return {"total_bytes": values["MemTotal"], "available_bytes": values["MemAvailable"]}


def read_cpu_counters(proc=Path("/proc")):
    with (proc / "stat").open(encoding="ascii") as stream:
        fields = stream.readline().split()
    if not fields or fields[0] != "cpu" or len(fields) < 5:
        raise ValueError("Missing aggregate cpu line in /proc/stat")
    counters = [int(value) for value in fields[1:9]]
    if any(value < 0 for value in counters):
        raise ValueError("Negative CPU counters")
    # guest and guest_nice (fields 9/10) are already included in user/nice.
    return counters


def cpu_delta(before, after, elapsed):
    if len(before) != len(after):
        raise ValueError("CPU counter fields changed during sampling")
    deltas = [end - start for start, end in zip(before, after)]
    total = sum(deltas)
    idle = deltas[3] + (deltas[4] if len(deltas) > 4 else 0)
    if any(value < 0 for value in deltas) or total <= 0:
        return {"sample_seconds": elapsed, "busy_percent": None,
                "error": "CPU counters reset, decreased, or did not advance"}
    return {"sample_seconds": elapsed, "busy_percent": 100.0 * (total - idle) / total,
            "total_ticks_delta": total, "idle_ticks_delta": idle}


def sample_cpu(proc=Path("/proc")):
    before = read_cpu_counters(proc)
    start = time.monotonic()
    time.sleep(SAMPLE_SECONDS)
    after = read_cpu_counters(proc)
    return cpu_delta(before, after, time.monotonic() - start)


def process_rss(proc=Path("/proc")):
    processes = []
    skipped = 0
    for directory in proc.iterdir():
        if not directory.name.isdecimal():
            continue
        try:
            text = (directory / "status").read_text(encoding="utf-8", errors="replace")
        except OSError as error:
            if error.errno in {errno.ENOENT, errno.ESRCH, errno.EACCES, errno.EPERM}:
                skipped += 1  # Exited processes and unreadable status files are normal.
                continue
            raise
        fields = {}
        for line in text.splitlines():
            key, separator, value = line.partition(":")
            if separator:
                fields[key] = value.strip()
        rss = None
        if "VmRSS" in fields:
            parts = fields["VmRSS"].split()
            if len(parts) != 2 or not parts[0].isdigit() or parts[1] != "kB":
                raise ValueError(f"Malformed VmRSS for PID {directory.name}")
            rss = int(parts[0]) * 1024
        processes.append({"pid": int(directory.name), "name": fields.get("Name"), "rss_bytes": rss})
    processes.sort(key=lambda item: (item["rss_bytes"] is None, -(item["rss_bytes"] or 0), item["pid"]))
    return {"processes": processes, "skipped_races_or_permissions": skipped,
            "note": "RSS is a non-atomic snapshot; shared pages may be counted in multiple processes. "
                    "Missing VmRSS (for example, a kernel thread) is reported as null."}


def boot_timing():
    executable = shutil.which("systemd-analyze")
    if not executable:
        return {"status": "unavailable", "reason": "systemd-analyze is not installed"}
    try:
        result = subprocess.run([executable, "time"], capture_output=True, text=True,
                                errors="replace", timeout=15, check=False)
    except subprocess.TimeoutExpired:
        return {"status": "unavailable", "reason": "systemd-analyze exceeded 15 seconds"}
    except OSError as error:
        return {"status": "unavailable", "reason": str(error)}
    if result.returncode:
        return {"status": "unavailable", "reason": result.stderr.strip() or f"Exit {result.returncode}"}
    return {"status": "ok", "output": result.stdout.strip()}


def collect():
    if platform.system() != "Linux":
        raise RuntimeError("This benchmark requires a live Linux /proc filesystem")
    result = {"recorded_at": datetime.now(timezone.utc).isoformat(), "errors": {}}
    for key, reader in (("memory", read_memory), ("cpu", sample_cpu), ("rss", process_rss)):
        try:
            result[key] = reader()
        except (OSError, ValueError) as error:
            result[key] = None
            result["errors"][key] = str(error)
    result["boot"] = boot_timing()
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Write JSON to this file (no other files are changed)")
    args = parser.parse_args(argv)
    try:
        result = collect()
        payload = json.dumps(result, indent=2) + "\n"
        if args.output:
            args.output.write_text(payload, encoding="utf-8")
        else:
            sys.stdout.write(payload)
    except (OSError, RuntimeError) as error:
        print(f"benchmark: {error}", file=sys.stderr)
        return 1
    return 1 if result["errors"] or result["cpu"].get("error") else 0


if __name__ == "__main__":
    raise SystemExit(main())
