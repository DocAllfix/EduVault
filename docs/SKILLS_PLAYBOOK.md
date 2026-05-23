# SKILLS & MCP PLAYBOOK — Nexus EduVault

> **Scopo.** Questo è il manuale operativo che dice a Claude Code (e all'umano) **quando** attivare ciascuna skill/MCP/estensione e **come** combinarle per massimizzare la qualità su questo progetto specifico. Non è una lista di feature: è una mappa di decisione.
> **Stato installato.** Tutto ciò citato come `[INSTALLED]` esiste già nell'ambiente al 2026-05-23. Quello marcato `[TODO-UMANO]` richiede un'azione manuale dell'utente (le 4 skill ufficiali Anthropic via `/plugin install`).
> **Principio guida.** Se posso scegliere tra "fare alla cieca" e "consultare la skill/MCP corretta", scelgo SEMPRE il secondo (riduce hallucinazioni → REI-5).

---

## 1. Mappa Skill ↔ Fasi del Progetto

| Fase BP | Cosa stiamo facendo | Skill/MCP da attivare PRIMA di scrivere codice |
|---|---|---|
| **STEP A-B** (setup) | Inizializzazione, toolbelt | `github` MCP per repo/PR. `codegraph` non utile (file vuoti). |
| **FASE 0** Infrastruttura | docker-compose, Dockerfile | est. VS Code Docker; `github` MCP. `karpathy-guidelines` per evitare Dockerfile over-engineered. |
| **FASE 1** DB + Auth (§03 §04 §08) | Schema PostgreSQL+pgvector, JWT, modelli | `postgres` MCP (restricted) per introspect; Ruff/Mypy; `code-review` skill; `karpathy-guidelines` (alto rischio over-engineering su auth_service). **Re-indicizzare `codegraph` a fine fase.** |
| **FASE 2** Knowledge Base (§06 §13) | Ingestion PDF, RAG, embedding | `postgres` MCP; `langchain-skills` (RAG patterns); `codegraph` per impact su `knowledge_repo` quando lo modifichi. |
| **FASE 3** Agenti LangGraph (§05 §06B) | Research+Content agent, pipeline | **`langchain-skills` UFFICIALE** critico; **`codegraph` critico** (i 2 agenti referenziano models/services pesantemente); `karpathy-guidelines` per il circuit breaker INLINE (no over-engineering — REI tecnica pipeline v2.0); `chrome-devtools-mcp` no. |
| **FASE 4** Production Builder (§07) | PPTX, PDF, Audio TTS | `ckm:slides` (può ispirare PPTX template); `codegraph_impact` prima di toccare `production_builder.py` (è chiamato da generation_service); nessun MCP frontend. |
| **FASE 5** API+WebSocket (§09 §10) | Endpoint REST, WS, dependencies | `code-review` skill prima di ogni commit; `codegraph_callers` su `services/dependencies.py` (cuore della DI). |
| **FASE 6** Frontend shadcn-admin (§10) | UI Next.js+shadcn+Tailwind | **CRITICO**: `frontend-design` + `impeccable` + `ckm:ui-styling` + `ckm:design-system` + `shadcn` MCP + Tailwind IntelliSense. Vedi sezione 7. |
| **FASE 7** Deploy (§12) | VPS, SSL, monitoring | `github` MCP per release; `chrome-devtools-mcp` per Core Web Vitals pre-deploy; nessun MCP design. |

---

## 2. Skill installate localmente (`.claude/skills/`)

### `impeccable` v3.1.1  `[INSTALLED]`
**Autore:** Paul Bakaus (ex Google Developer Advocate, creatore jQuery UI) — 15k★+
**Scope dichiarato:** "design, redesign, shape, critique, audit, polish... websites, landing pages, dashboards, product UI, app shells, components, forms, settings, onboarding, empty states... UX review, visual hierarchy, IA, cognitive load, accessibility, performance, responsive, theming, anti-patterns, typography, fonts, spacing, layout, alignment, color, motion, micro-interactions, UX copy, error states, edge cases, i18n, reusable design systems or tokens".
**Quando attivarla nel nostro progetto:**
- ✅ Prima di creare o modificare QUALSIASI componente React in FASE 6 (REI-11)
- ✅ Quando faccio audit visivo di una pagina shadcn-admin adattata al branding C.F.P. Montessori
- ✅ Quando devo decidere typography/spacing/colore per una nuova vista
- ❌ NON usare per backend/non-UI (dichiarato dalla skill stessa)
**Come si combina:** Impeccable detta la *direzione* estetica; `ckm:ui-styling` traduce in classi Tailwind; `shadcn` MCP fornisce i componenti reali.

### `ckm:ui-styling`  `[INSTALLED]`
**Famiglia:** UI/UX Pro Max (nextlevelbuilder — 71k★, attivare con prudenza autore singolo)
**Scope:** "shadcn/ui components (built on Radix UI + Tailwind), Tailwind CSS utility-first styling... building user interfaces, implementing design systems, creating responsive layouts, adding accessible components (dialogs, dropdowns, forms, tables), customizing themes and colors, implementing dark mode".
**Quando attivarla:** **È letteralmente il nostro stack.** Sempre attiva in FASE 6 per componenti shadcn-admin. Allineata a REI-1.

### `ckm:design-system`  `[INSTALLED]`
**Scope:** "Token architecture (primitive→semantic→component), CSS variables, spacing/typography scales".
**Quando attivarla:**
- ✅ All'inizio di FASE 6, per definire i design token del branding C.F.P. Montessori (logo, palette, font) come variabili CSS sovrascritte in `:root` (REI-1)
- ✅ Quando creo o modifico `tailwind.config.ts`

### `ckm:brand`  `[INSTALLED]`
**Scope:** Brand voice, visual identity, messaging frameworks, asset management, style guides.
**Quando attivarla:**
- ✅ Quando arrivano i materiali del cliente (SEZIONE 0 punto 32: logo, palette HEX, font, claim)
- ✅ Per consistenza claim/footer/disclaimer nei PDF generati (BP §07)

### `ckm:slides`  `[INSTALLED]`
**Scope:** Strategic HTML presentations con Chart.js, design tokens, layout responsive, copywriting.
**Quando attivarla:**
- 🤔 **Valutare** per FASE 4 (Production Builder PPTX): il nostro builder usa `python-pptx`, non HTML, ma la **strategia narrativa di slide** della skill può ispirare i prompt del Content Agent (BP §05). NON sostituisce python-pptx.

### `ckm:design` e `ckm:banner-design`  `[INSTALLED]`
Meta-skill (logo, CIP, banner social). **Bassa priorità** per noi: non facciamo social/marketing assets.

### `karpathy-guidelines`  `[INSTALLED]`
**Autore:** Forrest Chang / `multica-ai` — derivata dalle osservazioni di Andrej Karpathy sui fallimenti tipici degli LLM in coding (142k★, gennaio 2026, MIT).
**Contenuto:** 30 righe di principi: think-before-coding (state assumptions, ask if unclear), simplicity-first (minimum code, no speculative features), surgical changes (don't refactor unrelated code), goal-driven (verifiable success criteria).
**Quando attivarla nel nostro progetto:**
- ✅ **Sempre** quando scrivo nuova logica in `app/services/` o `app/agents/` (alto rischio di over-engineering)
- ✅ Prima di una refactor: forza a fare modifiche chirurgiche, non riscritture
- ✅ Quando l'utente chiede una feature ambigua: la skill mi obbliga a presentare le interpretazioni invece di sceglierne una silenziosamente
- ❌ Non serve per task triviali (file vuoti, struttura cartelle, edit di config)
**Sovrapposizioni con i nostri REI:** rinforza REI-5 (no invenzioni, "don't assume"), REI-8 (atomicità, "minimum code"), e la sezione "In caso di dubbio" di CLAUDE.md ("GAP: <descrizione> e fermati"). **Non duplicare** — questa skill è un "rinforzo behaviorale" complementare ai REI, non li sostituisce.

---

## 3. MCP Server configurati (`.mcp.json`)

### `github` — GitHub MCP (HTTP, token-based)  `[INSTALLED]`
**Manutentore:** GitHub + Anthropic (Go, MIT).
**Quando usarlo:**
- ✅ Aprire/listare PR, leggere review, vedere issue
- ✅ Cercare codice nel repo `DocAllfix/EduVault` senza clonare branch
- ⚠️ **Default in sola lettura** (lo dico nel commento di `.mcp.json`): per write ops chiediamo conferma esplicita
**Variabile richiesta:** `GITHUB_PERSONAL_ACCESS_TOKEN` (ENV o `.env`).

### `shadcn` — shadcn/ui official MCP (stdio, npx)  `[INSTALLED]`
**Manutentore:** shadcn (ufficiale).
**Quando usarlo:**
- ✅ **Auto-attivo in FASE 6** quando esiste `frontend/components.json`
- ✅ Quando devo aggiungere un componente al template (legge il registry, suggerisce installazione corretta)
- ✅ Per consultare API esatte di un componente shadcn (evita di inventare prop — REI-5)

### `playwright` — Microsoft Playwright MCP (stdio, npx)  `[INSTALLED]`
**Manutentore:** Microsoft.
**Quando usarlo:**
- ✅ E2E test e ispezione frontend reale a partire da FASE 6
- ⚠️ **Costoso in token** (~114k per task vs ~27k con `@playwright/cli`): per run batch usare la CLI, non l'MCP
- ❌ NON usare per task backend o quando il frontend non è ancora servito

### `codegraph` — Code Knowledge Graph (stdio, npx)  `[INSTALLED]`
**Manutentore:** Colby McHenry (`@colbymchenry/codegraph` su npm, 11.8k★, MIT). Stack: tree-sitter + SQLite FTS5, 100% locale.
**Tool esposti:** `codegraph_context` (contesto comprensivo per un task), `codegraph_search` (symbol search), `codegraph_callers` / `codegraph_callees` (call graph), `codegraph_impact` (blast radius di una modifica).
**Numeri dichiarati:** 35% cheaper, 59% fewer tokens, 49% faster, 70% fewer tool calls vs Grep/Read ripetuti.
**Quando usarlo nel nostro progetto — questo è il punto:**
- ✅ **CRITICO da FASE 3 in poi**, quando i 70+ file pianificati in BP §14.1 cominciano davvero a riferirsi tra loro (pipeline → agenti → services → models)
- ✅ Prima di modificare un Pydantic model in `app/models/`: `codegraph_callers` mi dice tutti i file che lo importano (evita import-circulars + rotture silenziose)
- ✅ Prima di rifirmare una funzione: `codegraph_impact` calcola blast radius (REI-8: atomicità, REI-5: no rotture inventate)
- ✅ Quando esploro per la prima volta un'area sconosciuta: `codegraph_context` invece di 10 Read+Grep
- ❌ Inutile finché i file sono vuoti (cioè ORA, fino a FASE 1). Va **re-indicizzato** dopo ogni grossa ristrutturazione: `npx @colbymchenry/codegraph index`.
**Vincolo Step A.2 → ora:** abbiamo 48 file applicativi a 0 byte. Codegraph oggi indicizzerebbe il nulla. **Primo uso reale: fine FASE 1** (dopo schema DB + modelli Pydantic riempiti).

### `postgres` — Postgres MCP Pro by Crystal DBA (stdio, uvx, **restricted**)  `[INSTALLED]`
**Manutentore:** Crystal DBA (MIT, ~2.8k★). ⚠️ Ultima release v0.3.0 del 2025-05-16 (>6 mesi) — supporto pgvector NON confermato esplicitamente sulla landing.
**Quando usarlo:**
- ✅ Introspezione schema reale dopo applicare le migration di FASE 1 (BP §03)
- ✅ `EXPLAIN`/index health quando ottimizzo query RAG (BP §06)
- ❌ Mai per scrivere — è in `--access-mode=restricted` di proposito
**Fallback:** se non funziona col nostro pgvector → `docker exec -it nexus-postgres psql ...` (vedi ENV_REPORT).

---

## 4. Plugin Claude Code UFFICIALI — STATUS AGGIORNATO 2026-05-23

**Scoperta tecnica:** il comando `/plugin` **non esiste** nell'estensione VS Code di Claude Code (bug noto, issue Anthropic #8569, #8590, #58556). Quindi i plugin sono stati **estratti manualmente** dai loro repo sorgenti e installati come skill/MCP/command nel progetto. Status:

### `frontend-design` ✅ INSTALLATA come skill in `.claude/skills/frontend-design/`
**Origine:** `anthropics/claude-code/plugins/frontend-design/` clonata 2026-05-23. SKILL.md ufficiale Anthropic.
**Quando attivare:** **OBBLIGATORIA** all'inizio di ogni componente frontend in FASE 6. Si combina con Impeccable (Impeccable = audit/polish; frontend-design = decisione estetica iniziale).

### `langchain-skills` ✅ INSTALLATE 6 skill su 14 (le rilevanti)
**Origine:** `langchain-ai/langchain-skills` clonate 2026-05-23. Scelte SOLO quelle utili al nostro stack BP §05/§09 (pipeline 2 nodi + checkpoint Postgres):
- `langgraph-fundamentals` — StateGraph, nodi, edge, Command, Send, streaming, error handling. **CRITICA in FASE 3.**
- `langgraph-cli` — `langgraph dev`, debug locale
- `langgraph-persistence` — checkpointer (il nostro AsyncPostgresSaver in BP §06B)
- `langgraph-human-in-the-loop` — interrupt, resume (per pacing engine + circuit breaker)
- `langchain-fundamentals` — base messages/chains/prompts
- `langchain-rag` — pattern RAG per la nostra Knowledge Base (BP §06)
**Scartate (REI-8):** `deep-agents-*`, `swarm`, `managed-deep-agents`, `langchain-dependencies`, `langchain-middleware`, `framework-selection` — non rilevanti per la nostra pipeline a 2 nodi.

### `code-review` ✅ INSTALLATO come slash command in `.claude/commands/code-review.md`
**Origine:** `anthropics/claude-code/plugins/code-review/commands/code-review.md` clonato 2026-05-23.
**Quando usarlo:** lancio `/code-review` su un PR (REI-6, fine FASE). Comando ufficiale Anthropic.

### `chrome-devtools-mcp` ✅ INSTALLATO (MCP + 6 skill)
**MCP server:** aggiunto a `.mcp.json` come `chrome-devtools`.
**6 skill compagne in `.claude/skills/cdt-*`**: a11y-debugging, chrome-devtools (base), chrome-devtools-cli, debug-optimize-lcp, memory-leak-debugging, troubleshooting.
**Quando usarle:** da FASE 6 in poi quando il frontend è servito. `cdt-debug-optimize-lcp` e `cdt-a11y-debugging` saranno critiche pre-deploy FASE 7.

### `figma@claude-plugins-official` `[OPZIONALE]`
**Quando attivare:** **SOLO se** il cliente fornisce file Figma reali (SEZIONE 0 punto 32). Senza materiale Figma, NON installare — è puro overhead di tool.

### `superpowers` (obra / Jesse Vincent — Prime Radiant) `[OPZIONALE — VALUTARE]`
**Manutentore:** Jesse Vincent (Prime Radiant). 200k★ a maggio 2026, da ottobre 2025 (crescita molto rapida ma sostenuta — non spike artificiale). Marketplace: `/plugin install superpowers@obra` o equivalente (verificare lo slug ufficiale).
**Cosa è:** **non una skill, una metodologia**. Forza Claude a: brainstorming prima di scrivere → writing-plans per multi-step → executing-plans con review checkpoint → TDD vero red/green → YAGNI + DRY → subagent-driven-development con review tra step.
**Sovrapposizione con il tuo ambiente attuale:** le skill native che vedo già attive (`brainstorming`, `writing-plans`, `executing-plans`, `subagent-driven-development`, `test-driven-development`, `systematic-debugging`) **sono probabilmente derivate o ispirate da Superpowers**. Installandolo potresti avere duplicazioni o conflitti di workflow.
**Verdetto per Nexus EduVault:** **valutare DOPO** aver finito FASE 1. Se le skill native già attive bastano per imporre disciplina, non serve. Se servirà più rigore (es. quando arriverà la pipeline LangGraph in FASE 3, alto rischio di derive), installarlo allora. **Non installare ora alla cieca** — rispetta REI-8 (atomicità) e il principio della skill stessa.

---

## 5. Estensioni VS Code (12 installate user-wide)  `[INSTALLED]`

| Estensione | ID | Si attiva quando | Allineata a |
|---|---|---|---|
| Python | `ms-python.python` | Apro qualsiasi `.py` | BP §1.1 Python 3.12 |
| Pylance | `ms-python.vscode-pylance` | IntelliSense Python | type hints (REI-6) |
| Mypy Type Checker | `ms-python.mypy-type-checker` | save `.py` in `app/` | REI-6 (`mypy --strict`) |
| Ruff | `charliermarsh.ruff` | save `.py` | REI-6 (`ruff check`) |
| Tailwind CSS IntelliSense | `bradlc.vscode-tailwindcss` | save `.tsx`/`.css` in `frontend/` | REI-1, REI-11, BP §1.2 |
| ESLint | `dbaeumer.vscode-eslint` | save `.ts`/`.tsx` | REI-11 qualità frontend |
| Docker | `ms-azuretools.vscode-docker` | Apro `Dockerfile`/`docker-compose.yml` | BP §1.3 |
| GitLens | `eamodio.gitlens` | sempre | branch hygiene |
| Playwright Test | `ms-playwright.playwright` | Apro `*.spec.ts` | FASE 6 testing |
| Vitest | `vitest.explorer` | Apro `*.test.ts` | FASE 6 unit test |
| PostgreSQL | `ms-ossdata.vscode-pgsql` | Apro `*.sql` | BP §03 schema |
| Markdown Mermaid | `bierner.markdown-mermaid` | preview `.md` con ```mermaid | doc interna. ⚠️ Issue #34607: se vedo "File has not been read yet" durante un Edit, è lei → disabilitare |

---

## 6. Tecnologie SCARTATE (con motivo, per non rifare la domanda)

### styled-components
**Motivo del rifiuto (analisi 2026-05-23):**
1. In **maintenance mode dal marzo 2025** (lead maintainer cerca co-maintainer)
2. **Runtime CSS-in-JS** → trade-off di performance documentati con React Server Components di Next.js 15 (nostro stack)
3. shadcn-admin è **già Tailwind 4**: aggiungerlo creerebbe **due sistemi di styling in conflitto** (viola REI-1)
4. Nessuna skill ufficiale supporta CSS-in-JS — quelle che abbiamo (frontend-design, impeccable, ckm:ui-styling) sono pensate per Tailwind/shadcn
**Decisione:** scartato. Branding via `:root` CSS vars + `tailwind.config.ts` come da REI-1.

---

## 7. Regole d'oro per combinare gli strumenti

### Regola "design top-down" (FASE 6)
**Ordine di consultazione, sempre questo:**
1. **`ckm:design-system`** → cosa sono i token base (colori, spacing, type)?
2. **`frontend-design`** → quale direzione estetica? (Purpose/Tone/Constraints/Differentiation)
3. **`impeccable`** → audit del primo draft, correzioni di hierarchy/cognitive load
4. **`ckm:ui-styling`** → tradurre in classi Tailwind+shadcn
5. **`shadcn` MCP** → API esatta del componente da usare
6. **Tailwind IntelliSense + ESLint** → mentre scrivo
7. **`chrome-devtools-mcp` o Playwright MCP** → verificare nel browser

### Regola "no invenzioni" (REI-5)
Prima di scrivere uno schema SQL, una prop di componente shadcn, o un nodo LangGraph: consulto SEMPRE il MCP/skill corrispondente. Se manca → "GAP rilevato", non invento.

### Regola "budget token"
- `playwright` MCP è pesante (~114k/task). Per batch usare `@playwright/cli`.
- `postgres` MCP `restricted` è leggero. OK averlo sempre acceso in FASE 1-2.
- `chrome-devtools-mcp` accenderlo solo quando serve davvero (FASE 6+).

### Regola "controllo qualità fine FASE"
Prima di marcare ✅ su una FASE nel Project Status Tracker (REI-12):
1. `pytest` verde (REI-6)
2. `mypy --strict` ok (REI-6)
3. `ruff check` ok (REI-6)
4. **Re-indicizzo codegraph** con `npx @colbymchenry/codegraph index` (REI-15, trigger b)
5. Se la FASE ha toccato frontend: lancio `/code-review` + audit `impeccable`
6. Aggiorno Tracker (REI-12)
7. Propongo `git commit` all'umano (REI-6, no auto-commit)

### Regola "REI-15 auto-reindex codegraph"
Eseguo `npx @colbymchenry/codegraph index` (dalla root, in background quando posso) automaticamente, **senza richiesta esplicita dell'umano**, in 4 momenti:
- (a) prima volta che `app/` ha file non vuoti (fine FASE 1 plausibile)
- (b) fine di ogni FASE, prima dell'aggiornamento Tracker
- (c) dopo rinomine/spostamenti/aggiunte di moduli in `app/`
- (d) prima di un task "modifica/refactor/sostituisci" su file Python esistente

Se l'indicizzazione fallisce, annoto "indice stale" nel Tracker e segnalo all'umano.
