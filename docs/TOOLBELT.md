# Toolbelt suggerito da Claude Code (data: 2026-05-23)

> **Metodo & disclaimer.** Ricerca via web search/fetch il 2026-05-23. Filtro applicato: commit recente, autore identificabile, doc d'installazione chiara, licenza permissiva (MIT/Apache-2). Dove la data dell'ultimo commit/release **non** è verificabile con certezza dalla pagina, la marco `da verificare` invece di inventarla (REI-5). Nessun nome di server è stato inventato: tutti provengono da risultati di ricerca con URL. **Nulla è stato installato** — decisione finale all'umano.

---

## A) PostgreSQL + pgvector

### MCP servers
| Nome | URL repo | Manutentore | Ultimo commit/release | Motivo della scelta |
|---|---|---|---|---|
| Postgres MCP Pro | https://github.com/crystaldba/postgres-mcp | Crystal DBA (azienda) | Release v0.3.0 **2025-05-16** (⚠️ >6 mesi alla data odierna) | Schema introspection, EXPLAIN/plan analysis, index tuning (pglast+HypoPG), **Restricted Mode read-only** per sicurezza. MIT, ~2.8k★. Supporto estensioni (la pagina cita PostGIS/pgvector altrove ma non sulla landing) → da confermare per pgvector |

> Nota: il vecchio server di reference `modelcontextprotocol/servers/postgres` è stato **archiviato/deprecato** nel repo ufficiale → NON raccomandato.

### Skills Claude Code (se applicabile)
| Nome | URL | Note |
|---|---|---|
| Nessuna skill ufficiale dedicata trovata al 2026-05-23 | — | Procedere col MCP o con `docker exec psql` |

### Estensioni VS Code
| Nome | Marketplace ID | Manutentore | Motivo |
|---|---|---|---|
| PostgreSQL (Microsoft) | `ms-ossdata.vscode-pgsql` | Microsoft | Client/explorer schema, query editor — alternativa a psql locale (assente, vedi ENV_REPORT) |

---

## B) FastAPI scaffolding, OpenAPI lint, async testing

### MCP servers
| Nome | URL repo | Manutentore | Ultimo commit | Motivo |
|---|---|---|---|---|
| Nessun MCP affidabile e specifico per FastAPI al 2026-05-23. Procedere senza. | — | — | — | FastAPI espone già `/openapi.json`; lo scaffolding si fa con i tool Python standard |

### Skills Claude Code
| Nome | URL | Note |
|---|---|---|
| Nessuna skill ufficiale dedicata trovata | — | — |

### Estensioni VS Code + CLI
| Nome | Marketplace ID / pkg | Manutentore | Motivo |
|---|---|---|---|
| Python | `ms-python.python` | Microsoft | Base linguaggio backend (BP §1.1 Python 3.12) |
| Pylance | `ms-python.vscode-pylance` | Microsoft | Type checking/IntelliSense |
| pytest + pytest-asyncio + httpx (CLI, non estensione) | pkg PyPI | — | Async testing FastAPI (pattern ufficiale FastAPI docs); httpx già in §1.1 |
| Spectral (OpenAPI lint) | `stoplight.spectral` | Stoplight | Lint dello schema OpenAPI generato — opzionale |

---

## C) LangGraph (debug state machine, visualizzare grafo, checkpoint inspect)

### MCP servers
| Nome | URL repo | Manutentore | Ultimo commit | Motivo |
|---|---|---|---|---|
| Nessun MCP affidabile dedicato a LangGraph al 2026-05-23. Procedere senza. | — | — | — | Il debug si fa con LangGraph Studio (vedi sotto), non via MCP |

### Tool / Skills
| Nome | URL | Manutentore | Note |
|---|---|---|---|
| LangGraph Studio | https://docs.langchain.com/langgraph-platform/langgraph-studio | LangChain (azienda) | Agent IDE ufficiale: visualizza grafo, ispeziona stato per nodo, **time-travel su checkpoint** (BP §05/§09: 2 nodi + checkpointing PostgreSQL) |

