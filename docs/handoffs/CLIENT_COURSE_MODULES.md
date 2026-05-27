# Catalogo moduli ufficiali cliente corsi8108

> Raccolta dei moduli ufficiali per i 10 corsi prioritari di **corsi8108.it**, scrapata
> 2026-05-25 via WebFetch. Fonte: pagine dettaglio corso del sito cliente.
>
> **Uso**: input per il refactor di `config/catalog_config.py` con campi
> `official_modules` (vincolanti per audit ASL/Ispettorato del Lavoro) e
> `subtopic_breakdown` (suddivisione operativa per PacingEngine + RAG retrieval).
>
> **Allineamento PDF normativi disponibili in DB** (vedi tabella in fondo):
> - ✅ DM 388/2003 — Primo Soccorso B/C e A (corsi completamente coperti)
> - ⚠️ D.Lgs 81/08 — Tutti gli altri corsi (parziale, mancano Accordi SR e altri DM)

---

## 1. Primo Soccorso — Aziende B e C (8 ore) ✅ FULL COVERAGE

**URL**: <https://www.corsi8108.it/formazione-addetto-primo-soccorso-aziende-b-e-c-8-ore/>

**Normative di riferimento (citate ESPLICITAMENTE dal cliente)**:
- D.Lgs. 81/08 art. 45 comma 2
- D.M. 388/2003

### Moduli ufficiali

| # | Modulo | Ore | Modalità |
|---|---|---|---|
| A | Aspetti normativi e riconoscimento emergenze | 4 | online |
| B | Traumi e patologie in ambiente lavoro | 4 | online |
| C | Formazione pratica (escluso da v1) | 4 | presenza |

### Argomenti dettagliati per modulo

**Modulo A (4h)**: aspetti legislativi e organizzativi; allertamento sistema soccorso;
individuazione cause infortunio; comunicazione servizi emergenza; riconoscimento
emergenze sanitarie; accertamento condizioni psicofisiche; nozioni anatomia apparato
cardiovascolare e respiratorio; tecniche autoprotezione; sostenimento funzioni vitali;
riconoscimento limiti intervento (lipotimia, sincope, shock, edema polmonare, crisi
asmatica, dolore stenocardico, reazioni allergiche, convulsioni, emorragie); conoscere
i rischi specifici dell'attività svolta.

**Modulo B (4h)**: traumi in ambiente lavoro; anatomia scheletro; lussazioni e
fratture; traumi cranio-encefalici e colonna vertebrale; traumi toracico-addominali;
patologie specifiche ambiente lavoro; lesioni da freddo/calore; lesioni da corrente
elettrica; lesioni da agenti chimici; intossicazioni; ferite lacero contuse;
emorragie esterne.

**Modulo C (4h)**: pratica presso medico, medico competente, personale infermieristico
o specializzato, secondo DM 388/2003. — **Escluso dalla generazione v1** (richiede
docente in presenza).

---

## 2. Primo Soccorso — Aziende A (10 ore) ✅ FULL COVERAGE

**URL**: <https://www.corsi8108.it/formazione-addetto-primo-soccorso-aziende-a-10-ore/>

**Normative**: D.Lgs. 81/08 art. 45 comma 2; D.M. 15 luglio 2003 n. 388.

### Differenziazione A vs B/C (vedi DM 388/2003 art. 2)

**Gruppo A** include aziende ad alto rischio: centrali termoelettriche, miniere,
aziende con agenti biologici gruppo 3-4 (allegato XLIV D.Lgs 81/08), aziende
chimiche con sostanze esplosive/infiammabili, cantieri temporanei o mobili >5
lavoratori/anno, aziende con indice infortuni INAIL alto, aziende >5 dipendenti
in agricoltura. **Rischio mortalità superiore → corso più operativo (BLS, RCP)**.

**Gruppi B+C** sono "tutti gli altri" (B ≥3 lavoratori, C <3, stesso programma 8h
perché stesso profilo rischio medio/basso).

### Differenze didattiche A vs B/C (focus tecnico per content_agent)

| Aspetto | B/C (8h) | A (10h) |
|---|---|---|
| Durata Modulo A | 4h | **6h** (+50% legislativo+intervento) |
| Durata Modulo B | 4h | 4h (identico) |
| Durata Modulo C presenza | 4h | 6h (+50%) |
| Respirazione artificiale | generica | **dettagliata, operativa** |
| Massaggio cardiaco esterno (BLS) | generico | **dettagliato, tecniche** |
| Lipotimia, sincope | menzionati | non menzionati esplicitamente |
| Convulsioni | menzionate | non menzionate esplicitamente |
| Dolore stenocardico | menzionato | non menzionato esplicitamente |
| Shock, edema polmonare | ✅ | ✅ |
| Crisi asmatica, allergie | ✅ | ✅ |
| Emorragie esterne | ✅ | ✅ |

