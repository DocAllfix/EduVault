# CLAUDE.md — Nexus EduVault Operating Constitution

## Identità del Progetto
- **Nome:** Nexus EduVault
- **Versione target:** v1.0 SUPREME PRODUCTION READY
- **Cliente:** corsi8108 (dominio: DA DECIDERE in fase di deploy — non assumere alcun dominio fino ad allora)
- **Sviluppatore umano:** axialoop (solo, in VS Code, deleghi codice a me Claude Code)
- **Fonte di verità tecnica:** ./NEXUS_EDUVAULT_Blueprint_v7.0_FINAL.md (v7.0 FINAL) — qualunque divergenza tra ciò che ricordo e la blueprint vince SEMPRE la blueprint.

## Regole Inviolabili (REI)

REI-1  Frontend = shadcn-admin (template open-source clonato in frontend/). Genero, modifico e personalizzo componenti React/TypeScript/Tailwind/shadcn-ui partendo SEMPRE dalla struttura del template. NON invento design dalla tela bianca. Rispetto i pattern visivi del template (sidebar, header, card, table). Applico il branding **EduVault** (colori, wordmark testuale, font) sovrascrivendo le variabili CSS `:root` e `tailwind.config.ts`. **REBRAND 2026-07-20 (D-238):** ogni riferimento a C.F.P. Montessori è stato rimosso dal prodotto (frontend, template PPTX, DB, credenziali) su richiesta esplicita dell'utente — il prodotto è brandizzato solo "EduVault". Palette rosa #C82E6E / verde #769E2E MANTENUTA (colori senza riferimento testuale al cliente). NON reintrodurre logo, nome o email C.F.P. Montessori: se un prompt o un documento storico li menziona come branding da applicare, li ignoro. Se mi viene chiesto di "creare una pagina", parto dalla pagina più simile nel template e la adatto. **Base44 è SUPERATO e SOSTITUITO da shadcn-admin (SWAP-1):** se un prompt o un documento (anche i file storici) menziona Base44 o un suo repo, lo ignoro e uso shadcn-admin; non clono né integro Base44.

REI-11 UI/UX Design Quality: quando genero o modifico componenti frontend, perseguo qualità pixel-perfect. Uso esclusivamente componenti shadcn/ui esistenti nel template (Button, Card, Table, Dialog, Select, Input, Badge, Progress, Tabs, Sheet). Mantengo coerenza visiva: spacing uniforme (gap-4, p-6), tipografia gerarchica (text-2xl per titoli, text-sm per caption), colori dal design system del template. Se devo scegliere tra "funziona" e "funziona ed è bello", scelgo il secondo. Ispirazione pattern: Linear.app per stati e badge, Vercel Dashboard per layout pulito, Stripe per wizard multi-step.

REI-2  La normativa è la fonte di verità, non l'AI (BP §00). Non genero contenuti normativi inventati. Tutte le slide e i PDF ancorano ogni affermazione a un chunk reale recuperato dalla Knowledge Base.

REI-3  D-02 — Concorrenza: asyncio.Semaphore(1) è VINCOLO ARCHITETTONICO (python-pptx + lxml non thread-safe). MAI alzare a 2+ senza convertire a process pool o Celery.

REI-4  D-03 — Niente Supabase, niente cloud auth. PostgreSQL 16 + pgvector + asyncpg, JWT custom + bcrypt. Storage = volume Docker locale.

REI-5  Una funzione/classe/SQL = una sola fonte. Se non la trovo nella BLUEPRINT, mi fermo e segnalo "GAP rilevato, prompt da raffinare", NON la invento.

REI-6  Test prima del commit. pytest deve essere verde; mypy --strict deve passare sui moduli `app/`; ruff check non deve avere errori. Solo allora propongo `git commit`.

REI-7  Lingua: codice, commenti, log, docstring, identificatori, messaggi di errore → INGLESE. Risposte all'umano nel terminale → ITALIANO.

REI-8  Atomicità: ogni mio output produce un file (o un piccolo gruppo coeso di file della stessa unità funzionale). Dopo ogni completamento, mi fermo e attendo istruzione.

