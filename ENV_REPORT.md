# ENV_REPORT — Nexus EduVault (Step B.1)

**Generato:** 2026-05-23
**Host:** DESKTOP-Q7022D1 — Windows 11 Pro 10.0.26200 (x86_64)
**Shell di rilevamento:** Git Bash (MINGW64) + PowerShell
**CPU logiche:** 8 — **RAM totale:** 15.81 GB — **RAM libera:** 3.19 GB
**Riferimento versioni:** BLUEPRINT §1.1 (Stack Backend), §1.2 (Frontend), §1.3 (Infrastruttura)

> Nota di fedeltà: le versioni sono riportate ESATTAMENTE come restituite dall'ambiente.
> Alcune (Docker 29, Compose v5, Node v24) risultano più recenti delle baseline tipiche;
> non sono state alterate. Versioni superiori al minimo §1.1 soddisfano il vincolo `≥`.

---

## 1. Versioni rilevate vs richieste (BP §1.1 / §1.2 / §1.3)

| Strumento | Rilevato | Richiesto (BP) | Esito |
|---|---|---|---|
| Python | 3.12.10 | 3.12 | ✅ OK |
| Docker | 29.4.0 | presente (§1.3) | ✅ OK |
| Docker Compose | v5.1.1 | presente (§1.3) | ✅ OK |
| psql (client locale) | non installato | — (non in §1.1) | ⚠️ Non bloccante — si usa `docker exec` verso il container `pgvector/pgvector:pg16` |
| git | 2.53.0.windows.1 | presente | ✅ OK |
| Node.js | v24.11.1 | per Next.js 15.x (§1.2, FASE 6) | ✅ Presente (≥ richiesto) |
| npm | 11.6.2 | con Node | ✅ OK |
| VS Code CLI (`code`) | 1.118.1 | disponibile | ✅ OK |

### Stack runtime (non installati localmente — vivono nei container / venv, NON oggetto di questo check)
Le librerie Python di §1.1 (FastAPI ≥0.111, LangGraph ≥0.2, asyncpg ≥0.29, python-pptx ≥0.6.23,
cairosvg ≥2.7, WeasyPrint ≥61, Pydantic v2 ≥2.7, structlog ≥24.1, tenacity ≥8.2, slowapi ≥0.1.9,
psutil ≥5.9, httpx ≥0.27, Pillow ≥10.0, pdfplumber ≥0.11, bcrypt ≥4.1, pyotp ≥2.9) e PostgreSQL 16
+ pgvector NON sono strumenti di sistema: saranno installati via `pyproject.toml` (venv) e via immagine
Docker `pgvector/pgvector:pg16`. Verranno verificati in FASE 0/1, non in questo Step B.1.

---

## 2. Dipendenze mancanti o sotto versione minima

| Voce | Stato | Bloccante? |
|---|---|---|
| psql client locale | **MANCANTE** | ❌ No — accesso DB via `docker exec -it <container> psql ...` |

Nessuna dipendenza è **sotto** la versione minima §1.1. Nessun blocco per procedere a Step B.2.

---

## 3. Comandi di remediation suggeriti (NON eseguiti — solo proposta)

### psql client locale (opzionale, comodità di debug)
Non necessario: lo stack usa PostgreSQL dentro Docker. Se si desidera comunque il client a riga di comando sull'host:

- **Windows (winget):**
  ```powershell
  winget install PostgreSQL.psql
  ```
- **Windows (Chocolatey):**
  ```powershell
  choco install postgresql16 --params '/Password:dummy' --no-progress
  ```
- **Debian/Ubuntu (apt):**
  ```bash
  sudo apt-get update && sudo apt-get install -y postgresql-client-16
  ```
- **macOS (brew):**
  ```bash
  brew install libpq && brew link --force libpq
  ```
- **Alternativa senza installare nulla (consigliata):**
  ```bash
  docker exec -it nexus-postgres psql -U nexus_admin -d nexus
  ```

### Tutto il resto
Nessuna remediation richiesta: Python 3.12, Docker, Docker Compose, git, Node, npm e VS Code CLI
soddisfano (o superano) i requisiti BP §1.1–§1.3.

---

## Note operative
- **RAM libera 3.19 GB** al momento del check: il build PPTX fa un memory-check (psutil, §1.1) prima di partire.
  La RAM totale (15.81 GB) supera il minimo VPS di §1.3 (8 GB). In dev locale, chiudere app pesanti se la RAM libera scende troppo durante un build.
- **Node v24** è ampiamente sufficiente per Next.js 15 (FASE 6). Nessuna azione prima di FASE 6.
- `uname` riportato dall'ambiente MINGW64 (Git Bash su Windows); `free -h`/`vm_stat` non esistono su Windows → memoria rilevata via PowerShell (`Win32_OperatingSystem`).
