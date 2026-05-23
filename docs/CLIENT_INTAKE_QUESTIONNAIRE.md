# Questionario di Intake Cliente — Nexus EduVault

**Cliente destinatario:** corsi8108
**Mittente:** Axialoop di Di Lonardo Alessandro
**Versione progetto:** Nexus EduVault v1.0 SUPREME PRODUCTION READY
**Data di invio:** ____________
**Scadenza per la restituzione completa:** ____________

> **Perché vi chiediamo queste informazioni.** Nexus EduVault è una piattaforma di generazione automatica di corsi di formazione ancorati alla normativa reale (D.Lgs 81/08, Accordo Stato-Regioni, HACCP, Primo Soccorso, Antincendio). Il principio architetturale dichiarato in [BLUEPRINT §00] è che *la normativa è la fonte di verità, non l'intelligenza artificiale*: ogni slide e ogni PDF generato cita un riferimento normativo verificabile, recuperato da una Knowledge Base interna. Per costruire questa Knowledge Base e per applicare la vostra identità visiva ai materiali generati abbiamo bisogno dei materiali elencati sotto. Senza di essi alcuni moduli del sistema non possono essere collaudati in FASE 2 (test ingestion) e altri non possono andare in produzione in FASE 7 (deploy).
>
> Le sezioni marcate 🔴 **bloccano il go-live** se non completate (riepilogo finale a fondo documento).

---

## 1. Identificazione cliente e ruoli

**1.1 Dominio / hosting**
- Avete un dominio già registrato e attualmente inutilizzato (o sotto-dominio) su cui possiamo far girare la piattaforma? Sì / No: ____________
  - Se sì, indicare nome dominio: ____________
  - Se sì, indicare provider DNS (Aruba/Register/Cloudflare/altro): ____________
- In alternativa, preferite che vi proponiamo noi una soluzione (acquisto + configurazione dominio nuovo)? Sì / No: ____________
- Preferenze sull'estensione (`.it`, `.com`, `.edu`): ____________

> *Nota interna axialoop:* finché questa risposta non arriva, il dominio resta `<DOMAIN_TBD>` in tutte le config (vincolo REI-13). La decisione si applica solo in FASE 7 (deploy).

**1.2 Lista utenti previsti al lancio**
Compilare la tabella per ogni utente che avrà accesso alla piattaforma. I ruoli previsti sono: `admin` (gestione completa), `operatore` (genera corsi), `revisore` (approva contenuti). Indicare almeno l'admin di bootstrap.

| # | Nome e Cognome | Email | Ruolo | Note (opzionale) |
|---|---|---|---|---|
| 1 | ____________ | ____________ | admin | ____________ |
| 2 | ____________ | ____________ | ____________ | ____________ |
| 3 | ____________ | ____________ | ____________ | ____________ |
| 4 | ____________ | ____________ | ____________ | ____________ |
| 5 | ____________ | ____________ | ____________ | ____________ |

> Aggiungere righe se necessario. L'utente admin di bootstrap riceverà via canale sicuro la password iniziale e dovrà cambiarla al primo login.