### Estensioni VS Code
| Nome | Marketplace ID | Manutentore | Motivo |
|---|---|---|---|
| langgraph-visualizer | `Naveenkumarar.langgraph-visualizer` (da verificare ID esatto) | community (Naveenkumarar) | Rileva codice LangGraph e disegna nodi/edge in un pannello. ⚠️ community, autore singolo → valutare prima di affidarcisi |

---

## D) Python typing strict + ruff + mypy

### MCP servers
| Nome | URL repo | Manutentore | Ultimo commit | Motivo |
|---|---|---|---|---|
| Nessun MCP necessario per questo ambito. Procedere senza. | — | — | — | ruff/mypy sono CLI + estensioni, non servono via MCP |

### Estensioni VS Code + CLI
| Nome | Marketplace ID / pkg | Manutentore | Motivo |
|---|---|---|---|
| Ruff | `charliermarsh.ruff` | Astral (azienda) | Lint+format velocissimo (REI-6: `ruff check` deve passare) |
| Mypy Type Checker | `ms-python.mypy-type-checker` | Microsoft | `mypy --strict` su `app/` (REI-6) |

---

## E) Docker + docker-compose (lint, run-in-container)

### MCP servers
| Nome | URL repo | Manutentore | Ultimo commit | Motivo |
|---|---|---|---|---|
| Docker MCP (Docker Hub MCP / docker-mcp toolkit) | https://github.com/docker (catalogo MCP Docker) | Docker (azienda) | da verificare release | Docker pubblica un MCP toolkit ufficiale; valutare se serve davvero o se basta la CLI già presente (ENV_REPORT: Docker 29 + Compose v5) |

### Estensioni VS Code
| Nome | Marketplace ID | Manutentore | Motivo |
|---|---|---|---|
| Container Tools / Docker | `ms-azuretools.vscode-docker` | Microsoft | Gestione container/compose, build (BP §1.3, §2.1 Dockerfile + §02 docker-compose) |

---

## F) Git / GitHub (PR review, branch hygiene)

### MCP servers
| Nome | URL repo | Manutentore | Ultimo commit/release | Motivo |
|---|---|---|---|---|
| GitHub MCP Server (ufficiale) | https://github.com/github/github-mcp-server | **GitHub** (Go, in collaborazione con Anthropic) | Attivo nel 2026 (changelog 2026-01-28); 870 commit | 51 tool: `pull_request_read`/`pull_request_review_write`, issue, search_code. **`--read-only` flag** per sicurezza. MIT. Il più maturo per l'ambito |
| Git (reference) | https://github.com/modelcontextprotocol/servers (dir `git`) | MCP steering group | reference | Operazioni git locali read/search/manipulate — utile se non si vuole il server GitHub remoto |

### Estensioni VS Code
| Nome | Marketplace ID | Manutentore | Motivo |
|---|---|---|---|
| GitLens | `eamodio.gitlens` | GitKraken | Branch hygiene, blame, history |

---

## G) Anthropic API monitoring (token usage, cost)

### MCP servers
| Nome | URL repo | Manutentore | Ultimo commit | Motivo |
|---|---|---|---|---|
| Nessun MCP dedicato affidabile al 2026-05-23. Procedere senza. | — | — | — | Anthropic fornisce **Usage & Cost API** native, non serve un MCP |

### Tool ufficiali (non MCP)
| Nome | URL | Manutentore | Note |
|---|---|---|---|
| Usage & Cost API | https://platform.claude.com/docs/en/build-with-claude/usage-cost-api | Anthropic | Endpoint `/v1/organizations/cost_report` e `usage_report/messages` per token e costo per modello/workspace. Rilevante per il budget alert di SEZIONE 0 |
| Workspace "Claude Code" su Console | console Anthropic | Anthropic | Tracking costi centralizzato auto-creato all'auth |

---

## H) Markdown / Mermaid (per documentazione interna)

### MCP servers
| Nome | URL repo | Manutentore | Ultimo commit | Motivo |
|---|---|---|---|---|
| Nessun MCP necessario. Procedere senza. | — | — | — | Sono estensioni di preview, non serve MCP |

