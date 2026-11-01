#!/usr/bin/env python3
from pathlib import Path
from string import Template

ROOT = Path(__file__).resolve().parent


def emit(relative, content):
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


PALETTES = {
    "Nova": dict(bg="#eef2f5", fg="#243447", base="#ffffff", muted="#566579",
                 border="#bcc7d2", hover="#dde6ef", pressed="#c9d9ea",
                 accent="#2467ac", accent_hover="#1c568f", selected="#ffffff",
                 disabled_bg="#e8edf1", disabled_fg="#748292", trough="#d6dfe7",
                 inactive_bg="#f3f5f7", inactive_fg="#667485", tooltip="#243447",
                 tooltip_fg="#ffffff"),
    "Nova-Dark": dict(bg="#252d37", fg="#e6edf5", base="#1c232c", muted="#b3c0cf",
                      border="#526174", hover="#354355", pressed="#435670",
                      accent="#306fb3", accent_hover="#397fc9", selected="#ffffff",
                      disabled_bg="#29323e", disabled_fg="#8997a8", trough="#19212a",
                      inactive_bg="#28303a", inactive_fg="#b3bfcd", tooltip="#e6edf5",
                      tooltip_fg="#1c232c"),
}

GTK3 = Template("""@define-color theme_bg_color $bg;
@define-color theme_fg_color $fg;
@define-color theme_base_color $base;
@define-color theme_text_color $fg;
@define-color theme_selected_bg_color $accent;
@define-color theme_selected_fg_color $selected;
@define-color insensitive_bg_color $disabled_bg;
@define-color insensitive_fg_color $disabled_fg;
@define-color insensitive_base_color $disabled_bg;
@define-color borders $border;
@define-color theme_unfocused_bg_color $inactive_bg;
@define-color theme_unfocused_fg_color $inactive_fg;
@define-color theme_unfocused_base_color $base;
@define-color theme_unfocused_text_color $inactive_fg;
@define-color theme_unfocused_selected_bg_color $accent;
@define-color theme_unfocused_selected_fg_color $selected;
@define-color unfocused_borders $border;
@define-color warning_color #bd7a14;
@define-color error_color #cf4343;
@define-color success_color #36875a;

* {
  outline-color: $accent;
  outline-style: dashed;
  outline-width: 1px;
  outline-offset: -3px;
  -gtk-secondary-caret-color: $accent;
}
.background { background-color: $bg; color: $fg; }
*:disabled { color: $disabled_fg; }
*:backdrop { -gtk-icon-effect: dim; }
.view, textview text, iconview { background-color: $base; color: $fg; }
textview border { background-color: $bg; }
selection, .view:selected, row:selected, iconview:selected,
textview text selection, entry selection {
  background-color: $accent;
  color: $selected;
}
label { color: inherit; }
label:disabled { color: $disabled_fg; }
label link, button.link { color: $accent; }
label link:hover, button.link:hover { color: $accent_hover; }
.dim-label { color: $muted; }
separator { min-width: 1px; min-height: 1px; background-color: $border; }
frame > border, .frame { border: 1px solid $border; border-radius: 3px; }
scrolledwindow > overshoot { background: none; }
scrolledwindow > junction { background-color: $bg; }

button, entry, spinbutton:not(.vertical), combobox > box > button {
  min-height: 24px;
  border: 1px solid $border;
  border-radius: 3px;
  padding: 3px 8px;
  color: $fg;
  background-color: $bg;
  background-image: none;
  box-shadow: none;
}
button:hover { background-color: $hover; }
button:active, button:checked { background-color: $pressed; border-color: $accent; }
button:disabled, entry:disabled { background-color: $disabled_bg; color: $disabled_fg; }
button:focus, entry:focus, spinbutton:focus { border-color: $accent; }
button.suggested-action { background-color: $accent; color: $selected; border-color: $accent; }
button.suggested-action:hover { background-color: $accent_hover; }
button.destructive-action { background-color: #c64141; border-color: #c64141; color: #ffffff; }
button.flat { border-color: transparent; background-color: transparent; }
button.flat:hover { background-color: $hover; }
button.flat:checked, button.flat:active { background-color: $pressed; border-color: $accent; }
button image { padding: 0; }
.linked > button, .linked > entry { border-radius: 0; }
.linked > button:first-child, .linked > entry:first-child {
  border-top-left-radius: 3px; border-bottom-left-radius: 3px;
}
.linked > button:last-child, .linked > entry:last-child {
  border-top-right-radius: 3px; border-bottom-right-radius: 3px;
}
entry { background-color: $base; caret-color: $fg; }
entry image { color: $muted; }
entry.error { border-color: @error_color; }
entry.warning { border-color: @warning_color; }
spinbutton entry { border: 0; background-color: $base; }
spinbutton button { min-width: 16px; min-height: 16px; padding: 0 4px; border: 0; }
combobox arrow { -gtk-icon-source: -gtk-icontheme("pan-down-symbolic"); min-width: 16px; min-height: 16px; }

check, radio {
  min-width: 16px; min-height: 16px; margin: 2px 4px;
  background-color: $base; border: 1px solid $border;
  color: $selected; -gtk-icon-source: none;
}
check { border-radius: 2px; }
radio { border-radius: 50%; }
check:hover, radio:hover { border-color: $accent; }
check:checked, radio:checked, check:indeterminate, radio:indeterminate {
  background-color: $accent; border-color: $accent;
}
check:checked { -gtk-icon-source: url("assets/check.svg"); }
radio:checked { -gtk-icon-source: url("assets/radio.svg"); }
check:indeterminate, radio:indeterminate { -gtk-icon-source: url("assets/dash.svg"); }
check:disabled, radio:disabled { opacity: 0.55; }
checkbutton, radiobutton { padding: 2px; }
switch {
  min-width: 38px; min-height: 20px;
  background-color: $trough; border: 1px solid $border; border-radius: 12px;
}
switch:checked { background-color: $accent; border-color: $accent; }
switch slider {
  min-width: 16px; min-height: 16px; margin: 2px;
  border-radius: 50%; background-color: $base; border: 1px solid $border;
}
switch:disabled { opacity: 0.55; }

notebook > header { background-color: $bg; padding: 2px; }
notebook > header > tabs > tab {
  padding: 6px 12px; margin: 1px; border: 1px solid transparent; border-radius: 3px;
}
notebook > header > tabs > tab:hover { background-color: $hover; }
notebook > header > tabs > tab:checked { background-color: $base; border-color: $border; }
notebook > stack { background-color: $base; }
notebook > header > tabs > arrow { min-width: 16px; min-height: 16px; color: $fg; }
list { background-color: $base; color: $fg; }
row { padding: 4px; }
row:hover { background-color: $hover; }
row:selected:hover { background-color: $accent_hover; color: $selected; }
treeview { -GtkTreeView-horizontal-separator: 4; -GtkTreeView-vertical-separator: 4; }
treeview.view header button { border-radius: 0; }
rubberband, .rubberband {
  border: 1px solid $accent; background-color: alpha($accent, 0.2);
}

menu, .menu, popover {
  background-color: $base; color: $fg; border: 1px solid $border;
  border-radius: 3px; padding: 4px; box-shadow: none;
}
menubar { background-color: $bg; padding: 2px; }
menuitem { padding: 5px 10px; border-radius: 2px; }
menuitem:hover { background-color: $accent; color: $selected; }
menuitem:disabled { color: $disabled_fg; }
menuitem arrow { min-width: 16px; min-height: 16px; -gtk-icon-source: -gtk-icontheme("pan-end-symbolic"); }
menu separator { margin: 4px 0; }
toolbar, .toolbar { background-color: $bg; padding: 4px; }
headerbar {
  background-color: $bg; color: $fg; padding: 4px 6px;
  border-bottom: 1px solid $border; box-shadow: none;
}
headerbar:backdrop { background-color: $inactive_bg; color: $inactive_fg; }
headerbar .title { font-weight: bold; }
headerbar .subtitle { color: $muted; font-size: smaller; }
statusbar { padding: 3px; }
infobar { background-color: $hover; color: $fg; }
infobar.error { border-bottom: 2px solid @error_color; }
infobar.warning { border-bottom: 2px solid @warning_color; }

scrollbar { background-color: $bg; }
scrollbar trough { background-color: $bg; }
scrollbar slider {
  min-width: 10px; min-height: 10px; margin: 2px;
  border: 1px solid $border; border-radius: 6px; background-color: $border;
}
scrollbar.vertical slider { min-height: 32px; }
scrollbar.horizontal slider { min-width: 32px; }
scrollbar slider:hover { background-color: $muted; }
scrollbar slider:active { background-color: $accent; }
scrollbar button { min-width: 0; min-height: 0; padding: 0; border: 0; }
scale { padding: 8px; }
scale trough, progressbar trough, levelbar trough {
  min-height: 6px; min-width: 6px; background-color: $trough;
  border: 1px solid $border; border-radius: 3px;
}
scale highlight, progressbar progress, levelbar block.filled {
  min-height: 6px; min-width: 6px; background-color: $accent; border-radius: 3px;
}
scale slider {
  min-height: 16px; min-width: 16px; margin: -6px;
  background-color: $base; border: 2px solid $accent; border-radius: 50%;
}
scale slider:hover { background-color: $hover; }
progressbar { padding: 2px; }
progressbar.vertical trough, progressbar.vertical progress { min-width: 6px; }
levelbar block { margin: 1px; }
levelbar block.empty { background-color: $trough; }
levelbar block.low { background-color: @warning_color; }
levelbar block.high, levelbar block.full { background-color: @success_color; }
spinner { -gtk-icon-source: -gtk-icontheme("process-working-symbolic"); }
spinner:checked { animation: nova-spin 1s linear infinite; }
@keyframes nova-spin { to { -gtk-icon-transform: rotate(1turn); } }

.tooltip, tooltip {
  background-color: $tooltip; color: $tooltip_fg;
  border: 1px solid $border; border-radius: 3px; padding: 5px;
}
tooltip label { color: $tooltip_fg; }
window decoration { box-shadow: none; border: 1px solid $border; border-radius: 3px; }
window.maximized decoration, window.fullscreen decoration { border-radius: 0; border-width: 0; }
.xfce4-panel { background-color: $bg; color: $fg; }
.xfce4-panel button { min-height: 0; min-width: 0; border-radius: 0; padding: 3px 6px; }
.xfce4-panel button:checked { background-color: $pressed; border-bottom: 2px solid $accent; }
#whiskermenu-window { background-color: $base; color: $fg; }
#whiskermenu-window entry { margin: 4px; }
XfdesktopIconView.view {
  background-color: transparent; color: #ffffff;
  -XfdesktopIconView-label-alpha: 60;
  -XfdesktopIconView-selected-label-alpha: 100;
}
XfdesktopIconView.view:selected { background-color: $accent; color: #ffffff; }
""")

