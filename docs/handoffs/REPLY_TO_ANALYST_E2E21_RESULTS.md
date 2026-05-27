# Risultati E2E #21 post-#31.2 — onestà sul gate NON passato

**Allegati Desktop:**
- `CFP_4h_E2E21_31.2_da_analista.pptx` (43 MB, 326 slide)
- `CFP_4h_E2E21_31.2_dispensa.pdf` (354 KB)

---

```
Caro analista,

E2E #21 con top_k=70 finito. Risultato misto, te lo dico dritto.

══════════════════════════════════════════════════════════════════
1. NUMERI — confronto E2E #20 vs #21
══════════════════════════════════════════════════════════════════

  Metrica                       E2E #20    E2E #21    Δ
  Tempo pipeline                10m 38s    8m 28s     -2m 10s (-20%!)
  Slide totali                  335        326        invariato
  per_module_kept M0            36         57         +21
  per_module_kept M1            32         47         +15
  per_module_kept M2            30         41         +11
  per_module_kept M3            38         52         +14
  duplicates_removed            44         83         +39 (più chunk = più sovrapposizione)
  reask_avg_per_batch           0.0        0.0        invariato
  Ripetizione "vie sgombre" M2  7          7          INVARIATO ❌

══════════════════════════════════════════════════════════════════
2. IL GATE TUO NON È PASSATO — ma in modo diagnostico utile
══════════════════════════════════════════════════════════════════

Tu mi avevi detto: "alza top_k 45→70, M2 perderà meno chunk alla
dedup, content_agent avrà più materiale DIVERSO da espandere,
la ripetizione crolla — voglio le 'vie sgombre' a 2-3".

I numeri dicono:
  - più chunk distinti per modulo (M2: 30→41, +37%) ✅
  - ma stesse 7 ripetizioni "vie sgombre/percorsi liberi" ❌

Le 7 occorrenze in M2 sono:
   5 [CONTENT_IMAGE]    Vie e uscite di emergenza sgombre e sicure
  41 [CONTENT_TEXT]     Vie e uscite di emergenza libere e accessibili
  43 [CONTENT_TEXT]     Evacuazione rapida e sicura: priorità in emergenza
  54 [CONTENT_TEXT]     Vie e uscite di emergenza sempre libere e senza ostacoli
  65 [CONTENT_IMAGE]    Evacuazione rapida e sicura dei posti di lavoro
  66 [CONTENT_IMAGE]    Vie di emergenza libere e sicure in officina
  69 [DIAGRAM]          Processo per vie e uscite di emergenza sicure

Lettura: il content_agent ha più materiale a disposizione (41 chunk
puri vs 30) ma continua a riformulare lo stesso concetto base con
parole leggermente diverse. Significa che il problema NON era SOLO
"chunk insufficienti", era ANCHE "content_agent non ha istruzioni
intra-modulo per variare angolazione".

Ho verificato il prompt del content_agent: c'è regola anti-ripetizione
CROSS-modulo (build_previous_summary passa titoli moduli precedenti),
ma NON c'è regola INTRA-modulo. Tu l'avevi chiamata "considerazione
marginale" — sui dati scopriamo che è NECESSARIA insieme a top_k=70,
non alternativa.

══════════════════════════════════════════════════════════════════
3. EFFETTO COLLATERALE SUL TEMPO: -20% ULTERIORE (8m 28s)
══════════════════════════════════════════════════════════════════

Te l'avevi previsto al contrario: "top_k=70 potrebbe riportare il
tempo a ~11.5 min, +1 min per token in più". Invece è SCESO di altri
2 min. Ipotesi (da verificare sui 3 corsi demo): con più chunk
distinti per modulo, il content_agent compone slide più semplici
(meno sforzo nel "inventare angolazioni nuove dal poco materiale"),
batch chiudono ancora più rapidamente. Reask sempre 0.

Stato tempi cumulativo:
  E2E #18 baseline pre-FIX#31:                 15m 41s
  E2E #19 post-FIX#31 (4 mosse):               13m 32s  (-13.7%)
  E2E #20 post-#31.1 (retrieval per-modulo):   10m 38s  (-21.4% vs #19)
  E2E #21 post-#31.2 (top_k=70):               8m 28s   (-20.4% vs #20)
  TOTALE da #18:                               -7m 13s  (-46%)

H6 scende ulteriormente di urgenza. A 8m 28s un'attesa self-serve è
gestibile senza grandi acrobazie UX.

══════════════════════════════════════════════════════════════════
4. PROPOSTA OPERATIVA — chiedo OK su scelta tra A e B
══════════════════════════════════════════════════════════════════

OPZIONE A: aggiungo la "riga prompt anti-ripetizione intra-modulo"
   nel content_agent (la tua considerazione marginale promossa a
   leva attiva). Esempio testo:
   
   "Quando generi slide CONTENT_TEXT/CONTENT_IMAGE consecutive su
   un tema simile, varia l'angolazione: definizione → esempio
   pratico → errore comune → caso reale → quiz. Non riformulare
   lo stesso punto con parole diverse."
   
   LOC: ~5 righe in app/agents/prompts.py.
   Tempo: 10 min code + 12 min E2E #22 verifica.
   Rischio: bassissimo, è solo testo nel system prompt.

OPZIONE B: accetto le 7 ripetizioni come "rumore on-topic"
   accettabile e procedo con la demo. Il cliente leggerebbe
   "vie sgombre" 7 volte su 84 slide M2 = 1 ogni 12 slide,
   distanziate (slide 5, 41, 43, 54, 65, 66, 69). Non sono
   consecutive, quindi se uno scorre dall'alto le incontra
   sparse non in blocco. È brutto ma sopravvivibile per una
   bozza-RSPP.

OPZIONE C: faccio A + procedo. La A non ha rischio, vale 22 min,
   e se funziona la demo parte con M2 davvero pulito (5-6
   ripetizioni → 2-3). Se NON funziona, faccio comunque la
   demo con opzione B (le 7 ripetizioni di adesso, niente
   regressioni).

La mia preferenza è C (faccio l'esperimento perché costa poco
e potrebbe funzionare; se non funziona, ho il fallback B
pronto). Ma la decisione è tua perché il gate "vie sgombre ≤3"
non è passato e tu hai il diritto di dire "no, ferma e ragiona
prima".

══════════════════════════════════════════════════════════════════
5. RIEPILOGO STATO ATTUALE
══════════════════════════════════════════════════════════════════

Allegato: CFP_4h_E2E21_31.2_da_analista.pptx (43 MB, 326 slide,
sotto Desktop).

Qualità complessiva: coerenza tematica M2/M3 confermata (no più
grab-bag), ripetizione M2 residua identica a #20, tutti altri
indicatori migliori o invariati.

DOMANDA SECCA: A, B o C?

(Se non rispondi entro 30 min vado avanti con C per non bloccare
la deadline demo cliente, ma fammi sapere appena puoi così
correggo rotta se diverso.)

Grazie.
```

