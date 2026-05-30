# B3 TOC verificata — D.Lgs 81/08 mappa Articolo/Allegato → Titolo

> Forma leggibile della Tabella 1 implementata in `app/services/regulation_metadata.py`.
> Verifiche eseguite contro Normattiva (testo coordinato vigente 2026) + Bosetti&Gatti
> (reference professionale). Punti ambigui residui annotati esplicitamente.

## Fonti consultate

- **Normattiva** (`normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2008-04-09;81`)
  — testo coordinato vigente, oracolo finale per i giunti critici.
- **Bosetti&Gatti** (`bosettiegatti.eu/info/norme/statali/2008_0081.htm`) — reference
  professionale, copertura completa allegati ma out-of-date su Allegato I-bis
  (patente a punti D.L. 19/2024).

## Verifiche puntuali eseguite (4 giunti critici + 1 extra)

| Giunto | Atteso | Verificato Normattiva |
|--------|--------|------------------------|
| Boundary Art. 61 ↔ 62 (Titolo I / Titolo II) | Art. 61 ultimo Titolo I, Art. 62 primo Titolo II | ✓ CONFERMATO |
| Boundary Art. 87 ↔ 88 (Titolo III / Titolo IV) | Art. 87 ultimo Titolo III, Art. 88 primo Titolo IV | ✓ CONFERMATO |
| Range Titolo X-bis | Art. 286-bis…286-septies (6 articoli, NON Art. 287+) | ✓ CONFERMATO |
| Boundary Titolo XI/XII/XIII | XI Art. 287-297, XII Art. 298-303, XIII Art. 304-306 | ✓ CONFERMATO |
| Esistenza Allegato I-bis | introdotto da D.L. 19/2024 conv. L. 56/2024 patente a punti, citato Art. 27 c.6 | ✓ CONFERMATO (Bosetti out-of-date) |

## 13 Titoli del D.Lgs 81/08 (Tabella 1.A — Articolo → Titolo)

**NOTA STRUTTURALE**: il D.Lgs 81/08 ha **13 Titoli, NON 14**. Il "Titolo I-bis Prevenzione
e protezione" è una **nomenclatura informale**: in realtà gli Art. 15-54 sono **Capo III
di Titolo I**, non un Titolo separato. B3 al livello Titolo NON discrimina chunks
intra-Titolo I (Art. 35 riunione periodica vs Art. 40 prevenzione incendi vs Art. 18 DVR
sono tutti `top_section = "Titolo I"`). Limite riconosciuto: target H8 + B4 D9 vincolante.

| Titolo | Range Art. | Nome ufficiale | Note |
|--------|-----------|----------------|------|
| Titolo I | 1-61 | Principi Comuni | Capo I (1-4), Capo II (5-14), Capo III (15-54) Gestione prevenzione, Capo IV (55-61) Disposizioni penali |
| Titolo II | 62-68 | Luoghi di lavoro | |
| Titolo III | 69-87 | Uso attrezzature e DPI | |
| Titolo IV | 88-160 | Cantieri temporanei o mobili | Più grande Titolo (73 articoli) |
| Titolo V | 161-166 | Segnaletica di salute e sicurezza | |
| Titolo VI | 167-171 | Movimentazione manuale carichi | |
| Titolo VII | 172-179 | Videoterminali | |
| Titolo VIII | 180-220 | Agenti fisici | Rumore, vibrazioni, CEM, ROA |
| Titolo IX | 221-265 | Sostanze pericolose | Chimici, cancerogeni, amianto |
| Titolo X | 266-286 | Agenti biologici | |
| **Titolo X-bis** | **Art. 286-bis…286-septies** | Protezione ferite da taglio settore ospedaliero | 6 articoli SUFFISSO, gestione speciale parser |
| Titolo XI | 287-297 | Atmosfere esplosive ATEX | |
| Titolo XII | 298-303 | Disposizioni penali | |
| Titolo XIII | 304-306 | Norme transitorie e finali | |

## 51 Allegati del D.Lgs 81/08 (Tabella 1.B — Allegato → Titolo)

Tutti con collocazione TOC esplicita. NESSUN "TRASVERSALE" (ritirato dallo schema su
sign-off analista — ogni Allegato ha un Titolo unico).

### Titolo I — sanzioni, organizzazione, sorveglianza sanitaria (6 Allegati)
| Allegato | Nome breve | Titolo |
|----------|-----------|--------|
| Allegato I | Gravi violazioni sospensione attività (Art. 14 c.1) | Titolo I |
| Allegato I-bis | Lavori particolari patente a punti (Art. 27 c.6) — D.L. 19/2024 | Titolo I |
| Allegato II | Casi datore svolge direttamente RSPP (Art. 34) | Titolo I |
| Allegato III | Cartella sanitaria e di rischio | Titolo I |
| Allegato 3A | Suddivisione Allegato III parte A | Titolo I |
| Allegato 3B | Suddivisione Allegato III parte B | Titolo I |

