"""Test real parsers/deltas against fixtures, not fabricated benchmark results."""

import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import types
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

    def test_process_memory_and_exit_race(self):
        for pid, status in (("10", "Name:\tsmall\nVmRSS:\t100 kB\n"),
                            ("11", "Name:\tlarge\nVmRSS:\t900 kB\n"),
                            ("12", "Name:\tkernel-thread\n")):
            directory = self.proc / pid
            directory.mkdir()
            (directory / "status").write_text(status, encoding="ascii")
        (self.proc / "99").mkdir()  # Process disappeared before its status was opened.
        (self.proc / "not-a-pid").mkdir()
        result = benchmark.process_memory(self.proc)
        self.assertEqual([item["pid"] for item in result["processes"]], [11, 10, 12])
        self.assertEqual(result["processes"][0]["rss_bytes"], 900 * 1024)
        self.assertIsNone(result["processes"][2]["rss_bytes"])
        self.assertEqual(result["skipped_races_or_permissions"], 1)

    def test_unexpected_io_error_not_silently_skipped(self):
        (self.proc / "10").mkdir()
        with mock.patch.object(Path, "read_text", side_effect=OSError(5, "Input/output error")), \
                self.assertRaises(OSError):
            benchmark.process_memory(self.proc)

    def test_process_permissions_are_reported_as_skipped(self):
        (self.proc / "10").mkdir()
        with mock.patch.object(Path, "read_text", side_effect=PermissionError(13, "Permission denied")):
            result = benchmark.process_memory(self.proc)
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
                mock.patch.object(benchmark, "read_swap", side_effect=ValueError("Malformed swaps line")), \
                mock.patch.object(benchmark, "read_cpu_ticks", side_effect=OSError("proc vanished")), \
                mock.patch.object(benchmark, "process_memory", return_value={"processes": []}), \
                mock.patch.object(benchmark, "boot_timing", return_value={"status": "unavailable"}):
            result = benchmark.collect()
        self.assertIsNone(result["memory"])
        self.assertIsNone(result["cpu"])
        self.assertIsNone(result["swap"])
        self.assertIsNone(result["process_cpu"])
        self.assertEqual(set(result["errors"]), {"memory", "cpu", "swap", "process_cpu"})

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


class MemoryBudgetTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.proc = Path(temporary.name)
        self.sys = self.proc / "sys-block"

    def test_swap_devices_and_measured_zram_ratio(self):
        (self.proc / "meminfo").write_text(
            "MemTotal: 1024000 kB\nSwapTotal: 512000 kB\nSwapFree: 400000 kB\nSwapCached: 100 kB\n",
            encoding="ascii")
        (self.proc / "swaps").write_text(
            "Filename\t\t\t\tType\t\tSize\t\tUsed\t\tPriority\n"
            "/dev/zram0                partition\t512000\t\t112000\t\t100\n", encoding="ascii")
        device = self.sys / "zram0"
        device.mkdir(parents=True)
        for name, value in (("disksize", "524288000"), ("orig_data_size", "900000"),
                            ("compr_data_size", "300000")):
            (device / name).write_text(value, encoding="ascii")
        result = benchmark.read_swap(self.proc, self.sys)
        self.assertEqual(result["fields"]["SwapTotal"], 512000 * 1024)
        self.assertEqual(result["devices"][0]["used_bytes"], 112000 * 1024)
        self.assertEqual(result["devices"][0]["zram"]["compression_ratio"], 3.0)

    def test_missing_swap_counters_are_omitted_not_zeroed(self):
        (self.proc / "meminfo").write_text("MemTotal: 1024000 kB\n", encoding="ascii")
        (self.proc / "swaps").write_text("Filename\tType\tSize\tUsed\tPriority\n", encoding="ascii")
        result = benchmark.read_swap(self.proc, self.sys)
        self.assertEqual(result["devices"], [])
        self.assertEqual(result["fields"], {})

    def test_malformed_swap_line_is_an_error(self):
        (self.proc / "meminfo").write_text("MemTotal: 1024000 kB\n", encoding="ascii")
        (self.proc / "swaps").write_text("Filename\tType\tSize\tUsed\tPriority\n/dev/zram0 partition\tlots\tnope\t100\n",
                                         encoding="ascii")
        with self.assertRaises(ValueError):
            benchmark.read_swap(self.proc, self.sys)

    def test_pss_is_read_when_available(self):
        directory = self.proc / "42"
        directory.mkdir()
        (directory / "status").write_text("Name:\txfce4-panel\nVmRSS:\t60000 kB\n", encoding="ascii")
        (directory / "smaps_rollup").write_text("Rss:\t  60000 kB\nPss:\t  21000 kB\n", encoding="ascii")
        self.assertEqual(benchmark.process_memory(self.proc)["processes"][0]["pss_bytes"], 21000 * 1024)

    def test_pss_absence_is_null_and_a_malformed_line_is_an_error(self):
        directory = self.proc / "42"
        directory.mkdir()
        self.assertIsNone(benchmark.process_pss(directory))  # No smaps_rollup at all.
        (directory / "smaps_rollup").write_text("Rss:\t5 kB\n", encoding="ascii")
        self.assertIsNone(benchmark.process_pss(directory))  # A rollup without Pss.
        (directory / "smaps_rollup").write_text("Pss:\tnot-a-number kB\n", encoding="ascii")
        with self.assertRaises(ValueError):
            benchmark.process_pss(directory)
        with mock.patch.object(benchmark.Path, "read_text", side_effect=PermissionError(13, "denied")):
            self.assertIsNone(benchmark.process_pss(directory))

    def test_ticks_ignore_spaces_and_parentheses_in_comm(self):
        directory = self.proc / "7"
        directory.mkdir()
        fields = " ".join(["S"] + ["0"] * 10 + ["50", "25"] + ["0"] * 30)
        (directory / "stat").write_text(f"7 (weird (name) helper) {fields}\n", encoding="ascii")
        (self.proc / "8").mkdir()  # No stat file: the process disappeared.
        self.assertEqual(benchmark.read_cpu_ticks(self.proc), {7: 75})

    def test_cpu_report_measures_the_window_it_was_given(self):
        result = benchmark.cpu_report({1: 100, 2: 500}, {1: 350, 2: 500, 3: 10}, 5.0, 100)
        self.assertEqual(result["window_seconds"], 5.0)
        self.assertEqual(result["top"][0], {"pid": 1, "cpu_percent_of_one_core": 50.0})
        self.assertEqual(result["processes_started_during_window"], 1)
        self.assertEqual(result["total_percent_of_one_core"], 50.0)

    def test_cpu_report_rejects_reversed_counters_and_empty_window(self):
        with self.assertRaises(ValueError):
            benchmark.cpu_report({1: 100}, {1: 90}, 5.0, 100)
        with self.assertRaises(ValueError):
            benchmark.cpu_report({1: 1}, {1: 2}, 0, 100)
        with self.assertRaises(ValueError):
            benchmark.cpu_report({1: 1}, {1: 2}, 5.0, 0)

    def test_rollup_groups_by_kernel_name_and_keeps_both_totals(self):
        snapshot = {"processes": [
            {"pid": 1, "name": "firefox", "rss_bytes": 300 * 1024, "pss_bytes": 200 * 1024},
            {"pid": 2, "name": "firefox", "rss_bytes": 200 * 1024, "pss_bytes": 150 * 1024},
            {"pid": 3, "name": "xfdesktop", "rss_bytes": 60 * 1024, "pss_bytes": 40 * 1024},
            {"pid": 4, "name": None, "rss_bytes": None, "pss_bytes": None}]}
        result = benchmark.memory_rollup(snapshot)
        self.assertEqual([group["name"] for group in result["groups"]], ["firefox", "xfdesktop", "unknown"])
        self.assertEqual(result["groups"][0]["processes"], 2)
        self.assertEqual(result["total_rss_bytes"], 560 * 1024)
        self.assertEqual(result["total_pss_bytes"], 390 * 1024)

    def test_clock_resolution_failure_is_not_a_fake_percentage(self):
        with mock.patch.object(benchmark, "os", types.SimpleNamespace()):
            with self.assertRaises(ValueError):
                benchmark.clock_ticks_per_second()
        with mock.patch.object(benchmark, "os", types.SimpleNamespace(sysconf=lambda name: 0)):
            with self.assertRaises(ValueError):
                benchmark.clock_ticks_per_second()

    def test_collect_reports_both_new_sections(self):
        snapshot = {"processes": [{"pid": 1, "name": "firefox", "rss_bytes": 10, "pss_bytes": 5}]}
        with mock.patch.object(benchmark.platform, "system", return_value="Linux"), \
                mock.patch.object(benchmark, "read_memory", return_value={"total_bytes": 1}), \
                mock.patch.object(benchmark, "sample_cpu", return_value={"busy_percent": 1.0}), \
                mock.patch.object(benchmark, "process_memory", return_value=snapshot), \
                mock.patch.object(benchmark, "read_swap", return_value={"fields": {}, "devices": []}), \
                mock.patch.object(benchmark, "read_cpu_ticks", side_effect=({1: 0}, {1: 100})), \
                mock.patch.object(benchmark, "clock_ticks_per_second", return_value=100), \
                mock.patch.object(benchmark.time, "monotonic", side_effect=(100.0, 105.0)), \
                mock.patch.object(benchmark, "boot_timing", return_value={"status": "unavailable"}):
            result = benchmark.collect()
        self.assertEqual(result["memory_rollup"]["total_pss_bytes"], 5)
        self.assertEqual(result["process_cpu"]["top"], [{"pid": 1, "cpu_percent_of_one_core": 20.0}])
        self.assertEqual(result["errors"], {})


if __name__ == "__main__":
    unittest.main()
