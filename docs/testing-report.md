# Stvarni izveštaj o proverama — 2026-10-29

## Isporuka i granica tvrdnje

Isporučen je izvorni razvojni projekat, **ne izgrađen i funkcionalno potvrđen operativni sistem**. Nema bootabilnog Nova ISO-a, instaliranog Nova sistema ili hardverskih RAM rezultata u ovom izveštaju.

## Okruženje

- Windows 11 NT 10.0.22631, x86-64, Git Bash/MSYS.
- `wsl.exe --status`: exit **50**; upotrebljiv Linux build runtime nije ustanovljen.
- Dostupni Bash, GnuPG i Python **3.13.14** preko `py -3`.
- Nisu dostupni xorriso, mksquashfs/unsquashfs, dpkg-deb, QEMU ni ShellCheck u ovom PATH-u.
- Priloženi prompt pročitan, početni workspace prazan; ništa postojeće nije prepisano.

## Izvršene provere

Komanda:

```sh
py -3 tests/run-tests.py
```

**Poslednji kompletan suite: 74 testa, 73 prošla, 1 preskočen, bez failure/error rezultata.** Python AST i `bash -n` za sve lokalne Python/Bash datoteke prolaze. Ove provere odnose se na izvor i alate, ne bootabilnost.

Obuhvat:

- Manifest: nazivi/version pins, duplikati i odbijanje shell-like unosa.
- APT simulacija: parsiranje i zaštita essential/kernel/desktop/installer paketa (jedinična logika, ne stvarna APT transakcija).
- Originalna installer-only package izuzeća očuvana u novom manifestu (jedinični test).
- GTK lokalne reference, XML/SVG parsing, XPM dimenzije/palete i odgovarajući XFCE launcher fajlovi.
- Stvarno filesystem staging Nova paketa i deploy profila u privremenu test strukturu; backup originala i odbijanje host root-a. **dpkg paket nije izgrađen niti instaliran.**
- Hardware/benchmark parseri nad kontrolisanim `/proc` fixtures; ne fizička merenja.
- Prefix validacija, argumenti bez shell-a, reversible move na stvarnim privremenim direktorijumima; Wine/Flatpak/APT procesi u relevantnim testovima mock-ovani.
- Allowlist i stvarna Python logika validacije APT izvora; ne realna instalacija komponenti.
- Root/symlink/traversal odbrane; jedan **stvarni symlink test preskočen** jer Windows nema potrebnu privilegiju (WinError 1314). Mock symlink testovi prošli.

### Kriptografski integracioni test — stvarni GnuPG

U privremenom izolovanom GPG home-u generisan je test RSA-2048 ključ, izvezen javni ključ, potpisan mali test SHA256 manifest i proverena autentičnost. Prošlo:

1. Ispravan signer i payload prihvaćeni.
2. Drugi, nezaključani fingerprint odbijen.
3. Izmenjen potpisani manifest odbijen.
4. Izmenjen ISO-like test payload odbijen.

Ovo **nije** potpisivanje/provera stvarnog Mint ISO-a. ISO nije preuzet. Testni privatni ključ nije release ključ; privremene datoteke nisu deo projekta. Početni test je otkrio MSYS GPG/Windows path grešku; ispravljena je eksplicitnom konverzijom putanja na granici tog alata, zatim kompletni testovi prolaze.

### Direktni smoke-test komandne linije

- `bash build/build-iso.sh --help`: exit 0, ispravna upotreba.
- `bash tests/installation/run-vm.sh --help`: exit 0.
- `bash build/verify-iso.sh` bez argumenata: exit 2.
- Build na Windows-u sa dummy input-ima: exit 1 pre kreiranja output direktorijuma.
- `bash system/performance/nova-performance.sh apply`: exit 1, Linux guard, host konfiguracija nepromenjena.
- `bash compatibility/install-component.sh wine64`: exit 1, Linux guard, nema instalacije.
- `py -3 tests/performance/benchmark.py`: exit 1 sa jasnim Linux `/proc` zahtevom; nema izmišljenih brojeva.

### Prvi ulazak — browser smoke

Pokrenut privremeni lokalni Python HTTP server za `installer/`, otvoren `welcome.html` kroz in-app browser. DOM snapshot potvrđuje naslov, sr-Latn sadržaj, svih pet sekcija, upozorenje o brisanju diska i 1 GB limitu. Nema console warning/error poruka niti eksternih resource zahteva; nema skripti.

Browser ima **skriven viewport 0×0**; screenshot vraća `NATIVE_BROWSER_VIEWPORT_UNAVAILABLE`. Vizuelni layout/responzivnost **nisu potvrđeni**. CSS je prilagođen uskim ekranima, ali DOM smoke nije vizuelni test. XFCE automatski prvi login nije izvršen.

## Nije izvršeno

- Stvarni source Mint ISO potpis/hash i njegova struktura.
- APT upgrade/install/purge i dpkg instalacija Nova paketa na Linux-u.
- Rootfs mount/chroot, kernel/initramfs, squashfs i xorriso build.
- Finalni ISO SHA256 i structural BIOS/UEFI verify.
- Legacy BIOS, UEFI i Secure Boot boot.
- Live sesija, LightDM, XFCE/GTK runtime, panel/wallpaper, stvarni Wine/Steam/Bottles.
- HDD/SSD instalacija, offline installer, disk-only reboot.
- 1/2/4 GB fizička/VM RAM/CPU merenja, browser pressure, Wi-Fi/audio/USB/suspend.
- Firmware pravna provera i potvrđena bit-identična reproducibilnost.

## Sledeći konkretni korak

Pripremiti namensku Ubuntu 24.04 amd64 build VM prema `build-guide.md`, preneti projekat i preuzeti potpisani Mint 22.1 XFCE ISO. Tada izvršiti fazu 8. Faze boot QA i 1 GB benchmark-a zavise od tog stvarnog ISO-a; ne označavati ih završenim na osnovu gornjih 73 prolaza.
