# Stvarni izveštaj o proverama — ažurirano 2026-11-01

## Isporuka i granica tvrdnje

Isporučen je izvorni razvojni projekat sa CI build pipeline-om. **Nije potvrđeno da Nova OS podiže, da se instalira
ili da radi sa 1 GB RAM-a.** Nijedan taj korak nije izvršen, a ovaj izveštaj razdvaja ono što je stvarno provereno
od onoga što tek čeka.

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

**82 testa, 81 prošlo, 1 preskočen (Windows nema privilegiju za stvarni symlink), bez failure/error rezultata.**
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
| 41340768775 | u toku | — | Run sa oba filtra; tekstualni izveštaj se dopunjuje po završetku. |

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

- **Podizanje Nova slike** — BIOS, UEFI, Secure Boot, live sesija, LightDM, XFCE/GTK runtime, Nova tema u realnom desktop-u. Strukturalna provera medija NIJE test boot-a.
- Instalacija na HDD/SSD, particionisanje, disk-only reboot, rollback.
- Merenja na 1/2/4 GB RAM-a, CPU, Wi-Fi, audio, USB, suspend, stvarni Wine/Steam/Bottles.
- Pravni pregled redistribucije (`licenses/inventory.csv` nosi `redistribution_review=pending`).
- Bit-identična reproducibilnost (nije cilj koji je dostignut; skriptovan remaster ≠ reproducible-build sertifikacija).

## Sledeći konkretni korak

Run 7 (41314409340) sa ispravljenim vlasništvom (`b0dabce`) treba da objavi draft prerelease sa `.part`
delovima + `SHA256SUMS`. Pošto se delovi spoje i provere lokalno (`scripts/join-and-verify.ps1`), slika je
spremna za USB; zatim se pokreće `Boot test Nova OS image` (QEMU TCG, snimci ekrana). **Emulirani boot daje
vizuelni dokaz, ne performanse.** Pravi 1 GB test i dalje zahteva fizički Celeron ili mašinu sa uključenim VT-x-om.

## Isporučni put (spajanje delova)

ISO je veći od GitHub-ovog limita od 2 GB po asset-u, pa se deli na `.part` delove. Provereno na sintetičkoj
10 MB slici:

- `.github/scripts/prepare-assets.py --limit 4000000` → 3 dela + `ASSET_SHA256SUMS`, original uklonjen.
- `scripts/join-and-verify.ps1` → spojen fajl sa poklapajućim SHA256; **namerno oštećen deo** dao je exit 1 sa
  porukom da se slika ne sme pisati na USB.
- `.github/scripts/join-parts.py --dir …` → spojeno 10.485.760 bajta, SHA256 identičan originalu.
  To je isti mehanizam koji `Boot test Nova OS image` koristi pre podizanja.
