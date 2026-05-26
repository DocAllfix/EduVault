"""SlideBuilderV2 — XML-level text substitution via python-pptx + lxml (MIT).

FASE 3 vast-hopping-sketch: risolve il GAP shape_map del SlideBuilder v1
(test E.03/E.04) che cercava placeholder PowerPoint canonici inesistenti nel
template Claude Design (solo AUTO_SHAPE). V2 lavora direttamente sulle shape
del layout, sostituendo il testo placeholder originale (es. "Formazione Generale
dei Lavoratori") con il contenuto LLM-generated.

Approccio: per ogni SlideType, mappiamo le shape semantiche (title/body/footer/
options/...) all'INDICE numerico dello shape nel layout — derivato da
``scripts/inspect_pptx_template.py`` su ``nexus_master.pptx``. La mappa è
hardcoded qui (deterministica, ~50 righe) invece che caricata da JSON: scelta
karpathy-guidelines (no astrazione prematura per single-use data).

Distinto da SlideBuilder v1 (deprecato non rimosso):
- v1 usa ``slide.placeholders`` API → fallisce su AUTO_SHAPE
- v2 usa ``slide.shapes[idx]`` + iterazione text_frame → funziona su qualsiasi shape

Sincronizzazione: il chiamante (``ProductionBuilder`` con ``asyncio.to_thread``)
mantiene il vincolo REI-3 ``Semaphore(1)``: python-pptx + lxml restano non
thread-safe, qui non cambiamo nulla.

Licenza pulita: codice nostro, ispirato al pattern OOXML standard Microsoft
(zip+xml manipulation). NESSUNA copia dal toolkit Anthropic skill `pptx`
(licenza proprietaria). Dipendenze: python-pptx (MIT) + lxml (BSD-like), già
in pyproject.toml.
"""

from __future__ import annotations

import copy
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog
from pptx import Presentation

from app.models.core import SlideType
from app.models.pipeline import SlideContent

logger = structlog.get_logger()


DEFAULT_TEMPLATE = Path("assets/templates/nexus_master_v2.pptx")
DEFAULT_OUTPUT_DIR = Path("output")
IMAGE_MISSING_FALLBACK = "[Immagine non disponibile]"


# Mapping SlideType → indice layout in nexus_master_v2.pptx (Claude Design rebrand)
# Order: TITLE, CONTENT_TEXT, CONTENT_IMAGE, DIAGRAM, QUIZ, CASE_STUDY, RECAP, CLOSING
DEFAULT_LAYOUT_MAP: dict[SlideType, int] = {
    SlideType.TITLE: 0,
    SlideType.CONTENT_TEXT: 1,
    SlideType.CONTENT_IMAGE: 2,
    SlideType.DIAGRAM: 3,
    SlideType.QUIZ: 4,
    SlideType.CASE_STUDY: 5,
    SlideType.RECAP: 6,
    SlideType.CLOSING: 7,
}


