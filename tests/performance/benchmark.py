#!/usr/bin/env python3
"""Read-only Linux snapshot: real RAM, swap and zram, one five-second CPU window with
per-process usage, and per-process memory reported as both RSS and PSS."""

import argparse
import os
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
MEMORY_FIELDS = {"MemTotal", "MemAvailable"}
SWAP_FIELDS = {"SwapTotal", "SwapFree", "SwapCached"}
ZRAM_COUNTERS = ("disksize", "orig_data_size", "compr_data_size")


def read_memory(proc=Path("/proc")):
    values = {}
    for line in (proc / "meminfo").read_text(encoding="ascii").splitlines():
        key, separator, raw = line.partition(":")
        if separator and key in MEMORY_FIELDS:
            fields = raw.split()
            if len(fields) != 2 or fields[1] != "kB" or not fields[0].isdigit():
                raise ValueError(f"Malformed {key} in meminfo")
            values[key] = int(fields[0]) * 1024
    if not MEMORY_FIELDS <= values.keys():
        raise ValueError("MemTotal and MemAvailable are required; no estimated RAM values are used")
    return {"total_bytes": values["MemTotal"], "available_bytes": values["MemAvailable"]}


def swap_fields(path=Path("/proc/meminfo")):
    values = {}
    for line in path.read_text(encoding="ascii").splitlines():
        key, separator, raw = line.partition(":")
        if separator and key in SWAP_FIELDS:
            fields = raw.split()
            if len(fields) != 2 or fields[1] != "kB" or not fields[0].isdigit():
                raise ValueError(f"Malformed {key} in {path.name}")
            values[key] = int(fields[0]) * 1024
    return values


def read_swap(proc=Path("/proc"), sys_root=Path("/sys/block")):
    """Swap the kernel accounts for, each device, and zram's measured compression ratio."""
    fields = swap_fields(proc / "meminfo")
    devices = []
    for line in (proc / "swaps").read_text(encoding="ascii").splitlines()[1:]:
        parts = line.split()
        if len(parts) < 4 or not parts[2].isdigit() or not parts[3].isdigit():
            raise ValueError(f"Malformed swaps line: {line}")
        device = {"filename": parts[0], "type": parts[1],
                  "size_bytes": int(parts[2]) * 1024, "used_bytes": int(parts[3]) * 1024}
        if parts[0].startswith("/dev/zram"):
            counters = {}
            for name in ZRAM_COUNTERS:
                entry = sys_root / Path(parts[0]).name / name
                try:
                    text = entry.read_text(encoding="ascii").strip()
                except OSError:
                    continue
                if text.isdigit():
                    counters[name + "_bytes"] = int(text)
            if counters.get("compr_data_size_bytes") and counters.get("orig_data_size_bytes"):
                counters["compression_ratio"] = round(counters["orig_data_size_bytes"]
                                                      / counters["compr_data_size_bytes"], 2)
            device["zram"] = counters
        devices.append(device)
    return {"fields": fields, "devices": devices}


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


def process_memory(proc=Path("/proc")):
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
        processes.append({"pid": int(directory.name), "name": fields.get("Name"),
                         "rss_bytes": kilo(fields.get("VmRSS"), f"VmRSS for PID {directory.name}"),
                         "pss_bytes": process_pss(directory)})
    processes.sort(key=lambda item: (item["rss_bytes"] is None, -(item["rss_bytes"] or 0), item["pid"]))
    return {"processes": processes, "skipped_races_or_permissions": skipped,
            "note": "RSS is a non-atomic snapshot and counts shared pages in every process that maps "
                    "them; PSS splits them, so PSS is the honest cost of removing a process. "
                    "Missing values (for example a kernel thread) are reported as null."}


def kilo(value, label):
    if value is None:
        return None
    parts = value.split()
    if len(parts) != 2 or not parts[0].isdigit() or parts[1] != "kB":
        raise ValueError(f"Malformed {label}")
    return int(parts[0]) * 1024


def process_pss(directory):
    try:
        text = (directory / "smaps_rollup").read_text(encoding="ascii", errors="replace")
    except OSError as error:
        # Unreadable rollup is normal without root or for a process that just exited.
        if error.errno in {errno.ENOENT, errno.ESRCH, errno.EACCES, errno.EPERM}:
            return None
        raise
    for line in text.splitlines():
        if line.startswith("Pss:"):
            return kilo(line.partition(":")[2], f"Pss for PID {directory.name}")
    return None