---

## Per te — note operative fuori dal messaggio

### Numeri grezzi sotto mano

| Aspetto | Valore |
|---|---|
| Tempo E2E #21 | **8m 28s** (era 10m 38s in #20, **-20%**) |
| Slide totali | 326 (era 335 in #20) |
| `per_module_kept` | M0:57 / M1:47 / M2:41 / M3:52 |
| `lost_to_other_module` | M0:13 / M1:23 / M2:29 / M3:18 (M2 perde di più) |
| `duplicates_removed` | 83 (era 44) — più chunk = più sovrapposizione cross-modulo |
| **"vie sgombre" M2** | **7 ancora** (target era ≤3) |

### Cosa farei se decidi opzione C senza aspettare analista

1. Edit `app/agents/prompts.py` aggiungendo regola anti-ripetizione intra-modulo (~5 LOC).
2. Sync + restart (disciplina backend).
3. Lancio E2E #22 (~8-9 min).
4. Riconteggio "vie sgombre" in M2.
5. Se ≤3 → gate passato, procedo con altri 2 corsi demo + commit + deploy.
6. Se ancora >5 → opzione B (consegno #21 com'è all'analista per OK come "bozza accettabile").

### Cosa NON farei senza tuo OK

- Toccare H6 (analista chiaro: "dopo le rifiniture").
- Modificare pacing/durata (vincolo categorico).
- Cambiare top_k oltre 70 (analista non l'ha autorizzato).

### Tempo stimato per chiudere demo (se opzione C funziona)

- Opzione C esperimento: 22 min
- 2 altri corsi demo (Generale 4h + Primo Soccorso 8h): ~30 min (era 40 stimati, ma con #21 a 8.5 min/corso scende a ~17 min ciascuno se 8h scala lineare = 17m × 2 = 34 min)
- Commit + push: 10 min
- Setup deploy Railway+Vercel: 3-4h
- **Totale**: 1h05 lavoro mio + 3-4h deploy + ~50 min E2E in background
