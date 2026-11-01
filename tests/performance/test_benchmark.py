"""Test real parsers/deltas against fixtures, not fabricated benchmark results."""

import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location("nova_benchmark", Path(__file__).with_name("benchmark.py"))
benchmark = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(benchmark)


class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.proc = Path(temporary.name)

    def test_real_memory_fields_and_units(self):
        (self.proc / "meminfo").write_text("MemTotal: 8192000 kB\nMemAvailable: 2048000 kB\nMemFree: 123 kB\n", encoding="ascii")
        self.assertEqual(benchmark.read_memory(self.proc),
                         {"total_bytes": 8192000 * 1024, "available_bytes": 2048000 * 1024})

    def test_missing_or_malformed_memavailable_fails_without_estimate(self):
        for text in ("MemTotal: 123 kB\nMemFree: 99 kB\n", "MemTotal: 123 kB\nMemAvailable: unknown kB\n"):
            (self.proc / "meminfo").write_text(text, encoding="ascii")
            with self.assertRaises(ValueError):
                benchmark.read_memory(self.proc)

    def test_cpu_excludes_double_counted_guest(self):
        (self.proc / "stat").write_text("cpu 100 20 30 200 10 5 5 2 80 10\ncpu0 1 1 1 1\n", encoding="ascii")
        self.assertEqual(benchmark.read_cpu_counters(self.proc), [100, 20, 30, 200, 10, 5, 5, 2])
        result = benchmark.cpu_delta([100, 0, 50, 100, 10, 0, 0, 0],
                                     [130, 0, 70, 145, 15, 0, 0, 0], 5.01)
        self.assertEqual(result["total_ticks_delta"], 100)
        self.assertEqual(result["idle_ticks_delta"], 50)
        self.assertEqual(result["busy_percent"], 50)
        self.assertEqual(result["sample_seconds"], 5.01)

    def test_reset_or_static_cpu_counters_are_not_fake_zero_usage(self):
        for before, after in (([1, 2, 3, 4], [1, 2, 3, 4]), ([2, 2, 2, 2], [1, 2, 2, 3])):
            result = benchmark.cpu_delta(before, after, 5)
            self.assertIsNone(result["busy_percent"])
            self.assertIn("error", result)

    def test_sampling_requests_five_seconds(self):
        with mock.patch.object(benchmark, "read_cpu_counters", side_effect=([10, 0, 10, 20], [20, 0, 20, 40])), \
                mock.patch.object(benchmark.time, "sleep") as sleep, \
                mock.patch.object(benchmark.time, "monotonic", side_effect=(100.0, 105.1)):
            result = benchmark.sample_cpu(self.proc)
        sleep.assert_called_once_with(5.0)
        self.assertAlmostEqual(result["sample_seconds"], 5.1)
        self.assertEqual(result["busy_percent"], 50)

    def test_process_rss_and_exit_race(self):
        for pid, status in (("10", "Name:\tsmall\nVmRSS:\t100 kB\n"),
                            ("11", "Name:\tlarge\nVmRSS:\t900 kB\n"),
                            ("12", "Name:\tkernel-thread\n")):
            directory = self.proc / pid
            directory.mkdir()
            (directory / "status").write_text(status, encoding="ascii")
        (self.proc / "99").mkdir()  # Process disappeared before its status was opened.
        (self.proc / "not-a-pid").mkdir()
        result = benchmark.process_rss(self.proc)
        self.assertEqual([item["pid"] for item in result["processes"]], [11, 10, 12])
        self.assertEqual(result["processes"][0]["rss_bytes"], 900 * 1024)
        self.assertIsNone(result["processes"][2]["rss_bytes"])
        self.assertEqual(result["skipped_races_or_permissions"], 1)

    def test_unexpected_io_error_not_silently_skipped(self):
        (self.proc / "10").mkdir()
        with mock.patch.object(Path, "read_text", side_effect=OSError(5, "Input/output error")), \
                self.assertRaises(OSError):
            benchmark.process_rss(self.proc)

    def test_process_permissions_are_reported_as_skipped(self):
        (self.proc / "10").mkdir()
        with mock.patch.object(Path, "read_text", side_effect=PermissionError(13, "Permission denied")):
            result = benchmark.process_rss(self.proc)
        self.assertEqual(result["processes"], [])
        self.assertEqual(result["skipped_races_or_permissions"], 1)

    def test_boot_missing_tool_and_timeout(self):
        with mock.patch.object(benchmark.shutil, "which", return_value=None):
            self.assertEqual(benchmark.boot_timing()["status"], "unavailable")
        with mock.patch.object(benchmark.shutil, "which", return_value="/mock/systemd-analyze"), \
                mock.patch.object(benchmark.subprocess, "run", side_effect=subprocess.TimeoutExpired("systemd-analyze", 15)):
            self.assertIn("15 seconds", benchmark.boot_timing()["reason"])

    def test_boot_preserves_actual_tool_output(self):
        completed = subprocess.CompletedProcess([], 0, "Startup finished in 2.100s (kernel) + 4.200s (userspace) = 6.300s\n", "")
        with mock.patch.object(benchmark.shutil, "which", return_value="/mock/systemd-analyze"), \
                mock.patch.object(benchmark.subprocess, "run", return_value=completed) as run:
            self.assertEqual(benchmark.boot_timing()["output"], completed.stdout.strip())
            self.assertEqual(run.call_args.kwargs["timeout"], 15)

    def test_missing_metrics_are_null_with_errors(self):
        with mock.patch.object(benchmark.platform, "system", return_value="Linux"), \
                mock.patch.object(benchmark, "read_memory", side_effect=ValueError("Missing MemAvailable")), \
                mock.patch.object(benchmark, "sample_cpu", side_effect=FileNotFoundError("Missing proc/stat")), \
                mock.patch.object(benchmark, "process_rss", return_value={"processes": []}), \
                mock.patch.object(benchmark, "boot_timing", return_value={"status": "unavailable"}):
            result = benchmark.collect()
        self.assertIsNone(result["memory"])
        self.assertIsNone(result["cpu"])
        self.assertEqual(set(result["errors"]), {"memory", "cpu"})

    def test_nonlinux_rejected_before_proc_reads(self):
        with mock.patch.object(benchmark.platform, "system", return_value="Windows"), \
                mock.patch.object(benchmark, "read_memory") as reader, self.assertRaises(RuntimeError):
            benchmark.collect()
        reader.assert_not_called()

    def test_output_only_when_requested(self):
        output = self.proc / "requested.json"
        # Verify serialization independently; these are test observations, not shipped metrics.
        observation = {"errors": {}, "cpu": {"busy_percent": 50}, "memory": {"available_bytes": 1024}}
        with mock.patch.object(benchmark, "collect", return_value=observation):
            self.assertEqual(benchmark.main(["--output", str(output)]), 0)
        self.assertEqual(json.loads(output.read_text(encoding="utf-8")), observation)


if __name__ == "__main__":
    unittest.main()
