"""Validate user actions and paths with mocked tools; never install packages or run Wine."""

import contextlib
import fnmatch
import glob
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

PROJECT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("nova_compat", PROJECT / "compatibility/nova-compat.py")
compat = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(compat)


class CompatibilityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        helper = self.home / "nova-install-component"
        helper.write_text("fixture helper; never executed", encoding="ascii")
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(compat.os, "geteuid", return_value=1000, create=True).start()
        mock.patch.object(compat, "INSTALL_HELPER", str(helper)).start()
        mock.patch.object(compat, "tool", side_effect=lambda name: f"/mock/{name}").start()
        self.run = mock.patch.object(compat.subprocess, "run",
                                     return_value=subprocess.CompletedProcess([], 0, "", "")).start()

    def prefix(self, name="legacy"):
        path = compat.prefix_path(name, self.home)
        path.mkdir(parents=True)
        (path / "system.reg").write_text("fixture", encoding="ascii")
        return path

    def test_allowed_names(self):
        for name in ("a", "Legacy_32", "game-64", "A" * 64):
            self.assertEqual(compat.validate_name(name), name)

    def test_traversal_absolute_and_invalid_names(self):
        for name in ("", ".", "..", "../escape", "a/b", "a\\b", "/tmp/prefix", "C:\\prefix",
                     "-option", "with space", "name;command", "a" * 65, "naïve", "name\n"):
            with self.subTest(name=name), self.assertRaises(compat.CompatError):
                compat.prefix_path(name, self.home)
        self.run.assert_not_called()

    def test_component_allowlist(self):
        for component in compat.COMPONENTS:
            self.assertEqual(compat.validate_component(component), component)
        for component in ("bash", "wine64;touch /tmp/oops", "../wine64", "WINE64"):
            with self.assertRaises(compat.CompatError):
                compat.install_component(component, confirmed=True)
        self.run.assert_not_called()

    def test_no_install_without_confirmation(self):
        for component in compat.COMPONENTS:
            with self.assertRaises(compat.CompatError):
                compat.install_component(component)
        self.run.assert_not_called()

    def test_privileged_installs_only_fixed_pkexec_helper(self):
        for component in ("wine64", "wine32", "steam"):
            self.run.reset_mock()
            compat.install_component(component, confirmed=True)
            command = self.run.call_args.args[0]
            self.assertEqual(command, ["/mock/pkexec", compat.INSTALL_HELPER, component])
            self.assertNotIn("shell", self.run.call_args.kwargs)
            self.assertGreater(self.run.call_args.kwargs["timeout"], 0)

    def test_bottles_only_uses_existing_official_user_remote(self):
        self.run.return_value = subprocess.CompletedProcess([], 0, "flathub\thttps://dl.flathub.org/repo/\n", "")
        compat.install_component("bottles", confirmed=True)
        remote_command = self.run.call_args_list[0].args[0]
        install_command = self.run.call_args_list[1].args[0]
        self.assertEqual(remote_command, ["/mock/flatpak", "remotes", "--user", "--columns=name,url"])
        self.assertEqual(install_command, ["/mock/flatpak", "install", "--user", "--noninteractive",
                                           "flathub", "com.usebottles.bottles"])
        self.assertFalse(any("pkexec" in word or "remote-add" in word for word in install_command))

    def test_bottles_missing_or_wrong_remote_never_installs(self):
        for listing in ("", "flathub https://untrusted.example/repo/\n", "system-flathub https://dl.flathub.org/repo/\n"):
            self.run.reset_mock()
            self.run.return_value = subprocess.CompletedProcess([], 0, listing, "")
            with self.assertRaises(compat.CompatError):
                compat.install_component("bottles", confirmed=True)
            self.assertEqual(self.run.call_count, 1)
            self.assertIn("remotes", self.run.call_args.args[0])

    def test_create_architecture_and_environment(self):
        for name, arch in (("new64", "win64"), ("new32", "win32")):
            path = compat.create_prefix(name, arch, self.home)
            self.assertTrue(path.is_dir())
            self.assertEqual(self.run.call_args.args[0], ["/mock/wineboot", "--init"])
            self.assertEqual(self.run.call_args.kwargs["env"]["WINEPREFIX"], str(path))
            self.assertEqual(self.run.call_args.kwargs["env"]["WINEARCH"], arch)
            self.assertNotIn("shell", self.run.call_args.kwargs)

    def test_duplicate_or_invalid_arch_never_executes(self):
        self.prefix()
        with self.assertRaises(compat.CompatError):
            compat.create_prefix("legacy", home=self.home)
        with self.assertRaises(compat.CompatError):
            compat.create_prefix("new", "anything", self.home)
        self.run.assert_not_called()

    def test_failed_create_keeps_data_for_reversible_removal(self):
        self.run.return_value = subprocess.CompletedProcess([], 1)
        with self.assertRaisesRegex(compat.CompatError, "Prefix retained"):
            compat.create_prefix("failed", home=self.home)
        path = compat.prefix_path("failed", self.home)
        self.assertTrue(path.is_dir())
        destination = compat.remove_prefix("failed", self.home)
        self.assertTrue(destination.is_dir())
        self.assertFalse(path.exists())

    def test_run_preserves_arguments_without_shell(self):
        path = self.prefix()
        args = ["hello world", "; touch /tmp/never", "$(id)", "--flag"]
        with mock.patch.dict(compat.os.environ, {"WINEARCH": "win32"}):
            compat.run_prefix("legacy", "C:\\Apps\\legacy.exe", args, self.home)
        self.assertEqual(self.run.call_args.args[0], ["/mock/wine", "C:\\Apps\\legacy.exe", *args])
        self.assertEqual(self.run.call_args.kwargs["env"]["WINEPREFIX"], str(path))
        self.assertNotIn("WINEARCH", self.run.call_args.kwargs["env"])
        self.assertNotIn("shell", self.run.call_args.kwargs)

    def test_run_missing_prefix_and_wine_options_rejected(self):
        with self.assertRaises(compat.CompatError):
            compat.run_prefix("missing", "program.exe", home=self.home)
        self.prefix()
        for program in ("", "--help", "bad\x00name"):
            with self.assertRaises(compat.CompatError):
                compat.run_prefix("legacy", program, home=self.home)
        self.run.assert_not_called()

    def test_remove_moves_reversibly_and_is_unique(self):
        original = self.prefix()
        first = compat.remove_prefix("legacy", self.home)
        self.assertFalse(original.exists())
        self.assertEqual((first / "system.reg").read_text(encoding="ascii"), "fixture")
        first.rename(original)
        second = compat.remove_prefix("legacy", self.home)
        self.assertNotEqual(first, second)
        self.assertTrue(second.is_dir())
        self.assertEqual(second.parent, self.home / ".local/share/nova/prefix-trash")
        self.run.assert_not_called()

    def test_symlink_prefix_parent_and_trash_are_rejected(self):
        # Simulate is_symlink for portable Windows tests where symlink creation is privileged.
        legacy = compat.prefix_path("legacy", self.home)
        paths = (legacy, legacy.parent, self.home / ".local", self.home / ".local/share/nova/prefix-trash")
        for unsafe in paths:
            with self.subTest(path=unsafe), \
                    mock.patch.object(Path, "is_symlink", autospec=True,
                                      side_effect=lambda path, target=unsafe: path == target), \
                    self.assertRaises(compat.CompatError):
                if unsafe.name == "prefix-trash":
                    compat.storage_dir(self.home, trash=True, create=True)
                else:
                    compat.prefix_path("legacy", self.home)
        self.run.assert_not_called()

    def test_real_symlink_is_rejected_when_supported(self):
        base = compat.storage_dir(self.home, create=True)
        outside = self.home / "outside"
        outside.mkdir()
        link = base / "unsafe"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError) as error:
            self.skipTest(f"Symlink creation unavailable: {error}")
        with self.assertRaises(compat.CompatError):
            compat.remove_prefix("unsafe", self.home)
        self.assertTrue(outside.exists())

    def test_root_is_rejected_for_all_mutating_actions(self):
        with mock.patch.object(compat.os, "geteuid", return_value=0):
            actions = [lambda: compat.create_prefix("root", home=self.home),
                       lambda: compat.run_prefix("root", "app.exe", home=self.home),
                       lambda: compat.remove_prefix("root", self.home),
                       lambda: compat.install_component("wine64", confirmed=True),
                       lambda: compat.install_component("bottles", confirmed=True)]
            for action in actions:
                with self.assertRaisesRegex(compat.CompatError, "root"):
                    action()
        self.run.assert_not_called()

    def test_timeout_is_visible(self):
        self.run.side_effect = subprocess.TimeoutExpired("tool", 120)
        with self.assertRaisesRegex(compat.CompatError, "exceeded"):
            compat.install_component("steam", confirmed=True)

    def test_cancelled_cli_does_not_install(self):
        with mock.patch("builtins.input", return_value="n"), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(compat.main(["install", "steam"]), 0)
        self.run.assert_not_called()


