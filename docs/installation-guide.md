# VM, USB, instalacija i oporavak

Izgrađen je **strukturalno proveren** ISO (draft release `nova-build-8`, 3.134.521.344 bajta, SHA256
`c0e848b44dc14209747d5bb69386cb21b8a2bdecaa28c1ed637c73488b01afbb`).

**Dokazano:** slika se podiže do live XFCE desktopa — snimci ekrana u `docs/evidence/boot-bios-4096mb-run41345675650/`,
`docs/evidence/boot-bios-1024mb-run41350648294/` (Legacy BIOS, QEMU TCG, prvo sa 4 GB pa sa **1 GB RAM-a**) i
`docs/evidence/boot-uefi-4096mb-run41361076620/` (UEFI/OVMF). Vidi se splash, zatim desktop sa panelom, satom,
Nova pozadinom i Nova dobrodošlicom iz `/usr/share/nova/welcome.html`. Sa 1 GB je desktop viđen kroz kadrove u
kojima sat napreduje 21:55 → 22:01, pa je i sam memory budget live sesije izvodljiv — bez ijedne otvorene
aplikacije preko auto-startovanog Firefox-a.

**Nije dokazano:** Secure Boot, instalacija na disk, boot sa diska i bilo kakva upotrebljivost ili performanse na
pravom Celeronu. UEFI desktop jeste viđen, ali **nakon jednog pritiska na Enter** — boot meni nema odbrojavanje,
pa na UEFI mašini neko mora da potvrdi prvu stavku. Zato su koraci niže i dalje napisani kao QA postupak, ne kao
uputstvo za gotov proizvod.

## 0. Ako slika dolazi podeljena na delove (Windows)

