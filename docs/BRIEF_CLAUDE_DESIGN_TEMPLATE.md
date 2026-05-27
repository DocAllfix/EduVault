# Brief per Claude Design — Potenziamento visivo template CFP Montessori

**Cliente:** C.F.P. Montessori — Ente formativo italiano (corsi sicurezza lavoro)
**Obiettivo:** Rendere il template esistente più professionale visivamente, mantenendo intatta la struttura tecnica.

---

## File allegati al brief

| File | Ruolo |
|---|---|
| `assets/templates/nexus_master.pptx` | **TEMPLATE BASE** da migliorare visivamente. Già ha la struttura tecnica giusta (8 layout corretti, shape names canonici, logo CFP). È solo BRUTTO esteticamente: layout scarno, font default, niente gradiente, niente accent visivi, troppo bianco vuoto. |
| `assets/templates/slidesgo_health_safety_original.pptx` | **ISPIRAZIONE VISIVA** — template Slidesgo "Health and Safety Workshop". DA NON USARE come base, solo come riferimento di stile (gradienti, micro-decorazioni eleganti, banded sections, hierarchy tipografica). |
| `assets/brand/cfp_montessori_logo.jpeg` | **Logo ufficiale CFP Montessori** (verde+rosa, "Formazione Globale"). Già presente in `nexus_master.pptx`, mantienilo identico in posizione/dimensione. |

---

## Cosa fare

Prendi `nexus_master.pptx` (il file base) e **migliora il suo aspetto visivo** ispirandoti agli elementi eleganti del template Slidesgo (gradient morbidi, bande colorate, micro-decorazioni geometriche, hierarchy tipografica forte), MA usando esclusivamente la palette CFP Montessori.

**Palette CFP Montessori (vincolata):**

| Ruolo | Hex | Uso |
|---|---|---|
| Primario rosa | `#C82E6E` | Bande full-width, accent verticali, badge sezione, bullet markers |
| Secondario verde | `#769E2E` | Banner RECAP, marker risposta corretta QUIZ, accent positivi |
| Dark navy | `#1F1F2C` | Tutti i titoli |
| Body text | `#1A1A1A` | Body text |
| Muted | `#6B7280` | Caption, footer normative_ref, page num |
| Background base | `#FFFFFF` | Slide background |
| Background soft | `#F8F9FA` | Card background interno, box DPI/diagrammi |
| Accent azzurro polvere | `#E1F0FF` | Shape decorativi morbidi (cerchi/blob discreti) |

**Font hierarchy:**
- Titoli: **Montserrat ExtraBold** (dimensioni proporzionate alla shape esistente)
- Body: **DM Sans Regular**
- Caption/footer: **DM Sans Regular** 11pt #6B7280

Embedda i font nel pptx.

---

## Cosa MIGLIORARE per ogni layout

Il template `nexus_master.pptx` ha già 8 layout con shape correttamente posizionate. **NON spostare** le shape, **NON rinominarle**, **NON cambiare la struttura**. Migliora SOLO l'estetica.

