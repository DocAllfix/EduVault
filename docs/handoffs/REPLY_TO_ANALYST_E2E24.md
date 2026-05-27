# Messaggio analista — E2E #24 risultato misto + 2 problemi residui

**Allegati Desktop:**
- `CFP_4h_E2E24_31.5_da_analista.pptx` (~45 MB, 336 slide)
- `CFP_4h_E2E24_31.5_dispensa.pdf`

---

```
Caro analista,

#31.5 implementato (A bullet 2→3 + B coercion + sub-batch recovery + C
Segnaletica ampliata) + E2E #24 finito in 11m 44s. Risultato MISTO,
te lo do dritto.

══════════════════════════════════════════════════════════════════
1. SUCCESSI VERI
══════════════════════════════════════════════════════════════════

  Metrica                  E2E #23     E2E #24    Δ
  Tempo pipeline           15m 16s     11m 44s    -3m 32s (-23%)
  Slide totali             301         336        +35
  M0 slide                 76          82         ✓ pieno
  M1 slide                 57 (-27!)   82         ✓ +25 recuperate
  M2 slide                 84          82         ≈ pieno
  M3 slide                 84          82         ≈ pieno
  batches_failed           2 (M1)      0          ✓ ZERO
  sub_batch_recovery       n/a         0          NON attivato (preventivo!)
  reask                    0           0          ✓

Spiegazione M1 recuperato senza sub-batch: il fix B coercion
source_chunk_ids ha probabilmente prevenuto i 2 batch fail di #23
(uno era proprio "Input should be an object [source_chunk_ids
stringa malformata]"). Quindi sub-batch recovery NON è scattato
perché non è servito. Preventivo > curativo. Tempo recuperato 4 min.

══════════════════════════════════════════════════════════════════
2. PROBLEMA RESIDUO #1 — DIAGRAM branded fallback peggio del previsto
══════════════════════════════════════════════════════════════════

La nuova telemetry (fix A) ha rivelato la verità che #23 nascondeva:

  diagram_fallbacks      = 14 (!!!)
  content_image_fallbacks = 0
  branded_fallbacks (tot) = 14

Su 19 DIAGRAM totali (vs 23 in #23): 14 branded fallback (74%!) e
solo 5 catalog veri. Tutti i 19 hanno diagram_filling valorizzato
nel DB (il render LLM produce filling, ma cairosvg non lo
trasforma in PNG perché il filling è invalido).

CAUSA (verbatim dai log, ripetuta 14 volte):
  diagram_filling_failed
    error="slot 'label_1' sfora max_chars=18 di più del 20%:
           33 caratteri (max tollerato 21).
           Riformula più sintetico."
    fallback=legacy_diagram_code

Esempi reali dei label troppo lunghi:
  - "valutaz. periodica DPI secondo la normativa" (33 char)
  - "obblighi DPI secondo D.Lgs. 81/08 Art. 225" (35 char)
  - "uso DPI secondo l'art. 76" (28 char)
  - "implementare DPI secondo la legge" (22 char)
  - "informazione DPI secondo Allegato VIII" (23 char)
  - "lavorare in sicurezza secondo art. 162" (23 char)

PATTERN OSTINATO: l'LLM aggiunge SUFFISSI NORMATIVI ("secondo la
normativa", "secondo D.Lgs. 81/08 Art. X", "secondo Allegato Y")
in coda al label, anche se max_chars=18. Lo schema rigetta, fallback
parte, e il render finale è branded.

Conoscevamo già la patologia (#30.9g pyramid era stesso pattern),
avevamo aggiunto tolerance 20% nel validator ma l'LLM scrive ben
oltre tolerance. Non sento già la mia prossima ipotesi.

DOMANDE PER TE:
(A) Tu hai esperienza diretta del prompt content_agent — secondo te
    la fix giusta è (1) regola ESPLICITA nel prompt DIAGRAM tipo
    "MAI suffissi 'secondo la normativa/legge/D.Lgs.' nei label —
    riferimento normativo solo in caption", oppure (2) post-process
    Pydantic che taglia in coercion (rimuove regex "secondo
    (la|il|gli|le)? \w+|D\.Lgs\..*|art\..*|Allegato.*") prima del
    validator?
(B) Se prompt+coercion non bastano, opzione C: alziamo tolerance
    da 20% a 50% per DIAGRAM, accettando label leggermente più
    lunghi ma con render OK (no fallback)?

Mia preferenza: (1) prompt esplicito + (2) coercion regex come
safety net. Ma vorrei la tua decisione perché tocca prompt che
hai validato in review precedenti.

══════════════════════════════════════════════════════════════════
3. PROBLEMA RESIDUO #2 — M3 Segnaletica DERIVA IDENTICA a #23
══════════════════════════════════════════════════════════════════

Fix C (MODULE_QUERY_EXPANSIONS ampliato a luminosi/acustici/gestuali/
esodo/formazione) NON ha risolto la deriva M3. Conteggio off-topic
in M3 #24:
  13 slide off-topic su 84 (= 15%) — IDENTICO a #23

Esempi titoli M3 off-topic:
  31: "Formazione sulla segnaletica di sicurezza"
  33: "Formazione pratica sui gesti di segnaletica"
  36: "Quiz: Quali sono le sanzioni per mancata formazione?"
  37: "Importanza della formazione continua sulla segnaletica"
  46: "Sanzioni per lavoratori autonomi in materia di segnaletica"
  71: "Giudizio del medico competente sulla mansione"
  72: "Misure del datore di lavoro in caso di inidoneità"
  73: "Documentazione del giudizio medico competente"

LETTURA ONESTA:
- Aggiungere "formazione specifica sulla segnaletica" nella query
  HA AGGIUNTO chunk "formazione" che ora finiscono in M3. Self-own.
- Le slide su sanzioni / medico competente / inidoneità sono ancora
  lì perché il corpus 81/08 ha cosine alto fra "segnaletica" e
  questi temi (sono parti del Testo Unico vicine semanticamente
  per quanto trasversale).

OPZIONI:
(1) Restringo query rimuovendo "formazione" e "obblighi del datore":
    porto query Segnaletica a CORE puri (cartelli/pittogrammi/colori/
    luminosi/acustici/gestuali/esodo). Rischio: per_module_kept M3
    scende sotto 30, allora content_agent ripadda con derive forse
    peggiori.
(2) Drop-list post-retrieval: nel codice di research_agent, dopo
    retrieve_chunks_per_module, filtro chunks_by_module[3] per
    title regex "sanzion|medic|inidonei|RSPP" → li scarta dal
    pool M3. Chirurgico, salva la query ampliata.
(3) Accettare 15% deriva come "bozza-RSPP" e procedere. Sui 4
    moduli totali, è il 4% off-topic complessivo, accettabile?

Mia preferenza: (2) drop-list, ~10 LOC, chirurgico.

══════════════════════════════════════════════════════════════════
4. RICHIESTE PARALLELE
══════════════════════════════════════════════════════════════════

Apri CFP_4h_E2E24_31.5_da_analista.pptx (Desktop) e dimmi:

(R1) M1 finalmente pieno a 82 slide. Lettura titoli M1 — coerente
     o ha sub-derive simili?
(R2) Render visivo: scegli 3-4 DIAGRAM a caso e dimmi se il branded
     fallback è davvero visibile (icona rosa + banda verde con testo
     overflow) o se grafica è accettabile come "bozza".
(R3) IMAGES contestualità su 15-20 slide: invariato vs #23 (era OK).
(R4) M3 deriva: 13 slide off-topic su 84 — accettabile o sospendi?

══════════════════════════════════════════════════════════════════
5. COSA TI CHIEDO IN UNA RISPOSTA
══════════════════════════════════════════════════════════════════

(D1) DIAGRAM fallback: opzione (1) prompt + (2) coercion regex,
     opzione (3) tolerance 50%, oppure combo?
(D2) M3 deriva: opzione (1) restringi query, (2) drop-list post-
     retrieval, (3) accetta 15% e procedi?
(D3) Se tu mi dici "fai #31.6 mini fix entrambi", lo faccio
     subito (~45 min totali codice+test+E2E #25). Se invece
     dici "stop, procedi con 2 corsi demo accettando difetti",
     parto con Generale 4h + Primo Soccorso 8h ora.
(D4) H6: post-demo come stabilito review 4, piano implementativo
     già pronto in docs/H6_IMPLEMENTATION_PLAN.md.

Aspetto le tue 4 risposte secche.

Grazie.
```

