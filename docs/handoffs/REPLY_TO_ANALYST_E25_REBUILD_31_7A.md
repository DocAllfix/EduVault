FIX #31.7A implementato esattamente come hai prescritto — auto-shrink font UNIFORME per diagramma, floor 16pt come ultima rete, raise rimosso da check_slots — e ho rebuildato il corso E2E #25 senza rifare la pipeline (le slide erano già nel DB, ho rilanciato solo prefetch_images + ProductionBuilder, 30 secondi).

Sul Desktop ora trovi:
- CFP_4h_E25_REBUILD_31.7A.pptx (50 MB, 336 slide, 22 diagrammi)
- CFP_4h_E25_REBUILD_31.7A.pdf (0,4 MB, dispensa)
- Cartella CFP_E25_diagrams_post_31_7A/ con 22 PNG singoli, naming = M{modulo}_idx{indice}_{font}pt_{slug-titolo}.png

Questo è il file candidato a diventare il primo demo cliente. Prima di lanciare i 3 corsi demo (Generale 4h + Primo Soccorso 8h + Specifica 4h) voglio il tuo OK in precisione su tutto il PPTX, slide per slide se necessario, perché se questo va al cliente non posso permettermi cose "che mi sono sfuggite".

═══════════════════════════════════════════════════════════════════
COSA HO CAMBIATO IN #31.7A (5 punti tecnici)
═══════════════════════════════════════════════════════════════════

1. RIMOSSO il raise di check_slots per sforo >20% sopra max_chars.
   Pre-fix: label 22c su max 18 (tol 21) → ValueError → fallback brandizzato.
   Post-fix: label 22c entra intero, render farà font-shrink.
   Conservato: truncate gentile sotto tolerance (label 19c → "Manutenz. continu…").
   Conservato: raise per slot mancanti (errore semantico vero).

2. AGGIUNTA funzione _compute_uniform_font_size(filling) → (font, slots).
   Algoritmo: per ogni slot calcola font_target = font_default * max_chars / actual_len.
   Prende il MIN tra tutti i font_target del diagramma.
   Clip a [16pt, font_default_max]. Tutti gli slot del diagramma usano lo
   stesso font uniforme (anti-imbalance, come hai insistito).

3. AGGIUNTO ultimo-rete truncate: se a 16pt qualche slot ancora sfora la
   capacità del box (raro per testi reali italiani 22-30c), tronca quello
   slot a capacity-1 + "…". Sui 22 diagrammi reali di E2E #25 NON è mai
   scattato.

4. MODIFICATO render_diagram_to_svg: dopo lo svg.read_text(), sostituisce
   font-size="N_default" con font-size="N_uniform" per TUTTI i tag <text>
   del template (regex replace mirato sui distinti font default del catalogo
   per quel template). Poi sostituisce i {{slot}} con i valori finali
   escapati XML come prima.

5. AGGIUNTO log strutturato "diagram_rendered" con template, uniform_font,
   default_font_max, shrunk=True/False. Così in futuro vediamo subito
   nei log quali diagrammi hanno avuto shrink e di quanto.

Codice: app/services/diagram_service.py, ~85 LOC nuovi (compreso il commento
narrativo), zero file touched fuori da diagram_service.py.

Test: tests/unit/test_diagram_font_shrink.py — 12 test isolati (5 unit su
_compute_uniform_font_size, 4 integration su render_diagram_to_svg, 3
regression su check_slots). Più i 15 test pre-esistenti
(test_label_suffix_strip.py) che continuano a passare. Totale 27/27 verdi.

═══════════════════════════════════════════════════════════════════
VERIFICA RETROATTIVA SUI 22 DIAGRAM E2E #25 (dati reali, non simulazione)
═══════════════════════════════════════════════════════════════════

Ho ricostruito DiagramFilling(**slide.image.diagram_filling) per tutti 22 e
ho fatto cairosvg.svg2png su ognuno:

  Pre-#31.7A telemetry: diagram_fallbacks=10/22 (45%)
  Post-#31.7A misurato: diagram_fallbacks=0/22 (0%)  ← gate raggiunto
  Render cairosvg:       22/22 OK, zero crash

Distribuzione font sui 22 diagrammi:
  34pt:  4 diagram (default flow_3step, no shrink)
  28pt:  8 diagram (default flow_4step, no shrink)  ← oltre metà al font pieno
  25pt:  1 diagram (M3/idx29 "Segnali Colore/Luminosi/Gestuali", caso emblematico)
  23pt:  1 diagram (M3/idx40 "Misure di manutenzione sicure" 29c)
  22pt:  2 diagram (M0/idx80, M3/idx81)
  21pt:  4 diagram
  20pt:  1 diagram (M3/idx69 "Flusso di sicurezza nei sistemi di comando")
  19pt:  1 diagram (M1/idx15 "Processo di selezione dei DPI adeguati")  ← MIN

  Floor 16pt: ZERO diagrammi scendono al floor.
  Sotto soft-warning 18pt: 2/22 (9%).
  Tuo gate ("se molti scendono sotto 18 → C work-item"): 9% ≤ soglia → C non serve.

═══════════════════════════════════════════════════════════════════
COSA TI CHIEDO DI VERIFICARE — slide per slide, in precisione
═══════════════════════════════════════════════════════════════════

Apri CFP_4h_E25_REBUILD_31.7A.pptx e fai il giro completo come se fossi il
cliente che lo riceve in mail come demo. Sono 336 slide, sono tante, ma il
costo di farsi sfuggire UN difetto adesso è alto. Ti chiedo specificamente:

