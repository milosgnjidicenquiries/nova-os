import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT / "installer/nova-firstboot.sh"
BASH = shutil.which("bash")

STUB = r'''
xdg-open() { printf 'open\t%s\n' "$*" >>"$MARKERS"; }
nova-notify() { printf 'notify\t%s\n' "$*" >>"$MARKERS"; return ${NOVA_NOTIFY_STATUS:-0}; }
export -f xdg-open nova-notify
/bin/bash "$1"
'''


@unittest.skipUnless(BASH, "Bash is required for the first-boot flow")
class FirstBootTests(unittest.TestCase):
    def run_firstboot(self, home, memtotal_kb=None, overrides=()):
        directory = Path(home)
        env = dict(os.environ, HOME=str(directory), XDG_STATE_HOME=str(directory / "state"),
                   MARKERS=str(directory / "markers"))
        if memtotal_kb is None:
            env["NOVA_MEMINFO"] = str(directory / "absent")
        else:
            fixture = directory / "meminfo"
            fixture.write_text(f"MemTotal:        {memtotal_kb} kB\nMemFree:          1234 kB\n", encoding="utf-8")
            env["NOVA_MEMINFO"] = fixture.as_posix()
        env.update(dict(pair.split("=", 1) for pair in overrides))
        result = subprocess.run([BASH, "-c", STUB, "nova-test", str(SCRIPT)],
                                env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        markers = directory / "markers"
        lines = markers.read_text(encoding="utf-8").splitlines() if markers.exists() else []
        return [line.split("\t", 1) for line in lines]

    def test_low_memory_notifies_instead_of_starting_a_browser(self):
        with tempfile.TemporaryDirectory() as home:
            calls = self.run_firstboot(home, 1006632)
            self.assertEqual([kind for kind, _ in calls], ["notify"])
            self.assertIn("dobrodošlica", calls[0][1])
            self.assertTrue((Path(home) / "state/nova/welcome-seen").is_file())

    def test_comfortable_memory_still_opens_the_welcome_page(self):
        with tempfile.TemporaryDirectory() as home:
            calls = self.run_firstboot(home, 4194304)
            self.assertEqual([kind for kind, _ in calls], ["open"])
            self.assertEqual(calls[0][1], "/usr/share/nova/welcome.html")

    def test_unreadable_meminfo_keeps_the_previous_behaviour(self):
        with tempfile.TemporaryDirectory() as home:
            self.assertEqual([kind for kind, _ in self.run_firstboot(home)], ["open"])

    def test_threshold_is_the_one_knob_a_2gb_machine_can_turn(self):
        with tempfile.TemporaryDirectory() as home:
            calls = self.run_firstboot(home, 1006632, ("NOVA_LOW_MEMORY_KB=500000",))
            self.assertEqual([kind for kind, _ in calls], ["open"])

    def test_welcome_runs_once_per_user(self):
        with tempfile.TemporaryDirectory() as home:
            first = self.run_firstboot(home, 4194304)
            self.assertEqual(self.run_firstboot(home, 4194304), first)

    def test_notification_failure_still_marks_the_session_seen(self):
        with tempfile.TemporaryDirectory() as home:
            calls = self.run_firstboot(home, 1006632, ("NOVA_NOTIFY_STATUS=1",))
            self.assertEqual([kind for kind, _ in calls], ["notify"])
            self.assertTrue((Path(home) / "state/nova/welcome-seen").is_file())


if __name__ == "__main__":
    unittest.main()
