# PPTX Render Fidelity Audit — F-NEXT Fase 3 (2026-06-02)

## Scopo

Verificare che il rendering client-side via `@aiden0z/pptx-renderer` (Step 4
F-STUDIO-UX) sia visivamente fedele al PPTX scaricabile, su tutti gli 8 layout
del template `nexus_master_v4.pptx`.

## Procedura

1. **Scarica PPTX** dal corso `5398fa8f` (Antincendio L1 4h, 342 slide, copre
   tutti i layout) o equivalente.
2. **Apri PPTX in PowerPoint Online / Desktop / LibreOffice Impress** (qualsiasi
   purché renderizzi fedele al file scaricato).
3. **Apri in webapp Course Studio** (PptxCanvasRenderer)
4. **Per ogni layout type sotto, screenshot side-by-side delle slide indicate e
   compila la tabella diff**.

## Layout coverage matrix (target 10 slide minimo)

Mapping da `app/builders/slide_builder.py:DEFAULT_LAYOUT_MAP`:

| Layout idx | slide_type | Esempi corso 5398fa8f (slide pos globale) |
|------------|------------|-------------------------------------------|
| 0 | TITLE | slide 1 (TITLE corso), slide 89 (TITLE M2) |
| 1 | CONTENT_TEXT | slide 2, 3, 5 (M0 body bullet) |
| 2 | CONTENT_IMAGE | slide 4 (Decreto Minicodice), slide 7 (Misure precauzionali) |
| 3 | DIAGRAM | (verificare presenza nel corso 5398fa8f) |
| 4 | QUIZ | slide 9, 10, 11, 12 (Quiz M0) |
| 5 | CASE_STUDY | (cercare nel deck) |
| 6 | RECAP | (cercare ultima slide modulo) |
| 7 | CLOSING | slide 342 (ultima del corso) |

## Tabella diff (da compilare durante audit)

> Compila ogni riga con OBSERVAZIONE + SEVERITÀ (basso/medio/alto) + WORKAROUND
> proposto. Severità alta = bloccare (utente vede preview molto diversa dal
> file scaricabile). Severità media/basso = documentare come limitazione nota.

| # | slide pos | layout | osservazione | severità | workaround |
|---|-----------|--------|--------------|----------|------------|
| 1 | 1 | TITLE | _da compilare_ | _ | _ |
| 2 | 2 | CONTENT_TEXT (corto) | _ | _ | _ |
| 3 | 3 | CONTENT_TEXT (medio) | _ | _ | _ |
| 4 | 5 | CONTENT_TEXT (lungo) | _ | _ | _ |
| 5 | 4 | CONTENT_IMAGE | _ | _ | _ |
| 6 | 7 | CONTENT_IMAGE | _ | _ | _ |
| 7 | _ | DIAGRAM | _ | _ | _ |
| 8 | 9 | QUIZ | _ | _ | _ |
| 9 | _ | CASE_STUDY | _ | _ | _ |
| 10 | 342 | CLOSING | _ | _ | _ |

## Aspetti da verificare per ogni slide

- **Font**: family, size, weight (Montserrat brand + fallback DejaVu)
- **Colore**: testo, sfondo, accent bar
- **Posizionamento**: margini, centratura, line-height bullets
- **Immagini**: aspect ratio mantenuto, risoluzione adeguata
- **Diagrammi SVG**: forme renderizzate, label visibili
- **Quiz options**: spaziatura A/B/C/D, indicator correct option
- **Bookend visual**: barra primary rosa #C82E6E, badge accent verde #769E2E
- **Footer**: normative_ref e page counter visibili e leggibili

## Diff tolleranza accettata

- Font fallback se Montserrat non installato lato libreria: ACCETTATO se leggibile
- Aspect immagine entro ±2%: ACCETTATO
- Posizione testo ±5px: ACCETTATO
- Hyperlink non clickable in render: ACCETTATO (è viewer, non editor)

## Diff da considerare REGRESSIONI (severità alta)

- Testo mancante (placeholder vuoto invece di bullets)
- Immagine non renderizzata (placeholder grigio invece di foto)
- Diagramma totalmente vuoto (SVG path non resolved)
- Quiz layout completamente scomposto
- Colore brand sostituito da grigio default
- Layout sovrapposti / testo fuori bordi

## Patch puntuali possibili

Se rendering specifico layout regredisce gravemente:
- `frontend/src/features/course-studio/components/pptx-canvas-renderer.tsx`:
  intercettare `onSlideError` per quel slide_type specifico → fallback a
  PNG backend (PdfPagePreview) per quella slide soltanto
- Documentare in `app/services/pptx_preview_service.py` patch settings
  `preview_source_per_layout` per slide_type problematico

## Output finale audit

Quando questo doc è compilato e diff severità alta = 0:
- Sign-off cliente
- Aggiornare `docs/VERIFICATION_DEBT.md` D-218 (fidelity audit done)
- Notazione in Tracker: "Render PPTX fedele verificato su 10 slide rappresentative"
