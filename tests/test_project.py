import importlib.util
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, PROJECT / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


source = load("verify_source", "build/verify-source.py")
configure = load("configure_rootfs", "build/configure-rootfs.py")
finalize = load("finalize_tree", "build/finalize-tree.py")
lock = load("check_lock", "build/check-lock.py")
packager = load("create_defaults", "build/create-defaults.py")
deployment = load("deploy_defaults", "build/deploy-defaults.py")
writer = load("write_iso", "build/write-iso.py")


class PackagingTests(unittest.TestCase):
    def test_complete_staged_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            stage = Path(directory) / "stage"
            stage.mkdir()
            packager.stage_payload(PROJECT, stage)
            for relative in ("usr/local/bin/nova-hardware", "usr/local/bin/nova-compat", "usr/local/libexec/nova-install-component", "usr/local/bin/nova-benchmark", "usr/local/bin/nova-notify", "usr/share/nova/browser/nova.js", "usr/share/applications/nova-welcome.desktop", "usr/share/backgrounds/nova.svg", "usr/share/nova/skel/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-panel.xml", "usr/share/nova/performance/zramswap", "etc/nova-release", "DEBIAN/control"):
                self.assertTrue((stage / relative).is_file(), relative)
            self.assertFalse((stage / "etc/default/zramswap").exists())
            self.assertFalse((stage / "etc/skel").exists())
            self.assertEqual((stage / "DEBIAN/conffiles").read_text(), "/etc/nova-release\n")

    def test_deploy_preserves_original_and_backups(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "etc/linuxmint").mkdir(parents=True)
            (root / "etc/linuxmint/info").touch()
            (root / "etc/default").mkdir()
            (root / "etc/default/zramswap").write_text("ORIGINAL=yes\n")
            stage = root / "payload"
            stage.mkdir()
            packager.stage_payload(PROJECT, stage)
            shutil.copytree(stage / "usr/share/nova", root / "usr/share/nova")
            deployment.deploy(root)
            self.assertEqual((root / "var/lib/nova/backups/zramswap").read_text(), "ORIGINAL=yes\n")
            self.assertTrue((root / "var/lib/nova/backups/nova-performance.conf.absent").exists())
            self.assertIn("PERCENT=35", (root / "etc/default/zramswap").read_text())
            self.assertTrue((root / "etc/skel/.config/autostart/nova-firstboot.desktop").is_file())
            deployment.deploy(root)
            self.assertEqual((root / "var/lib/nova/backups/zramswap").read_text(), "ORIGINAL=yes\n")

    def test_deploy_rejects_host_root(self):
        with self.assertRaises(ValueError):
            deployment.deploy("/")

    def staged_root(self, directory):
        root = Path(directory)
        (root / "etc/linuxmint").mkdir(parents=True)
        (root / "etc/linuxmint/info").touch()
        stage = root / "payload"
        stage.mkdir()
        packager.stage_payload(PROJECT, stage)
        shutil.copytree(stage / "usr/share/nova", root / "usr/share/nova")
        return root

    def test_browser_defaults_reach_only_an_installed_firefox(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.staged_root(directory)
            deployment.deploy(root)
            self.assertFalse((root / "usr/lib/firefox/defaults").exists())
            (root / "usr/lib/firefox/defaults/preferences").mkdir(parents=True)
            deployment.deploy(root)
            self.assertIn('pref("dom.ipc.processCount", 2);',
                          (root / "usr/lib/firefox/defaults/preferences/00-nova.js").read_text())
            self.assertTrue((root / "var/lib/nova/backups/browser/firefox-nova.js.absent").is_file())
            (root / "usr/lib/firefox-esr/defaults/preferences").mkdir(parents=True)
            deployment.deploy(root)
            self.assertTrue((root / "usr/lib/firefox-esr/defaults/preferences/00-nova.js").is_file())

    def test_browser_defaults_stay_overridable(self):
        text = (PROJECT / "system/browser/nova.js").read_text()
        self.assertNotIn("lockPref", text)
        self.assertIn('pref("browser.uidensity", 1);', text)


class ManifestTests(unittest.TestCase):
    def test_source_digest(self):
        self.assertEqual(source.manifest_digest("a" * 64 + " *test.iso\n", "test.iso"), "a" * 64)

    def test_source_wrong_filename(self):
        with self.assertRaises(ValueError):
            source.manifest_digest("a" * 64 + "  other.iso\n", "test.iso")

    def test_source_duplicate(self):
        with self.assertRaises(ValueError):
            source.manifest_digest(("a" * 64 + "  test.iso\n") * 2, "test.iso")

    def test_source_malformed(self):
        with self.assertRaises(ValueError):
            source.manifest_digest("xyz  test.iso", "test.iso")

    def test_manifest_safe(self):
        self.assertIn("xfce4", configure.read_manifest(PROJECT / "build/packages.txt"))
        self.assertNotIn("wine", configure.read_manifest(PROJECT / "build/packages.txt"))

    def test_manifest_rejects_command(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "packages"
            path.write_text("firefox;touch /tmp/pwned\n")
            with self.assertRaises(ValueError):
                configure.read_manifest(path)

    def test_manifest_rejects_duplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "packages"
            path.write_text("firefox\nfirefox\n")
            with self.assertRaises(ValueError):
                configure.read_manifest(path)

    def test_version_pins(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "packages"
            path.write_text("libc6:amd64=2.39-0ubuntu8.6\n")
            self.assertEqual(configure.read_manifest(path), ["libc6:amd64=2.39-0ubuntu8.6"])

    def test_dependency_plan(self):
        self.assertEqual(configure.removal_plan("Remv libreoffice-writer [1]\nRemv xfce4 [4]\n"), ["libreoffice-writer", "xfce4"])

    def test_essential_protected(self):
        self.assertEqual(configure.unsafe_removals(["libc6:amd64", "linux-image-6.8.0-1-generic", "wine"], set(), {"libc6"}), ["libc6:amd64", "linux-image-6.8.0-1-generic"])

    def test_required_desktop_protected(self):
        self.assertEqual(configure.unsafe_removals(["xfce4"], {"xfce4"}, set()), ["xfce4"])

    def test_installer_exclusions_preserved(self):
        original = "casper 1\nubiquity 1\nxfce4 4\n"
        installed = "xfce4 4\n"
        current = "casper 2\nubiquity 2\nxfce4 5\nnova-defaults 0.1.0\n"
        self.assertEqual(finalize.desktop_manifest(current, original, installed), "xfce4 5\nnova-defaults 0.1.0\n")

    def test_remove_list_drops_purged_packages(self):
        original_remove = "boot-repair\nthunderbird\nfirefox-locale-en\n"
        self.assertEqual(finalize.prune_remove_list(original_remove, {"boot-repair", "firefox-locale-en"}), "boot-repair\nfirefox-locale-en\n")

    def test_tab_separated_manifest_still_parses(self):
        # Mint 22.1 ships casper manifests as "package\tversion", not "package version".
        original = "casper\t1\nxfce4\t4\n"
        installed = "xfce4\t4\n"
        current = "casper\t2\nxfce4\t5\n"
        self.assertEqual(finalize.desktop_manifest(current, original, installed), "xfce4\t5\n")

    def test_full_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "lock"
            path.write_text("# lock\nfirefox=1.0\nlibc6:amd64=2.0\n")
            self.assertEqual(lock.entries(path), {"firefox": "1.0", "libc6:amd64": "2.0"})


class BootCommandTests(unittest.TestCase):
    # Captured by xorriso -report_el_torito cmd on the real Mint 22.1 XFCE image.
    REPORT = """-boot_image isolinux system_area=--interval:imported_iso:0s-15s:zero_mbrpt,zero_gpt,zero_apm:'/abs/linuxmint-22.1-xfce-64bit.iso'
-boot_image any partition_cyl_align=off
-boot_image any partition_offset=16
-boot_image any mbr_force_bootable=on
-boot_image any apm_block_size=2048
-boot_image any iso_mbr_part_type=0x00
-boot_image any cat_path='/isolinux/boot.cat'
-boot_image isolinux bin_path='/isolinux/isolinux.bin'
-boot_image any platform_id=0x00
-boot_image any emul_type=no_emulation
-boot_image any load_size=2048
-boot_image any boot_info_table=on
-boot_image any next
-boot_image any efi_path='/boot/grub/efi.img'
-boot_image any platform_id=0xef
-boot_image any emul_type=no_emulation
-boot_image any load_size=5242880
-boot_image isolinux partition_entry=gpt_basdat
-boot_image isolinux partition_entry=apm_hfsplus
"""

    def test_each_report_line_becomes_separate_argv_tokens(self):
        flags = writer.require(writer.boot_flags(self.REPORT))
        self.assertEqual(flags[:3], ["-boot_image", "isolinux", "system_area=--interval:imported_iso:0s-15s:zero_mbrpt,zero_gpt,zero_apm:/abs/linuxmint-22.1-xfce-64bit.iso"])
        self.assertIn("cat_path=/isolinux/boot.cat", flags)
        self.assertIn("bin_path=/isolinux/isolinux.bin", flags)
        self.assertIn("efi_path=/boot/grub/efi.img", flags)
        self.assertNotIn("-boot_image any cat_path='/isolinux/boot.cat'", flags)
        self.assertEqual(flags.count("-boot_image"), self.REPORT.count("\n-boot_image") + 1)

    def test_missing_required_flags_rejected(self):
        with self.assertRaises(ValueError):
            writer.require(writer.boot_flags("-boot_image any cat_path=/isolinux/boot.cat\n"))

    def test_empty_report_rejected(self):
        with self.assertRaises(ValueError):
            writer.require(writer.boot_flags("xorriso : NOTE : nothing here\n"))


class DeliveryTests(unittest.TestCase):
    NAME = "nova-os-0.1.0-amd64.iso"

    def stage(self, directory, payload, corrupt=False):
        folder = Path(directory)
        (folder / "SHA256SUMS").write_text(hashlib.sha256(payload).hexdigest() + "  " + self.NAME + "\n")
        chunks = [payload[:5000], payload[5000:]]
        for index, chunk in enumerate(chunks):
            if corrupt and index == 0:
                chunk = bytes([chunk[0] ^ 0xFF]) + chunk[1:]
            (folder / f"{self.NAME}.{index:02d}.part").write_bytes(chunk)
        return folder

    def test_join_reassembles_and_verifies(self):
        with tempfile.TemporaryDirectory() as directory:
            payload = b"\x00nova-build" * 1000
            self.stage(directory, payload)
            result = subprocess.run([sys.executable, str(PROJECT / ".github/scripts/join-parts.py"), "--dir", directory], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((Path(directory) / self.NAME).read_bytes(), payload)

    def test_join_rejects_corrupted_part(self):
        with tempfile.TemporaryDirectory() as directory:
            self.stage(directory, b"\x00nova-build" * 1000, corrupt=True)
            result = subprocess.run([sys.executable, str(PROJECT / ".github/scripts/join-parts.py"), "--dir", directory], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn("Checksum mismatch", result.stderr)

    def test_join_refuses_to_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            self.stage(directory, b"\x00nova-build" * 1000)
            (Path(directory) / self.NAME).write_bytes(b"previous")
            result = subprocess.run([sys.executable, str(PROJECT / ".github/scripts/join-parts.py"), "--dir", directory], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertEqual((Path(directory) / self.NAME).read_bytes(), b"previous")

    def test_asset_list_skips_lock_and_empty_files(self):
        # GitHub rejects a zero-byte asset with "Bad Content-Length" and aborts the
        # whole upload, so the build lock and any empty log must never be offered.
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            self.stage(directory, b"\x00nova-build" * 1000)
            (folder / "build.lock").write_bytes(b"")
            (folder / "build.log").write_text("noise")
            (folder / ".hidden").write_bytes(b"data")
            (folder / "sub").mkdir()
            (folder / "sub" / "inner").write_bytes(b"x")
            result = subprocess.run([sys.executable, str(PROJECT / ".github/scripts/asset-list.py"), "--dir", directory],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            # Path ordering is case-insensitive on Windows, so compare as a set;
            # the CI script relies on the parts sorting numerically, which they do.
            self.assertEqual(set(result.stdout.split()), {
                "SHA256SUMS",
                "nova-os-0.1.0-amd64.iso.00.part",
                "nova-os-0.1.0-amd64.iso.01.part",
            })


class ReleaseFetchTests(unittest.TestCase):
    # A draft release has no git tag, so `gh release download <tag>` cannot find it;
    # these are the real shapes the API returns for build 8.
    RELEASES = [{"id": 430640878, "tag_name": "nova-build-7", "draft": True},
                {"id": 430818980, "tag_name": "nova-build-8", "draft": True},
                {"id": 430000000, "tag_name": "v1.0", "draft": False}]
    ASSETS = [{"name": "nova-os-0.1.0-amd64.iso.01.part", "id": 3, "size": 5, "state": "uploaded"},
              {"name": "nova-os-0.1.0-amd64.iso.00.part", "id": 1, "size": 5, "state": "uploaded"},
              {"name": "SHA256SUMS", "id": 2, "size": 90, "state": "uploaded"},
              {"name": "source-verification.json", "id": 4, "size": 235, "state": "uploaded"}]

    def setUp(self):
        self.fetch = load("fetch_release_assets", ".github/scripts/fetch-release-assets.py")

    def test_exact_tag_and_newest_draft(self):
        self.assertEqual(self.fetch.pick_release(self.RELEASES, "nova-build-7")["id"], 430640878)
        self.assertEqual(self.fetch.pick_release(self.RELEASES, None)["id"], 430818980)

    def test_unknown_tag_and_public_only(self):
        with self.assertRaises(SystemExit):
            self.fetch.pick_release(self.RELEASES, "nova-build-99")
        with self.assertRaises(SystemExit):
            self.fetch.pick_release([self.RELEASES[2]], None)

    def test_patterns_pick_image_and_checksum_only(self):
        chosen = self.fetch.select_assets(self.ASSETS, ["nova-os-0.1.0-amd64.iso*", "SHA256SUMS"])
        self.assertEqual([asset["name"] for asset in chosen],
                         ["SHA256SUMS", "nova-os-0.1.0-amd64.iso.00.part", "nova-os-0.1.0-amd64.iso.01.part"])

    def test_partially_uploaded_asset_blocks_boot(self):
        broken = [dict(asset) for asset in self.ASSETS]
        broken[0]["state"] = "starter"
        with self.assertRaises(SystemExit):
            self.fetch.select_assets(broken, ["nova-os-0.1.0-amd64.iso*"])

    def test_no_matching_asset_is_fatal(self):
        with self.assertRaises(SystemExit):
            self.fetch.select_assets(self.ASSETS, ["nothing-here*"])


class AssetTests(unittest.TestCase):
    def test_xml_assets_parse(self):
        files = list((PROJECT / "desktop").rglob("*.xml")) + list((PROJECT / "desktop").rglob("*.svg"))
        self.assertTrue(files)
        for file in files:
            with self.subTest(file=file.relative_to(PROJECT)):
                ET.parse(file)

    def test_themes_present(self):
        for theme in ("Nova", "Nova-Dark"):
            for asset in ("gtk-3.0/gtk.css", "gtk-2.0/gtkrc", "xfwm4/themerc"):
                self.assertTrue((PROJECT / "desktop/themes" / theme / asset).is_file(), f"{theme}/{asset}")

    def test_no_proprietary_default_components(self):
        packages = set(configure.read_manifest(PROJECT / "build/packages.txt"))
        self.assertFalse(packages & {"steam", "steam-installer", "wine", "wine32:i386", "bottles", "gimp", "vlc", "libreoffice"})

    def test_no_crlf(self):
        for file in PROJECT.rglob("*"):
            if file.suffix in {".sh", ".py", ".xml", ".svg"}:
                self.assertNotIn(b"\r\n", file.read_bytes(), str(file))

    def test_base_pin(self):
        base = json.loads((PROJECT / "build/base.json").read_text())
        self.assertEqual(base["architecture"], "amd64")
        self.assertEqual(base["ubuntu_suite"], "noble")
        self.assertRegex(base["signing_key_fingerprint"], r"^[A-F0-9]{40}$")

    def test_gtk_asset_references(self):
        for css in (PROJECT / "desktop/themes").rglob("gtk.css"):
            for reference in re.findall(r'url\("([^\"]+)"\)', css.read_text()):
                self.assertTrue((css.parent / reference).is_file(), reference)

    def test_xpm_dimensions_and_palette(self):
        files = list((PROJECT / "desktop/themes").rglob("*.xpm"))
        self.assertTrue(files)
        for path in files:
            with self.subTest(path=path.name):
                lines = re.findall(r'"([^\"]*)"', path.read_text())
                width, height, colors, cpp = map(int, lines[0].split())
                self.assertEqual(len(lines), 1 + colors + height)
                palette = {line[:cpp] for line in lines[1:1 + colors]}
                for line in lines[1 + colors:]:
                    self.assertEqual(len(line), width * cpp)
                    self.assertTrue(all(line[index:index + cpp] in palette for index in range(0, len(line), cpp)))

    def test_launcher_references(self):
        directory = PROJECT / "desktop/xfce-config/xfce4"
        channel = ET.parse(directory / "xfconf/xfce-perchannel-xml/xfce4-panel.xml").getroot()
        for plugin in channel.findall("./property[@name='plugins']/property"):
            if plugin.get("value") == "launcher":
                name = plugin.get("name").replace("plugin-", "launcher-")
                for item in plugin.findall("./property[@name='items']/value"):
                    self.assertTrue((directory / "panel" / name / item.get("value")).is_file())


@unittest.skipUnless(shutil.which("gpg"), "GnuPG not installed")
class SignatureIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="nova-test-sign-")
        cls.directory = Path(cls.temp.name)
        cls.home = cls.directory / "gnupg"
        cls.home.mkdir(mode=0o700)
        cls.command = [shutil.which("gpg"), "--batch", "--no-options", "--homedir", source.gpg_path(cls.home), "--pinentry-mode", "loopback", "--passphrase", ""]
        subprocess.run(cls.command + ["--quick-generate-key", "Nova Test <test@example.invalid>", "rsa2048", "sign", "1d"], check=True, capture_output=True)
        listing = subprocess.check_output(cls.command + ["--with-colons", "--list-keys"], text=True)
        fingerprint = next(line.split(":")[9] for line in listing.splitlines() if line.startswith("fpr:"))
        cls.iso = cls.directory / "test.iso"
        cls.iso.write_bytes(b"Test ISO payload, not a boot image\n")
        cls.sums = cls.directory / "sha256sum.txt"
        cls.sums.write_text(source.sha256(cls.iso) + "  test.iso\n")
        cls.signature = cls.directory / "sha256sum.txt.gpg"
        subprocess.run(cls.command + ["--detach-sign", "--output", source.gpg_path(cls.signature), source.gpg_path(cls.sums)], check=True, capture_output=True)
        cls.key = cls.directory / "test-key.asc"
        cls.key.write_bytes(subprocess.check_output(cls.command + ["--armor", "--export", fingerprint]))
        cls.config = {"iso_filename": "test.iso", "signing_key_fingerprint": fingerprint, "release": "test-only"}

    @classmethod
    def tearDownClass(cls):
        subprocess.run(cls.command[:5] + ["--no-autostart", "--list-keys"], capture_output=True)
        cls.temp.cleanup()

    def test_signed_source_passes(self):
        self.assertTrue(source.verify(self.iso, self.sums, self.signature, self.key, self.config)["verified"])

    def test_unpinned_signer_rejected(self):
        with self.assertRaises(ValueError):
            source.verify(self.iso, self.sums, self.signature, self.key, {**self.config, "signing_key_fingerprint": "0" * 40})

    def test_tampered_manifest_rejected(self):
        path = self.directory / "tampered.txt"
        path.write_text("0" * 64 + "  test.iso\n")
        with self.assertRaises(subprocess.CalledProcessError):
            source.verify(self.iso, path, self.signature, self.key, self.config)

    def test_tampered_iso_rejected(self):
        directory = self.directory / "tampered"
        directory.mkdir()
        iso = directory / "test.iso"
        iso.write_bytes(b"Altered payload")
        with self.assertRaises(ValueError):
            source.verify(iso, self.sums, self.signature, self.key, self.config)
