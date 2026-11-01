"""Fixture-only tests: never inspect the Windows host or real PCI devices."""

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

PROJECT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("nova_hardware", PROJECT / "scripts/nova-hardware.py")
hardware = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(hardware)


class HardwareTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "proc").mkdir()
        (self.root / "sys/firmware").mkdir(parents=True)
        self.cpu("lm nx sse2 sse4_2")
        self.memory(4 * 1024 ** 2, 2 * 1024 ** 2)

    def cpu(self, flags):
        (self.root / "proc/cpuinfo").write_text(
            f"processor : 0\nmodel name : Fixture AMD64\nflags : {flags}\n\n"
            f"processor : 1\nmodel name : Fixture AMD64\nflags : {flags}\n", encoding="utf-8")

    def memory(self, total, available):
        (self.root / "proc/meminfo").write_text(
            f"MemTotal: {total} kB\nMemAvailable: {available} kB\n"
            "SwapTotal: 524288 kB\nSwapFree: 262144 kB\n", encoding="ascii")

    def test_supported_cpu_and_available_memory(self):
        info = hardware.diagnose(str(self.root))
        self.assertTrue(info["cpu"]["supported_amd64_cpu"])
        self.assertEqual(info["cpu"]["logical_cpus"], 2)
        self.assertIn("sse4_2", info["cpu"]["flags"])
        self.assertEqual(info["memory"]["total_bytes"], 4 * 1024 ** 3)
        self.assertEqual(info["memory"]["available_bytes"], 2 * 1024 ** 3)
        self.assertEqual(info["memory"]["swap_free_bytes"], 262144 * 1024)

    def test_missing_cpu_flags_and_low_ram(self):
        self.cpu("lm sse2")
        self.memory(768 * 1024, 128 * 1024)
        info = hardware.diagnose(str(self.root))
        self.assertFalse(info["cpu"]["supported_amd64_cpu"])
        self.assertFalse(info["cpu"]["required_flags"]["nx"])
        self.assertTrue(any("missing flags" in warning and "nx" in warning for warning in info["warnings"]))
        self.assertTrue(any("Low RAM" in warning for warning in info["warnings"]))
        self.assertTrue(any("Low available RAM" in warning for warning in info["warnings"]))

    def test_flags_must_be_available_on_all_processors(self):
        (self.root / "proc/cpuinfo").write_text(
            "processor: 0\nflags: lm nx sse2\n\nprocessor: 1\nflags: nx sse2\n", encoding="ascii")
        info = hardware.diagnose(str(self.root))
        self.assertFalse(info["cpu"]["supported_amd64_cpu"])
        self.assertNotIn("lm", info["cpu"]["flags"])
        self.assertIn("lm", info["cpu"]["flags_by_cpu"][0])

    def test_uefi_and_absent_efi(self):
        self.assertEqual(hardware.diagnose(str(self.root))["boot"]["mode"], "bios_or_unknown")
        (self.root / "sys/firmware/efi").mkdir()
        self.assertEqual(hardware.diagnose(str(self.root))["boot"]["mode"], "uefi")

    def test_missing_evidence_is_unknown_not_fabricated(self):
        (self.root / "proc/cpuinfo").unlink()
        (self.root / "proc/meminfo").unlink()
        (self.root / "sys/firmware").rmdir()
        info = hardware.diagnose(str(self.root))
        self.assertIsNone(info["cpu"]["supported_amd64_cpu"])
        self.assertIsNone(info["memory"]["available_bytes"])
        self.assertEqual(info["boot"]["mode"], "unknown")
        self.assertTrue(any("CPU information is missing" in warning for warning in info["warnings"]))

    def test_memfree_is_not_a_memavailable_substitute(self):
        (self.root / "proc/meminfo").write_text("MemTotal: 4000000 kB\nMemFree: 500000 kB\n", encoding="ascii")
        self.assertIsNone(hardware.diagnose(str(self.root))["memory"]["available_bytes"])

    def test_fixture_never_queries_host_even_on_linux(self):
        with mock.patch.object(hardware.platform, "system", return_value="Linux"), \
                mock.patch.object(hardware.shutil, "which", side_effect=AssertionError("Host lookup")), \
                mock.patch.object(hardware.subprocess, "run", side_effect=AssertionError("Host command")):
            self.assertEqual(hardware.diagnose(str(self.root))["pci"]["status"], "not_queried")

    def test_live_pci_command_and_timeout(self):
        completed = subprocess.CompletedProcess([], 0, "00:00.0 Device [1234:5678]\nKernel driver in use: example\n", "")
        with mock.patch.object(hardware.shutil, "which", return_value="/usr/bin/lspci"), \
                mock.patch.object(hardware.subprocess, "run", return_value=completed) as run:
            info = hardware.pci_evidence(True)
            self.assertEqual(info["status"], "ok")
            self.assertIn("[1234:5678]", info["listing"])
            run.assert_called_once_with(["/usr/bin/lspci", "-nnk"], capture_output=True, text=True,
                                        errors="replace", timeout=10, check=False)
        with mock.patch.object(hardware.shutil, "which", return_value="/usr/bin/lspci"), \
                mock.patch.object(hardware.subprocess, "run", side_effect=subprocess.TimeoutExpired("lspci", 10)):
            self.assertEqual(hardware.pci_evidence(True)["status"], "unavailable")

    def test_missing_lspci(self):
        with mock.patch.object(hardware.shutil, "which", return_value=None):
            self.assertIn("not installed", hardware.pci_evidence(True)["reason"])

    def test_cli_outputs_json(self):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            self.assertEqual(hardware.main(["--root", str(self.root)]), 0)
        self.assertEqual(json.loads(stream.getvalue())["root"], str(self.root))


if __name__ == "__main__":
    unittest.main()
