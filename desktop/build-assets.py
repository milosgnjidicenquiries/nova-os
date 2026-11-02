#!/usr/bin/env python3
from pathlib import Path
from string import Template

ROOT = Path(__file__).resolve().parent


def emit(relative, content):
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


# Flat surfaces with a tinted selection follow the Windows 11 visual language. Real Mica
# needs a compositor, so each surface carries the wallpaper tint instead of a blur.
PALETTES = {
    "Nova": dict(bg="#f3f3f3", fg="#1b1b1b", base="#ffffff", muted="#616161",
                 border="#e0e0e0", hover="#eaeaea", pressed="#dcdcdc",
                 accent="#0067c0", accent_hover="#1975c4", selected="#ffffff",
                 disabled_bg="#f5f5f5", disabled_fg="#a0a0a0", trough="#e5e5e5",
                 inactive_bg="#f9f9f9", inactive_fg="#8a8a8a", tooltip="#ffffff",
                 tooltip_fg="#1b1b1b", panel="#f3f3f3", tint="0.22"),
    "Nova-Dark": dict(bg="#202020", fg="#ffffff", base="#272727", muted="#cfcfcf",
                      border="#3d3d3d", hover="#2e2e2e", pressed="#383838",
                      accent="#4cc2ff", accent_hover="#62ccff", selected="#000000",
                      disabled_bg="#2e2e2e", disabled_fg="#757575", trough="#333333",
                      inactive_bg="#262626", inactive_fg="#a5a5a5", tooltip="#2b2b2b",
                      tooltip_fg="#ffffff", panel="#1c1c1c", tint="0.28"),
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
  outline-color: alpha($fg, 0.8);
  outline-style: solid;
  outline-width: 2px;
  outline-offset: -4px;
  -gtk-outline-radius: 2px;
  -gtk-secondary-caret-color: $accent;
}
.background { background-color: $bg; color: $fg; }
*:disabled { color: $disabled_fg; }
*:backdrop { -gtk-icon-effect: dim; }
.view, textview text, iconview { background-color: $base; color: $fg; }
textview border { background-color: $bg; }
selection, .view:selected, row:selected, iconview:selected,
textview text selection, entry selection {
  background-color: alpha($accent, $tint);
  color: $fg;
}
selection:backdrop, .view:selected:backdrop, row:selected:backdrop {
  background-color: alpha($inactive_fg, $tint);
  color: $fg;
}
label { color: inherit; }
label:disabled { color: $disabled_fg; }
label link, button.link { color: $accent; }
label link:hover, button.link:hover { color: $accent_hover; }
.dim-label { color: $muted; }
separator { min-width: 1px; min-height: 1px; background-color: $border; }
frame > border, .frame { border: 1px solid $border; border-radius: 8px; }
scrolledwindow > overshoot { background: none; }
scrolledwindow > junction { background-color: $bg; }

button, entry, spinbutton:not(.vertical), combobox > box > button {
  min-height: 24px;
  border: 1px solid $border;
  border-radius: 4px;
  padding: 4px 10px;
  color: $fg;
  background-color: $base;
  background-image: none;
  box-shadow: none;
  text-shadow: none;
}
button:hover { background-color: $hover; }
button:active, button:checked { background-color: $pressed; border-color: alpha($fg, 0.4); }
button:disabled, entry:disabled { background-color: $disabled_bg; color: $disabled_fg; }
button:focus-visible, entry:focus, spinbutton:focus { border-color: alpha($fg, 0.45); }
button.suggested-action { background-color: $accent; color: $selected; border-color: $accent; }
button.suggested-action:hover { background-color: $accent_hover; }
button.default { background-color: $accent; color: $selected; border-color: $accent; }
button.default:hover { background-color: $accent_hover; }
button.destructive-action { background-color: #c64141; border-color: #c64141; color: #ffffff; }
button.flat { border-color: transparent; background-color: transparent; }
button.flat:hover { background-color: $hover; }
button.flat:checked, button.flat:active { background-color: $pressed; border-color: transparent; }
button image { padding: 0; }
.linked > button, .linked > entry { border-radius: 0; }
.linked > button:first-child, .linked > entry:first-child {
  border-top-left-radius: 4px; border-bottom-left-radius: 4px;
}
.linked > button:last-child, .linked > entry:last-child {
  border-top-right-radius: 4px; border-bottom-right-radius: 4px;
}
entry { background-color: $base; caret-color: $fg; }
// Windows 11 marks a focused text box with an accent underline instead of a glow.
entry:focus { box-shadow: inset 0 -2px 0 $accent; }
entry image { color: $muted; }
entry.error { border-color: @error_color; }
entry.warning { border-color: @warning_color; }
spinbutton entry { border: 0; background-color: $base; }
spinbutton button { min-width: 16px; min-height: 16px; padding: 0 4px; border: 0; color: $muted; }
spinbutton button.up { border-bottom: 1px solid $border; }
spinbutton button:hover { color: $fg; background-color: $hover; }
combobox arrow { -gtk-icon-source: -gtk-icontheme("pan-down-symbolic"); min-width: 16px; min-height: 16px; }

check, radio {
  min-width: 16px; min-height: 16px; margin: 2px 6px;
  background-color: $base; border: 1px solid alpha($fg, 0.45);
  color: $selected; -gtk-icon-source: none;
}
check { border-radius: 4px; }
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
  min-width: 40px; min-height: 20px;
  background-color: $base; border: 1px solid alpha($fg, 0.45); border-radius: 10px;
}
switch:checked { background-color: $accent; border-color: $accent; }
switch slider {
  min-width: 12px; min-height: 12px; margin: 3px;
  border-radius: 50%; background-color: alpha($fg, 0.8); border: 0;
}
switch:checked slider { background-color: $selected; }
switch:disabled { opacity: 0.55; }

