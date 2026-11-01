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

**76 testova, 75 prošlo, 1 preskočen (Windows nema privilegiju za stvarni symlink), bez failure/error rezultata.**
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
| 41304966852 | u toku | — | Prvi run sa ispravljenim odkačenjem. Rezultat se upisuje ovde tek po završetku. |

U sva tri neuspeha, `Verify signature and ISO hash before touching the image` i `Repository checks` su **prošli**,
što znači da je kriptografska kapija i lokalni suite preneti u Linux okruženje bez promene ponašanja.

## Isporučni put (spajanje delova)

ISO je veći od GitHub-ovog limita od 2 GB po asset-u, pa se deli na `.part` delove. Provereno na sintetičkoj
10 MB slici:

- `.github/scripts/prepare-assets.py --limit 4000000` → 3 dela + `ASSET_SHA256SUMS`, original uklonjen.
- `scripts/join-and-verify.ps1` → spojen fajl sa poklapajućim SHA256; **namerno oštećen deo** dao je exit 1 sa
  porukom da se slika ne sme pisati na USB.
- `.github/scripts/join-parts.py --dir …` → spojeno 10.485.760 bajta, SHA256 identičan originalu.
  To je isti mehanizam koji `Boot test Nova OS image` koristi pre podizanja.

## Nije izvršeno

- **Podizanje bilo koje slike** — BIOS, UEFI, Secure Boot, live sesija, LightDM, XFCE/GTK runtime, Nova tema u realnom desktop-u.
- Instalacija na HDD/SSD, particionisanje, disk-only reboot, rollback.
- Merenja na 1/2/4 GB RAM-a, CPU, Wi-Fi, audio, USB, suspend, stvarni Wine/Steam/Bottles.
- Pravni pregled redistribucije (`licenses/inventory.csv` nosi `redistribution_review=pending`).
- Bit-identična reproducibilnost (nije cilj koji je dostignut; skriptovan remaster ≠ reproducible-build sertifikacija).

## Sledeći konkretni korak

Dovršiti run 41304966852, objaviti draft prerelease sa slikom, spojiti i proveriti delove, pa pokrenuti
`Boot test Nova OS image` (QEMU TCG, snimci ekrana). **Emulirani boot daje vizuelni dokaz, ne performanse.**
Pravi 1 GB test i dalje zahteva fizički Celeron ili mašinu sa uključenim VT-x-om.
