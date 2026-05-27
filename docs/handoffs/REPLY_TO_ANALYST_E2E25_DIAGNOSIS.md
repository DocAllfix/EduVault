Hai ragione, la tua diagnosi "mismatch strutturale" non regge — e nemmeno la mia "cairosvg crash". Ho fatto quello che mi hai detto: ho aperto il fallimento vero invece di indovinare. Ti porto la diagnosi completa, perché è ancora diversa da entrambe le ipotesi e cambia la rotta di #31.7.

═══════════════════════════════════════════════════════════════════
COSA HO FATTO
═══════════════════════════════════════════════════════════════════

Ho ricostruito `DiagramFilling(**slide.image.diagram_filling)` esattamente come fa image_service._render_diagram_sync (riga 283) su tutti e 22 i DIAGRAM del corso E2E #25. Per ognuno ho misurato slot-per-slot e tentato l'istanziazione Pydantic.

Risultato esatto: **10 FAIL su 22 = 45%**, match perfetto col telemetry diagram_fallbacks=10.

Cosa fallisce: ZERO sono crash cairosvg. ZERO sono mismatch strutturale (LLM sceglie flow per gerarchie). TUTTI E 10 sono `pydantic ValueError` lanciato dal `check_slots` della classe `DiagramFilling` PRIMA che cairosvg sia mai chiamato. Cioè il fallback brandizzato scatta perché Pydantic respinge l'istanziazione, non perché il render fallisce.

═══════════════════════════════════════════════════════════════════
QUAL È IL TRIGGER ESATTO
═══════════════════════════════════════════════════════════════════

