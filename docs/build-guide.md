# ISO build vodič

## Prvi korak: Linux build VM

Na ovom Windows hostu `wsl.exe --status` vraća 50; xorriso, squashfs-tools i QEMU nisu dostupni. Git Bash nije Linux kernel. Build nije izvršen. Pripremite namensku **Ubuntu 24.04 amd64 VM**, najmanje 4 GB RAM-a, 2 CPU niti i 30–40 GB slobodnog diska. Build mašina nije ciljna mašina od 1 GB. Potrebni su internet i root za chroot/mount.

Na toj VM, ne na Windows-u:

```sh
sudo apt-get update
sudo apt-get install --no-install-recommends bash coreutils python3 gnupg xorriso squashfs-tools dpkg-dev rsync util-linux mount initramfs-tools qemu-system-x86 qemu-utils ovmf shellcheck desktop-file-utils
```

QEMU, OVMF i desktop-file-utils služe QA-u. `tee`, `du`, `install`, `realpath`, `sha256sum` i `mktemp` dolaze iz coreutils; flock iz util-linux. Repozitorijum kopirati na Linux filesystem sa dovoljno prostora; skripte se mogu pokretati eksplicitnim `bash`/`python3` bez oslanjanja na Windows executable bit.

## Zvanični ulazi i potpis

Sa zvanične stranice izaberite Mint 22.1 **XFCE**, ne Cinnamon, MATE ili HWE, i preuzmite u lokalni `inputs/`:

- `linuxmint-22.1-xfce-64bit.iso`
- `sha256sum.txt`
- `sha256sum.txt.gpg`

Izvor: https://linuxmint.com/download_all.php

Ključ nabavite prateći zvanični vodič i proverite **ceo fingerprint**, ne samo kratki key ID:

https://linuxmint-installation-guide.readthedocs.io/en/latest/verify.html

```text
27DE B156 44C6 B3CF 3BD7 D291 300F 846B A25B AE09
```

Izvezeni javni ključ sačuvajte kao `inputs/mint-iso-signing-key.asc`. To je javni ključ, ne privatni ključ. Program ne veruje nazivu tog fajla: proverava signer fingerprint nakon kriptografske provere potpisa. Ako Mint rotira/ukine ključ, zaustavite build i proverite zvaničnu objavu; ne isključujte proveru.

```sh
python3 build/verify-source.py \
  --iso inputs/linuxmint-22.1-xfce-64bit.iso \
  --checksums inputs/sha256sum.txt \
  --signature inputs/sha256sum.txt.gpg \
  --key inputs/mint-iso-signing-key.asc
```

Projekat ne sadrži ISO, izmišljeni SHA256, privatne ključeve niti preskočene provere potpisa.

## Build

```sh
python3 tests/run-tests.py
mkdir -p out
sudo bash build/build-iso.sh \
  --iso inputs/linuxmint-22.1-xfce-64bit.iso \
  --checksums inputs/sha256sum.txt \
  --signature inputs/sha256sum.txt.gpg \
  --key inputs/mint-iso-signing-key.asc \
  --output-dir out/nova-0.1.0-build1
```

Output direktorijum mora biti nov; postojeći output se nikada ne prepisuje. Nema operacija sa fizičkim diskovima. `--keep-work` zadržava radno stablo i nakon uspeha; pri neuspehu ono ostaje automatski. Mount-ovi rade u privatnom mount namespace-u. Pri čišćenju se prvo zaustavljaju procesi čiji je root samo build hord, pa se kačenja skidaju **od najdubljeg ka plićem** (`findmnt`), jer potkačenje koje je napravio `update-initramfs` (npr. `/sys/fs/cgroup`) drži roditelja zauzetim. Ako tri runde običnog `umount`-a ne uspe, sledi `umount -l` uz ispisano `fuser -vm` objašnjenje ko ga je držao; tek ako ni to ne prođe stablo ostaje sačuvano radi ručnog pregleda.

APT radi `update`, bezbednu `upgrade --with-new-pkgs` bez uklanjanja paketa, zatim manifest. Zadržava Mint/Ubuntu izvore i provere potpisa. Nema `dist-upgrade`, `autoremove`, custom kernela ni automatskog isključivanja sistemskih usluga. Pre purga optional paketa radi se simulacija; ako bi uklonila zaštićen paket, build staje. U tom slučaju pregledajte `build.log` i korigujte whitelist; nemojte zaobilaziti proveru.

Nasleđeni initrd naziv (`initrd`, `initrd.lz` ili `initrd.gz`) i putanja se očuvaju; kernel/initramfs se sinhronizuju. BIOS/UEFI informacije se preuzimaju od originalnog ISO-a, ne iz pretpostavljenih GRUB flag-ova. To nije `-boot_image any replay`: u Mint 22.1 BIOS El Torito unos **nema ISO9660 putanju** (samo LBA 4675), pa replay odbija sa „not a data file in the ISO filesystem“. Umesto toga `build/write-iso.py` poziva `xorriso -report_el_torito cmd` i preuzima izvorne `-boot_image` komande (`cat_path=/isolinux/boot.cat`, `bin_path=/isolinux/isolinux.bin`, `efi_path=/boot/grub/efi.img`, `system_area=--interval:imported_iso…`). Svaka izveštajna linija je **više argumenata** i razdvaja se sa `shlex.split` u zasebne argv stavke (proslediti celu liniju kao jedan argument daje xorriso „Not a known command“). Build staje ako bilo koji od četiri obavezna flag-a nedostaje. Volumen je `NOVAOS010` (samo A–Z/0–9, jer prethodni `NOVA_OS_0_1` izaziva ISO 9660 upozorenje). To nije ugrozio boot: izvorni `/boot/grub/grub.cfg` (pročitan iz samog ISO-a) učitava `/casper/vmlinuz` i `/casper/initrd.lz` preko `${iso_path}`, a BIOS ide kroz El Torito katalog — nijedna putanja ne zavisi od starog label-a „Linux Mint 22.1 Xfce 64-bit“. `isolinux/live.cfg` ima `timeout 100` (10 s) sa `menu default` na „Start Linux Mint“, pa i headless boot sam nastavlja ka live sesiji.