### Estensioni VS Code
| Nome | Marketplace ID | Manutentore | Ultimo aggiornamento | Motivo |
|---|---|---|---|---|
| Markdown Preview Mermaid Support | `bierner.markdown-mermaid` | Matt Bierner | v1.32.0 (feb 2026) | Render Mermaid nella preview Markdown. ⚠️ **Nota conflitto noto**: l'issue anthropics/claude-code #34607 segnala che abilitarla può rompere il diff Edit/Cascade con "File has not been read yet" → valutare con cautela |
| (alternativa) Mermaid built-in VS Code | — | Microsoft | 2026 | Funzionalità Mermaid ora **integrata** in VS Code recenti → potrebbe non servire l'estensione separata |

---

## I) [v4.0 SWAP-4] UI/UX Design & Frontend

### MCP servers / Plugin Claude Code
| Nome | URL | Manutentore | Ultimo agg. | Motivo |
|---|---|---|---|---|
| **Figma plugin (ufficiale)** | install: `claude plugin install figma@claude-plugins-official` — https://claude.com/plugins/figma | **Anthropic + Figma** | attivo 2026 (123k+ install ad apr 2026) | Legge design da Figma: componenti, design token, layout→codice. Esattamente lo SWAP-4. Include MCP server + Agent Skills |
| shadcn/ui MCP (ufficiale) | https://ui.shadcn.com/docs/mcp | shadcn (progetto ufficiale) | attivo 2026 | Browse/search/install componenti dal registry shadcn via linguaggio naturale. Allineato a REI-1 (frontend = shadcn-admin) e REI-11 |

### Estensioni VS Code
| Nome | Marketplace ID | Manutentore | Motivo |
|---|---|---|---|
| Tailwind CSS IntelliSense | `bradlc.vscode-tailwindcss` | Tailwind Labs (ufficiale) | Autocomplete classi, hover preview, lint (BP §1.2 TailwindCSS 4; REI-11 spacing/tipografia) |
| ESLint | `dbaeumer.vscode-eslint` | Microsoft | Qualità React/TS (FASE 6) |

> Per "React/Next.js best practices" non esiste un MCP affidabile dedicato al 2026-05-23: si usano doc ufficiali Next.js 15 + le skill del plugin Figma. Procedere senza MCP specifico.

---

## J) [v4.0 SWAP-4] Frontend Testing (Playwright, Vitest, RTL)

### MCP servers
| Nome | URL repo | Manutentore | Ultimo agg. | Motivo |
|---|---|---|---|---|
| **Playwright MCP (ufficiale)** | https://github.com/microsoft/playwright-mcp | **Microsoft** | attivo 2026 (early-2026 `@playwright/cli`) | Browser automation/E2E via accessibility snapshot, no vision model. Funziona out-of-the-box con Claude. ⚠️ alto consumo token via MCP (~114k/task) vs CLI (~27k) → considerare `@playwright/cli` |

### Estensioni VS Code + pkg
| Nome | Marketplace ID / pkg | Manutentore | Motivo |
|---|---|---|---|
| Playwright Test for VSCode | `ms-playwright.playwright` | Microsoft | Esecuzione/debug test E2E |
| Vitest | `vitest.explorer` | Vitest team | Unit test componenti React (FASE 6) |
| React Testing Library | pkg npm `@testing-library/react` | Testing Library (community consolidata) | Test componenti — libreria, non estensione. Nessun MCP dedicato: procedere come libreria |

---

## Raccomandazione di installazione

Ordine di priorità degli strumenti che **io (Claude Code) considero essenziali** per NON allucinare durante lo sviluppo di Nexus EduVault, ciascuno con il perché ancorato alla BLUEPRINT:

