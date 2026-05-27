E2E #25 chiusa — FIX #31.6 (4 punti: prompt POSITIVO + coercion strip suffissi + query Segnaletica ricalibrata + drop-list)

Ti ho appena messo sul Desktop il PPTX: CFP_4h_E2E25_31.6_da_analista.pptx (52 MB, 336 slide).

═══════════════════════════════════════════════════════════════════
NUMERI E2E #25 vs E2E #24
═══════════════════════════════════════════════════════════════════

Metrica                                #24                 #25
Tempo pipeline                         11m 44s             9m 36s  ✅ -18%
Slide totali                           336                 336
M0/M1/M2/M3 slide count                82/55/82/82(*)      82/82/82/82  ✅ M1 recuperato (sub-batch)
batches_failed                         2 (M1)              0 ovunque  ✅
diagram_fallbacks                      14                  10  ⚠️ -29% ma target era ≤2-3
M3 Segnaletica off-topic in coda       13 slide            0 slide  ✅ drop-list+query OK
reask_avg_per_batch                    0.0                 0.0
images_inserted                        ~135                137
image_fallbacks                        0                   0

(*) #24 M1 aveva 55 slide perché 2 batch falliti senza recovery; #25
la sub-batch recovery ha salvato il modulo a 82/82.

═══════════════════════════════════════════════════════════════════
TE LO DICO IN ONESTÀ — i 10 diagram_fallbacks residui
═══════════════════════════════════════════════════════════════════

Ho ispezionato i 22 DIAGRAM nel DB. Le slot dei label sono PERFETTE:

  DIAGRAM #9 (M0): label_1="Identificazione rischi" (24c)
                   label_2="Valutazione rischi" (19c)
                   label_3="Misure prevenzione" (18c)
                   label_4="Monitoraggio e controllo" (24c)
                   caption="Le 4 fasi obbligatorie del processo di
                            gestione rischio art. 28 D.Lgs. 81/08." (77c)

Tutti i label sono corti, zero suffissi "secondo D.Lgs.", zero "ai sensi
di". La coercion strip ha fatto il suo lavoro. Quindi i 10 fallback
NON sono più per validation/lunghezza.

Però guardando il template_name scelto:
  - 22 DIAGRAM su 22 usano flow_horizontal_3step (4) o flow_horizontal_4step (18)
  - 0 org_tree_3level, 0 pyramid_3level, 0 cluster_central

Questa è esattamente la diagnosi che mi avevi anticipato nella review 7:
"i fallback che restano voglio vedere se sono mismatch strutturali veri
(gerarchie che vorrebbero org_tree) o ancora lunghezza."

→ Adesso so che è MISMATCH STRUTTURALE. L'LLM sceglie sempre flow_*
anche per concetti come "Componenti del sistema di gestione delle
emergenze" (vorrebbe pyramid o cluster), o "Posizionamento e
caratteristiche dei cartelli segnaletici" (vorrebbe cluster_central),
e poi cairosvg non riesce a popolare lo slot caption + label in
quegli SVG specifici (ipotesi mia) oppure il render genera SVG
malformati che cairosvg non parsa.

Domanda 1 — voglio aprire i 10 fallback (te li elenco se serve) per
capire se cairosvg ha realmente fallito (un crash) o se il PPTX
contiene il PNG renderizzato ma è stato comunque contato fallback
dal nostro telemetry (bug di metrica). Mi confermi che la diagnosi
"mismatch strutturale" giustifica un fix come #31.7 con un set di
example concreti nel prompt che mappano "gerarchia → pyramid",
"cluster di sotto-concetti → cluster_central", "step temporali → flow_*"?
O preferisci che provi prima a forzare deterministicamente la scelta
di template via euristica sui caption ("processo di X → flow",
"componenti di X → pyramid")?

═══════════════════════════════════════════════════════════════════
M3 Segnaletica: ti elenco i primi 30 titoli (zero off-topic)
═══════════════════════════════════════════════════════════════════

1. Caratteristiche intrinseche dei cartelli segnaletici
2. Forma e colori dei cartelli
3. Materiali e resistenza dei cartelli
4. Esempi di cartelli segnaletici in cantiere (CONTENT_IMAGE)
5. Dimensioni e visibilità dei cartelli
6. Posizione e montaggio della segnaletica
7. Cartelli luminosi e riflettenti in magazzino (CONTENT_IMAGE)
8. Quiz: dove posizionare un cartello di rischio specifico?
9. Posizionamento e caratteristiche dei cartelli segnaletici (DIAGRAM)
10. Caso studio: segnaletica inefficace in cantiere edile
11. Tipi di segnale nella segnaletica di sicurezza
12-15. Esempi di segnali divieto/avvertimento/prescrizione/salvataggio
16. Tipologie di segnale nella segnaletica di sicurezza (DIAGRAM)
17-19. Quiz su tipi segnali
20. Riepilogo: categorie di segnaletica di sicurezza (RECAP)
21. Segnaletica per rischi di urto e caduta
22. Segnaletica permanente per vie di circolazione
23. Segnalazione occasionale in situazioni di pericolo
24. Guida occasionale tramite segnali gestuali
25. Intercambiabilità della segnaletica
26. Colori di sicurezza e loro significato
27. Esempi di segnaletica con colori di sicurezza permanenti
28. Segnali luminosi e acustici per situazioni occasionali
29. Combinazioni di segnaletica secondo la legge (DIAGRAM)
30. Caso studio: scorretta segnalazione di pericoli occasionali