---

## Per te — note operative fuori dal messaggio

### Stato file Desktop

| File | Cosa contiene |
|---|---|
| `CFP_4h_E2E24_31.5_da_analista.pptx` (45 MB) | Build post-FIX#31.5 — moduli pieni ma 14 DIAGRAM in branded fallback |
| `CFP_4h_E2E24_31.5_dispensa.pdf` | PDF |
| Già lì: `CFP_4h_E2E23_31.4_da_analista.pptx` | Per confronto (M1 era 57 lì) |

### I 2 problemi residui in numeri

| Problema | Severità | Fix proposto | LOC |
|---|---|---|---|
| 14/19 DIAGRAM branded fallback per label LLM troppo lunghi | ALTA | prompt esplicito + coercion regex | ~20 |
| 13/84 M3 deriva su sanzioni/medico/formazione | MEDIA | drop-list post-retrieval | ~10 |

### Tempistica se l'analista dice "fai #31.6"

- 5 min: scrivo regola prompt DIAGRAM "no suffissi normativi nei label"
- 10 min: coercion regex `_truncate_label_suffix` in `diagram_service.py`
- 10 min: drop-list M3 post-retrieval in `research_agent.py`
- 5 min: sync + restart + smoke
- ~12 min: E2E #25
- 15 min: estrazione + lettura M3 + render 4 DIAGRAM + invio

**Totale**: ~57 min dal "vai".

### Se invece dice "procedi con 2 corsi demo accettando difetti"

- 12 min: corso "Generale Lavoratori 4h"
- ~25 min: corso "Primo Soccorso 8h"
- 5 min: copia entrambi Desktop
- 30 min: commit `fix(31.5)` + push
- 3-4h: setup deploy Railway + Vercel

**Totale**: ~5h dal "vai".

### Cosa NON faccio senza ulteriore OK analista

- Toccare prompt DIAGRAM (lui ha validato in review precedenti, decisione sua)
- Toccare query expansion Segnaletica oltre quello che già è
- Iniziare H6 (post-demo, deciso)
- Audio bug fix (separato)