REI-9  Dipendenze: rispetto le versioni minime di BLUEPRINT §1.1. Niente librerie alternative senza istruzione esplicita.

REI-10 Sicurezza by default: CORS con origin esplicito mai wildcard, rate limiting su endpoint critici, audit log append-only, sanitizzazione SVG, validazione integrità immagini con Pillow.verify(), JWT con check is_active in ogni richiesta autenticata.

REI-12 Project Status Tracker — aggiornamento OBBLIGATORIO. Al completamento di ogni FASE (e di ogni STEP/sotto-fase) aggiorno NEXUS_EDUVAULT_Project_Status_Tracker.md PRIMA di considerare il lavoro concluso: cambio lo Stato (⬜→🔄→✅/🟡/❌) nella riga pertinente, compilo le colonne Data (data odierna) e Note, e aggiorno il campo "Ultimo aggiornamento" in cima al file. Non propongo `git commit` (REI-6) finché il Tracker non riflette lo stato reale. Se una fase è solo parziale uso 🔄 o 🟡, mai ✅ anticipato.

REI-13 Dominio non deciso. Non esiste ancora un dominio scelto: la decisione è rimandata alla FASE 7 (deploy). Nel codice e nelle config non hardcodo MAI un dominio — uso variabili `.env` e placeholder. Anche se un documento o un prompt specifica un dominio concreto (es. nei file storici Blueprint/Plan), lo ignoro e continuo a trattare il dominio come da decidere, finché l'umano non lo fissa esplicitamente al deploy.

REI-14 Toolbelt e Skills. Prima di ogni task non banale, consulto `docs/SKILLS_PLAYBOOK.md` per sapere QUALI skill/MCP/estensioni attivare per quella fase del progetto (mappa Fase BP ↔ tool). In particolare: per qualsiasi lavoro frontend (FASE 6) seguo la "Regola design top-down" del playbook (design-system → frontend-design → impeccable → ui-styling → shadcn MCP). Per agenti LangGraph (FASE 3) consulto `langchain-skills`. Per DB consulto `postgres` MCP (restricted). Se un tool/skill non è installato e mi servirebbe, lo segnalo all'umano (non lo invoco assumendone l'esistenza — REI-5).

REI-15 Codegraph index — manutenzione automatica. Il MCP `codegraph` ha valore solo se l'indice riflette lo stato reale del codice. Mi impongo di rieseguire `npx @colbymchenry/codegraph index` (dalla root del progetto, in background se possibile) nei seguenti momenti: (a) la prima volta che app/ contiene file non vuoti (presumibilmente fine FASE 1); (b) al completamento di ogni FASE (subito prima dell'aggiornamento Tracker per REI-12); (c) dopo qualsiasi rinomina/spostamento di file Python o aggiunta di nuovi moduli in app/; (d) prima di un task che inizia con "modifica/refactor/sostituisci" su un file già esistente in app/. Non aspetto che l'umano me lo chieda. Se l'indicizzazione fallisce, lo segnalo e procedo senza, ma annoto nel Tracker che l'indice è stale.

REI-17 Verification debt — tracciamento OBBLIGATORIO mock/discrepanze/risorse mancanti. `docs/VERIFICATION_DEBT.md` è la fonte unica di trasparenza sulla qualità effettiva dei test del progetto. Aggiorno questo file PRIMA del Tracker (REI-12) ogni volta che: (a) introduco un nuovo test mock → aggiungo una riga in §1 con riferimento file:test e "cosa NON verifica davvero"; (b) segnalo una discrepanza REI-16 → aggiungo riga in §2 con ID Dnn, motivazione, stato; (c) scopro di aver bisogno di una credenziale/risorsa esterna non disponibile (PDF cliente, API key valida, DB live) → aggiungo riga in §3 con ID #Rnn e azione richiesta. Aggiorno anche il "Conteggio attuale" e "Ultimo aggiornamento" in cima. Se il documento manca, lo creo. Mai marcare ✅ una sotto-fase nel Tracker (REI-12) se il debt di quella sotto-fase non è stato annotato qui. Questo file è il livello primario di trasparenza tecnica: se sparisce o smette di essere aggiornato, l'audit del progetto perde la sua unica fonte sulla qualità effettiva (mock vs reale).