GTK2 = Template("""gtk-color-scheme = "bg_color:$bg\\nfg_color:$fg\\nbase_color:$base\\ntext_color:$fg\\nselected_bg_color:$accent\\nselected_fg_color:$selected\\ntooltip_bg_color:$tooltip\\ntooltip_fg_color:$tooltip_fg"

style "nova-default" {
  font_name = "Sans 10"
  xthickness = 3
  ythickness = 3
  fg[NORMAL] = "$fg"
  fg[PRELIGHT] = "$fg"
  fg[ACTIVE] = "$fg"
  fg[SELECTED] = "$selected"
  fg[INSENSITIVE] = "$disabled_fg"
  bg[NORMAL] = "$bg"
  bg[PRELIGHT] = "$hover"
  bg[ACTIVE] = "$pressed"
  bg[SELECTED] = "$accent"
  bg[INSENSITIVE] = "$disabled_bg"
  base[NORMAL] = "$base"
  base[PRELIGHT] = "$base"
  base[ACTIVE] = "$pressed"
  base[SELECTED] = "$accent"
  base[INSENSITIVE] = "$disabled_bg"
  text[NORMAL] = "$fg"
  text[PRELIGHT] = "$fg"
  text[ACTIVE] = "$fg"
  text[SELECTED] = "$selected"
  text[INSENSITIVE] = "$disabled_fg"
  GtkWidget::focus-line-width = 1
  GtkWidget::focus-padding = 2
  GtkButton::default-border = { 0, 0, 0, 0 }
  GtkButton::inner-border = { 4, 4, 2, 2 }
  GtkButton::child-displacement-x = 0
  GtkButton::child-displacement-y = 0
  GtkEntry::inner-border = { 4, 4, 3, 3 }
  GtkRange::trough-border = 1
  GtkRange::slider-width = 12
  GtkRange::stepper-size = 0
  GtkScrollbar::min-slider-length = 32
  GtkScrollbar::has-backward-stepper = 0
  GtkScrollbar::has-forward-stepper = 0
  GtkCheckButton::indicator-size = 16
  GtkCheckButton::indicator-spacing = 4
  GtkMenu::horizontal-padding = 4
  GtkMenu::vertical-padding = 4
  GtkTreeView::horizontal-separator = 4
  GtkTreeView::vertical-separator = 4
}
class "*" style "nova-default"

style "nova-menu" = "nova-default" {
  xthickness = 2
  ythickness = 3
  bg[NORMAL] = "$base"
  bg[PRELIGHT] = "$accent"
  fg[PRELIGHT] = "$selected"
}
widget_class "*<GtkMenu>*" style "nova-menu"

style "nova-tooltip" = "nova-default" {
  bg[NORMAL] = "$tooltip"
  fg[NORMAL] = "$tooltip_fg"
}
widget "gtk-tooltip*" style "nova-tooltip"

style "nova-panel" = "nova-default" {
  xthickness = 1
  ythickness = 1
}
widget "*PanelWidget*" style "nova-panel"
widget "*PanelApplet*" style "nova-panel"
""")


