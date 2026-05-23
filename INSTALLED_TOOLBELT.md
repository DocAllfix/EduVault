# INSTALLED_TOOLBELT — Nexus EduVault

**Data snapshot:** 2026-05-23
**Scopo:** fotografia dello stato **realmente installato** al termine di Step B.3. Per le decisioni "quando e come usare ognuno" vedere `docs/SKILLS_PLAYBOOK.md`; per la mappa "perché abbiamo scelto questi" vedere `docs/TOOLBELT.md`.

> Verifica fatta: filesystem reale, `code --list-extensions`, `.mcp.json`, `.claude/skills/`, `.claude/commands/`. Nessuna voce è inferita: tutte sono presenti sul disco.

---

## MCP Server attivi — 6 (configurati in [.mcp.json](.mcp.json))

| Nome | Tipo | Sorgente | Quando si attiva |
|---|---|---|---|
| `github` | http | api.githubcopilot.com/mcp/ + `GITHUB_PERSONAL_ACCESS_TOKEN` | Operazioni su repo/PR/issue di `DocAllfix/EduVault` |
| `shadcn` | stdio | `npx -y shadcn@latest mcp` | Auto su presenza di `frontend/components.json` (FASE 6) |
| `playwright` | stdio | `npx -y @playwright/mcp@latest` | E2E test e ispezione frontend (FASE 6+); pesante in token |
| `postgres` | stdio | `uvx postgres-mcp --access-mode=restricted` + `DATABASE_URI` | Introspezione schema + EXPLAIN read-only (FASE 1+) |
| `codegraph` | stdio | `npx -y @colbymchenry/codegraph mcp` | Code knowledge graph locale; auto-reindex via REI-15 |
| `chrome-devtools` | stdio | `npx -y chrome-devtools-mcp@latest` | Inspect/debug browser reale (FASE 6+, Core Web Vitals FASE 7) |

## Skill installate — 21 (in [.claude/skills/](.claude/skills/), totale 8.2 MB)

### Design / Frontend (10)
| Skill | Fonte | Note |
|---|---|---|
| `impeccable` | pbakaus/impeccable | 15k★, anti-AI-slop di Paul Bakaus |
| `frontend-design` | anthropics/claude-code | Ufficiale Anthropic — direzione estetica deliberata |
| `ckm:ui-styling` | nextlevelbuilder/ui-ux-pro-max-skill | shadcn + Tailwind + Radix |
| `ckm:design-system` | idem | token primitive→semantic→component |
| `ckm:design` | idem | meta-skill (logo, CIP, mockup) |
| `ckm:brand` | idem | brand voice, identity, style guide |
| `ckm:slides` | idem | HTML presentations + Chart.js |
| `ckm:banner-design` | idem | bassa priorità per noi |
| `cdt-a11y-debugging` | ChromeDevTools/chrome-devtools-mcp | Accessibility |
| `cdt-debug-optimize-lcp` | idem | Core Web Vitals (FASE 7) |

### LangChain / LangGraph (6, da langchain-ai/langchain-skills)
| Skill | Quando attivarla |
|---|---|
| `langgraph-fundamentals` | **CRITICA in FASE 3** — StateGraph, Command, Send |
| `langgraph-cli` | `langgraph dev` debug locale |
| `langgraph-persistence` | AsyncPostgresSaver (BP §06B) |
| `langgraph-human-in-the-loop` | interrupt/resume |
| `langchain-fundamentals` | base messages/chains/prompts |
| `langchain-rag` | pattern RAG (BP §06) |

### Chrome DevTools compagne (4 oltre alle 2 già contate sopra)
| Skill | Note |
|---|---|
| `cdt-chrome-devtools` | base CDP |
| `cdt-chrome-devtools-cli` | risparmio token vs MCP |
| `cdt-memory-leak-debugging` | edge case |
| `cdt-troubleshooting` | edge case |

### Behavioral (1)
| Skill | Note |
|---|---|
| `karpathy-guidelines` | multica-ai (142k★) — rinforza REI-5/REI-8 |

## Slash command — 1 (in [.claude/commands/](.claude/commands/))

| Comando | Fonte | Uso |
|---|---|---|
| `/code-review` | anthropics/claude-code | PR review automatica con agenti |

## Estensioni VS Code installate user-wide — 12+ (rilevanti per il progetto)

Verificate live con `code --list-extensions`:

| ID | Ruolo |
|---|---|
| `ms-python.python` | Python language base (BP §1.1) |
| `ms-python.vscode-pylance` | IntelliSense Python |
| `ms-python.mypy-type-checker` | `mypy --strict` su `app/` (REI-6) |
| `ms-python.debugpy` | Debugger Python |
| `ms-python.vscode-python-envs` | venv management |
| `charliermarsh.ruff` | Lint + format Python (REI-6) |
| `bradlc.vscode-tailwindcss` | Tailwind 4 IntelliSense (BP §1.2, REI-11) |
| `dbaeumer.vscode-eslint` | ESLint per TS/TSX (FASE 6) |
| `ms-azuretools.vscode-docker` | Container Tools (BP §1.3) |
| `eamodio.gitlens` | Branch hygiene |
| `ms-playwright.playwright` | Playwright Test runner (FASE 6) |
| `vitest.explorer` | Vitest test runner (FASE 6) |
| `ms-ossdata.vscode-pgsql` | Client PostgreSQL (sostituto di `psql` locale) |
| `bierner.markdown-mermaid` | Mermaid preview ⚠️ issue #34607 |

Altre estensioni rilevate ma marginali per il progetto:
- `littlefoxteam.vscode-python-test-adapter` (era già presente; redundante con pytest nativo)

## Opzionali NON installati (decisione consapevole)

| Tool | Motivo di non installazione |
|---|---|
| `figma@claude-plugins-official` | Solo se cliente fornisce mockup Figma reali (SEZIONE 0 punto 32). Senza: overhead |
| `superpowers@obra` | Sovrapposizione con skill native già attive (brainstorming, executing-plans, TDD…). Decidere dopo FASE 1 |
| `psql` client locale | Si usa `docker exec` verso container pgvector (vedi ENV_REPORT.md) |
| CSS-in-JS / styled-components | **Scartato** — vedi SKILLS_PLAYBOOK §6 (incompatibile con Tailwind 4 + RSC, in maintenance mode) |

## Auto-comportamenti vincolanti

- **REI-12** — aggiorno il Project Status Tracker prima di ogni commit di FASE
- **REI-13** — nessun dominio hardcoded, mai
- **REI-14** — consulto `docs/SKILLS_PLAYBOOK.md` prima di task non banali
- **REI-15** — eseguo `npx @colbymchenry/codegraph index` automaticamente ai 4 trigger (auto-reindex)
- **Hook SessionStart** in `.claude/settings.json` — inietta briefing onboarding a ogni nuova sessione e dopo compattazione
