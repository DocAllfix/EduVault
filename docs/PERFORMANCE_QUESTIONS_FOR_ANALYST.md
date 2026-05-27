# Messaggio analista — performance pipeline corso 4h

**Data:** 2026-05-27
**Contesto:** post FIX #30.9g (pyramid OK, max_chars per-slot, tolerance 20%).
Qualità diagrammi sotto controllo, serve capire come scendere sotto i 4-5 min/corso.

---

```
Caro analista,

Allego il PPTX `CFP_4h_v6_E2E18_da_analizzare.pptx` (42MB, 333 slide,
generato dall'E2E #18 stamattina). Cosa guardarci per dare il senso
qualitativo prima delle domande performance:

  - 8 MODULE_OPEN/CLOSE programmatici (4+4): controlla coerenza
    titolo/sezione modulo.
  - 21 DIAGRAM tutti col catalogo (13 flow_4step + 8 flow_3step). NON ci
    sono pyramid/org_tree/matrix usati in questo run, e su slide
    gerarchiche tipo "Gerarchia SSL/dirigenti/preposti/lavoratori"
    avrebbe avuto senso una pyramid o org_tree (vedi sotto domanda
    qualitativa).
  - 100 CONTENT_IMAGE Pexels reali (zero brandizzato), aspect hint
    funzionante.
  - normative_ref deterministico via lookup DB: 244 'art.', 101
    'allegato', ZERO 'pag.' (citazioni sempre verificabili).

DUE ANALISI QUALITATIVE che mi servono SOLO TU possa fare (io vedo i
dati strutturali dal DB, non valuto coerenza semantica):

(Q-A) COERENZA TEMATICA PER MODULO. I 4 moduli del catalogo CFP sono
"Rischi specifici", "DPI", "Procedure di emergenza", "Segnaletica".
Per ogni modulo, leggi 5-6 slide e dimmi se:
   - il modulo ha un FILO conduttore o salta di tema in tema
   - eventuali slide "ospite" che parlano d'altro (es. una slide su
     "formazione generale" finita nel modulo DPI)
   - il MODULE_OPEN promette qualcosa di diverso dal contenuto reale
   - il MODULE_CLOSE riepiloga davvero il modulo o è generico

(Q-B) ORDINE DELLE SLIDE DENTRO IL MODULO. Cluster cosine assegna i
chunk al modulo via similarity ma NON ordina le slide tematicamente
dentro il modulo (l'LLM genera in 8 batch da 10, e gli indici sono
sequenziali per batch). Esempio sospetto: nel module 0 "Rischi
specifici", la slide 7 (DIAGRAM "Tipi principali di rischi specifici")
arriva DOPO 6 slide di altro tema. Sarebbe più logico in apertura.
Vale la pena introdurre un passaggio di re-ordering tematico delle
slide DENTRO il modulo prima del build PPTX (es. via embedding
similarity sui titoli)? O lo vedi come over-engineering vs il guadagno
percepito?

Tre numeri reali per fissare lo scenario (corso 4h, ~330-360 slide, catalogo
fisso 4 moduli, Azure gpt-4.1-mini):

  Run                              Slides   Job (sec)   Job (min)
  CFP 4h FINALE v2 (#30.9e)         336        520       8m 40s
  CFP FINAL 4h (#30.9d-rev2)        360        240       4m 00s
  CFP 4h v6 (E2E #18 #30.9g)        333        941      15m 41s  ⚠

Trend regressivo netto: 4m → 8m → 15m sugli ultimi tre run. Le cause cumulate
nei FIX successivi (bookends programmatici, 4 moduli grandi al posto di 12
piccoli, prefetch Pexels più voluminoso, retrieval per-modulo, retry-loop
instructor sui sloter diagram fuori max_chars) hanno peggiorato i tempi a
parità di output. Non ho ancora isolato chi pesa cosa.

DATI DI QUALITÀ E2E #18 (dal DB del corso, NON dai warning di log):
  - 333 slide totali su 4 moduli da ~83 slide (uniformi, ottimo)
  - distribution: CONTENT_TEXT 42%, CONTENT_IMAGE 30%, QUIZ 13%, DIAGRAM 6%,
    CASE_STUDY 4%, RECAP 2%, MODULE_OPEN/CLOSE 4 cad
  - 21 DIAGRAM, 21/21 con diagram_filling valido (100% catalogo, ZERO branded
    fallback finali). Le 8 'diagram_filling_failed' nei log erano i tentativi
    iniziali rifiutati dal validator → retry instructor → tutti chiusi OK
    nel DB. Il giro di vite tolerance 50→20% ha funzionato senza degradare
    l'output finale.
  - 100/100 CONTENT_IMAGE con query Pexels valida
  - normative_ref: 244 con 'art.', 101 con 'allegato', ZERO con 'pag.'
    (lookup DB regge — no allucinazioni)

PROBLEMA QUALITATIVO RESIDUO #18: zero template pyramid/org_tree/matrix
usati. L'LLM ha scelto SOLO flow_3step (8) e flow_4step (13) per i 21
diagrammi, anche per slide tematicamente gerarchiche (es. "Gerarchia ruoli
SSL"). Vale la pena promuovere meglio gli altri 5 template nel prompt o
è normale che su sicurezza lavoratori prevalgano i flow sequenziali?

PROBLEMA DI PERFORMANCE RESIDUO #18: il backfill immagini post-prefetch
ha 8 wave da 20s = 160s buttati alla fine (filled=0 per ogni wave, tutte
le 8 cadono comunque in branded). È retry inutile, lo riduco da 8 a 2
wave o lo elimino del tutto?

Per la consegna venerdì il sistema funziona, ma 8-10 min/corso non scala se
il cliente passa a "10 corsi in batch notturno" o se l'utente in studio vuole
preview iterative. Devo capire quali sono le leve di velocizzazione realistiche
SENZA riaprire le bonifiche qualitative appena chiuse (#30.9c..g) e SENZA
intaccare REI-3 (Semaphore(1) python-pptx).

Configurazione attuale:
  - LangGraph 2-nodi: research (Voyage embed query + pgvector + cluster cosine
    + rebalance) → content (instructor batch da 10 slide × Semaphore(20) moduli
    paralleli su Azure gpt-4.1-mini 200K TPM)
  - Post-pipeline serial: ProductionBuilder → PPTX (python-pptx) → PDF (LibreOffice)
    → audio edge-tts sequenziale per slide
  - REI-3: Semaphore(1) sul builder PPTX (python-pptx non thread-safe)

Le mie 6 ipotesi su dove tagliare tempo, con dubbi sostanziali per ognuna:

──────────────────────────────────────────────────────────────────────────────
H1 — RESEARCH ha consumato 5+ min sul #18, ma il job ne ha consumati 15 totali
──────────────────────────────────────────────────────────────────────────────
Avevo inizialmente sospettato che cluster cosine + retrieval pgvector +
rebalance per 4 moduli fosse il collo. Verifica sui log #18: il research
finisce a ~07:09 (job start 06:55), poi entra in content_agent fino a
~07:23 (15 min), poi prefetch immagini fino a ~07:24, poi backfill 8 wave
fino a 07:26 (160s), poi PPTX+PDF (~10s totali).
Stima rapida: ~10 min content_agent + 3 min research + 2.5 min image+backfill
+ 0.5 min build = 16 min totali. Il pezzo grosso è il content_agent. NON
strumento più finemente prima di tagliare lì.

──────────────────────────────────────────────────────────────────────────────
H2 — AUDIO TTS sequenziale è dove vanno via 5-6 min
──────────────────────────────────────────────────────────────────────────────
336 slide × ~1s/MP3 = ~5-6 min se edge-tts è serial. Parallelizzarlo con
asyncio.gather (semaforo a 20-30) dovrebbe dimezzare. Ma:
  - edge-tts ha un rate limit non documentato (è un servizio Microsoft Edge
    "free")?
  - Conviene farlo in pipeline o spostarlo DOPO la consegna del PPTX (= corso
    "pronto da scaricare" mentre l'audio si genera in background)?
Hai esperienza diretta con edge-tts paralleli?

──────────────────────────────────────────────────────────────────────────────
H3 — content_agent batch da 10 + concorrenza 20: troppo conservativo?
──────────────────────────────────────────────────────────────────────────────
Azure gpt-4.1-mini ha 200K TPM. Con 4 moduli da ~80 slide (8 batch da 10),
Semaphore(20) significa che 20 batch possono partire in parallelo MA in pratica
sono 8 batch × 4 moduli = 32 batch totali (= solo 20 in volo). Con latenza
media ~15-20s/batch instructor, il throughput effettivo è
  (200000 TPM × 18s) / (8000 token/batch × 60s) = ~7.5 batch sostenibili
  contro 20 teorici del semaforo.
Il vero gate sembra il TPM, non il semaforo. Posso:
  (a) ridurre il batch a 7 (meno token/chiamata → più batch sostenibili)
  (b) alzare DEPLOYMENT a PTU (Provisioned Throughput Unit) Azure (costo fisso
      mensile, throughput dedicato)
  (c) sostituire con DeepSeek V4 Flash (no TPM, ma qualità italiano)
Quale leveresti per primo?

──────────────────────────────────────────────────────────────────────────────
H4 — PREFETCH IMMAGINI Pexels in pipeline vs background
──────────────────────────────────────────────────────────────────────────────
Per ~80 slide CONTENT_IMAGE × ~1.5s/request Pexels (rate limit 200/h free
tier) = ~2 min se serial. È già parallelizzato (Semaphore 50). Ma scarica
file binari (~200KB ciascuno) durante la pipeline. Vale la pena spostare
il download EFFETTIVO post-PPTX, e in pipeline solo registrare l'URL Pexels
+ insert PICTURE placeholder con path lazy? Vincolo: python-pptx vuole il
file fisicamente esistente per add_picture.

──────────────────────────────────────────────────────────────────────────────
H5 — PRODUCTION BUILDER python-pptx serial (REI-3)
──────────────────────────────────────────────────────────────────────────────
Il vincolo REI-3 Semaphore(1) ci tiene un solo corso in build per volta.
Per 1 corso singolo non è collo (build PPTX da 336 slide = ~30-40s totali,
verificato). Ma se il cliente lancia 5 corsi insieme dalla UI, vanno in fila
× 8 min = 40 min cumulati. Esiste un pattern per girare ProductionBuilder
in un process pool separato (multiprocessing.Pool, NON thread) per parallel
build di corsi DIVERSI mantenendo l'invariante "1 corso = 1 processo
python-pptx"?

──────────────────────────────────────────────────────────────────────────────
H6 — Affiancare OpenAI diretto (gpt-4.1-mini) ad Azure: load-balancing TPM
──────────────────────────────────────────────────────────────────────────────
Il cliente ha già una chiave OpenAI diretto con gpt-4.1-mini stesso modello
di Azure: 200K TPM / 500 RPM / 2M TPD, stesso prezzo ($0.40 in / $1.60 out
per 1M tk), stesso supporto JSON strict mode.

L'idea NON è sostituire Azure, ma AGGIUNGERE OpenAI come secondo L0 in
load-balancing round-robin con Azure:

  Azure mini      → 200K TPM
  OpenAI mini     → 200K TPM (aggiunto)
  ────────────────────────────
  Aggregato       → 400K TPM = raddoppio capacità content_agent

L'effetto su H3 (TPM-bound, ~7.5 batch sostenibili oggi) sarebbe ~15 batch
sostenibili = circa -40% del tempo content_agent (che è la fetta grande dello
job dopo audio TTS). LOC stimati: ~30 righe in _FALLBACK_CHAIN + counter
round-robin, no architettura nuova, no breaking change. Compliance non in
discussione: lavoriamo su normativa pubblica D.Lgs. 81/08, non dati personali.

Rischi che ho identificato:
  (a) Tier OpenAI: i 200K visti potrebbero essere tier 1 default. Se cliente
      sale a tier 3-4 (storico spesa), diventa 2-10M TPM e cambia
      completamente il piano (a quel punto OpenAI L0 unico, Azure L1
      fallback). Non lo sappiamo ancora.
  (b) Fallback chain riordino: oggi è L0=Azure mini → L1=Azure gpt-4o
      → L2=Sonnet. Se aggiungo OpenAI come L0bis, dove va gpt-4o? Resta L1?
      O lo demoto a L2 e Sonnet sparisce? Conta perché gpt-4o costa 5×
      mini, una scelta sbagliata raddoppia la spesa in caso di outage.

Domande secche:
  - Per problema TPM, il load-balancing Azure+OpenAI è la prima leva o ne
    vedi una migliore (es. ridurre batch size da 10 a 6 per stare più
    dentro il budget per chiamata)?
  - Il riordino fallback come lo penseresti? Io tengo L1=gpt-4o e demoto
    Sonnet a L3 emergenza vera, ma è gusto.
──────────────────────────────────────────────────────────────────────────────

La mia priorità d'attacco (da confermare con te):
  1. Strumentare timing per fase (research / content / build / audio) → 30 min
     di lavoro per capire DOVE perdo tempo, non dove credo di perderlo.
  2. Parallelizzare edge-tts (H2) — facile e probabilmente ad alto impatto.
  3. Decidere insieme a te H3 (batch+TPM) e H5 (process pool) sulla base
     dei numeri reali del punto 1.
  4. Valutare con te H6 (OpenAI mini affiancato in load-balance) PRIMA di
     muoverlo: ~30 LOC ma tocca fallback chain, non lo apro senza il tuo OK.

Vincoli che non tocco senza il tuo OK:
  - REI-3 (Semaphore(1) python-pptx). Eventuale process pool è cambiamento
    grosso, non lo apro senza scambio.
  - Pacing dinamico chunks-based (#30.2) e cluster cosine (#30.9c/d). Hanno
    appena raggiunto qualità accettabile, non li riapro.
  - Catalogo COURSE_CATALOG (#30.9e) con 4 moduli fissi. Il cliente è abituato
    a vedere quella tassonomia.

Cosa consigli? In particolare H1 (vero collo nel research?), H2 (edge-tts
parallel safe?) e H6 (load-balance Azure+OpenAI) mi servono per decidere se
lavoro stanotte o aspetto la tua risposta domattina.

──────────────────────────────────────────────────────────────────────────────
MIE DOMANDE OPERATIVE (a cui rispondi quando rispondi al resto)
──────────────────────────────────────────────────────────────────────────────

(D1) BACKFILL WAVE INUTILI
Il prefetch immagini chiude con 8 buchi non risolti, poi parte un loop
'backfill_wave' che fa 8 wave da 20s ciascuna (160s totali) tentando di
riempirli, e ad ogni wave filled=0. Tutti gli 8 finiscono in branded
fallback comunque. È retry cieco che brucia 2.5 min. Posso:
  (a) ridurlo a 2 wave (cap 40s);
  (b) eliminarlo del tutto e mandare i buchi direttamente in branded
      fallback senza riprovare;
  (c) tenerlo a 8 wave perché in casi diversi (rete instabile) tornava
      utile e qui sono stato sfortunato.
Sai dirmi se nei tuoi run precedenti il backfill ha MAI risolto buchi
(filled>0), o è sempre stato 0 e quindi è morto da rimuovere?

(D2) TEMPLATE CATALOG: PROMOZIONE NEL PROMPT
Su 21 diagrammi, l'LLM ha usato SOLO flow_3step e flow_4step. I 5 template
rimanenti (pyramid, org_tree, matrix_2x2, causa_effetto, compare_2col)
sono zero. Due ipotesi:
  (a) Il prompt elenca i 7 template con descrizione one-liner ma il
      modello tende al "sequenziale" perché è il pattern più frequente
      nel corpus di training.
  (b) Il contenuto del corso CFP "sicurezza lavoratori specifica basso
      rischio" è genuinamente lineare/processuale e i template
      gerarchici/matriciali non avrebbero senso applicarli a forza.
Tu che hai letto le slide, dimmi se la (b) regge o se c'erano slide
dove pyramid/org_tree/matrix sarebbero state più adatte. Se sì, modifico
il prompt aggiungendo 1-2 esempi positivi per ogni template
sottoutilizzato (few-shot in prompt, no fine-tuning).

(D3) CARDINALITÀ DIAGRAM SU CORSI 8H
Sui corsi 4h ho 21 DIAGRAM = 6% (sotto il 7% target). Sui 8h non ho
ancora misurato. Vale la pena alzare la quota target DIAGRAM dal 5%
al 8-10% (significherebbe ~50 DIAGRAM su un 8h)? Il rischio è che il
modello inizi a forzare diagrammi su contenuti che andrebbero meglio
in CONTENT_TEXT (l'opposto di D2). La mia istinto è "no, lascia 5%
e fa' funzionare bene quei 21", ma chiedo a te che hai il quadro
didattico.

(D4) AUDIO TTS PRIORITY
Audio TTS è ~5 min sui 15 totali. Se lo paralleliz​zo con Semaphore(20)
mi aspetto 1.5-2 min. Ma c'è un'opzione che non ho considerato: spostarlo
DOPO la consegna PPTX (utente scarica subito il pptx, l'audio si genera
in background e arriva via WebSocket quando pronto). Per come usi i
corsi in produzione, è accettabile "scarica PPTX adesso, audio MP3 fra
3 minuti via notifica" o l'utente si aspetta il pacchetto completo
disponibile insieme?

(D5) IMMAGINE 'CONFRONTO GUANTI DPI OFFICINA' RIDONDANZA
Guardando il log Pexels, vedo che 'https://...8487792.jpeg' (un'immagine
DPI specifica) ricorre 8+ volte nel corso come risultato di query diverse
('procedure DPI sicurezza lavoro', 'datore lavoro DPI istruzioni', 'DPI
guanti', 'cantieri uso DPI', ecc.). Pexels restituisce la stessa
foto perché è quella più rilevante in catalog per "DPI". Tu vorresti che
implementi una de-duplica (dopo prefetch, se la stessa URL appare >2
volte, ri-cerca con query alternativa)? O 8 ripetizioni della stessa
foto su 100 CONTENT_IMAGE non è un problema didattico?

Grazie.
```
