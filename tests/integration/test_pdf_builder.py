"""PdfBuilder tests (FASE 4.4).

The Jinja2 template is exercised against deterministic Pydantic input
(``render_html``) — that's the OPT-3 substitution gate. The actual
WeasyPrint call is mocked: real PDF rendering requires GTK runtime
(libgobject/cairo/pango) which is present in the Docker image but not
on the Windows dev host. The PDF binary output is best validated in CI
on Linux (debt tracked in VERIFICATION_DEBT.md #R12).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# WeasyPrint requires GTK runtime (libgobject/cairo/pango) which is present
# in the Docker image but not on the Windows dev host. Inject a stub so the
# lazy `import weasyprint` inside PdfBuilder.build() resolves to a mock
# without crashing. Tests can then patch ``weasyprint.HTML`` normally.
if "weasyprint" not in sys.modules:  # pragma: no cover
    _stub = MagicMock()
    sys.modules["weasyprint"] = _stub

from app.builders.pdf_builder import (  # noqa: E402
    DEFAULT_PRIMARY,
    DEFAULT_SECONDARY,
    DEFAULT_TEMPLATES_DIR,
    PdfBuilder,
    _group_slides_by_module,
    _slide_to_dict,
)
from app.models.core import SlideType
from app.models.pipeline import ImageStrategy, SlideContent


# ─────────────── helpers ───────────────


def _slide(
    index: int,
    *,
    module_index: int = 0,
    stype: SlideType = SlideType.CONTENT_TEXT,
    title: str = "Titolo slide",
    body: str | None = None,
    normative_ref: str = "Art. 1, DM 388/2003",
    speaker_notes: str | None = None,
    quiz_options: list[str] | None = None,
    quiz_correct: int | None = None,
) -> SlideContent:
    """FASE 1 vast-hopping: delega a make_slide centralizzato."""
    from tests._helpers import make_slide

    overrides: dict[str, object] = {
        "index": index,
        "module_index": module_index,
        "normative_ref": normative_ref,
    }
    if title != "Titolo slide":
        overrides["title"] = title
    if body is not None:
        overrides["body"] = body
    if speaker_notes:
        overrides["speaker_notes"] = speaker_notes
    if quiz_options is not None:
        overrides["quiz_options"] = quiz_options
    if quiz_correct is not None:
        overrides["quiz_correct"] = quiz_correct
    return make_slide(stype, **overrides)


@pytest.fixture
def builder(tmp_path: Path) -> PdfBuilder:
    return PdfBuilder(
        brand_config={"palette": {"primary": "#aa0000", "secondary": "#00aa00"}},
        templates_dir=DEFAULT_TEMPLATES_DIR,
        output_dir=tmp_path,
    )


# ─────────────── 1. _group_slides_by_module (pure) ───────────────


def test_group_slides_creates_one_entry_per_module_index() -> None:
    slides = [
        _slide(0, module_index=0),
        _slide(1, module_index=0),
        _slide(2, module_index=1),
        _slide(3, module_index=2),
    ]
    modules = _group_slides_by_module(slides)
    assert [m["index"] for m in modules] == [0, 1, 2]
    assert [len(m["slides"]) for m in modules] == [2, 1, 1]


def test_group_slides_preserves_order_within_module() -> None:
    s_a = _slide(0, module_index=0, title="Prima")
    s_b = _slide(1, module_index=0, title="Seconda")
    modules = _group_slides_by_module([s_a, s_b])
    assert [s["title"] for s in modules[0]["slides"]] == ["Prima", "Seconda"]


def test_group_slides_empty_input_returns_empty() -> None:
    assert _group_slides_by_module([]) == []


def test_slide_to_dict_exposes_slide_type_value_as_string() -> None:
    d = _slide_to_dict(_slide(0, stype=SlideType.QUIZ))
    assert d["slide_type_value"] == "QUIZ"
    assert isinstance(d["slide_type_value"], str)


# ─────────────── 2. Constructor ───────────────


def test_constructor_raises_if_templates_dir_missing(tmp_path: Path) -> None:
    missing = tmp_path / "no_templates"
    with pytest.raises(FileNotFoundError, match="Templates dir not found"):
        PdfBuilder(templates_dir=missing, output_dir=tmp_path)


def test_constructor_raises_on_missing_template_name(tmp_path: Path) -> None:
    # Existing dir but template file not there → Jinja2 raises TemplateNotFound
    from jinja2 import TemplateNotFound

    fake_dir = tmp_path / "fake_templates"
    fake_dir.mkdir()
    with pytest.raises(TemplateNotFound):
        PdfBuilder(templates_dir=fake_dir, output_dir=tmp_path)


# ─────────────── 3. render_html — Jinja2 deterministic ───────────────


def test_render_html_includes_course_title_and_metadata(
    builder: PdfBuilder,
) -> None:
    course = {
        "id": "c1",
        "title": "Primo Soccorso Gruppo B/C",
        "duration_hours": 4,
        "target": "discente",
    }
    slides = [_slide(0)]
    html = builder.render_html(slides, course)
    assert "Primo Soccorso Gruppo B/C" in html
    assert "Durata: 4h" in html
    assert "discente" in html


def test_render_html_renders_one_module_section_per_module(
    builder: PdfBuilder,
) -> None:
    slides = [
        _slide(0, module_index=0, title="Slide M0"),
        _slide(1, module_index=1, title="Slide M1"),
        _slide(2, module_index=2, title="Slide M2"),
    ]
    html = builder.render_html(slides, {"id": "c1", "title": "X"})
    assert "Modulo 1" in html  # module_index 0 → "Modulo 1"
    assert "Modulo 2" in html
    assert "Modulo 3" in html


def test_render_html_includes_normative_ref_when_present(
    builder: PdfBuilder,
) -> None:
    slides = [_slide(0, normative_ref="Art. 36, D.Lgs 81/08")]
    html = builder.render_html(slides, {"id": "c1", "title": "X"})
    assert '<p class="normative-ref">Rif.: Art. 36, D.Lgs 81/08</p>' in html


def test_render_html_omits_normative_ref_when_empty(
    builder: PdfBuilder,
) -> None:
    slides = [_slide(0, normative_ref="")]
    html = builder.render_html(slides, {"id": "c1", "title": "X"})
    assert 'class="normative-ref"' not in html


def test_render_html_includes_speaker_notes_when_present(
    builder: PdfBuilder,
) -> None:
    # FASE 1: speaker_notes valido (75-90 parole) + parola chiave "RSPP"
    notes = (
        "Sottolineare il ruolo determinante del RSPP come figura tecnica di "
        "supporto qualificato al datore di lavoro nella gestione preventiva "
        "dei rischi. Spiegare in dettaglio le competenze tecniche specifiche "
        "richieste dall'articolo trentadue del decreto legislativo ottantuno "
        "del duemilaotto, le responsabilità formalmente delegate al ruolo, il "
        "rapporto operativo quotidiano con dirigenti e preposti aziendali, "
        "l'integrazione strategica con il medico competente nel sistema "
        "completo di gestione della sicurezza aziendale moderna. Citare "
        "esempi pratici concreti di consulenza preventiva ai vari livelli."
    )
    slides = [_slide(0, speaker_notes=notes)]
    html = builder.render_html(slides, {"id": "c1", "title": "X"})
    assert 'class="speaker-notes"' in html
    assert "RSPP" in html


def test_render_html_omits_speaker_notes_when_empty(
    builder: PdfBuilder,
) -> None:
    """FASE 1: il validator strict rigetta speaker_notes vuote per CONTENT_TEXT.
    Per verificare l'omissione HTML, usiamo CLOSING che ha notes_min_words più
    permissivo, e patchiamo il campo a stringa vuota post-construction."""
    slide = _slide(0)
    # Bypass post-construction per simulare scenario edge "notes svuotate"
    object.__setattr__(slide, "speaker_notes", "")
    html = builder.render_html([slide], {"id": "c1", "title": "X"})
    assert 'class="speaker-notes"' not in html


def test_render_html_renders_quiz_block_with_options_and_correct_marker(
    builder: PdfBuilder,
) -> None:
    # FASE 1: QUIZ non ha body (è options-only)
    slides = [
        _slide(
            0,
            stype=SlideType.QUIZ,
            title="Quanti addetti al primo soccorso minimi in gruppo B?",
            quiz_options=["1", "2", "3", "Dipende"],
            quiz_correct=2,
        )
    ]
    html = builder.render_html(slides, {"id": "c1", "title": "X"})
    assert 'class="quiz"' in html
    assert "A. 1" in html
    assert "B. 2" in html
    assert "C. 3" in html
    assert "D. Dipende" in html
    # Correct option (index 2 → C) carries the .correct class + checkmark
    assert 'class="option correct"' in html
    assert "C. 3 &#10003;" in html or "C. 3 ✓" in html


def test_render_html_skips_quiz_block_for_non_quiz_slides(
    builder: PdfBuilder,
) -> None:
    slides = [
        _slide(
            0,
            stype=SlideType.CONTENT_TEXT,
            quiz_options=["A", "B"],  # set but type is not QUIZ
            quiz_correct=0,
        )
    ]
    html = builder.render_html(slides, {"id": "c1", "title": "X"})
    assert 'class="quiz"' not in html


def test_render_html_injects_brand_palette(builder: PdfBuilder) -> None:
    html = builder.render_html([_slide(0)], {"id": "c1", "title": "X"})
    # Palette set in the fixture must reach the CSS variables
    assert "#aa0000" in html
    assert "#00aa00" in html
    # Default palette must NOT appear when overridden
    assert DEFAULT_PRIMARY not in html
    assert DEFAULT_SECONDARY not in html


def test_render_html_falls_back_to_default_palette_when_missing(
    tmp_path: Path,
) -> None:
    no_brand = PdfBuilder(
        brand_config={},
        templates_dir=DEFAULT_TEMPLATES_DIR,
        output_dir=tmp_path,
    )
    html = no_brand.render_html([_slide(0)], {"id": "c1", "title": "X"})
    assert DEFAULT_PRIMARY in html
    assert DEFAULT_SECONDARY in html


def test_render_html_contains_page_counter_css(builder: PdfBuilder) -> None:
    """Footer page numbering is the BP §07.2 contract — verify the CSS rule
    survives Jinja2 templating intact."""
    html = builder.render_html([_slide(0)], {"id": "c1", "title": "X"})
    assert "@bottom-center" in html
    assert "counter(page)" in html


def test_render_html_lists_normative_references_in_cover(
    builder: PdfBuilder,
) -> None:
    course = {
        "id": "c1",
        "title": "X",
        "regulations": ["DM 388/2003", "Accordo Stato-Regioni 2011"],
    }
    html = builder.render_html([_slide(0)], course)
    assert "DM 388/2003" in html
    assert "Accordo Stato-Regioni 2011" in html


def test_render_html_escapes_html_in_user_content(builder: PdfBuilder) -> None:
    """autoescape must neutralize raw HTML coming from LLM/normative text."""
    slides = [_slide(0, body="<script>alert(1)</script>", title="X")]
    html = builder.render_html(slides, {"id": "c1", "title": "X"})
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


# ─────────────── 3b. TOC + header/footer brand (FASE 4 audit) ───────────────


def test_render_html_includes_toc_with_module_links(builder: PdfBuilder) -> None:
    """TOC section listing every module with internal anchor."""
    slides = [
        _slide(0, module_index=0, title="A"),
        _slide(1, module_index=1, title="B"),
        _slide(2, module_index=2, title="C"),
    ]
    html = builder.render_html(slides, {"id": "c1", "title": "Test"})
    assert 'class="toc"' in html
    assert "Indice" in html
    # One anchor per module
    assert 'href="#modulo-0"' in html
    assert 'href="#modulo-1"' in html
    assert 'href="#modulo-2"' in html


def test_render_html_body_module_headings_have_anchor_ids(
    builder: PdfBuilder,
) -> None:
    """Body <h1> must carry id="modulo-{index}" so TOC links resolve."""
    slides = [_slide(0, module_index=0), _slide(1, module_index=1)]
    html = builder.render_html(slides, {"id": "c1", "title": "Test"})
    assert 'id="modulo-0"' in html
    assert 'id="modulo-1"' in html


def test_render_html_toc_uses_target_counter_for_page_numbers(
    builder: PdfBuilder,
) -> None:
    """WeasyPrint resolves ``target-counter(attr(href), page)`` to the
    actual page of the target during PDF rendering."""
    html = builder.render_html(
        [_slide(0)], {"id": "c1", "title": "Test"}
    )
    assert "target-counter(attr(href), page)" in html


def test_render_html_page_header_contains_organization_and_title(
    builder: PdfBuilder,
) -> None:
    """Branded running header: @top-left = organization, @top-right = title."""
    html = builder.render_html(
        [_slide(0)],
        {
            "id": "c1",
            "title": "Corso Sicurezza",
            "organization": "C.F.P. Montessori",
        },
    )
    # Header CSS must reference the two slots and the dynamic content
    assert "@top-left" in html
    assert "@top-right" in html
    assert "C.F.P. Montessori" in html
    assert "Corso Sicurezza" in html


def test_render_html_first_page_has_empty_header(builder: PdfBuilder) -> None:
    """The cover page must NOT show the running header (it would visually
    clash with the cover title). Achieved via ``@page :first``."""
    html = builder.render_html([_slide(0)], {"id": "c1", "title": "T"})
    assert "@page :first" in html


def test_render_html_cover_renders_organization_when_present(
    builder: PdfBuilder,
) -> None:
    html = builder.render_html(
        [_slide(0)],
        {"id": "c1", "title": "T", "organization": "C.F.P. Montessori"},
    )
    # The cover section calls it out explicitly with <strong>
    assert "<strong>C.F.P. Montessori</strong>" in html


def test_render_html_cover_omits_organization_when_missing(
    builder: PdfBuilder,
) -> None:
    html = builder.render_html([_slide(0)], {"id": "c1", "title": "T"})
    assert "<strong>" not in html or "Montessori" not in html


# ─────────────── 4. build() — full path (WeasyPrint mocked) ───────────────


def test_build_writes_pdf_to_output_dir_with_safe_name(
    builder: PdfBuilder, tmp_path: Path
) -> None:
    slides = [_slide(0)]
    course = {"id": "course-abc-123", "title": "X"}

    fake_html = MagicMock()
    with patch("weasyprint.HTML", return_value=fake_html) as cls:
        out = builder.build(slides, course)

    out_path = Path(out)
    assert out_path.parent == tmp_path
    assert out_path.name == "course-abc-123_dispensa.pdf"
    # weasyprint.HTML must have been invoked with a non-empty rendered HTML
    args, kwargs = cls.call_args
    assert "string" in kwargs
    assert "<html" in kwargs["string"].lower()
    # write_pdf was called with our path
    fake_html.write_pdf.assert_called_once_with(str(out_path))


def test_build_strips_path_separators_from_course_id(
    builder: PdfBuilder, tmp_path: Path
) -> None:
    fake_html = MagicMock()
    with patch("weasyprint.HTML", return_value=fake_html):
        out = builder.build([_slide(0)], {"id": "ab/cd", "title": "X"})
    assert Path(out).name == "ab_cd_dispensa.pdf"
    assert Path(out).parent == tmp_path


def test_build_falls_back_to_course_when_id_missing(
    builder: PdfBuilder, tmp_path: Path
) -> None:
    fake_html = MagicMock()
    with patch("weasyprint.HTML", return_value=fake_html):
        out = builder.build([_slide(0)], {"title": "X"})
    assert Path(out).name == "course_dispensa.pdf"


def test_build_handles_multi_module_course_end_to_end(
    builder: PdfBuilder, tmp_path: Path
) -> None:
    slides = [
        _slide(0, module_index=0, title="Intro"),
        _slide(1, module_index=0, title="Concetti"),
        _slide(2, module_index=1, title="Casi pratici"),
        _slide(
            3,
            module_index=1,
            stype=SlideType.QUIZ,
            title="Verifica conoscenze del modulo casi pratici",
            quiz_options=["A1", "A2", "A3", "A4"],
            quiz_correct=1,
        ),
    ]
    course: dict[str, Any] = {"id": "multi-mod", "title": "Corso Multi"}

    captured: dict[str, str] = {}

    def fake_html_ctor(*_a: Any, **kw: Any) -> Any:
        captured["html"] = kw["string"]
        return MagicMock()

    with patch("weasyprint.HTML", side_effect=fake_html_ctor):
        builder.build(slides, course)

    rendered = captured["html"]
    assert "Modulo 1" in rendered
    assert "Modulo 2" in rendered
    assert "Casi pratici" in rendered
    assert 'class="quiz"' in rendered


# ─────────────── 5. structural meta-test (OPT-3) ───────────────


def test_pdf_builder_uses_jinja2_not_str_format() -> None:
    """OPT-3 invariant: PdfBuilder must NOT use str.format() for HTML
    templating. Verified by AST inspection (skips docstrings/comments so
    the rule is checked against real CODE, not narrative prose).
    """
    import ast
    import inspect

    from app.builders import pdf_builder

    src = inspect.getsource(pdf_builder)
    assert "FileSystemLoader" in src
    assert "Environment" in src

    # Strip module docstring + function/class docstrings before scanning
    tree = ast.parse(src)

    class _StripDocstrings(ast.NodeTransformer):
        def _strip(self, node: Any) -> Any:
            body = getattr(node, "body", None)
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                node.body = body[1:] or [ast.Pass()]
            return node

        def visit_Module(self, node: ast.Module) -> Any:
            self.generic_visit(node)
            return self._strip(node)

        def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
            self.generic_visit(node)
            return self._strip(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
            self.generic_visit(node)
            return self._strip(node)

        def visit_ClassDef(self, node: ast.ClassDef) -> Any:
            self.generic_visit(node)
            return self._strip(node)

    stripped = ast.unparse(_StripDocstrings().visit(tree))
    assert "PDF_TEMPLATE.format(" not in stripped, (
        "OPT-3 violation: f-string/str.format on a PDF_TEMPLATE blob "
        "found in production code"
    )