def xpm(relative, pixels):
    height, width = len(pixels), len(pixels[0])
    assert all(len(row) == width for row in pixels)
    colors = list(dict.fromkeys(color for row in pixels for color in row))
    symbols = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    assert len(colors) <= len(symbols)
    palette = dict(zip(colors, symbols))
    lines = [f"{width} {height} {len(colors)} 1"]
    lines += [f"{palette[color]} c {color}" for color in colors]
    lines += ["".join(palette[color] for color in row) for row in pixels]
    name = Path(relative).stem.replace("-", "_")
    emit(relative, "/* XPM */\nstatic char *" + name + "[] = {\n" +
         ",\n".join('"' + line + '"' for line in lines) + "\n};\n")


def canvas(width, height, color):
    return [[color] * width for _ in range(height)]


def line(pixels, x0, y0, x1, y1, color):
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx, sy = 1 if x0 < x1 else -1, 1 if y0 < y1 else -1
    error = dx + dy
    while True:
        pixels[y0][x0] = color
        if (x0, y0) == (x1, y1):
            break
        twice = 2 * error
        if twice >= dy:
            error += dy
            x0 += sx
        if twice <= dx:
            error += dx
            y0 += sy


def rectangle(pixels, x0, y0, x1, y1, color):
    line(pixels, x0, y0, x1, y0, color)
    line(pixels, x0, y1, x1, y1, color)
    line(pixels, x0, y0, x0, y1, color)
    line(pixels, x1, y0, x1, y1, color)


