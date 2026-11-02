#!/usr/bin/env python3
from pathlib import Path
import ast
import configparser
import os
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
ast.parse((ROOT / "build-assets.py").read_text(encoding="utf-8"))
xmls = sorted(ROOT.rglob("*.xml"))
svgs = sorted(ROOT.rglob("*.svg"))
for path in xmls + svgs:
    ET.parse(path)

allowed_types = {"empty", "array", "string", "bool", "int", "uint", "double"}
for path in xmls:
    channel = ET.parse(path).getroot()
    assert channel.tag == "channel" and channel.attrib["name"] == path.stem
    assert channel.attrib["version"] == "1.0"
    for parent in channel.iter():
        names = [child.attrib["name"] for child in parent if child.tag == "property"]
        assert len(names) == len(set(names)), (path, names)
    for node in channel.iter("property"):
        assert node.attrib["type"] in allowed_types, (path, node.attrib)
        kind = node.attrib["type"]
        if kind == "bool":
            assert node.attrib["value"] in ("true", "false")
        elif kind in ("int", "uint"):
            value = int(node.attrib["value"])
            assert kind != "uint" or value >= 0
        elif kind == "array":
            assert len(node.findall("value")) > 0
    for value in channel.iter("value"):
        if value.attrib["type"] in ("int", "uint"):
            int(value.attrib["value"])
        elif value.attrib["type"] == "double":
            float(value.attrib["value"])


def props(path):
    values = {}

    def walk(node, prefix=""):
        for child in node.findall("property"):
            name = prefix + "/" + child.attrib["name"]
            values[name] = child
            walk(child, name)

    walk(ET.parse(path).getroot())
    return values


cfg = ROOT / "xfce-config/xfce4"
panel = props(cfg / "xfconf/xfce-perchannel-xml/xfce4-panel.xml")
assert panel["/configver"].attrib["value"] == "2"
assert [n.attrib["value"] for n in panel["/panels"].findall("value")] == ["1"]
assert panel["/panels/panel-1/position"].attrib["value"] == "p=10;x=0;y=0"
assert panel["/panels/panel-1/length"].attrib["value"] == "100"
assert panel["/panels/panel-1/size"].attrib["value"] == "48"
# Two expand separators hold the menu, launchers and window list as one centered block.
expected_plugins = ["separator", "whiskermenu", "launcher", "launcher", "tasklist", "separator",
                    "systray", "pulseaudio", "power-manager-plugin", "clock", "showdesktop"]
ids = [n.attrib["value"] for n in panel["/panels/panel-1/plugin-ids"].findall("value")]
plugins = [panel[f"/plugins/plugin-{n}"].attrib["value"] for n in ids]
assert plugins == expected_plugins
assert [panel[f"/plugins/plugin-{n}/expand"].attrib["value"] for n, kind in zip(ids, plugins)
        if kind == "separator"] == ["true", "true"]
assert len([key for key in panel if re.fullmatch(r"/plugins/plugin-\d+", key)]) == len(ids)

index = configparser.ConfigParser(interpolation=None)
index.optionxform = str
index.read(ROOT / "icons/Nova/index.theme", encoding="utf-8")
assert index["Icon Theme"]["Inherits"] == "Adwaita,hicolor"
for directory in index["Icon Theme"]["Directories"].split(","):
    folder = ROOT / "icons/Nova" / directory
    assert folder.is_dir() and list(folder.glob("*.svg")), directory
    assert directory in index
    for icon in folder.glob("*.svg"):
        svg = ET.parse(icon).getroot()
        assert svg.attrib["viewBox"] == "0 0 48 48"
        assert int(svg.attrib["width"]) == int(index[directory]["Size"])

