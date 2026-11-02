# Tehnička arhitektura

## Izbor osnove — provera 2026-10-29

Zvanično najnovije izdanje je Mint 22.3. Podržani su i 21.x (do aprila 2027) i 22.x (do aprila 2029). Mint navodi XFCE kao najlakši desktop, ali nema zvaničnih uporednih RAM merenja kojima bi se dokazalo najlakše konkretno izdanje. 21.3 koristi kernel 5.15 i ima kratak preostali period podrške. 22/22.1 koriste GA 6.8; 22.2/22.3 standardni ISO koriste 6.14.

Izabrana je **22.1 Xia XFCE**: GA 6.8, duži period podrške, bez prelaska na HWE. Star hardver sam po sebi nije dokaz da noviji kernel ne radi. Konkretne regresije moraju se izmeriti. Primarno izdanje je amd64; posebna 32-bit Nova ISO nije implementirana. i386 Wine biblioteke nisu 32-bit operativni sistem.

Nema merenja koja potvrđuju 250–400 MB RAM-a. Zvanični minimum Mint-a je 2 GB; 1 GB je Nova eksperimentalni target, posebno težak za installer i savremeni pregledač.

## Repozitorijumi i identitet

Preserviraju se izvori, APT preference i keyring paketi zvaničnog potpisanog ISO-a:

- Mint: `xia`, komponente `main upstream import backport`.
- Ubuntu: `noble`, `noble-updates`, `noble-backports`, `noble-security`.
- Ubuntu komponente: `main restricted universe multiverse`.
- Paketi poverenja: `linuxmint-keyring`, `ubuntu-keyring`.

Ne dodaju se PPA-i, WineHQ ni neprovereni mirrors. Bez eksplicitne promene baze ne prelazi se na `zena`, `jammy` ili drugu suite. APT potpisi ostaju uključeni. Build čuva stvarne sources.list datoteke i ceo instalirani package lock.

`/etc/os-release` i `/etc/linuxmint/info` zadržavaju upstream identitet radi kompatibilnosti Mint updater-a, driver manager-a, repozitorijuma i instalera. `/etc/nova-release` navodi Nova identitet. Nasleđeni installer/boot ekran mogu prikazivati Mint oznake: ovo nije završeno rebrand izdanje niti proizvod Linux Mint tima.

## Slojevi

1. Zvanični ISO, proverena potpisana SHA256 lista i zaključan fingerprint.
2. Rootfs iz squashfs-a, APT bez preporučenih dodataka i sa dostupnim update-ima.
3. Paket `nova-defaults`, instaliran preko dpkg-a: tema, ikone, wallpaper, `/etc/skel` XFCE profil, launcher-i, dijagnostika, compatibility center i prvi ulazak.
4. Kernel i initramfs ponovo usklađeni sa instaliranim stock kernelom i casper hooks.
5. Izvorni Mint casper/Ubiquity live/installer i originalna lista installer-only paketa.
6. xorriso remaster sa originalnim El Torito/system-area replay-om.

Paket se zadržava u instaliranom sistemu. Originalni Nova profil je u `/usr/share/nova/skel`; build ga kopira u `/etc/skel` uz backup u `/var/lib/nova/backups/skel`. Aktivna zram/journald konfiguracija se takođe kopira uz backup; paket ne preuzima vlasništvo nad datotekama drugih paketa. `/etc/nova-release` je dpkg conffile. Novi korisnici dobijaju profil iz skel-a; postojeći korisnički profil ne prepisuje se automatski van rootfs-a zvaničnog live ISO-a. Nadogradnja Nova paketa ne prepisuje korisnički profil ili aktivne optimizacije; promene se primenjuju eksplicitno.

## Bezbednost

