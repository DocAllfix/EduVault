Strategia merge prima del deploy Railway/Vercel — chiarimento veloce

═══════════════════════════════════════════════════════════════════
STATO ATTUALE GITHUB
═══════════════════════════════════════════════════════════════════

Ho pushato 2 commit consolidati su branch `fix/31-pipeline-surgery`:
  - 8e50b3b fix(31.5-8 + 32): pipeline scaling + diagrammi + refinement M1
  - 66dd1e8 chore: cleanup pre-deploy (docs/handoffs + .gitignore + vercel.json)

PR creata in DRAFT: https://github.com/DocAllfix/EduVault/pull/1
  fix/31-pipeline-surgery → main

Stato `main` su GitHub: vecchio, non aggiornato dai miei fix #30-32.
Source of truth attuale del lavoro = `fix/31-pipeline-surgery`.

═══════════════════════════════════════════════════════════════════
DOMANDA TECNICA DEPLOY
═══════════════════════════════════════════════════════════════════

Devo configurare Railway (backend) e Vercel (frontend) per puntare
al branch GitHub. Tre opzioni:

OPZIONE A — Mergio PR #1 a main PRIMA del deploy
  - Tolgo Draft + merge (squash o no)
  - Railway/Vercel puntano a `main` → deploy production
  - Pro: storia pulita, main = produzione canonica
  - Contro: serve review (chi la fa? te o salto?)

OPZIONE B — Deploy direttamente da branch `fix/31-pipeline-surgery`
  - Railway/Vercel puntano al branch `fix/...`
  - Demo cliente live da branch
  - Pro: nessuna decisione merge ora, demo live più veloce
  - Contro: branch `fix/...` come fonte produzione è inusuale

OPZIONE C — Squash merge IMMEDIATO (no review formale)
  - `gh pr merge 1 --squash --delete-branch`
  - Pro: storia pulita E veloce
  - Contro: nessuno revisiona formalmente la PR
  - NB: siamo solo io + tu + utente, nessun team formale

═══════════════════════════════════════════════════════════════════
COSA AVEVI DETTO TU NELLA REVIEW DEPLOY (G1+G2)
═══════════════════════════════════════════════════════════════════

G1 commit atomici → OK FATTO (2 commit consolidati, OPZIONE B
   accettata)
G2 "Pusha subito, PR aperta finale. Apri come Draft finché non sei
   pronto al merge. Cliente vede l'URL del production deploy"

Quindi avevi suggerito strategia A (merge a main = produzione), MA
non avevi specificato chi fa la review. Vuoi vedere il diff PR #1
(60 file changed, ~60 test verdi, 3 demo approvati) prima del merge,
oppure consideri il review fatto durante le 13 review iterative
delle ultime sessioni?

═══════════════════════════════════════════════════════════════════
DOMANDA SECCA
═══════════════════════════════════════════════════════════════════

DQ. Quale strategia preferisci?
  - A1: passi tu sulla PR #1, mi dai OK → squash merge → deploy main
  - A2: io tolgo Draft + squash merge senza tua review (review già
       fatta nelle 13 iterazioni precedenti) → deploy main
  - B:  deploy diretto da fix/31-pipeline-surgery (no merge ora,
       rinominiamo branch a main post-demo)

Aspetto 1 lettera (A1/A2/B) per procedere. Deploy gira ~3-4h dopo
la tua risposta.