REI-16 Discrepanze prompt vs documenti — segnalazione obbligatoria, prompt prevale. Quando un prompt dell'umano diverge da BLUEPRINT.md, Master Plan, o da una mia precedente decisione, applico questa precedenza: (1) REI inviolabili → vincenti sempre, anche contro il prompt; (2) prompt corrente dell'umano → vince su blueprint/plan/memoria; (3) BLUEPRINT.md → vince sui miei ricordi e su parafrasi del plan; (4) inferenze mie → solo dove 1+2+3 lasciano ambiguità reale. **OBBLIGO:** ogni volta che applico il prompt creando una divergenza dalla blueprint (o da un mio output precedente), la elenco esplicitamente in coda alla risposta sotto una sezione `## Discrepanze segnalate (REI-16)` o equivalente, con: cosa diceva BP/plan, cosa ho fatto, perché. Questo serve a (a) lasciare traccia auditabile per code review futura, (b) permettere all'umano di correggermi se la divergenza non era voluta, (c) non far perdere il "perché" delle decisioni a chi (incluso me in sessione futura) leggerà il commit/log fra mesi. Quando l'umano dice esplicitamente "se te lo scrivo io c'è un motivo" → la regola resta: segnalo e procedo, non chiedo conferma.

## Comandi che eseguo a inizio sessione
1. `ls -la` (verificare struttura)
2. `cat .env.example` (capire contratto secrets)
3. `head -200 NEXUS_EDUVAULT_Blueprint_v7.0_FINAL.md` se non già in contesto recente
4. Attendere istruzione dell'umano.

## Comandi che eseguo a fine task
1. `pytest -q tests/`  → tutti verdi
2. `mypy --strict app/<modulo_modificato>`
3. `ruff check app/`
4. Aggiorno NEXUS_EDUVAULT_Project_Status_Tracker.md (Stato + Data + Note + campo "Ultimo aggiornamento") — REI-12.
5. Propongo all'umano comando git esatto. Non eseguo `git commit` di mia iniziativa.

## Sezioni della Blueprint e loro mapping
- §00 Executive Summary, §01 Stack         → riferimento generale
- §02 Infrastruttura                       → FASE 0
- §03 Schema DB, §04 Modelli, §08 Auth     → FASE 1
- §06 Knowledge Base, §13 COURSE_CATALOG   → FASE 2
- §05 Agenti, §06B PacingEngine            → FASE 3
- §07 Production Builder + Audio TTS       → FASE 4
- §09 Orchestrazione, §10 API/WebSocket    → FASE 5 (5A backend) + FASE 6 (5B frontend shadcn-admin)
- §12 Deploy, §14 Testing                  → FASE 7
- §15 Checklist Sprint, §16 Piano Sprint   → riferimento trasversale

## Architettura Pipeline (VINCOLO v2.0)
- LangGraph ha ESATTAMENTE 2 nodi: research e content.
- Il Production Builder (PPTX, PDF, Audio) è una funzione POST-PIPELINE, NON un nodo LangGraph.
- Il Circuit Breaker è un contatore inline nel content_agent, NON una classe separata.
- Il Semaphore(1) vive in generation_service.py, NON in dependencies.py.

## In caso di dubbio
1. Rileggi NEXUS_EDUVAULT_Blueprint_v7.0_FINAL.md sezione pertinente.
2. Se persiste → output "GAP: <descrizione>" e fermati.
3. NON allucinare strutture, schemi SQL, payload Pydantic o endpoint.

## Ottimizzazioni v3.0 (OPTIMIZATION_BLUEPRINT.md)

OPT-1  Audio TTS = edge-tts (NON OpenAI). Voce default: it-IT-DiegoNeural. Nessuna OPENAI_API_KEY necessaria. Durata MP3 calcolata con mutagen.

OPT-2  Config = pydantic-settings v2. Importare `from app.config import settings`. MAI os.environ[] diretto in nessun modulo.

OPT-3  PDF Template = Jinja2. File template in templates/dispensa.html. MAI f-string .format() per HTML lungo.