**1.3 Procedura di reset password preferita**
- [ ] Reset manuale via admin (l'admin imposta una nuova password temporanea e la comunica all'utente fuori canale)
- [ ] Reset via email (l'utente riceve un link temporaneo e si auto-gestisce)
- [ ] Entrambe disponibili (admin può forzare, ma l'utente può anche auto-resettarsi via email)

---

## 2. Materiale normativo richiesto 🔴 (PDF — TUTTI obbligatori per FASE 2)

Per ciascun documento richiediamo: **PDF integrale, versione consolidata e vigente, data di pubblicazione/ultimo aggiornamento, fonte ufficiale** (es. normattiva.it, EUR-Lex, Gazzetta Ufficiale). I PDF devono essere testuali (non scansioni-immagine), altrimenti il chunking normativo non li può processare ([BLUEPRINT §06]).

**2.1 D.Lgs 81/08 — Testo Unico Sicurezza** 🔴
- PDF integrale fornito? Sì / No: ____________
- Versione consolidata aggiornata al (data): ____________
- Fonte ufficiale (URL): ____________
- Note (eventuali allegati separati): ____________

**2.2 Accordo Stato-Regioni 21/12/2011 (Formazione lavoratori)** 🔴
- PDF integrale fornito? Sì / No: ____________
- Versione: ____________
- Fonte ufficiale (URL): ____________
- Note: ____________

**2.3 DM 388/2003 (Primo Soccorso aziendale)**
- PDF integrale fornito? Sì / No: ____________
- Versione consolidata aggiornata al (data): ____________
- Fonte ufficiale (URL): ____________

**2.4 DM 02/09/2021 (Criteri formazione addetti antincendio)**
- PDF integrale fornito? Sì / No: ____________
- Versione: ____________
- Fonte ufficiale (URL): ____________

**2.5 Reg. (CE) 852/2004 (Igiene dei prodotti alimentari — HACCP base)**
- PDF integrale fornito? Sì / No: ____________
- Versione consolidata aggiornata al (data): ____________
- Fonte ufficiale (URL EUR-Lex): ____________

**2.6 Normativa HACCP regionale (Campania)** — necessaria per il corso `haccp_addetto` con `regional: True` ([BLUEPRINT §13])
- Atto regionale di riferimento (es. DGR Campania n. __/____ del ________): ____________
- PDF integrale fornito? Sì / No: ____________
- Fonte ufficiale (URL Regione Campania o BURC): ____________
- Note: ____________

**2.7 Altri documenti normativi che ritenete debbano essere inclusi nella Knowledge Base** (opzionale)
| Documento | Versione/data | Fonte | Per quale corso serve |
|---|---|---|---|
| ____________ | ____________ | ____________ | ____________ |
| ____________ | ____________ | ____________ | ____________ |

---

## 3. Catalogo corsi target (cross-check con [BLUEPRINT §13])

Il sistema supporta 6 tipi corso predefiniti. Per ciascuno indicate se va attivato in v1.0, la durata target, il pubblico, e — dove applicabile — se richiede validazione regionale. Le ore minime/massime e le normative collegate **NON sono modificabili** (vincolate dalla legge): sono mostrate per riferimento.

**3.1 Sicurezza Lavoratori — Formazione Generale** (slug: `sicurezza_lavoratori_generale`)
- Normative: D.Lgs 81/08 + Accordo Stato-Regioni 2011
- Ore vincolate: 4 (fisse)
- Attivare in v1.0? Sì / No: ____________
- Durata target in ore: ____________
- Target audience: ____________
- Richiede validazione regionale? Sì / No: ____________
- Note: ____________

**3.2 Sicurezza Lavoratori — Formazione Specifica Rischio Basso** (slug: `sicurezza_lavoratori_specifica_basso`)
- Normative: D.Lgs 81/08 + Accordo Stato-Regioni 2011
- Ore vincolate: 4 (fisse)
- Attivare in v1.0? Sì / No: ____________
- Durata target in ore: ____________
- Target audience: ____________
- Richiede validazione regionale? Sì / No: ____________
- Note: ____________

**3.3 Primo Soccorso — Gruppi B e C** (slug: `primo_soccorso_gruppo_b_c`)
- Normative: D.Lgs 81/08 + DM 388/2003
- Ore vincolate: 12 (fisse)
- Attivare in v1.0? Sì / No: ____________
- Durata target in ore: ____________
- Target audience: ____________
- Richiede validazione regionale? Sì / No: ____________
- Note: ____________

**3.4 Addetto Antincendio — Livello 1** (slug: `antincendio_livello_1`)
- Normative: D.Lgs 81/08 + DM 02/09/2021
- Ore vincolate: 4 (fisse)
- Attivare in v1.0? Sì / No: ____________
- Durata target in ore: ____________
- Target audience: ____________
- Richiede validazione regionale? Sì / No: ____________
- Note: ____________

**3.5 Formazione HACCP Addetti** (slug: `haccp_addetto`) ⚠️ **richiede validazione regionale di default**
- Normative: Reg. CE 852/2004 + normativa regionale Campania (vedi 2.6)
- Ore: range 4-8 (decidere durata target)
- Attivare in v1.0? Sì / No: ____________
- Durata target in ore (4-8): ____________
- Target audience: ____________
- Regione di erogazione (Campania o nazionale): ____________
- Note: ____________

**3.6 Formazione Preposti** (slug: `preposti`)
- Normative: D.Lgs 81/08 + Accordo Stato-Regioni 2011
- Ore vincolate: 8 (fisse)
- Attivare in v1.0? Sì / No: ____________
- Durata target in ore: ____________
- Target audience: ____________
- Richiede validazione regionale? Sì / No: ____________
- Note: ____________

**3.7 Corsi NON in catalogo che vorreste fossero aggiunti in versioni future** (informativo, NON in v1.0)
- ____________
- ____________

---

## 4. Identità visuale e branding 🔴 (LAVORO UMANO — non delegabile a Claude Code, [BP §16 punto 4])

Tutti i materiali generati (slide PPTX e dispense PDF) devono rispettare la vostra identità visiva. Richiediamo file fisici, non descrizioni a parole.

**4.1 Logo**
- Logo principale in PNG con sfondo trasparente, **512×512 px** — file fornito (nome): ____________
- Logo principale in PNG con sfondo trasparente, **2048×2048 px** — file fornito (nome): ____________
- Logo in formato vettoriale SVG (se disponibile): ____________
- Versione monocromatica (per stampa B/N) se diversa: ____________

**4.2 Palette colori brand** (codice HEX, es. `#1A2B3C`)
- Colore primario: `#________`
- Colore secondario: `#________`
- Colore accento: `#________`
- Neutro chiaro (background): `#________`
- Neutro scuro (testo): `#________`
- Eventuali colori aggiuntivi: ____________

**4.3 Font ufficiale**
- Nome del font: ____________
- Licenza posseduta (commerciale / open source / Google Fonts): ____________
- File `.ttf` o `.otf` fornito (nome): ____________
- Font fallback in caso di non disponibilità (es. Montserrat, Inter): ____________
- Pesi/varianti richieste (Regular, Bold, ecc.): ____________

---

## 6. SLA e ciclo di vita

**6.1 Frequenza attesa di generazione corsi**
- Numero corsi/mese previsto: ____________
- Picchi stagionali noti (es. inizio anno fiscale, scadenze formative): ____________

**6.2 Utenti simultanei**
- Numero massimo utenti previsti in uso contemporaneo (valore atteso BP: 5-15): ____________

> *Nota tecnica:* il sistema processa **un solo job di generazione corso alla volta** (vincolo architetturale `Semaphore(1)` per python-pptx, [REI-3 + D-02]). Gli utenti possono usare l'interfaccia simultaneamente, ma le generazioni vengono accodate.

**6.3 Backup database**
- Frequenza desiderata `pg_dump`: ____________ (consigliato: giornaliero)
- Retention (per quanti giorni/settimane mantenere i backup): ____________ (consigliato: 30 giorni)
- Test di restore periodico richiesto? Sì / No — frequenza: ____________

---

## 8. Tempi di ritorno

**8.1 Date di consegna impegnate dal cliente**
| Sezione | Data impegnata di consegna completa |
|---|---|
| Sezione 2 (Materiali normativi 🔴) | ____________ |
| Sezione 4 (Identità visuale 🔴) | ____________ |
| Sezioni 1, 3, 6 (informative) | ____________ |

**8.2 Persona di riferimento operativa lato cliente** (referente unico per chiarimenti e consegna materiali)
- Nome e cognome: ____________
- Ruolo: ____________
- Email: ____________
- Telefono / canale chat preferito: ____________

**8.3 Eventuale secondo referente** (in caso di assenza del primo)
- Nome e cognome: ____________
- Email: ____________

---

## Cosa BLOCCA il go-live se manca

Le seguenti voci sono **bloccanti**. Senza di esse il sistema non può essere consegnato:

- 🔴 **2.1** — D.Lgs 81/08 PDF integrale (Testo Unico Sicurezza). Senza, 5 corsi su 6 non producibili.
- 🔴 **2.2** — Accordo Stato-Regioni 21/12/2011. Senza, 4 corsi su 6 non producibili (tutti i corsi di formazione lavoratori e preposti).
- 🔴 **4 (logo + palette + font)** — Identità visuale completa: logo (4.1) + palette HEX (4.2) + font ufficiale + licenza (4.3). Senza, slide e PDF non possono essere brandizzati e i materiali generati non sono pubblicabili.
- 🔴 **5 (VPS)** — VPS provisioned con accesso amministrativo, SSL/DNS e backup off-site. Senza, nessun deploy possibile in FASE 7.

Le voci 2.3, 2.4, 2.5, 2.6 sono bloccanti **solo per i rispettivi corsi**: se il corso non viene attivato in v1.0 (sezione 3), il documento normativo associato può essere posticipato a v1.1.

---

**Compilato da:** ____________
**Data di compilazione:** ____________
**Firma/conferma email:** ____________
