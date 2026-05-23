# Client Intake Tracking — Nexus EduVault

**Cliente:** corsi8108
**Documento gemello:** [`CLIENT_INTAKE_QUESTIONNAIRE.md`](CLIENT_INTAKE_QUESTIONNAIRE.md) — i numeri di sezione/item qui riflettono esattamente quelli del questionario.
**Data creazione tracker:** 2026-05-23
**Ultimo aggiornamento:** 2026-05-23

> **Come usare questa tabella.** Ogni riga = un item del questionario. Quando il cliente invia il materiale, aggiornare `Stato`, `Data ricezione`, `Path locale` (se applicabile) e `Note`. Stati: ⏳ in attesa, 🔄 ricevuto parzialmente, ✅ ricevuto e validato, ❌ rifiutato/non conforme, ⚪ non applicabile (es. corso disattivato in v1.0).
>
> **Bloccanti go-live (🔴):** vedi sezione finale del questionario — sono `2.1`, `2.2`, `4` (logo+palette+font), `5 (VPS)`.

---

## Tabella di tracking

| Sezione | Item | Stato | Data richiesta | Data ricezione | Path locale | Note |
|---|---|---|---|---|---|---|
| **1.1** | Dominio / hosting (esistente o nuovo) | ⏳ in attesa | YYYY-MM-DD | — | — | REI-13: finché manca, dominio = `<DOMAIN_TBD>` |
| **1.2** | Lista utenti previsti al lancio (admin/operatore/revisore) | ⏳ in attesa | YYYY-MM-DD | — | — | Almeno admin di bootstrap |
| **1.3** | Procedura reset password preferita | ⏳ in attesa | YYYY-MM-DD | — | — | Default proposto: entrambe (admin + email) |
| **2.1** 🔴 | D.Lgs 81/08 — Testo Unico Sicurezza (PDF integrale consolidato) | ⏳ in attesa | YYYY-MM-DD | — | `storage/pdfs/dlgs_81_08.pdf` | **BLOCCANTE GO-LIVE**. 5/6 corsi dipendono da questo PDF |
| **2.2** 🔴 | Accordo Stato-Regioni 21/12/2011 (PDF) | ⏳ in attesa | YYYY-MM-DD | — | `storage/pdfs/accordo_stato_regioni_2011.pdf` | **BLOCCANTE GO-LIVE**. 4/6 corsi (lavoratori + preposti) |
| **2.3** | DM 388/2003 — Primo Soccorso aziendale (PDF) | ⏳ in attesa | YYYY-MM-DD | — | `storage/pdfs/dm_388_2003.pdf` | TEST chunking minimo (4 pagine, BP §16 punto 3). Bloccante solo se attivato 3.3 |
| **2.4** | DM 02/09/2021 — Antincendio (PDF) | ⏳ in attesa | YYYY-MM-DD | — | `storage/pdfs/dm_02_09_2021.pdf` | Bloccante solo se attivato 3.4 |
| **2.5** | Reg. (CE) 852/2004 — HACCP base (PDF EUR-Lex) | ⏳ in attesa | YYYY-MM-DD | — | `storage/pdfs/reg_ce_852_2004.pdf` | Bloccante solo se attivato 3.5 |
| **2.6** | Normativa HACCP regionale Campania (DGR/atto + PDF) | ⏳ in attesa | YYYY-MM-DD | — | `storage/pdfs/haccp_campania.pdf` | Validazione JOIN regionale NULL-safe (BP §13). Bloccante solo se 3.5 attivato per Campania |
| **2.7** | Altri documenti normativi opzionali | ⏳ in attesa | YYYY-MM-DD | — | `storage/pdfs/extra/` | Lista a discrezione cliente |
| **3.1** | Attivazione corso `sicurezza_lavoratori_generale` (Sì/No + durata + audience) | ⏳ in attesa | YYYY-MM-DD | — | — | Ore vincolate per legge: 4 |
| **3.2** | Attivazione corso `sicurezza_lavoratori_specifica_basso` | ⏳ in attesa | YYYY-MM-DD | — | — | Ore vincolate: 4 |
| **3.3** | Attivazione corso `primo_soccorso_gruppo_b_c` | ⏳ in attesa | YYYY-MM-DD | — | — | Ore vincolate: 12 |
| **3.4** | Attivazione corso `antincendio_livello_1` | ⏳ in attesa | YYYY-MM-DD | — | — | Ore vincolate: 4 |
| **3.5** | Attivazione corso `haccp_addetto` (+ regione + durata 4-8) | ⏳ in attesa | YYYY-MM-DD | — | — | ⚠️ richiede validazione regionale (`regional: True`) |
| **3.6** | Attivazione corso `preposti` | ⏳ in attesa | YYYY-MM-DD | — | — | Ore vincolate: 8 |
| **3.7** | Corsi futuri (v1.1+) non in catalogo | ⏳ in attesa | YYYY-MM-DD | — | — | Informativo, NON v1.0 |
| **4.1** 🔴 | Logo (PNG 512×512 + 2048×2048 + SVG opzionale + B/N) | ⏳ in attesa | YYYY-MM-DD | — | `assets/templates/` + `assets/branding/logo/` | **BLOCCANTE GO-LIVE** |
| **4.2** 🔴 | Palette HEX (primario, secondario, accento, neutri) | ⏳ in attesa | YYYY-MM-DD | — | `assets/branding/palette.json` | **BLOCCANTE GO-LIVE** — usata in `tailwind.config.ts` + template PPTX |
| **4.3** 🔴 | Font ufficiale (nome + licenza + .ttf/.otf + pesi) | ⏳ in attesa | YYYY-MM-DD | — | `assets/fonts/<NomeFont>/` | **BLOCCANTE GO-LIVE**. Slot già presente `assets/fonts/Montserrat/` (fallback default) |
| **6.1** | Frequenza attesa generazione corsi + picchi stagionali | ⏳ in attesa | YYYY-MM-DD | — | — | Per dimensionamento e SLA |
| **6.2** | Numero max utenti simultanei | ⏳ in attesa | YYYY-MM-DD | — | — | Atteso 5-15. Vincolo Semaphore(1) sui job (REI-3) |
| **6.3** | Backup: frequenza `pg_dump` + retention + test restore | ⏳ in attesa | YYYY-MM-DD | — | — | Default suggerito: daily / 30gg / restore trimestrale |
| **8.1** | Date di consegna impegnate per sezioni 2, 4, e altre | ⏳ in attesa | YYYY-MM-DD | — | — | Necessario per pianificazione FASE 2 |
| **8.2** | Referente operativo lato cliente (nome, ruolo, email, canale) | ⏳ in attesa | YYYY-MM-DD | — | — | Punto di contatto unico |
| **8.3** | Secondo referente (backup) | ⏳ in attesa | YYYY-MM-DD | — | — | Opzionale ma raccomandato |
| **5 (VPS)** 🔴 | Provisioning VPS + accesso SSH + SSL/DNS + backup off-site | ⏳ in attesa | YYYY-MM-DD | — | — | **BLOCCANTE GO-LIVE**. Voce semantica del questionario (cfr. sezione finale). Senza, nessun deploy in FASE 7 |