def frame_assets(theme, p):
    dest = f"themes/{theme}/xfwm4/"
    for state in ("active", "inactive"):
        bg = p["bg"] if state == "active" else p["inactive_bg"]
        border = p["border"]
        for number in range(1, 6):
            pixels = canvas(2, 32, bg)
            line(pixels, 0, 0, 1, 0, border)
            xpm(dest + f"title-{number}-{state}.xpm", pixels)
        for side in ("left", "right"):
            outer = 0 if side == "left" else 4
            pixels = canvas(5, 32, bg)
            line(pixels, 0, 0, 4, 0, border)
            line(pixels, outer, 0, outer, 31, border)
            xpm(dest + f"top-{side}-{state}.xpm", pixels)
            pixels = canvas(3, 2, bg)
            outer = 0 if side == "left" else 2
            line(pixels, outer, 0, outer, 1, border)
            xpm(dest + f"{side}-{state}.xpm", pixels)
            pixels = canvas(5, 3, bg)
            line(pixels, 0, 2, 4, 2, border)
            outer = 0 if side == "left" else 4
            line(pixels, outer, 0, outer, 2, border)
            xpm(dest + f"bottom-{side}-{state}.xpm", pixels)
        pixels = canvas(2, 3, bg)
        line(pixels, 0, 2, 1, 2, border)
        xpm(dest + f"bottom-{state}.xpm", pixels)

    for button in ("close", "hide", "maximize", "menu", "shade", "stick"):
        toggles = (False, True) if button in ("maximize", "shade", "stick") else (False,)
        for toggled in toggles:
            for state in ("active", "inactive", "prelight", "pressed"):
                bg = {"active": p["bg"], "inactive": p["inactive_bg"],
                      "prelight": p["hover"], "pressed": p["pressed"]}[state]
                fg = p["inactive_fg"] if state == "inactive" else p["fg"]
                if button == "close" and state in ("prelight", "pressed"):
                    bg = "#d94a48" if state == "prelight" else "#b83b39"
                    fg = "#ffffff"
                pixels = canvas(36, 26, bg)
                if button == "close":
                    for offset in (0, 1):
                        line(pixels, 12, 7 + offset, 22, 17 + offset, fg)
                        line(pixels, 22, 7 + offset, 12, 17 + offset, fg)
                elif button == "hide":
                    line(pixels, 12, 16, 23, 16, fg)
                    line(pixels, 12, 17, 23, 17, fg)
                elif button == "maximize":
                    if toggled:
                        rectangle(pixels, 15, 7, 24, 14, fg)
                        for y in range(10, 18):
                            for x in range(12, 22):
                                pixels[y][x] = bg
                        rectangle(pixels, 12, 10, 21, 17, fg)
                        line(pixels, 13, 11, 20, 11, fg)
                    else:
                        rectangle(pixels, 12, 7, 23, 18, fg)
                        line(pixels, 13, 8, 22, 8, fg)
                elif button == "menu":
                    for y in (8, 12, 16):
                        line(pixels, 12, y, 23, y, fg)
                elif button == "shade":
                    line(pixels, 12, 7, 23, 7, fg)
                    if toggled:
                        line(pixels, 13, 11, 18, 16, fg)
                        line(pixels, 18, 16, 23, 11, fg)
                    else:
                        line(pixels, 13, 16, 18, 11, fg)
                        line(pixels, 18, 11, 23, 16, fg)
                elif button == "stick":
                    rectangle(pixels, 15, 7, 21, 11, fg)
                    line(pixels, 13, 13, 23, 13, fg)
                    line(pixels, 18, 11, 18, 19, fg)
                    if toggled:
                        line(pixels, 12, 19, 24, 7, fg)
                suffix = "toggled-" if toggled else ""
                xpm(dest + f"{button}-{suffix}{state}.xpm", pixels)
    emit(dest + "themerc", f"""active_text_color={p['fg']}
inactive_text_color={p['inactive_fg']}
active_text_shadow_color={p['bg']}
inactive_text_shadow_color={p['inactive_bg']}
button_offset=3
button_spacing=0
full_width_title=true
frame_border_top=3
maximized_offset=3
show_app_icon=false
title_alignment=left
title_horizontal_offset=8
title_vertical_offset_active=0
title_vertical_offset_inactive=0
title_shadow_active=false
title_shadow_inactive=false
shadow_opacity=0
""")