def read_cpu_ticks(proc=Path("/proc")):
    """Scheduling ticks consumed per process, read twice around a window."""
    ticks = {}
    for directory in proc.iterdir():
        if not directory.name.isdecimal():
            continue
        try:
            text = (directory / "stat").read_text(encoding="utf-8", errors="replace")
        except OSError as error:
            if error.errno in {errno.ENOENT, errno.ESRCH, errno.EACCES, errno.EPERM}:
                continue
            raise
        # The comm field can contain spaces and parentheses, so fields after the last
        # closing parenthesis are the ones that can be counted on.
        fields = text.rpartition(")")[2].split()
        if len(fields) < 13:
            continue
        try:
            ticks[int(directory.name)] = int(fields[11]) + int(fields[12])
        except ValueError:
            continue
    return ticks


def clock_ticks_per_second():
    getter = getattr(os, "sysconf", None)
    if getter is None:
        raise ValueError("SC_CLK_TCK is unavailable on this platform")
    try:
        value = getter("SC_CLK_TCK")
    except (ValueError, KeyError, OSError) as error:
        raise ValueError(f"SC_CLK_TCK is unavailable: {error}")
    if not isinstance(value, int) or value <= 0:
        raise ValueError("SC_CLK_TCK is not a positive integer")
    return value


def cpu_report(before, after, elapsed, ticks_per_second):
    if elapsed <= 0 or ticks_per_second <= 0:
        raise ValueError("CPU window or clock resolution is unusable")
    rows = []
    baseline_missing = 0
    for pid, value in after.items():
        if pid not in before:
            baseline_missing += 1  # Started during the window; there is nothing to measure.
            continue
        delta = value - before[pid]
        if delta < 0:
            raise ValueError(f"PID {pid} scheduling counters decreased during the window")
        rows.append({"pid": pid, "cpu_percent_of_one_core": round(100.0 * delta / ticks_per_second / elapsed, 2)})
    rows.sort(key=lambda row: (-row["cpu_percent_of_one_core"], row["pid"]))
    return {"window_seconds": round(elapsed, 3), "clock_ticks_per_second": ticks_per_second,
            "processes_started_during_window": baseline_missing,
            "total_percent_of_one_core": round(sum(row["cpu_percent_of_one_core"] for row in rows), 2),
            "top": rows[:20]}


def memory_rollup(snapshot):
    """Measured per-process memory grouped by the name the kernel reports."""
    groups = {}
    for item in snapshot.get("processes", []):
        name = item["name"] or "unknown"
        group = groups.setdefault(name, {"name": name, "processes": 0, "rss_bytes": 0, "pss_bytes": 0})
        group["processes"] += 1
        group["rss_bytes"] += item["rss_bytes"] or 0
        group["pss_bytes"] += item["pss_bytes"] or 0
    ordered = sorted(groups.values(), key=lambda group: (-group["pss_bytes"], -group["rss_bytes"], group["name"]))
    return {"groups": ordered,
            "total_rss_bytes": sum(group["rss_bytes"] for group in ordered),
            "total_pss_bytes": sum(group["pss_bytes"] for group in ordered)}


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
    proc = Path("/proc")
    result = {"recorded_at": datetime.now(timezone.utc).isoformat(), "errors": {}}
    try:
        ticks_before = read_cpu_ticks(proc)
    except (OSError, ValueError) as error:
        ticks_before = None
        result["errors"]["process_cpu"] = str(error)
    window_start = time.monotonic()
    for key, reader in (("memory", read_memory), ("cpu", sample_cpu),
                        ("processes", process_memory), ("swap", read_swap)):
        try:
            result[key] = reader()
        except (OSError, ValueError) as error:
            result[key] = None
            result["errors"][key] = str(error)
    result["memory_rollup"] = memory_rollup(result["processes"]) if result["processes"] else None
    result["process_cpu"] = None
    if ticks_before is not None:
        try:
            result["process_cpu"] = cpu_report(ticks_before, read_cpu_ticks(proc),
                                               time.monotonic() - window_start, clock_ticks_per_second())
        except (OSError, ValueError) as error:
            result["process_cpu"] = None
            result["errors"]["process_cpu"] = str(error)
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
    return 1 if result["errors"] or (result["cpu"] or {}).get("error") else 0


if __name__ == "__main__":
    raise SystemExit(main())
