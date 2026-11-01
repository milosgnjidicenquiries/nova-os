#!/usr/bin/env python3
"""Explicit optional installers and per-user Wine prefixes; no compatibility guarantees."""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone

INSTALL_HELPER = "/usr/local/libexec/nova-install-component"
COMPONENTS = {
    "wine64": "Wine 64-bit: wine, wine64, winetricks (no i386 enablement)",
    "wine32": "Wine 32-bit: explicitly enable i386, then install wine32:i386",
    "steam": "Steam: explicitly enable i386, then install steam-installer",
    "bottles": "Bottles: user-only Flatpak from an already configured Flathub remote",
}
RESOURCE_WARNING = (
    "Legacy Windows apps may need at least 1 GiB of RAM for the app alone; allow additional "
    "RAM for Linux Mint XFCE. Modern apps/games often need substantially more. "
    "SSE requirements vary; Vulkan support and anti-cheat compatibility are not universal. "
    "No application or game is guaranteed to work. No gaming dependencies are installed automatically."
)
NAME_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z", re.ASCII)
FLATHUB_URLS = {"https://dl.flathub.org/repo", "https://dl.flathub.org/repo/"}


class CompatError(Exception):
    """Expected validation or external-tool failure, suitable for display to a user."""


def require_user():
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        raise CompatError("Do not run Nova Compatibility or Wine as root; use your normal desktop user.")


def validate_component(component):
    if component not in COMPONENTS:
        raise CompatError("Unknown component; choose wine64, wine32, steam, or bottles.")
    return component


def validate_name(name):
    if not NAME_PATTERN.fullmatch(name):
        raise CompatError("Prefix names must be 1-64 ASCII letters/digits, '_' or '-', starting with a letter/digit.")
    return name


def ensure_no_symlinks(path):
    # Inspect lexical ancestors, not resolve(): resolve() would hide a symlink.
    path = Path(path).absolute()
    for part in [*reversed(path.parents), path]:
        if part.is_symlink():
            raise CompatError(f"Refusing symlink in prefix storage path: {part}")
    return path


def storage_dir(home=None, trash=False, create=False):
    home = Path.home() if home is None else Path(home)
    base = ensure_no_symlinks(home / ".local/share/nova" / ("prefix-trash" if trash else "prefixes"))
    if base.exists() and not base.is_dir():
        raise CompatError(f"Prefix storage is not a directory: {base}")
    if create:
        base.mkdir(mode=0o700, parents=True, exist_ok=True)
    return base


def prefix_path(name, home=None, existing=False):
    validate_name(name)
    path = ensure_no_symlinks(storage_dir(home) / name)
    if existing and not path.is_dir():
        raise CompatError(f"Prefix does not exist: {name}")
    if path.exists() and not path.is_dir():
        raise CompatError(f"Prefix is not a directory: {name}")
    return path


def tool(name):
    executable = shutil.which(name)
    if not executable:
        raise CompatError(f"{name} is not installed. Install the appropriate optional component explicitly first.")
    return executable