A. DIAGRAMMI (22 totali — i PNG singoli sono nella cartella per ispezione
   rapida fuori dal PPTX)
   - Apri prima M3/idx29 (font 25pt, caso emblematico): "Segnali Gestuali
     e Verbali" deve essere INTERO nel box, nessun "…". È il test che mi hai
     chiesto verbatim. Se non lo è, qualcosa non torna.
   - Apri M1/idx15 (font 19pt, il minimo): è leggibile o è troppo piccolo?
     Vedi i 4 slot allo STESSO font (uniforme) o c'è qualche slot più grande
     accanto a uno più piccolo? Se vedi imbalance, lo shrink non è uniforme
     come hai chiesto.
   - Apri M3/idx69 (font 20pt): stessa verifica.
   - Apri qualche font 28-34pt (i 12 che erano già OK prima): sono identici
     a prima, nessuna regressione visiva?
   - Per ognuno dei 22: il testo entra DENTRO la box (no sbordature, no
     overflow sui margini)?
   - Le frecce/connessioni del template sono tutte presenti?

B. CONTENUTO SLIDE (336 totali, campione casuale 15-20 per modulo)
   - I bullet sono normativamente sostanziali (citano articoli, allegati,
     misure concrete) o sono fuffa generica ("è importante", "bisogna fare
     attenzione")?
   - source_chunk_ids nei caption / note speaker hanno riferimenti
     coerenti col contenuto?
   - Ripetizioni: "vie sgombre" o sinonimi compaiono ancora 5+ volte in M2?
   - Slide CONTENT_IMAGE: il bullet sotto è coerente con l'immagine sopra
     (es. titolo "cartelli antincendio" → immagine cartello antincendio +
     bullet che parla davvero di cartelli antincendio)?

C. COERENZA TRA MODULI (i 4 titoli sequenziali)
   - M0 "Rischi specifici": tutto coerente al titolo del modulo? Niente
     deriva su altri temi?
   - M1 "DPI": coerente, e la qualità delle slide nel range 28-55 (range
     dove c'era stato il sub-batch recovery #25) è uguale al resto?
   - M2 "Procedure di emergenza": ripetizione "vie sgombre" scesa rispetto
     a #20? SPREAD intra-modulo ancora attivo (sotto-temi diversificati)?
   - M3 "Segnaletica": confermi che NON ci sono più sanzioni/medico/RSPP
     sparsi nelle 82 slide? (la mia query SQL ne ha contati ZERO, ma
     visivamente sui titoli completi sembra strano se ce ne fossero)

D. IMMAGINI (137 totali — provenienti da Pexels/Pixabay ricerca real)
   - Apri 10-15 CONTENT_IMAGE casuali: sono contestuali al titolo della
     slide?
   - Risoluzione e qualità OK, niente watermark, niente loghi terzi?
   - Dedup: vedi mai la STESSA immagine in 2 slide diverse?

E. QUIZ e CASE_STUDY (rispettivamente ~28 e ~16)
   - I quiz hanno 4 opzioni plausibili, una sola risposta corretta
     evidente, le altre 3 distrattori sensati?
   - I case study hanno scenario credibile e domanda di chiusura ragionata?

F. BOOKENDS (1 INTRO + 1 INDICE + 4 MODULE_OPEN + 4 MODULE_CLOSE + 1 RECAP
   FINALE + 1 CERTIFICATE = 12 slide)
   - Sono tutti coerenti tra loro (stesso titolo corso, stessi 4 nomi
     modulo)?
   - Il branding C.F.P. Montessori (logo, colori rosa/verde) è applicato
     in modo uniforme su tutte le 336?
   - Il CERTIFICATE è plausibilmente compilabile e usabile?

G. NOTE SPEAKER (auto-generate sotto ogni slide nel PPTX)
   - Sono lunghe ~90-110 parole come da spec o sono troppo brevi/lunghe?
   - Sono coerenti col contenuto della slide o sembrano riempitivo?

═══════════════════════════════════════════════════════════════════
DOMANDE PER CHIUDERE IL GATE
═══════════════════════════════════════════════════════════════════

Q1. Vista la verifica A-G, è questo PPTX in stato bozza-RSPP consegnabile
    come PRIMO file demo cliente, oppure ci sono difetti residui che vuoi
    che fixi prima dei 3 corsi demo finali?

Q2. Se rilevi difetti specifici e localizzati (es. "slide 173 ha un bullet
    sbagliato", "diagramma M0/idx9 sbordato 1px") posso correggerli
    manualmente nel Course Studio (l'editor in-app per slide singole)
    OPPURE rigenerare il singolo modulo. Quale preferisci?

Q3. Sui 2 diagrammi con font basso (19pt e 20pt), li accetti per la demo
    o vuoi che lavori sull'opzione C (allargare le box SVG dei flow) come
    work-item dedicato prima di lanciare i 3 corsi demo?

Q4. Confermi la sequenza: tu approvi #25 rebuild → io lancio i 3 corsi
    demo finali (Generale 4h, Primo Soccorso 8h, Specifica 4h) → tu li
    rivedi uno per uno → io commit + Chrome DevTools test + deploy
    Vercel+Railway?

═══════════════════════════════════════════════════════════════════

Ti aspetto con il responso slide-per-slide.

PS — Sui PNG nella cartella CFP_E25_diagrams_post_31_7A: il naming porta
direttamente il font usato (es. M0_idx009_21pt_*.png = M0, indice 9, font
21pt). Ordinandoli alfabeticamente vedi subito i 2 sotto 21pt (M1/idx015
a 19pt, M3/idx069 a 20pt) per ispezione mirata.