GLYPHS = {
    "check": '<path d="M3 8l3 3 7-7" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
    "radio": '<circle cx="8" cy="8" r="4" fill="#fff"/>',
    "dash": '<path d="M4 8h8" stroke="#fff" stroke-width="2" stroke-linecap="round"/>',
}

ICONS = {
    ("apps", "nova-start"): ('Nova applications', '<rect x="3" y="3" width="42" height="42" rx="10" fill="#2467ac"/><path d="M14 34V14h5l10 14V14h5v20h-5L19 20v14z" fill="#fff"/>'),
    ("apps", "system-file-manager"): ('File manager', '<path d="M4 13a4 4 0 0 1 4-4h11l5 5h16a4 4 0 0 1 4 4v19a4 4 0 0 1-4 4H8a4 4 0 0 1-4-4z" fill="#bd7a24"/><path d="M4 20h40v17a4 4 0 0 1-4 4H8a4 4 0 0 1-4-4z" fill="#efbb66"/><path d="M8 24h32" stroke="#fff" stroke-opacity=".6" stroke-width="2"/>'),
    ("apps", "nova-web"): ('Web browser', '<circle cx="24" cy="24" r="20" fill="#2467ac"/><g fill="none" stroke="#fff" stroke-width="2"><circle cx="24" cy="24" r="15"/><ellipse cx="24" cy="24" rx="7" ry="15"/><path d="M9 24h30M12 16h24M12 32h24"/></g>'),
    ("places", "user-desktop"): ('Desktop', '<rect x="3" y="5" width="42" height="29" rx="3" fill="#526174"/><rect x="6" y="8" width="36" height="22" rx="1" fill="#2467ac"/><path d="M6 26l12-10 8 6 8-8 8 12v4H6z" fill="#7fafd0"/><path d="M21 34h6v6h8v3H13v-3h8z" fill="#526174"/>'),
}


