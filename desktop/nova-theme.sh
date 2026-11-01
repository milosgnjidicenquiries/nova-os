#!/bin/bash
set -eu

if [ "$#" -ne 1 ]; then
    printf 'Usage: nova-theme light|dark\n' >&2
    exit 2
fi
case "$1" in
    light) theme=Nova; dark=false ;;
    dark) theme=Nova-Dark; dark=true ;;
    *) printf 'Usage: nova-theme light|dark\n' >&2; exit 2 ;;
esac

if ! command -v xfconf-query >/dev/null 2>&1; then
    printf 'nova-theme: xfconf-query is required in your XFCE user session.\n' >&2
    exit 127
fi

set_property() {
    local channel="$1" property="$2" type="$3" value="$4"
    if xfconf-query -c "$channel" -p "$property" >/dev/null 2>&1; then
        xfconf-query -c "$channel" -p "$property" -s "$value"
    else
        xfconf-query -c "$channel" -p "$property" -n -t "$type" -s "$value"
    fi
}

# Never enable compositing when changing appearance.
set_property xfwm4 /general/use_compositing bool false
set_property xsettings /Net/ThemeName string "$theme"
set_property xsettings /Net/IconThemeName string Nova
set_property xsettings /Gtk/FontName string 'Sans 10'
set_property xsettings /Gtk/ApplicationPreferDarkTheme bool "$dark"
set_property xsettings /Gtk/EnableAnimations bool false
set_property xfwm4 /general/theme string "$theme"
set_property xfce4-panel /panels/dark-mode bool "$dark"
printf 'Nova theme: %s (compositor off)\n' "$1"