# Mapping per-layout: ruolo semantico → NOME shape nel layout v2 (Claude Design).
# I name sono canonici `nx_*` come da brief BRIEF_CLAUDE_DESIGN_TEMPLATE.md.
# Quando il backend scrive un ruolo, fa lookup `slide.shapes[?].name == nx_xxx`.
SHAPE_MAP: dict[SlideType, dict[str, str | None]] = {
    SlideType.TITLE: {
        "title": "nx_title",
        "subtitle": "nx_subtitle",
    },
    SlideType.CONTENT_TEXT: {
        "title": "nx_title",
        "body": "nx_body",
        "normative_ref": "nx_ref",
        "page_num": "nx_page",
    },
    SlideType.CONTENT_IMAGE: {
        "title": "nx_title",
        "body": "nx_body",
        "image_caption": "nx_caption",
        "normative_ref": "nx_ref",
        "page_num": "nx_page",
    },
    SlideType.DIAGRAM: {
        "title": "nx_title",
        "body": "nx_body",
        "diagram_caption": "nx_caption",
        "normative_ref": "nx_ref",
        "page_num": "nx_page",
    },
    SlideType.QUIZ: {
        "title": "nx_title",
        "option_a": "nx_option_a",
        "option_b": "nx_option_b",
        "option_c": "nx_option_c",
        "option_d": "nx_option_d",
        "correct_marker": "nx_correct_marker",
    },
    SlideType.CASE_STUDY: {
        "title": "nx_title",
        "situazione": "nx_situazione",
        "azione": "nx_azione",
        "risultato": "nx_risultato",
        "normative_ref": "nx_ref",
        "page_num": "nx_page",
    },
    SlideType.RECAP: {
        "title": "nx_title",
        # FIX #24 (2026-05-26): RECAP ha 5 shape separate per i bullet check
        # (nx_recap_text_710 ... 750), non una nx_body unica. Mappiamo `body`
        # alla prima shape: il SlideBuilder splitta il body in linee e
        # distribuisce sulle 5 shape.
        "body": "nx_recap_text_710",
        "recap_text_1": "nx_recap_text_710",
        "recap_text_2": "nx_recap_text_720",
        "recap_text_3": "nx_recap_text_730",
        "recap_text_4": "nx_recap_text_740",
        "recap_text_5": "nx_recap_text_750",
        # FIX #27.2: checkmark "✓" per riga — azzerati se la riga non è usata
        "recap_check_1": "nx_recap_checkmark_710",
        "recap_check_2": "nx_recap_checkmark_720",
        "recap_check_3": "nx_recap_checkmark_730",
        "recap_check_4": "nx_recap_checkmark_740",
        "recap_check_5": "nx_recap_checkmark_750",
        "module_ref": "nx_module_ref",
        "page_num": "nx_page",
    },
    SlideType.CLOSING: {
        "title": "nx_title",
        "tagline": "nx_tagline",
    },
}


@dataclass
class BuildReport:
    """Per-build counters for diagnostics."""

    slides_built: int = 0
    shapes_written: int = 0
    images_inserted: int = 0
    image_fallbacks: int = 0
    warnings: list[str] = field(default_factory=list)


def _is_local_path(value: str | None) -> bool:
    """True iff ``value`` is a non-empty local file path on disk."""
    if not value:
        return False
    lowered = value.lower()
    if lowered.startswith(("http://", "https://", "file://", "ftp://")):
        return False
    return os.path.isfile(value)


def _clean_caption(query: str | None) -> str:
    """Turn an image query into a human caption — no "[ ]" placeholder syntax.

    FIX #25 (2026-05-26): empty query → empty caption (blank shape, never a
    "[ immagine ]" stub). Otherwise capitalise the first letter and trim, so
    a real photo reads as "Cassetta primo soccorso", not "[ cassetta ... ]".
    """
    q = (query or "").strip()
    if not q:
        return ""
    return q[0].upper() + q[1:]


import re as _re

# FIX #27.2: marker testuali dei placeholder del template v2. Qualsiasi shape
# il cui testo inizia con uno di questi (o con '[') e che NON è stato riscritto
# va azzerato a fine render, così non resta MAI un placeholder visibile.
_PLACEHOLDER_MARKERS: tuple[str, ...] = (
    "Testo sezione",
    "Titolo Slide",
    "Primo punto",
    "Secondo punto",
    "Terzo punto",
    "Quarto punto",
    "Quinto punto",
    "Sottotitolo",
    "Didascalia",
    "Cosa hai imparato",
    "AUTO_SHAPE",
)
# Etichette DECORATIVE fisse del template (band, label sezione, checkmark): NON
# toccare — fanno parte del design, non sono placeholder di contenuto.
_DECORATIVE_SHAPE_NAMES: frozenset[str] = frozenset({
    "nx_recap_band_label", "nx_case_band_label",
    "nx_case_label_situazione", "nx_case_label_azione", "nx_case_label_risultato",
})