**Conclusione tecnica**: **A è più operativo/avanzato** (enfatizza tecniche di
intervento immediato per scenari ad alto rischio mortalità). **B/C è più ampio
nell'elenco patologie minori** (copre più condizioni in tono didattico-descrittivo).

Modulo B (traumi/patologie) è **identico** tra A e B/C.

### Moduli

| # | Modulo | Ore | Modalità |
|---|---|---|---|
| A | Aspetti legislativi + tecniche operative BLS | 6 | online |
| B | Traumi e patologie | 4 | online |
| C | Formazione pratica (escluso v1) | 6 | presenza |

**Modulo A (6h)** [esteso rispetto a B/C, focus operativo]: aspetti legislativi e
organizzativi; allertamento sistema soccorso; riconoscimento emergenze sanitarie;
accertamento condizioni psicofisiche infortunato; tecniche autoprotezione;
sostentamento funzioni vitali; **respirazione artificiale** (tecnica dettagliata);
**massaggio cardiaco esterno BLS** (tecnica dettagliata); riconoscimento shock,
edema polmonare, asma, reazioni allergiche, emorragie esterne.

**Modulo B (4h)** [identico a B/C]: traumi ambiente lavoro; anatomia scheletro;
fratture e lussazioni; traumi cranio-encefalici e colonna vertebrale; lesioni
toracico-addominali; patologie specifiche; lesioni da freddo/calore, corrente
elettrica, agenti chimici; intossicazioni; ferite e emorragie esterne.

### Strategia catalog (proposta v1)

Differenziazione gestita tramite nuovi campi:
- `risk_profile: "alto"` (A) vs `"medio_basso"` (B/C)
- `target_audience` testuale (per system prompt LLM)
- `focus_areas` per ogni `official_modules` entry

Vedi esempio JSON in fondo a questo documento.

> ⚠️ **Attualmente nel catalog esiste SOLO `primo_soccorso_gruppo_b_c`** —
> `primo_soccorso_gruppo_a` va aggiunto nel refactor catalog post-FASE 1.

---

## 3. Formazione Lavoratori — Generale (4 ore) ⚠️ PARTIAL (manca Accordo SR 2011)

**URL**: <https://www.corsi8108.it/formazione-lavoratori-formazione-generale-4-ore/>

**Normative**: D.Lgs. 81/08 art. 37; Accordo Stato-Regioni 21/12/2011.

| # | Modulo | Ore | Modalità |
|---|---|---|---|
| 1 | Modulo Generale unico | 4 | online |

**Argomenti**: concetti di rischio; danno; prevenzione; protezione; organizzazione
prevenzione aziendale; diritti, doveri e sanzioni per i vari soggetti aziendali;
organi di vigilanza, controllo e assistenza.

---

## 4. Formazione Lavoratori — Rischio Basso (8 ore) ⚠️ PARTIAL

**URL**: <https://www.corsi8108.it/formazione-lavoratori-rischio-basso-8-ore/>

**Normative**: Art. 37 c.2 D.Lgs. 81/08; Accordo SR 21/12/2011.

| # | Modulo | Ore | Modalità |
|---|---|---|---|
| 1 | Modulo Generale | 4 | online |
| 2 | Modulo Specifico (Rischio Basso, ATECO) | 4 | online o docente |

**Modulo Generale (4h)** [identico al corso #3]: concetti rischio, danno, prevenzione,
protezione, organizzazione aziendale, diritti/doveri/sanzioni, vigilanza.

**Modulo Specifico Basso (4h)**: rischi infortuni; meccanici generali; elettrici
generali; macchine; attrezzature; cadute dall'alto; esplosione; chimici (nebbie, oli
fumi, vapori, polveri, etichettatura); cancerogeni; biologici; fisici (rumore,
vibrazione, radiazioni); microclima e illuminazione; videoterminali; DPI e
organizzazione lavoro; sorveglianza sanitaria; ambienti lavoro; stress lavoro-correlato;
movimentazione manuale carichi; movimentazione merci; segnaletica; emergenze;
procedure sicurezza per profilo rischio; esodo e incendi; primo soccorso organizzativo;
incidenti/infortuni mancati.

---

## 5. Formazione Lavoratori — Rischio Medio (12 ore) ⚠️ PARTIAL

**URL**: <https://www.corsi8108.it/formazione-lavoratori-rischio-medio-12-ore/>