**UEFI strana nema to svojstvo.** `/boot/grub/grub.cfg` (989 bajtova, kopiran nepromenjen) ne sadrži nijednu
`set timeout` liniju, a `/boot/grub/x86_64-efi/grub.cfg` (254 bajta) samo `insmod`-uje particione module i
`source`-uje grub.cfg. GRUB bez timeout-a čeka tastaturu beskonačno, pa se UEFI boot zaustavlja na meniju dok
neko ne pritisne Enter — viđeno u emulaciji (`41350074375` stoji na meniju, `41361076620` čeka 120 s pa diže
desktop), i potkrepljeno istom veličinom fajla u izvornoj Mint slici, dakle nasleđeno a ne Nova greška.
Dodavanje timeout-a znači menjanje najrizičnijeg fajla u slici i za sada se namerno ne radi; boot test harness
zato ima `--enter-at` koji šalje `sendkey ret`.

Mint 22.1 Xfce u `casper/` nema `filesystem.manifest-desktop`: spisak paketa za uklanjanje pri instalaciji je u
`filesystem.manifest-remove` (128 stavki, samo nazivi), a `filesystem.manifest` je tabom razdvojen. `finalize-tree.py`
prihvata oba rasporeda, regeneriše `filesystem.manifest-remove` tako što izbacuje pakete koje je Nova već purgovala, i
zadržava razdvajanje kakvo ima baza. Prvobitna provera je to odbila (build je stao pre nego što je išta dirnuo) —
zato što je tražila isključivo `manifest-desktop`.

## Očekivani output — tek nakon stvarnog uspešnog build-a

- `nova-os-0.1.0-amd64.iso`
- `SHA256SUMS`, `verification.log`, `build.log`
- `source-verification.json`, `base.json`
- `packages.lock`: kompletni tačni instalirani paketi/verzije
- `repositories/`: stvarni izvori korišćeni za build
- `licenses/`: copyright kopije i CSV sa **pending** pravnom proverom

Ovi fajlovi još nisu proizvedeni ovom sesijom. `SHA256SUMS` za Nova output potvrđuje lokalni integritet, ne identitet izdavača: pre javnog release-a Nova tim mora posebno potpisati finalni checksum svojim kontrolisanim release ključem.

## Ponovljivost: precizno ograničenje

Build postupak je skriptovan, izvorni ISO kriptografski proveren i baza zaključana. squashfs dobija fiksni `SOURCE_DATE_EPOCH` (podrazumevano datum izlaska baze). Ponovljivi package-state build može koristiti prethodni `packages.lock`:

```sh
sudo bash build/build-iso.sh \
  --iso inputs/linuxmint-22.1-xfce-64bit.iso \
  --checksums inputs/sha256sum.txt \
  --signature inputs/sha256sum.txt.gpg \
  --key inputs/mint-iso-signing-key.asc \
  --package-lock out/nova-0.1.0-build1/packages.lock \
  --output-dir out/nova-0.1.0-build2
```

To uspeva samo dok su navedene verzije u repo-u ili u sopstvenoj zakonito održavanoj, potpisanoj arhivi. Konačni package inventar mora tačno odgovarati lock-u; mismatch zaustavlja build. Snapshot repo, sačuvani .deb paketi, verzije build alata, initramfs i instalacioni timestamp-ovi nisu potpuno zaključani. **Bit-identična reproducibilnost nije ostvarena niti potvrđena.** Ne predstavljati skriptovan remaster kao dokaz reproducible-build sertifikacije. Za bezbednosno novo izdanje regenerisati lock sa aktuelnim potpisanim paketima, ne zaključavati zastarelu bezbednosnu verziju zauvek.

## squashfs kompresija kao izmjeriva poluga

Live sistem dekomprimuje squashfs pri svakom čitanju, pa je taj CPU rad plat po read-u na Celeronu 2008. — ne jednokratan trošak builda. Zato `build-iso.sh` prima `--squashfs-comp source|gzip|lz4|lzo|xz|zstd`, a `source` (kompresija zatečena iz baze, ispisana u build logu) ostaje default:

```sh
sudo bash build/build-iso.sh ... --squashfs-comp lz4
```

Za svaki kandidat su potrebna dva para izlaza na ciljnoj mašini — `nova-performance status` plus `nova-benchmark` pre i posle pokretanja istog skupa koraka — pre nego što se neki od njih proglasi boljim. Projekat ne menja default bez takvog merenja.

## Kontrola ISO-a

```sh
bash build/verify-iso.sh out/nova-0.1.0-build1/nova-os-0.1.0-amd64.iso out/nova-0.1.0-build1/SHA256SUMS
```

Proverava checksum, squashfs, Nova payload, installer manifest, El Torito BIOS/UEFI i hybrid system area. **Ne testira stvarno podizanje, instalaciju, Secure Boot niti drajvere.** Sledeća faza je QA iz installation/test vodiča.
