# Stvarni izveštaj o proverama — ažurirano 2026-11-01

## Isporuka i granica tvrdnje

Isporučen je izvorni razvojni projekat sa CI build pipeline-om **i jedna stvarno izgrađena, strukturalno proverena
slika** (draft release `nova-build-8`, 3.134.521.344 bajta). Slika **podiže do live XFCE desktopa** — viđeno na
snimcima ekrana u emulaciji, i sa 4 GB **i sa 1 GB RAM-a**. **Nije potvrđeno** da se instalira, da UEFI putanja
dođe do desktopa (GRUB meni pod UEFI-jem jeste viđen), ni da je sesija upotrebljiva na pravom Celeronu. Nijedan
taj korak nije završen, a ovaj izveštaj razdvaja ono što je stvarno provereno od onoga što tek čeka.

## Okruženja

Lokalno (ne menja se):

- Windows 11 NT 10.0.22631, x86-64, Git Bash/MSYS, Python 3.13 preko `py -3`, `gh` 2.103.3 portable.
- `wsl.exe --status` exit 50; VirtualBox 64-bit gost pada sa `VERR_NEM_NOT_AVAILABLE` /
  `VT-x is disabled in the BIOS (VERR_VMX_MSR_ALL_VMX_DISABLED)`. Zato lokalni build/boot VM nije izvodljiv.

CI (GitHub Actions, privatni repo `milosgnjidicenquiries/nova-os`):

- `ubuntu-24.04`, root kroz `sudo`, bez `/dev/kvm` (emulirani boot samo kroz QEMU TCG).

## Stvarno proverena autentičnost baze

Preuzeti su `linuxmint-22.1-xfce-64bit.iso` (2.885.681.152 bajta), `sha256sum.txt`, `sha256sum.txt.gpg` i javni
ključ. `build/verify-source.py` je, i lokalno i u CI-u, dobio `GOODSIG` i `VALIDSIG` sa fingerprintom
`27DEB15644C6B3CF3BD7D291300F846BA25BAE09` (Linux Mint ISO Signing Key) i poklapajući SHA256
`6451496af35e6855ffe1454f061993ea9cb884d2b4bc8bf17e7d5925ae2ae86d`. Fingerprint je proveren i preuzimanjem ključa
sa `keyserver.ubuntu.com`: ista vrednost. Ako bi se promenio, build staje.

## Lokalni suite

```sh
py -3 tests/run-tests.py
```

**88 testova, 87 prošlo, 1 preskočen (Windows nema privilegiju za stvarni symlink), bez failure/error rezultata.**
Obuhvat: manifest parsing i zaštita essential paketa, installer manifest logika, GTK/XML/SVG/XPM reference,
filesystem staging i deploy Nova paketa, `/proc` fixture parseri za hardware/benchmark, Wine prefix putanje,
APT source validacija, stvarni GnuPG integracioni test (generisan privremeni ključ, potpisan i proveren manifest,
odbijen drugi fingerprint, odbijen izmenjen manifest i payload). **To su provere izvora, ne sistema.**

## CI istorija — stvarni ishodi

