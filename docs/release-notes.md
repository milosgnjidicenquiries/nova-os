# Nova OS 0.1.0 — razvojna beleška

Datum: 2026-10-29. **Source-only izdanje; nije javno potvrđen bootabilni release.**

## Implementirano u izvoru

- Pinned Mint 22.1 XFCE / Ubuntu noble / amd64 baza i potpisani source-ISO verifier.
- Minimalni manifest, optional removal lista sa dependency-plan zaštitom.
- Originalne Nova/Nova-Dark GTK2/GTK3/XFWM teme, ikone i vektorska pozadina.
- XFCE panel, launcheri, meni/search, tray/audio/power/clock i prečice.
- Linux hardware JSON, stvarni benchmark collector za ciljnu sesiju i fixture testovi.
- zram/journald profili sa sačuvanim originalima i eksplicitnim rollback-om, bez gašenja essential servisa.
- Opcioni compatibility CLI/GTK center i ograničen privilegovani helper; korisnički Wine prefixes i reversible removal.
- `nova-performance status` (read-only, bez roota), hardverski uslovljen RAM profil: 50% zram pool i drop-in s `vm.swappiness`, `vm.page-cluster`, `vm.vfs_cache_pressure` i `vm.dirty_background_bytes`/`vm.dirty_bytes` samo kad mašina prijavi ≤1,5 GB i `/proc/swaps` pokaže aktivan zram; žive vrednosti se zapisuju i vraćaju rollback-om.
- `nova-performance-auto.service` pokreće `apply` pri svakom bootu instaliranog sistema, posle `zramswap.service`; rollback piše `/var/lib/nova/performance-auto.disabled` kao trajni odustanak, a `apply` ga briše.
- Firefox memorija: RAM cache ograničen na 32 MiB, hardware video decode isključen za r600/pre-AVX2, unload pozadinskih tabova eksplicitan; sve kao `pref`, nikako `lockPref`.
- Windows 11 sloj: 46x32 caption polje, 2 px fokus prsten, accent podvlačenje fokusanog polja, ravni treeview headeri s separatorima, sidebar i infobar površine, scrollbar thumb koji se zadebljava pod pointerom, crveni close hover u CSD-u, Super+strelice za snap i Super+Shift+strelice za premještanje između monitora.
- `nova-benchmark` sada prijavljuje PSS i RSS rollup po imenu procesa, swap/`/dev/zram*` uređaje s izmjerenim lz4 omjerom i CPU po procesu u istom petosekundnom prozoru.
- Lokalni first-boot vodič; Software Manager, updater i package manager ostaju upstream.
- `pref()` defaulti za Firefox (dva content procesa, ograničen page-cache, bez GPU akceleracije i feedova) i first-boot koji na ≤1,5 GB šalje obaveštenje umesto da diže pregledač — isti prag kao performance profil; stranica dobrodošlice ostaje u meniju.
- Panel u Windows 11 rasporedu: centrirana grupa meni/pokretači/prozori, 48 px, ikonice bez natpisa, dvoredni sat; tema sa 4 px kontrolama, 8 px flyout uglima, obojenom selekcijom i zaobljenim naslovnom trakom (zaobljivanje zavisi od XFWM podrške).
- `nova-defaults` package staging, izolovan mount namespace, chroot remaster, kernel/initrd sinhronizacija, BIOS/UEFI replay i structural ISO verifier.
- Build, instalaciona, recovery i QA dokumentacija; license inventory export.

## Poznata ograničenja