### Titolo II — requisiti luoghi di lavoro (1 Allegato)
| Allegato | Nome breve | Titolo |
|----------|-----------|--------|
| Allegato IV | Requisiti dei luoghi di lavoro | Titolo II |

### Titolo III — uso attrezzature e DPI (5 Allegati)
| Allegato | Nome breve | Titolo |
|----------|-----------|--------|
| Allegato V | Requisiti attrezzature di lavoro | Titolo III |
| Allegato VI | Disposizioni uso attrezzature | Titolo III |
| Allegato VII | Verifiche periodiche attrezzature | Titolo III |
| Allegato VIII | DPI - Protezioni particolari | Titolo III |
| Allegato IX | Valori tensioni nominali macchine | Titolo III |

### Titolo IV — cantieri (14 Allegati)
| Allegato | Nome breve | Titolo |
|----------|-----------|--------|
| Allegato X | Elenco lavori edili/ingegneria civile | Titolo IV |
| Allegato XI | Elenco lavori con rischi particolari | Titolo IV |
| Allegato XII | Contenuto notifica preliminare | Titolo IV |
| Allegato XIII | Prescrizioni logistica cantiere | Titolo IV |
| Allegato XIV | Contenuti corso coordinatori | Titolo IV |
| Allegato XV | Contenuti minimi PSC | Titolo IV |
| Allegato XVI | Fascicolo caratteristiche opera | Titolo IV |
| Allegato XVII | Idoneità tecnico professionale | Titolo IV |
| Allegato XVIII | Viabilità cantieri, ponteggi, trasporti | Titolo IV |
| Allegato XIX | Verifiche sicurezza ponteggi metallici | Titolo IV |
| Allegato XX | Costruzione scale portatili | Titolo IV |
| Allegato XXI | Accordo corsi formazione lavori in quota | Titolo IV |
| Allegato XXII | Contenuti minimi Pi.M.U.S. | Titolo IV |
| Allegato XXIII | Deroga ponti su ruote a torre | Titolo IV |

### Titolo V — segnaletica (9 Allegati)
| Allegato | Nome breve | Titolo |
|----------|-----------|--------|
| Allegato XXIV | Prescrizioni generali segnaletica | Titolo V |
| Allegato XXV | Prescrizioni cartelli segnaletici | Titolo V |
| Allegato XXVI | Prescrizioni segnaletica contenitori | Titolo V |
| Allegato XXVII | Prescrizioni segnaletica attrezzature antincendio | Titolo V |
| Allegato XXVIII | Prescrizioni ostacoli e punti pericolo | Titolo V |
| Allegato XXIX | Prescrizioni segnali luminosi | Titolo V |
| Allegato XXX | Prescrizioni segnali acustici | Titolo V |
| Allegato XXXI | Prescrizioni comunicazione verbale | Titolo V |
| Allegato XXXII | Prescrizioni segnali gestuali | Titolo V |

### Titolo VI — movimentazione manuale (1 Allegato)
| Allegato | Nome breve | Titolo |
|----------|-----------|--------|
| Allegato XXXIII | Movimentazione manuale carichi | Titolo VI |

### Titolo VII — videoterminali (1 Allegato)
| Allegato | Nome breve | Titolo |
|----------|-----------|--------|
| Allegato XXXIV | Requisiti minimi videoterminali | Titolo VII |

### Titolo VIII — agenti fisici (5 Allegati)
| Allegato | Nome breve | Titolo |
|----------|-----------|--------|
| Allegato XXXV | Vibrazioni | Titolo VIII |
| Allegato XXXVI | Campi elettromagnetici (CEM) | Titolo VIII |
| Allegato XXXVII | Radiazioni ottiche artificiali (ROA) | Titolo VIII |
| Allegato XXXVIII | Valori limite esposizione professionale agenti fisici | Titolo VIII |
| Allegato XXXIX | Valori limite biologici e sorveglianza | Titolo VIII |

### Titolo IX — sostanze pericolose (2 Allegati)
| Allegato | Nome breve | Titolo |
|----------|-----------|--------|
| Allegato XL | Divieti agenti chimici | Titolo IX |
| Allegato XLI | Atmosfera - Norme UNI | Titolo IX |

### Titolo X — agenti biologici (7 Allegati)
| Allegato | Nome breve | Titolo |
|----------|-----------|--------|
| Allegato XLII | Specifiche misure contenimento biologico | Titolo X |
| Allegato XLIII | Valori limite esposizione biologica | Titolo X |
| Allegato XLIII-bis | Integrazione valori limite biologici | Titolo X |
| Allegato XLIII-ter | Ulteriore integrazione | Titolo X |
| Allegato XLIV | Elenco attività con agenti biologici | Titolo X |
| Allegato XLV | Segnale rischio biologico | Titolo X |
| Allegato XLVI | Elenco agenti biologici classificati | Titolo X |
| Allegato XLVII | Specifiche misure contenimento biologico II | Titolo X |
| Allegato XLVIII | Specifiche processi industriali biologici | Titolo X |