| Run | Trajanje | Ishod | Stvarni uzrok i ispravka |
| --- | --- | --- | --- |
| 41301661037 | 3m23s | neuspeh u `Build ISO` | Gate je odbacio `casper/` raspored: Mint 22.1 Xfce **nema** `filesystem.manifest-desktop`, već `filesystem.manifest-remove` (128 stavki) i manifest razdvojen tabom. Pročitano iz samog ISO-a (pycdlib), ispravljeno u `cfd5af9`. |
| 41302359780 | 11m17s | neuspeh u `Build ISO` | Ceo hord prošao (purge, `nova-defaults`, UFW, `update-initramfs` na 6.8.0-147-generic, licence), pad na `umount .../rootfs/sys: target is busy`. Prvi pokušaj zaustavljanja procesa (`ff534d5`). |
| 41303919507 | 10m22s | neuspeh u `Build ISO` | Isti umount pad, ali **bez ijednog procesa sa root-om u hordu**: uzrok nije proces nego potkačenje pod `/sys`. Skidanje sada ide od najdubljeg ka plićem preko `findmnt`, uz `fuser -vm` dijagnostiku i `umount -l` posle tri neuspele runde (`329ae0e`). |
| 41304966852 | 27m11s | neuspeh u `Build ISO` | Odkačenje prošlo, squashfs i manifesti gotovi. Pad na `xorriso -boot_image any replay`: „Cannot enable EL Torito boot image #1 because it is not a data file“. Iz samog ISO-a pročitan katalog (BIOS = 2 KB na LBA 4675, EFI = 5 MB na LBA 2115, **nijedan nije fajl u drvetu**) i dodata CI dijagnostika `Inspect source ISO boot layout`. Ispravka `72044cf`. |
| 41307824091 | 29m18s | neuspeh u `Build ISO` | Oporavak flag-ova radio, ali je cela `-boot_image …` linija prosleđena kao **jedan** argument → xorriso „Not a known command“ za svaku. Pisanje slike prebačeno u `build/write-iso.py` sa `shlex.split` po liniji, uz testove nad stvarnim izveštajem (`008b962`). |
| 41310365536 | 29m41s | neuspeh u `Prepare release assets` | **`Build ISO` je prošao do kraja** i napravio stvarnu sliku (detalji dole). Pad na `split: … .part: Permission denied` — `out/nova-build` je napravio `sudo`, pa je ostao root-ov, a korak deljenja radi kao običan korisnik i nije smeo da piše u direktijum. Ispravka `b0dabce`: `build-iso.sh` vraća vlasništvo nad output-om na `SUDO_UID:SUDO_GID`. |
| 41314409340 | 30m6s | neuspeh u `Publish image as draft prerelease` | Build, `split`, `Upload build metadata artifact` — **sve prošlo**. `gh release create` pao na `HTTP 400: Bad Content-Length` za asset `build.lock`: `asset-list.py` je ponudio i zaključni fajl veličine 0 bajta, GitHub odbija prazan asset i ceo upload staje (delovi su ostali u `starter` stanju, bez sadržaja). Ispravka: `asset-list.py` preskače `build.lock` i svaki fajl nula bajtova, uz test `test_asset_list_skips_lock_and_empty_files`. |
| 41340768775 | 39m45s | **sve prošlé** | Build, `split`, metadata artifact i `Publish image as draft prerelease` — svi koraci zeleno. Draft release **`nova-build-8`**: `nova-os-0.1.0-amd64.iso.00.part` (1.900.000.000 B), `.01.part` (1.234.521.344 B), `SHA256SUMS`, `ASSET_SHA256SUMS`, `source-verification.json`. Zbir delova = 3.134.521.344 B, isto kao `Report image size`. |
| 41344185706 | — | neuspeh u `Resolve the image release` (boot test) | `gh release download <tag>` i `gh api releases/tags/<tag>` **ne vide draft release** bez git tag-a; prvi pokus boot testa tako i pade. Zamenjeno sa `.github/scripts/fetch-release-assets.py` (release ID + asset ID preko API-ja, odbija asset u `starter` stanju). |
| 41344663028 | 2m0s | neuspeh u `Resolve the image release` | Ispravka iznad nije bila dovoljna: **Actions token sa `contents: read` uopšte ne vidi draft release-ove**. `boot-test.yml` sada traži `contents: write` i ispisuje šta mu je API vratio kad tag nedostaje. |
| 41345007667 | 4m24s | neuspeh u boot koraku | `join-parts.py` spojio 2 dela i potvrdio SHA256, ali QEMU monitor kod je blokirao na `stream.read(4096)` (dočekuje 4096 bajtova, a pozdrav je kraći) → `TimeoutError`, nijedan kadar. `serial.log` je **prazan** jer Mint koristi `quiet splash` bez `console=ttyS0`, pa je screendump jedini kanal. Ispravka: `recv` sa istekom + ponavljanje (`boot-capture.py`). |
| 41345675650 | 47m | **boot dokazan** | BIOS/TCG, `-m 4096`, 2 vCPU. Kadrovi: splash tokom podizanja (~25 s), pa **živ XFCE desktop** sa panelom, satom 20:23 → 20:25 kroz uzastopne kadrove, i Nova dobrodošlicom otvorenom iz `/usr/share/nova/welcome.html`. Snimci su u `docs/evidence/boot-bios-4096mb-run41345675650/`. |
| 41350074375 | 39m55s | delimičan (UEFI boot test) | Koraci zeleni, ali od 25 kadrova sačuvana su **samo 2** (015 i 023) i oba prikazuju **GRUB 2.12 EFI meni** — dokaz da EFI boot slika i GRUB-EFI rade, bez dokaza o desktopu. Uzrok mirovanja: `grub.cfg` nema `set timeout` (nasleđeno iz Mint-a). Harness je odbacivao monitor odgovor pa je svaki neuspeo kadar bio neobjašnjiv. |
| 41350648294 | 1h13m | **1 GB desktop viđen** | BIOS/TCG sa `-m 1024`. Kadri 008–013: live XFCE sa dobrodošlicom, sat 21:55 → 22:01. Od kadra 016 nadalje ujednačena crnina (pixel-identični kadrovi) — najverovatnije DPMS gašenje, ali harness ne budi ekran pa se ne tvrdi ništa. Snimci: `docs/evidence/boot-bios-1024mb-run41350648294/`. |
| 41354005351 | 1h14m | bez novog dokaza | UEFI sa `--enter-at 120,300`. Sačuvana **opet samo 2** od 25 kadrova, i dalje GRUB meni. Log konačno pokazuje uzrok: `(qemu)` bez greške = komanda nikad izvršena. QEMU dozvoljava jednog monitor klijenta, pa konekcija-po-komandi baca i `screendump` i `sendkey`. |
| 41357268299 | — | u toku | BIOS `-m 1024` sa Enter-om na 900/1200/1500/1800 s, da se vidi da li se desktop posle gašenja ekrana vraća. |
| 41361076620 | — | u redu | UEFI sa ispravljenim monitorom (jedna veza + `info status` rukovanje) i Enter-om na 120/300 s. |