for n in ("2", "3"):
    for item in panel[f"/plugins/plugin-{n}/items"].findall("value"):
        launcher = cfg / f"panel/launcher-{n}" / item.attrib["value"]
        assert launcher.is_file(), launcher
        entry = configparser.ConfigParser(interpolation=None)
        entry.optionxform = str
        entry.read(launcher, encoding="utf-8")
        entry = entry["Desktop Entry"]
        assert entry["Type"] == "Application" and entry["Terminal"] == "false"
        assert entry["Exec"].split()[0] == entry["TryExec"]
        assert (ROOT / "icons/Nova/scalable/apps" / (entry["Icon"] + ".svg")).is_file()
rc = dict(line.split("=", 1) for line in (cfg / "panel/whiskermenu-1.rc").read_text().splitlines())
assert (ROOT / "icons/Nova/scalable/apps" / (rc["button-icon"] + ".svg")).is_file()
ET.fromstring(panel["/plugins/plugin-9/digital-format"].attrib["value"])
wm = props(cfg / "xfconf/xfce-perchannel-xml/xfwm4.xml")
settings = props(cfg / "xfconf/xfce-perchannel-xml/xsettings.xml")
assert wm["/general/use_compositing"].attrib["value"] == "false"
assert wm["/general/theme"].attrib["value"] == settings["/Net/ThemeName"].attrib["value"] == "Nova"
assert settings["/Net/IconThemeName"].attrib["value"] == "Nova"
assert settings["/Gtk/FontName"].attrib["value"] == "Sans 10"
for node in ET.parse(cfg / "xfconf/xfce-perchannel-xml/xfce4-desktop.xml").iter("property"):
    if node.attrib.get("name") in ("last-image", "image-path"):
        assert node.attrib["value"] == "/usr/share/backgrounds/nova.svg"
        assert (ROOT / "wallpapers/nova.svg").is_file()

expected = set()
for state in ("active", "inactive"):
    parts = ["bottom", "bottom-left", "bottom-right", "left", "right", "top-left", "top-right"]
    parts += [f"title-{i}" for i in range(1, 6)]
    expected.update(f"{part}-{state}.xpm" for part in parts)
for button in ("close", "hide", "maximize", "menu", "shade", "stick"):
    toggles = ("", "toggled-") if button in ("maximize", "shade", "stick") else ("",)
    for toggled in toggles:
        expected.update(f"{button}-{toggled}{state}.xpm"
                        for state in ("active", "inactive", "prelight", "pressed"))
assert len(expected) == 60
xpms = sorted(ROOT.rglob("*.xpm"))
assert len(xpms) == 120
for theme in ("Nova", "Nova-Dark"):
    assert {p.name for p in (ROOT / f"themes/{theme}/xfwm4").glob("*.xpm")} == expected
for path in xpms:
    text = path.read_text()
    assert text.startswith("/* XPM */\n")
    rows = re.findall(r'^"(.*)"[,]?$', text, re.M)
    width, height, count, cpp = map(int, rows[0].split())
    assert cpp == 1 and len(rows) == 1 + count + height
    colors = set()
    for color in rows[1:1 + count]:
        assert re.fullmatch(r". c #[0-9a-fA-F]{6}", color)
        colors.add(color[0])
    assert len(colors) == count
    assert all(len(row) == width and set(row) <= colors for row in rows[1 + count:]), path
for path in ROOT.rglob("*.css"):
    text = path.read_text()
    assert text.count("{") == text.count("}"), path
    for resource in re.findall(r'url\("([^\"]+)"\)', text):
        assert (path.parent / resource).is_file(), (path, resource)
for path in ROOT.rglob("gtkrc"):
    text = path.read_text()
    assert text.count("{") == text.count("}")
    assert "engine " not in text and "include " not in text
    for state in ("NORMAL", "PRELIGHT", "ACTIVE", "SELECTED", "INSENSITIVE"):
        assert all(f"{kind}[{state}]" in text for kind in ("fg", "bg", "base", "text"))
