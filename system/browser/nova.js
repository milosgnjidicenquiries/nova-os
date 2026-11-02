// Nova OS browser defaults, installed as defaults/preferences/00-nova.js next to the
// Firefox binary. These are default values, not locks: the user can change anything here.
// Chosen for the 1 GB target and for GPUs without usable acceleration, such as the
// Radeon HD 3450; site isolation, passwords, history and updates are left untouched.

// Each content process costs tens of MB. Two is enough for a small window count while
// keeping cross-site isolation on.
pref("dom.ipc.processCount", 2);

// Page-cache viewers hold rendered documents alive; two keeps Back/Forward usable
// without the default auto-scaled pool.
pref("browser.sessionhistory.max_total_viewers", 2);

// Compact density shows more content in the 1366x768 panels these machines have.
pref("browser.uidensity", 1);

// Software paths are steadier than the r600/GL acceleration route on this hardware.
pref("layers.acceleration.disabled", true);
pref("gfx.canvas.accelerated", false);

// Background reporting and the sponsored/discovery feeds cost CPU, RAM and bandwidth.
pref("datareporting.policy.dataSubmissionEnabled", false);
pref("datareporting.healthreport.uploadEnabled", false);
pref("toolkit.telemetry.archive.enabled", false);
pref("app.shield.optoutstudies.enabled", false);
pref("extensions.pocket.enabled", false);
pref("browser.newtabpage.activity-stream.feeds.systemtopstories", false);
pref("browser.urlbar.quicksuggest.enabled", false);