notebook > header { background-color: $bg; padding: 2px; }
notebook > header.top { border-bottom: 1px solid $border; }
notebook > header.bottom { border-top: 1px solid $border; }
notebook > header.left { border-right: 1px solid $border; }
notebook > header.right { border-left: 1px solid $border; }
notebook > header > tabs > tab {
  padding: 6px 12px; margin: 1px; border: 1px solid transparent; border-radius: 4px;
  font-weight: normal;
}
notebook > header > tabs > tab:hover { background-color: $hover; }
notebook > header > tabs > tab:checked {
  background-color: $base; border-color: transparent;
  border-bottom: 3px solid $accent; border-radius: 4px 4px 0 0;
}
notebook > stack { background-color: $base; }
notebook > header > tabs > arrow { min-width: 16px; min-height: 16px; color: $fg; }
list { background-color: $base; color: $fg; }
row { padding: 6px; }
row:hover { background-color: $hover; }
row:selected:hover { background-color: alpha($accent, 0.32); color: $fg; }
treeview { -GtkTreeView-horizontal-separator: 4; -GtkTreeView-vertical-separator: 4; }
// File-manager column headers read as a flat strip with dividers, like Windows 11 Explorer.
treeview.view header button {
  padding: 6px 8px; border: 0; border-right: 1px solid $border;
  border-radius: 0; background-color: $bg; color: $muted;
}
treeview.view header button:last-child { border-right: 0; }
treeview.view header button:hover { background-color: $hover; color: $fg; }
treeview.view header button sortindicator, treeview.view header button indicator {
  color: $muted; -gtk-icon-size: 12px;
}
sidebar, .sidebar { background-color: $bg; }
sidebar > row { padding: 5px 8px; margin: 1px 4px; border-radius: 4px; }
sidebar row:hover { background-color: $hover; }
sidebar row:selected { background-color: alpha($accent, $tint); color: $fg; }
rubberband, .rubberband {
  border: 1px solid $accent; background-color: alpha($accent, 0.16);
}