### Titolo XI — atmosfere esplosive ATEX (3 Allegati)
| Allegato | Nome breve | Titolo |
|----------|-----------|--------|
| Allegato XLIX | Ripartizione aree atmosfere esplosive | Titolo XI |
| Allegato L | Specifiche atmosfere esplosive | Titolo XI |
| Allegato LI | Segnale avvertimento atmosfere esplosive | Titolo XI |

**Totale Allegati**: 51 (compresi I-bis, 3A, 3B, XLIII-bis, XLIII-ter).

## Single-section regulations (no Tabella, top_section = slug stesso)

```python
SINGLE_SECTION_REGULATIONS = {
    "reg_ce_852_2004",         # HACCP, regolamento UE singolo
    "reg_ce_1272_2008",        # CLP, regolamento UE singolo
    "dm_02_09_2021",           # DM antincendio gestione e livelli formativi
    "dm_03_09_2021",           # DM antincendio minicodice
    "dm_01_09_2021",           # DM antincendio controlli impianti
    "dlgs_193_2007",           # D.Lgs italiano attuazione Reg CE 852/2004
    "accordo_stato_regioni_2025",
    "accordo_stato_regioni_2011",
    "accordo_stato_regioni_2016",
    "dm_388_2003",             # DM Primo Soccorso
}
```

B3 su queste regulations è **trivial single-section** (pool tutto same-Titolo per regulation
→ decay mai applicato). Telemetria log `b3_trivial_single_section: regulation_id=X` per
distinguere da no-op patologico.

## Punti ambigui residui (post-verifica)

### 1. Collegamento Allegati XLIX-LI a Titolo XI ATEX
- **Bosetti dice Titolo XI** (coerente con tematica ATEX e con la posizione finale degli Allegati,
  che tipicamente segue la sequenza dei Titoli).
- **Normattiva incerto** sul collegamento esplicito (l'oracolo fetch ha risposto "non riporta
  rimando esplicito").
- **Decisione provvisoria**: compilati come Titolo XI per coerenza tematica + Bosetti.
- **Validazione post-backfill staging**: campionerò chunks degli Allegati XLIX-LI dal DB
  per verificare che il body sia effettivamente su ATEX. Se discordante, riclassifico.

### 2. Allegato 3A/3B
- TOC originale ha "Allegato III" come Allegato unico.
- Versione vigente Normattiva ha **Allegato 3A** e **Allegato 3B** come suddivisione del III.
- **Decisione**: trattati come distinti, entrambi sotto Titolo I. Il parser di
  `_normalize_allegato_key` gestisce sia "Allegato 3A" sia "Allegato III A" come stessa chiave.
- **Validazione post-backfill**: campionerò chunks DB con article "Allegato III/3A/3B" e
  verificherò che la normalizzazione catturi tutte le varianti di parsing.

### 3. Allegato I-bis nel DB vs Bosetti out-of-date
- Bosetti ha smentito esistenza Allegato I-bis. Normattiva l'ha confermato (D.L. 19/2024
  patente a punti, citato Art. 27 c.6).
- **Decisione**: compilato come Titolo I (sanzionatorio, stesso Titolo del citante Art. 27).
- **Validazione post-backfill**: i chunks DB con article "Allegato I-bis" devono risultare
  classificati Titolo I (matching col Bosetti aggiornato implicito tramite Normattiva).

## Cosa chiedo a te (sign-off prima di migration 008 + backfill)

1. **Conferma TOC 13 Titoli** + accetti limite intra-Titolo I (chunks Art. 35/47/18 NON
   decadenti da B3, target H8 + B4).
2. **Conferma 51 Allegati** con i 3 ambigui residui sopra (XLIX-LI ATEX, 3A/3B, I-bis Titolo I).
3. **Conferma sequenza disciplinata**:
   - Migration 008 add column `top_section`
   - Backfill su staging con script idempotente `UPDATE ... WHERE top_section IS DISTINCT FROM oracolo`
   - Run B3 strumentato su 3 pool (ANT M0 + ANT M3 + GEN M1)
   - Sample-read log: B3 decade quello che ti aspetti?
   - Se OK, replay backfill su prod (stesso script).
4. **Conferma config esposte** B3_DECAY_FACTOR=0.4 + B3_THRESHOLD_RATIO=0.30 (settings env-override).
5. **Conferma log strutturato** `{chunk_id, top_section, dominante, cosine_orig, weight_post_decay, soglia, decisione, regulation_id, b3_noop_reason}` per ogni applicazione B3.

Se sign-off pieno, procedo nell'ordine. Senza setback minimi.
