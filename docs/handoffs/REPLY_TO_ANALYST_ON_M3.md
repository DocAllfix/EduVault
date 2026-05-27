# Risposta all'analista — il numero che ha chiesto + M3 + 4 domande nuove

**Data:** 2026-05-27 pomeriggio inoltrato
**Da copiaincollare in chat all'analista** (sezione racchiusa in ``` sotto).

---

```
Caro analista,

Ho il numero che mi hai chiesto in cima, e cambia meno di quanto sperassi.
Poi rispondo alla cosa di M3 (è l'urgenza adesso) e ti chiedo quattro cose
precise.

══════════════════════════════════════════════════════════════════
IL NUMERO — tempo-fino-al-PPTX-scaricabile
══════════════════════════════════════════════════════════════════

Verificato sui log E2E #19 (timestamp granulari):
  pipeline start           09:12:51
  pptx_built_v2            09:26:14
  pptx_validated           09:26:15
  pdf_generated            09:26:23
  pipeline_completed       09:26:23  ← elapsed_seconds=812.7
  audio_in_background      False     ← l'audio NON è partito

Il 13m32s NON include audio: è davvero il tempo pieno fino a
PPTX+PDF scaricabile. MOSSA 3 ha decoupplato il codice, ma c'è un
bug pre-esistente (colonna `outputs` non persistita nella tabella
courses, già noto da #18) che fa sì che `audio_requested=False`
sempre, quindi non c'è audio da spostare in background.

Confronto giusto apples-to-apples con E2E #18 (anche lì niente
audio attivo): 15m41s → 13m32s = -2m09s reali, MOSSA 3 non sta
nascondendo regressioni. Ma il problema "spinner 13 min" è REALE,
non un artefatto di misura. Il cliente in self-serve la sente tutta.

Quindi il tuo "se il PPTX è già pronto a ~8 min, H6 e progress page
crollano di urgenza" — non si applica. PPTX scaricabile = 13m32s
oggi. H6 e/o progress page restano dove erano nella priorità.

══════════════════════════════════════════════════════════════════
M3 — la coerenza tematica, e cosa ho capito leggendo il codice
══════════════════════════════════════════════════════════════════

Voglio risolvere M3, non gestirlo. Hai ragione che "demo
self-serve con M3 grab-bag" è il rischio peggiore. Aprire un modulo
"Procedure di emergenza" e leggere sanzioni penali per 30 slide
è il segnale "auto-generato" più immediato.

Leggendo `app/agents/research_agent.py` ho ricostruito perché
succede oggi:

1. Si fa UNA query `search_chunks(course_query)` globale → top ~40
   chunk dal corpus su voyage embed del query corso.
2. `distribute_chunks_to_modules_cosine` (riga 514): per ogni
   modulo embed_query(MODULE_QUERY_EXPANSIONS[title]), poi assegna
   ogni chunk al modulo con cosine max, rebalance per quote.
3. PROBLEMA: il pool dei 40 chunk è SBILANCIATO sui temi reali del
   corpus (es. ~20 vere emergenze, ~8 RLS, ~12 sanzioni, ~14
   finanziamenti). Quando rebalance forza M3 a quota 74 slide, i
   54 chunk sopra le 20 vere emergenze finiscono lì comunque,
   semplicemente perché sono il "meno-peggio" per cosine.
4. Il fix-vero (quello che chiamiamo #31.1) è: NON UN retrieval
   globale + cluster, MA N RETRIEVAL indipendenti uno per modulo,
   con MODULE_QUERY_EXPANSIONS già definite (le hai approvate tu
   in #30.9d). Ogni modulo riceve ~15-20 chunk TEMATICAMENTE PURI,
   il rebalance globale sparisce, M3 contiene SOLO chunk che il
   cosine ha trovato per "Procedure emergenza", e se sono solo 20
   il modulo è da 20 slide, non 74 forzate.

L'effetto collaterale è che il corso non sarà più 326 slide ma
forse 220-280 (perché ogni modulo ha solo i chunk che gli
appartengono davvero). Il cliente CFP però paga la durata 4h, non
il count slide: 220 slide × 45s/slide = ~165 min = ~2h45min, e
non rispetta più la regola commerciale "1 slide ~ 30-45s = durata
totale 4h". Dovrei o accettare corsi più corti per durata reale
o riformulare il pacing.

QUI ho un dubbio sostanziale, e te lo passo:

DOMANDA 1 (urgentissima, blocca tutto il resto):
Il fix #31.1 vero (retrieval per-modulo) potenzialmente accorcia
i corsi sotto la durata commerciale. Due strade:
 (a) Accettiamo durata reale variabile (corso "4h" può uscire
     2h45 se il corpus ha solo 220 chunk per 4 temi). Onesto ma
     rinegoziamo l'aspettativa cliente "4h = 4h" → "4h = il
     materiale che il corpus copre". Vuoi tu rinegoziare con CFP?
 (b) Pacing dinamico: se un modulo ha solo 20 chunk veri, ne fa
     20 contenuto + bookends ma alziamo il numero di slide per
     contenuto (es. ogni chunk → 2 slide invece di 1, espandendo
     con quiz, recap parziali, case study sintetici). Il pacing
     dinamico esisteva già pre-#30.9e ed era stato disattivato.
     Riattivare ha rischio di tornare a "modulo lungo di
     riempimento" che era esattamente il problema che #30.9e ha
     risolto.
La strada (c) "lasciamo i moduli forzati a 74 slide e quindi
grab-bag" è dove siamo ora, e sappiamo che non funziona per la
demo self-serve.

DOMANDA 2 (operativa):
Per la demo CFP venerdì, accetti che NON aggiusto M3 ma inquadro
la demo come dicevi tu — "qualità slide + branding + diagrammi +
quiz, la riorganizzazione tematica è una bozza che l'RSPP
finalizza"? Mi serve un go/no-go esplicito perché incidenta sul
testo che mando al cliente con l'URL demo.

DOMANDA 3 (tier OpenAI):
Lo verifico io stasera con una request a OpenAI direttamente,
leggendo `x-ratelimit-limit-tokens`. Ti mando il numero così
decidi se H6 è 200K→400K o se siamo già tier alto.

DOMANDA 4 (M4 Segnaletica):
Tu avevi detto "se vuoi prima della demo leggo M4 come ho fatto
con M3, sospetto stesso grab-bag". Sì, leggilo per favore. Se
M4 è grab-bag anche lui, il rischio "demo self-serve mostra
moduli grezzi" raddoppia e il fix #31.1 diventa precondizione
per la demo, non opzione.

══════════════════════════════════════════════════════════════════
COSA FACCIO MENTRE ASPETTO LE TUE 4 RISPOSTE
══════════════════════════════════════════════════════════════════

(1) Verifico tier OpenAI con la chiamata API (10 min, te lo mando)
(2) Setup Railway+Vercel demo (1 giorno, indipendente da M3 —
    deploy può anche andare con M3 grab-bag se gestisco UX),
    parallelizzo
(3) Smoke Chrome DevTools su Course Studio (verificare che funziona
    edit slide + regenerate)

Quello che NON tocco fino al tuo OK:
- #31.1 retrieval per-modulo (rischio rompere quello che funziona M1
  DPI e M0 Rischi specifici — voglio il tuo OK su DOMANDA 1)
- Progress page engaging (decisione dopo numero tier OpenAI: se H6
  ti dà -5 min facili, sposto progress page in priorità bassa)
- Fix bug `outputs` per attivare audio (out of scope demo CFP,
  posso fare dopo)

Aspetto le tue 4. Grazie.
```