---

## Sintesi bloccanti

| Item | Bloccante? | Senza questo non si può… |
|---|---|---|
| 2.1 D.Lgs 81/08 | 🔴 Sì | Generare 5/6 corsi (sicurezza, primo soccorso, antincendio, preposti) |
| 2.2 Accordo Stato-Regioni | 🔴 Sì | Generare 4/6 corsi (sicurezza + preposti) |
| 4 (logo + palette + font) | 🔴 Sì | Brandizzare slide/PDF, andare in produzione |
| 5 (VPS) | 🔴 Sì | Deploy FASE 7 |

Tutti gli altri item sono **non bloccanti per il go-live globale**, ma possono bloccare la disponibilità del corso specifico (es. senza 2.6 il corso HACCP Campania non parte).

---

## Path convention (per coerenza con la struttura di [BP §14.1])

- PDF normativi → `storage/pdfs/<slug_regulation>.pdf` — slug come da `COURSE_CATALOG.regs` ([BP §13])
- Logo → `assets/templates/` (master PPTX) + `assets/branding/logo/` (asset brand)
- Font → `assets/fonts/<NomeFont>/<file>.ttf|.otf` (la dir `assets/fonts/Montserrat/` esiste già come default fallback)
- Palette JSON → `assets/branding/palette.json`

> Quando un item viene ricevuto: aggiornare la cella `Stato` (✅ o 🔄), la data, e — se il file è stato effettivamente messo nel path indicato — confermarlo nelle Note. Se il path effettivo differisce, riportarlo esatto.