def icon_assets():
    directories = []
    sections = []
    for size in (16, 22, 24, 32, 48, 64, None):
        for context in ("apps", "places"):
            directory = (f"{size}x{size}" if size else "scalable") + "/" + context
            directories.append(directory)
            if size:
                sections.append(f"[{directory}]\nSize={size}\nContext={'Applications' if context == 'apps' else 'Places'}\nType=Fixed\n")
            else:
                sections.append(f"[{directory}]\nSize=48\nContext={'Applications' if context == 'apps' else 'Places'}\nType=Scalable\nMinSize=16\nMaxSize=512\n")
            for (icon_context, name), (title, paths) in ICONS.items():
                if context == icon_context:
                    dimension = size or 48
                    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{dimension}" height="{dimension}" viewBox="0 0 48 48"><title>{title}</title>{paths}</svg>\n'
                    emit(f"icons/Nova/{directory}/{name}.svg", svg)
    emit("icons/Nova/index.theme", "[Icon Theme]\nName=Nova\nComment=Original Nova additions with standard icon fallbacks\nInherits=Adwaita,hicolor\nDirectories=" + ",".join(directories) + "\n\n" + "\n".join(sections))


def main():
    for theme, palette in PALETTES.items():
        emit(f"themes/{theme}/gtk-3.0/gtk.css", GTK3.substitute(palette))
        if theme == "Nova-Dark":
            emit(f"themes/{theme}/gtk-3.0/gtk-dark.css", '@import url("gtk.css");\n')
        emit(f"themes/{theme}/gtk-2.0/gtkrc", GTK2.substitute(palette))
        for name, paths in GLYPHS.items():
            emit(f"themes/{theme}/gtk-3.0/assets/{name}.svg", '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">' + paths + '</svg>\n')
        frame_assets(theme, palette)
        emit(f"themes/{theme}/index.theme", f"[Desktop Entry]\nType=X-GNOME-Metatheme\nName={theme}\nComment=Original lightweight Nova desktop theme\n\n[X-GNOME-Metatheme]\nGtkTheme={theme}\nIconTheme=Nova\nCursorTheme=Adwaita\n")
    icon_assets()
    print("Generated two GTK2/GTK3/XFWM4 themes, 120 text XPM assets and 28 SVG icons.")


if __name__ == "__main__":
    main()
