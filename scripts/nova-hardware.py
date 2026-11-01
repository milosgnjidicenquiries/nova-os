#!/usr/bin/env python3
"""Read-only hardware evidence for the planned Linux Mint/noble amd64 target."""

import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess

REQUIRED_FLAGS = {"lm", "nx", "sse2"}
GIB = 1024 ** 3


def parse_cpuinfo(text):
    processors = []
    for block in text.strip().split("\n\n"):
        fields = {}
        for line in block.splitlines():
            key, separator, value = line.partition(":")
            if separator:
                fields[key.strip()] = value.strip()
        if fields:
            processors.append(fields)
    flag_sets = [set(cpu.get("flags", "").split()) for cpu in processors]
    common = set.intersection(*flag_sets) if flag_sets else set()
    return {
        "logical_cpus": len(processors) if processors else None,
        "models": sorted({cpu["model name"] for cpu in processors if "model name" in cpu}),
        "flags": sorted(common),
        "flags_by_cpu": [sorted(flags) for flags in flag_sets],
        "required_flags": {flag: flag in common for flag in sorted(REQUIRED_FLAGS)},
        "supported_amd64_cpu": REQUIRED_FLAGS <= common if processors else None,
    }


def parse_meminfo(text):
    values = {}
    for line in text.splitlines():
        key, separator, raw = line.partition(":")
        if separator and key in {"MemTotal", "MemAvailable", "SwapTotal", "SwapFree"}:
            fields = raw.split()
            if len(fields) == 2 and fields[0].isdigit() and fields[1] == "kB":
                values[key] = int(fields[0]) * 1024
    return {key: values.get(source) for key, source in (
        ("total_bytes", "MemTotal"), ("available_bytes", "MemAvailable"),
        ("swap_total_bytes", "SwapTotal"), ("swap_free_bytes", "SwapFree"),
    )}


def read_evidence(path, warnings):
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError as error:
        warnings.append(f"Cannot read {path}: {error.strerror or str(error)}")
        return ""


def pci_evidence(live):
    if not live:
        return {"status": "not_queried", "reason": "Fixture or non-Linux mode; no host devices queried."}
    executable = shutil.which("lspci")
    if not executable:
        return {"status": "unavailable", "reason": "lspci is not installed; PCI devices and drivers are unknown."}
    try:
        result = subprocess.run([executable, "-nnk"], capture_output=True, text=True,
                                errors="replace", timeout=10, check=False)
    except subprocess.TimeoutExpired:
        return {"status": "unavailable", "reason": "lspci exceeded the 10-second timeout."}
    except OSError as error:
        return {"status": "unavailable", "reason": f"Cannot execute lspci: {error}"}
    if result.returncode:
        return {"status": "unavailable", "reason": result.stderr.strip() or f"lspci exited {result.returncode}"}
    if not result.stdout.strip():
        return {"status": "unavailable", "reason": "lspci returned no PCI devices."}
    return {"status": "ok", "listing": result.stdout.rstrip()}


def diagnose(root="/"):
    # Test roots must never trigger host commands, even if they resolve to '/'.
    live = os.fspath(root) == "/" and platform.system() == "Linux"
    base = Path(root)
    warnings = []
    if os.fspath(root) == "/" and not live:
        warnings.append("Live diagnostics require Linux; /proc and /sys evidence may be unavailable.")
    cpu = parse_cpuinfo(read_evidence(base / "proc/cpuinfo", warnings))
    memory = parse_meminfo(read_evidence(base / "proc/meminfo", warnings))
    if cpu["logical_cpus"] is None:
        warnings.append("CPU information is missing; amd64 support cannot be established.")
    else:
        missing = REQUIRED_FLAGS - set(cpu["flags"])
        if missing:
            warnings.append("CPU support is not established for the planned amd64 OS: "
                            "missing flags on one or more CPUs: " + ", ".join(sorted(missing)) + ".")
    total = memory["total_bytes"]
    available = memory["available_bytes"]
    if total is None:
        warnings.append("MemTotal is missing; installed RAM is unknown.")
    elif total < 2 * GIB:
        warnings.append("Low RAM: below 2 GiB. Legacy Windows apps may need at least 1 GiB "
                        "for the app alone; the OS and modern apps need additional memory.")
    if available is None:
        warnings.append("MemAvailable is missing; available RAM is unknown (not estimated from MemFree).")
    elif available < 512 * 1024 ** 2:
        warnings.append("Low available RAM: less than 512 MiB; close applications before heavy workloads.")
    firmware = base / "sys/firmware"
    if (firmware / "efi").is_dir():
        boot = {"mode": "uefi", "evidence": "sys/firmware/efi exists"}
    elif firmware.is_dir():
        boot = {"mode": "bios_or_unknown", "evidence": "sys/firmware/efi is absent"}
    else:
        boot = {"mode": "unknown", "evidence": "sys/firmware is unavailable"}
        warnings.append("Firmware information is missing; boot mode cannot be determined.")
    pci = pci_evidence(live)
    if pci["status"] != "ok":
        warnings.append(pci["reason"])
    return {
        "target": "Linux Mint XFCE, Ubuntu noble base, amd64 (planned)",
        "root": os.fspath(root), "cpu": cpu, "memory": memory, "boot": boot,
        "pci": pci, "warnings": warnings,
        "limitations": ["PCI identification does not establish graphics acceleration or Vulkan support.",
                        "CPU flags do not guarantee application, driver, or anti-cheat compatibility."],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="/", help="Fixture root containing proc/ and sys/; never probes host PCI")
    args = parser.parse_args(argv)
    print(json.dumps(diagnose(args.root), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