E così via per altri 54 titoli, tutti su segnaletica reale:
cartelli, segnali luminosi/acustici/gestuali, colori,
posizionamento, recinzione cantiere, dispositivi di comando,
illuminazione, attrezzature, contenitori/tubazioni.
ZERO sanzioni, ZERO medico competente, ZERO RSPP, ZERO inidoneità,
ZERO sorveglianza sanitaria.

═══════════════════════════════════════════════════════════════════
DOMANDE AL TUO OK
═══════════════════════════════════════════════════════════════════

D1. Apro il PPTX con gli occhi: 10 fallback su 22 DIAGRAM = ~45%.
    M3 ne ha 6 (idx 9, 16, 29, 40, 69, 81): vuoi che te ne render
    visivamente 2-3 per vedere se sono branded fallback o
    veramente cairo-rendered SVG con slot poco utilizzati?

D2. M3 Segnaletica è ON-TOPIC al 100% adesso. Il drop-list di sanzioni/
    medico/RSPP funziona. Possiamo dichiarare M3 chiuso?

D3. Tempo a 9m 36s (-18% vs #24) — è il limite con singolo modello
    Azure mini? H6 (load-balance Azure+OpenAI) può scendere a 7-8
    min secondo te? Ho il piano pronto in docs/H6_IMPLEMENTATION_PLAN.md
    (introduce semaforo soft Azure + fallback OpenAI quando reask).

D4. Considerati i 10 fallback DIAGRAM ancora aperti (mismatch
    template, non più lunghezza), TI BASTA che vada in demo
    cliente con questi 10 (su 336 slide = 3%) sapendo che sono
    branded fallback "CFP rosa", o vuoi che fixi PRIMA il mismatch
    di template scelta come #31.7?

═══════════════════════════════════════════════════════════════════
COSA TI CHIEDO DI VERIFICARE APRENDO IL PPTX
═══════════════════════════════════════════════════════════════════

Aprilo e guardalo con gli occhi modulo per modulo, perché le
metriche numeriche stavolta sono buone su quasi tutto e voglio
che TU mi dica se è bozza-RSPP consegnabile per la demo cliente:

1. IMMAGINI (137 totali) — apri qualche CONTENT_IMAGE casuale e
   dimmi:
   - Sono contestuali al titolo della slide? (es. "Esempi di cartelli
     segnaletici in cantiere" → la foto mostra davvero cartelli in
     un cantiere edile, non un quadro generico)
   - Risoluzione/qualità accettabile, niente loghi watermark, niente
     foto stock palesemente americane fuori contesto?
   - Una stessa immagine appare in più slide diverse? (deduplicazione
     ha funzionato — ne ho contate 137 distinte ma può comunque essere
     che la stessa appaia 2-3 volte in moduli diversi)

2. DIAGRAMMI (22 totali) — apri i 22 e dimmi quanti sono:
   - Diagrammi reali catalog (con flow box, frecce, label colorati)
   - vs Branded fallback (icona stella rosa CFP + testo che sborda)
   So che il telemetry dice 10 fallback. Voglio la conta REALE con
   gli occhi: c'è discrepanza tra metrica e visivo?

3. CONTENUTO SLIDE — apri 10-15 slide a campione per modulo e dimmi:
   - I bullet sono normativi sostanziali o fuffa generica?
   - I caption/source_chunk_ids hanno riferimenti articolo coerenti?
   - Si vede ripetizione di concetti (es. "vie sgombre" già detto
     altrove)?

4. COERENZA TRA MODULI — leggi i titoli dei 4 moduli sequenzialmente
   e dimmi:
   - M0 "Rischi specifici" è coerente al titolo? (era OK in #23)
   - M1 "DPI" è coerente al titolo? (era OK in #23+24, in #25 recuperato
     a 82 slide via sub-batch — il recovery NON ha cambiato qualità?)
   - M2 "Procedure di emergenza" è coerente? (ripetizione "vie sgombre"
     scesa? SPREAD intra-modulo ancora attivo?)
   - M3 "Segnaletica" è coerente? (drop-list ha eliminato off-topic
     in coda — confermi che NON ci sono più sanzioni/medico
     sparse nelle 82 slide?)

5. QUIZ e CASE_STUDY — apri 3-4 quiz e 2-3 case study e dimmi:
   - I quiz hanno opzioni plausibili, non assurde?
   - I case study hanno scenario credibile, non parodia?

6. BOOKENDS — apri INTRO + INDICE + MODULE_OPEN x4 + MODULE_CLOSE x4
   + RECAP finale + CERTIFICATE e dimmi:
   - Sono coerenti tra loro (stesso titolo corso, stessi 4 nomi modulo)?
   - Il layout/branding C.F.P. Montessori è applicato uniforme?

═══════════════════════════════════════════════════════════════════

PPTX sul Desktop: CFP_4h_E2E25_31.6_da_analista.pptx (52 MB).
In attesa del tuo OK gate completo prima di generare i 2 corsi demo
(Generale 4h + Primo Soccorso 8h) e fare commit + deploy
Vercel+Railway.

PS — H6 piano pronto. Se vuoi, dopo questa demo lo apriamo e
mi dici se preferisci semaforo soft Azure→OpenAI on-reask, oppure
50/50 split deterministico fra i due provider.