**Normative**: Art. 37 c.2 D.Lgs. 81/08; Accordo SR 21/12/2011; Accordo SR 07/07/2016
(GU n. 193 del 19/08/2016).

| # | Modulo | Ore | Modalità |
|---|---|---|---|
| 1 | Modulo Generale | 4 | online |
| 2 | Modulo Specifico (Rischio Medio) | 8 | docente in presenza |

Argomenti identici a Rischio Basso ma con copertura più approfondita nel Modulo
Specifico (durata 8h vs 4h).

---

## 6. Formazione Lavoratori — Rischio Alto (16 ore) ⚠️ PARTIAL

**URL**: <https://www.corsi8108.it/formazione-lavoratori-rischio-alto-16-ore/>

**Normative**: Art. 37 D.Lgs. 81/08; Accordo SR 21/12/2011 e 07/07/2016.

| # | Modulo | Ore | Modalità |
|---|---|---|---|
| 1 | Modulo Generale | 4 | online |
| 2 | Modulo Specifico (Rischio Alto) | 12 | docente in presenza |

Argomenti identici alle versioni Basso/Medio ma con copertura massima 12h nel
Modulo Specifico.

---

## 7. ASPP/RSPP Modulo A (28 ore) ⚠️ PARTIAL (manca Accordo SR 2016)

**URL**: <https://www.corsi8108.it/corso-di-formazione-aspprspp-modulo-a-28-ore/>

**Normative**: D.Lgs. 81/08; Accordo SR 21/12/2011 (validità nazionale degli
attestati).

| # | Unità didattica | Ore |
|---|---|---|
| A1 | Introduzione + approccio preventivo D.Lgs 81 + sistema istituzionale prevenzione + vigilanza e assistenza | 8 |
| A2 | Attori del sistema di prevenzione aziendale | 4 |
| A3 | Processo di valutazione dei rischi | 8 |
| A4 | Applicazioni organizzative valutazione rischi + gestione emergenze + sorveglianza sanitaria | 4 |
| A5 | Strumenti relazionali: informazione, formazione, addestramento, consultazione, partecipazione | 4 |

---

## 8. Antincendio Livello 1 — Rischio Basso (4 ore) ⚠️ PARTIAL (manca DM 10/03/1998)

**URL**: <https://www.corsi8108.it/corso-formazione-antincendio-basso-rischio/>

**Normative**: Allegato IX del DM 10/03/1998 (corso A, rischio incendio liv. 1);
art. 46 D.Lgs 81/08.

> ⚠️ **Nota**: il cliente cita ancora il vecchio DM 10/03/1998 (NON il nuovo DM
> 02/09/2021 che lo sostituisce dal 4/10/2022). Da verificare con cliente in FASE 7
> se aggiornare oppure mantenere riferimento storico.

| # | Modulo | Ore |
|---|---|---|
| 1 | L'Incendio e la Prevenzione | 1 |
| 2 | Protezione Antincendio e Procedure di Emergenza | 1 |
| 3 | Esercitazioni Pratiche (esclusa da v1: presenza) | 2 |

**Modulo 1 (1h)**: principi combustione, triangolo combustione, cause incendio,
prodotti combustione, sostanze estinguenti, effetti del fuoco sull'uomo, misure
preventive, divieti, comportamenti corretti.

**Modulo 2 (1h)**: misure protezione antincendi, procedure in caso di incendio,
evacuazione, contatti VVF, attrezzature e impianti di estinzione, sistemi di allarme,
segnaletica, illuminazione emergenza.

**Modulo 3 (2h)**: utilizzo pratico estintori — **escluso v1** (in presenza).

---

## 9. RLS — Rappresentante Lavoratori Sicurezza (32 ore) ✅ FULL COVERAGE (solo D.Lgs 81)

**URL**: <https://www.corsi8108.it/corso-formazione-r-l-s/>

**Normative**: D.Lgs. 81/08 artt. 37 c.10-11, 47, 50.

> Il corso non è suddiviso in moduli con nomi, ma in **8 contenuti minimi obbligatori**.
> Sono trattati come "moduli" equivalenti nel catalog refactor.

| # | Contenuto minimo | Ore (stima) |
|---|---|---|
| 1 | Principi giuridici comunitari e nazionali | 4 |
| 2 | Legislazione generale e speciale salute/sicurezza | 4 |
| 3 | Soggetti e obblighi (attori coinvolti) | 4 |
| 4 | Fattori di rischio: definizione e individuazione | 4 |
| 5 | Valutazione dei rischi | 4 |
| 6 | Misure di prevenzione tecniche, organizzative, procedurali | 4 |
| 7 | Rappresentanza dei lavoratori — aspetti normativi | 4 |
| 8 | Comunicazione — nozioni di tecnica | 4 |

