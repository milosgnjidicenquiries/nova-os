# Project Nova OS 0.1.0 — razvojni projekat

Nova OS je minimalni XFCE derivat Linux Mint-a, ne kernel napisan od nule. Cilj je osnovna upotreba starog x86-64 računara sa 1 GB RAM-a, bez obećanja univerzalne kompatibilnosti.

**Trenutno isporučeno: izvorni projekat, desktop sredstva, dijagnostika, opcione kompatibilne aplikacije i ISO build pipeline koji je stvarno proizveo sliku `nova-build-8` — viđenu u emulaciji kako diže live XFCE desktop (BIOS i UEFI, sa 4 GB i sa 1 GB RAM-a).** Instalacija na disk, pravi hardver i performanse nisu provereni; detalji i granice tvrdnji su u [izveštaju o testiranju](docs/testing-report.md).

## Osnova

- Linux Mint **22.1 Xfce / Xia**, Ubuntu **24.04 LTS / noble**, amd64.
- XFCE 4.18; Ubuntu GA kernel serije 6.8 sa dostupnim zakrpama.
- Zvanična Mint podrška do aprila 2029.
- Mint zvanični minimum: **2 GB RAM-a**. Nova cilj od 1 GB je eksperimentalan.
- Cilj 250–400 MB u instaliranoj praznoj sesiji **nije izmeren**.
- Repozitorijumi i potpisni ključ: [osnova](build/base.json) i [arhitektura](docs/architecture.md).

## Šta projekat radi

- Originalne svetla/tamna Nova teme, vektorska pozadina, donja XFCE traka i prečice.
- Minimalni [manifest](build/packages.txt); uklanjanje samo eksplicitnih opcionih aplikacija posle APT simulacije.
- zram profil, ograničenje logova, isključen kompozitor; bez slepog gašenja sistemskih servisa.
- `nova-hardware`: čitanje stvarnih hardverskih podataka i upozorenja.
- `nova-compat`: opcioni Wine/Winetricks, 32-bit komponenta, Steam i Bottles; nema automatskih gaming zavisnosti.
- Potpisana provera zvaničnog ISO-a, izolovan build rootfs, paket `nova-defaults`, stock kernel/initramfs, postojeći Mint live/installer, replay BIOS/UEFI boot strukture.
- Lokalne provere integriteta, testovi alata i bezbedna interaktivna QEMU test skripta.

## Dostupne provere

Na Linux-u:

```sh
python3 tests/run-tests.py
```

Na ovom Windows računaru sa Python launcher-om i Git Bash-om:

```sh
py -3 tests/run-tests.py
```

Prolazak ovih provera nije dokaz rada desktopa, instalera, Wine-a ili hardvera. Stvarni obuhvat je u [izveštaju](docs/testing-report.md).

## Izrada i testiranje

1. [Build vodič](docs/build-guide.md): zavisnosti, zvanični ISO i potpis, build komanda, granice ponovljivosti.
2. [Instalacija i oporavak](docs/installation-guide.md): VM, USB, particije i zaštita podataka.
3. [Test plan](docs/test-plan.md): 1/2/4 GB, BIOS/UEFI i fizičko merenje.
4. [Ograničenja i release status](docs/release-notes.md).

Ne izvršavajte build u root-u svog glavnog radnog Linux-a. Koristite namensku build VM; chroot nije bezbednosna izolacija.

## Licence

Nova izvorni kod i originalna sredstva: [MIT](LICENSES/NOVA-MIT.txt). Nasleđeni distro paketi i firmware imaju zasebne licence. Build izvozi inventar copyright datoteka; pravna provera, izvorni paketi i uslovi distribucije su release gate, ne automatska potvrda.