class RepositoryValidatorTests(unittest.TestCase):
    """Execute the helper's real stdlib validator with fake /etc/apt files, not apt."""

    @classmethod
    def setUpClass(cls):
        cls.helper = PROJECT / "compatibility/install-component.sh"
        text = cls.helper.read_text(encoding="utf-8")
        cls.source = text.split("<<'PY'\n", 1)[1].split("\nPY\n", 1)[0]

    def validate_sources(self, files):
        # Windows pathlib stringification uses backslashes; normalize only test lookup keys.
        def key(path):
            return str(path).replace("\\", "/")

        namespace = {"__name__": "repository_validator_fixture"}
        with mock.patch.object(sys, "argv", ["-", "wilma"]), \
                mock.patch.object(glob, "glob", side_effect=lambda pattern: [name for name in files if fnmatch.fnmatch(name, pattern)]), \
                mock.patch.object(Path, "exists", autospec=True, side_effect=lambda path: key(path) in files), \
                mock.patch.object(Path, "read_text", autospec=True, side_effect=lambda path, **_kwargs: files[key(path)]):
            exec(compile(self.source, str(self.helper), "exec"), namespace)
        return namespace

    def official(self, extra=""):
        return {"/etc/apt/sources.list.d/official.list":
                "deb http://packages.linuxmint.com wilma main upstream import backport\n"
                "deb http://archive.ubuntu.com/ubuntu noble main restricted universe multiverse\n"
                "deb http://security.ubuntu.com/ubuntu noble-security main universe\n" + extra}

    def test_official_traditional_sources(self):
        namespace = self.validate_sources(self.official(
            "deb [arch=amd64 signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] "
            "https://gb.archive.ubuntu.com/ubuntu noble-updates main\n"))
        self.assertEqual(namespace["seen"], {"mint", "ubuntu"})

    def test_deb822_and_disabled_third_party(self):
        files = {"/etc/apt/sources.list": "deb http://packages.linuxmint.com wilma main\n",
                 "/etc/apt/sources.list.d/ubuntu.sources":
                 "Types: deb\nURIs: http://archive.ubuntu.com/ubuntu\n"
                 "Suites: noble noble-updates noble-backports\nComponents: main universe\n"
                 "Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg\n\n"
                 "Types: deb\nURIs: http://security.ubuntu.com/ubuntu\nSuites: noble-security\nComponents: main\n",
                 "/etc/apt/sources.list.d/disabled.sources":
                 "Enabled: no\nTypes: deb\nURIs: https://ppa.launchpadcontent.net/example/ppa/ubuntu\nSuites: noble\nComponents: main\n"}
        self.assertEqual(self.validate_sources(files)["seen"], {"mint", "ubuntu"})

    def test_ppa_and_unknown_hosts_are_rejected(self):
        for uri in ("https://ppa.launchpadcontent.net/example/ppa/ubuntu", "https://example.com/ubuntu",
                    "https://archive.ubuntu.com.evil.example/ubuntu", "file:///tmp/repo"):
            with self.subTest(uri=uri), self.assertRaises(SystemExit):
                self.validate_sources(self.official(f"deb {uri} noble main\n"))

    def test_source_trust_bypasses_are_rejected(self):
        for option in ("trusted=yes", "allow-insecure=yes", "allow-weak=true", "allow-downgrade-to-insecure=1"):
            with self.subTest(option=option), self.assertRaises(SystemExit):
                self.validate_sources(self.official(f"deb [{option}] http://archive.ubuntu.com/ubuntu noble main\n"))
        files = self.official()
        files["/etc/apt/sources.list.d/unsafe.sources"] = (
            "Types: deb\nURIs: http://archive.ubuntu.com/ubuntu\nSuites: noble\nComponents: main\nTrusted: yes\n")
        with self.assertRaises(SystemExit):
            self.validate_sources(files)

    def test_wrong_suite_missing_sources_and_malformed_options(self):
        for extra in ("deb http://archive.ubuntu.com/ubuntu jammy main\n",
                      "deb http://packages.linuxmint.com xia main\n",
                      "deb [trusted=yes http://archive.ubuntu.com/ubuntu noble main\n"):
            with self.assertRaises(SystemExit):
                self.validate_sources(self.official(extra))
        with self.assertRaises(SystemExit):
            self.validate_sources({})


if __name__ == "__main__":
    unittest.main()