def _parse_case_study_sections(body: str) -> list[str]:
    """Split a CASE_STUDY body into [situazione, azione, risultato].

    Cascade: (1) '---' separator (the prompt-mandated format), (2) labelled
    sections "Situazione:/Azione:/Risultato:", (3) newline. Always returns the
    cleaned non-empty pieces in order. Label prefixes are stripped so the
    rendered text reads "un operaio salda…" not "Situazione: un operaio…"
    (the template already shows the SITUAZIONE/AZIONE/RISULTATO labels).
    """
    body = (body or "").strip()
    if not body:
        return []

    if "---" in body:
        parts = [p.strip() for p in body.split("---")]
    else:
        # Try labelled sections (case-insensitive) anywhere in the text.
        label_re = _re.compile(
            r"(?im)^\s*(situazione|azione|risultato|decisione|esito)\s*[:\-]\s*"
        )
        if label_re.search(body):
            # Split keeping the text after each label.
            chunks = _re.split(r"(?im)^\s*(?:situazione|azione|risultato|decisione|esito)\s*[:\-]\s*", body)
            parts = [c.strip() for c in chunks if c.strip()]
        else:
            parts = [ln.strip() for ln in body.split("\n")]

    # Strip a leading inline label if still present (e.g. "Situazione: ...").
    cleaned: list[str] = []
    for p in parts:
        p = _re.sub(
            r"^\s*(situazione|azione|risultato|decisione|esito)\s*[:\-]\s*",
            "", p, flags=_re.IGNORECASE,
        ).strip()
        if p:
            cleaned.append(p)
    return cleaned


def _blank_layout_placeholder_text(prs: Any) -> None:
    """FIX #27.7: svuota il testo placeholder degli shape NEI LAYOUT.

    Ogni slide eredita gli shape del proprio layout (showMasterSp). Se un layout
    ha `nx_title="Cosa hai imparato"`, quel testo appare SOTTO il titolo scritto
    nella slide → sovrapposizione. Svuotiamo i text-frame di tutti gli shape dei
    layout TRANNE le label decorative fisse (banda RIEPILOGO/CASO STUDIO, label
    sezione SITUAZIONE/AZIONE/RISULTATO, checkmark ✓) che devono restare.
    """
    keep = _DECORATIVE_SHAPE_NAMES | {
        "nx_recap_checkmark_710", "nx_recap_checkmark_720", "nx_recap_checkmark_730",
        "nx_recap_checkmark_740", "nx_recap_checkmark_750",
    }
    for layout in prs.slide_layouts:
        for sh in layout.shapes:
            if (sh.name or "") in keep:
                continue
            if sh.has_text_frame and sh.text_frame.text.strip():
                sh.text_frame.text = ""


def _blank_unwritten_placeholders(slide: Any) -> None:
    """FIX #27.2: azzera ogni text_frame ancora col placeholder del template.

    Garanzia anti-placeholder universale (decisione utente: "slide sempre piena,
    pulita, funzionale"). Scorre le shape della slide DOPO che i ruoli sono stati
    scritti: se un text_frame inizia con '[' o con un marker placeholder noto, e
    la shape NON è decorativa fissa, lo svuota. Non tocca shape già riscritte con
    contenuto reale (che non iniziano con i marker).
    """
    for shape in slide.shapes:
        name = shape.name or ""
        if name in _DECORATIVE_SHAPE_NAMES:
            continue
        if not shape.has_text_frame:
            continue
        text = shape.text_frame.text.strip()
        if not text:
            continue
        is_placeholder = text.startswith("[") or any(
            text.startswith(m) for m in _PLACEHOLDER_MARKERS
        )
        if is_placeholder:
            shape.text_frame.text = ""


def _set_shape_text(shape: Any, text: str) -> bool:
    """Replace text in a shape's text_frame preserving formatting of first run.

    Returns True if the write succeeded, False if the shape has no text_frame.

    FIX #21 (2026-05-25): aggiunto AUTO-FIT testo. Algoritmo MIT
    (Office-PowerPoint-MCP-Server). Calcola la dimensione font ottimale
    dato il numero di caratteri e le dimensioni del box (width, height),
    setta word_wrap=True e MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE come fallback.
    Garantisce min 10pt (leggibilità), max 32pt (titoli).
    """
    from pptx.enum.text import MSO_AUTO_SIZE
    from pptx.util import Pt

    if not shape.has_text_frame:
        return False
    tf = shape.text_frame
    tf.text = text
    # Auto-fit: stima font ottimale per evitare overflow
    try:
        # Stima n. righe necessarie dato word_wrap. Approx 60 char/riga a 18pt.
        n_chars = len(text)
        # box dimensions in EMU → punti (1 EMU = 1/12700 pt)
        box_w_pt = (shape.width or 0) / 12700
        box_h_pt = (shape.height or 0) / 12700
        # Calcola font basato su area disponibile vs caratteri
        # avg char width ≈ font_size * 0.55, line height ≈ font_size * 1.2
        # Numero linee stimate: n_chars * char_w / box_w; altezza richiesta: n_linee * line_h
        # Risolvendo: font ≈ sqrt(box_w * box_h / (n_chars * 0.55 * 1.2))
        if n_chars > 0 and box_w_pt > 0 and box_h_pt > 0:
            import math
            optimal = int(math.sqrt((box_w_pt * box_h_pt) / max(n_chars * 0.66, 1)))
            # Hard limits per leggibilità
            optimal = max(10, min(optimal, 32))
            for paragraph in tf.paragraphs:
                for run in paragraph.runs:
                    run.font.size = Pt(optimal)
        # Word-wrap + autosize come safety net
        tf.word_wrap = True
        tf.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
    except Exception as exc:
        logger.debug("autofit_failed", error=str(exc))
    return True


