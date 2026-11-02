#!/usr/bin/env python3
"""Send one freedesktop notification over the session bus without extra packages.

python3-gi is already a nova-defaults dependency; notify-send is not guaranteed on a
minimal desktop, and a missing binary must not stop the first-boot flow.
"""
import sys

from gi.repository import Gio, GLib

APP_NAME = "Nova OS"
SIGNATURE = "(susssasa{sv}i)"


def notify(summary, body, timeout_ms=10000):
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    result = bus.call_sync("org.freedesktop.Notifications",
                           "/org/freedesktop/Notifications",
                           "org.freedesktop.Notifications", "Notify",
                           GLib.Variant(SIGNATURE, (APP_NAME, 0, "", summary, body, [], {}, timeout_ms)),
                           Gio.DBusCallFlags.NONE, -1, None)
    return result.unpack()[0]


def main():
    if len(sys.argv) != 3:
        print("Usage: nova-notify SUMMARY BODY", file=sys.stderr)
        return 2
    try:
        notify(sys.argv[1], sys.argv[2])
    except GLib.Error as error:
        print(f"nova-notify: {error.message}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