---

## Note operative per me (fuori dal messaggio analista)

### Stato verificato adesso
- E2E #19 audio = **MAI partito** (audio_in_background=False). Il 13m32s è puro PPTX+PDF.
- MOSSA 3 codice è giusto ma inerte finché non si fixa bug `outputs` pre-esistente.
- Il "delta -2 min" tra #18 e #19 è **tutto** da MOSSA 1 (backfill waves -2:30) + leggera variance. M2 invisibile sul tempo (era 0-tempo per design). M3 invisibile sul tempo (audio non parte). M4 invisibile sul tempo (è solo logging).

### Numeri pronti per qualsiasi futura domanda analista
- pipeline_completed = 13m32s = 812.7s (E2E #19)
- audio_in_background = False = audio non spawnato
- reask_avg_per_batch = 0.0 su tutti 4 moduli
- DIAGRAM 18/18 catalog
- distribution 45/28/12/5.5/3/3 + bookends

### Ordine di lavoro mentre aspetto analista
1. **Verifica tier OpenAI** (10 min) — chiamata API + lettura header rate-limit
2. **Setup Railway/Vercel** se ho un buco di tempo (indipendente da M3)
3. **NON tocco #31.1** finché analista risponde DOMANDA 1
4. **NON tocco audio bg fix** (out of scope demo)