for path in svgs:
    svg = ET.parse(path).getroot()
    for node in svg.iter():
        for key, value in node.attrib.items():
            if key.endswith("href"):
                assert value.startswith("#"), (path, value)
            for fragment in re.findall(r"url\(#([^)]*)\)", value):
                assert any(n.attrib.get("id") == fragment for n in svg.iter()), (path, fragment)
assert not list(ROOT.rglob("*.md"))
print(f"PASS: {len(xmls)} XFconf XML files, {len(svgs)} SVG files, 120 XPM assets, icon metadata, plugin order, launchers and local resources.")
print("PASS: Python AST and basic CSS/GTK2 structural checks, not GTK runtime parsing.")

bash = shutil.which("bash")
assert bash, "Bash is required for shell tests"
script = ROOT / "nova-theme.sh"
subprocess.run([bash, "-n", str(script)], check=True)
stub = r'''
xfconf-query() {
    local arg writing=false
    for arg in "$@"; do
        if [ "$arg" = -s ]; then writing=true; fi
    done
    if [ "$writing" = false ]; then
        [ "${NOVA_TEST_MISSING:-0}" = 0 ]
        return
    fi
    printf 'SET'
    printf '\t%s' "$@"
    printf '\n'
    [ "${NOVA_TEST_FAIL:-0}" = 0 ]
}
export -f xfconf-query
/bin/bash "$1" "${@:2}"
'''
checks = 0
for missing in ("0", "1"):
    for mode, theme, dark in (("light", "Nova", "false"), ("dark", "Nova-Dark", "true")):
        env = dict(os.environ, NOVA_TEST_MISSING=missing, NOVA_TEST_FAIL="0")
        result = subprocess.run([bash, "-c", stub, "nova-test", str(script), mode],
                                env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        calls = [line.split("\t")[1:] for line in result.stdout.splitlines() if line.startswith("SET\t")]
        assert len(calls) == 8, calls
        expected_calls = [
            ("xfwm4", "/general/use_compositing", "bool", "false"),
            ("xsettings", "/Net/ThemeName", "string", theme),
            ("xsettings", "/Net/IconThemeName", "string", "Nova"),
            ("xsettings", "/Gtk/FontName", "string", "Sans 10"),
            ("xsettings", "/Gtk/ApplicationPreferDarkTheme", "bool", dark),
            ("xsettings", "/Gtk/EnableAnimations", "bool", "false"),
            ("xfwm4", "/general/theme", "string", theme),
            ("xfce4-panel", "/panels/dark-mode", "bool", dark),
        ]
        for call, (channel, prop, kind, value) in zip(calls, expected_calls):
            expected_call = ["-c", channel, "-p", prop]
            if missing == "1":
                expected_call += ["-n", "-t", kind]
            expected_call += ["-s", value]
            assert call == expected_call, (call, expected_call)
        checks += 1
for args in ([], ["invalid"], ["Light"], ["light", "dark"]):
    result = subprocess.run([bash, "-c", stub, "nova-test", str(script), *args],
                            capture_output=True, text=True)
    assert result.returncode == 2 and "SET" not in result.stdout, result
    checks += 1
result = subprocess.run([bash, "-c", stub, "nova-test", str(script), "light"],
                        env=dict(os.environ, NOVA_TEST_FAIL="1"), capture_output=True, text=True)
assert result.returncode != 0 and result.stdout.count("SET\t") == 1
checks += 1
missing_tool = r'''
command() {
    if [ "$1" = -v ] && [ "$2" = xfconf-query ]; then return 1; fi
    builtin command "$@"
}
export -f command
/bin/bash "$1" light
'''
result = subprocess.run([bash, "-c", missing_tool, "nova-test", str(script)],
                        capture_output=True, text=True)
assert result.returncode == 127 and "required" in result.stderr
checks += 1
print(f"PASS: bash -n and {checks} simulated shell cases; no real xfconf writes or XFCE display test.")
files = [p for p in ROOT.rglob("*") if p.is_file()]
print(f"Deliverable: {len(files)} files, {sum(p.stat().st_size for p in files)} bytes.")