menu, .menu, popover {
  background-color: $base; color: $fg; border: 1px solid $border;
  border-radius: 8px; padding: 4px; box-shadow: none;
}
menubar { background-color: $bg; padding: 2px; }
menuitem { padding: 7px 12px; border-radius: 4px; }
menuitem:hover { background-color: $hover; color: $fg; }
menuitem:disabled { color: $disabled_fg; }
menuitem accelerator { color: $muted; }
menuitem arrow { min-width: 16px; min-height: 16px; -gtk-icon-source: -gtk-icontheme("pan-end-symbolic"); }
menu separator { margin: 4px 0; }
toolbar, .toolbar { background-color: $bg; padding: 4px; }
headerbar {
  min-height: 32px;
  background-color: $bg; color: $fg; padding: 4px 8px;
  border: 0; box-shadow: none;
}
headerbar:backdrop { background-color: $inactive_bg; color: $inactive_fg; }
headerbar .title { font-weight: bold; }
headerbar .subtitle { color: $muted; font-size: smaller; }
headerbar button { min-height: 24px; padding: 2px 8px; }
// Windows 11 turns the caption close button red; the shape stays a flat square.
headerbar button.titlebar.close:hover, headerbar button.close:hover,
window decoration button.close:hover { background-color: #c42b1c; border-color: #c42b1c; color: #ffffff; }
headerbar button.titlebar.close:active, headerbar button.close:active { background-color: #ac2718; }
statusbar { padding: 3px; }
infobar { background-color: $hover; color: $fg; border-radius: 0; }
infobar > revealer > box { padding: 8px 12px; border-bottom: 1px solid $border; }
infobar.error > revealer > box { background-color: alpha(@error_color, 0.14); border-bottom: 2px solid @error_color; }
infobar.warning > revealer > box { background-color: alpha(@warning_color, 0.14); border-bottom: 2px solid @warning_color; }
infobar.question > revealer > box, infobar.other > revealer > box { background-color: alpha($accent, $tint); }

scrollbar { background-color: transparent; }
scrollbar trough { background-color: transparent; border: 0; }
scrollbar slider {
  min-width: 6px; min-height: 6px; margin: 2px;
  border: 0; border-radius: 4px; background-color: alpha($fg, 0.35);
}
scrollbar.vertical slider { min-height: 32px; }
scrollbar.horizontal slider { min-width: 32px; }
// The thumb thickens under the pointer instead of the trough changing size.
scrollbar.vertical slider:hover { min-width: 8px; }
scrollbar.horizontal slider:hover { min-height: 8px; }
scrollbar slider:hover { background-color: alpha($fg, 0.55); }
scrollbar slider:active { background-color: $accent; }
scrollbar button { min-width: 0; min-height: 0; padding: 0; border: 0; }
scale { padding: 8px; }
scale trough, progressbar trough, levelbar trough {
  min-height: 4px; min-width: 4px; background-color: $trough;
  border: 0; border-radius: 2px;
}
scale highlight, progressbar progress, levelbar block.filled {
  min-height: 4px; min-width: 4px; background-color: $accent; border-radius: 2px;
}
scale slider {
  min-height: 12px; min-width: 12px; margin: -6px;
  background-color: $accent; border: 4px solid $accent; border-radius: 50%;
}
scale slider:hover { background-color: $accent_hover; border-color: $accent_hover; }
progressbar { padding: 2px; }
progressbar.vertical trough, progressbar.vertical progress { min-width: 4px; }
levelbar block { margin: 1px; }
levelbar block.empty { background-color: $trough; }
levelbar block.low { background-color: @warning_color; }
levelbar block.high, levelbar block.full { background-color: @success_color; }
spinner { -gtk-icon-source: -gtk-icontheme("process-working-symbolic"); }
spinner:checked { animation: nova-spin 1s linear infinite; }
@keyframes nova-spin { to { -gtk-icon-transform: rotate(1turn); } }

.tooltip, tooltip {
  background-color: $tooltip; color: $tooltip_fg;
  border: 1px solid $border; border-radius: 8px; padding: 8px;
  box-shadow: none;
}
tooltip label { color: $tooltip_fg; }
window decoration {
  box-shadow: none; border: 1px solid $border; border-radius: 8px;
  margin: 0;
}
window.maximized decoration, window.fullscreen decoration { border-radius: 0; border-width: 0; }
.xfce4-panel { background-color: $panel; color: $fg; border-top: 1px solid $border; }
.xfce4-panel button {
  min-height: 0; min-width: 0; padding: 4px 6px;
  margin: 6px 2px; border: 1px solid transparent; border-radius: 4px;
  background-color: transparent;
}
.xfce4-panel button:hover { background-color: alpha($fg, 0.07); }
.xfce4-panel button:checked {
  background-color: alpha($fg, 0.07); border-color: transparent;
  border-bottom: 3px solid $accent;
}
.xfce4-panel button:active { background-color: alpha($fg, 0.12); }
#tasklist button label { font-size: smaller; }
#whiskermenu-window { background-color: $base; color: $fg; border-radius: 8px; }
#whiskermenu-window entry { margin: 6px; }
#whiskermenu-window button { border: 0; background-color: transparent; border-radius: 4px; }
#whiskermenu-window button:hover { background-color: $hover; }
#whiskermenu-window button:checked, #whiskermenu-window button:active { background-color: alpha($accent, $tint); }
#whiskermenu-window treeview { background-color: $base; color: $fg; }
#whiskermenu-window treeview:selected { background-color: alpha($accent, $tint); color: $fg; }
XfdesktopIconView.view {
  background-color: transparent; color: #ffffff;
  -XfdesktopIconView-label-alpha: 60;
  -XfdesktopIconView-selected-label-alpha: 100;
}
XfdesktopIconView.view:selected { background-color: alpha($accent, 0.5); color: #ffffff; }
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
  GtkWidget::focus-padding = 0
  GtkButton::default-border = { 0, 0, 0, 0 }
  GtkButton::interior-focus = 1
  GtkButton::default-outstanding = 0
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
  GtkMenuItem::arrow-scaling = 0.7
  GtkMenuItem::horizontal-padding = 4
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


def center_in(pixels, width, color):
    """Widen a drawn glyph strip to a caption-button cell, keeping the art centred."""
    source = len(pixels[0])
    if width == source:
        return pixels
    offset = (width - source) // 2
    widened = [[color] * width for _ in range(len(pixels))]
    for y, row in enumerate(pixels):
        for x, value in enumerate(row):
            widened[y][offset + x] = value
    return widened


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
                glyph = canvas(36, 32, bg)
                if button == "close":
                    for step in (0, 1):
                        line(glyph, 12, 11 + step, 22, 21 + step, fg)
                        line(glyph, 22, 11 + step, 12, 21 + step, fg)
                elif button == "hide":
                    line(glyph, 12, 20, 23, 20, fg)
                    line(glyph, 12, 21, 23, 21, fg)
                elif button == "maximize":
                    if toggled:
                        rectangle(glyph, 15, 11, 24, 18, fg)
                        for y in range(14, 22):
                            for x in range(12, 22):
                                glyph[y][x] = bg
                        rectangle(glyph, 12, 14, 21, 21, fg)
                        line(glyph, 13, 15, 20, 15, fg)
                    else:
                        rectangle(glyph, 12, 11, 23, 22, fg)
                        line(glyph, 13, 12, 22, 12, fg)
                elif button == "menu":
                    for y in (12, 16, 20):
                        line(glyph, 12, y, 23, y, fg)
                elif button == "shade":
                    line(glyph, 12, 11, 23, 11, fg)
                    if toggled:
                        line(glyph, 13, 15, 18, 20, fg)
                        line(glyph, 18, 20, 23, 15, fg)
                    else:
                        line(glyph, 13, 20, 18, 15, fg)
                        line(glyph, 18, 15, 23, 20, fg)
                elif button == "stick":
                    rectangle(glyph, 15, 11, 21, 15, fg)
                    line(glyph, 13, 17, 23, 17, fg)
                    line(glyph, 18, 15, 18, 23, fg)
                    if toggled:
                        line(glyph, 12, 23, 24, 11, fg)
                suffix = "toggled-" if toggled else ""
                # 46x32 is the Windows 11 caption cell; the glyphs stay at their drawn size.
                xpm(dest + f"{button}-{suffix}{state}.xpm", center_in(glyph, 46, bg))
    emit(dest + "themerc", f"""active_text_color={p['fg']}
inactive_text_color={p['inactive_fg']}
active_text_shadow_color={p['bg']}
inactive_text_shadow_color={p['inactive_bg']}
button_offset=2
button_spacing=0
full_width_title=true
frame_border_top=0
maximized_offset=2
show_app_icon=false
title_alignment=left
title_horizontal_offset=10
title_vertical_offset_active=0
title_vertical_offset_inactive=0
title_shadow_active=false
title_shadow_inactive=false
shadow_opacity=0
rounded_corner_radius_top=8
rounded_corner_radius_bot=8
""")


GLYPHS = {
    "check": '<path d="M3 8l3 3 7-7" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
    "radio": '<circle cx="8" cy="8" r="4" fill="#fff"/>',
    "dash": '<path d="M4 8h8" stroke="#fff" stroke-width="2" stroke-linecap="round"/>',
}

ICONS = {
    ("apps", "nova-start"): ('Nova applications', '<g fill="#0067c0"><rect x="4" y="4" width="18" height="18" rx="3"/><rect x="26" y="4" width="18" height="18" rx="3"/><rect x="4" y="26" width="18" height="18" rx="3"/><rect x="26" y="26" width="18" height="18" rx="3"/></g>'),
    ("apps", "system-file-manager"): ('File manager', '<path d="M4 13a4 4 0 0 1 4-4h11l5 5h16a4 4 0 0 1 4 4v19a4 4 0 0 1-4 4H8a4 4 0 0 1-4-4z" fill="#bd7a24"/><path d="M4 20h40v17a4 4 0 0 1-4 4H8a4 4 0 0 1-4-4z" fill="#efbb66"/><path d="M8 24h32" stroke="#fff" stroke-opacity=".6" stroke-width="2"/>'),
    ("apps", "nova-web"): ('Web browser', '<circle cx="24" cy="24" r="20" fill="#0067c0"/><g fill="none" stroke="#fff" stroke-width="2"><circle cx="24" cy="24" r="15"/><ellipse cx="24" cy="24" rx="7" ry="15"/><path d="M9 24h30M12 16h24M12 32h24"/></g>'),
    ("places", "user-desktop"): ('Desktop', '<rect x="3" y="5" width="42" height="29" rx="4" fill="#5f5f5f"/><rect x="6" y="8" width="36" height="22" rx="2" fill="#0067c0"/><path d="M6 26l12-10 8 6 8-8 8 12v4H6z" fill="#7fb8e6"/><path d="M21 34h6v6h8v3H13v-3h8z" fill="#5f5f5f"/>'),
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