Il check_slots ha questa logica (l'hai approvata tu in #30.9f post-tolerance):
  - max_chars per slot (es. flow_horizontal_4step.label_*: 18 char)
  - tolerance = int(max_chars * 1.2) = 21 char per quel template
  - Se slot <= max_chars: passa intatto
  - Se max_chars < slot <= tolerance: truncate gentile "primi (max-1) char + …"
  - Se slot > tolerance: raise ValueError → fallback brandizzato

Esempi reali dai 10 fail:
  M0/idx9   "Identificazione rischi"  = 22c > tol 21 → raise (4.7% over tol)
  M0/idx80  "Identificazione agente"  = 22c > tol 21 → raise
  M3/idx29  "Segnale Colore o Cartello"        = 25c (tol 24) → raise
            "Segnali Luminosi o Acustici"      = 27c → raise
            "Segnali Gestuali e Verbali"       = 26c → raise
  M3/idx16  "Segnale di avvertimento" = 23c > tol 21 → raise
  M3/idx40  "Misure di manutenzione sicure" = 29c > tol 24 → raise

E delle 12 che passano, 8 usano il truncate gentile (label 19-21c → "Manutenz. continu…"). Quindi il truncate funziona dove arriva, semplicemente non arriva sui +4-9 char di sforo.

Pattern semantico dei label che falliscono: NON sono garbage LLM, sono label corretti dove sostantivi tecnici (`Identificazione rischi/agente`, `Segnale di X`, `Sorveglianza sanitaria`, `Monitoraggio e controllo`) hanno lunghezza intrinseca 22-29c che NON si comprime senza danneggiare la semantica. "Identificazione" in italiano è 15c di per sé.

═══════════════════════════════════════════════════════════════════
PERCHÉ ANCHE LA TUA IPOTESI "FORZARE TEMPLATE GIUSTO" NON RISOLVE
═══════════════════════════════════════════════════════════════════

Tutti i 10 fallback usano `flow_horizontal_4step` (max 18c) o `flow_horizontal_3step` (max 20c). Anche se forzassi pyramid_3level (max 17-30c) o org_tree_3level (max 22-40c) sui contenuti gerarchici/cluster, i pochi label tipo "Identificazione rischi" 22c o "Segnali Gestuali e Verbali" 26c sforerebbero anche su altri template (level_2a di org_tree è 22c, slot di pyramid level_1 è 17c). Il problema è trasversale: l'italiano tecnico normativo richiede 22-30c medi per essere semanticamente accurato; max_chars 18 è troppo stretto.

═══════════════════════════════════════════════════════════════════
TRE OPZIONI DI FIX — DECIDI TU
═══════════════════════════════════════════════════════════════════

Opzione A — Auto-shrink font invece di raise. Il commento del catalogo dice già: "auto-shrink font runtime: se il testo sta dentro max_chars ma è grande in pixel, scala font-size SVG fino a un minimo leggibile (14pt)". Il codice questo NON LO FA — il check_slots tronca o solleva. Il vero rimedio sarebbe: se slot > max_chars, non troncare e non raisare — emettere lo slot intero e scalare font_size SVG in proporzione (font_size * max_chars / actual_len, clipped a min 16pt). Pro: zero perdita semantica, mantieni "Sorveglianza sanitaria" pieno e leggibile a font 22pt invece di 28. Contro: ~25-40 LOC di tweaking SVG runtime (modifica `font-size="28"` nel raw_svg per quello slot specifico). Test: pytest unitario con 5 slot tra 18-30c e verifica che font_size esce coerente.

Opzione B — Truncate sempre (rimuovi il gate raise). Il check_slots tronca gentile fino a tolerance, raise oltre. Sostituire il raise con truncate sempre (anche a 25-30c): "Segnali Luminosi o Acu…", "Monitoraggio e contr…". Pro: 5 LOC, fix in 1 minuto, fallback scompare. Contro: alcuni truncate sono cosmeticamente brutti ("Segnali Gestuali e Ve…" perde "Verbali" intero); il principio "raise se sforo grosso = errore semantico vero" che hai approvato in #30.9f viene smontato. Ma `Identificazione rischi` 22c NON È errore semantico vero — è italiano normativo onesto, e il principio è tarato male.

Opzione C — Alza max_chars del catalogo + ridisegna SVG box. Riaprire flow_horizontal_4step.svg e allargare le box da 320px a 380px → max_chars sale da 18 a 22, e il check_slots passa per la maggioranza dei fallimenti. Pro: 0 perdita semantica, font_size invariato, nessun trick runtime. Contro: serve LibreOffice/Inkscape su 2-3 SVG (i flow_*step principalmente), rifare i max_chars del catalogo, testare visivamente che le frecce/connessioni si allarghino di conseguenza. Probabilmente 1-2h di lavoro grafico, ma è il fix di radice.

═══════════════════════════════════════════════════════════════════
LE MIE PROPENSIONI (poi decidi tu)
═══════════════════════════════════════════════════════════════════

A è la più elegante ma è codice runtime nuovo non testato (rischio regressioni su altri template). B è la più rapida (5 LOC, deploy in 5 min) ma cosmeticamente subottimale sui truncate aggressivi. C è strutturalmente più sana ma è lavoro grafico che non so quanto LibreOffice/Inkscape mi farà battagliare su Windows.

Propensione mia: **B subito per sbloccare la demo (5 LOC, regressione 0), e C come work-item post-demo per qualità lungo termine.** A lo lascerei stare perché il valore aggiunto vs B è cosmetico e il rischio runtime no.

═══════════════════════════════════════════════════════════════════
DOMANDE
═══════════════════════════════════════════════════════════════════

DQ1. Quale delle 3 (A/B/C) implemento per #31.7? Se B, vuoi che il truncate massimo sia un cap (es. max 28c, oltre raise comunque)? O truncate sempre senza limite?

DQ2. Se vai su B, lo stesso check_slots ha già la logica truncate per range [max_chars, tolerance]. Per estenderla a (tolerance, ∞) basta rimuovere il `raise` e fare truncate sempre? O preferisci due strategie: gentile (truncate fino a max_chars-1 + …) sotto tolerance, aggressivo (truncate fino a max_chars-3 + … = 3 char ellisse evidenti) sopra tolerance?

DQ3. Se preferisci C, sei OK che io modifichi i 2 SVG flow_horizontal_* a mano via editing diretto del file SVG (sono XML, posso ricalcolarne le coordinate senza GUI grafica) e aggiorno i max_chars del catalogo a 22/24? Oppure preferisci che faccia A e B in stack?

DQ4. Dopo il fix scelto: testo E2E rapido 1h corso "Aggiornamento" (1 modulo ~20 slide, ~3-5 DIAGRAM stimati) per verificare diagram_fallbacks scende a 0. Se OK, lancio i 3 corsi demo finali e poi me li valuti uno per uno prima di deploy. Va bene questa sequenza?

PPTX corso E2E #25 ancora sul Desktop, ti dico solo che pure tutto il resto è verde: M3 zero off-topic, M1 recuperato a 82, 9m 36s. Aspetto il tuo OK su DQ1-DQ4 e parto.
