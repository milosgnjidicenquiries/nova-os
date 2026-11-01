# QA i benchmark plan

## Status faza

1–7: izvor i implementacioni alati; lokalne provere ne zamenjuju Linux integraciju.
8: Linux ISO build još nije izvršen.
9: VM boot/instalacija čekaju ISO.
10: fizički USB postupak pripremljen, nije izvršen.
11: 1 GB hardverski benchmark nije izvršen.
12: razvojna dokumentacija pripremljena; release approval čeka stvarnu QA.

## Matrica

| Cilj | Režim | Obavezna provera |
|---|---|---|
| Dual-core Celeron oko 2008, 1 GB, Intel iGPU, SATA HDD | BIOS | CPU flags, live boot, mogućnost instalacije, instalirana idle sesija i lagani app |
| 2 GB stari x86-64 | BIOS + UEFI gde postoji | Installer, browser, paket/update, OOM/pressure |
| 4 GB x86-64 | BIOS/UEFI | Desktop, sleep/resume, opcioni Wine |
| Moderan Intel/AMD x86-64 | UEFI + zasebno Secure Boot | Novi Wi-Fi/grafika, storage, recovery kernel |

Svako polje trenutno: **NIJE TESTIRANO**. Ne popunjavati PASS na osnovu XML ili mock testova.

## Redosled

1. Proverena SHA256 i potpis upstream source-a.
2. Uspešan dpkg/APT audit i ISO structural verify.
3. 1/2/4 GB QEMU BIOS live boot; potom UEFI.
4. Potpuna instalacija na NOV virtuelni disk; reboot bez ISO-a.
5. Isti smoke-test na fizičkom USB-u bez promene diska.
6. Potvrđena instalacija na namenski prazni test HDD/SSD.
7. Benchmark instaliranog 1 GB računara i regresije posle update-a.

## Golden path i rubni slučajevi

- Boot: BIOS, UEFI, prazan/nepodržan medij, nema mreže, OOM na 1 GB; evidentirati poruku i kernel log.
- Login: LightDM, novi korisnik, postojeći korisnik, prvi i naredni login; vodič samo prvi put.
- Desktop: Start pretraga, pinned launcheri, tasklist, systray, clock/calendar, battery/no battery, context menus, rezolucija i dva monitora.
- Teme: svetla/tamna, compositor ostaje off; GTK2/GTK3 widgets, modalni dijalozi, disabled/selected/focus i skaliranje fontova.
- I/O: kopiranje fajla, arhiva, PDF, screenshot, tastatura/miš, USB mount/unmount, printer kada dostupan.
- Mreža/audio: Ethernet, realni Wi-Fi chipset, DHCP, audio input/output, Bluetooth samo gde postoji.
- Browser: jedna osnovna web stranica, 1/3/5 kartica, HTTPS, CPU/memory pressure; ne oceniti samo prazni browser.
- Paketi: potpisani install/update, offline fail, nedostupna verzija lock-a; bez dodavanja drugog release repoa.
- Firewall: stvarni `ufw status verbose`, incoming blocked/outgoing allowed; bez isključivanja security radi rezultata.
- Power: shutdown/reboot, sleep/resume, stari HDD, AC/battery.
- Compatibility: eksplicitni cancel ništa ne instalira; i386 samo potvrđeni izbor; legacy 32/64-bit program u odvojenim prefixes; nekompatibilan program daje korisnu grešku; prefix remove/restore; root odbijen.
- Bottles: odsutan Flatpak/remote, system-only remote, validan user remote; bez tihog remote-add.
- Steam/Proton: samo opciono na odgovarajućem test hardveru; Vulkan/anti-cheat kompatibilnost nije zaključena po PCI nazivu.

## Merenje

Na instaliranom sistemu, sa poznatim paketima i kernelom, sačekati 120 sekundi posle login-a; prvo merenje bez otvorenog browsera i Compatibility Center-a. Sačuvati tri ponovljena rezultata:

```sh
nova-hardware > hardware.json
nova-benchmark --output benchmark-idle-1.json
nova-benchmark --output benchmark-idle-2.json
nova-benchmark --output benchmark-idle-3.json
```

Zabeležiti MemTotal, MemAvailable i razliku u MiB; razlika je standardna procena zauzete memorije, ne zbir RSS-a. RSS shared pages mogu biti prebrojane. CPU uzorak je agregat za 5 sekundi. `systemd-analyze time` nije ukupno vreme do spremnog desktopa: zasebno meriti boot/login/otvaranje Thunar-a spoljnim štopericom.

Zatim isto pri otvaranju browsera/stranice, PDF-a i lakog legacy Windows programa. Sačuvati `zramctl`, `swapon --show`, `systemctl --failed`, `journalctl -b -p warning`, kernel i package lock. Logovi mogu sadržati privatne podatke; pregledati pre deljenja.

Cilj 250–400 MB idle RAM-a, mali CPU i udobna responzivnost su kriterijumi istraživanja. Ako rezultat odstupa, prijaviti stvaran rezultat, uzrok i naredni mali zahvat; ne uklanjati essential servise zbog broja. TCG/live squashfs merenje nije fizički instalirani HDD benchmark.

## Release gate

Nema javne tvrdnje o funkcionalnom ISO-u dok nema BIOS i UEFI boot-a, potvrđene instalacije i stvarnih testova izveštaja. Secure Boot, 1 GB usability i pojedinačni drajveri moraju biti posebno označeni. Pravna provera firmware/copyright-a, zahtevan source-code pristup i Nova release potpis su dodatni gate-ovi.