1. **GitHub MCP Server** (`github/github-mcp-server`, `--read-only` finché non serve scrivere) — serve perché tutto lo Step A/B passa da repo `DocAllfix/EduVault`; PR review e branch hygiene su un progetto che evolve a fasi (BP §15/§16 sprint). Maturità e manutenzione massime.
2. **Mypy Type Checker + Ruff (estensioni VS Code)** — REI-6 impone `mypy --strict` su `app/` e `ruff check` verde prima di ogni commit; averli inline evita di scoprire errori solo a fine task.
3. **Postgres MCP Pro** (in **Restricted/read-only mode**) — BP §03 (schema DB con pgvector/HNSW) e §06 (RAG): introspezione schema reale + EXPLAIN evitano che inventi colonne/indici (REI-5). ⚠️ verificare prima il supporto pgvector e la freschezza (release datata): se non confermato, ripiegare su `docker exec psql` (ENV_REPORT).
4. **Tailwind CSS IntelliSense** (`bradlc.vscode-tailwindcss`) — REI-1/REI-11: frontend = shadcn-admin su Tailwind 4 (BP §1.2); autocomplete/lint classi mantiene la qualità pixel-perfect e impedisce classi inesistenti.
5. **shadcn/ui MCP** (ufficiale) — REI-1: parto SEMPRE dal template shadcn; avere il registry componenti accessibile evita di inventare API di componenti in FASE 6 (BP §10 frontend).
6. **Figma plugin** (`figma@claude-plugins-official`) — SWAP-4: SOLO se il cliente fornisce file Figma (BP §16/SEZIONE 0 materiali); altrimenti rimandabile a FASE 6.
7. **Playwright MCP / `@playwright/cli`** (Microsoft) — SWAP-4 frontend testing E2E (BP §14 testing); preferire la CLI per il risparmio token. Necessario solo da FASE 6.
8. **Container Tools/Docker** (`ms-azuretools.vscode-docker`) — BP §1.3 + §02: build docker-compose riproducibile; comoda ma non bloccante (CLI già presente).
9. **LangGraph Studio** — BP §05/§09: utile per ispezionare i 2 nodi e i checkpoint PostgreSQL in FASE 3/5; non un MCP, tool a sé.
10. **Markdown Preview Mermaid** (`bierner.markdown-mermaid`) — solo documentazione interna; ⚠️ valutare il conflitto noto con il diff di Claude Code (issue #34607) prima di abilitarla.

**Ambiti senza MCP affidabile al 2026-05-23 (procedere senza):** FastAPI (b), Anthropic monitoring (g, usare API native), Markdown/Mermaid (h), React/Next best-practices (i, solo doc+skill).

---

## Addendum 2026-05-23 — Analisi del carosello `@sebastianhardy_` "OPERATOR NOTES 05.21"

Carosello da Instagram suggerisce 8+ repo. Analizzati 6 visibili, applicato filtro severo del TOOLBELT (autore identificabile, MIT/Apache, ultimo commit recente, **+ allineamento al nostro stack**).

| # | Repo | ⭐ | Verdetto Nexus EduVault | Motivo |
|---|---|---|---|---|
| 01 | `anthropics/claude-plugins-official` | 21.1k | ✅ già nel toolbelt | Da qui pesco i 4 plugin TODO |
| 02 | `colbymchenry/codegraph` | 11.8k | ✅ **AGGIUNTO** in `.mcp.json` | Riduce token/tool-call del 35-70%; critico dalla FASE 3 in poi sui 70+ file di BP §14.1 |
| 03 | `multica-ai/andrej-karpathy-skills` | 142k | ✅ **AGGIUNTO** come skill `karpathy-guidelines` | Rinforza REI-5/REI-8; importata SOLO come skill, mai sovrascritto il nostro CLAUDE.md |
| 04 | `dotnet/skills` | 2k | ❌ scartato | Stack C#/.NET, noi siamo Python (BP §1.1) |
| 05 | `obra/superpowers` | 200k | 🟡 **TODO-UMANO opzionale, valutare a fine FASE 1** | Cambia metodologia (TDD/YAGNI/subagent); sovrapposizione con skill native già attive (brainstorming, executing-plans, TDD…) — installare solo se serve più rigore |
| 07 | `ChromeDevTools/chrome-devtools-mcp` | 40.3k | ✅ già nel TOOLBELT come TODO-UMANO | Lo stesso che era già in raccomandazione #11 del TOOLBELT |

**Aggiornamenti applicati al PLAYBOOK:** sezione 1 (mappa fase↔tool) rivista con `codegraph` (da FASE 1) e `karpathy-guidelines` (da FASE 0); sezione 2 (skill) integrata con `karpathy-guidelines`; sezione 3 (MCP) integrata con `codegraph`; sezione 4 (TODO-UMANO) integrata con `superpowers` come opzionale.