def run_checked(command, timeout, env=None):
    try:
        result = subprocess.run(command, env=env, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as error:
        raise CompatError(f"{command[0]} exceeded {timeout} seconds; check its state before retrying.") from error
    except OSError as error:
        raise CompatError(f"Cannot execute {command[0]}: {error}") from error
    if result.returncode:
        raise CompatError(f"{command[0]} exited with status {result.returncode}.")
    return result


def user_flathub_available():
    executable = tool("flatpak")
    try:
        result = subprocess.run([executable, "remotes", "--user", "--columns=name,url"],
                                capture_output=True, text=True, timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise CompatError(f"Cannot inspect user Flatpak remotes: {error}") from error
    if result.returncode:
        raise CompatError(result.stderr.strip() or "Cannot list user Flatpak remotes.")
    return any(len(fields) == 2 and fields[0] == "flathub" and fields[1] in FLATHUB_URLS
               for fields in (line.split() for line in result.stdout.splitlines()))


def install_component(component, confirmed=False):
    require_user()
    validate_component(component)
    if not confirmed:
        raise CompatError("Installation requires explicit confirmation; nothing changed.")
    if component == "bottles":
        if not user_flathub_available():
            raise CompatError("Configure the official Flathub remote for your user explicitly first. "
                              "Nova will not add remotes or use a system-only remote.")
        return run_checked([tool("flatpak"), "install", "--user", "--noninteractive",
                            "flathub", "com.usebottles.bottles"], timeout=1800)
    # Only a fixed helper receives a single allowlisted component, never package names.
    if not Path(INSTALL_HELPER).is_file():
        raise CompatError(f"The target OS must install compatibility/install-component.sh as {INSTALL_HELPER}.")
    # Allow the helper's bounded update (900s) and install (1800s) to finish.
    return run_checked([tool("pkexec"), INSTALL_HELPER, component], timeout=2800)


def create_prefix(name, arch="win64", home=None):
    require_user()
    validate_name(name)
    if arch not in {"win64", "win32"}:
        raise CompatError("Architecture must be win64 or win32.")
    path = prefix_path(name, home)
    if path.exists():
        raise CompatError(f"Prefix already exists: {name}")
    executable = tool("wineboot")
    storage_dir(home, create=True)
    path.mkdir(mode=0o700)
    env = os.environ.copy()
    env.update(WINEPREFIX=str(path), WINEARCH=arch)
    try:
        run_checked([executable, "--init"], timeout=120, env=env)
    except CompatError as error:
        raise CompatError(f"{error} Prefix retained at {path}; use 'remove {name}' to move it to trash.") from error
    return path


def run_prefix(name, program, arguments=(), home=None):
    require_user()
    path = prefix_path(name, home, existing=True)
    if not isinstance(program, str) or not program or "\x00" in program or program.startswith("-"):
        raise CompatError("Specify a program path, not a Wine option.")
    executable = tool("wine")
    env = os.environ.copy()
    env.pop("WINEARCH", None)  # Existing prefixes retain their architecture.
    env["WINEPREFIX"] = str(path)
    return run_checked([executable, program, *arguments], timeout=3600, env=env)


def remove_prefix(name, home=None):
    require_user()
    path = prefix_path(name, home, existing=True)
    trash = storage_dir(home, trash=True, create=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    destination = trash / f"{name}-{stamp}-{uuid.uuid4().hex}"
    ensure_no_symlinks(destination)
    # Same user data tree/filesystem: rename is reversible, no recursive deletion.
    path.rename(destination)
    return destination


def diagnostics():
    info = {"planned_target": "Linux Mint XFCE / Ubuntu noble / amd64",
            "components": COMPONENTS, "warning": RESOURCE_WARNING,
            "tools": {name: shutil.which(name) for name in ("wine", "wineboot", "flatpak", "pkexec")},
            "helper_installed": Path(INSTALL_HELPER).is_file(),
            "prefix_cli": "nova-compat create NAME --arch win64|win32; run NAME PROGRAM [args]; remove NAME"}
    os_release = Path("/etc/os-release")
    try:
        info["os_release"] = os_release.read_text(encoding="utf-8")
    except OSError as error:
        info["os_release_error"] = str(error)
    hardware = shutil.which("nova-hardware")
    if hardware:
        try:
            result = subprocess.run([hardware], capture_output=True, text=True, timeout=15, check=False)
            if result.returncode:
                info["hardware_error"] = result.stderr.strip() or f"Exit {result.returncode}"
            else:
                info["hardware"] = json.loads(result.stdout)
        except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as error:
            info["hardware_error"] = str(error)
    else:
        info["hardware_note"] = "Run nova-hardware in a terminal for CPU, RAM, boot, and PCI diagnostics."
    return info


def gui():
    require_user()
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import GLib, Gtk
    except (ImportError, ValueError) as error:
        raise CompatError("GTK3 GUI requires the distribution packages python3-gi and gir1.2-gtk-3.0. "
                          "The CLI remains usable.") from error
    available, _ = Gtk.init_check()
    if not available:
        raise CompatError("No GTK display is available; use the CLI in a terminal.")
    window = Gtk.Window(title="Nova Compatibility")
    window.set_default_size(760, 620)
    window.set_border_width(12)
    window.connect("destroy", Gtk.main_quit)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    window.add(box)
    warning = Gtk.Label(label=RESOURCE_WARNING)
    warning.set_line_wrap(True)
    warning.set_xalign(0)
    box.pack_start(warning, False, False, 0)
    scroll = Gtk.ScrolledWindow()
    scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
    view = Gtk.TextView(editable=False, cursor_visible=False)
    view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
    view.get_buffer().set_text(json.dumps(diagnostics(), indent=2))
    scroll.add(view)
    box.pack_start(scroll, True, True, 0)
    status = Gtk.Label(label="No installations are performed until you choose and confirm a component.")
    status.set_line_wrap(True)
    status.set_xalign(0)
    buttons = []

    def finished(message):
        status.set_text(message)
        for button in buttons:
            button.set_sensitive(True)
        return False

    def worker(component):
        try:
            install_component(component, confirmed=True)
            message = f"{component}: installation completed."
        except (CompatError, OSError) as error:
            message = str(error)
        GLib.idle_add(finished, message)

    def clicked(_button, component):
        dialog = Gtk.MessageDialog(transient_for=window, modal=True,
                                   message_type=Gtk.MessageType.QUESTION,
                                   buttons=Gtk.ButtonsType.YES_NO, text="Install this optional component?")
        dialog.format_secondary_text(COMPONENTS[component] + "\n\n" + RESOURCE_WARNING)
        dialog.set_default_response(Gtk.ResponseType.NO)
        response = dialog.run()
        dialog.destroy()
        if response == Gtk.ResponseType.YES:
            for button in buttons:
                button.set_sensitive(False)
            status.set_text(f"Installing {component}; authorization may be requested. See terminal for tool output.")
            threading.Thread(target=worker, args=(component,), daemon=True).start()

    for component, description in COMPONENTS.items():
        button = Gtk.Button(label=f"Install {component}")
        button.set_tooltip_text(description)
        button.connect("clicked", clicked, component)
        buttons.append(button)
        box.pack_start(button, False, False, 0)
    box.pack_start(status, False, False, 0)
    window.show_all()
    Gtk.main()
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gui", action="store_true", help="GTK3 explicit installers and diagnostics; prefixes use CLI")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("status", help="Read-only diagnostics and limitations")
    installer = commands.add_parser("install", help="Explicitly install one optional component")
    installer.add_argument("component", choices=COMPONENTS)
    installer.add_argument("--yes", action="store_true", help="Explicitly confirm this component (including i386 if applicable)")
    creator = commands.add_parser("create", help="Create a per-user Wine prefix")
    creator.add_argument("name")
    creator.add_argument("--arch", choices=("win64", "win32"), default="win64")
    runner = commands.add_parser("run", help="Run a program without a shell, in an existing prefix")
    runner.add_argument("name")
    runner.add_argument("program")
    runner.add_argument("arguments", nargs=argparse.REMAINDER)
    remover = commands.add_parser("remove", help="Reversibly move a prefix to ~/.local/share/nova/prefix-trash")
    remover.add_argument("name")
    args = parser.parse_args(argv)
    if args.gui and args.command:
        parser.error("--gui cannot be combined with a CLI command")
    try:
        if args.gui:
            return gui()
        if args.command in {None, "status"}:
            print(json.dumps(diagnostics(), indent=2))
        elif args.command == "install":
            require_user()
            print(COMPONENTS[args.component] + "\n" + RESOURCE_WARNING)
            confirmed = args.yes
            if not confirmed:
                try:
                    confirmed = input("Install this component? [y/N] ").strip().lower() in {"y", "yes"}
                except EOFError:
                    confirmed = False
            if not confirmed:
                print("Cancelled; nothing changed.")
                return 0
            install_component(args.component, confirmed=True)
        elif args.command == "create":
            print(create_prefix(args.name, args.arch))
        elif args.command == "run":
            run_prefix(args.name, args.program, args.arguments)
        elif args.command == "remove":
            print(f"Prefix moved to {remove_prefix(args.name)}; move it back to restore it when Wine is not running.")
    except (CompatError, OSError) as error:
        print(f"nova-compat: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