### Layout 0 — TITLE (cover corso)
**Stato attuale:** Linea rosa sottile in alto + titolo nero + sottotitolo + logo grande basso. Scarno.
**Migliorie:**
- Sostituisci la linea rosa sottile con una **banda full-width gradient** rosa CFP (#C82E6E) → verde brand (#769E2E) lateralmente
- Aggiungi un **blob azzurro morbido** (#E1F0FF) decorativo in basso-sx, dimensione 4×4 inch, opacità 40%
- Titolo molto grande Montserrat ExtraBold (60-72pt)
- Aggiungi una **piccola accent dot rosa** (●) accanto al sottotitolo

### Layout 1 — CONTENT_TEXT (slide testo bullet)
**Stato attuale:** Titolo top-left + accent line sotto + body bullets + footer ref + page num + logo piccolo. Layout standard ma piatto.
**Migliorie:**
- Sostituisci l'accent line nera sotto il titolo con una **mini-bar rosa** larga 1.5 inch, alta 4px (sotto il titolo a sinistra)
- Aggiungi un **piccolo blob azzurro polvere** decorativo top-dx (1.5×1.5 inch, opacità 30%) — solo decorazione, non invasivo
- Marker bullet **rosa CFP** (cerchio pieno ● invece di trattino)
- Aggiungi una **sottile linea verticale rosa** (2px wide) sul margine sx come accent
- Footer ref in un **piccolo pill rosa chiaro** rounded (background `#FCE4EC`, text rosa CFP)

### Layout 2 — CONTENT_IMAGE (testo + foto)
**Stato attuale:** Split 50/50 testo sinistra + box immagine destra + footer + logo.
**Migliorie:**
- Box immagine con **cornice rounded** (border radius 12px) + sottile bordo grigio
- Aggiungi un **piccolo badge "Foto operativa" o accent** sopra il box immagine
- Stesso accent verticale sx come Layout 1

### Layout 3 — DIAGRAM (immagine SVG renderizzata da LLM)
**Stato attuale:** Title + box diagramma + caption + footer.
**Migliorie:**
- Box diagramma con **background `#F8F9FA`** + cornice rounded 12px
- Caption sotto il diagramma in italic Calibri muted

### Layout 4 — QUIZ (4 opzioni A/B/C/D)
**Stato attuale:** Titolo domanda + 4 opzioni + banda rosa bottom con "Risposta corretta: B".
**Migliorie:**
- Domanda in **box rounded** con background `#F8F9FA`
- Le 4 opzioni come **card singole rounded** con badge lettera (A/B/C/D) in **cerchio rosa CFP** a sinistra
- Mantieni la banda rosa CFP full-width in basso

### Layout 5 — CASE_STUDY (3 sezioni)
**Stato attuale:** Banda rosa top "CASO STUDIO" + titolo + 3 sezioni SITUAZIONE/AZIONE/RISULTATO con bar laterali.
**Migliorie:**
- Banda top con **gradient rosa CFP → rosa più scuro** invece di colore piatto
- Bar laterali sinistre delle 3 sezioni con **colori distinti**:
  - SITUAZIONE → rosa CFP `#C82E6E`
  - AZIONE → verde brand `#769E2E`
  - RISULTATO → dark navy `#1F1F2C`
- Background sezioni `#F8F9FA` con border-radius 8px

### Layout 6 — RECAP (riepilogo modulo)
**Stato attuale:** Banda VERDE full-width + titolo + bullet riepilogo.
**Migliorie:**
- Banda verde **gradient** dal verde brand → verde più scuro
- Aggiungi piccola **icona check ✓** (sostituibile con un cerchio) accanto ad ogni bullet riepilogo
- Footer module_ref in pill verde chiaro

### Layout 7 — CLOSING (chiusura corso)
**Stato attuale:** "Grazie" centrato + logo grande sotto + tagline.
**Migliorie:**
- Sfondo con **gradient diagonale** molto morbido (bianco → `#FCE4EC` rosa polvere sull'angolo basso-dx, opacità 30%)
- "Grazie" Montserrat ExtraBold 80-96pt centro
- Aggiungi sotto al logo una **piccola decorazione**: 3 cerchi orizzontali (rosa, verde, dark navy) come accent firma

---

## Elementi di STILE da prendere da Slidesgo (senza rubarli direttamente)

Guarda `slidesgo_health_safety_original.pptx` e RUBA L'IDEA (non copiare le illustrazioni) di:

1. ✅ **Bande verticali laterali sottili** come accent (Slidesgo le fa arancioni striped, noi le facciamo **rosa CFP solide**, larghe 4-8px)
2. ✅ **Blob azzurri polverosi** discreti come decorazione sfondo (NO grandi e invasivi, ma piccoli e opaci 30-40%)
3. ✅ **Hierarchy tipografica forte** (titoli giganti, body piccolo, caption muted)
4. ✅ **Card rounded** con background morbido `#F8F9FA` per raggruppare contenuti
5. ✅ **Mini-bar accent colorate** sotto i titoli (4px alta, 1-2 inch larga, NO accent line piena slide-width che sembra AI-generated)
6. ✅ **Badge colorati con testo bianco** UPPERCASE per le sezioni (CASO STUDIO, RIEPILOGO, QUIZ)
7. ❌ **NO illustrazioni** vettoriali di persone/lampade/mensole (sono off-topic Slidesgo)
8. ❌ **NO strisce diagonali pattern** arancione/bianco (rumore visivo)

---

## Vincoli tecnici (NON DEROGABILI)

1. **NON cambiare i nomi delle shape esistenti.** Il backend Python le cerca per name (`Text 0`, `Text 2`, ecc. — vedi `app/builders/slide_builder_v2.py` SHAPE_MAP).
2. **NON spostare significativamente le shape esistenti** (max ±0.1 inch per assestamenti). La posizione attuale è il contratto col mio renderer.
3. **NON aggiungere/rimuovere layout.** Sono esattamente 8 layout (0..7) mappati al mio SlideType enum. NON aggiungere CUSTOM_X.
4. **NON aggiungere slide nel template.** Il file deve avere 0 slide finali (solo i 8 layout master).
5. **Slide size 20×11.25 inch widescreen** (NON cambiare).
6. **Logo CFP Montessori** identico al file `cfp_montessori_logo.jpeg`. NON ridisegnarlo, NON sostituirlo.
7. **NO testo placeholder demo** dentro le shape (es. "Lorem ipsum", "Your title here"). Lascia le shape vuote OPPURE con testi italiani reali sicurezza (vedi esempi sotto).
8. **Font embeddati** nel pptx (Montserrat ExtraBold + DM Sans).
9. **NO accent line piena slide-width** sotto i titoli (anti-AI look). Usa mini-bar 1-2 inch.

---

## Esempi testi italiani sicurezza (per popolare le shape se serve mockup)

- **Title:** "Primo Soccorso — Gruppi B e C"
- **Subtitle:** "Formazione 8 ore — D.Lgs 81/08 art. 45 + DM 388/2003"
- **Body bullet:** "Designare un numero adeguato di lavoratori incaricati\nFornire la formazione obbligatoria DM 388/2003\nMettere a disposizione la cassetta di pronto soccorso\nGarantire procedure di chiamata 112 NUE"
- **Normative ref footer:** "Art. 45 D.Lgs 81/08"
- **Caso studio:** "Infortunio in magazzino: caduta da scala portatile"
- **Quiz:** "Chi nomina il Responsabile del Servizio di Prevenzione e Protezione?"

---

## Deliverable atteso

1. **File `nexus_master_v2.pptx`** — stesso file `nexus_master.pptx` di partenza ma visivamente migliorato secondo le specifiche sopra
2. **0 slide nel file** (solo 8 layout master)
3. **Font Montserrat ExtraBold + DM Sans embeddati**
4. **8 mockup PNG** (uno per layout) renderizzati con i testi italiani esempio per validazione visiva

---

## Test di accettazione

- [ ] Aperto in PowerPoint mostra solo 8 layout (TITLE/CONTENT_TEXT/CONTENT_IMAGE/DIAGRAM/QUIZ/CASE_STUDY/RECAP/CLOSING)
- [ ] Logo CFP visibile in ogni layout (1.5×0.4 inch basso-destra su content, 2.5×0.7 inch centro-basso su TITLE/CLOSING)
- [ ] Nessuna accent line piena sotto titoli (solo mini-bar 1-2 inch)
- [ ] Font Montserrat ExtraBold + DM Sans embedded
- [ ] Shape names IDENTICI a quelli del template di partenza (verifica con `python scripts/inspect_template.py`)
- [ ] Palette CFP applicata uniformemente (NO arancione, NO giallo, NO altri colori fuori palette)
- [ ] Slide size 20×11.25 inch
- [ ] 0 slide nel file
- [ ] Almeno 3 elementi visivi presi da Slidesgo style (gradient OR blob azzurro OR mini-bar accent OR card rounded)