- Firewall: incoming/forward DROP, outgoing ACCEPT; samo rootfs datoteke, bez `ufw enable` u chroot-u koji bi mogao menjati host firewall.
- Bezbednosni servisi, AppArmor, mreža, audio, storage i update manager se ne gase radi RAM broja.
- Servisi se blokiraju privremenim policy-rc.d samo tokom build-a; upstream datoteka se vraća.
- Korisničke aplikacije/Wine nikada ne izvršavati kao root.
- Privilegovani opcioni instalater ima fiksni allowlist, bez sastavljanja shell komandi od korisničkog teksta.
- Nema automatskog formatiranja, particionisanja ili pisanja na fizičke diskove.
- Desktop efekti su isključeni; pretraga aplikacija je Whisker, ne pozadinski indeksator.

## Optimizacije i rollback

| Promena | Razlog | Oporavak |
|---|---|---|
| XFWM kompozitor off | Slaba integrisana grafika, manje GPU/CPU rada | Window Manager Tweaks ili `xfconf-query -c xfwm4 -p /general/use_compositing -s true` |
| zram lz4, 35% RAM-a, prioritet 100 | Komprimovani swap pre HDD-a; fizička alokacija raste s korišćenjem | `sudo nova-performance rollback`; vraćanje backup-a ili upstream zram profila |
| journald limit | Ograničen disk/log prostor, bez isključivanja sigurnosnih logova | `sudo nova-performance rollback` i restart journald-a |
| Opciono uklanjanje aplikacija | Manji image i manje nepotrebnog softvera | Reinstalirati paket preko Software Manager-a/APT-a |
| XFCE profil/tema | Familiarni taskbar bez efekata | XFCE Settings, `nova-theme light|dark`; novi korisnik ili uklanjanje Nova profila |
| Firefox defaulti (`00-nova.js`) | Dva content procesa, ograničen page-cache, bez GPU akceleracije i bez pozadinskih feedova — najskuplji potrošač na 1 GB | Ukloniti `/usr/lib/firefox/defaults/preferences/00-nova.js`; ništa od ovoga nije `lockPref` |
| Dobrodošlica bez pregledača ispod 1,6 GB | Live sesija na 1 GB ne diže Firefox sama; stranica ostaje u meniju ("Nova OS — dobrodošlica") | `rm ~/.local/state/nova/welcome-seen` i ponovni `nova-firstboot`, ili drugi prag preko `NOVA_LOW_MEMORY_KB` |
| UFW default | Minimalno izložene mrežne usluge | Vratiti sačuvane rootfs konfiguracije; na instaliranom sistemu pregledati pravila pre promene |

zram nije dodatni stvarni RAM i nije zamena za testiranje. HDD swap podesiti kroz potvrđeno particionisanje u installer-u; build ne pravi niti formatira swap particije.

## Hardver i aplikacije

Kernel i firmware su upstream paketi; nema posebnih binarnih drajvera niti obećanja svih Wi-Fi/GPU uređaja. Driver Manager ostaje dostupna opciona upstream mogućnost. Vulkan/DXVK/VKD3D nisu automatski uključeni. Bottles/Steam su opciona preuzimanja za hardver s dovoljno RAM-a; Flathub remote se ne dodaje automatski.

Firefox se koristi zbog održavanih bezbednosnih izdanja i Mint native paketa; nije obećan mali RAM footprint. Xreader je PDF viewer. Thunar, Terminal, Synaptic, mintupdate i mintinstall ostaju; nema duplog custom package manager-a.

`system/browser/nova.js` se postavlja uz instalirani Firefox (`defaults/preferences/00-nova.js`) i sadrži samo `pref()` defaulte: bez zaključanih vrednosti, bez gašenja site izolacije, bez diranja auto-ažuriranja. Build preskaže taj korak ako Firefox direktorijum ne postoji (npr. ESR ili drugачија instalacija).

## Izvori

- https://linuxmint.com/download_all.php
- https://linuxmint.com/rel_xia_xfce_whatsnew.php
- https://blog.linuxmint.com/?p=4793
- https://linuxmint-installation-guide.readthedocs.io/en/latest/choose.html
- https://linuxmint-installation-guide.readthedocs.io/en/latest/verify.html
- https://ubuntu.com/kernel/lifecycle

Zvanične web informacije nisu zamena za stvarni ISO manifest i boot test.