1. Jedna slika (`nova-build-8`) je izgrađena i viđena kako u emulaciji diže live XFCE desktop, BIOS i UEFI putanjom, sa 4 GB i sa 1 GB. Instalacija na disk, pravi hardver i Secure Boot nisu potvrđeni. Promene u ovoj listi (panel, CSS, Firefox defaulti, first-boot) nisu još nigde renderovane — strukturne provere i bash simulacije jesu, vizuelna i memorijska verifikacija tek dolaze sa sledećim build-om i boot capture-om.
2. 1 GB je ispod zvaničnog Mint minimuma 2 GB. Idle 250–400 MB i browser usability nisu izmereni. Installer može zahtevati više memorije. „Sve ispod 500 MB s pokrenutim Firefoxom“ se ne tvrdi i ne može se postići podešavanjem — Firefox sam traži više stotina MB, a mjerenje odlučuje i koliko sesija stvarno košta.
3. CPU mora podržavati amd64; dijagnostika proverava LM/NX/SSE2, ali pojedinačni browseri/aplikacije mogu zahtevati dodatne instrukcije. Nema 32-bit Nova ISO-a.
4. Secure Boot nije testiran; očuvan upstream boot materijal nije dokaz funkcionalnosti.
5. XFCE monitor/wallpaper migracija i GTK tema zahtevaju stvarni UI test. First-boot HTML je DOM-smoke testiran, ne vizuelno potvrđen zbog skrivenog browser viewport-a.
6. Wine/Bottles/Steam instalacije i konkretni Windows programi nisu testirani. Prefix CLI nije sandbox za zlonameran program. Anti-cheat, Vulkan, DirectX i RAM ograničenja ostaju.
7. Bottles zahteva već instaliran Flatpak i već konfigurisan zvanični **user** Flathub remote; nisu automatski dodati. Helper prihvata samo zvanične Mint/Ubuntu hostove, pa drugi mirrors/PPAs izazivaju jasno odbijanje čak i kada ih je korisnik ranije dodao.
8. DXVK/VKD3D/Proton se ne instaliraju posebno automatski; Proton bira korisnik u opcionalnom Steam-u. Nema testirane lokalne game compatibility liste.
9. Nasleđeni Mint paketi/branding i poneke dependency aplikacije mogu ostati; konačna minimalnost se utvrđuje iz stvarnog build manifesta. Installer nije novi Nova particioner.
10. Skriptovan build i tačan package lock nisu bit-identična reproducibilnost. Potrebne su arhivirane verzije/snapshot i ponovljeni hash testovi.
11. Firmware/proprietary sadržaj nasleđenog ISO-a nije konačno pravno auditovan; copyright inventory je pomoć, ne approval. Upstream oznake i zahtevi za objavu odgovarajućeg izvornog koda moraju se poštovati.
12. Nema posebne sertifikacije CPU/GPU/Wi-Fi uređaja, disk instalacije niti fizičkog USB testa.
13. Low-memory profil (50% zram pool i svih pet `vm.*` tunable-a), `nova-performance status` i `nova-performance-auto.service` nikad nisu izvršeni na živoj Linux mašini; testirani su samo sintaksa bash-a i ugovori u fixture testovima. `sysctl -p` zahteva procps, a `smaps_rollup` zahteva kernel 4.14+.
14. Novi CSS selectori, 46x32 caption polje i Super+Shift+strelice nisu renderovani ni pritisnuti u pravom GTK/XFCE okruženju; nepoznate xfwm4 akcije se tiho ignorišu, ne javljaju grešku.
15. Vrednosti tunable-a su mehanizam, ne izmereno poboljšanje: `vm.dirty_background_bytes`/`vm.dirty_bytes` su apsolutne kape (ne proporcionalne RAM-u), pa se na mašini s više memorije moraju ponovo proceniti. `--squashfs-comp` menja samo izlaz remastera; `source` (zatečeње iz baze) ostaje default dok neki kandidat ne bude izmerjen na ciljnom CPU-u.

## Spremnost faza

Faze 1–7 imaju razvojnu implementaciju i lokalne alatske provere. Faza 8 čeka Linux build VM; 9–11 zavise od ISO-a i test hardvera. Ova dokumentacija ne znači da je faza 12/release approval završena.

Sledeći korak: Linux build prema `docs/build-guide.md`, zatim VM BIOS boot sa 1024 MB i detaljno beleženje stvarnog rezultata. Ne objavljivati kao gotov svakodnevni OS pre QA.
