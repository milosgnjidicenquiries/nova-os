# Cloud build preko GitHub Actions

Koristi se kada lokalni računar nema Linux build okruženje (bez VT-x-a, bez WSL-a). Runner je GitHub-ova
ubuntu-24.04 virtuelna mašina sa root pristupom; tvoj laptop se ne menja.

## Šta workflow radi

`.github/workflows/build-iso.yml` (ručno se pokreće: Actions → Build Nova OS ISO → Run workflow):

1. Instalira gradivne alate (`xorriso`, `squashfs-tools`, `dpkg-dev`, `initramfs-tools`, `systemd`, `shellcheck`).
2. Dohvata javni Linux Mint ISO signing key i ispisuje njegov fingerprint.
3. Preuzima `linuxmint-22.1-xfce-64bit.iso`, `sha256sum.txt` i `sha256sum.txt.gpg` sa zvaničnog mirrora.
4. `build/verify-source.py` kriptografski proverava potpis manifiesta i poredi SHA256 ISO-a sa fingerprintom
   zaključanim u `build/base.json`. Ako bilo šta ne prođe, build staje pre diranja slike.
5. Pokreće `tests/run-tests.py` i informativni `shellcheck`.
6. `sudo bash build/build-iso.sh` radi remaster u privatnom mount namespace-u, pa `build/verify-iso.sh`
   proverava strukturu (checksum, squashfs, casper/Ubiquity manifest, BIOS i UEFI El Torito unose).
7. Objavljuje **draft prerelease**: `nova-os-0.1.0-amd64.iso` (kao ceo fajl ako je ispod 2 GB, ili `.part`
   delovi uz `ASSET_SHA256SUMS`), plus logove, `packages.lock` i `SHA256SUMS`.

## Preuzimanje i sastavljanje

```powershell
cd C:\path\do\nova-os
powershell -ExecutionPolicy Bypass -File scripts\join-and-verify.ps1 -Folder "C:\path\do\preuzeto"
```

Skripta spoji `.part` delove u ispravnom redosledu i poredi SHA256 sa `SHA256SUMS`. Bez poklapanja nemoj
pisati sliku na USB.

## Ograničenja

- Kvarke minuta: private repo ima mesečnu kvotu (Free plan 2.000 minuta); jedan build tipično 30–90 minuta.
- Runner nema `/dev/kvm`, zato **boot test nije deo ovog workflow-a**. Strukturalna provera nije isto što i
  podizanje; VM provera i 1 GB merenje ostaju odvojeni koraci.
- `SHA256SUMS` dokazuje integritet, ne identitet izdavača: pre javne objave Nova tim treba da potpiše finalni
  checksum svojim kontrolisanim release ključem.
- Mirror je workflow input; zameni ga samo zvaničnim Linux Mint mirrorom (`linuxmint.com/mirrors.php`).