---

## 10. Aggiornamento Formazione Lavoratori (6 ore) ⚠️ PARTIAL

**URL**: <https://www.corsi8108.it/aggiornamento-formazione-lavoratori-on-line-6-ore/>

**Normative**: D.Lgs. 81/08 art. 37 c.2; Accordo SR 21/12/2011 (Allegato II ATECO 2007);
Accordo SR 07/07/2016.

| # | Modulo | Ore |
|---|---|---|
| 1 | Modulo Generale | 4 |
| 2 | Modulo Specifico (ATECO-adatto) | 2 |

---

## ❌ Corsi non recuperati (URL 404)

I seguenti corsi sono presenti sul sito ma le URL elencate nella homepage hanno
ritornato 404. Provare in FASE 7 pattern URL alternativi (es. categoria-slug),
oppure chiedere al cliente copia-incolla manuale dei moduli:

- Formazione Preposti (8 ore)
- Formazione Dirigenti (16 ore)

---

## 📊 Allineamento PDF normativi disponibili nel DB

| Corso | DM 388/2003 in DB | D.Lgs 81/08 in DB | Coverage status |
|---|---|---|---|
| Primo Soccorso B/C | ✅ | ✅ | **FULL** — usabile per generazione v1 |
| Primo Soccorso A | ✅ | ✅ | **FULL** — usabile per generazione v1 |
| Lavoratori Generale | — | ✅ | PARTIAL — manca Accordo SR 21/12/2011 |
| Lavoratori Rischio Basso/Medio/Alto | — | ✅ | PARTIAL — mancano Accordi SR 2011+2016 |
| ASPP/RSPP Modulo A | — | ✅ | PARTIAL — manca Accordo SR 2011 |
| Antincendio Liv. 1 | — | ✅ | PARTIAL — manca DM 10/03/1998 |
| RLS | — | ✅ | FULL — solo D.Lgs 81 richiesto |
| Aggiornamento Lavoratori | — | ✅ | PARTIAL — mancano Accordi SR |

**Conclusione operativa per v1**:
- **Generazione pronta**: Primo Soccorso B/C, Primo Soccorso A, RLS (tutti coperti
  dai PDF già ingeriti, normativa cliente citata 1:1 con quanto disponibile).
- **Generazione possibile con qualità ridotta**: gli altri (D.Lgs 81 base, ma sezioni
  Accordo SR avranno bibliografia generica anziché chunk RAG specifici).
- **Per coverage 100% v2**: ingerire Accordo SR 21/12/2011, Accordo SR 07/07/2016,
  DM 10/03/1998 (o DM 02/09/2021 se cliente concorda aggiornamento). Vedi
  `vast-hopping-sketch.md` plan file per piano deploy completo.

---

**Generato automaticamente da**: WebFetch 9 pagine `corsi8108.it` — 2026-05-25.

---

## ⏳ DECISIONE APERTA — Formato export voce sincronizzata (2026-05-25)

Il cliente esporta i corsi su una **piattaforma corsi** (LMS). La voce
DiegoNeural (edge-tts, OPT-1) sincronizzata con le slide può essere consegnata
in 3 formati, da decidere quando il cliente conferma cosa accetta la sua
piattaforma:

| Formato | Voce sincronizzata | Effort | Quando preferirlo |
|---|---|---|---|
| **PPTX audio embedded** | autoplay per slide (`add_movie()` + play_mode AUTO XML) | ~1 giorno | piattaforma renderizza .pptx nativo. File ~150MB/corso 4h |
| **SCORM** (standard e-learning) | HTML5 + audio + timing nel browser | ~2-3 giorni | piattaforma è un LMS standard (molto probabile) |
| **MP4 video** | voce su timeline video | ~1 giorno | serve formato universale (YouTube/sito) |

**Ricerca industria 2026** (Articulate, iSpring, Cognispark): i leader e-learning
importano PPTX come scheletro, aggiungono voce sincronizzata, ed esportano in
**SCORM/xAPI/HTML5**, NON in .pptx nativo. SCORM è lo standard de-facto per LMS.

**Stato attuale**: la voce è disponibile (a) in-app via Course Studio AudioPlayer
(FASE 10), (b) ZIP di MP3 scaricabili. L'export voce-nel-file è rinviato a
decisione cliente sul formato piattaforma.

**Azione richiesta**: chiedere al cliente quale formato accetta la sua piattaforma
corsi (PPTX con media? SCORM? MP4?).