## Emulirani boot — šta je viđen, a šta nije

Videno na snimcima slike `nova-build-8`: izolinux → kernel → casper → LightDM → XFCE sesija; donja traka sa
Nova launcherima; prozor Firefox-a sa lokalnom Nova dobrodošlicom (srpski sadržaj, upozorenje o brisanju diska i
1 GB limitu); sat napreduje između kadrova 6 i 8, dakle sesija radi, ne miruje.

Nije videno i ne tvrdi se: instalacija na disk, ponašanje pri restartu sa diska, Secure Boot, UEFI putanja
(ovaj run je BIOS režim), izgled Nove GTK/treme u punom obimu, i bilo kakve performanse — TCG emulacija bez KVM-a
meri brzinu hosta, ne Celerona. Vreme do desktopa (~6 min) **nije** broj koji sme da se citira kao performansa.

### UEFI emulirani boot (run 41350074375): do GRUB-a, ne i do desktopa

`boot_mode=uefi`, 4096 MB, 25 planiranih kadrova. Od toga je **sačuvan samo kadar 015 i 023** (ostali
`screendump` nisu napravili fajl), i oba pokazuju **isti ekran**: `GNU GRUB version 2.12` meni sa
„Start Linux Mint 22.1 Xfce 64-bit", „compatibility mode", „OEM install", „Boot from next volume",
„UEFI Firmware Settings" i „Memory test".