def _write_shape_by_role(
    slide: Any,
    layout_type: SlideType,
    role: str,
    text: str,
    report: BuildReport,
) -> None:
    """Scrive `text` nello shape del `role` nel `layout_type` cercando per NAME.

    Template v2 (Claude Design) usa shape names canonici `nx_*` invece di
    indici fissi. Più robusto a future modifiche del template.
    """
    role_map = SHAPE_MAP.get(layout_type, {})
    shape_name = role_map.get(role)
    if shape_name is None:
        return
    # Cerca per name nella slide (e nelle shape clonate dal layout)
    target_shape = None
    for shape in slide.shapes:
        if shape.name == shape_name:
            target_shape = shape
            break
    if target_shape is None:
        msg = f"shape name {shape_name!r} not found in layout {layout_type.value} role={role}"
        logger.warning("shape_missing", layout=layout_type.value, role=role, name=shape_name)
        report.warnings.append(msg)
        return
    if _set_shape_text(target_shape, text):
        report.shapes_written += 1
    else:
        logger.warning("shape_no_text_frame", layout=layout_type.value, role=role, name=shape_name)


class SlideBuilderV2:
    """XML-level slide builder via python-pptx shape iteration (FASE 3).

    Stesso contratto pubblico di SlideBuilder v1 (build / output_path) per
    drop-in replacement in ProductionBuilder.
    """

    def __init__(
        self,
        brand_config: dict[str, Any] | None = None,
        template_path: Path = DEFAULT_TEMPLATE,
        output_dir: Path = DEFAULT_OUTPUT_DIR,
        layout_map: dict[SlideType, int] | None = None,
    ) -> None:
        self.brand_config = brand_config or {}
        self.template_path = template_path
        self.output_dir = output_dir
        self.layout_map = layout_map or DEFAULT_LAYOUT_MAP

    # ─── Public API ───

    def build(
        self,
        slides: list[SlideContent],
        course: dict[str, Any],
        image_map: dict[int, str],
    ) -> str:
        """Build a PPTX from slides + image_map and return output path."""
        report = BuildReport()
        prs = Presentation(str(self.template_path))
        # FIX #27.7 (2026-05-26): svuota il testo placeholder DEGLI SHAPE NEI
        # LAYOUT (es. nx_title="Cosa hai imparato", nx_body, nx_recap_text_X...).
        # Causa bug "titolo sovrapposto": il layout mantiene i suoi shape con
        # testo placeholder, che PowerPoint EREDITA e mostra SOTTO il testo
        # scritto nella slide → due titoli sovrapposti. Svuotando i layout una
        # volta, l'eredità non porta testo. Le label decorative fisse
        # (RIEPILOGO, CASO STUDIO, SITUAZIONE...) restano (whitelist).
        _blank_layout_placeholder_text(prs)
        # Rimuovi le slide di esempio del template (se presenti)
        self._strip_template_example_slides(prs)
        total_pages = len(slides)

        # FIX #26 (2026-05-26): enumerate gives the GLOBAL position used as the
        # image_map key — slide.index is module-local and collides. page_num
        # also uses pos (slide.index repeated per module gave duplicate page
        # numbers like "32 / 493" fourteen times).
        for pos, slide in enumerate(slides):
            self._render_slide(prs, pos, slide, image_map, total_pages, report)

        output_path = self._compute_output_path(course)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        prs.save(output_path)
        logger.info(
            "pptx_built_v2",
            output=output_path,
            slides=report.slides_built,
            shapes_written=report.shapes_written,
            images_inserted=report.images_inserted,
            image_fallbacks=report.image_fallbacks,
            warnings=len(report.warnings),
        )
        return output_path

    # ─── Private helpers ───

    def _strip_template_example_slides(self, prs: Any) -> None:
        """Rimuove le eventuali slide di esempio dal template (non i layout)."""
        # nexus_master.pptx ha 0 slide e 8 layout — niente da rimuovere.
        # Ma se in futuro il template avrà slide demo, vanno via QUI.
        xml_slides = prs.slides._sldIdLst  # type: ignore[attr-defined]
        for sld_id in list(xml_slides):
            xml_slides.remove(sld_id)

    def _render_slide(
        self,
        prs: Any,
        pos: int,
        slide_content: SlideContent,
        image_map: dict[int, str],
        total_pages: int,
        report: BuildReport,
    ) -> None:
        layout_idx = self.layout_map.get(slide_content.slide_type)
        if layout_idx is None or layout_idx >= len(prs.slide_layouts):
            layout_idx = 1  # fallback CONTENT_TEXT
            report.warnings.append(
                f"slide {slide_content.index}: no layout for {slide_content.slide_type.value}, "
                f"falling back to CONTENT_TEXT"
            )
        layout = prs.slide_layouts[layout_idx]
        slide = prs.slides.add_slide(layout)
        report.slides_built += 1

        # ─── CRITICAL (FASE 3 + FIX #20 2026-05-25): clona SOLO le AUTO_SHAPE
        # testuali dal layout, NON le PICTURE (logo brand). Il logo resta come
        # eredità del layer layout/master e viene renderizzato automaticamente.
        # showMasterSp resta default (=1) → eredità ON, testo scritto sulle
        # nostre shape clonate copre il testo placeholder originale del layout.
        self._clone_layout_text_shapes_only(slide, layout)

        # ─── Speaker notes (sempre, per audio TTS) ───
        if slide_content.speaker_notes:
            slide.notes_slide.notes_text_frame.text = slide_content.speaker_notes

        page_num = f"{pos + 1} / {total_pages}"

        # ─── Branch per SlideType ───
        st = slide_content.slide_type
        if st == SlideType.TITLE:
            _write_shape_by_role(slide, st, "title", slide_content.title, report)
            # Subtitle: dal metadata corso (titolo + ore + normativa), NON dall'LLM
            # (TITLE non ha body per design FASE 1). Se normative_ref valorizzato,
            # lo usiamo come subtitle informativo.
            if slide_content.normative_ref and slide_content.normative_ref != "—":
                _write_shape_by_role(
                    slide, st, "subtitle", slide_content.normative_ref, report
                )

        elif st == SlideType.CONTENT_TEXT:
            _write_shape_by_role(slide, st, "title", slide_content.title, report)
            _write_shape_by_role(slide, st, "body", slide_content.body, report)
            if slide_content.normative_ref:
                _write_shape_by_role(
                    slide, st, "normative_ref", slide_content.normative_ref, report
                )
            _write_shape_by_role(slide, st, "page_num", page_num, report)

        elif st == SlideType.RECAP:
            # FIX #24 (2026-05-26): RECAP ha 5 shape separate per bullet check.
            # FIX #27.2: con i minimi (RECAP=5) il body ha 5 righe; ma se per
            # qualunque motivo ne arrivano meno, AZZERIAMO le righe + i checkmark
            # ✓ non usati così non restano spunte orfane.
            _write_shape_by_role(slide, st, "title", slide_content.title, report)
            body_lines = [ln.strip() for ln in (slide_content.body or "").split("\n") if ln.strip()]
            for i in range(5):
                if i < len(body_lines):
                    _write_shape_by_role(slide, st, f"recap_text_{i+1}", body_lines[i], report)
                else:
                    # riga non usata: svuota testo E nascondi il checkmark ✓
                    _write_shape_by_role(slide, st, f"recap_text_{i+1}", "", report)
                    _write_shape_by_role(slide, st, f"recap_check_{i+1}", "", report)
            _write_shape_by_role(slide, st, "page_num", page_num, report)
            _write_shape_by_role(
                slide, st, "module_ref", f"Modulo {slide_content.module_index + 1}", report
            )

        elif st == SlideType.CONTENT_IMAGE:
            _write_shape_by_role(slide, st, "title", slide_content.title, report)
            _write_shape_by_role(slide, st, "body", slide_content.body, report)
            # FIX #25 (2026-05-26): clean caption, NOT "[ query ]". The bracket
            # syntax read as a leftover placeholder (and the verify script
            # flagged it as such). A real photo gets a real, capitalised
            # caption; an empty query gets no caption at all (blank shape).
            _write_shape_by_role(
                slide, st, "image_caption",
                _clean_caption(slide_content.image.query),
                report,
            )
            _write_shape_by_role(
                slide, st, "normative_ref", slide_content.normative_ref, report
            )
            _write_shape_by_role(slide, st, "page_num", page_num, report)
            # Inserimento immagine (se path locale disponibile)
            self._maybe_insert_image(slide, pos, image_map, report)

        elif st == SlideType.DIAGRAM:
            _write_shape_by_role(slide, st, "title", slide_content.title, report)
            _write_shape_by_role(slide, st, "body", slide_content.body, report)
            # diagram caption è body in DIAGRAM (didascalia breve)
            _write_shape_by_role(slide, st, "diagram_caption", slide_content.body, report)
            _write_shape_by_role(
                slide, st, "normative_ref", slide_content.normative_ref, report
            )
            _write_shape_by_role(slide, st, "page_num", page_num, report)
            # Inserimento PNG diagramma renderizzato (se disponibile)
            self._maybe_insert_image(slide, pos, image_map, report)

        elif st == SlideType.QUIZ:
            _write_shape_by_role(slide, st, "title", slide_content.title, report)
            options = slide_content.quiz_options or []
            roles = ["option_a", "option_b", "option_c", "option_d"]
            for i, role in enumerate(roles):
                if i < len(options):
                    letter = chr(ord("A") + i)
                    _write_shape_by_role(slide, st, role, f"{letter}. {options[i]}", report)
            # Marker risposta corretta
            if slide_content.quiz_correct is not None and 0 <= slide_content.quiz_correct < 4:
                correct_letter = chr(ord("A") + slide_content.quiz_correct)
                _write_shape_by_role(
                    slide, st, "correct_marker", f"Risposta corretta: {correct_letter}", report
                )

        elif st == SlideType.CASE_STUDY:
            _write_shape_by_role(slide, st, "title", slide_content.title, report)
            # FIX #27.2: parsing robusto delle 3 sezioni. L'LLM a volte usa '---',
            # a volte etichette "Situazione:/Azione:/Risultato:", a volte newline.
            # Proviamo in cascata. Sezioni mancanti → AZZERIAMO il placeholder
            # ("Testo sezione azione.") invece di lasciarlo visibile.
            sections = _parse_case_study_sections(slide_content.body)
            roles_3 = ["situazione", "azione", "risultato"]
            for i, role in enumerate(roles_3):
                text = sections[i] if i < len(sections) else ""
                _write_shape_by_role(slide, st, role, text, report)
            _write_shape_by_role(
                slide, st, "normative_ref", slide_content.normative_ref, report
            )
            _write_shape_by_role(slide, st, "page_num", page_num, report)

        elif st == SlideType.CLOSING:
            _write_shape_by_role(slide, st, "title", slide_content.title or "Grazie", report)

        # FIX #27.2: garanzia anti-placeholder universale. Dopo aver scritto i
        # ruoli, azzera ogni text_frame ancora col testo placeholder del template
        # (es. "Testo sezione azione." non sovrascritto, "[ AUTO_SHAPE... ]" del
        # box immagine non riempito). Slide sempre pulita.
        _blank_unwritten_placeholders(slide)

    def _clone_layout_text_shapes_only(self, slide: Any, layout: Any) -> None:
        """Deep-copy SOLO gli AUTO_SHAPE testuali del layout — NO PICTURE.

        FIX #20 (2026-05-25): rispetto al precedente _clone_layout_shapes:
        - PICTURE shapes (logo brand 'Image 0') NON vengono clonate.
          Il logo resta come eredità del layer layout/master, visibile
          automaticamente perché showMasterSp default = 1.
        - Solo <p:sp> (AutoShape testuali) vengono clonate. Quando scriviamo
          testo via SHAPE_MAP indici, sovrascriviamo il testo placeholder del
          layout senza toccare il logo.

        Risultato: testo per-slide editabile + logo brand sempre visibile +
        banda rosa/footer fissi del layout sempre visibili.
        """
        from pptx.oxml.ns import qn

        slide_spTree = slide.shapes._spTree  # type: ignore[attr-defined]
        layout_spTree = layout.shapes._spTree  # type: ignore[attr-defined]

        # Rimuovi solo gli <p:sp> già copiati da add_slide (placeholders).
        # NON tocchiamo <p:pic> esistenti (non dovrebbero essercene, ma safe).
        for existing in list(slide_spTree):
            if existing.tag == qn("p:sp"):
                slide_spTree.remove(existing)

        # Clona SOLO <p:sp> dal layout. Le <p:pic> (logo) restano ereditate.
        for shape_el in layout_spTree:
            if shape_el.tag == qn("p:sp"):
                slide_spTree.append(copy.deepcopy(shape_el))

    def _maybe_insert_image(
        self,
        slide: Any,
        pos: int,
        image_map: dict[int, str],
        report: BuildReport,
    ) -> None:
        """FASE 4: inserisce l'immagine in image_map[pos] nel box dedicato.

        FIX #26 (2026-05-26): box selezionato PER NOME canonico
        (nx_image_box / nx_diagram_box) invece che con l'euristica fragile
        "shape più grande senza testo". L'euristica sceglieva nx_body (77in²
        > nx_image_box 50in²) quando il body era ancora vuoto al momento
        della selezione, lasciando l'immagine non inserita (54 fallback su
        101 chiamate nel corso #21). Il nome canonico è deterministico.
        """
        path = image_map.get(pos)
        if not _is_local_path(path):
            logger.warning("image_no_path", pos=pos, in_map=pos in image_map)
            report.image_fallbacks += 1
            return
        assert path is not None

        from pptx.util import Emu

        from app.services.image_service import fit_image_to_box

        # Box selection: prefer the canonical named box, fall back to the
        # largest non-PICTURE shape only if the name is absent.
        _IMAGE_BOX_NAMES = ("nx_image_box", "nx_diagram_box", "nx_image", "nx_diagram")
        best_box = None
        for sh in slide.shapes:
            if (sh.name or "") in _IMAGE_BOX_NAMES:
                best_box = sh
                break

        if best_box is None:
            # Fallback heuristic: largest AUTO_SHAPE that is NOT the logo PICTURE
            # and carries only placeholder-style text (starts with [ or ().
            best_area = 0
            for sh in slide.shapes:
                try:
                    w = int(sh.width or 0)
                    h = int(sh.height or 0)
                except Exception:
                    continue
                area = w * h
                if sh.shape_type is not None and "PICTURE" in str(sh.shape_type):
                    continue
                if area < int(2.0 * 914400) ** 2:
                    continue
                if sh.has_text_frame:
                    text = sh.text_frame.text.strip()
                    if text and not (text.startswith("[") or text.startswith("(")):
                        continue
                if area > best_area:
                    best_area = area
                    best_box = sh

        if best_box is None:
            logger.warning("image_no_box", pos=pos, shapes=[sh.name for sh in slide.shapes])
            report.image_fallbacks += 1
            return

        pic_shape = best_box
        left, top = pic_shape.left, pic_shape.top
        width, height = pic_shape.width, pic_shape.height

        # Fit-to-box: converto EMU → px (~96 dpi: 914400 EMU = 1 inch = 96px)
        box_w_px = max(1, int(width / 914400 * 96))
        box_h_px = max(1, int(height / 914400 * 96))
        fitted_path = fit_image_to_box(path, box_w_px, box_h_px)

        # Rimuovo il placeholder PICTURE e inserisco l'immagine fitted stessa box
        try:
            pic_el = pic_shape._element  # type: ignore[attr-defined]
            pic_el.getparent().remove(pic_el)
            slide.shapes.add_picture(
                fitted_path, Emu(left), Emu(top), width=Emu(width), height=Emu(height)
            )
            report.images_inserted += 1
        except Exception as exc:
            logger.warning("image_insert_failed", pos=pos, error=str(exc))
            report.image_fallbacks += 1

    def _compute_output_path(self, course: dict[str, Any]) -> str:
        course_id_raw = str(course.get("id") or course.get("course_type") or "course")
        # Strip path separators per sicurezza
        course_id = course_id_raw.replace("/", "_").replace("\\", "_")
        return str(self.output_dir / f"{course_id}.pptx")
