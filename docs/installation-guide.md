# VM, USB, instalacija i oporavak

**Nema izgrađenog/testiranog ISO-a u ovom projektu još.** Ovaj postupak se izvršava tek nakon uspešnog Linux build-a i provere output SHA256.

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

Napravite rezervnu kopiju podataka. Izberite prazan USB odgovarajuće veličine. Koristite postojeći provereni USB image writer (Mint USB Image Writer ili Rufus na Windows-u) i **ručno proverite kapacitet, model i slovo USB uređaja** pre potvrde.

Pisanje ISO-a briše prethodni sadržaj USB-a. Projekat ne izdaje automatske `dd`, format ili partition komande. Ne pravite boot USB na disku sa važnim podacima. Bez proverene image-writing operacije ne pretpostavljajte da kopiranje .iso fajla na USB čini USB bootabilnim.

## 3. Live provera

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
nova-hardware > hardware.json
nova-benchmark --output benchmark-installed.json
nova-compat status
```

Koristite Update Manager za aktuelna bezbednosna ažuriranja. Po potrebi proverite `sudo ufw status verbose` i `zramctl`/`swapon --show`; ne pretpostavljajte aktivaciju bez izlaza tih komandi. Softver se dodaje preko Software Manager-a. Wine/Steam/Bottles ne dolaze automatski.

## 6. Oporavak

- GRUB recovery/prior kernel ili verified live USB služe dijagnostici.
- Ako nov stock kernel regresira, privremeno pokrenite prethodni instalirani kernel i zabeležite problem. Ne uklanjajte sve kernale.
- `sudo nova-performance rollback` vraća originalni zram/journald profil i restartuje samo aktivne odgovarajuće servise; ne gasi mrežu/audio/security.
- Originalni skel je u `/var/lib/nova/backups/skel`; vratite samo pregledane pojedinačne fajlove i odjavite/prijavite korisnika. Postojeći korisnički `.config/xfce4` prvo sačuvati.
- Tema se može promeniti u XFCE Appearance ili `nova-theme light`.
- Uklonjen Wine prefix je u `~/.local/share/nova/prefix-trash`; vratite ga pre pokretanja Wine-a, ne dok aplikacije rade. Aktivne Wine procese zatvorite pre uklanjanja prefiksa.

Popravka GRUB-a, filesystem-a ili particija zahteva identifikaciju stvarnog diska i backup. Projekat namerno ne automatizuje te rizične komande.