To što meni postoji **jeste dokaz** tri stvari: EFI El Torito slika (`/boot/grub/efi.img`) se pronalaži,
GRUB-ov EFI binarni modul startuje, i on učitava baš naš `/boot/grub/grub.cfg` (ulazi „UEFI Firmware Settings"
i „Boot from next volume" se dodaju samo kada je `$grub_platform` = efi).

To što je i dalje tu posle 23 minuta **nije** dokaz da UEFI desktop radi. Razlog je nađen direktno iz slike,
bez alata za ISO (`_probe/iso_read.py`): `/boot/grub/grub.cfg` ima 989 bajtova i **nijednu `set timeout`
liniju**, a `/boot/grub/x86_64-efi/grub.cfg` (254 bajta) samo `insmod`-uje particione module i
`source /boot/grub/grub.cfg`. Bez timeout-a GRUB čeka tastaturu beskonačno — odatle meni bez odbrojavanja.
Izvor (Mint 22.1) ima `grub.cfg` iste veličine, 989 bajtova (videti `inspect` log), pa je ovo **nasleđeno
ponašanje Mint-ovog boot loadera, a ne Nova regresija**. Posledica po korisnika je realna: na UEFI mašini
neko mora da pritisne Enter. Da li Nova to menja dodavanjem timeout-a u bootloader konfiguraciju je odluka
koja se ne donosi usput — to je najrizičniji fajl u slici.

Dva fixa u harnessu (commit `33f2d23`): monitor odgovor se više ne odbacuje, pa sledeći run govori *zašto* kadar
nije napravljen, i dodato je `--enter-at` koje šalje `sendkey ret` u zadate sekunde. Run `41354005351`
ponavlja UEFI sa Enter-om na 120 s i 300 s.

**Ponovljeni run je dao isti crni rezultat, i time je razotkrio pravi uzrok.** Od 25 kadrova opet su sačuvana
samo dva (019 i 025), oba i dalje GRUB meni, i log sada kaže zašto: svaki neuspeli pokušaj odgovara sa
`(qemu)` **bez ijedne poruke o grešci** — tj. komanda nikad nije izvršena. QEMU uslužuje **jednog** monitor
klijenta odjednom, pa konekcija po komandi nasleđuje prethodni prompt i komandu baci. Iz istog razloga i
`sendkey ret` nikad nije stigao do tastature: Enter je „poslat“ u mrtvu vezu, ne u gostu. Zato dosadašnji
UEFI kadrovi ne govore ništa o tome da li prvi unos menija diže desktop.

Ispravka (`1f5d855`): jedna dugovezna veza nad whole run-om, plus rukovanje `info status` odmah po startu —
ako se monitor ne javi, test staje odmah umesto da sat vremena skuplja prazne kadrove. Logika je proverena
protiv lažnog HMP toka bajtova (deljenog u komade) pre nego što je potrošen još jedan CI sat. Run
`41361076620` ponavlja UEFI sa tim kodom.

### 1 GB RAM (run 41350648294): desktop ustaje, pa se ekran ugasi

`boot_mode=bios`, `-m 1024`, 2 vCPU, 30 kadrova (sačuvano 20). Trajanje run-a 1h13m26s naspram 40 min za 4 GB —
i to je razlika u emulaciji, ne merenje performansi.

- kadar 001 (~25 s): splash **Mint-ovog** logotipa. Nova još ne menja boot splash, što je poznat propust u
  brendingu, ne kvar.
- kadrovi 008–013 (21:56 → 22:02): **puni live XFCE desktop** sa 1024 MB RAM-a — panel, Nova launcher, Firefox sa
  dobrodošlicom, a sat napreduje 21:55 → 22:01 kroz uzastopne kadrove. Sesija živi najmanje 6 minuta svog vremena.
- kadrovi 016–029: **ujednačena crnina**. Provereno je dekodiranjem PNG-a da su ti kadroi piksel-identični i svi
  nula, dakle ekran je zaista crn, a ne da harness pravi razliku.

Crn ekran **nije** dokaz o rušenju i nije dokaz da sesija radi i dalje. Najverovatnije je DPMS gašenje ekrana po
isteku mirovanja (redosled se poklapa sa ~10 min neaktivnosti), a crash bi obično ostavio tekst ili poruku, ne
čistu crnu framebuffer sliku. Harness nikad ne budi ekran, pa se ovo ne može rešiti iz postojećih kadrova.

**Rešeno run-om `41357268299`** (BIOS, `-m 1024`, 32 kadra, `sendkey ret` na 900/1200/1500/1800 s):

| kadar | vreme na satu sesije | ekran |
| --- | --- | --- |
| 015 | 23:25 | desktop sa prozorom i panelom |
| — | 23:26:25 | `sent Enter at 910s` |
| 016 | — | crn (282 B, ujednačen) |
| 017 | 23:28 | **desktop se vratio** |
| 032 | 23:48 | i dalje tu, sat napreduje |

Sesija je preživela gašenje ekrana: sat je posle povratka išao 23:28 → 23:48. Dakle crni rep iz prvog 1 GB run-a
je **DPMS, ne rušenje**. Dokazi: `docs/evidence/boot-bios-1024mb-run41357268299/`.

Nova posledica, i to prava: **Nova ne isporučuje `xfce4-power-manager.xml`** (skel ima samo desktop, keyboard,
panel, xfwm i xsettings kanale), pa na ciljnoj mašini važi podrazumevano gašenje ekrana posle ~10 minuta. Za
„upali i radi" UX to je odluka koja treba da bude doneta, a ne nasleđena.

Usput se vidi i cena jednog nasumičnog pritiska: posle Enter-a je Firefox preko celog ekrana, a panela nema,
kao da je tastatura aktivirala stavku taskbara. Nije dokazano koji je tačno put, ali to je ono što se menja na
slici između 015 i 017 — ne promena u sistemu.

Šta ovo **ne** tvrdi: ništa o upotrebljivosti na pravom Celeronu. U tih 1 GB nijedna aplikacija nije otvorena
osim auto-startovanog Firefox-a, nema instalacije, nema opterećenja. Dokazano je samo da live sesija sa 1 GB
**dostiže desktop i drži ga**.

Usput je nađen još jedan flaw u harnessu: „changed/same" se računalo nad PNG bajtovima, a ImageMagick u svaki PNG
upisuje varijabilan chunk, pa je svakih crnih 282 bajta izgledalo kao nov ekran. Sada se hešira PPM.

### Slike između run-ova nisu identične

Run 6 je dao SHA256 `ee5fa2d631d32ed562eb4507118221824b1c0ea309cbe3d982bee2b42b0470f6`, run 8 `c0e848b44dc14209747d5bb69386cb21b8a2bdecaa28c1ed637c73488b01afbb`. Razlika je očekivana i dokazuje da pipeline **nije** bit-reproducible: `apt upgrade` unutar horda uzima aktuelne pakete u trenutku build-a, a `SOURCE_DATE_EPOCH` samo normalizuje timestamp-ove i squashfs metabaze. Reproducibilnost zahteva fiksiranje celog APT snapshot-a, što ovaj projekat ne tvrdi.

`ASSET_SHA256SUMS` iz run 8 nosi `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` za `build.lock` — heš praznog sadržaja, tj. upravo taj fajl nula bajta koji je GitHub odbio kao asset u run 7.

## Šta run 41310365536 dokazuje o samoj slici

Korak `Build ISO` je prvi put prošao **celu** putanju i napravio stvarni fajl:

- `out/nova-build/nova-os-0.1.0-amd64.iso` = **3.134.521.344 bajta**, SHA256
  `ee5fa2d631d32ed562eb4507118221824b1c0ea309cbe3d982bee2b42b0470f6`.
- `xorriso` je iz izvorne slike vratio i primenio njene sopstvene boot komade (`system_area` sa
  `zero_mbrpt,zero_gpt,zero_apm`, `partition_offset=16`, `cat_path=/isolinux/boot.cat`,
  `bin_path=/isolinux/isolinux.bin`, `efi_path=/boot/grub/efi.img`, `load_size=5242880`) umesto izmišljenih flag-ova.
- `verify-iso.sh` je nad **napravljenom** slikom potvrdio El Torito katalog sa **dve** boot slike —
  BIOS (4 sektora, `/isolinux/isolinux.bin`, boot-info-table/isohybrid) i UEFI (10.240 sektora,
  `/boot/grub/efi.img`) — plus squashfs payload, `filesystem.manifest`, `nova-defaults`, `casper` i `ubiquity`
  u manifestu i lokalni SHA256 (`SHA256: OK`).
- `update-initramfs` je generisao `initrd.img-6.8.0-147-generic` unutar horda; jedina napomena je
  `cryptsetup: WARNING: Couldn't determine root device`, očekivana za live medij bez kriptovane root particije.

U svih šest run-ova, `Verify signature and ISO hash before touching the image` i `Repository checks` su **prošli**,
što znači da je kriptografska kapija i lokalni suite preneti u Linux okruženje bez promene ponašanja. Run 6
(41310365536) je prvi put prošao i ceo `Build ISO`; pao je tek na `Prepare release assets` zbog vlasništva nad
direktorijumom, a ne zbog sadržaja slike.

## Nije izvršeno

- **Podizanje na pravom mediju i hardveru:** Secure Boot, fizička mašina, USB stik, BIOS i UEFI boot na hardveru.
  Emulirani BIOS boot do XFCE desktopa je **viđen** (gore), a emulirani UEFI samo do GRUB menija — ni jedno ni
  drugo nije dokaz o platformi.
- Instalacija na HDD/SSD, particionisanje, disk-only reboot, rollback.
- Merenja na 1/2/4 GB RAM-a, CPU, Wi-Fi, audio, USB, suspend, stvarni Wine/Steam/Bottles. Live sesija sa 1 GB je
  viđena kako **dostiže desktop i drži ga**, ali bez ijedne otvorene aplikacije osim auto-startovanog Firefox-a,
  dakle bez dokaza o upotrebljivosti.
- Pravni pregled redistribucije (`licenses/inventory.csv` nosi `redistribution_review=pending`).
- Bit-identična reproducibilnost (nije cilj koji je dostignut; skriptovan remaster ≠ reproducible-build sertifikacija).

## Sledeći konkretni korak

Slika `nova-build-8` je spojena i proverena na Windows hostu (`_release/nova-os-0.1.0-amd64.iso`, SHA256
`c0e848b4…01afbb`) i emulirano je viđeno kako diže do XFCE desktopa. Redosled koji preostaje:

1. **UEFI emulirani boot** — prvi pokušaj (`41350074375`) stao je na GRUB meni jer konfiguracija nema timeout,
   a drugi (`41354005351`) nije stigao ni do menija jer je `sendkey` išao u mrtvu monitor vezu. `41361076620`
   je treći pokušaj, sa ispravljenom harness vezom i Enter-om na 120 s i 300 s, da se vidi da li ta stavka
   menija diže desktop.
2. **Da li je crn ekran posle 10. minuta gašenje ili nešto gore** — rešeno (`41357268299`): sesija preživi,
   ekran se ugasi po DPMS-u i vrati se na taster. Preostaje samo odluka da li Nova treba da promeni taj
   nasleđeni default; sam default je ponašanje koje ima i Windows, pa se menja samo ako korisnik traži drugačije.
3. **USB + fizičko podizanje.** Ručno pisanje proverenim image writer-om (Rufus DD mode ili Ventoy), bez
   automatizovanog `dd`; uputstvo i provera heša su u `docs/installation-guide.md`, korak 2. Zahteva USB od 8 GB+
   koji korisnik mora fizički da priključi — na ovom hostu trenutno nema nijedan USB uređaj.
4. **Instalacija na testni disk** i proverа reboot-a sa diska, pa tek onda `nova-hardware` i benchmark na 1 GB.

Performanse se i dalje ne mere emulacijom; pravi 1 GB test traži fizički Celeron ili mašinu sa uključenim VT-x-om.

## Isporučni put (spajanje delova)

ISO je veći od GitHub-ovog limita od 2 GB po asset-u, pa se deli na `.part` delove. Provereno na sintetičkoj
10 MB slici:

- `.github/scripts/prepare-assets.py --limit 4000000` → 3 dela + `ASSET_SHA256SUMS`, original uklonjen.
- `scripts/join-and-verify.ps1` → spojen fajl sa poklapajućim SHA256; **namerno oštećen deo** dao je exit 1 sa
  porukom da se slika ne sme pisati na USB.
- `.github/scripts/join-parts.py --dir …` → spojeno 10.485.760 bajta, SHA256 identičan originalu.
  To je isti mehanizam koji `Boot test Nova OS image` koristi pre podizanja.