GitHub release ne prima asset veći od 2 GB, pa se Nova isporučuje kao `nova-os-0.1.0-amd64.iso.00.part`,
`.01.part`, … uz `SHA256SUMS` i `ASSET_SHA256SUMS`. Stavite sve te fajlove u jedan prazan folder (npr.
`C:\Downloads\nova`) i spojite ih:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\join-and-verify.ps1 -Folder "C:\Downloads\nova"
```

Skripta ne dira nijedan disk: samo čita delove i pravi novi `.iso` pored njih. Nastavite tek ako ispiše `OK:`
sa SHA256 vrednošću. Ako ispiše da se heš ne poklapa, **nemojte pisati taj fajl na USB** — obrišite folder i
ponovite download iz iste release stavke. Ako slika dolazi kao jedan `.iso`, isti skript je koristi samo za proveru.

## 1. VM pre fizičke instalacije

Na Linux QA hostu:

```sh
bash tests/installation/run-vm.sh --iso out/nova-0.1.0-build1/nova-os-0.1.0-amd64.iso --ram 1024
bash tests/installation/run-vm.sh --iso out/nova-0.1.0-build1/nova-os-0.1.0-amd64.iso --ram 2048 --disk out/test-install.qcow2
```

`--disk` prihvata samo NOV regularni qcow2 fajl, ne `/dev` disk. Kreira 24 GB sparse virtuelni disk. Installer pokreće korisnik iz live desktopa i sam potvrđuje particionisanje. Bez opcije disk testira se samo live sesija. TCG emulacija nije benchmark stvarnog Celerona.

Za UEFI koristite odgovarajući par instaliranih OVMF CODE/VARS fajlova (na Ubuntu proverite `ls /usr/share/OVMF`). Prosledite postojeći CODE i VARS preko `--uefi CODE_PATH VARS_PATH`; skripta kopira VARS u privremeni folder. Ne koristiti nasumično pomešane 2 MB/4 MB ili Secure Boot/ne-Secure Boot firmware fajlove.

Legacy BIOS test prvo, zatim UEFI. Originalni Mint shim/GRUB/kernel se čuvaju, ali **Secure Boot nije potvrđen**: proveriti zasebno. UEFI boot entry u ISO-u nije dokaz Secure Boot rada.

Po instalaciji zatvoriti VM i ručno pokrenuti QEMU bez `-cdrom`, sa napravljenim qcow2 diskom i istim BIOS/UEFI režimom. Proveriti GRUB, login, mrežu, update, shutdown i reboot sa diska. Nova test skripta namerno uvek podiže ISO; disk-only boot je odvojeni QA korak.

## 2. USB — izbor uređaja mora biti ručan

Fajl koji se piše je `nova-os-0.1.0-amd64.iso` (3,13 GB, SHA256 počinje sa `c0e848b4`). Treba vam USB od **najmanje
8 GB** (4 GB je premalo za ovu sliku) na kojem nema ničega što vam treba.

Dve provere pre pisanja:
1. Velčina i model USB-a moraju se poklapati sa onim što vidite u Windows Exploreru.
2. Heš: `Get-FileHash -Algorithm SHA256 .\nova-os-0.1.0-amd64.iso` treba da da `C0E848B4...01AFBB` (velika/mala slova nebitna).

**Opcija A — Rufus (jedan USB po buildu).** Pokrenite Rufus, u polju „Boot selection" stavite putanju do `.iso`,
izaberite **DD / raw write** kad Rufus pita, i potvrdu dajte tek kad provera slova uređaja odgovara tom USB-u.
Trajanje zavisi od USB-a i može biti i 20+ minuta; ne prekidajte.

**Opcija B — Ventoy (jednom flashovan USB, posle samo kopirate `.iso` kao običan fajl).** Praktičnije dok se
buildovi menjaju, ali Ventoy podiže sliku preko sopstvenog GRUB-a, pa **uspešan boot pod Ventoy-om nije dokaz
da radi i sirovo napisana slika**. Za konačnu proveru na Celeronu koristite opciju A.

Pisanje ISO-a briše prethodni sadržaj USB-a. Projekat ne izdaje automatske `dd`, format ili partition komande. Ne pravite boot USB na disku sa važnim podacima. Bez proverene image-writing operacije ne pretpostavljajte da kopiranje .iso fajla na USB čini USB bootabilnim.

## 3. Live provera

**Šta se vidi odmah posle uključivanja.** Na Legacy BIOS mašini (stariji Celeron) boot ide sam: isolinux ima
timeout od 10 s i podiže „Start Linux Mint" bez pitanja. Na UEFI mašini se pojavi GRUB meni sa listom unosa i
**stoji na ekranu** dok ne pritisnete Enter — nasleđena Mint-ova konfiguracija nema `set timeout`. To je očekivano,
nije kvar; prvi unos na listi je pravi. Upravo tako je i snimljeno u emulaciji: kadar 002 u
`docs/evidence/boot-uefi-4096mb-run41361076620/` je meni, a kadar 013 je desktop koji se pojavio posle Enter-a.

Pre otvaranja instalera proverite:

- Ispravan BIOS/UEFI režim (`nova-hardware`).
- CPU i RAM; 1 GB je ispod upstream minimuma i installer može ostati bez memorije.
- Prikaz i rezoluciju; tastaturu/miš; USB fleš.
- Ethernet/Wi-Fi, audio, PDF i browser.
- SATA disk je vidljiv, ali se ne menja tokom live provere.

Ako 1 GB ne dozvoljava installer-u da radi, prvo zabeležite OOM/logove. Najmanji praktičan sledeći korak je test sa privremenih 2 GB RAM-a ako hardver podržava, ne slepo dodavanje swap-a na disk sa podacima. Nije potvrđena alternativna low-memory instalacija.

## 4. Instalacija

Otvorite nasleđeni Mint installer iz live sesije. Može prikazivati Mint oznake: Nova ne sadrži novi particioner.

- Izaberite jezik, raspored tastature i vremensku zonu.
- Pre bilo koje promene proverite oznaku/model/veličinu ciljnog diska.
- Opcija **Erase disk** trajno briše sve na izabranom disku. Koristite je samo za potvrđeno prazan, namenski disk.
- Za postojeće podatke i dual boot koristite ručno particionisanje samo ako razumete postojeće particije; pre toga backup i plan oporavka.
- UEFI zahteva odgovarajuću EFI sistemsku particiju; Legacy BIOS drugi bootloader raspored. Prepustite validaciju installer-u i proverite režim boot-a.
- Offline instalacija koristi sadržaj ISO-a. Novi Wi-Fi/proprietary drajveri ili opcione aplikacije mogu zahtevati internet.

Nijedna od ovih instalacija nije još izvršena i potvrđena u ovoj sesiji.

## 5. Prvi ulazak i ažuriranja

Prvi Nova ulazak otvara lokalni vodič jednom po korisniku. Program nije pozadinski servis. Posle instalacije:

```sh
nova-performance status
nova-hardware > hardware.json
nova-benchmark --output benchmark-installed.json
nova-compat status
```

`nova-performance status` ne traži root i ništa ne menja — prijaviće MemTotal, koji zram profil mašina zaslužuje, instalirani procenat pool-a, aktivne `/dev/zram*` uređaje i žive `vm.swappiness`/`vm.page-cluster`. `sudo nova-performance apply` zatim postavlja 35% pool, a na mašini koja prijavi 1,5 GB ili manje 50% pool, uz `vm.swappiness=140` i `vm.page-cluster=0` samo ako zram zaista postoji; prethodne vrednosti se zapisuju i vraćaju rollback-om.

Koristite Update Manager za aktuelna bezbednosna ažuriranja. Po potrebi proverite `sudo ufw status verbose` i `zramctl`/`swapon --show`; ne pretpostavljajte aktivaciju bez izlaza tih komandi. Softver se dodaje preko Software Manager-a. Wine/Steam/Bottles ne dolaze automatski.

## 6. Oporavak

- GRUB recovery/prior kernel ili verified live USB služe dijagnostici.
- Ako nov stock kernel regresira, privremeno pokrenite prethodni instalirani kernel i zabeležite problem. Ne uklanjajte sve kernale.
- `sudo nova-performance rollback` vraća originalni zram/journald profil, uklanja low-memory drop-in i vraća `vm.swappiness`/`vm.page-cluster` na vrednosti zabilježene pri apply-u; restartuje samo aktivne odgovarajuće servise i ne gasi mrežu/audio/security.
- Originalni skel je u `/var/lib/nova/backups/skel`; vratite samo pregledane pojedinačne fajlove i odjavite/prijavite korisnika. Postojeći korisnički `.config/xfce4` prvo sačuvati.
- Tema se može promeniti u XFCE Appearance ili `nova-theme light`.
- Uklonjen Wine prefix je u `~/.local/share/nova/prefix-trash`; vratite ga pre pokretanja Wine-a, ne dok aplikacije rade. Aktivne Wine procese zatvorite pre uklanjanja prefiksa.

Popravka GRUB-a, filesystem-a ili particija zahteva identifikaciju stvarnog diska i backup. Projekat namerno ne automatizuje te rizične komande.
