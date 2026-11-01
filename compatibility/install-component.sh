#!/bin/bash
# Install as root:root, mode 0755, /usr/local/libexec/nova-install-component.
# This helper is called via pkexec only after the UI/CLI explicitly confirms a choice.
set -euo pipefail
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
unset APT_CONFIG PYTHONPATH PYTHONHOME

fail() { printf 'nova-install-component: %s\n' "$*" >&2; exit 1; }
[[ $# == 1 ]] || fail 'Exactly one component is required: wine64, wine32, or steam.'
case "$1" in
    wine64) packages=(wine wine64 winetricks); multiarch=no ;;
    wine32) packages=(wine32:i386); multiarch=yes ;;
    steam) packages=(steam-installer); multiarch=yes ;;
    bottles) fail 'Bottles is user-only Flatpak; never run its installer as root.' ;;
    *) fail 'Component is not allowlisted.' ;;
esac
[[ $(uname -s) == Linux ]] || fail 'Requires Linux.'
[[ $EUID == 0 ]] || fail 'Authorization required: invoke through pkexec from Nova Compatibility.'
[[ -f /etc/os-release ]] || fail 'Missing distribution identity.'
# The installed distribution owns this standard shell-compatible file.
. /etc/os-release
[[ ${ID:-} == linuxmint && ${UBUNTU_CODENAME:-} == noble && -n ${VERSION_CODENAME:-} ]] || fail 'Only Linux Mint based on Ubuntu noble is supported.'
[[ $(dpkg --print-architecture) == amd64 ]] || fail 'Only the planned amd64 target is supported.'

# Fail closed on PPAs, third-party repositories, or per-source trust bypasses.
# Existing official Mint/Ubuntu sources are used; no repositories or keys are added.
# apt itself verifies InRelease/Release signatures before using package indexes.
python3 -I - "$VERSION_CODENAME" <<'PY'
import glob
from pathlib import Path
import re
import shlex
import sys
from urllib.parse import urlsplit

mint_suite = sys.argv[1]
ubuntu_suites = {"noble", "noble-updates", "noble-security", "noble-backports"}
seen = set()


def reject(message):
    raise SystemExit("nova-install-component: " + message)


def validate(uri, suites, options, source):
    parsed = urlsplit(uri)
    host = parsed.hostname or ""
    if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password or parsed.port:
        reject(f"Unsupported repository URI in {source}: {uri}")
    if parsed.query or parsed.fragment:
        reject(f"Unsupported repository URI in {source}: {uri}")
    if host == "packages.linuxmint.com" and parsed.path in {"", "/"}:
        kind, allowed = "mint", {mint_suite}
    elif (host in {"archive.ubuntu.com", "security.ubuntu.com"} or host.endswith(".archive.ubuntu.com")) and parsed.path in {"/ubuntu", "/ubuntu/"}:
        kind, allowed = "ubuntu", ubuntu_suites
    else:
        reject(f"Only official Mint/Ubuntu repositories are accepted, not PPAs or third-party sources: {uri}")
    if not suites or any(suite not in allowed for suite in suites):
        reject(f"Repository suite does not match Mint/{mint_suite} or Ubuntu noble: {source}")
    for key in ("trusted", "allow-insecure", "allow-weak", "allow-downgrade-to-insecure"):
        if key in options and options[key].strip().lower() not in {"no", "false", "0"}:
            reject(f"Repository signature/trust bypass ({key}) in {source}")
    seen.add(kind)


def traditional(path):
    for line in path.read_text(encoding="utf-8").splitlines():
        words = shlex.split(line, comments=True)
        if not words:
            continue
        if words[0] not in {"deb", "deb-src"}:
            reject(f"Unrecognized source line in {path}")
        words = words[1:]
        options = {}
        if words and words[0].startswith("["):
            option_words = []
            while words:
                word = words.pop(0)
                option_words.append(word)
                if word.endswith("]"):
                    break
            raw = " ".join(option_words)
            if not raw.endswith("]"):
                reject(f"Malformed source options in {path}")
            for item in raw[1:-1].split():
                key, separator, value = item.partition("=")
                if not separator:
                    reject(f"Malformed source option in {path}")
                options[key.lower()] = value
        if len(words) < 3:
            reject(f"Malformed source line in {path}")
        validate(words[0], [words[1]], options, path)


def deb822(path):
    fields = {}
    last = None
    # Also flush the final stanza without requiring a trailing blank line.
    for line in path.read_text(encoding="utf-8").splitlines() + [""]:
        if line.lstrip().startswith("#"):
            continue
        if not line.strip():
            if fields and fields.get("enabled", "yes").lower() != "no":
                types = fields.get("types", "").split()
                uris = fields.get("uris", "").split()
                suites = fields.get("suites", "").split()
                if not types or any(kind not in {"deb", "deb-src"} for kind in types) or not uris:
                    reject(f"Malformed deb822 source in {path}")
                for uri in uris:
                    validate(uri, suites, fields, path)
            fields, last = {}, None
        elif line[0].isspace():
            if last is None:
                reject(f"Invalid deb822 continuation in {path}")
            fields[last] += " " + line.strip()
        else:
            key, separator, value = line.partition(":")
            key = key.lower()
            if not separator or key in fields:
                reject(f"Invalid or duplicate deb822 field in {path}")
            fields[key], last = value.strip(), key


paths = [Path("/etc/apt/sources.list")]
paths += [Path(name) for name in sorted(glob.glob("/etc/apt/sources.list.d/*.list"))]
paths += [Path(name) for name in sorted(glob.glob("/etc/apt/sources.list.d/*.sources"))]
for path in paths:
    if path.exists():
        try:
            (deb822 if path.suffix == ".sources" else traditional)(path)
        except (OSError, ValueError) as error:
            reject(f"Cannot validate {path}: {error}")
if seen != {"mint", "ubuntu"}:
    reject("Both official Mint and Ubuntu noble sources must already be configured.")
PY

printf '%s\n' 'Compatibility is optional: legacy apps may need 1 GiB RAM plus OS overhead; modern games need more.'
printf '%s\n' 'SSE, Vulkan and anti-cheat support vary; installation does not guarantee compatibility.'
if [[ $multiarch == yes ]]; then
    printf 'Explicit %s choice: enabling i386 multiarch.\n' "$1"
    dpkg --add-architecture i386
fi
# Override insecure global settings as well as rejecting per-source bypasses.
apt_options=(
    -o Dir::Etc::sourcelist=/etc/apt/sources.list
    -o Dir::Etc::sourceparts=/etc/apt/sources.list.d
    -o APT::Get::AllowUnauthenticated=false
    -o Acquire::AllowInsecureRepositories=false
    -o Acquire::AllowWeakRepositories=false
    -o Acquire::AllowDowngradeToInsecureRepositories=false
    -o Acquire::Check-Valid-Until=true
    -o Acquire::http::Timeout=30
    -o Acquire::https::Timeout=30
    -o Acquire::Retries=1
    -o APT::Update::Error-Mode=any
)
timeout --foreground 900 apt-get "${apt_options[@]}" update
# Dependencies of the chosen packages are necessary; optional recommendations are not automatic.
timeout --foreground 1800 apt-get "${apt_options[@]}" --yes --no-install-recommends install "${packages[@]}"
